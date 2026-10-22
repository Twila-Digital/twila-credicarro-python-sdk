from typing import Optional

from .base import CredicarroError


class CredicarroAuthenticationError(CredicarroError):
    """Falha ao gerar o token (`401`/`400` em `v1/authentication/accesstoken`) ou `401` persistente numa rota."""

    def __init__(
        self,
        message: str,
        cause: Optional[BaseException] = None,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
    ) -> None:
        super().__init__(message, cause)
        self.status_code = status_code
        self.error_code = error_code
