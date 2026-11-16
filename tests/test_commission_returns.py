import json

import httpx
import pytest
import respx

from conftest import make_client
from test_simulations_client import OPTION
from twila_credicarro import (
    CommissionReturn,
    CommissionReturnTarget,
    CreateFinancingSimulationRequest,
    CreateFinancingSimulationV1Request,
    CreateRefinancingSimulationRequest,
    CredicarroBusinessRuleError,
    SimulationType,
)


def test_get_commission_returns_sends_store_and_maps_ranges(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.get("v2/proposal/simulation/commission-returns").mock(
        return_value=httpx.Response(
            200,
            json={
                "retornos_comissao": [
                    {
                        "tipo": "Financing",
                        "alvo": "Store",
                        "retorno_minimo": 0,
                        "retorno_maximo": 4,
                        "permite_taxa_padrao": True,
                    },
                    {
                        "tipo": "Refinancing",
                        "alvo": "Organization",
                        "retorno_minimo": 1,
                        "retorno_maximo": 3,
                        "permite_taxa_padrao": False,
                    },
                    {
                        "tipo": "Outro",
                        "alvo": "Novo",
                        "retorno_minimo": 0,
                        "retorno_maximo": 0,
                        "permite_taxa_padrao": False,
                    },
                ]
            },
        )
    )
    client = make_client()

    returns = client.simulations.get_commission_returns("11.222.333/0001-81")
    client.close()

    assert route.calls.last.request.url.params["cnpjLoja"] == "11.222.333/0001-81"
    assert returns == [
        CommissionReturn(SimulationType.FINANCING, CommissionReturnTarget.STORE, 0, 4, True),
        CommissionReturn(SimulationType.REFINANCING, CommissionReturnTarget.ORGANIZATION, 1, 3, False),
        CommissionReturn(SimulationType.UNKNOWN, CommissionReturnTarget.UNKNOWN, 0, 0, False),
    ]


def test_get_commission_returns_empty(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.get("v2/proposal/simulation/commission-returns").mock(
        return_value=httpx.Response(200, json={"retornos_comissao": []})
    )
    client = make_client()

    assert client.simulations.get_commission_returns("11222333000181") == []
    client.close()


def test_simulations_send_commission_return_only_when_provided(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    financing = mock_router.post("v2/proposal/simulation/financing").mock(
        return_value=httpx.Response(201, json={"simulacoes": [OPTION]})
    )
    refinancing = mock_router.post("v2/proposal/simulation/refinancing").mock(
        return_value=httpx.Response(201, json={"simulacoes": [OPTION]})
    )
    client = make_client()

    client.simulations.create_financing(
        CreateFinancingSimulationRequest("12345678909", "ABC1D23", 45000, 5000, "SP", False, "11222333000181", 2)
    )
    client.simulations.create_refinancing(
        CreateRefinancingSimulationRequest("12345678909", "ABC1D23", 25000, "11222333000181", commission_return=0)
    )
    client.simulations.create_refinancing(
        CreateRefinancingSimulationRequest("12345678909", "ABC1D23", 25000, "11222333000181")
    )
    client.close()

    assert json.loads(financing.calls.last.request.content)["retornoComissao"] == 2
    assert json.loads(refinancing.calls[0].request.content)["retornoComissao"] == 0
    assert "retornoComissao" not in json.loads(refinancing.calls[1].request.content)


def test_v1_request_has_no_commission_return() -> None:
    with pytest.raises(TypeError):
        CreateFinancingSimulationV1Request(  # type: ignore[call-arg]
            "12345678909", "ABC1D23", 45000, 5000, "SP", False, commission_return=2
        )


def test_commission_return_out_of_range_is_a_business_rule_error(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    mock_router.post("v2/proposal/simulation/financing").mock(
        return_value=httpx.Response(
            422,
            json={
                "tipo": "Store.CommissionReturn.OutOfRange",
                "titulo": "Regra de negócio não atendida",
                "status": 422,
                "detalhe": "O valor deve estar entre 0 e 4.",
            },
        )
    )
    client = make_client()

    with pytest.raises(CredicarroBusinessRuleError) as error:
        client.simulations.create_financing(
            CreateFinancingSimulationRequest("12345678909", "ABC1D23", 45000, 5000, "SP", False, "11222333000181", 9)
        )
    client.close()

    assert error.value.error_code == "Store.CommissionReturn.OutOfRange"
