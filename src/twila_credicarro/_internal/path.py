import uuid
from typing import Union
from urllib.parse import quote

Identifier = Union[str, uuid.UUID]


def path_segment(value: Identifier) -> str:
    """Identificador (UUID em texto ou `uuid.UUID`) pronto para entrar no caminho da URL."""
    text = str(value)
    if not text.strip():
        raise ValueError("O identificador não pode ser vazio.")
    return quote(text, safe="")
