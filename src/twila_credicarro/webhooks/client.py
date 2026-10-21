from typing import Optional

from .._internal.http.api_request_executor import ApiRequestExecutor
from .._internal.http.query_string import QueryStringBuilder
from .._internal.mapping.paged_mapper import paged_result_from_wire
from .._internal.mapping.webhook_mapper import (
    create_webhook_request_to_wire,
    create_webhook_result_to_public,
    update_webhook_request_to_wire,
    webhook_to_public,
)
from .._internal.path import Identifier, path_segment
from ..paged_result import ListRequest, PagedResult
from .types import CreateWebhookRequest, CreateWebhookResult, UpdateWebhookRequest, Webhook


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

    def list(self, request: Optional[ListRequest] = None) -> PagedResult[Webhook]:
        """Lista os webhooks do parceiro, paginados (`GET v1/webhook`)."""
        request = request or ListRequest()

        path = (
            QueryStringBuilder()
            .add("pagina_inicial", request.page)
            .add("limite", request.page_size)
            .build("v1/webhook")
        )
        response = self._executor.get(path)
        ApiRequestExecutor.ensure_success(response)

        return paged_result_from_wire(response.body, webhook_to_public)
