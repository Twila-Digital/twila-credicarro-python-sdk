from typing import Any

import httpx
import pytest
import respx

from conftest import make_client
from twila_credicarro import (
    CredicarroApiError,
    CredicarroAuthenticationError,
    CredicarroBusinessRuleError,
    CredicarroError,
    CredicarroRateLimitError,
    CredicarroValidationError,
    ListRequest,
)

PROPOSAL_ID = "bea8d060-f93d-48eb-b6c4-45f64483cdd9"
PROPOSAL_PATH = f"v2/proposal/{PROPOSAL_ID}"


def _get_proposal(mock_router: respx.MockRouter, response: httpx.Response, **resilience: Any) -> None:
    mock_router.get(PROPOSAL_PATH).mock(return_value=response)
    client = make_client(**resilience)
    try:
        client.proposals.get(PROPOSAL_ID)
    finally:
        client.close()


def test_422_maps_to_business_rule_error(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    body = {
        "tipo": "Store.Integration.Intermediation",
        "titulo": "Regra de negócio não atendida",
        "status": 422,
        "detalhe": "A loja possui contrato de intermediação e não é elegível para a integração.",
    }

    with pytest.raises(CredicarroBusinessRuleError) as error:
        _get_proposal(mock_router, httpx.Response(422, json=body))

    assert isinstance(error.value, CredicarroApiError)
    assert error.value.status_code == 422
    assert error.value.error_code == "Store.Integration.Intermediation"
    assert error.value.title == "Regra de negócio não atendida"
    assert error.value.detail == body["detalhe"]
    assert error.value.field is None


def test_message_has_status_code_and_title_but_not_the_detail_or_body(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    body = {
        "tipo": "Validation.Cpf.Invalid",
        "titulo": "Requisição inválida",
        "status": 400,
        "detalhe": "O CPF 123.456.789-09 informado é inválido.",
        "campo": "cpf",
    }

    with pytest.raises(CredicarroValidationError) as error:
        _get_proposal(mock_router, httpx.Response(400, json=body))

    message = str(error.value)
    assert "400" in message
    assert "Validation.Cpf.Invalid" in message
    assert "Requisição inválida" in message
    assert "123.456.789-09" not in message
    assert error.value.detail is not None and "123.456.789-09" in error.value.detail
    assert error.value.raw_body is not None and "123.456.789-09" in error.value.raw_body
    assert error.value.field == "cpf"


def test_400_exposes_the_errors_list(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    body = {
        "tipo": "Validation.InvalidFormat",
        "titulo": "Requisição inválida",
        "status": 400,
        "erros": [
            {
                "codigo": "Validation.InvalidFormat",
                "mensagem": "O valor de 'valorVeiculo' não é um número.",
                "campo": "valorVeiculo",
            },
            {"codigo": "Validation.Field.Required", "mensagem": "Campo obrigatório.", "campo": None},
        ],
    }

    with pytest.raises(CredicarroValidationError) as error:
        _get_proposal(mock_router, httpx.Response(400, json=body))

    assert error.value.status_code == 400
    assert [(item.code, item.field) for item in error.value.errors] == [
        ("Validation.InvalidFormat", "valorVeiculo"),
        ("Validation.Field.Required", None),
    ]
    assert error.value.errors[0].message == "O valor de 'valorVeiculo' não é um número."


def test_standard_problem_details_fields_are_used_as_fallback(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    body = {
        "type": "https://tools.ietf.org/html/rfc9110#section-15.6.1",
        "title": "An error occurred",
        "status": 500,
        "detail": "Falha inesperada",
    }

    with pytest.raises(CredicarroApiError) as error:
        _get_proposal(mock_router, httpx.Response(500, json=body), retry_on_500=False)

    assert type(error.value) is CredicarroApiError
    assert error.value.status_code == 500
    assert error.value.error_code == "https://tools.ietf.org/html/rfc9110#section-15.6.1"
    assert error.value.title == "An error occurred"
    assert error.value.detail == "Falha inesperada"


def test_401_without_body_raises_authentication_error(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    with pytest.raises(CredicarroAuthenticationError) as error:
        _get_proposal(mock_router, httpx.Response(401))

    assert error.value.status_code == 401
    assert "Não autorizado" in str(error.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="Internal Server Error"),
        httpx.Response(502, content=b"<html>bad gateway</html>"),
        httpx.Response(404),
    ],
)
def test_non_json_or_empty_bodies_still_raise_api_error(
    mock_router: respx.MockRouter, token_route: respx.Route, response: httpx.Response
) -> None:
    with pytest.raises(CredicarroApiError) as error:
        _get_proposal(mock_router, response, retry_on_500=False, max_retry_attempts=1)

    assert error.value.status_code == response.status_code
    assert error.value.error_code is None
    assert str(response.status_code) in str(error.value)


def test_404_with_problem_details(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    body = {"tipo": "Proposal.Access.NotFound", "titulo": "Não encontrado", "status": 404}

    with pytest.raises(CredicarroApiError) as error:
        _get_proposal(mock_router, httpx.Response(404, json=body))

    assert error.value.error_code == "Proposal.Access.NotFound"
    assert not isinstance(error.value, (CredicarroValidationError, CredicarroBusinessRuleError))


def test_429_exposes_retry_after_and_is_not_retried_when_exhausted(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.get(PROPOSAL_PATH).mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, json={"tipo": "RateLimit"})
    )
    client = make_client(max_retry_attempts=2)

    with pytest.raises(CredicarroRateLimitError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert error.value.status_code == 429
    assert error.value.retry_after_ms is None
    assert route.call_count == 2


def test_other_4xx_are_never_retried(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.get(PROPOSAL_PATH).mock(return_value=httpx.Response(409, json={"tipo": "X"}))
    client = make_client()

    with pytest.raises(CredicarroApiError):
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert route.call_count == 1


def test_all_sdk_errors_share_the_base_class() -> None:
    for error_type in (
        CredicarroApiError,
        CredicarroAuthenticationError,
        CredicarroBusinessRuleError,
        CredicarroRateLimitError,
        CredicarroValidationError,
    ):
        assert issubclass(error_type, CredicarroError)


@pytest.mark.parametrize("page,size", [(0, 10), (1, 0), (1, 101), (-1, 10)])
def test_list_request_validates_bounds(page: int, size: int) -> None:
    with pytest.raises(ValueError):
        ListRequest(page=page, page_size=size)


def test_list_request_accepts_the_limits() -> None:
    assert ListRequest(page=1, page_size=1).page_size == 1
    assert ListRequest(page=7, page_size=100).page_size == 100
