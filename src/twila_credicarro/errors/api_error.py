from typing import Optional

from .base import CredicarroError
from .problem_details import ProblemDetails, ProblemError


class CredicarroApiError(CredicarroError):
    """Resposta de erro da API. A mensagem traz só status, `tipo` e `titulo`; `detail` e `raw_body` ficam em
    propriedades porque podem conter dados pessoais."""

    def __init__(
        self,
        message: str,
        status_code: int,
        problem_details: ProblemDetails,
        raw_body: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.problem_details = problem_details
        self.raw_body = raw_body

    @property
    def error_code(self) -> Optional[str]:
        return self.problem_details.type

    @property
    def title(self) -> Optional[str]:
        return self.problem_details.title

    @property
    def detail(self) -> Optional[str]:
        return self.problem_details.detail

    @property
    def field(self) -> Optional[str]:
        return self.problem_details.field

    @property
    def errors(self) -> tuple[ProblemError, ...]:
        return self.problem_details.errors
