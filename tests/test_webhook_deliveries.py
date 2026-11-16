from datetime import date, datetime, timezone

import httpx
import pytest
import respx

from conftest import make_client
from twila_credicarro import (
    CredicarroApiError,
    ListWebhookDeliveriesRequest,
    WebhookResendResult,
    WebhookType,
)

AUDIT_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
WEBHOOK_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
PAGE = {"tem_proximo": False, "tem_anterior": False, "numero": 1, "tamanho": 10, "total": 2}


def test_list_deliveries_sends_filters_and_paging(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.get("v1/webhook/audit").mock(
        return_value=httpx.Response(
            200,
            json={
                "itens": [
                    {
                        "id_auditoria": AUDIT_ID,
                        "id_webhook": WEBHOOK_ID,
                        "tipo": "Proposal",
                        "requisicao": '{"id_proposta":"x"}',
                        "resposta": '{"recebido":true}',
                        "status_http": 200,
                        "data_criacao": "2026-11-05T14:32:10.123+00:00",
                    },
                    {
                        "id_auditoria": AUDIT_ID,
                        "id_webhook": None,
                        "tipo": "Algo",
                        "requisicao": "{}",
                        "resposta": "",
                        "status_http": None,
                        "data_criacao": "2026-11-05T14:33:00Z",
                    },
                ],
                "pagina": PAGE,
            },
        )
    )
    client = make_client()

    page = client.webhooks.list_deliveries(
        ListWebhookDeliveriesRequest(
            initial_date=date(2026, 11, 1),
            final_date=datetime(2026, 11, 5, 23, 59, 59),
            proposal_id=WEBHOOK_ID,
            proposal_number="12345",
            status_code=500,
            page=2,
            page_size=50,
        )
    )
    client.close()

    assert dict(route.calls.last.request.url.params) == {
        "data_inicial": "2026-11-01",
        "data_final": "2026-11-05T23:59:59-03:00",
        "id_proposta": WEBHOOK_ID,
        "numero_proposta": "12345",
        "status_http": "500",
        "pagina_inicial": "2",
        "limite": "50",
    }
    first, second = page.items
    assert first.id == AUDIT_ID
    assert first.webhook_id == WEBHOOK_ID
    assert first.type == WebhookType.PROPOSAL
    assert first.status_code == 200
    assert first.response == '{"recebido":true}'
    assert first.created_at == datetime(2026, 11, 5, 14, 32, 10, 123000, tzinfo=timezone.utc)
    assert (second.webhook_id, second.type, second.status_code, second.response) == (
        None,
        WebhookType.UNKNOWN,
        None,
        "",
    )
    assert '{"id_proposta"' not in repr(first)


def test_list_deliveries_without_filters_sends_default_paging(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.get("v1/webhook/audit").mock(
        return_value=httpx.Response(200, json={"itens": [], "pagina": PAGE})
    )
    client = make_client()

    client.webhooks.list_deliveries()
    client.close()

    assert dict(route.calls.last.request.url.params) == {"pagina_inicial": "1", "limite": "10"}


def test_list_deliveries_validates_paging() -> None:
    with pytest.raises(ValueError):
        ListWebhookDeliveriesRequest(page_size=101)


def test_resend_posts_without_body_or_idempotency_key(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post(f"v1/webhook/audit/{AUDIT_ID}/resend").mock(
        return_value=httpx.Response(200, json={"status_http": None, "resposta": ""})
    )
    client = make_client()

    result = client.webhooks.resend(AUDIT_ID)
    client.close()

    request = route.calls.last.request
    assert request.content == b""
    assert "Idempotency-Key" not in request.headers
    assert result == WebhookResendResult(response="", status_code=None)


def test_resend_is_not_retried_on_503(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post(f"v1/webhook/audit/{AUDIT_ID}/resend").mock(
        return_value=httpx.Response(
            503,
            json={"tipo": "Organization.Webhook.Resend.DependencyUnavailable", "titulo": "Indisponível", "status": 503},
        )
    )
    client = make_client()

    with pytest.raises(CredicarroApiError) as error:
        client.webhooks.resend(AUDIT_ID)
    client.close()

    assert route.call_count == 1
    assert error.value.error_code == "Organization.Webhook.Resend.DependencyUnavailable"


def test_resend_not_found(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.post(f"v1/webhook/audit/{AUDIT_ID}/resend").mock(
        return_value=httpx.Response(
            404, json={"tipo": "Webhook.Audit.NotFound", "titulo": "Não encontrado", "status": 404}
        )
    )
    client = make_client()

    with pytest.raises(CredicarroApiError) as error:
        client.webhooks.resend(AUDIT_ID)
    client.close()

    assert error.value.error_code == "Webhook.Audit.NotFound"
