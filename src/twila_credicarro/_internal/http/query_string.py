from typing import Optional, Union
from urllib.parse import quote


class QueryStringBuilder:
    def __init__(self) -> None:
        self._parameters: list[str] = []

    def add(self, name: str, value: Optional[Union[str, int, float]]) -> "QueryStringBuilder":
        if value is None:
            return self

        self._parameters.append(f"{quote(name, safe='')}={quote(str(value), safe='')}")
        return self

    def build(self, path: str) -> str:
        if not self._parameters:
            return path

        return f"{path}?{'&'.join(self._parameters)}"
