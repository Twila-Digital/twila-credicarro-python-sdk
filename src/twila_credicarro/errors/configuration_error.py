from .base import CredicarroError


class CredicarroConfigurationError(CredicarroError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
