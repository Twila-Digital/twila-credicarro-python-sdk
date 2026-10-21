from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Optional


@dataclass(frozen=True)
class ProblemError:
    """Item de `erros`: presente só quando o JSON enviado está malformado ou tem valor de tipo errado."""

    code: Optional[str] = None
    message: Optional[str] = dc_field(default=None, repr=False)
    field: Optional[str] = None


@dataclass(frozen=True)
class ProblemDetails:
    """`ProblemDetails` da API (`tipo`, `titulo`, `status`, `detalhe`, `campo`, `erros`), com fallback para o
    formato padrão (`type`, `title`, `status`, `detail`).

    `detail` e `raw_body` podem conter dados pessoais — não os registre em log.
    """

    type: Optional[str] = None
    title: Optional[str] = None
    status: Optional[int] = None
    detail: Optional[str] = dc_field(default=None, repr=False)
    field: Optional[str] = None
    errors: tuple[ProblemError, ...] = dc_field(default=(), repr=False)


def parse_problem_details(body: Any) -> ProblemDetails:
    if not isinstance(body, dict):
        return ProblemDetails()

    status = body.get("status")

    return ProblemDetails(
        type=_first_text(body, "tipo", "type"),
        title=_first_text(body, "titulo", "title"),
        status=status if isinstance(status, int) and not isinstance(status, bool) else None,
        detail=_first_text(body, "detalhe", "detail"),
        field=_first_text(body, "campo"),
        errors=_parse_errors(body.get("erros")),
    )


def _first_text(body: dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = body.get(key)
        if isinstance(value, str) and value != "":
            return value
    return None


def _parse_errors(raw: Any) -> tuple[ProblemError, ...]:
    if not isinstance(raw, list):
        return ()

    return tuple(
        ProblemError(
            code=_first_text(item, "codigo"),
            message=_first_text(item, "mensagem"),
            field=_first_text(item, "campo"),
        )
        for item in raw
        if isinstance(item, dict)
    )
