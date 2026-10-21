from typing import Any

import pytest

from twila_credicarro import (
    CredicarroClient,
    CredicarroClientOptions,
    CredicarroConfigurationError,
    CredicarroEnvironment,
    CredicarroResilienceOptions,
)
from twila_credicarro.config.client_options import resolve_client_options


def _options(**overrides: Any) -> CredicarroClientOptions:
    values: dict[str, Any] = {"client_id": "id", "client_secret": "secret"}
    values.update(overrides)
    return CredicarroClientOptions(**values)


def test_production_is_the_default_environment() -> None:
    assert _options().environment is CredicarroEnvironment.PRODUCTION
    assert resolve_client_options(_options()).base_url == "https://api.credicarro.com.br/integration/"


def test_staging_base_url() -> None:
    resolved = resolve_client_options(_options(environment=CredicarroEnvironment.STAGING))

    assert resolved.base_url == "https://api.staging.credicarro.com.br/integration/"


def test_base_url_override_gets_trailing_slash() -> None:
    resolved = resolve_client_options(_options(base_url="https://x.local/integration"))

    assert resolved.base_url == "https://x.local/integration/"


@pytest.mark.parametrize("base_url", ["http://localhost:5000/integration", "http://127.0.0.1:8080/"])
def test_http_is_accepted_only_for_local_hosts(base_url: str) -> None:
    assert resolve_client_options(_options(base_url=base_url)).base_url.startswith("http://")


@pytest.mark.parametrize(
    "base_url", ["http://api.credicarro.com.br/integration", "ftp://x.local/", "api.credicarro.com.br", "https://"]
)
def test_non_https_or_invalid_base_url_is_rejected(base_url: str) -> None:
    with pytest.raises(CredicarroConfigurationError):
        resolve_client_options(_options(base_url=base_url))


@pytest.mark.parametrize("field", ["client_id", "client_secret"])
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_credentials_are_rejected(field: str, value: str) -> None:
    with pytest.raises(CredicarroConfigurationError):
        CredicarroClient(_options(**{field: value}))


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_retry_attempts": 0},
        {"total_timeout_ms": 0},
        {"attempt_timeout_ms": 0},
        {"document_upload_attempt_timeout_ms": 0},
        {"attempt_timeout_ms": 40_000},
        {"circuit_breaker_failure_ratio": 0},
        {"circuit_breaker_failure_ratio": 1.5},
        {"circuit_breaker_minimum_throughput": 1},
    ],
)
def test_invalid_resilience_options_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(CredicarroConfigurationError):
        resolve_client_options(_options(resilience=CredicarroResilienceOptions(**overrides)))


def test_client_is_a_context_manager() -> None:
    with CredicarroClient(_options()) as client:
        assert client.customers is not None
        assert client.v1.proposals is not None
