from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ApiResponse:
    status_code: int
    body: Any
    headers: dict[str, str]
    text: Optional[str] = None
