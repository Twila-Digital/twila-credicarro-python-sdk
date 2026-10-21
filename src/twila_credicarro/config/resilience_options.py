from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CredicarroResilienceOptions:
    total_timeout_ms: int = 30_000
    attempt_timeout_ms: int = 10_000
    document_upload_attempt_timeout_ms: int = 60_000
    max_retry_attempts: int = 3
    retry_base_delay_ms: int = 500
    circuit_breaker_failure_ratio: float = 0.5
    circuit_breaker_sampling_duration_ms: int = 30_000
    circuit_breaker_minimum_throughput: int = 10
    circuit_breaker_break_duration_ms: int = 15_000
    # A documentação manda repetir `500` com a mesma Idempotency-Key — só vale para requisições retry-safe.
    retry_on_500: bool = True
    disable_automatic_idempotency_key: bool = False


DEFAULT_RESILIENCE_OPTIONS = CredicarroResilienceOptions()


def resolve_resilience_options(
    overrides: Optional["CredicarroResilienceOptions"] = None,
) -> CredicarroResilienceOptions:
    if overrides is None:
        return DEFAULT_RESILIENCE_OPTIONS
    return overrides
