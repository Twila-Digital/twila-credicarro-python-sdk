"""Mascaramento de dados pessoais e segredos em `repr` (logs, Sentry e depuradores usam `repr`)."""

import dataclasses
import re
from collections.abc import Iterable
from typing import Any, Callable, TypeVar

T = TypeVar("T")

MASK = "***"


class SecretStr(str):
    """Texto secreto (client_secret, token): funciona como `str`, mas `repr` mostra só `'***'`."""

    __slots__ = ()

    def __repr__(self) -> str:
        return f"'{MASK}'"


def mask_cpf(value: object) -> str:
    """`12345678909` / `123.456.789-09` => `***.456.789-**`. Qualquer outra coisa => `***`."""
    digits = re.sub(r"[^0-9]", "", value) if isinstance(value, str) else ""
    if len(digits) != 11:
        return MASK
    return f"***.{digits[3:6]}.{digits[6:9]}-**"


def mask_document(value: object) -> str:
    """CPF é mascarado; CNPJ (dado de empresa) e ausência de valor passam como estão."""
    if value is None:
        return "None"
    digits = re.sub(r"[^0-9]", "", value) if isinstance(value, str) else ""
    if len(digits) == 14:
        return repr(value)
    return mask_cpf(value)


def masked_repr(
    *,
    cpf: Iterable[str] = (),
    document: Iterable[str] = (),
    secret: Iterable[str] = (),
) -> Callable[[type[T]], type[T]]:
    """Substitui o `__repr__` do dataclass mascarando os campos informados (`None` continua `None`)."""
    cpf_fields = frozenset(cpf)
    document_fields = frozenset(document)
    secret_fields = frozenset(secret)

    def decorate(cls: type[T]) -> type[T]:
        names = [field.name for field in dataclasses.fields(cls) if field.repr]  # type: ignore[arg-type]

        def __repr__(self: Any) -> str:  # noqa: N807
            parts = []
            for name in names:
                value = getattr(self, name)
                if value is None:
                    text = "None"
                elif name in cpf_fields:
                    text = mask_cpf(value)
                elif name in document_fields:
                    text = mask_document(value)
                elif name in secret_fields:
                    text = MASK
                else:
                    text = repr(value)
                parts.append(f"{name}={text}")
            return f"{type(self).__name__}({', '.join(parts)})"

        cls.__repr__ = __repr__  # type: ignore[method-assign]
        return cls

    return decorate
