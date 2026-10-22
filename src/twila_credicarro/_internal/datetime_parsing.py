"""Leitura de datas ISO-8601 da API.

`datetime.fromisoformat` só aceita `Z` a partir do Python 3.11 e só aceita 3 ou 6 dígitos de fração até o 3.10.
A API devolve frações de 1 a 7 dígitos (`.NET`) e `Z` ou `+00:00`; por isso a leitura é feita aqui, à mão.
"""

import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Union

_ISO_PATTERN = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})"
    r"(?:[Tt ]([0-9]{2}):([0-9]{2})(?::([0-9]{2})(?:[.,]([0-9]{1,9}))?)?)?"
    r"([Zz]|[+-][0-9]{2}(?::?[0-9]{2})?)?"
)

_BRAZIL_OFFSET = "-03:00"


def parse_iso_datetime(value: object) -> Optional[datetime]:
    """Converte uma data ISO-8601 em `datetime` com fuso. Sem fuso informado, assume UTC. Devolve `None` se inválida."""
    if not isinstance(value, str):
        return None

    match = _ISO_PATTERN.fullmatch(value.strip())
    if match is None:
        return None

    year, month, day, hour, minute, second, fraction, offset = match.groups()

    try:
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour or 0),
            int(minute or 0),
            int(second or 0),
            int((fraction or "0")[:6].ljust(6, "0")),
            tzinfo=_parse_offset(offset),
        )
    except ValueError:
        return None


def to_iso_string(value: Union[str, date, datetime]) -> str:
    """Texto ISO-8601 com offset, como a API exige em `dataDeNascimento`.

    Texto é repassado como está. `date` e `datetime` sem fuso saem à meia-noite/hora informada em `-03:00`
    (horário de Brasília), o padrão da documentação.
    """
    if isinstance(value, str):
        return value

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return f"{value.isoformat()}{_BRAZIL_OFFSET}"
        return value.isoformat()

    return f"{value.isoformat()}T00:00:00{_BRAZIL_OFFSET}"


def _parse_offset(offset: Optional[str]) -> timezone:
    if offset is None or offset in ("Z", "z"):
        return timezone.utc

    sign = -1 if offset[0] == "-" else 1
    digits = offset[1:].replace(":", "")
    hours = int(digits[:2])
    minutes = int(digits[2:4] or 0)

    if hours > 23 or minutes > 59:
        raise ValueError("offset inválido")

    return timezone(sign * timedelta(hours=hours, minutes=minutes))
