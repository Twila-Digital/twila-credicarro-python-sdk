from .base import CredicarroError


class CredicarroWebhookSignatureError(CredicarroError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
