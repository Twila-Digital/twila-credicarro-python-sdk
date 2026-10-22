import json

import httpx
import pytest
import respx

from conftest import make_client
from twila_credicarro import (
    CreateWebhookRequest,
    CredicarroApiError,
    CredicarroBusinessRuleError,
    ListRequest,
    UpdateWebhookRequest,
    WebhookAuthenticationType,
    WebhookStatus,
    WebhookType,
)

WEBHOOK_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


def test_create_returns_id_and_signing_secret(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post("v1/webhook").mock(
        return_value=httpx.Response(201, json={"id_webhook": WEBHOOK_ID, "segredo_assinatura": "segredo-de-exemplo"})
    )
    client = make_client()

    result = client.webhooks.create(
        CreateWebhookRequest(
            type=WebhookType.PROPOSAL,
            url="https://parceiro.com.br/webhooks/credicarro",
            authentication_type=WebhookAuthenticationType.BASIC,
            credential="dXN1YXJpbzpzZW5oYQ==",
        )
    )
    client.close()

    assert result.webhook_id == WEBHOOK_ID
    assert result.signing_secret == "segredo-de-exemplo"
    assert "segredo-de-exemplo" not in repr(result)
    assert json.loads(route.calls.last.request.content) == {
        "tipo": 3,
        "url": "https://parceiro.com.br/webhooks/credicarro",
        "tipo_autenticacao": 2,
        "credencial": "dXN1YXJpbzpzZW5oYQ==",
    }


def test_create_without_credential_omits_the_field_and_hides_it_from_repr(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post("v1/webhook").mock(
        return_value=httpx.Response(201, json={"id_webhook": WEBHOOK_ID, "segredo_assinatura": "s"})
    )
    client = make_client()

    client.webhooks.create(
        CreateWebhookRequest(
            type=WebhookType.CUSTOMER,
            url="https://parceiro.com.br/hook",
            authentication_type=WebhookAuthenticationType.NONE,
        )
    )
    client.close()

    assert "credencial" not in json.loads(route.calls.last.request.content)
    assert "credential" not in repr(
        CreateWebhookRequest(
            type=WebhookType.CUSTOMER,
            url="https://x.com",
            authentication_type=WebhookAuthenticationType.JWT,
            credential="token-secreto",
        )
    )


def test_invalid_endpoint_is_a_business_rule_error(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.post("v1/webhook").mock(
        return_value=httpx.Response(
            422, json={"tipo": "Organization.Webhook.InvalidEndpoint", "titulo": "Regra de negócio", "status": 422}
        )
    )
    client = make_client()

    with pytest.raises(CredicarroBusinessRuleError) as error:
        client.webhooks.create(
            CreateWebhookRequest(
                type=WebhookType.PROPOSAL,
                url="https://localhost/x",
                authentication_type=WebhookAuthenticationType.NONE,
            )
        )
    client.close()

    assert error.value.error_code == "Organization.Webhook.InvalidEndpoint"


def test_list_maps_enums_from_text(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.get("v1/webhook").mock(
        return_value=httpx.Response(
            200,
            json={
                "itens": [
                    {
                        "id_webhook": WEBHOOK_ID,
                        "tipo": "Proposal",
                        "url": "https://parceiro.com.br/webhooks/credicarro",
                        "tipo_autenticacao": "Basic",
                        "status": "Active",
                    },
                    {
                        "id_webhook": "x",
                        "tipo": "Novo",
                        "url": "https://a.com",
                        "tipo_autenticacao": "Oauth",
                        "status": "Paused",
                    },
                ],
                "pagina": {"tem_proximo": False, "tem_anterior": False, "numero": 1, "tamanho": 10, "total": 2},
            },
        )
    )
    client = make_client()

    page = client.webhooks.list(ListRequest(page=1, page_size=10))
    client.close()

    first, second = page.items
    assert (first.id, first.type, first.authentication_type, first.status) == (
        WEBHOOK_ID,
        WebhookType.PROPOSAL,
        WebhookAuthenticationType.BASIC,
        WebhookStatus.ACTIVE,
    )
    assert (second.type, second.authentication_type, second.status) == (
        WebhookType.UNKNOWN,
        WebhookAuthenticationType.UNKNOWN,
        WebhookStatus.UNKNOWN,
    )
    assert route.calls.last.request.url.params["limite"] == "10"
    assert page.total_count == 2


def test_update_sends_status_only_when_given(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.put(f"v1/webhook/{WEBHOOK_ID}").mock(return_value=httpx.Response(204))
    client = make_client()

    client.webhooks.update(WEBHOOK_ID, UpdateWebhookRequest(type=WebhookType.PROPOSAL, url="https://a.com/h"))
    client.webhooks.update(
        WEBHOOK_ID,
        UpdateWebhookRequest(type=WebhookType.SIMULATION, url="https://a.com/h", status=WebhookStatus.INACTIVE),
    )
    client.close()

    assert json.loads(route.calls[0].request.content) == {"tipo": 3, "url": "https://a.com/h"}
    assert json.loads(route.calls[1].request.content) == {"tipo": 2, "url": "https://a.com/h", "status": 2}
    assert "idempotency-key" not in route.calls[0].request.headers


def test_update_and_delete_are_retry_safe(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    put_responses = iter([httpx.Response(503), httpx.Response(204)])
    delete_responses = iter([httpx.Response(502), httpx.Response(204)])
    put_route = mock_router.put(f"v1/webhook/{WEBHOOK_ID}").mock(side_effect=lambda request: next(put_responses))
    delete_route = mock_router.delete(f"v1/webhook/{WEBHOOK_ID}").mock(
        side_effect=lambda request: next(delete_responses)
    )
    client = make_client()

    client.webhooks.update(WEBHOOK_ID, UpdateWebhookRequest(type=WebhookType.PROPOSAL, url="https://a.com/h"))
    client.webhooks.delete(WEBHOOK_ID)
    client.close()

    assert put_route.call_count == 2
    assert delete_route.call_count == 2


def test_delete_not_found(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.delete(f"v1/webhook/{WEBHOOK_ID}").mock(
        return_value=httpx.Response(404, json={"tipo": "Webhook.Registration.NotFound", "status": 404})
    )
    client = make_client()

    with pytest.raises(CredicarroApiError) as error:
        client.webhooks.delete(WEBHOOK_ID)
    client.close()

    assert error.value.error_code == "Webhook.Registration.NotFound"
