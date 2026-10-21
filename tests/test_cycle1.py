"""Testes do ciclo 1 de correção: circuit breaker, Retry-After, orçamento do upload, sanitização, PII e webhook."""

import base64
import hashlib
import json
import time
import traceback
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from typing import Any
from unittest import mock

import httpx
import pytest
import respx

from conftest import make_client, token_body
from twila_credicarro import (
    CreateCustomerRequest,
    CreateFinancingSimulationRequest,
    CreateProposalRequest,
    CreateWebhookRequest,
    CredicarroApiError,
    CredicarroAuthenticationError,
    CredicarroClientOptions,
    CredicarroRateLimitError,
    CredicarroResilienceOptions,
    CredicarroTimeoutError,
    CredicarroWebhookSignatureError,
    CustomerAddress,
    DepositAccount,
    DepositAccountType,
    DocumentFile,
    DocumentType,
    OccupationType,
    ProfessionalData,
    ProposalDocumentUpload,
    ProposalParticipant,
    UpsertCustomerRequest,
    WebhookAuthenticationType,
    WebhookType,
    compute_webhook_signature,
    get_pending_actions,
    parse_webhook_event,
    parse_webhook_payload,
    verify_webhook_authorization,
    verify_webhook_signature,
)
from twila_credicarro._internal.auth.access_token_provider import AccessTokenProvider
from twila_credicarro._internal.auth.credentials import TokenCredentials
from twila_credicarro._internal.masking import SecretStr, mask_cpf
from twila_credicarro._internal.resilience.resilience_pipeline import ResiliencePipeline

PROPOSAL_ID = "bea8d060-f93d-48eb-b6c4-45f64483cdd9"
MAX_BYTES = 10 * 1024 * 1024



def test_breaker_recovers_after_a_trial_that_ends_with_authentication_error(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    responses = iter([503, 503, 401, 401, 200, 200])
    route = mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(
        side_effect=lambda request: httpx.Response(next(responses), json={"id_proposta": PROPOSAL_ID})
    )
    client = make_client(
        max_retry_attempts=1,
        circuit_breaker_minimum_throughput=2,
        circuit_breaker_failure_ratio=0.5,
        circuit_breaker_break_duration_ms=300,
    )

    for _ in range(2):
        with pytest.raises(CredicarroApiError):
            client.proposals.get(PROPOSAL_ID)

    with pytest.raises(CredicarroTimeoutError, match="circuit breaker"):
        client.proposals.get(PROPOSAL_ID)
    assert route.call_count == 2

    time.sleep(0.4)

    with pytest.raises(CredicarroAuthenticationError):
        client.proposals.get(PROPOSAL_ID)

    assert client.proposals.get(PROPOSAL_ID).id == PROPOSAL_ID
    assert client.proposals.get(PROPOSAL_ID).id == PROPOSAL_ID
    client.close()


def test_breaker_trial_is_released_by_any_exception() -> None:
    options = CredicarroResilienceOptions(
        max_retry_attempts=1,
        circuit_breaker_minimum_throughput=2,
        circuit_breaker_break_duration_ms=50,
    )
    pipeline = ResiliencePipeline(options)

    def failing() -> Any:
        from twila_credicarro._internal.http.api_response import ApiResponse

        return ApiResponse(503, None, {})

    pipeline.execute(False, failing)
    pipeline.execute(False, failing)
    time.sleep(0.1)

    def explode() -> Any:
        raise RuntimeError("falha inesperada")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            pipeline.execute(False, explode)

    from twila_credicarro._internal.http.api_response import ApiResponse

    assert pipeline.execute(False, lambda: ApiResponse(200, None, {})).status_code == 200



def _connect_error() -> httpx.ConnectError:
    request = httpx.Request(
        "POST",
        "https://sdk-test.local/integration/v2/proposal",
        headers={"Authorization": "Bearer token-super-secreto"},
        content=b'{"cpf":"12345678909"}',
    )
    return httpx.ConnectError("conexão recusada", request=request)


def _formatted(error: BaseException) -> str:
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))


def test_network_failure_is_sanitized(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(side_effect=_connect_error())
    client = make_client(max_retry_attempts=2)

    with pytest.raises(CredicarroTimeoutError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert "ConnectError" in str(error.value)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    text = _formatted(error.value)
    assert "token-super-secreto" not in text
    assert "12345678909" not in text


def test_token_network_failure_is_sanitized_and_does_not_leak_the_secret(mock_router: respx.MockRouter) -> None:
    mock_router.post("v1/authentication/accesstoken").mock(side_effect=_connect_error())
    client = make_client(max_retry_attempts=2)

    with pytest.raises(CredicarroTimeoutError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert "test-client-secret" not in _formatted(error.value)


def test_secrets_are_masked_in_repr() -> None:
    credentials = TokenCredentials("meu-id", "meu-segredo")
    options = CredicarroClientOptions(client_id="meu-id", client_secret="meu-segredo")

    assert "meu-segredo" not in repr(credentials)
    assert "meu-segredo" not in str(credentials)
    assert "meu-segredo" not in repr(options)
    assert repr(SecretStr("abc")) == "'***'"
    assert SecretStr("abc") == "abc"
    with pytest.raises(TypeError):
        import pickle

        pickle.dumps(credentials)


def test_token_provider_does_not_expose_the_token_or_secret_in_repr() -> None:
    class Api:
        def generate(self, credentials: object) -> dict[str, Any]:
            return token_body("token-do-cache")

    provider = AccessTokenProvider(Api(), TokenCredentials("id", "segredo-x"))  # type: ignore[arg-type]
    provider.get_token()

    assert "token-do-cache" not in repr(provider)
    assert "token-do-cache" not in repr(provider._cached)
    assert "segredo-x" not in repr(vars(provider))



def test_retry_after_larger_than_the_budget_raises_rate_limit_without_waiting(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "3600"}, json={"tipo": "RateLimit"})
    )
    client = make_client()

    started = time.monotonic()
    with pytest.raises(CredicarroRateLimitError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert time.monotonic() - started < 2
    assert route.call_count == 1
    assert error.value.retry_after_ms == 3_600_000


@pytest.mark.parametrize("value", ["abc", "-5", "0", "nan", "inf", "1e999"])
def test_invalid_retry_after_falls_back_to_backoff(
    mock_router: respx.MockRouter, token_route: respx.Route, value: str
) -> None:
    responses = iter(
        [httpx.Response(503, headers={"Retry-After": value}), httpx.Response(200, json={"id_proposta": PROPOSAL_ID})]
    )
    route = mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(side_effect=lambda request: next(responses))
    client = make_client()

    started = time.monotonic()
    client.proposals.get(PROPOSAL_ID)
    client.close()

    assert route.call_count == 2
    assert time.monotonic() - started < 3


def test_absurd_retry_after_is_clamped_before_conversion(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "99999999999999"})
    )
    client = make_client()

    with pytest.raises(CredicarroRateLimitError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert error.value.retry_after_ms == 86_400_000


def test_retry_after_as_http_date_in_the_past_is_ignored(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    past = format_datetime(datetime.now(timezone.utc) - timedelta(minutes=5), usegmt=True)
    responses = iter(
        [httpx.Response(429, headers={"Retry-After": past}), httpx.Response(200, json={"id_proposta": PROPOSAL_ID})]
    )
    route = mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(side_effect=lambda request: next(responses))
    client = make_client()

    client.proposals.get(PROPOSAL_ID)
    client.close()

    assert route.call_count == 2


def test_sleep_is_limited_to_the_remaining_budget() -> None:
    from twila_credicarro._internal.http.api_response import ApiResponse

    pipeline = ResiliencePipeline(
        CredicarroResilienceOptions(total_timeout_ms=300, attempt_timeout_ms=300, retry_base_delay_ms=60_000)
    )

    def attempt() -> Any:
        return ApiResponse(503, None, {})

    started = time.monotonic()
    try:
        pipeline.execute(True, attempt)
    except CredicarroTimeoutError:
        pass

    assert time.monotonic() - started < 2



def test_document_upload_budget_is_attempt_timeout_times_attempts(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    mock_router.post(f"v2/proposal/{PROPOSAL_ID}/document").mock(return_value=httpx.Response(204))
    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(
        return_value=httpx.Response(200, json={"id_proposta": PROPOSAL_ID})
    )
    client = make_client()
    upload = ProposalDocumentUpload(ProposalParticipant.BUYER, DocumentType.CNH, DocumentFile.from_bytes(b"x", "a.pdf"))

    with mock.patch.object(
        client._executor._resilience, "execute", wraps=client._executor._resilience.execute
    ) as execute:
        client.proposals.upload_document(PROPOSAL_ID, upload)
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert execute.call_args_list[0].args[2] == 180_000
    assert execute.call_args_list[1].args[2] is None


def test_document_upload_budget_follows_the_options(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    client = make_client(document_upload_attempt_timeout_ms=5_000, max_retry_attempts=2)

    assert client.proposals._document_upload_total_timeout_ms == 10_000
    client.close()


def test_redirects_are_not_followed(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(
        return_value=httpx.Response(302, headers={"Location": "https://outro-host.local/x"})
    )
    target = mock_router.get(url="https://outro-host.local/x").mock(return_value=httpx.Response(200))
    client = make_client()

    with pytest.raises(CredicarroApiError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert error.value.status_code == 302
    assert target.call_count == 0


def test_redirect_on_the_token_endpoint_is_not_followed(mock_router: respx.MockRouter) -> None:
    mock_router.post("v1/authentication/accesstoken").mock(
        return_value=httpx.Response(307, headers={"Location": "https://outro-host.local/token"})
    )
    target = mock_router.post(url="https://outro-host.local/token").mock(return_value=httpx.Response(200))
    client = make_client()

    with pytest.raises(CredicarroApiError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert error.value.status_code == 307

    assert target.call_count == 0


def test_request_body_is_serialized_once_and_replayed(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    responses = iter([httpx.Response(503), httpx.Response(204)])
    route = mock_router.post(f"v2/proposal/{PROPOSAL_ID}/document").mock(side_effect=lambda request: next(responses))
    client = make_client()
    upload = ProposalDocumentUpload(
        ProposalParticipant.BUYER, DocumentType.CNH, DocumentFile.from_bytes(b"x" * 1000, "a.pdf")
    )

    real_dumps = json.dumps
    with mock.patch("twila_credicarro._internal.http.api_request_executor.json.dumps", wraps=real_dumps) as dumps:
        client.proposals.upload_document(PROPOSAL_ID, upload)
    client.close()

    assert route.call_count == 2
    assert dumps.call_count == 1
    assert route.calls[0].request.content == route.calls[1].request.content
    assert route.calls[0].request.headers["content-type"] == "application/json"



@pytest.mark.parametrize("key", ["", " ", "   ", "chave-ç", "chave\n", "chave\tx", "a" * 201, "chave\x7f"])
def test_invalid_explicit_idempotency_keys_are_rejected_before_any_request(
    mock_router: respx.MockRouter, token_route: respx.Route, key: str
) -> None:
    route = mock_router.post("v1/customer/unified").mock(
        return_value=httpx.Response(200, json={"id_cliente": PROPOSAL_ID})
    )
    client = make_client()

    with pytest.raises(ValueError):
        client.customers.upsert(_upsert(), idempotency_key=key)
    client.close()

    assert route.call_count == 0
    assert token_route.call_count == 0


@pytest.mark.parametrize("key", ["a", "a" * 200, "envio 123 / comprador:cnh", "~!@#$%^&*()"])
def test_valid_explicit_idempotency_keys(mock_router: respx.MockRouter, token_route: respx.Route, key: str) -> None:
    route = mock_router.post("v1/customer/unified").mock(
        return_value=httpx.Response(200, json={"id_cliente": PROPOSAL_ID})
    )
    client = make_client()

    client.customers.upsert(_upsert(), idempotency_key=key)
    client.close()

    assert route.calls.last.request.headers["idempotency-key"] == key



@pytest.mark.parametrize("seconds,expected", [(3600, 3540), (100, 50), (120, 60), (61, 30.5), (30, 15)])
def test_token_lifetime_without_expira_em(seconds: int, expected: float) -> None:
    class Api:
        def generate(self, credentials: object) -> dict[str, Any]:
            return {"token_de_acesso": "t", "expira_em_segundos": seconds}

    provider = AccessTokenProvider(Api(), TokenCredentials("i", "s"), clock=lambda: 1000.0)  # type: ignore[arg-type]

    provider.get_token()

    assert provider._cached is not None
    assert provider._cached.expires_at == pytest.approx(1000.0 + expected)



def _upsert() -> UpsertCustomerRequest:
    return UpsertCustomerRequest(
        cpf="12345678909",
        first_name="Maria",
        last_name="Souza",
        email="maria.souza@exemplo.com.br",
        phone_number="+55 (11) 99876-5432",
        date_of_birth="1990-05-20T00:00:00-03:00",
        address=CustomerAddress(
            street="Av. Paulista", neighborhood="Bela Vista", city="São Paulo", state="SP", postal_code="01311000"
        ),
        professional_data=ProfessionalData(occupation=OccupationType.EMPLOYEE, monthly_income=6543.21),
    )


def test_mask_cpf() -> None:
    assert mask_cpf("12345678909") == "***.456.789-**"
    assert mask_cpf("123.456.789-09") == "***.456.789-**"
    assert mask_cpf("1234") == "***"
    assert mask_cpf(None) == "***"


def test_request_reprs_mask_personal_data() -> None:
    text = repr(_upsert())

    assert "***.456.789-**" in text
    for secret in ("12345678909", "maria.souza@exemplo.com.br", "99876-5432", "1990-05-20", "6543.21"):
        assert secret not in text
    assert "Maria" not in text and "Souza" not in text and "Paulista" not in text

    simple = CreateCustomerRequest(
        "12345678909", "M", "S", "m@x.com", "+55 (11) 99876-5432", "1990-05-20T00:00:00-03:00"
    )
    assert "m@x.com" not in repr(simple) and "12345678909" not in repr(simple)


def test_other_reprs_mask_cpf_account_and_credentials() -> None:
    account = DepositAccount("12345678909", "001", "1234", "5", "987654", "7", DepositAccountType.CHECKING)
    proposal = CreateProposalRequest("12345678909", PROPOSAL_ID)
    simulation = CreateFinancingSimulationRequest("12345678909", "ABC1D23", 1, 0, "SP", False, "11222333000181")
    webhook = CreateWebhookRequest(
        WebhookType.PROPOSAL, "https://a.com", WebhookAuthenticationType.BASIC, "dXNlcjpwdw=="
    )

    for value, hidden in (
        (account, ("12345678909", "987654", "1234")),
        (proposal, ("12345678909",)),
        (simulation, ("12345678909",)),
        (webhook, ("dXNlcjpwdw==",)),
    ):
        for secret in hidden:
            assert secret not in repr(value)
    assert "***" in repr(account)


def test_response_reprs_mask_cpf_and_error_details(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    body = {
        "id_proposta": PROPOSAL_ID,
        "tipo": "Financing",
        "status": "Approved",
        "comprador": {"cpf": "12345678909"},
        "vendedor": {"cpf": "98765432100"},
    }
    mock_router.get(f"v1/proposal/{PROPOSAL_ID}").mock(return_value=httpx.Response(200, json=body))
    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(
        return_value=httpx.Response(
            400,
            json={"tipo": "Validation.Cpf.Invalid", "titulo": "Inválido", "detalhe": "CPF 12345678909 inválido"},
        )
    )
    client = make_client()

    summary = client.v1.proposals.get(PROPOSAL_ID)
    with pytest.raises(CredicarroApiError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert "12345678909" not in repr(summary) and "98765432100" not in repr(summary)
    assert "12345678909" not in repr(error.value.problem_details)
    assert "12345678909" not in str(error.value)
    assert error.value.detail == "CPF 12345678909 inválido"


def test_participant_state_masks_cpf_but_keeps_cnpj() -> None:
    from twila_credicarro import ProposalParticipantState

    assert "12345678909" not in repr(ProposalParticipantState(document="12345678909"))
    assert "11222333000181" in repr(ProposalParticipantState(document="11222333000181"))



def _b64(size: int) -> str:
    return base64.b64encode(b"\x00" * size).decode()


@pytest.mark.parametrize(
    "content",
    [
        "",
        "abc",
        "ab=d",
        "data:application/pdf;base64,AAAA",
        "AAAA\nAAAA",
        "AA AA",
        "====",
        "AAAA" + "=",
        pytest.param(_b64(MAX_BYTES + 1), id="acima-de-10-mib"),
    ],
)
def test_direct_construction_validates_base64_and_size(content: str) -> None:
    with pytest.raises(ValueError):
        DocumentFile(file_name="a.pdf", base64_content=content)


def test_direct_construction_accepts_valid_base64_up_to_the_limit() -> None:
    assert DocumentFile(file_name="a.pdf", base64_content=_b64(1)).file_name == "a.pdf"
    assert DocumentFile(file_name="a.pdf", base64_content=_b64(MAX_BYTES)).file_name == "a.pdf"


class _ChunkedStream:
    """Stream que nunca devolve mais que `chunk` bytes por leitura e não informa tamanho."""

    def __init__(self, total: int, chunk: int) -> None:
        self.remaining = total
        self.chunk = chunk
        self.read_total = 0

    def read(self, size: int = -1) -> bytes:
        count = min(self.chunk, self.remaining, size if size >= 0 else self.chunk)
        self.remaining -= count
        self.read_total += count
        return b"\x01" * count


def test_from_stream_reads_in_a_loop_until_eof() -> None:
    stream = _ChunkedStream(total=5000, chunk=7)

    file = DocumentFile.from_stream(stream, "a.png")  # type: ignore[arg-type]

    assert base64.b64decode(file.base64_content) == b"\x01" * 5000


def test_from_stream_never_reads_more_than_the_limit_plus_one() -> None:
    stream = _ChunkedStream(total=MAX_BYTES * 3, chunk=1024 * 1024)

    with pytest.raises(ValueError, match="10 MiB"):
        DocumentFile.from_stream(stream, "a.png")  # type: ignore[arg-type]

    assert stream.read_total == MAX_BYTES + 1


def test_from_file_does_not_trust_the_reported_size(tmp_path: Any) -> None:
    path = tmp_path / "grande.pdf"
    path.write_bytes(b"\x00" * (MAX_BYTES + 1))

    with pytest.raises(ValueError, match="10 MiB"):
        DocumentFile.from_file(path)


SECRET = "segredo-de-exemplo"
TIMESTAMP = 1715792400
NOW = datetime.fromtimestamp(TIMESTAMP, tz=timezone.utc)
BODY = f'{{"id_proposta":"{PROPOSAL_ID}","enum_status":2,"status":"Approved"}}'


def _signature(body: str = BODY) -> str:
    return compute_webhook_signature(SECRET, TIMESTAMP, body)


def test_duplicate_v1_or_t_in_the_header_is_invalid() -> None:
    signature = _signature()
    headers = [
        f"t={TIMESTAMP},v1={signature},v1={signature}",
        f"t={TIMESTAMP},v1={signature},v1={'0' * 64}",
        f"t={TIMESTAMP},t={TIMESTAMP},v1={signature}",
        f"t={TIMESTAMP},v1={'0' * 64},v1={signature}",
    ]

    assert verify_webhook_signature(BODY, f"t={TIMESTAMP},v1={signature}", SECRET, now=NOW) is True
    for header in headers:
        assert verify_webhook_signature(BODY, header, SECRET, now=NOW) is False
        with pytest.raises(CredicarroWebhookSignatureError):
            parse_webhook_event(BODY, header, SECRET, now=NOW)


def test_verified_parse_requires_header_and_secret() -> None:
    for header, secret in (
        (None, SECRET),
        (f"t={TIMESTAMP},v1={_signature()}", None),
        (f"t={TIMESTAMP},v1={_signature()}", ""),
    ):
        with pytest.raises(CredicarroWebhookSignatureError):
            parse_webhook_event(BODY, header, secret, now=NOW)


@pytest.mark.parametrize(
    "proposal_id", ["", "p-1", "123", "not-a-uuid", "bea8d060-f93d-48eb-b6c4-45f64483cdd", None, 7]
)
def test_body_without_a_valid_uuid_proposal_id_is_rejected(proposal_id: Any) -> None:
    body = json.dumps({"id_proposta": proposal_id, "enum_status": 2, "status": "Approved"})

    with pytest.raises(CredicarroWebhookSignatureError):
        parse_webhook_payload(body)

    header = f"t={TIMESTAMP},v1={compute_webhook_signature(SECRET, TIMESTAMP, body)}"
    with pytest.raises(CredicarroWebhookSignatureError):
        parse_webhook_event(body, header, SECRET, now=NOW)


@pytest.mark.parametrize("tolerance", [timedelta(seconds=-1), timedelta(days=-1), None, 300, float("inf")])
def test_tolerance_must_be_a_non_negative_timedelta(tolerance: Any) -> None:
    with pytest.raises(ValueError):
        verify_webhook_signature(BODY, f"t={TIMESTAMP},v1={_signature()}", SECRET, tolerance=tolerance, now=NOW)


def test_zero_tolerance_is_accepted() -> None:
    header = f"t={TIMESTAMP},v1={_signature()}"

    assert verify_webhook_signature(BODY, header, SECRET, tolerance=timedelta(0), now=NOW) is True
    assert (
        verify_webhook_signature(BODY, header, SECRET, tolerance=timedelta(0), now=NOW + timedelta(seconds=1)) is False
    )


def test_authorization_compares_digests_regardless_of_length() -> None:
    expected = "Basic dXN1YXJpbzpzZW5oYQ=="

    assert verify_webhook_authorization(expected, expected) is True
    assert verify_webhook_authorization(expected + "x", expected) is False
    assert verify_webhook_authorization("B", expected) is False
    assert verify_webhook_authorization(expected, expected[:-1]) is False
    assert verify_webhook_authorization(expected, "") is False
    assert verify_webhook_authorization("", "") is False
    assert verify_webhook_authorization(None, None) is False
    assert len(hashlib.sha256(expected.encode()).digest()) == 32


def test_event_and_function_list_pending_actions_for_the_detailed_payload() -> None:
    payload = {
        "id_proposta": PROPOSAL_ID,
        "enum_status": 2,
        "status": "APROVADA",
        "motivo_evento": "STATUS_ALTERADO",
        "comprador": {
            "cpf": "12345678909",
            "enum_biometria": 3,
            "status_ativo": {
                "enum_etapa": 6,
                "enum_situacao": 1,
                "enum_responsavel_acao": 2,
            },
            "documentos": [{"enum_tipo": 1, "enum_status": 5}, {"enum_tipo": 5, "enum_status": 1}],
        },
        "loja": None,
    }

    event = parse_webhook_payload(json.dumps(payload))
    actions = event.get_pending_actions()

    assert [(a.participant, a.kind.value, a.document_types) for a in actions] == [
        (ProposalParticipant.BUYER, "SendDocuments", (DocumentType.CNH,))
    ]
    assert get_pending_actions(event) == actions
    assert actions[0].participant is ProposalParticipant.BUYER
    assert event.buyer is not None and event.buyer.active_step is not None
    assert event.buyer.active_step.action_owner.name == "INTEGRATOR"
    assert "12345678909" not in repr(event)


def test_v1_event_has_no_pending_actions() -> None:
    assert parse_webhook_payload(BODY).get_pending_actions() == []


def test_paged_result_uses_page() -> None:
    from twila_credicarro import PagedResult

    result: PagedResult[int] = PagedResult(
        items=[1], has_next=False, has_previous=False, page=3, page_size=10, total_count=21
    )

    assert result.page == 3
    assert not hasattr(result, "page_number")


def test_document_from_bytes_takes_content_first() -> None:
    assert DocumentFile.from_bytes(b"abc", "x.pdf").file_name == "x.pdf"
    with pytest.raises((ValueError, TypeError)):
        DocumentFile.from_bytes("x.pdf", b"abc")  # type: ignore[arg-type]
