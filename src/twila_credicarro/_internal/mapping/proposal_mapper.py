from typing import Any, Optional

from ...proposals.types import (
    ActionOwner,
    ActiveStep,
    BiometryStatus,
    CompletedStep,
    CreateProposalRequest,
    DepositAccount,
    DocumentStatus,
    DocumentType,
    ProposalDetails,
    ProposalDocument,
    ProposalDocumentUpload,
    ProposalParticipantState,
    ProposalStatus,
    ProposalStep,
    ProposalSummary,
    ProposalType,
    StepSituation,
    VehicleDetails,
)
from ..datetime_parsing import parse_iso_datetime
from .wire import as_dict, opt_dict, opt_int, opt_list, opt_str, req_str


def create_proposal_request_to_wire(request: CreateProposalRequest) -> dict[str, Any]:
    return {"cpf": request.cpf, "simulacaoId": str(request.simulation_id)}


def vehicle_details_to_wire(details: VehicleDetails) -> dict[str, Any]:
    return {
        "renavam": details.renavam,
        "chassi": details.chassis,
        "placa": details.license_plate,
        "cor": details.color,
    }


def deposit_account_to_wire(account: DepositAccount) -> dict[str, Any]:
    return {
        "cpfTitular": account.holder_cpf,
        "codigoBanco": account.bank_code,
        "agencia": account.branch,
        "digitoAgencia": account.branch_digit,
        "conta": account.account_number,
        "digitoConta": account.account_digit,
        "tipoConta": account.account_type.value,
    }


def document_upload_to_wire(upload: ProposalDocumentUpload) -> dict[str, Any]:
    if upload.document_type is DocumentType.UNKNOWN:
        raise ValueError("document_type não pode ser UNKNOWN no envio de documento.")

    return {
        "participante": upload.participant.value,
        "tipoDocumento": int(upload.document_type),
        "nomeArquivo": upload.file.file_name,
        "conteudoBase64": upload.file.base64_content,
    }


def proposal_id_to_public(wire: Any) -> str:
    return req_str(as_dict(wire, "a resposta da criação da proposta"), "id_proposta")


def proposal_details_to_public(wire: dict[str, Any]) -> ProposalDetails:
    status_raw = opt_int(wire, "enum_status")
    status_name = opt_str(wire, "status")
    type_name = opt_str(wire, "tipo")

    return ProposalDetails(
        id=req_str(wire, "id_proposta"),
        number=opt_int(wire, "numero"),
        simulation_id=opt_str(wire, "id_simulacao"),
        status=ProposalStatus.resolve(status_raw, status_name),
        type=ProposalType.from_wire_name(type_name),
        status_raw=status_raw,
        status_name=status_name,
        type_name=type_name,
        created_at=parse_iso_datetime(wire.get("data_criacao")),
        refusal_reason=opt_str(wire, "motivo_recusa"),
        biometry_link=opt_str(wire, "link_biometria"),
        buyer=participant_to_public(opt_dict(wire, "comprador"), "cpf"),
        seller=participant_to_public(opt_dict(wire, "vendedor"), "cpf"),
        store=participant_to_public(opt_dict(wire, "loja"), "cnpj", with_biometry=False),
    )


def proposal_summary_to_public(wire: dict[str, Any]) -> ProposalSummary:
    status_name = opt_str(wire, "status")
    type_name = opt_str(wire, "tipo")
    buyer = opt_dict(wire, "comprador")
    seller = opt_dict(wire, "vendedor")

    return ProposalSummary(
        id=req_str(wire, "id_proposta"),
        number=opt_int(wire, "numero"),
        simulation_id=opt_str(wire, "id_simulacao"),
        type=ProposalType.from_wire_name(type_name),
        status=ProposalStatus.from_wire_name(status_name),
        status_name=status_name,
        type_name=type_name,
        buyer_cpf=opt_str(buyer, "cpf") if buyer is not None else None,
        seller_cpf=opt_str(seller, "cpf") if seller is not None else None,
        created_at=parse_iso_datetime(wire.get("data_criacao")),
    )


def participant_to_public(
    wire: Optional[dict[str, Any]], document_key: str, with_biometry: bool = True
) -> Optional[ProposalParticipantState]:
    """`with_biometry=False` para a loja, que não tem biometria no schema."""
    if wire is None:
        return None

    biometry_raw = opt_int(wire, "enum_biometria") if with_biometry else None
    biometry_name = opt_str(wire, "biometria") if with_biometry else None
    has_biometry = biometry_raw is not None or biometry_name is not None

    return ProposalParticipantState(
        document=opt_str(wire, document_key),
        biometry=BiometryStatus.resolve(biometry_raw, biometry_name) if has_biometry else None,
        biometry_raw=biometry_raw,
        biometry_name=biometry_name,
        active_step=_active_step(opt_dict(wire, "status_ativo")),
        completed_steps=[_completed_step(item) for item in _dicts(wire, "etapas_concluidas")],
        documents=[_document(item) for item in _dicts(wire, "documentos")],
    )


def _dicts(wire: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [item for item in opt_list(wire, key) if isinstance(item, dict)]


def _active_step(wire: Optional[dict[str, Any]]) -> Optional[ActiveStep]:
    if wire is None:
        return None

    step_raw = opt_int(wire, "enum_etapa")
    step_name = opt_str(wire, "etapa")
    situation_raw = opt_int(wire, "enum_situacao")
    situation_name = opt_str(wire, "situacao")
    owner_raw = opt_int(wire, "enum_responsavel_acao")
    owner_name = opt_str(wire, "responsavel_acao")

    return ActiveStep(
        step=ProposalStep.resolve(step_raw, step_name),
        situation=StepSituation.resolve(situation_raw, situation_name),
        action_owner=ActionOwner.resolve(owner_raw, owner_name),
        step_raw=step_raw,
        step_name=step_name,
        situation_raw=situation_raw,
        situation_name=situation_name,
        action_owner_raw=owner_raw,
        action_owner_name=owner_name,
    )


def _completed_step(wire: dict[str, Any]) -> CompletedStep:
    step_raw = opt_int(wire, "enum_etapa")
    step_name = opt_str(wire, "etapa")

    return CompletedStep(
        step=ProposalStep.resolve(step_raw, step_name),
        step_raw=step_raw,
        step_name=step_name,
        date=parse_iso_datetime(wire.get("data")),
    )


def _document(wire: dict[str, Any]) -> ProposalDocument:
    type_raw = opt_int(wire, "enum_tipo")
    type_name = opt_str(wire, "tipo")
    status_raw = opt_int(wire, "enum_status")
    status_name = opt_str(wire, "status")

    return ProposalDocument(
        type=DocumentType.resolve(type_raw, type_name),
        status=DocumentStatus.resolve(status_raw, status_name),
        type_raw=type_raw,
        type_name=type_name,
        status_raw=status_raw,
        status_name=status_name,
        reason=opt_str(wire, "motivo"),
    )
