from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse

from ..errors.configuration_error import CredicarroConfigurationError
from .environment import CredicarroEnvironment, environment_base_url
from .resilience_options import DEFAULT_RESILIENCE_OPTIONS, CredicarroResilienceOptions

_LOCAL_HOSTS = ("localhost", "127.0.0.1")


@dataclass(frozen=True)
class CredicarroClientOptions:
    client_id: str
    client_secret: str = field(repr=False)
    environment: CredicarroEnvironment = CredicarroEnvironment.PRODUCTION
    base_url: Optional[str] = None
    resilience: CredicarroResilienceOptions = DEFAULT_RESILIENCE_OPTIONS

    def __reduce__(self) -> Any:
        raise TypeError("CredicarroClientOptions guarda credenciais e não pode ser serializado.")


@dataclass(frozen=True)
class ResolvedCredicarroClientOptions:
    client_id: str
    client_secret: str = field(repr=False)
    base_url: str
    resilience: CredicarroResilienceOptions

    def __reduce__(self) -> Any:
        raise TypeError("ResolvedCredicarroClientOptions guarda credenciais e não pode ser serializado.")


def resolve_client_options(options: CredicarroClientOptions) -> ResolvedCredicarroClientOptions:
    _validate(options)

    base_url = _resolve_base_url(options)

    return ResolvedCredicarroClientOptions(
        client_id=options.client_id,
        client_secret=options.client_secret,
        base_url=base_url,
        resilience=options.resilience,
    )


def _resolve_base_url(options: CredicarroClientOptions) -> str:
    raw = options.base_url or environment_base_url(options.environment)
    return raw if raw.endswith("/") else f"{raw}/"


def _validate(options: CredicarroClientOptions) -> None:
    if _is_blank(options.client_id):
        raise CredicarroConfigurationError("client_id é obrigatório.")
    if _is_blank(options.client_secret):
        raise CredicarroConfigurationError("client_secret é obrigatório.")

    if options.base_url is not None:
        _validate_base_url(options.base_url)

    resilience = options.resilience

    if resilience.max_retry_attempts < 1:
        raise CredicarroConfigurationError("resilience.max_retry_attempts deve ser maior ou igual a 1.")

    if resilience.total_timeout_ms <= 0:
        raise CredicarroConfigurationError("resilience.total_timeout_ms deve ser maior que zero.")

    if resilience.attempt_timeout_ms <= 0:
        raise CredicarroConfigurationError("resilience.attempt_timeout_ms deve ser maior que zero.")

    if resilience.document_upload_attempt_timeout_ms <= 0:
        raise CredicarroConfigurationError("resilience.document_upload_attempt_timeout_ms deve ser maior que zero.")

    if resilience.attempt_timeout_ms > resilience.total_timeout_ms:
        raise CredicarroConfigurationError(
            "resilience.attempt_timeout_ms não pode ser maior que resilience.total_timeout_ms."
        )

    if not (0 < resilience.circuit_breaker_failure_ratio <= 1):
        raise CredicarroConfigurationError(
            "resilience.circuit_breaker_failure_ratio deve estar entre 0 (exclusivo) e 1 (inclusivo)."
        )

    if resilience.circuit_breaker_minimum_throughput < 2:
        raise CredicarroConfigurationError("resilience.circuit_breaker_minimum_throughput deve ser maior ou igual a 2.")


def _validate_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise CredicarroConfigurationError("base_url, quando informada, deve ser uma URL absoluta válida.")

    if parsed.scheme == "https":
        return

    if parsed.scheme == "http" and parsed.hostname in _LOCAL_HOSTS:
        return

    raise CredicarroConfigurationError("base_url deve usar https (http só é aceito para localhost e 127.0.0.1).")


def _is_blank(value: Optional[str]) -> bool:
    return value is None or value.strip() == ""
