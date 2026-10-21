"""Acesso ao `openapi.yaml` público do Credicarro e utilitários para conferir os wire types do SDK contra ele.

O swagger de staging exige autenticação (`401`); por isso o contrato vem do OpenAPI publicado na documentação.
Para usar outra fonte, defina `CREDICARRO_CONTRACT_TESTS_OPENAPI_URL` (URL http(s) ou caminho de arquivo).
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml

OPENAPI_URL = "https://documentacao.credicarro.com.br/openapi.yaml"
HTTP_METHODS = ("get", "post", "put", "delete", "patch")


@lru_cache(maxsize=1)
def fetch_openapi() -> dict[str, Any]:
    source = os.environ.get("CREDICARRO_CONTRACT_TESTS_OPENAPI_URL", OPENAPI_URL)

    if source.startswith(("http://", "https://")):
        response = httpx.get(source, timeout=30.0, follow_redirects=True)
        if response.status_code != 200:
            raise RuntimeError(f"Falha ao buscar o openapi.yaml ({source}): HTTP {response.status_code}")
        text = response.text
    else:
        text = Path(source).read_text(encoding="utf-8")

    document = yaml.safe_load(text)
    if not isinstance(document, dict) or "paths" not in document:
        raise RuntimeError(f"O conteúdo de {source} não é um OpenAPI válido.")

    return document


def operations(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """(método em minúsculas, caminho) => operação."""
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for path, item in spec["paths"].items():
        for method in HTTP_METHODS:
            if method in item:
                result[(method, path)] = item[method]
    return result


def resolve(spec: dict[str, Any], node: Any) -> Any:
    """Segue `$ref` e junta `allOf`."""
    if not isinstance(node, dict):
        return node

    if "$ref" in node:
        target: Any = spec
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        return resolve(spec, target)

    if "allOf" in node:
        merged: dict[str, Any] = {k: v for k, v in node.items() if k != "allOf"}
        for part in node["allOf"]:
            resolved = resolve(spec, part)
            merged["properties"] = {**merged.get("properties", {}), **resolved.get("properties", {})}
            merged["required"] = [*merged.get("required", []), *resolved.get("required", [])]
        return merged

    return node


def parameters(spec: dict[str, Any], operation: dict[str, Any]) -> list[dict[str, Any]]:
    return [resolve(spec, parameter) for parameter in operation.get("parameters", [])]


def request_schema(spec: dict[str, Any], operation: dict[str, Any]) -> Optional[dict[str, Any]]:
    body = operation.get("requestBody")
    if body is None:
        return None
    return resolve(spec, body["content"]["application/json"]["schema"])  # type: ignore[no-any-return]


def response_schema(spec: dict[str, Any], operation: dict[str, Any], status: str) -> dict[str, Any]:
    response = resolve(spec, operation["responses"][status])
    return resolve(spec, response["content"]["application/json"]["schema"])  # type: ignore[no-any-return]


class RecordingDict(dict):  # type: ignore[type-arg]
    """Objeto JSON de exemplo que registra a leitura de chaves que não existem no schema."""

    def __init__(self, allowed: set[str], label: str, violations: list[str]) -> None:
        super().__init__()
        self._allowed = allowed
        self._label = label
        self._violations = violations

    def _check(self, key: Any) -> None:
        if key not in self._allowed:
            self._violations.append(f"{self._label}.{key}")

    def __getitem__(self, key: Any) -> Any:
        self._check(key)
        return super().__getitem__(key)

    def get(self, key: Any, default: Any = None) -> Any:
        self._check(key)
        return super().get(key, default)

    def __contains__(self, key: object) -> bool:
        self._check(key)
        return super().__contains__(key)


def sample(
    spec: dict[str, Any],
    schema: Any,
    violations: list[str],
    label: str,
    extra_allowed: frozenset[str] = frozenset(),
) -> Any:
    """Gera um valor de exemplo a partir do schema (todas as propriedades preenchidas)."""
    schema = resolve(spec, schema)
    schema_type = schema.get("type")

    if "properties" in schema or schema_type == "object":
        properties = schema.get("properties", {})
        value = RecordingDict(set(properties) | set(extra_allowed), label, violations)
        for name, child in properties.items():
            dict.__setitem__(value, name, sample(spec, child, violations, f"{label}.{name}", extra_allowed))
        return value

    if schema_type == "array":
        return [sample(spec, schema.get("items", {}), violations, f"{label}[]", extra_allowed)]

    if "enum" in schema:
        return schema["enum"][0]

    if schema_type == "integer":
        example = schema.get("example")
        return example if isinstance(example, int) and not isinstance(example, bool) else 1

    if schema_type == "number":
        example = schema.get("example")
        return example if isinstance(example, (int, float)) and not isinstance(example, bool) else 1.5

    if schema_type == "boolean":
        return True

    if schema.get("format") == "date-time":
        return "2026-10-12T14:05:08.984-03:00"

    if schema.get("format") == "uuid":
        return "bea8d060-f93d-48eb-b6c4-45f64483cdd9"

    example = schema.get("example")
    return str(example) if example is not None else "texto"


def assert_matches_schema(spec: dict[str, Any], schema: Any, value: Any, path: str = "$") -> None:
    """O valor enviado pelo SDK só usa propriedades do schema, traz as obrigatórias e respeita tipo/enum."""
    schema = resolve(spec, schema)
    schema_type = schema.get("type")

    if schema_type == "object" or "properties" in schema:
        assert isinstance(value, dict), f"{path}: esperado objeto, veio {type(value).__name__}"
        properties = schema.get("properties", {})
        extra = sorted(set(value) - set(properties))
        assert not extra, f"{path}: propriedades fora do schema: {extra}"
        missing = sorted(set(schema.get("required", [])) - set(value))
        assert not missing, f"{path}: propriedades obrigatórias ausentes: {missing}"
        for name, child in value.items():
            assert_matches_schema(spec, properties[name], child, f"{path}.{name}")
        return

    if schema_type == "array":
        assert isinstance(value, list), f"{path}: esperado lista"
        for index, item in enumerate(value):
            assert_matches_schema(spec, schema.get("items", {}), item, f"{path}[{index}]")
        return

    if "enum" in schema:
        assert value in schema["enum"], f"{path}: {value!r} fora do enum {schema['enum']}"

    if schema_type == "string":
        assert isinstance(value, str), f"{path}: esperado texto"
    elif schema_type == "integer":
        assert isinstance(value, int) and not isinstance(value, bool), f"{path}: esperado inteiro"
    elif schema_type == "number":
        assert isinstance(value, (int, float)) and not isinstance(value, bool), f"{path}: esperado número"
    elif schema_type == "boolean":
        assert isinstance(value, bool), f"{path}: esperado booleano"
