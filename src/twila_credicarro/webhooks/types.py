from dataclasses import dataclass, field
from datetime import date, datetime
from enum import IntEnum
from typing import Optional, Union

from .._internal.enum_support import build_name_table, enum_from_name, enum_from_value
from .._internal.masking import masked_repr
from ..paged_result import ListRequest
from ..proposals.types import (
    PendingAction,
    ProposalEventReason,
    ProposalParticipantState,
    ProposalStatus,
    get_pending_actions,
)


class WebhookType(IntEnum):
    """Evento notificado pelo webhook (`tipo`)."""

    CUSTOMER = 1
    SIMULATION = 2
    PROPOSAL = 3
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "WebhookType":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "WebhookType":
        return enum_from_name(_WEBHOOK_TYPE_NAMES, value, cls.UNKNOWN)


class WebhookAuthenticationType(IntEnum):
    """Autenticação enviada pela Credicarro ao chamar a URL (`tipo_autenticacao`)."""

    NONE = 1
    BASIC = 2
    JWT = 3
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "WebhookAuthenticationType":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "WebhookAuthenticationType":
        return enum_from_name(_WEBHOOK_AUTHENTICATION_NAMES, value, cls.UNKNOWN)


class WebhookStatus(IntEnum):
    ACTIVE = 1
    INACTIVE = 2
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "WebhookStatus":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "WebhookStatus":
        return enum_from_name(_WEBHOOK_STATUS_NAMES, value, cls.UNKNOWN)


_WEBHOOK_TYPE_NAMES = build_name_table(WebhookType)
_WEBHOOK_AUTHENTICATION_NAMES = build_name_table(WebhookAuthenticationType)
_WEBHOOK_STATUS_NAMES = build_name_table(WebhookStatus)


@dataclass(frozen=True)
class Webhook:
    """Webhook cadastrado. A credencial e o segredo de assinatura nunca são devolvidos."""

    id: str
    type: WebhookType
    url: str
    authentication_type: WebhookAuthenticationType
    status: WebhookStatus


@dataclass(frozen=True)
class CreateWebhookRequest:
    """`credential` é obrigatória em Basic (Base64 de `usuario:senha`) e Jwt (o token)."""

    type: WebhookType
    url: str
    authentication_type: WebhookAuthenticationType
    credential: Optional[str] = field(default=None, repr=False)


@dataclass(frozen=True)
class CreateWebhookResult:
    """O `signing_secret` só vem nesta resposta e não pode ser recuperado depois: guarde-o agora."""

    webhook_id: str
    signing_secret: str = field(repr=False)


@dataclass(frozen=True)
class UpdateWebhookRequest:
    """Atualiza tipo, URL e status. Sem `status`, o atual é mantido."""

    type: WebhookType
    url: str
    status: Optional[WebhookStatus] = None


DateFilter = Union[str, date, datetime]


@dataclass(frozen=True)
class ListWebhookDeliveriesRequest:
    """Filtros e paginação do histórico de envios (`GET v1/webhook/audit`). Todos os filtros são opcionais.

    `date` (sem horário) vale pelo dia inteiro; `datetime` sem fuso é enviado em `-03:00`.
    """

    initial_date: Optional[DateFilter] = None
    final_date: Optional[DateFilter] = None
    proposal_id: Optional[str] = None
    simulation_id: Optional[str] = None
    proposal_number: Optional[str] = None
    status_code: Optional[int] = None
    page: int = 1
    page_size: int = 10

    def __post_init__(self) -> None:
        ListRequest(self.page, self.page_size)


@masked_repr(secret=("request", "response"))
@dataclass(frozen=True)
class WebhookDelivery:
    """Envio registrado no histórico. Use `id` (`id_auditoria`) em `resend`."""

    id: str
    type: WebhookType
    request: str
    response: str
    created_at: Optional[datetime]
    webhook_id: Optional[str] = None
    status_code: Optional[int] = None
    """Status HTTP devolvido pela sua URL; `None` quando ela não respondeu (ex.: timeout)."""


@masked_repr(secret=("response",))
@dataclass(frozen=True)
class WebhookResendResult:
    """Resultado imediato do reenvio. `status_code` é `None` quando a sua URL não respondeu."""

    response: str
    status_code: Optional[int] = None


@masked_repr(secret=("refusal_reason",))
@dataclass(frozen=True)
class ProposalWebhookEvent:
    """Notificação de proposta. `is_detailed` indica o payload v2 (retrato completo); o v1 traz só id e status."""

    proposal_id: str
    status: ProposalStatus
    status_raw: Optional[int] = None
    status_name: Optional[str] = None
    event_reason: Optional[ProposalEventReason] = None
    event_reason_raw: Optional[str] = None
    refusal_reason: Optional[str] = None
    event_date: Optional[datetime] = None
    buyer: Optional[ProposalParticipantState] = None
    seller: Optional[ProposalParticipantState] = None
    store: Optional[ProposalParticipantState] = None
    is_detailed: bool = False

    def get_pending_actions(self) -> list[PendingAction]:
        """Ações do integrador num evento v2 (`is_detailed`). O payload v1 não traz participantes: lista vazia —
        consulte a proposta (`client.proposals.get`) para saber o que fazer."""
        return get_pending_actions(self)
