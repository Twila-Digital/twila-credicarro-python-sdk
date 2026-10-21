import base64
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import BinaryIO, Optional, Protocol, Union

from .._internal.enum_support import build_name_table, enum_from_name, enum_from_value, enum_resolve
from .._internal.masking import masked_repr
from .._internal.path import Identifier

MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024
MAX_DOCUMENT_FILE_NAME_LENGTH = 255
ALLOWED_DOCUMENT_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png")


class ProposalType(IntEnum):
    """Modalidade da proposta (`tipo`: `Financing` ou `Refinancing`)."""

    FINANCING = 1
    REFINANCING = 2
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "ProposalType":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "ProposalType":
        return enum_from_name(_PROPOSAL_TYPE_NAMES, value, cls.UNKNOWN)


class ProposalStatus(IntEnum):
    """Status da proposta. Aceita os nomes em português (`EM_ANALISE`, payload v2) e em inglês (`Analysing`, v1)."""

    ANALYSING = 1
    APPROVED = 2
    REFUSED = 3
    CANCELED = 4
    MANUAL_ANALYSIS = 5
    COMPLETED = 6
    IN_NEGOTIATION = 7
    EXPIRED = 8
    PENDING = 9
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "ProposalStatus":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "ProposalStatus":
        return enum_from_name(_PROPOSAL_STATUS_NAMES, value, cls.UNKNOWN)

    @classmethod
    def resolve(cls, value: object, name: object) -> "ProposalStatus":
        return enum_resolve(cls, _PROPOSAL_STATUS_NAMES, value, name, cls.UNKNOWN)


class ProposalStep(IntEnum):
    """Etapa do participante (`enum_etapa` / `etapa`)."""

    UNDEFINED = 0
    PROPOSAL_CREATED = 1
    PROPOSAL_APPROVED = 2
    SELLER_NOTIFICATION = 3
    BIOMETRY_ANALYSIS = 4
    DEPOSIT_ACCOUNT = 5
    DOCUMENT_SUBMISSION = 6
    DOCUMENT_CORRECTION = 7
    VEHICLE_DETAILS = 8
    INSPECTION = 9
    SIGNATURE = 10
    PAYMENT = 11
    PROPOSAL_COMPLETED = 12
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "ProposalStep":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "ProposalStep":
        return enum_from_name(_PROPOSAL_STEP_NAMES, value, cls.UNKNOWN)

    @classmethod
    def resolve(cls, value: object, name: object) -> "ProposalStep":
        return enum_resolve(cls, _PROPOSAL_STEP_NAMES, value, name, cls.UNKNOWN)


class StepSituation(IntEnum):
    """Situação da etapa (`enum_situacao` / `situacao`)."""

    AWAITING_SUBMISSION = 1
    AWAITING_CUSTOMER = 2
    PROCESSING = 3
    PENDING_CORRECTION = 4
    BLOCKED = 5
    COMPLETED = 6
    CANCELED = 7
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "StepSituation":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "StepSituation":
        return enum_from_name(_STEP_SITUATION_NAMES, value, cls.UNKNOWN)

    @classmethod
    def resolve(cls, value: object, name: object) -> "StepSituation":
        return enum_resolve(cls, _STEP_SITUATION_NAMES, value, name, cls.UNKNOWN)


class ActionOwner(IntEnum):
    """Quem precisa agir (`enum_responsavel_acao` / `responsavel_acao`)."""

    NONE = 0
    CUSTOMER = 1
    INTEGRATOR = 2
    CREDICARRO = 3
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "ActionOwner":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "ActionOwner":
        return enum_from_name(_ACTION_OWNER_NAMES, value, cls.UNKNOWN)

    @classmethod
    def resolve(cls, value: object, name: object) -> "ActionOwner":
        return enum_resolve(cls, _ACTION_OWNER_NAMES, value, name, cls.UNKNOWN)


class BiometryStatus(IntEnum):
    """Situação da biometria (`enum_biometria` / `biometria`)."""

    NOT_STARTED = 0
    SESSION_CREATED = 1
    IN_ANALYSIS = 2
    APPROVED = 3
    REJECTED = 4
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "BiometryStatus":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "BiometryStatus":
        return enum_from_name(_BIOMETRY_STATUS_NAMES, value, cls.UNKNOWN)

    @classmethod
    def resolve(cls, value: object, name: object) -> "BiometryStatus":
        return enum_resolve(cls, _BIOMETRY_STATUS_NAMES, value, name, cls.UNKNOWN)


class DocumentStatus(IntEnum):
    """Status do documento (`enum_status` / `status` em `documentos`). `PENDING` = exigido e ainda não enviado."""

    RECEIVED = 0
    VALID = 1
    INVALID = 2
    IN_ANALYSIS = 3
    DELETED = 4
    PENDING = 5
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "DocumentStatus":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "DocumentStatus":
        return enum_from_name(_DOCUMENT_STATUS_NAMES, value, cls.UNKNOWN)

    @classmethod
    def resolve(cls, value: object, name: object) -> "DocumentStatus":
        return enum_resolve(cls, _DOCUMENT_STATUS_NAMES, value, name, cls.UNKNOWN)


class DocumentType(IntEnum):
    """Tipo do documento (`tipoDocumento` no envio; `enum_tipo` / `tipo` na consulta)."""

    CNH = 1
    CPF = 2
    RG = 3
    PROOF_OF_INCOME = 4
    PROOF_OF_ADDRESS = 5
    VEHICLE_DOCUMENT = 6
    DIGITAL_CNH = 7
    ECV_REPORT = 8
    INSPECTION_REPORT = 9
    CNPJ_CARD = 11
    ATPV = 57
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "DocumentType":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "DocumentType":
        return enum_from_name(_DOCUMENT_TYPE_NAMES, value, cls.UNKNOWN)

    @classmethod
    def resolve(cls, value: object, name: object) -> "DocumentType":
        return enum_resolve(cls, _DOCUMENT_TYPE_NAMES, value, name, cls.UNKNOWN)


class ProposalEventReason(IntEnum):
    """`motivo_evento` do webhook v2: o que disparou a notificação."""

    STATUS_CHANGED = 1
    STEPS_CHANGED = 2
    DOCUMENTS_CHANGED = 3
    UNKNOWN = -1

    @classmethod
    def from_wire_name(cls, value: object) -> "ProposalEventReason":
        return enum_from_name(_EVENT_REASON_NAMES, value, cls.UNKNOWN)


class ProposalParticipant(str, Enum):
    """`participante` do envio de documento."""

    BUYER = "COMPRADOR"
    SELLER = "VENDEDOR"
    STORE = "LOJA"


class DepositAccountType(str, Enum):
    """`tipoConta` da conta de recebimento."""

    CHECKING = "CORRENTE"
    SAVINGS = "POUPANCA"
    PAYMENT = "PAGAMENTO"


class PendingActionKind(str, Enum):
    SEND_DOCUMENTS = "SendDocuments"
    CORRECT_DOCUMENTS = "CorrectDocuments"
    SEND_VEHICLE_DETAILS = "SendVehicleDetails"
    SEND_DEPOSIT_ACCOUNT = "SendDepositAccount"


_PROPOSAL_TYPE_NAMES = build_name_table(ProposalType)

_PROPOSAL_STATUS_NAMES = build_name_table(
    ProposalStatus,
    {
        "EM_ANALISE": ProposalStatus.ANALYSING,
        "APROVADA": ProposalStatus.APPROVED,
        "RECUSADA": ProposalStatus.REFUSED,
        "CANCELADA": ProposalStatus.CANCELED,
        "ANALISE_MANUAL": ProposalStatus.MANUAL_ANALYSIS,
        "FINALIZADA": ProposalStatus.COMPLETED,
        "EM_NEGOCIACAO": ProposalStatus.IN_NEGOTIATION,
        "EXPIRADA": ProposalStatus.EXPIRED,
        "PENDENTE": ProposalStatus.PENDING,
    },
)

_PROPOSAL_STEP_NAMES = build_name_table(
    ProposalStep,
    {
        "INDEFINIDO": ProposalStep.UNDEFINED,
        "PROPOSTA_CRIADA": ProposalStep.PROPOSAL_CREATED,
        "PROPOSTA_APROVADA": ProposalStep.PROPOSAL_APPROVED,
        "NOTIFICACAO_VENDEDOR": ProposalStep.SELLER_NOTIFICATION,
        "ANALISE_BIOMETRIA": ProposalStep.BIOMETRY_ANALYSIS,
        "CONTA_RECEBIMENTO": ProposalStep.DEPOSIT_ACCOUNT,
        "ENVIO_DOCUMENTOS": ProposalStep.DOCUMENT_SUBMISSION,
        "CORRECAO_DOCUMENTOS": ProposalStep.DOCUMENT_CORRECTION,
        "DADOS_VEICULO": ProposalStep.VEHICLE_DETAILS,
        "VISTORIA": ProposalStep.INSPECTION,
        "ASSINATURA": ProposalStep.SIGNATURE,
        "PAGAMENTO": ProposalStep.PAYMENT,
        "PROPOSTA_FINALIZADA": ProposalStep.PROPOSAL_COMPLETED,
    },
)

_STEP_SITUATION_NAMES = build_name_table(
    StepSituation,
    {
        "AGUARDANDO_ENVIO": StepSituation.AWAITING_SUBMISSION,
        "AGUARDANDO_CLIENTE": StepSituation.AWAITING_CUSTOMER,
        "EM_PROCESSAMENTO": StepSituation.PROCESSING,
        "PENDENTE_CORRECAO": StepSituation.PENDING_CORRECTION,
        "BLOQUEADA": StepSituation.BLOCKED,
        "CONCLUIDA": StepSituation.COMPLETED,
        "CANCELADA": StepSituation.CANCELED,
    },
)

_ACTION_OWNER_NAMES = build_name_table(
    ActionOwner,
    {
        "NENHUM": ActionOwner.NONE,
        "CLIENTE": ActionOwner.CUSTOMER,
        "INTEGRADOR": ActionOwner.INTEGRATOR,
        "CREDICARRO": ActionOwner.CREDICARRO,
    },
)

_BIOMETRY_STATUS_NAMES = build_name_table(
    BiometryStatus,
    {
        "NAO_INICIADA": BiometryStatus.NOT_STARTED,
        "SESSAO_CRIADA": BiometryStatus.SESSION_CREATED,
        "EM_ANALISE": BiometryStatus.IN_ANALYSIS,
        "APROVADA": BiometryStatus.APPROVED,
        "REPROVADA": BiometryStatus.REJECTED,
    },
)

_DOCUMENT_STATUS_NAMES = build_name_table(
    DocumentStatus,
    {
        "RECEBIDO": DocumentStatus.RECEIVED,
        "VALIDO": DocumentStatus.VALID,
        "INVALIDO": DocumentStatus.INVALID,
        "EM_ANALISE": DocumentStatus.IN_ANALYSIS,
        "EXCLUIDO": DocumentStatus.DELETED,
        "PENDENTE": DocumentStatus.PENDING,
    },
)

_DOCUMENT_TYPE_NAMES = build_name_table(
    DocumentType,
    {
        "COMPROVANTE_RENDA": DocumentType.PROOF_OF_INCOME,
        "COMPROVANTE_RESIDENCIA": DocumentType.PROOF_OF_ADDRESS,
        "DOCUMENTO_VEICULO": DocumentType.VEHICLE_DOCUMENT,
        "CNH_DIGITAL": DocumentType.DIGITAL_CNH,
        "LAUDO_ECV": DocumentType.ECV_REPORT,
        "LAUDO_VISTORIA": DocumentType.INSPECTION_REPORT,
        "CARTAO_CNPJ": DocumentType.CNPJ_CARD,
    },
)

_EVENT_REASON_NAMES = build_name_table(
    ProposalEventReason,
    {
        "STATUS_ALTERADO": ProposalEventReason.STATUS_CHANGED,
        "ETAPAS_ALTERADAS": ProposalEventReason.STEPS_CHANGED,
        "DOCUMENTOS_ALTERADOS": ProposalEventReason.DOCUMENTS_CHANGED,
    },
)


@dataclass(frozen=True)
class DocumentFile:
    """Arquivo para `POST v2/proposal/{id}/document`: PDF, JPG/JPEG ou PNG, de 1 byte a 10 MiB, em Base64 puro.

    O conteúdo fica guardado uma única vez, já em Base64; as tentativas e o replay do 401 reaproveitam esse mesmo
    texto. A construção direta valida nome, Base64 e tamanho, como as fábricas.
    """

    file_name: str
    base64_content: str = field(repr=False)

    def __post_init__(self) -> None:
        _validate_file_name(self.file_name)
        _validate_base64_content(self.base64_content)

    @classmethod
    def from_bytes(cls, content: Union[bytes, bytearray, memoryview], file_name: str) -> "DocumentFile":
        _validate_file_name(file_name)
        _validate_content_size(len(content))
        return cls(file_name=file_name, base64_content=base64.b64encode(content).decode("ascii"))

    @classmethod
    def from_stream(cls, stream: BinaryIO, file_name: str) -> "DocumentFile":
        """Lê em laço até `10 MiB + 1` bytes (nunca confia em tamanho informado) e recusa o que passar do limite."""
        _validate_file_name(file_name)

        buffer = bytearray()
        while len(buffer) <= MAX_DOCUMENT_SIZE_BYTES:
            chunk = stream.read(min(_READ_CHUNK_SIZE, MAX_DOCUMENT_SIZE_BYTES + 1 - len(buffer)))
            if not chunk:
                break
            buffer.extend(chunk)

        return cls.from_bytes(buffer, file_name)

    @classmethod
    def from_file(cls, path: Union[str, "os.PathLike[str]"], file_name: Optional[str] = None) -> "DocumentFile":
        resolved_name = file_name if file_name is not None else os.path.basename(os.fspath(path))
        _validate_file_name(resolved_name)

        with open(path, "rb") as handle:
            return cls.from_stream(handle, resolved_name)


_READ_CHUNK_SIZE = 64 * 1024
_BASE64_PATTERN = re.compile(r"[A-Za-z0-9+/]*={0,2}")


def _validate_file_name(file_name: str) -> None:
    if not isinstance(file_name, str) or not file_name.strip():
        raise ValueError("O nome do arquivo é obrigatório.")
    if len(file_name) > MAX_DOCUMENT_FILE_NAME_LENGTH:
        raise ValueError(f"O nome do arquivo deve ter no máximo {MAX_DOCUMENT_FILE_NAME_LENGTH} caracteres.")
    if "/" in file_name or "\\" in file_name or "\x00" in file_name:
        raise ValueError("O nome do arquivo não pode conter caminho (informe só o nome, ex.: cnh.pdf).")
    if not file_name.lower().endswith(ALLOWED_DOCUMENT_EXTENSIONS):
        raise ValueError("A extensão do arquivo deve ser .pdf, .jpg, .jpeg ou .png.")


def _validate_base64_content(content: str) -> None:
    if not isinstance(content, str) or len(content) % 4 != 0 or _BASE64_PATTERN.fullmatch(content) is None:
        raise ValueError("O conteúdo do arquivo deve estar em Base64 puro (sem prefixo 'data:' nem quebras de linha).")

    padding = len(content) - len(content.rstrip("="))
    _validate_content_size(len(content) // 4 * 3 - padding)


def _validate_content_size(size: int) -> None:
    if size < 1:
        raise ValueError("O arquivo está vazio.")
    if size > MAX_DOCUMENT_SIZE_BYTES:
        raise ValueError("O arquivo excede o limite de 10 MiB.")


@masked_repr(cpf=("cpf",))
@dataclass(frozen=True)
class CreateProposalRequest:
    """`simulation_id` é o `id_simulacao` da opção escolhida (cada opção gera uma única proposta)."""

    cpf: str
    simulation_id: Identifier


@masked_repr(secret=("license_plate",))
@dataclass(frozen=True)
class VehicleDetails:
    """Dados do veículo, aceitos enquanto a etapa `DADOS_VEICULO` (8) está ativa."""

    renavam: str
    chassis: str
    license_plate: str
    color: str


@masked_repr(cpf=("holder_cpf",), secret=("branch", "branch_digit", "account_number", "account_digit"))
@dataclass(frozen=True)
class DepositAccount:
    """Conta de recebimento (só refinanciamento, na etapa `CONTA_RECEBIMENTO`). Enviar de novo substitui."""

    holder_cpf: str
    bank_code: str
    branch: str
    branch_digit: str
    account_number: str
    account_digit: str
    account_type: DepositAccountType


@dataclass(frozen=True)
class ProposalDocumentUpload:
    participant: ProposalParticipant
    document_type: DocumentType
    file: DocumentFile


@dataclass(frozen=True)
class ActiveStep:
    step: ProposalStep
    situation: StepSituation
    action_owner: ActionOwner
    step_raw: Optional[int] = None
    step_name: Optional[str] = None
    situation_raw: Optional[int] = None
    situation_name: Optional[str] = None
    action_owner_raw: Optional[int] = None
    action_owner_name: Optional[str] = None


@dataclass(frozen=True)
class CompletedStep:
    step: ProposalStep
    step_raw: Optional[int] = None
    step_name: Optional[str] = None
    date: Optional[datetime] = None


@dataclass(frozen=True)
class ProposalDocument:
    type: DocumentType
    status: DocumentStatus
    type_raw: Optional[int] = None
    type_name: Optional[str] = None
    status_raw: Optional[int] = None
    status_name: Optional[str] = None
    reason: Optional[str] = None


@masked_repr(document=("document",))
@dataclass(frozen=True)
class ProposalParticipantState:
    """Estado de um participante (comprador, vendedor ou loja). `document` é o CPF ou, na loja, o CNPJ."""

    document: Optional[str] = None
    biometry: Optional[BiometryStatus] = None
    biometry_raw: Optional[int] = None
    biometry_name: Optional[str] = None
    active_step: Optional[ActiveStep] = None
    completed_steps: list[CompletedStep] = field(default_factory=list)
    documents: list[ProposalDocument] = field(default_factory=list)


@dataclass(frozen=True)
class PendingAction:
    """Ação que o integrador precisa executar. `document_types` só vem em `SEND_DOCUMENTS` e `CORRECT_DOCUMENTS`."""

    participant: ProposalParticipant
    step: ProposalStep
    kind: PendingActionKind
    document_types: tuple[DocumentType, ...] = ()


@masked_repr(secret=("refusal_reason", "biometry_link"))
@dataclass(frozen=True)
class ProposalDetails:
    """Retrato atual da proposta (`GET v2/proposal/{id}`)."""

    id: str
    number: Optional[int]
    simulation_id: Optional[str]
    status: ProposalStatus
    type: ProposalType
    status_raw: Optional[int] = None
    status_name: Optional[str] = None
    type_name: Optional[str] = None
    created_at: Optional[datetime] = None
    refusal_reason: Optional[str] = None
    biometry_link: Optional[str] = None
    buyer: Optional[ProposalParticipantState] = None
    seller: Optional[ProposalParticipantState] = None
    store: Optional[ProposalParticipantState] = None

    def get_pending_actions(self) -> list[PendingAction]:
        """O que o integrador precisa fazer agora, participante a participante (`ActionOwner.INTEGRATOR`).

        Etapa 6 => enviar os documentos `PENDING`; 7 => corrigir os `INVALID`; 8 => dados do veículo;
        5 => conta de recebimento.
        """
        return get_pending_actions(self)


@masked_repr(cpf=("buyer_cpf", "seller_cpf"))
@dataclass(frozen=True)
class ProposalSummary:
    """Proposta da listagem e das consultas v1 (`ProposalResponse`)."""

    id: str
    number: Optional[int]
    simulation_id: Optional[str]
    type: ProposalType
    status: ProposalStatus
    status_name: Optional[str] = None
    type_name: Optional[str] = None
    buyer_cpf: Optional[str] = None
    seller_cpf: Optional[str] = None
    created_at: Optional[datetime] = None


class _HasParticipants(Protocol):
    """`ProposalDetails` ou o evento detalhado do webhook (`ProposalWebhookEvent`)."""

    @property
    def buyer(self) -> Optional[ProposalParticipantState]: ...

    @property
    def seller(self) -> Optional[ProposalParticipantState]: ...

    @property
    def store(self) -> Optional[ProposalParticipantState]: ...


def get_pending_actions(proposal: _HasParticipants) -> list[PendingAction]:
    """Ações do integrador numa proposta consultada (`ProposalDetails`) ou num evento v2 do webhook."""
    participants = (
        (ProposalParticipant.BUYER, proposal.buyer),
        (ProposalParticipant.SELLER, proposal.seller),
        (ProposalParticipant.STORE, proposal.store),
    )

    actions: list[PendingAction] = []
    for participant, state in participants:
        action = _pending_action(participant, state)
        if action is not None:
            actions.append(action)
    return actions


def _pending_action(
    participant: ProposalParticipant, state: Optional[ProposalParticipantState]
) -> Optional[PendingAction]:
    if state is None or state.active_step is None:
        return None

    active = state.active_step
    if active.action_owner is not ActionOwner.INTEGRATOR:
        return None

    if active.step is ProposalStep.DOCUMENT_SUBMISSION:
        return PendingAction(
            participant,
            active.step,
            PendingActionKind.SEND_DOCUMENTS,
            _document_types(state, DocumentStatus.PENDING),
        )

    if active.step is ProposalStep.DOCUMENT_CORRECTION:
        return PendingAction(
            participant,
            active.step,
            PendingActionKind.CORRECT_DOCUMENTS,
            _document_types(state, DocumentStatus.INVALID),
        )

    if active.step is ProposalStep.VEHICLE_DETAILS:
        return PendingAction(participant, active.step, PendingActionKind.SEND_VEHICLE_DETAILS)

    if active.step is ProposalStep.DEPOSIT_ACCOUNT:
        return PendingAction(participant, active.step, PendingActionKind.SEND_DEPOSIT_ACCOUNT)

    return None


def _document_types(state: ProposalParticipantState, status: DocumentStatus) -> tuple[DocumentType, ...]:
    return tuple(document.type for document in state.documents if document.status is status)
