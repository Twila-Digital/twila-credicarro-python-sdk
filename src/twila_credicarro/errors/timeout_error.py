from typing import Optional

from .base import CredicarroError


class CredicarroTimeoutError(CredicarroError):
    def __init__(self, message: str, cause: Optional[BaseException] = None) -> None:
        super().__init__(message, cause)
