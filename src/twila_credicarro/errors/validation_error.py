from typing import Optional

from .api_error import CredicarroApiError
from .problem_details import ProblemDetails


class CredicarroValidationError(CredicarroApiError):
    """`400` — dados inválidos. Veja `field` e `errors`."""

    def __init__(self, message: str, problem_details: ProblemDetails, raw_body: Optional[str] = None) -> None:
        super().__init__(message, 400, problem_details, raw_body)
