import random
import threading
import time
from collections import deque
from typing import Callable, Optional

from ...config.resilience_options import CredicarroResilienceOptions
from ...errors.timeout_error import CredicarroTimeoutError
from ..http.api_response import ApiResponse
from ..http.retry_after import retry_after_seconds
from .transient_failure_classifier import NETWORK_ERRORS, is_transient_response


class _CircuitBreaker:
    """Disjuntor por janela deslizante de amostras (mesma semântica do SDK Node)."""

    def __init__(self, options: CredicarroResilienceOptions) -> None:
        self._options = options
        self._lock = threading.Lock()
        self._events: deque[tuple[float, bool]] = deque()
        self._opened_at: Optional[float] = None
        self._half_open_trial_in_flight = False

    def before_call(self) -> bool:
        """`True` se a chamada pode seguir; `False` se o circuito está aberto (ou já há um teste de meia-abertura)."""
        with self._lock:
            if self._opened_at is None:
                return True

            elapsed_ms = (time.monotonic() - self._opened_at) * 1000
            if elapsed_ms < self._options.circuit_breaker_break_duration_ms:
                return False

            if self._half_open_trial_in_flight:
                return False

            self._half_open_trial_in_flight = True
            return True

    def release(self) -> None:
        """Encerra o teste de meia-abertura sem veredito (a tentativa terminou por exceção que não é de rede)."""
        with self._lock:
            self._half_open_trial_in_flight = False

    def on_success(self) -> None:
        with self._lock:
            if self._opened_at is not None:
                self._opened_at = None
                self._half_open_trial_in_flight = False
                self._events.clear()
                return

            self._record(is_failure=False)

    def on_failure(self) -> None:
        with self._lock:
            if self._opened_at is not None:
                self._opened_at = time.monotonic()
                self._half_open_trial_in_flight = False
                return

            self._record(is_failure=True)
            self._maybe_open()

    def _record(self, is_failure: bool) -> None:
        now = time.monotonic()
        self._events.append((now, is_failure))
        cutoff = now - self._options.circuit_breaker_sampling_duration_ms / 1000
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    def _maybe_open(self) -> None:
        total = len(self._events)
        if total < self._options.circuit_breaker_minimum_throughput:
            return

        failures = sum(1 for _, failed in self._events if failed)
        if failures / total >= self._options.circuit_breaker_failure_ratio:
            self._opened_at = time.monotonic()
            self._events.clear()


class ResiliencePipeline:
    def __init__(self, options: CredicarroResilienceOptions) -> None:
        self._options = options
        self._circuit_breaker = _CircuitBreaker(options)

    def execute(
        self,
        retry_safe: bool,
        attempt: Callable[[], ApiResponse],
        total_timeout_ms: Optional[int] = None,
    ) -> ApiResponse:
        """Executa com retry (só se `retry_safe`), circuit breaker e orçamento total (`total_timeout_ms`)."""
        budget_ms = total_timeout_ms if total_timeout_ms is not None else self._options.total_timeout_ms
        deadline = time.monotonic() + budget_ms / 1000
        max_attempts = max(1, self._options.max_retry_attempts)

        for attempt_number in range(1, max_attempts + 1):
            if time.monotonic() >= deadline:
                raise CredicarroTimeoutError("A requisição excedeu o tempo limite configurado.")

            if not self._circuit_breaker.before_call():
                raise CredicarroTimeoutError(
                    "O circuit breaker está aberto — chamadas recentes falharam de forma consistente."
                )

            response, network_failure = self._attempt_once(attempt)
            remaining = deadline - time.monotonic()
            can_retry = retry_safe and attempt_number < max_attempts and remaining > 0

            if network_failure is not None:
                if not can_retry:
                    raise CredicarroTimeoutError(
                        f"Falha de rede ou timeout ao chamar a API do Credicarro ({network_failure})."
                    )
                time.sleep(min(self._backoff_seconds(attempt_number), remaining))
                continue

            assert response is not None
            delay = self._retry_delay(response, attempt_number, remaining) if can_retry else None
            if delay is None:
                return response
            time.sleep(min(delay, remaining))

        raise AssertionError("unreachable: resilience pipeline loop did not return or raise")

    def _attempt_once(self, attempt: Callable[[], ApiResponse]) -> tuple[Optional[ApiResponse], Optional[str]]:
        """Roda uma tentativa e registra o resultado no circuit breaker. Devolve a resposta ou a falha de rede."""
        try:
            response = attempt()
        except NETWORK_ERRORS as error:
            self._circuit_breaker.on_failure()
            return None, type(error).__name__
        except BaseException:
            self._circuit_breaker.release()
            raise

        if is_transient_response(response, self._options):
            self._circuit_breaker.on_failure()
        else:
            self._circuit_breaker.on_success()
        return response, None

    def _retry_delay(self, response: ApiResponse, attempt_number: int, remaining: float) -> Optional[float]:
        """Segundos até a próxima tentativa, ou `None` quando a resposta deve ser devolvida já."""
        if not is_transient_response(response, self._options):
            return None

        retry_after = retry_after_seconds(response.headers)
        if retry_after is not None and retry_after > remaining:
            return None

        return retry_after if retry_after is not None else self._backoff_seconds(attempt_number)

    def _backoff_seconds(self, attempt_number: int) -> float:
        base_delay_ms = self._options.retry_base_delay_ms
        exponential: int = base_delay_ms * (2 ** max(0, attempt_number - 1))
        jitter_factor = 0.5 + random.random()
        result: float = (exponential * jitter_factor) / 1000
        return result
