import hashlib
import hmac
import json
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional, Union

from .._internal.datetime_parsing import parse_iso_datetime
from .._internal.mapping.proposal_mapper import participant_to_public
from .._internal.mapping.wire import opt_dict, opt_int, opt_str
from ..errors.webhook_signature_error import CredicarroWebhookSignatureError
from ..proposals.types import ProposalEventReason, ProposalStatus
from .types import ProposalWebhookEvent

DEFAULT_SIGNATURE_TOLERANCE = timedelta(minutes=5)

_TIMESTAMP_PATTERN = re.compile(r"[0-9]{1,10}")
_SIGNATURE_PATTERN = re.compile(r"[0-9a-fA-F]{64}")
_DETAILED_KEYS = ("motivo_evento", "data_evento", "comprador", "vendedor", "loja")

RawBody = Union[str, bytes]


def compute_webhook_signature(signing_secret: str, timestamp: Union[int, str], payload: RawBody) -> str:
    """HMAC-SHA256 (hex minúsculo) de `"{t}.{corpo bruto}"`, com o segredo em UTF-8."""
    signed_content = f"{timestamp}.".encode() + _to_bytes(payload)
    return hmac.new(signing_secret.encode("utf-8"), signed_content, hashlib.sha256).hexdigest()


def verify_webhook_signature(
    raw_body: RawBody,
    signature_header: Optional[str],
    signing_secret: Optional[str],
    tolerance: timedelta = DEFAULT_SIGNATURE_TOLERANCE,
    now: Optional[datetime] = None,
) -> bool:
    """`True` se o cabeçalho `X-CrediCarro-Signature` (`t={timestamp},v1={assinatura}`) confere com o corpo bruto e o
    timestamp está dentro da tolerância (nos dois sentidos). Segredo vazio é sempre inválido."""
    return _signature_failure(raw_body, signature_header, signing_secret, tolerance, now) is None


def verify_webhook_authorization(received_header: Optional[str], expected_header: Optional[str]) -> bool:
    """Compara o header `Authorization` recebido com o esperado em tempo constante."""
    if not received_header or not expected_header:
        return False

    # Compara os SHA-256: tamanho fixo, então o tempo não revela o tamanho do valor esperado.
    received_digest = hashlib.sha256(received_header.encode("utf-8")).digest()
    expected_digest = hashlib.sha256(expected_header.encode("utf-8")).digest()
    return hmac.compare_digest(received_digest, expected_digest)


def parse_webhook_event(
    raw_body: RawBody,
    signature_header: Optional[str],
    signing_secret: Optional[str],
    tolerance: timedelta = DEFAULT_SIGNATURE_TOLERANCE,
    now: Optional[datetime] = None,
) -> ProposalWebhookEvent:
    """Verifica a assinatura contra o corpo bruto e só então interpreta o evento (payload v1 ou v2).

    Lança `CredicarroWebhookSignatureError` se a assinatura, o timestamp ou o JSON forem inválidos.
    """
    failure = _signature_failure(raw_body, signature_header, signing_secret, tolerance, now)
    if failure is not None:
        raise CredicarroWebhookSignatureError(failure)

    return parse_webhook_payload(raw_body)


def parse_webhook_payload(raw_body: RawBody) -> ProposalWebhookEvent:
    """Interpreta o evento SEM verificar a assinatura. Use só em testes: em produção use `parse_webhook_event`."""
    wire = _load_json(raw_body)

    proposal_id = opt_str(wire, "id_proposta")
    if proposal_id is None or not _is_uuid(proposal_id):
        raise CredicarroWebhookSignatureError("O corpo do webhook não traz um 'id_proposta' (UUID) válido.")

    status_raw = opt_int(wire, "enum_status")
    status_name = opt_str(wire, "status")
    reason_name = opt_str(wire, "motivo_evento")

    return ProposalWebhookEvent(
        proposal_id=proposal_id,
        status=ProposalStatus.resolve(status_raw, status_name),
        status_raw=status_raw,
        status_name=status_name,
        event_reason=ProposalEventReason.from_wire_name(reason_name) if reason_name is not None else None,
        event_reason_raw=reason_name,
        refusal_reason=opt_str(wire, "motivo_recusa"),
        event_date=parse_iso_datetime(wire.get("data_evento")),
        buyer=participant_to_public(opt_dict(wire, "comprador"), "cpf"),
        seller=participant_to_public(opt_dict(wire, "vendedor"), "cpf"),
        store=participant_to_public(opt_dict(wire, "loja"), "cnpj", with_biometry=False),
        is_detailed=any(key in wire for key in _DETAILED_KEYS),
    )


def _signature_failure(
    raw_body: RawBody,
    signature_header: Optional[str],
    signing_secret: Optional[str],
    tolerance: timedelta,
    now: Optional[datetime],
) -> Optional[str]:
    if not isinstance(tolerance, timedelta) or tolerance < timedelta(0):
        raise ValueError("tolerance deve ser um timedelta finito maior ou igual a zero.")

    if not signing_secret:
        return "O segredo de assinatura do webhook não foi informado."

    parsed = _parse_signature_header(signature_header)
    if parsed is None:
        return "O cabeçalho de assinatura do webhook está ausente ou malformado."

    timestamp_text, signature = parsed

    expected = compute_webhook_signature(signing_secret, timestamp_text, raw_body).encode("ascii")

    if not hmac.compare_digest(expected, signature.lower().encode("ascii")):
        return "A assinatura do webhook não confere."

    current = now.timestamp() if now is not None else time.time()
    if abs(current - int(timestamp_text)) > tolerance.total_seconds():
        return "O timestamp do webhook está fora da tolerância — possível reenvio malicioso."

    return None


def _parse_signature_header(signature_header: Optional[str]) -> Optional[tuple[str, str]]:
    """Devolve (`t` bruto, `v1`) ou `None` se o cabeçalho for inválido.

    `t` precisa ser de 1 a 10 dígitos ASCII (`str.isdigit`/`int()` aceitariam dígitos unicode e `_`).
    """
    if not isinstance(signature_header, str) or not signature_header.strip():
        return None

    timestamp: Optional[str] = None
    signature: Optional[str] = None

    for part in signature_header.split(","):
        key, _, value = part.partition("=")
        key = key.strip()
        value = value.strip()

        if key == "t":
            if timestamp is not None or _TIMESTAMP_PATTERN.fullmatch(value) is None:
                return None
            timestamp = value
        elif key == "v1":
            # v1 repetido (ou fora do formato hexadecimal de 64 caracteres) invalida o cabeçalho.
            if signature is not None or _SIGNATURE_PATTERN.fullmatch(value) is None:
                return None
            signature = value

    if timestamp is None or signature is None:
        return None

    return timestamp, signature


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _load_json(raw_body: RawBody) -> dict[str, Any]:
    try:
        text = raw_body.decode("utf-8") if isinstance(raw_body, bytes) else raw_body
        wire = json.loads(text)
    except (ValueError, TypeError) as error:
        raise CredicarroWebhookSignatureError("O corpo do webhook está vazio ou não é um JSON válido.") from error

    if not isinstance(wire, dict):
        raise CredicarroWebhookSignatureError("O corpo do webhook está vazio ou não é um JSON válido.")

    return wire


def _to_bytes(payload: RawBody) -> bytes:
    return payload if isinstance(payload, bytes) else payload.encode("utf-8")
