from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx

from twila_credicarro import CredicarroClient, CredicarroClientOptions, CredicarroResilienceOptions

BASE_URL = "https://sdk-test.local/integration/"
FAST_RETRY = {"retry_base_delay_ms": 1}


def token_body(token: str = "test-token", **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "token_de_acesso": token,
        "expira_em_segundos": 3600,
        "expira_em": "2099-01-01T00:00:00.000+00:00",
        "tipo_de_token": "Bearer",
        "escopo": "credicarro.integration.access/full",
    }
    body.update(overrides)
    return body


@pytest.fixture
def mock_router() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        yield router


@pytest.fixture
def token_route(mock_router: respx.MockRouter) -> respx.Route:
    return mock_router.post("v1/authentication/accesstoken").mock(return_value=httpx.Response(200, json=token_body()))


def make_client(**resilience_overrides: Any) -> CredicarroClient:
    overrides = {**FAST_RETRY, **resilience_overrides}

    options = CredicarroClientOptions(
        client_id="test-client-id",
        client_secret="test-client-secret",
        base_url=BASE_URL,
        resilience=CredicarroResilienceOptions(**overrides),
    )
    return CredicarroClient(options)


@pytest.fixture
def client(token_route: respx.Route) -> Iterator[CredicarroClient]:
    c = make_client()
    yield c
    c.close()
