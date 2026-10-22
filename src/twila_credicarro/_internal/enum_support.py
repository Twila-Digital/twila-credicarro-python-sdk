from collections.abc import Mapping
from enum import IntEnum
from typing import Optional, TypeVar

E = TypeVar("E", bound=IntEnum)


def enum_from_value(enum_class: type[E], value: object, unknown: E) -> E:
    """Valor numérico da API => membro do enum, ou `unknown` quando o SDK não conhece o valor."""
    if isinstance(value, bool) or not isinstance(value, int):
        return unknown

    try:
        return enum_class(value)
    except ValueError:
        return unknown


def enum_from_name(names: Mapping[str, E], value: object, unknown: E) -> E:
    """Nome textual da API (sem diferenciar maiúsculas) => membro do enum, ou `unknown`."""
    if not isinstance(value, str):
        return unknown

    return names.get(value.strip().upper(), unknown)


def enum_resolve(
    enum_class: type[E],
    names: Mapping[str, E],
    raw_value: object,
    raw_name: object,
    unknown: E,
) -> E:
    """Prefere o código numérico; sem ele, usa o nome."""
    if isinstance(raw_value, int) and not isinstance(raw_value, bool):
        return enum_from_value(enum_class, raw_value, unknown)

    return enum_from_name(names, raw_name, unknown)


def build_name_table(enum_class: type[E], extra: Optional[Mapping[str, E]] = None) -> dict[str, E]:
    """Tabela nome (maiúsculas) => membro. Cada membro entra com e sem `_` (`IN_NEGOTIATION` e `INNEGOTIATION`,
    que cobre `InNegotiation`); nomes em português entram por `extra`."""
    table: dict[str, E] = {}
    for member in enum_class:
        table[member.name.upper()] = member
        table[member.name.replace("_", "").upper()] = member
    if extra:
        for key, member in extra.items():
            table[key.upper()] = member
    return table
