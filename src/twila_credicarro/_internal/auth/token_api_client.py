from typing import Any
from urllib.parse import urljoin

import httpx

from ...config.resilience_options import CredicarroResilienceOptions
from ...errors.authentication_error import CredicarroAuthenticationError
from ...errors.exception_factory import exception_from_response
from ..http.api_response import ApiResponse
from ..http.json_response import to_api_response
from ..resilience.resilience_pipeline import ResiliencePipeline
from .credentials import TokenCredentials


class TokenApiClient:
    """Chama `POST v1/authentication/accesstoken` (retry-safe) com o próprio pipeline de resiliência."""

    def __init__(self, http: httpx.Client, base_url: str, resilience_options: CredicarroResilienceOptions) -> None:
        self._http = http
        self._url = urljoin(base_url, "v1/authentication/accesstoken")
        self._timeout_seconds = resilience_options.attempt_timeout_ms / 1000
        self._pipeline = ResiliencePipeline(resilience_options)

    def generate(self, credentials: TokenCredentials) -> dict[str, Any]:
        def attempt() -> ApiResponse:
            # O corpo (com o segredo) é montado aqui, sem variável local. Falha de rede vira
            # CredicarroTimeoutError sanitizado dentro do pipeline.
            return to_api_response(
                self._http.post(self._url, json=credentials.as_request_body(), timeout=self._timeout_seconds)
            )

        response = self._pipeline.execute(True, attempt)

        if not (200 <= response.status_code < 300):
            failure = exception_from_response(response)
            if isinstance(failure, CredicarroAuthenticationError):
                raise failure
            if response.status_code == 400:
                raise CredicarroAuthenticationError(
                    "Falha ao gerar o token de acesso (400): confira o client_id e o client_secret.",
                    status_code=400,
                    error_code=getattr(failure, "error_code", None),
                )
            # 3xx, 5xx (depois das tentativas) e demais status: erro de API com status e `tipo`.
            raise failure

        result = response.body
        token = result.get("token_de_acesso") if isinstance(result, dict) else None
        if not isinstance(result, dict) or not isinstance(token, str) or not token:
            raise CredicarroAuthenticationError(
                "A API do Credicarro retornou uma resposta vazia ao gerar o token de acesso."
            )

        return result
