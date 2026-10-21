import httpx

from ._internal.auth.access_token_provider import AccessTokenProvider
from ._internal.auth.credentials import TokenCredentials
from ._internal.auth.token_api_client import TokenApiClient
from ._internal.http.api_request_executor import ApiRequestExecutor
from ._version import __version__
from .config.client_options import CredicarroClientOptions, resolve_client_options
from .customers.client import CustomersClient
from .proposals.client import ProposalsClient
from .simulations.client import SimulationsClient
from .v1.client import V1Client
from .webhooks.client import WebhooksClient


class CredicarroClient:
    """Cliente principal do SDK — thread-safe, deve ser reaproveitado como singleton na aplicação."""

    def __init__(self, options: CredicarroClientOptions) -> None:
        resolved = resolve_client_options(options)

        # Um único httpx.Client (pool de conexões e contexto TLS) para o token e para as chamadas da API.
        # Redirecionamentos desligados: um 3xx vira CredicarroApiError (o Authorization não segue para outro host).
        self._http = httpx.Client(
            headers={"User-Agent": f"twila-credicarro-python/{__version__}", "Accept": "application/json"},
            follow_redirects=False,
        )

        token_api_client = TokenApiClient(self._http, resolved.base_url, resolved.resilience)
        token_provider = AccessTokenProvider(
            token_api_client, TokenCredentials(resolved.client_id, resolved.client_secret)
        )

        self._executor = ApiRequestExecutor(self._http, resolved.base_url, token_provider, resolved.resilience)

        self.customers = CustomersClient(self._executor)
        self.simulations = SimulationsClient(self._executor)
        self.proposals = ProposalsClient(
            self._executor,
            resolved.resilience.document_upload_attempt_timeout_ms,
            resolved.resilience.max_retry_attempts,
        )
        self.webhooks = WebhooksClient(self._executor)
        self.v1 = V1Client(self._executor)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "CredicarroClient":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()
