import json
from typing import Any

import httpx
import pytest
import respx

from conftest import make_client
from twila_credicarro import (
    CreateCustomerRequest,
    CreateFinancingSimulationRequest,
    CreateProposalRequest,
    CreateWebhookRequest,
    CredicarroApiError,
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
    VehicleDetails,
    WebhookAuthenticationType,
    WebhookType,
)
from twila_credicarro._internal.idempotency.idempotency_classifier import (
    idempotency_key_is_mandatory,
    is_retry_safe,
    requires_idempotency_key,
)

PROPOSAL_ID = "bea8d060-f93d-48eb-b6c4-45f64483cdd9"
SIMULATION_ID = "123e4567-e89b-12d3-a456-426614174000"


def _upsert_request() -> UpsertCustomerRequest:
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
        professional_data=ProfessionalData(occupation=OccupationType.EMPLOYEE, monthly_income=6500.0),
    )


@pytest.mark.parametrize(
    "path,expected",
    [
        ("v1/customer", True),
        ("v1/customer/address", True),
        ("v1/customer/professional", True),
        ("v1/customer/unified", False),
        ("v1/proposal/simulation/financing", True),
        ("v1/proposal/simulation/refinancing", True),
        ("v2/proposal/simulation/financing", True),
        ("v2/proposal/simulation/refinancing", True),
        ("v1/proposal", True),
        ("v2/proposal", True),
        (f"v2/proposal/{PROPOSAL_ID}/document", True),
        (f"v2/proposal/{PROPOSAL_ID}/vehicle-detail", False),
        (f"v2/proposal/{PROPOSAL_ID}/deposit-account", False),
        ("v1/webhook", False),
        ("v1/authentication/accesstoken", False),
    ],
)
def test_requires_automatic_idempotency_key_for_post(path: str, expected: bool) -> None:
    assert requires_idempotency_key("POST", path) is expected


def test_only_post_receives_automatic_key_and_only_document_is_mandatory() -> None:
    assert requires_idempotency_key("GET", "v1/proposal") is False
    assert idempotency_key_is_mandatory("POST", f"v2/proposal/{PROPOSAL_ID}/document") is True
    assert idempotency_key_is_mandatory("POST", "v2/proposal") is False


@pytest.mark.parametrize(
    "method,path,has_key,expected",
    [
        ("GET", f"v2/proposal/{PROPOSAL_ID}", False, True),
        ("GET", "v1/webhook?pagina_inicial=1", False, True),
        ("POST", "v1/authentication/accesstoken", False, True),
        ("POST", "v2/proposal", True, True),
        ("POST", "v2/proposal", False, False),
        ("POST", "v1/customer/unified", True, True),
        ("POST", "v1/customer/unified", False, False),
        ("POST", "v1/webhook", False, False),
        ("POST", f"v2/proposal/{PROPOSAL_ID}/vehicle-detail", False, True),
        ("POST", f"v2/proposal/{PROPOSAL_ID}/deposit-account", False, True),
        ("PUT", f"v1/webhook/{PROPOSAL_ID}", False, True),
        ("DELETE", f"v1/webhook/{PROPOSAL_ID}", False, True),
        ("PUT", f"v2/proposal/{PROPOSAL_ID}", False, False),
    ],
)
def test_is_retry_safe(method: str, path: str, has_key: bool, expected: bool) -> None:
    assert is_retry_safe(method, path, has_key) is expected


def test_unified_without_key_sends_no_key_and_is_not_retried(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post("v1/customer/unified").mock(return_value=httpx.Response(503))
    client = make_client()

    with pytest.raises(CredicarroApiError):
        client.customers.upsert(_upsert_request())
    client.close()

    assert route.call_count == 1
    assert "idempotency-key" not in route.calls.last.request.headers


def test_unified_with_explicit_key_sends_it_and_retries_with_the_same_key(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    responses = iter([httpx.Response(503), httpx.Response(200, json={"id_cliente": SIMULATION_ID})])
    route = mock_router.post("v1/customer/unified").mock(side_effect=lambda request: next(responses))
    client = make_client()

    customer_id = client.customers.upsert(_upsert_request(), idempotency_key="minha-chave-1")
    client.close()

    assert customer_id == SIMULATION_ID
    assert route.call_count == 2
    assert [call.request.headers["idempotency-key"] for call in route.calls] == ["minha-chave-1", "minha-chave-1"]


def test_automatic_key_is_generated_once_and_repeated_on_retries(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    responses = iter([httpx.Response(500), httpx.Response(503), httpx.Response(201, json={"id_proposta": PROPOSAL_ID})])
    route = mock_router.post("v2/proposal").mock(side_effect=lambda request: next(responses))
    client = make_client()

    proposal_id = client.proposals.create(CreateProposalRequest(cpf="12345678909", simulation_id=SIMULATION_ID))
    client.close()

    keys = [call.request.headers["idempotency-key"] for call in route.calls]
    assert proposal_id == PROPOSAL_ID
    assert len(keys) == 3
    assert len(set(keys)) == 1
    assert 1 <= len(keys[0]) <= 200


def test_each_logical_call_gets_a_new_automatic_key(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post("v1/customer").mock(return_value=httpx.Response(200, json={"id_cliente": SIMULATION_ID}))
    client = make_client()
    request = CreateCustomerRequest(
        cpf="12345678909",
        first_name="Maria",
        last_name="Souza",
        email="m@exemplo.com.br",
        phone_number="+55 (11) 99876-5432",
        date_of_birth="1990-05-20T00:00:00-03:00",
    )

    client.customers.create(request)
    client.customers.create(request)
    client.close()

    first, second = (call.request.headers["idempotency-key"] for call in route.calls)
    assert first != second


def test_disable_automatic_key_sends_no_key_and_does_not_retry(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post("v2/proposal/simulation/financing").mock(return_value=httpx.Response(503))
    client = make_client(disable_automatic_idempotency_key=True)

    with pytest.raises(CredicarroApiError):
        client.simulations.create_financing(
            CreateFinancingSimulationRequest(
                cpf="12345678909",
                license_plate="ABC1D23",
                vehicle_amount=45000,
                down_payment=5000,
                state="SP",
                is_zero_km=False,
                store_cnpj="11222333000181",
            )
        )
    client.close()

    assert route.call_count == 1
    assert "idempotency-key" not in route.calls.last.request.headers


def _upload() -> ProposalDocumentUpload:
    return ProposalDocumentUpload(
        participant=ProposalParticipant.BUYER,
        document_type=DocumentType.CNH,
        file=DocumentFile.from_bytes(b"%PDF-1.7 conteudo", "cnh.pdf"),
    )


def test_document_upload_reuses_the_same_key_on_every_attempt(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    responses = iter([httpx.Response(502), httpx.Response(408), httpx.Response(204)])
    route = mock_router.post(f"v2/proposal/{PROPOSAL_ID}/document").mock(side_effect=lambda request: next(responses))
    client = make_client()

    client.proposals.upload_document(PROPOSAL_ID, _upload())
    client.close()

    keys = [call.request.headers["idempotency-key"] for call in route.calls]
    assert len(keys) == 3
    assert len(set(keys)) == 1


def test_document_upload_uses_the_explicit_key(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post(f"v2/proposal/{PROPOSAL_ID}/document").mock(return_value=httpx.Response(204))
    client = make_client()

    client.proposals.upload_document(PROPOSAL_ID, _upload(), idempotency_key="envio-123")
    client.close()

    request = route.calls.last.request
    body: dict[str, Any] = json.loads(request.content)
    assert request.headers["idempotency-key"] == "envio-123"
    assert body["participante"] == "COMPRADOR"
    assert body["tipoDocumento"] == 1
    assert body["nomeArquivo"] == "cnh.pdf"


def test_document_upload_always_sends_a_key_even_when_automatic_keys_are_disabled(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post(f"v2/proposal/{PROPOSAL_ID}/document").mock(return_value=httpx.Response(204))
    client = make_client(disable_automatic_idempotency_key=True)

    client.proposals.upload_document(PROPOSAL_ID, _upload())
    client.close()

    assert route.calls.last.request.headers["idempotency-key"]


def test_two_document_uploads_without_key_use_different_keys(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post(f"v2/proposal/{PROPOSAL_ID}/document").mock(return_value=httpx.Response(204))
    client = make_client()

    client.proposals.upload_document(PROPOSAL_ID, _upload())
    client.proposals.upload_document(PROPOSAL_ID, _upload())
    client.close()

    first, second = (call.request.headers["idempotency-key"] for call in route.calls)
    assert first != second


@pytest.mark.parametrize("key", ["", "   ", "x" * 201])
def test_invalid_explicit_key_is_rejected_before_any_request(
    mock_router: respx.MockRouter, token_route: respx.Route, key: str
) -> None:
    route = mock_router.post(f"v2/proposal/{PROPOSAL_ID}/document").mock(return_value=httpx.Response(204))
    client = make_client()

    with pytest.raises(ValueError):
        client.proposals.upload_document(PROPOSAL_ID, _upload(), idempotency_key=key)
    client.close()

    assert route.call_count == 0


def test_webhook_creation_is_not_retried_and_has_no_key(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post("v1/webhook").mock(return_value=httpx.Response(503))
    client = make_client()

    with pytest.raises(CredicarroApiError):
        client.webhooks.create(
            CreateWebhookRequest(
                type=WebhookType.PROPOSAL,
                url="https://parceiro.com.br/webhooks/credicarro",
                authentication_type=WebhookAuthenticationType.NONE,
            )
        )
    client.close()

    assert route.call_count == 1
    assert "idempotency-key" not in route.calls.last.request.headers


def test_vehicle_detail_and_deposit_account_are_retried_without_key(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    vehicle_responses = iter([httpx.Response(503), httpx.Response(204)])
    deposit_responses = iter([httpx.Response(502), httpx.Response(204)])
    vehicle = mock_router.post(f"v2/proposal/{PROPOSAL_ID}/vehicle-detail").mock(
        side_effect=lambda request: next(vehicle_responses)
    )
    deposit = mock_router.post(f"v2/proposal/{PROPOSAL_ID}/deposit-account").mock(
        side_effect=lambda request: next(deposit_responses)
    )
    client = make_client()

    client.proposals.send_vehicle_details(
        PROPOSAL_ID,
        VehicleDetails(renavam="12345678900", chassis="9BWZZZ377VT004251", license_plate="ABC1D23", color="PRATA"),
    )
    client.proposals.send_deposit_account(
        PROPOSAL_ID,
        DepositAccount(
            holder_cpf="12345678909",
            bank_code="001",
            branch="1234",
            branch_digit="5",
            account_number="123456",
            account_digit="7",
            account_type=DepositAccountType.CHECKING,
        ),
    )
    client.close()

    assert vehicle.call_count == 2
    assert deposit.call_count == 2
    assert "idempotency-key" not in vehicle.calls.last.request.headers
    assert "idempotency-key" not in deposit.calls.last.request.headers
