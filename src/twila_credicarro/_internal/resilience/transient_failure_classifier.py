import httpx

from ...config.resilience_options import CredicarroResilienceOptions
from ..http.api_response import ApiResponse

_TRANSIENT_STATUS_CODES = {408, 429, 502, 503, 504}

# Falhas de transporte (conexão, timeout, protocolo) que contam como falha de rede.
NETWORK_ERRORS: tuple[type[BaseException], ...] = (httpx.HTTPError,)


def is_transient_response(response: ApiResponse, options: CredicarroResilienceOptions) -> bool:
    if response.status_code in _TRANSIENT_STATUS_CODES:
        return True

    return response.status_code == 500 and options.retry_on_500


def is_network_error(error: BaseException) -> bool:
    return isinstance(error, NETWORK_ERRORS)
