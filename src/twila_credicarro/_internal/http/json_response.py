from typing import Any

import httpx

from .api_response import ApiResponse


def to_api_response(raw: httpx.Response) -> ApiResponse:
    return ApiResponse(
        status_code=raw.status_code,
        body=_safe_json(raw),
        headers=dict(raw.headers),
        text=_safe_text(raw),
    )


def _safe_json(raw: httpx.Response) -> Any:
    if not raw.content:
        return None
    try:
        return raw.json()
    except ValueError:
        return None


def _safe_text(raw: httpx.Response) -> Any:
    if not raw.content:
        return None
    try:
        return raw.text
    except ValueError:
        return None
