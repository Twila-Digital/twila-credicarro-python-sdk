from typing import Optional


class CredicarroError(Exception):
    """Raiz de todas as exceções lançadas pelo SDK do Credicarro."""

    def __init__(self, message: str, cause: Optional[BaseException] = None) -> None:
        super().__init__(message)
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause
