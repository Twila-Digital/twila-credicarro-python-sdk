from typing import Optional

from .api_error import CredicarroApiError
from .problem_details import ProblemDetails


class CredicarroBusinessRuleError(CredicarroApiError):
    """`422` — regra de negócio não atendida. Trate pelo `error_code` (ex.: `Store.Integration.Intermediation`)."""

    def __init__(self, message: str, problem_details: ProblemDetails, raw_body: Optional[str] = None) -> None:
        super().__init__(message, 422, problem_details, raw_body)
