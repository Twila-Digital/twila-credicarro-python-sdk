from .base import CredicarroError


class CredicarroTimeoutError(CredicarroError):
    """Timeout (por tentativa ou total), falha de rede ou circuit breaker aberto."""
