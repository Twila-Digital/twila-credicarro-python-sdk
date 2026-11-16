from typing import Optional

from .._internal.http.api_request_executor import ApiRequestExecutor
from .._internal.http.query_string import QueryStringBuilder, paged_path
from .._internal.mapping.paged_mapper import paged_result_from_wire
from .._internal.mapping.webhook_mapper import (
    add_webhook_delivery_filter,
    create_webhook_request_to_wire,
    create_webhook_result_to_public,
    update_webhook_request_to_wire,
    webhook_delivery_chart_to_public,
    webhook_delivery_to_public,
    webhook_resend_result_to_public,
    webhook_to_public,
)
from .._internal.path import Identifier, path_segment
from ..paged_result import ListRequest, PagedResult
from .types import (
    CreateWebhookRequest,
    CreateWebhookResult,
    ListWebhookDeliveriesRequest,
    UpdateWebhookRequest,
    Webhook,
    WebhookDelivery,
    WebhookDeliveryChartPoint,
    WebhookDeliveryChartRequest,
    WebhookResendResult,
)

_RESEND_ATTEMPT_TIMEOUT_MS = 30_000
"""O reenvio espera a resposta da URL do integrador (até 15 s do lado da Credicarro)."""


class WebhooksClient:
    def __init__(self, executor: ApiRequestExecutor) -> None:
        self._executor = executor

    def create(self, request: CreateWebhookRequest) -> CreateWebhookResult:
        """Cadastra um webhook (`POST v1/webhook`). O `signing_secret` só vem aqui: guarde-o.

        Sem `Idempotency-Key` e sem repetição automática: se a chamada falhar por rede, liste os webhooks antes de
        cadastrar de novo.
        """
        response = self._executor.post("v1/webhook", create_webhook_request_to_wire(request))
        ApiRequestExecutor.ensure_success(response)

        return create_webhook_result_to_public(response.body)

    def update(self, webhook_id: Identifier, request: UpdateWebhookRequest) -> None:
        """Atualiza tipo, URL e status (`PUT v1/webhook/{id}`, `204`). A autenticação não pode ser alterada."""
        response = self._executor.put(f"v1/webhook/{path_segment(webhook_id)}", update_webhook_request_to_wire(request))
        ApiRequestExecutor.ensure_success(response)

    def delete(self, webhook_id: Identifier) -> None:
        """Exclui o webhook (`DELETE v1/webhook/{id}`, `204`)."""
        response = self._executor.delete(f"v1/webhook/{path_segment(webhook_id)}")
        ApiRequestExecutor.ensure_success(response)

    def list_deliveries(
        self, request: Optional[ListWebhookDeliveriesRequest] = None
    ) -> PagedResult[WebhookDelivery]:
        """Histórico de envios, com o corpo enviado, a resposta da sua URL e o status HTTP (`GET v1/webhook/audit`)."""
        request = request or ListWebhookDeliveriesRequest()

        path = (
            add_webhook_delivery_filter(QueryStringBuilder(), request)
            .add("pagina_inicial", request.page)
            .add("limite", request.page_size)
            .build("v1/webhook/audit")
        )
        response = self._executor.get(path)
        ApiRequestExecutor.ensure_success(response)

        return paged_result_from_wire(response.body, webhook_delivery_to_public)

    def get_delivery_chart(self, request: WebhookDeliveryChartRequest) -> list[WebhookDeliveryChartPoint]:
        """Sucessos e erros por intervalo, no horário de Brasília (`GET v1/webhook/audit/chart`).

        O período é obrigatório e pode ter até 31 dias.
        """
        if request.initial_date is None or request.final_date is None:
            raise ValueError("initial_date e final_date são obrigatórios no gráfico de envios.")

        path = add_webhook_delivery_filter(QueryStringBuilder(), request).build("v1/webhook/audit/chart")
        response = self._executor.get(path)
        ApiRequestExecutor.ensure_success(response)

        return webhook_delivery_chart_to_public(response.body)

    def resend(self, delivery_id: Identifier) -> WebhookResendResult:
        """Reenvia um envio do histórico (`POST v1/webhook/audit/{id}/resend`).

        Uma única tentativa, sem repetição automática (repetir dispararia o webhook de novo). O reenvio chega à sua
        URL com uma `Idempotency-Key` nova (`{id_mensagem}:{id_webhook}:{id_tentativa}`).
        """
        response = self._executor.post(
            f"v1/webhook/audit/{path_segment(delivery_id)}/resend",
            None,
            attempt_timeout_ms=_RESEND_ATTEMPT_TIMEOUT_MS,
        )
        ApiRequestExecutor.ensure_success(response)

        return webhook_resend_result_to_public(response.body)

    def list(self, request: Optional[ListRequest] = None) -> PagedResult[Webhook]:
        """Lista os webhooks do parceiro, paginados (`GET v1/webhook`)."""
        request = request or ListRequest()

        path = paged_path("v1/webhook", request.page, request.page_size)
        response = self._executor.get(path)
        ApiRequestExecutor.ensure_success(response)

        return paged_result_from_wire(response.body, webhook_to_public)
