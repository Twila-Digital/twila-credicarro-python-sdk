from typing import Optional

from .._internal.http.api_response import ApiResponse
from .._internal.http.retry_after import retry_after_seconds
from .api_error import CredicarroApiError
from .authentication_error import CredicarroAuthenticationError
from .base import CredicarroError
from .business_rule_error import CredicarroBusinessRuleError
from .problem_details import ProblemDetails, parse_problem_details
from .rate_limit_error import CredicarroRateLimitError
from .validation_error import CredicarroValidationError


def exception_from_response(response: ApiResponse) -> CredicarroError:
    problem_details = parse_problem_details(response.body)
    message = _build_message(response.status_code, problem_details)
    raw_body = response.text or None

    if response.status_code == 401:
        return CredicarroAuthenticationError(
            _authentication_message(problem_details),
            status_code=401,
            error_code=problem_details.type,
        )

    if response.status_code == 400:
        return CredicarroValidationError(message, problem_details, raw_body)

    if response.status_code == 422:
        return CredicarroBusinessRuleError(message, problem_details, raw_body)

    if response.status_code == 429:
        return CredicarroRateLimitError(message, problem_details, _retry_after_ms(response), raw_body)

    return CredicarroApiError(message, response.status_code, problem_details, raw_body)


def _build_message(status_code: int, problem_details: ProblemDetails) -> str:
    message = f"A API do Credicarro respondeu com status {status_code}"

    if problem_details.type:
        message += f" ({problem_details.type})"

    if problem_details.title:
        message += f": {problem_details.title}"

    return message if message.endswith(".") else f"{message}."


def _authentication_message(problem_details: ProblemDetails) -> str:
    if problem_details.type:
        return f"Não autorizado ({problem_details.type}): confira o client_id e o client_secret."

    return "Não autorizado: o token de acesso está ausente, é inválido ou expirou."


def _retry_after_ms(response: ApiResponse) -> Optional[int]:
    seconds = retry_after_seconds(response.headers)
    return None if seconds is None else int(seconds * 1000)
