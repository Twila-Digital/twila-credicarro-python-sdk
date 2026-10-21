import json
import re
import uuid
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from ...config.resilience_options import CredicarroResilienceOptions
from ...errors.exception_factory import exception_from_response
from ..auth.access_token_provider import AccessTokenProvider
from ..idempotency.idempotency_classifier import (
    idempotency_key_is_mandatory,
    is_retry_safe,
    requires_idempotency_key,
)
from ..masking import SecretStr
from ..resilience.resilience_pipeline import ResiliencePipeline
from .api_response import ApiResponse
from .json_response import to_api_response

MAX_IDEMPOTENCY_KEY_LENGTH = 200


class ApiRequestExecutor:
    def __init__(
        self,
        http: httpx.Client,
        base_url: str,
        token_provider: AccessTokenProvider,
        resilience_options: CredicarroResilienceOptions,
    ) -> None:
        self._base_url = base_url
        self._token_provider = token_provider
        self._resilience_options = resilience_options
        self._http = http
        self._resilience = ResiliencePipeline(resilience_options)

    def get(self, path: str) -> ApiResponse:
        return self._send("GET", path, None, self._resilience_options.attempt_timeout_ms, None, None)

    def post(
        self,
        path: str,
        body: Any,
        attempt_timeout_ms: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        total_timeout_ms: Optional[int] = None,
    ) -> ApiResponse:
        return self._send(
            "POST",
            path,
            body,
            attempt_timeout_ms or self._resilience_options.attempt_timeout_ms,
            idempotency_key,
            total_timeout_ms,
        )

    def put(self, path: str, body: Any) -> ApiResponse:
        return self._send("PUT", path, body, self._resilience_options.attempt_timeout_ms, None, None)

    def delete(self, path: str) -> ApiResponse:
        return self._send("DELETE", path, None, self._resilience_options.attempt_timeout_ms, None, None)

    @staticmethod
    def ensure_success(response: ApiResponse) -> None:
        if not (200 <= response.status_code < 300):
            raise exception_from_response(response)

    def _send(
        self,
        method: str,
        path: str,
        body: Any,
        attempt_timeout_ms: int,
        explicit_idempotency_key: Optional[str],
        total_timeout_ms: Optional[int],
    ) -> ApiResponse:
        # A chave nasce aqui, fora do laço de tentativas: todas as tentativas reaproveitam a mesma.
        idempotency_key = self._resolve_idempotency_key(method, path, explicit_idempotency_key)

        # O corpo é serializado uma única vez: tentativas e o replay do 401 reaproveitam os mesmos bytes.
        content = None if body is None else json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        retry_safe = is_retry_safe(method, path, idempotency_key is not None)

        return self._resilience.execute(
            retry_safe,
            lambda: self._send_with_auth(method, path, content, idempotency_key, attempt_timeout_ms),
            total_timeout_ms,
        )

    def _resolve_idempotency_key(self, method: str, path: str, explicit_key: Optional[str]) -> Optional[str]:
        if explicit_key is not None:
            _validate_idempotency_key(explicit_key)
            return explicit_key

        if not requires_idempotency_key(method, path):
            return None

        if self._resilience_options.disable_automatic_idempotency_key and not idempotency_key_is_mandatory(
            method, path
        ):
            return None

        return str(uuid.uuid4())

    def _send_with_auth(
        self,
        method: str,
        path: str,
        content: Optional[bytes],
        idempotency_key: Optional[str],
        attempt_timeout_ms: int,
    ) -> ApiResponse:
        token = self._token_provider.get_token()
        response = self._send_once(method, path, content, idempotency_key, attempt_timeout_ms, token)

        if response.status_code != 401:
            return response

        # Renova e repete uma única vez. O cache só é descartado se o token rejeitado ainda for o atual.
        self._token_provider.invalidate(token)
        new_token = self._token_provider.get_token()
        retried = self._send_once(method, path, content, idempotency_key, attempt_timeout_ms, new_token)

        if retried.status_code != 401:
            return retried

        raise exception_from_response(retried)

    def _send_once(
        self,
        method: str,
        path: str,
        content: Optional[bytes],
        idempotency_key: Optional[str],
        attempt_timeout_ms: int,
        token: str,
    ) -> ApiResponse:
        url = urljoin(self._base_url, path)

        headers: dict[str, str] = {"Authorization": SecretStr(f"Bearer {token}")}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if content is not None:
            headers["Content-Type"] = "application/json"

        raw = self._http.request(method, url, content=content, headers=headers, timeout=attempt_timeout_ms / 1000)

        return to_api_response(raw)


_IDEMPOTENCY_KEY_PATTERN = re.compile(r"[ -~]{1,%d}" % MAX_IDEMPOTENCY_KEY_LENGTH)  # noqa: UP031


def _validate_idempotency_key(key: str) -> None:
    """1 a 200 caracteres ASCII imprimíveis (0x20–0x7E), não só espaços. Chave vazia nunca vira "sem chave"."""
    if not isinstance(key, str) or not key.strip() or _IDEMPOTENCY_KEY_PATTERN.fullmatch(key) is None:
        raise ValueError(
            f"idempotency_key deve ter de 1 a {MAX_IDEMPOTENCY_KEY_LENGTH} caracteres ASCII imprimíveis, "
            "e não pode ser só espaços."
        )
