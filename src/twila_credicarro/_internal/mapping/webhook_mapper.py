from typing import Any

from ...webhooks.types import (
    CreateWebhookRequest,
    CreateWebhookResult,
    UpdateWebhookRequest,
    Webhook,
    WebhookAuthenticationType,
    WebhookStatus,
    WebhookType,
)
from .wire import as_dict, req_str


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


def update_webhook_request_to_wire(request: UpdateWebhookRequest) -> dict[str, Any]:
    wire: dict[str, Any] = {"tipo": int(request.type), "url": request.url}
    if request.status is not None:
        wire["status"] = int(request.status)
    return wire
