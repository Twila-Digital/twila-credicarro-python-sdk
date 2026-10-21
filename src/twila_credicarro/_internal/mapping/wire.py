"""Leitura defensiva dos JSON da API. Campo obrigatório ausente vira `CredicarroError` em português."""

from typing import Any, Optional

from ...errors.base import CredicarroError


def as_dict(value: Any, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CredicarroError(f"Resposta inesperada da API: {what} deveria ser um objeto JSON.")
    return value


def as_list(value: Any, what: str) -> list[Any]:
    if not isinstance(value, list):
        raise CredicarroError(f"Resposta inesperada da API: {what} deveria ser uma lista JSON.")
    return value


def opt_dict(wire: dict[str, Any], key: str) -> Optional[dict[str, Any]]:
    value = wire.get(key)
    return value if isinstance(value, dict) else None


def opt_list(wire: dict[str, Any], key: str) -> list[Any]:
    value = wire.get(key)
    return value if isinstance(value, list) else []


def req(wire: dict[str, Any], key: str) -> Any:
    value = wire.get(key)
    if value is None:
        raise CredicarroError(f"Resposta inesperada da API: o campo '{key}' não veio na resposta.")
    return value


def req_str(wire: dict[str, Any], key: str) -> str:
    return str(req(wire, key))


def opt_str(wire: dict[str, Any], key: str) -> Optional[str]:
    value = wire.get(key)
    return value if isinstance(value, str) else None


def req_int(wire: dict[str, Any], key: str) -> int:
    value = req(wire, key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CredicarroError(f"Resposta inesperada da API: o campo '{key}' deveria ser numérico.")
    return int(value)


def opt_int(wire: dict[str, Any], key: str) -> Optional[int]:
    value = wire.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def req_float(wire: dict[str, Any], key: str) -> float:
    value = req(wire, key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CredicarroError(f"Resposta inesperada da API: o campo '{key}' deveria ser numérico.")
    return float(value)


def opt_float(wire: dict[str, Any], key: str) -> Optional[float]:
    value = wire.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def opt_bool(wire: dict[str, Any], key: str) -> Optional[bool]:
    value = wire.get(key)
    return value if isinstance(value, bool) else None
