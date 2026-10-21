from typing import Optional

from .api_error import CredicarroApiError
from .problem_details import ProblemDetails


class CredicarroRateLimitError(CredicarroApiError):
    def __init__(
        self,
        message: str,
        problem_details: ProblemDetails,
        retry_after_ms: Optional[int] = None,
        raw_body: Optional[str] = None,
    ) -> None:
        super().__init__(message, 429, problem_details, raw_body)
        self.retry_after_ms = retry_after_ms
