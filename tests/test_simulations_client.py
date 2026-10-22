import json
from typing import Any

import httpx
import pytest
import respx

from conftest import make_client
from twila_credicarro import (
    CreateFinancingSimulationRequest,
    CreateRefinancingSimulationRequest,
    CredicarroBusinessRuleError,
    CredicarroError,
    ListRequest,
    SimulationType,
)

SIMULATION_ID = "bea8d060-f93d-48eb-b6c4-45f64483cdd9"
OPTION = {
    "id_simulacao": SIMULATION_ID,
    "valor_solicitado": 40000,
    "prazo": 36,
    "valor_parcela": 2042.42,
    "valor_tac": 1500,
    "valor_boleto": 3.5,
    "valor_seguro": 0,
    "valor_iof": 872,
    "percentual_iof": 1.92,
    "valor_credito_total": 42722,
    "valor_divida_total": 73527.12,
    "percentual_cet_mensal": 3.62,
    "percentual_cet_anual": 53.25,
    "percentual_juros_mensal": 3.29,
    "percentual_juros_anual": 47.53,
}


def test_get_financing_range_sends_plate_and_store(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.get("v2/proposal/simulation/range/financing").mock(
        return_value=httpx.Response(
            200,
            json={
                "opcoes_por_prazo": [
                    {"prazo": 12, "valor_minimo_entrada": 5000.0},
                    {"prazo": 24, "valor_minimo_entrada": 4000},
                ]
            },
        )
    )
    client = make_client()

    options = client.simulations.get_financing_range("ABC1D23", "11.222.333/0001-81")
    client.close()

    assert [(item.term, item.minimum_down_payment) for item in options] == [(12, 5000.0), (24, 4000.0)]
    params = route.calls.last.request.url.params
    assert params["placa"] == "ABC1D23"
    assert params["cnpjLoja"] == "11.222.333/0001-81"


def test_get_refinancing_range(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.get("v2/proposal/simulation/range/refinancing").mock(
        return_value=httpx.Response(
            200,
            json={
                "opcoes_por_prazo": [
                    {"prazo": 6, "valor_minimo_refinanciavel": 12480, "valor_maximo_refinanciavel": 35720}
                ]
            },
        )
    )
    client = make_client()

    options = client.simulations.get_refinancing_range("ABC1D23", "11222333000181")
    client.close()

    assert (options[0].term, options[0].minimum_amount, options[0].maximum_amount) == (6, 12480.0, 35720.0)
    assert route.calls.last.request.url.params["cnpjLoja"] == "11222333000181"


def test_create_financing_maps_request_and_options(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post("v2/proposal/simulation/financing").mock(
        return_value=httpx.Response(
            201, json={"simulacoes": [OPTION, {**OPTION, "prazo": 48, "valor_retencao_diaria_aproximado": 12.5}]}
        )
    )
    client = make_client()

    options = client.simulations.create_financing(
        CreateFinancingSimulationRequest(
            cpf="12345678909",
            license_plate="ABC1D23",
            vehicle_amount=45000,
            down_payment=5000,
            state="SP",
            is_zero_km=False,
            store_cnpj="11.222.333/0001-81",
        )
    )
    client.close()

    assert json.loads(route.calls.last.request.content) == {
        "cpf": "12345678909",
        "placa": "ABC1D23",
        "valorVeiculo": 45000,
        "valorEntrada": 5000,
        "uf": "SP",
        "isVeiculoZeroKm": False,
        "cnpjLoja": "11.222.333/0001-81",
    }
    first, second = options
    assert first.simulation_id == SIMULATION_ID
    assert (first.term, first.installment_amount, first.tac_amount) == (36, 2042.42, 1500.0)
    assert (first.boleto_amount, first.insurance_amount, first.iof_amount, first.iof_rate) == (3.5, 0.0, 872.0, 1.92)
    assert (first.total_credit_amount, first.total_debt_amount) == (42722.0, 73527.12)
    assert (first.monthly_cet, first.annual_cet) == (3.62, 53.25)
    assert (first.monthly_interest_rate, first.annual_interest_rate) == (3.29, 47.53)
    assert first.approximate_daily_retention is None
    assert second.term == 48
    assert second.approximate_daily_retention == 12.5


def test_create_refinancing(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post("v2/proposal/simulation/refinancing").mock(
        return_value=httpx.Response(201, json={"simulacoes": [OPTION]})
    )
    client = make_client()

    options = client.simulations.create_refinancing(
        CreateRefinancingSimulationRequest(
            cpf="12345678909", license_plate="ABC1D23", requested_amount=25000, store_cnpj="11222333000181"
        )
    )
    client.close()

    assert len(options) == 1
    assert json.loads(route.calls.last.request.content) == {
        "cpf": "12345678909",
        "placa": "ABC1D23",
        "valorSolicitado": 25000,
        "cnpjLoja": "11222333000181",
    }


def test_business_rule_error_on_simulation(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.post("v2/proposal/simulation/refinancing").mock(
        return_value=httpx.Response(
            422, json={"tipo": "Simulation.Refinancing.AmountOutOfRange", "titulo": "Regra de negócio", "status": 422}
        )
    )
    client = make_client()

    with pytest.raises(CredicarroBusinessRuleError) as error:
        client.simulations.create_refinancing(
            CreateRefinancingSimulationRequest(
                cpf="12345678909", license_plate="ABC1D23", requested_amount=1, store_cnpj="11222333000181"
            )
        )
    client.close()

    assert error.value.error_code == "Simulation.Refinancing.AmountOutOfRange"


def test_get_simulation_maps_nested_objects(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    body: dict[str, Any] = {
        "id_simulacao": SIMULATION_ID,
        "prazo": 24,
        "valor_parcela": 2356,
        "valor_solicitado": 37908,
        "valor_entrada": 9786,
        "valor_bem": 47694,
        "valor_tac": 1500,
        "taxa_juros_negociada": 2.79,
        "valor_registro": 487,
        "uf": "SP",
        "tipo": "Refinancing",
        "transacao": {"valor_total_credito": 78495, "valor_total_debito": 78000},
        "juros": {"percentual_juros_mensal": 3.29, "percentual_juros_anual": 39.48},
        "cet": {"percentual_mensal": 3.62, "percentual_anual": 43.44},
        "iof": {"valor": 872, "percentual": 1.92},
        "veiculo": {
            "marca": "Honda",
            "modelo": "Civic",
            "versao": "Turing",
            "ano": 2024,
            "valor": 124654,
            "placa": "MWO-3910",
            "veiculo_zero_km": False,
            "chassi": "1Y5Ye4U8kydsr4828",
            "renavam": "70502561697",
            "cor": "Prata",
        },
        "cliente": {"cpf": "123.456.789-01"},
        "data_criacao": "2025-10-17T19:05:08.9840000Z",
    }
    mock_router.get(f"v1/proposal/simulation/{SIMULATION_ID}").mock(return_value=httpx.Response(200, json=body))
    client = make_client()

    simulation = client.simulations.get(SIMULATION_ID)
    client.close()

    assert simulation.simulation_id == SIMULATION_ID
    assert simulation.type is SimulationType.REFINANCING
    assert (simulation.down_payment, simulation.asset_amount, simulation.registration_amount) == (
        9786.0,
        47694.0,
        487.0,
    )
    assert simulation.negotiated_interest_rate == 2.79
    assert simulation.state == "SP"
    assert simulation.transaction is not None
    assert (simulation.transaction.total_credit, simulation.transaction.total_debit) == (78495.0, 78000.0)
    assert simulation.interest is not None and simulation.interest.annual_rate == 39.48
    assert simulation.cet is not None and (simulation.cet.monthly_rate, simulation.cet.annual_rate) == (3.62, 43.44)
    assert simulation.iof is not None and (simulation.iof.amount, simulation.iof.rate) == (872.0, 1.92)
    assert simulation.vehicle is not None
    assert (simulation.vehicle.brand, simulation.vehicle.year, simulation.vehicle.is_zero_km) == ("Honda", 2024, False)
    assert simulation.customer_cpf == "123.456.789-01"
    assert simulation.created_at is not None and simulation.created_at.year == 2025


def test_unknown_simulation_type_falls_back_to_unknown(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.get(f"v1/proposal/simulation/{SIMULATION_ID}").mock(
        return_value=httpx.Response(200, json={"id_simulacao": SIMULATION_ID, "tipo": "Leasing"})
    )
    client = make_client()

    simulation = client.simulations.get(SIMULATION_ID)
    client.close()

    assert simulation.type is SimulationType.UNKNOWN
    assert simulation.type_name == "Leasing"


def test_list_simulations_is_paged(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.get("v1/proposal/simulation").mock(
        return_value=httpx.Response(
            200,
            json={
                "itens": [{"id_simulacao": SIMULATION_ID, "prazo": 12}],
                "pagina": {"tem_proximo": True, "tem_anterior": False, "numero": 1, "tamanho": 20, "total": 45},
            },
        )
    )
    client = make_client()

    page = client.simulations.list(ListRequest(page=1, page_size=20))
    default_page = client.simulations.list()
    client.close()

    params = route.calls[0].request.url.params
    assert (params["pagina_inicial"], params["limite"]) == ("1", "20")
    assert (default_page.page_size, default_page.total_count) == (20, 45)
    assert default_page is not page
    assert page.has_next is True and page.has_previous is False
    assert (page.page, page.page_size, page.total_count) == (1, 20, 45)
    assert page.items[0].simulation_id == SIMULATION_ID
    default_params = route.calls[1].request.url.params
    assert (default_params["pagina_inicial"], default_params["limite"]) == ("1", "10")


def test_missing_required_field_raises_credicarro_error(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    mock_router.post("v2/proposal/simulation/financing").mock(
        return_value=httpx.Response(201, json={"simulacoes": [{"id_simulacao": SIMULATION_ID}]})
    )
    client = make_client()

    with pytest.raises(CredicarroError) as error:
        client.simulations.create_financing(
            CreateFinancingSimulationRequest(
                cpf="12345678909",
                license_plate="ABC1D23",
                vehicle_amount=1,
                down_payment=0,
                state="SP",
                is_zero_km=True,
                store_cnpj="11222333000181",
            )
        )
    client.close()

    assert "valor_solicitado" in str(error.value)
