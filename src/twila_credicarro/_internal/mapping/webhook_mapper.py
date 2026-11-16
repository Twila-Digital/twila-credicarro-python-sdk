from datetime import datetime
from typing import Any, Optional, Union

from ...webhooks.types import (
    CreateWebhookRequest,
    CreateWebhookResult,
    DateFilter,
    ListWebhookDeliveriesRequest,
    UpdateWebhookRequest,
    Webhook,
    WebhookAuthenticationType,
    WebhookDelivery,
    WebhookDeliveryChartPoint,
    WebhookDeliveryChartRequest,
    WebhookResendResult,
    WebhookStatus,
    WebhookType,
)
from ..datetime_parsing import parse_iso_datetime
from ..http.query_string import QueryStringBuilder
from .wire import as_dict, as_list, opt_int, opt_str, req_int, req_str


def webhook_to_public(wire: dict[str, Any]) -> Webhook:
    return Webhook(
        id=req_str(wire, "id_webhook"),
        type=WebhookType.from_wire_name(wire.get("tipo")),
        url=req_str(wire, "url"),
        authentication_type=WebhookAuthenticationType.from_wire_name(wire.get("tipo_autenticacao")),
        status=WebhookStatus.from_wire_name(wire.get("status")),
    )


def create_webhook_result_to_public(wire: Any) -> CreateWebhookResult:
    root = as_dict(wire, "a resposta do cadastro do webhook")
    return CreateWebhookResult(
        webhook_id=req_str(root, "id_webhook"),
        signing_secret=req_str(root, "segredo_assinatura"),
    )


def create_webhook_request_to_wire(request: CreateWebhookRequest) -> dict[str, Any]:
    wire: dict[str, Any] = {
        "tipo": int(request.type),
        "url": request.url,
        "tipo_autenticacao": int(request.authentication_type),
    }
    if request.credential is not None:
        wire["credencial"] = request.credential
    return wire


def date_filter_to_wire(value: Optional[DateFilter]) -> Optional[str]:
    """Texto vai como está; `date` vai sem horário (dia inteiro); `datetime` sem fuso vai em `-03:00`."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat() if value.tzinfo is not None else f"{value.isoformat()}-03:00"
    return value.isoformat()


def add_webhook_delivery_filter(
    query: QueryStringBuilder, request: Union[ListWebhookDeliveriesRequest, WebhookDeliveryChartRequest]
) -> QueryStringBuilder:
    return (
        query.add("data_inicial", date_filter_to_wire(request.initial_date))
        .add("data_final", date_filter_to_wire(request.final_date))
        .add("id_proposta", request.proposal_id)
        .add("id_simulacao", request.simulation_id)
        .add("numero_proposta", request.proposal_number)
        .add("status_http", request.status_code)
    )


def webhook_delivery_to_public(wire: dict[str, Any]) -> WebhookDelivery:
    return WebhookDelivery(
        id=req_str(wire, "id_auditoria"),
        webhook_id=opt_str(wire, "id_webhook"),
        type=WebhookType.from_wire_name(wire.get("tipo")),
        request=opt_str(wire, "requisicao") or "",
        response=opt_str(wire, "resposta") or "",
        status_code=opt_int(wire, "status_http"),
        created_at=parse_iso_datetime(wire.get("data_criacao")),
    )


def webhook_delivery_chart_to_public(wire: Any) -> list[WebhookDeliveryChartPoint]:
    return [
        WebhookDeliveryChartPoint(
            label=req_str(item, "rotulo"),
            success_count=req_int(item, "sucessos"),
            error_count=req_int(item, "erros"),
        )
        for item in (as_dict(entry, "um ponto do gráfico de envios") for entry in as_list(wire, "o gráfico de envios"))
    ]


def webhook_resend_result_to_public(wire: Any) -> WebhookResendResult:
    root = as_dict(wire, "a resposta do reenvio do webhook")
    return WebhookResendResult(status_code=opt_int(root, "status_http"), response=opt_str(root, "resposta") or "")


def update_webhook_request_to_wire(request: UpdateWebhookRequest) -> dict[str, Any]:
    wire: dict[str, Any] = {"tipo": int(request.type), "url": request.url}
    if request.status is not None:
        wire["status"] = int(request.status)
    return wire
