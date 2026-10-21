from enum import IntEnum
from typing import Any

import pytest

from twila_credicarro import (
    ActionOwner,
    BiometryStatus,
    DocumentStatus,
    DocumentType,
    OccupationType,
    ProposalEventReason,
    ProposalStatus,
    ProposalStep,
    ProposalType,
    SimulationType,
    StepSituation,
    WebhookAuthenticationType,
    WebhookStatus,
    WebhookType,
)

CONTRACT: dict[Any, dict[str, int]] = {
    ProposalStatus: {
        "ANALYSING": 1,
        "APPROVED": 2,
        "REFUSED": 3,
        "CANCELED": 4,
        "MANUAL_ANALYSIS": 5,
        "COMPLETED": 6,
        "IN_NEGOTIATION": 7,
        "EXPIRED": 8,
        "PENDING": 9,
    },
    ProposalStep: {
        "UNDEFINED": 0,
        "PROPOSAL_CREATED": 1,
        "PROPOSAL_APPROVED": 2,
        "SELLER_NOTIFICATION": 3,
        "BIOMETRY_ANALYSIS": 4,
        "DEPOSIT_ACCOUNT": 5,
        "DOCUMENT_SUBMISSION": 6,
        "DOCUMENT_CORRECTION": 7,
        "VEHICLE_DETAILS": 8,
        "INSPECTION": 9,
        "SIGNATURE": 10,
        "PAYMENT": 11,
        "PROPOSAL_COMPLETED": 12,
    },
    StepSituation: {
        "AWAITING_SUBMISSION": 1,
        "AWAITING_CUSTOMER": 2,
        "PROCESSING": 3,
        "PENDING_CORRECTION": 4,
        "BLOCKED": 5,
        "COMPLETED": 6,
        "CANCELED": 7,
    },
    ActionOwner: {"NONE": 0, "CUSTOMER": 1, "INTEGRATOR": 2, "CREDICARRO": 3},
    BiometryStatus: {"NOT_STARTED": 0, "SESSION_CREATED": 1, "IN_ANALYSIS": 2, "APPROVED": 3, "REJECTED": 4},
    DocumentStatus: {"RECEIVED": 0, "VALID": 1, "INVALID": 2, "IN_ANALYSIS": 3, "DELETED": 4, "PENDING": 5},
    DocumentType: {
        "CNH": 1,
        "CPF": 2,
        "RG": 3,
        "PROOF_OF_INCOME": 4,
        "PROOF_OF_ADDRESS": 5,
        "VEHICLE_DOCUMENT": 6,
        "DIGITAL_CNH": 7,
        "ECV_REPORT": 8,
        "INSPECTION_REPORT": 9,
        "CNPJ_CARD": 11,
        "ATPV": 57,
    },
    WebhookType: {"CUSTOMER": 1, "SIMULATION": 2, "PROPOSAL": 3},
    WebhookAuthenticationType: {"NONE": 1, "BASIC": 2, "JWT": 3},
    WebhookStatus: {"ACTIVE": 1, "INACTIVE": 2},
    OccupationType: {
        "RETIRED": 1,
        "PENSIONER": 2,
        "EMPLOYEE": 3,
        "SELF_EMPLOYED": 4,
        "FREELANCER": 6,
        "BUSINESS_OWNER": 7,
    },
}


@pytest.mark.parametrize("enum_class", list(CONTRACT))
def test_enum_values_follow_the_contract_and_have_unknown_minus_one(enum_class: type[IntEnum]) -> None:
    members = {member.name: int(member) for member in enum_class if member.name != "UNKNOWN"}

    assert members == CONTRACT[enum_class]
    assert int(enum_class["UNKNOWN"]) == -1


@pytest.mark.parametrize("enum_class", list(CONTRACT) + [ProposalType, SimulationType])
def test_unknown_numeric_values_fall_back_to_unknown(enum_class: Any) -> None:
    for value in (999, -5, None, "2", 2.5, True):
        assert enum_class.from_wire_value(value) is enum_class.UNKNOWN


@pytest.mark.parametrize("enum_class", [ProposalStatus, ProposalStep, StepSituation, ActionOwner, BiometryStatus])
def test_numeric_values_map_to_members(enum_class: Any) -> None:
    for name, value in CONTRACT[enum_class].items():
        assert enum_class.from_wire_value(value) is enum_class[name]


@pytest.mark.parametrize(
    "name,expected",
    [
        ("EM_ANALISE", ProposalStatus.ANALYSING),
        ("Analysing", ProposalStatus.ANALYSING),
        ("APROVADA", ProposalStatus.APPROVED),
        ("Approved", ProposalStatus.APPROVED),
        ("RECUSADA", ProposalStatus.REFUSED),
        ("Refused", ProposalStatus.REFUSED),
        ("CANCELADA", ProposalStatus.CANCELED),
        ("Canceled", ProposalStatus.CANCELED),
        ("ANALISE_MANUAL", ProposalStatus.MANUAL_ANALYSIS),
        ("ManualAnalysis", ProposalStatus.MANUAL_ANALYSIS),
        ("FINALIZADA", ProposalStatus.COMPLETED),
        ("Completed", ProposalStatus.COMPLETED),
        ("EM_NEGOCIACAO", ProposalStatus.IN_NEGOTIATION),
        ("InNegotiation", ProposalStatus.IN_NEGOTIATION),
        ("EXPIRADA", ProposalStatus.EXPIRED),
        ("Expired", ProposalStatus.EXPIRED),
        ("PENDENTE", ProposalStatus.PENDING),
        ("Pending", ProposalStatus.PENDING),
        ("aprovada", ProposalStatus.APPROVED),
        ("DESCONHECIDO", ProposalStatus.UNKNOWN),
        ("", ProposalStatus.UNKNOWN),
        (None, ProposalStatus.UNKNOWN),
    ],
)
def test_proposal_status_names_in_portuguese_and_english(name: Any, expected: ProposalStatus) -> None:
    assert ProposalStatus.from_wire_name(name) is expected


def test_resolve_prefers_the_numeric_code_and_falls_back_to_the_name() -> None:
    assert ProposalStatus.resolve(2, "RECUSADA") is ProposalStatus.APPROVED
    assert ProposalStatus.resolve(None, "RECUSADA") is ProposalStatus.REFUSED
    assert ProposalStatus.resolve(77, "APROVADA") is ProposalStatus.UNKNOWN
    assert ProposalStatus.resolve(None, None) is ProposalStatus.UNKNOWN


def test_step_situation_owner_biometry_document_names() -> None:
    assert ProposalStep.from_wire_name("ENVIO_DOCUMENTOS") is ProposalStep.DOCUMENT_SUBMISSION
    assert ProposalStep.from_wire_name("PROPOSTA_FINALIZADA") is ProposalStep.PROPOSAL_COMPLETED
    assert StepSituation.from_wire_name("PENDENTE_CORRECAO") is StepSituation.PENDING_CORRECTION
    assert ActionOwner.from_wire_name("INTEGRADOR") is ActionOwner.INTEGRATOR
    assert ActionOwner.from_wire_name("NENHUM") is ActionOwner.NONE
    assert BiometryStatus.from_wire_name("SESSAO_CRIADA") is BiometryStatus.SESSION_CREATED
    assert DocumentStatus.from_wire_name("INVALIDO") is DocumentStatus.INVALID
    assert DocumentType.from_wire_name("COMPROVANTE_RESIDENCIA") is DocumentType.PROOF_OF_ADDRESS
    assert DocumentType.from_wire_name("CNH_DIGITAL") is DocumentType.DIGITAL_CNH
    assert DocumentType.from_wire_name("ATPV") is DocumentType.ATPV


def test_event_reason_names() -> None:
    assert ProposalEventReason.from_wire_name("STATUS_ALTERADO") is ProposalEventReason.STATUS_CHANGED
    assert ProposalEventReason.from_wire_name("ETAPAS_ALTERADAS") is ProposalEventReason.STEPS_CHANGED
    assert ProposalEventReason.from_wire_name("DOCUMENTOS_ALTERADOS") is ProposalEventReason.DOCUMENTS_CHANGED
    assert ProposalEventReason.from_wire_name("NOVO_MOTIVO") is ProposalEventReason.UNKNOWN


def test_webhook_enums_from_text() -> None:
    assert WebhookType.from_wire_name("Proposal") is WebhookType.PROPOSAL
    assert WebhookAuthenticationType.from_wire_name("Jwt") is WebhookAuthenticationType.JWT
    assert WebhookAuthenticationType.from_wire_name("None") is WebhookAuthenticationType.NONE
    assert WebhookStatus.from_wire_name("Inactive") is WebhookStatus.INACTIVE
    assert WebhookStatus.from_wire_name("Paused") is WebhookStatus.UNKNOWN
