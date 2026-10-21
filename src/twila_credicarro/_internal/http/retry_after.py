import math
from collections.abc import Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

# Acima disso o valor é tratado como "esperar muito": limitado aqui, antes de qualquer conversão para ms/duração.
MAX_RETRY_AFTER_SECONDS = 86_400.0


def retry_after_seconds(headers: Mapping[str, str]) -> Optional[float]:
    """Interpreta `Retry-After` (segundos ou data HTTP) e devolve a espera em segundos.

    Devolve `None` para valor ausente, inválido, não finito ou ≤ 0 (o chamador usa o backoff). Valores absurdos
    são limitados a 24 h.
    """
    value = headers.get("retry-after")
    if not value:
        return None

    seconds = _parse_seconds(value.strip())
    if seconds is None or not math.isfinite(seconds) or seconds <= 0:
        return None

    return min(seconds, MAX_RETRY_AFTER_SECONDS)


def _parse_seconds(value: str) -> Optional[float]:
    try:
        return float(value)
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)

    try:
        return (retry_at - datetime.now(timezone.utc)).total_seconds()
    except OverflowError:
        return None
