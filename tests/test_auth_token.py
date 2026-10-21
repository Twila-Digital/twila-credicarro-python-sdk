import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
import pytest
import respx

from conftest import make_client, token_body
from twila_credicarro import (
    CredicarroApiError,
    CredicarroAuthenticationError,
    CredicarroClientOptions,
    CredicarroEnvironment,
    CredicarroTimeoutError,
)
from twila_credicarro._internal.auth.access_token_provider import AccessTokenProvider
from twila_credicarro._internal.auth.credentials import TokenCredentials
from twila_credicarro._internal.datetime_parsing import parse_iso_datetime

PROPOSAL_ID = "bea8d060-f93d-48eb-b6c4-45f64483cdd9"


class FakeTokenApi:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def generate(self, credentials: object) -> dict[str, Any]:
        self.calls += 1
        time.sleep(0.01)
        return self._responses[min(self.calls, len(self._responses)) - 1]


def _provider(api: FakeTokenApi, clock: Any) -> AccessTokenProvider:
    return AccessTokenProvider(api, TokenCredentials("id", "secret"), clock=clock)  # type: ignore[arg-type]


@pytest.mark.parametrize("fraction", ["", ".9", ".98", ".984", ".9845", ".98456", ".984567", ".9845678"])
@pytest.mark.parametrize("suffix", ["Z", "+00:00", "z"])
def test_parse_iso_datetime_accepts_fraction_of_1_to_7_digits_and_z(fraction: str, suffix: str) -> None:
    parsed = parse_iso_datetime(f"2026-10-12T14:05:08{fraction}{suffix}")

    assert parsed == datetime(2026, 10, 12, 14, 5, 8, int((fraction[1:] or "0")[:6].ljust(6, "0")), tzinfo=timezone.utc)


def test_parse_iso_datetime_keeps_offset_and_rejects_garbage() -> None:
    parsed = parse_iso_datetime("2026-10-12T14:05:08.984-03:00")

    assert parsed is not None
    assert parsed.utcoffset() == timedelta(hours=-3)
    assert parsed.astimezone(timezone.utc).hour == 17
    assert parse_iso_datetime("ontem") is None
    assert parse_iso_datetime(None) is None
    assert parse_iso_datetime("2026-13-45T00:00:00Z") is None


def test_token_is_cached_until_expira_em() -> None:
    now = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
    clock_value = [now.timestamp()]
    api = FakeTokenApi(
        [
            token_body("t1", expira_em="2026-10-19T12:59:00.1234567Z"),
            token_body("t2", expira_em="2026-10-19T14:00:00Z"),
        ]
    )
    provider = _provider(api, lambda: clock_value[0])

    assert provider.get_token() == "t1"
    clock_value[0] = now.timestamp() + 3000
    assert provider.get_token() == "t1"
    assert api.calls == 1

    clock_value[0] = now.timestamp() + 3541  # passou de 12:59:00
    assert provider.get_token() == "t2"
    assert api.calls == 2


def test_token_without_expira_em_uses_expira_em_segundos_minus_60() -> None:
    clock_value = [1_000_000.0]
    api = FakeTokenApi([{"token_de_acesso": "t1", "expira_em_segundos": 3600}, {"token_de_acesso": "t2"}])
    provider = _provider(api, lambda: clock_value[0])

    assert provider.get_token() == "t1"
    clock_value[0] += 3539
    assert provider.get_token() == "t1"
    clock_value[0] += 2  # 3541 s > 3600 - 60
    assert provider.get_token() == "t2"
    assert api.calls == 2


def test_invalidate_with_stale_token_keeps_newer_cached_token() -> None:
    api = FakeTokenApi([token_body("t1"), token_body("t2")])
    provider = _provider(api, time.time)

    assert provider.get_token() == "t1"
    provider.invalidate("t1")
    assert provider.get_token() == "t2"

    provider.invalidate("t1")  # token rejeitado já não é o atual: não descarta o cache
    assert provider.get_token() == "t2"
    assert api.calls == 2


def test_token_refresh_is_single_flight() -> None:
    api = FakeTokenApi([token_body("t1")])
    provider = _provider(api, time.time)
    tokens: list[str] = []

    def worker() -> None:
        tokens.append(provider.get_token())

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert tokens == ["t1"] * 8
    assert api.calls == 1


def test_client_reuses_token_across_calls(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(
        return_value=httpx.Response(200, json={"id_proposta": PROPOSAL_ID, "enum_status": 2, "status": "APROVADA"})
    )
    client = make_client()

    client.proposals.get(PROPOSAL_ID)
    client.proposals.get(PROPOSAL_ID)
    client.close()

    assert token_route.call_count == 1
    request = token_route.calls.last.request
    assert request.headers["content-type"].startswith("application/json")
    assert b"test-client-secret" in request.content  # o segredo só vai no corpo do token


def test_401_refreshes_token_and_retries_once(mock_router: respx.MockRouter) -> None:
    token_responses = iter(
        [httpx.Response(200, json=token_body("stale-token")), httpx.Response(200, json=token_body("fresh-token"))]
    )
    token_route = mock_router.post("v1/authentication/accesstoken").mock(
        side_effect=lambda request: next(token_responses)
    )

    seen: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        if request.headers["authorization"] == "Bearer stale-token":
            return httpx.Response(401)
        return httpx.Response(200, json={"id_proposta": PROPOSAL_ID, "enum_status": 1, "status": "EM_ANALISE"})

    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(side_effect=respond)
    client = make_client()

    proposal = client.proposals.get(PROPOSAL_ID)
    client.close()

    assert proposal.id == PROPOSAL_ID
    assert seen == ["Bearer stale-token", "Bearer fresh-token"]
    assert token_route.call_count == 2


def test_persistent_401_raises_authentication_error_after_a_single_retry(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(return_value=httpx.Response(401))
    client = make_client()

    with pytest.raises(CredicarroAuthenticationError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert route.call_count == 2
    assert error.value.status_code == 401
    assert "test-client-secret" not in str(error.value)


@pytest.mark.parametrize(
    "status,body,expected_code",
    [
        (
            401,
            {"tipo": "Integration.Authentication.InvalidCredentials", "titulo": "Não autorizado", "status": 401},
            "Integration.Authentication.InvalidCredentials",
        ),
        (
            400,
            {"tipo": "Validation.Field.Required", "titulo": "Requisição inválida", "status": 400, "campo": "clientId"},
            "Validation.Field.Required",
        ),
    ],
)
def test_token_failure_raises_authentication_error(
    mock_router: respx.MockRouter, status: int, body: dict[str, Any], expected_code: Optional[str]
) -> None:
    mock_router.post("v1/authentication/accesstoken").mock(return_value=httpx.Response(status, json=body))
    client = make_client()

    with pytest.raises(CredicarroAuthenticationError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert error.value.status_code == status
    assert error.value.error_code == expected_code
    assert "test-client-secret" not in str(error.value)


def test_token_network_failure_raises_sanitized_timeout_error(mock_router: respx.MockRouter) -> None:
    mock_router.post("v1/authentication/accesstoken").mock(side_effect=httpx.ConnectError("sem rede"))
    client = make_client(max_retry_attempts=2)

    with pytest.raises(CredicarroTimeoutError):
        client.proposals.get(PROPOSAL_ID)
    client.close()


def test_token_endpoint_is_retried_on_503(mock_router: respx.MockRouter) -> None:
    responses = iter([httpx.Response(503), httpx.Response(200, json=token_body("ok"))])
    token_route = mock_router.post("v1/authentication/accesstoken").mock(side_effect=lambda request: next(responses))
    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(
        return_value=httpx.Response(200, json={"id_proposta": PROPOSAL_ID})
    )
    client = make_client()

    assert client.proposals.get(PROPOSAL_ID).id == PROPOSAL_ID
    client.close()

    assert token_route.call_count == 2


def test_client_secret_never_appears_in_repr_of_options() -> None:
    options = CredicarroClientOptions(
        client_id="abc", client_secret="super-segredo", environment=CredicarroEnvironment.STAGING
    )

    assert "super-segredo" not in repr(options)
    assert "super-segredo" not in str(options)


def test_api_error_is_not_swallowed_as_authentication_error(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(
        return_value=httpx.Response(404, json={"tipo": "Proposal.Access.NotFound"})
    )
    client = make_client()

    with pytest.raises(CredicarroApiError):
        client.proposals.get(PROPOSAL_ID)
    client.close()
