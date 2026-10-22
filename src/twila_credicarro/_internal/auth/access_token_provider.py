import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..datetime_parsing import parse_iso_datetime
from ..masking import SecretStr
from .credentials import TokenCredentials
from .token_api_client import TokenApiClient

_CLOCK_SKEW_SECONDS = 60
_DEFAULT_LIFETIME_SECONDS = 3600


@dataclass
class _CachedToken:
    value: str
    expires_at: float


class AccessTokenProvider:
    """Token em cache até `expira_em`, com renovação single-flight (o lock cobre a chamada de geração)."""

    def __init__(
        self,
        token_api_client: TokenApiClient,
        credentials: TokenCredentials,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._token_api_client = token_api_client
        self._credentials = credentials
        self._clock = clock
        self._lock = threading.Lock()
        self._cached: Optional[_CachedToken] = None

    def __repr__(self) -> str:
        return "AccessTokenProvider()"

    def __reduce__(self) -> Any:
        raise TypeError("AccessTokenProvider guarda o token de acesso e não pode ser serializado.")

    def get_token(self) -> str:
        with self._lock:
            current = self._cached
            if current is not None and self._clock() < current.expires_at:
                return current.value

            response = self._token_api_client.generate(self._credentials)
            fresh = _CachedToken(value=SecretStr(response["token_de_acesso"]), expires_at=self._expires_at(response))
            self._cached = fresh
            return fresh.value

    def invalidate(self, rejected_token: Optional[str] = None) -> None:
        """Descarta o cache. Com `rejected_token`, só se ele ainda for o token atual (outra thread pode já ter
        renovado)."""
        with self._lock:
            if rejected_token is None or (self._cached is not None and self._cached.value == rejected_token):
                self._cached = None

    def _expires_at(self, response: dict[str, Any]) -> float:
        now = self._clock()

        parsed = parse_iso_datetime(response.get("expira_em"))
        if parsed is not None and parsed.timestamp() > now:
            return parsed.timestamp()

        seconds = response.get("expira_em_segundos")
        lifetime = float(seconds) if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) else None
        if lifetime is None:
            lifetime = float(_DEFAULT_LIFETIME_SECONDS)

        return now + max(lifetime / 2, lifetime - _CLOCK_SKEW_SECONDS)
