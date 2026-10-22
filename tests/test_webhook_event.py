import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from twila_credicarro import (
    ActionOwner,
    CredicarroWebhookSignatureError,
    DocumentStatus,
    ProposalEventReason,
    ProposalStatus,
    ProposalStep,
    compute_webhook_signature,
    parse_webhook_event,
    parse_webhook_payload,
    verify_webhook_authorization,
    verify_webhook_signature,
)

SECRET = "segredo-de-exemplo"
TIMESTAMP = 1715792400
BODY = '{"id_proposta":"bea8d060-f93d-48eb-b6c4-45f64483cdd9","enum_status":2,"status":"Approved"}'
VECTOR_SIGNATURE = "db66c554eb116ef2577deb63f72619793502a31520f622b2d59864b074eb8df2"
NOW = datetime.fromtimestamp(TIMESTAMP, tz=timezone.utc)

V2_PAYLOAD: dict[str, Any] = {
    "id_proposta": "bea8d060-f93d-48eb-b6c4-45f64483cdd9",
    "enum_status": 2,
    "status": "APROVADA",
    "motivo_evento": "DOCUMENTOS_ALTERADOS",
    "motivo_recusa": None,
    "data_evento": "2026-10-12T17:20:31.512+00:00",
    "comprador": {
        "cpf": "12345678909",
        "enum_biometria": 3,
        "biometria": "APROVADA",
        "status_ativo": {
            "enum_etapa": 7,
            "etapa": "CORRECAO_DOCUMENTOS",
            "enum_situacao": 4,
            "situacao": "PENDENTE_CORRECAO",
            "enum_responsavel_acao": 2,
            "responsavel_acao": "INTEGRADOR",
        },
        "etapas_concluidas": [{"enum_etapa": 1, "etapa": "PROPOSTA_CRIADA", "data": "2026-10-12T14:05:08-03:00"}],
        "documentos": [
            {"enum_tipo": 1, "tipo": "CNH", "enum_status": 2, "status": "INVALIDO", "motivo": "Documento ilegível"}
        ],
    },
    "loja": {
        "cnpj": "11222333000181",
        "status_ativo": {
            "enum_etapa": 6,
            "etapa": "ENVIO_DOCUMENTOS",
            "enum_situacao": 1,
            "situacao": "AGUARDANDO_ENVIO",
            "enum_responsavel_acao": 2,
            "responsavel_acao": "INTEGRADOR",
        },
        "etapas_concluidas": [],
        "documentos": [],
    },
    "vendedor": None,
}


def _header(timestamp: Any = TIMESTAMP, signature: str = VECTOR_SIGNATURE) -> str:
    return f"t={timestamp},v1={signature}"


def test_documentation_vector_is_reproduced() -> None:
    assert compute_webhook_signature(SECRET, TIMESTAMP, BODY) == VECTOR_SIGNATURE
    assert compute_webhook_signature(SECRET, str(TIMESTAMP), BODY.encode()) == VECTOR_SIGNATURE


def test_documentation_vector_is_accepted() -> None:
    assert verify_webhook_signature(BODY, _header(), SECRET, now=NOW) is True
    assert verify_webhook_signature(BODY.encode(), _header(), SECRET, now=NOW) is True


def test_parse_with_signature_returns_the_v1_event() -> None:
    event = parse_webhook_event(BODY, _header(), SECRET, now=NOW)

    assert event.proposal_id == "bea8d060-f93d-48eb-b6c4-45f64483cdd9"
    assert event.status is ProposalStatus.APPROVED
    assert event.status_raw == 2
    assert event.status_name == "Approved"
    assert event.is_detailed is False
    assert event.event_reason is None
    assert event.buyer is None and event.seller is None and event.store is None


def test_uppercase_hex_signature_is_accepted() -> None:
    assert verify_webhook_signature(BODY, _header(signature=VECTOR_SIGNATURE.upper()), SECRET, now=NOW) is True


def test_extra_whitespace_and_fields_in_the_header_are_tolerated() -> None:
    header = f" t = {TIMESTAMP} , v0=abc , v1 = {VECTOR_SIGNATURE} "

    assert verify_webhook_signature(BODY, header, SECRET, now=NOW) is True


def test_wrong_signature_secret_or_body_is_rejected() -> None:
    assert verify_webhook_signature(BODY, _header(signature="0" * 64), SECRET, now=NOW) is False
    assert verify_webhook_signature(BODY, _header(), "outro-segredo", now=NOW) is False
    assert verify_webhook_signature(BODY + " ", _header(), SECRET, now=NOW) is False
    assert verify_webhook_signature(BODY, _header(TIMESTAMP + 1), SECRET, now=NOW) is False

    with pytest.raises(CredicarroWebhookSignatureError):
        parse_webhook_event(BODY, _header(signature="0" * 64), SECRET, now=NOW)


@pytest.mark.parametrize("secret", ["", None])
def test_empty_secret_is_always_invalid(secret: Any) -> None:
    valid_for_empty_secret = compute_webhook_signature("", TIMESTAMP, BODY)

    assert verify_webhook_signature(BODY, _header(signature=valid_for_empty_secret), secret, now=NOW) is False
    with pytest.raises(CredicarroWebhookSignatureError):
        parse_webhook_event(BODY, _header(signature=valid_for_empty_secret), secret, now=NOW)


@pytest.mark.parametrize(
    "timestamp",
    [
        "",
        " ",
        "abc",
        "-1",
        "+1715792400",
        "1715792400.5",
        "1_715_792_400",
        "17157924000",
        "１７１５７９２４００",
        "١٧١٥٧٩٢٤٠٠",
        "1715792400\n",
    ],
)
def test_invalid_timestamp_in_header_is_rejected(timestamp: str) -> None:
    signature = compute_webhook_signature(SECRET, timestamp, BODY)
    header = f"t={timestamp},v1={signature}"

    assert verify_webhook_signature(BODY, header, SECRET, now=NOW) is False
    with pytest.raises(CredicarroWebhookSignatureError):
        parse_webhook_event(BODY, header, SECRET, now=NOW)


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "   ",
        "garbage",
        f"v1={VECTOR_SIGNATURE}",
        f"t={TIMESTAMP}",
        f"t={TIMESTAMP},v1=",
        f"t={TIMESTAMP},v1=nao-e-hex",
        f"t={TIMESTAMP},v1={VECTOR_SIGNATURE[:-1]}",
        f"t={TIMESTAMP},t={TIMESTAMP},v1={VECTOR_SIGNATURE}",
    ],
)
def test_missing_or_malformed_header_is_rejected(header: Any) -> None:
    assert verify_webhook_signature(BODY, header, SECRET, now=NOW) is False
    with pytest.raises(CredicarroWebhookSignatureError):
        parse_webhook_event(BODY, header, SECRET, now=NOW)


def test_tolerance_applies_in_both_directions() -> None:
    assert verify_webhook_signature(BODY, _header(), SECRET, now=NOW + timedelta(minutes=5)) is True
    assert verify_webhook_signature(BODY, _header(), SECRET, now=NOW - timedelta(minutes=5)) is True
    assert verify_webhook_signature(BODY, _header(), SECRET, now=NOW + timedelta(minutes=5, seconds=1)) is False
    assert verify_webhook_signature(BODY, _header(), SECRET, now=NOW - timedelta(minutes=5, seconds=1)) is False


def test_custom_tolerance() -> None:
    later = NOW + timedelta(minutes=30)

    assert verify_webhook_signature(BODY, _header(), SECRET, now=later) is False
    assert verify_webhook_signature(BODY, _header(), SECRET, tolerance=timedelta(hours=1), now=later) is True
    with pytest.raises(CredicarroWebhookSignatureError, match="tolerância"):
        parse_webhook_event(BODY, _header(), SECRET, now=later)


def test_default_clock_rejects_an_old_timestamp() -> None:
    assert verify_webhook_signature(BODY, _header(), SECRET) is False


def test_valid_signature_with_current_time_passes_without_injected_clock() -> None:
    timestamp = int(datetime.now(timezone.utc).timestamp())
    signature = compute_webhook_signature(SECRET, timestamp, BODY)

    assert parse_webhook_event(BODY, _header(timestamp, signature), SECRET).proposal_id.startswith("bea8d060")


def test_parse_v2_payload_with_participants() -> None:
    raw = json.dumps(V2_PAYLOAD)
    timestamp = TIMESTAMP
    header = _header(timestamp, compute_webhook_signature(SECRET, timestamp, raw))

    event = parse_webhook_event(raw, header, SECRET, now=NOW)

    assert event.is_detailed is True
    assert event.status is ProposalStatus.APPROVED
    assert (event.status_raw, event.status_name) == (2, "APROVADA")
    assert event.event_reason is ProposalEventReason.DOCUMENTS_CHANGED
    assert event.event_reason_raw == "DOCUMENTOS_ALTERADOS"
    assert event.refusal_reason is None
    assert event.event_date == datetime(2026, 10, 12, 17, 20, 31, 512000, tzinfo=timezone.utc)
    assert event.seller is None

    assert event.buyer is not None
    assert event.buyer.document == "12345678909"
    assert event.buyer.active_step is not None
    assert event.buyer.active_step.step is ProposalStep.DOCUMENT_CORRECTION
    assert event.buyer.active_step.action_owner is ActionOwner.INTEGRATOR
    assert event.buyer.documents[0].status is DocumentStatus.INVALID

    assert event.store is not None
    assert event.store.document == "11222333000181"
    assert event.store.active_step is not None
    assert event.store.active_step.step is ProposalStep.DOCUMENT_SUBMISSION


def test_parse_payload_without_verification_for_tests() -> None:
    event = parse_webhook_payload(
        json.dumps({"id_proposta": "00000000-0000-0000-0000-000000000001", "enum_status": 3, "status": "Refused"})
    )

    assert event.status is ProposalStatus.REFUSED
    assert event.proposal_id == "00000000-0000-0000-0000-000000000001"
    assert event.is_detailed is False


def test_unknown_status_and_reason_are_preserved() -> None:
    event = parse_webhook_payload(
        json.dumps(
            {
                "id_proposta": "00000000-0000-0000-0000-000000000002",
                "enum_status": 77,
                "status": "NOVO",
                "motivo_evento": "OUTRO_MOTIVO",
            }
        )
    )

    assert event.status is ProposalStatus.UNKNOWN
    assert event.status_raw == 77
    assert event.status_name == "NOVO"
    assert event.event_reason is ProposalEventReason.UNKNOWN
    assert event.event_reason_raw == "OUTRO_MOTIVO"
    assert event.is_detailed is True


def test_status_by_name_when_the_code_is_missing() -> None:
    event = parse_webhook_payload('{"id_proposta": "00000000-0000-0000-0000-000000000002", "status": "EM_NEGOCIACAO"}')

    assert event.status is ProposalStatus.IN_NEGOTIATION
    assert event.status_raw is None


@pytest.mark.parametrize(
    "raw", ["", "not json", "[]", "null", '{"enum_status": 2}', '{"id_proposta": ""}', b"\xff\xfe"]
)
def test_invalid_json_or_missing_id_raises(raw: Any) -> None:
    with pytest.raises(CredicarroWebhookSignatureError):
        parse_webhook_payload(raw)


def test_signature_is_checked_before_the_body_is_parsed() -> None:
    with pytest.raises(CredicarroWebhookSignatureError, match="assinatura"):
        parse_webhook_event("not json", _header(signature="0" * 64), SECRET, now=NOW)


def test_verify_authorization_is_constant_time_equality() -> None:
    assert verify_webhook_authorization("Basic dXN1YXJpbzpzZW5oYQ==", "Basic dXN1YXJpbzpzZW5oYQ==") is True
    assert verify_webhook_authorization("Basic dXN1YXJpbzpzZW5oYQ==", "Basic outro") is False
    assert verify_webhook_authorization("Bearer abc", "Basic abc") is False
    assert verify_webhook_authorization("Bearer ábc", "Bearer ábc") is True
    assert verify_webhook_authorization(None, "Basic x") is False
    assert verify_webhook_authorization("Basic x", None) is False
    assert verify_webhook_authorization("", "") is False
