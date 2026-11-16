import json
from typing import Any

import httpx
import pytest
import respx

from conftest import make_client
from twila_credicarro import (
    CreateFinancingSimulationV1Request,
    CreateFinancingWithoutCpfRequest,
    CreateProposalRequest,
    CreateRefinancingSimulationV1Request,
    CreateRefinancingWithoutCpfRequest,
    CredicarroApiError,
    ProposalStatus,
    ProposalType,
)

PROPOSAL_ID = "bea8d060-f93d-48eb-b6c4-45f64483cdd9"
SIMULATION_ID = "123e4567-e89b-12d3-a456-426614174000"
OPTION: dict[str, Any] = {
    "id_simulacao": SIMULATION_ID,
    "valor_solicitado": 1,
    "prazo": 12,
    "valor_parcela": 1,
    "valor_tac": 1,
    "valor_boleto": 1,
    "valor_seguro": 1,
    "valor_iof": 1,
    "percentual_iof": 1,
    "valor_credito_total": 1,
    "valor_divida_total": 1,
    "percentual_cet_mensal": 1,
    "percentual_cet_anual": 1,
    "percentual_juros_mensal": 1,
    "percentual_juros_anual": 1,
}


def test_v1_ranges_do_not_send_the_store(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    financing = mock_router.get("v1/proposal/simulation/range/financing").mock(
        return_value=httpx.Response(200, json={"opcoes_por_prazo": [{"prazo": 12, "valor_minimo_entrada": 5000}]})
    )
    refinancing = mock_router.get("v1/proposal/simulation/range/refinancing").mock(
        return_value=httpx.Response(
            200,
            json={"opcoes_por_prazo": [{"prazo": 6, "valor_minimo_refinanciavel": 1, "valor_maximo_refinanciavel": 2}]},
        )
    )
    client = make_client()

    fin = client.v1.simulations.get_financing_range("ABC-1234")
    refin = client.v1.simulations.get_refinancing_range("ABC1D23")
    client.close()

    assert (fin[0].term, fin[0].minimum_down_payment) == (12, 5000.0)
    assert (refin[0].minimum_amount, refin[0].maximum_amount) == (1.0, 2.0)
    assert dict(financing.calls.last.request.url.params) == {"placa": "ABC-1234"}
    assert dict(refinancing.calls.last.request.url.params) == {"placa": "ABC1D23"}


def test_v1_create_simulations_without_store(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    financing = mock_router.post("v1/proposal/simulation/financing").mock(
        return_value=httpx.Response(201, json={"simulacoes": [OPTION]})
    )
    refinancing = mock_router.post("v1/proposal/simulation/refinancing").mock(
        return_value=httpx.Response(201, json={"simulacoes": [OPTION, OPTION]})
    )
    client = make_client()

    fin = client.v1.simulations.create_financing(
        CreateFinancingSimulationV1Request(
            cpf="12345678909",
            license_plate="ABC1D23",
            vehicle_amount=45000,
            down_payment=5000,
            state="SP",
            is_zero_km=True,
        )
    )
    refin = client.v1.simulations.create_refinancing(
        CreateRefinancingSimulationV1Request(cpf="12345678909", license_plate="ABC1D23", requested_amount=25000)
    )
    client.close()

    assert (len(fin), len(refin)) == (1, 2)
    assert json.loads(financing.calls.last.request.content) == {
        "cpf": "12345678909",
        "placa": "ABC1D23",
        "valorVeiculo": 45000,
        "valorEntrada": 5000,
        "uf": "SP",
        "isVeiculoZeroKm": True,
    }
    assert json.loads(refinancing.calls.last.request.content) == {
        "cpf": "12345678909",
        "placa": "ABC1D23",
        "valorSolicitado": 25000,
    }
    assert financing.calls.last.request.headers["idempotency-key"]
    assert refinancing.calls.last.request.headers["idempotency-key"]


def test_v1_proposals_create_and_get(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    create = mock_router.post("v1/proposal").mock(return_value=httpx.Response(201, json={"id_proposta": PROPOSAL_ID}))
    get = mock_router.get(f"v1/proposal/{PROPOSAL_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id_proposta": PROPOSAL_ID,
                "numero": 171020250001,
                "id_simulacao": SIMULATION_ID,
                "tipo": "Financing",
                "status": "Approved",
                "comprador": {"cpf": "123.456.789-01"},
                "data_criacao": "2025-10-17T19:05:08.984Z",
            },
        )
    )
    client = make_client()

    proposal_id = client.v1.proposals.create(CreateProposalRequest(cpf="12345678909", simulation_id=SIMULATION_ID))
    summary = client.v1.proposals.get(PROPOSAL_ID)
    client.close()

    assert proposal_id == PROPOSAL_ID
    assert json.loads(create.calls.last.request.content) == {"cpf": "12345678909", "simulacaoId": SIMULATION_ID}
    assert get.call_count == 1
    assert summary.id == PROPOSAL_ID
    assert summary.number == 171020250001
    assert summary.type is ProposalType.FINANCING
    assert summary.status is ProposalStatus.APPROVED
    assert summary.status_name == "Approved"
    assert summary.buyer_cpf == "123.456.789-01"
    assert summary.seller_cpf is None
    assert summary.created_at is not None


WITHOUT_CPF_PATH = "v1/proposal/simulation/financing/without-cpf"
WITHOUT_CPF_OPTION: dict[str, Any] = {
    "valor_solicitado": 40000,
    "prazo": 24,
    "valor_parcela": 2100.5,
    "valor_tac": 1,
    "valor_boleto": 2,
    "valor_seguro": 3,
    "valor_iof": 4,
    "percentual_iof": 0.38,
    "valor_credito_total": 41000,
    "valor_divida_total": 50400,
    "percentual_cet_mensal": 2.9,
    "percentual_cet_anual": 41.2,
    "percentual_juros_mensal": 2.5,
    "percentual_juros_anual": 34.5,
    "valor_retencao_diaria_aproximado": 12.5,
    "valor_entrada_minima": 5000,
}


def test_v1_create_financing_without_cpf_maps_options_and_sends_down_payment(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post(WITHOUT_CPF_PATH).mock(
        return_value=httpx.Response(200, json={"cotacoes": [WITHOUT_CPF_OPTION]})
    )
    client = make_client()

    options = client.v1.simulations.create_financing_without_cpf(
        CreateFinancingWithoutCpfRequest(license_plate="ABC1D23", vehicle_amount=45000, state="SP", down_payment=5000)
    )
    client.close()

    assert json.loads(route.calls.last.request.content) == {
        "placa": "ABC1D23",
        "valorVeiculo": 45000,
        "valorEntrada": 5000,
        "uf": "SP",
    }
    assert len(options) == 1
    option = options[0]
    assert (option.requested_amount, option.term, option.installment_amount) == (40000.0, 24, 2100.5)
    assert (option.tac_amount, option.boleto_amount, option.insurance_amount) == (1.0, 2.0, 3.0)
    assert (option.iof_amount, option.iof_rate) == (4.0, 0.38)
    assert (option.total_credit_amount, option.total_debt_amount) == (41000.0, 50400.0)
    assert (option.monthly_cet, option.annual_cet) == (2.9, 41.2)
    assert (option.monthly_interest_rate, option.annual_interest_rate) == (2.5, 34.5)
    assert option.minimum_down_payment == 5000.0
    assert option.approximate_daily_retention == 12.5
    assert not hasattr(option, "simulation_id")


def test_v1_create_financing_without_cpf_omits_down_payment_and_optional_field(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    option = {k: v for k, v in WITHOUT_CPF_OPTION.items() if k != "valor_retencao_diaria_aproximado"}
    route = mock_router.post(WITHOUT_CPF_PATH).mock(return_value=httpx.Response(200, json={"cotacoes": [option]}))
    client = make_client()

    options = client.v1.simulations.create_financing_without_cpf(
        CreateFinancingWithoutCpfRequest(license_plate="ABC1D23", vehicle_amount=45000, state="SP")
    )
    client.close()

    assert json.loads(route.calls.last.request.content) == {"placa": "ABC1D23", "valorVeiculo": 45000, "uf": "SP"}
    assert options[0].approximate_daily_retention is None


def test_v1_create_financing_without_cpf_does_not_send_idempotency_key_and_retries(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post(WITHOUT_CPF_PATH).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"cotacoes": [WITHOUT_CPF_OPTION]})]
    )
    client = make_client()

    options = client.v1.simulations.create_financing_without_cpf(
        CreateFinancingWithoutCpfRequest(license_plate="ABC1D23", vehicle_amount=45000, state="SP")
    )
    client.close()

    assert len(options) == 1
    assert route.call_count == 2
    assert all("idempotency-key" not in call.request.headers for call in route.calls)


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (404, "Fipe.VehiclePlateNotFound"),
        (404, "Store.Integration.NotFound"),
        (422, "Proposal.DownPaymentInvalid"),
        (422, "Simulation.Terms.Unavailable"),
    ],
)
def test_v1_create_financing_without_cpf_maps_problem_details(
    mock_router: respx.MockRouter, token_route: respx.Route, status: int, code: str
) -> None:
    route = mock_router.post(WITHOUT_CPF_PATH).mock(
        return_value=httpx.Response(status, json={"tipo": code, "titulo": "Erro", "status": status})
    )
    client = make_client()

    with pytest.raises(CredicarroApiError) as error:
        client.v1.simulations.create_financing_without_cpf(
            CreateFinancingWithoutCpfRequest(license_plate="ABC1D23", vehicle_amount=45000, state="SP")
        )
    client.close()

    assert error.value.status_code == status
    assert error.value.error_code == code
    assert route.call_count == 1


def test_create_financing_without_cpf_request_masks_license_plate() -> None:
    request = CreateFinancingWithoutCpfRequest(license_plate="ABC1D23", vehicle_amount=45000, state="SP")

    assert "ABC1D23" not in repr(request)


REFI_WITHOUT_CPF_PATH = "v1/proposal/simulation/refinancing/without-cpf"
REFI_WITHOUT_CPF_OPTION: dict[str, Any] = {
    "valor_solicitado": 25000,
    "prazo": 24,
    "valor_parcela": 1500.5,
    "valor_tac": 1,
    "valor_boleto": 2,
    "valor_seguro": 3,
    "valor_iof": 4,
    "percentual_iof": 0.38,
    "valor_credito_total": 26000,
    "valor_divida_total": 36000,
    "percentual_cet_mensal": 2.9,
    "percentual_cet_anual": 41.2,
    "percentual_juros_mensal": 2.5,
    "percentual_juros_anual": 34.5,
    "valor_retencao_diaria_aproximado": 12.5,
    "valor_minimo_refinanciavel": 10000,
    "valor_maximo_refinanciavel": 30000,
}


def test_v1_create_refinancing_without_cpf_maps_options_and_sends_wire_body(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post(REFI_WITHOUT_CPF_PATH).mock(
        return_value=httpx.Response(200, json={"cotacoes": [REFI_WITHOUT_CPF_OPTION]})
    )
    client = make_client()

    options = client.v1.simulations.create_refinancing_without_cpf(
        CreateRefinancingWithoutCpfRequest(license_plate="ABC1D23", requested_amount=25000, state="SP")
    )
    client.close()

    assert json.loads(route.calls.last.request.content) == {"placa": "ABC1D23", "valorSolicitado": 25000, "uf": "SP"}
    assert len(options) == 1
    option = options[0]
    assert (option.requested_amount, option.term, option.installment_amount) == (25000.0, 24, 1500.5)
    assert (option.tac_amount, option.boleto_amount, option.insurance_amount) == (1.0, 2.0, 3.0)
    assert (option.iof_amount, option.iof_rate) == (4.0, 0.38)
    assert (option.total_credit_amount, option.total_debt_amount) == (26000.0, 36000.0)
    assert (option.monthly_cet, option.annual_cet) == (2.9, 41.2)
    assert (option.monthly_interest_rate, option.annual_interest_rate) == (2.5, 34.5)
    assert (option.minimum_amount, option.maximum_amount) == (10000.0, 30000.0)
    assert option.approximate_daily_retention == 12.5
    assert not hasattr(option, "simulation_id")


def test_v1_create_refinancing_without_cpf_handles_missing_optional_field_and_empty_list(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    option = {k: v for k, v in REFI_WITHOUT_CPF_OPTION.items() if k != "valor_retencao_diaria_aproximado"}
    mock_router.post(REFI_WITHOUT_CPF_PATH).mock(
        side_effect=[
            httpx.Response(200, json={"cotacoes": [option]}),
            httpx.Response(200, json={"cotacoes": []}),
        ]
    )
    client = make_client()
    request = CreateRefinancingWithoutCpfRequest(license_plate="ABC1D23", requested_amount=25000, state="SP")

    options = client.v1.simulations.create_refinancing_without_cpf(request)
    empty = client.v1.simulations.create_refinancing_without_cpf(request)
    client.close()

    assert options[0].approximate_daily_retention is None
    assert empty == []


def test_v1_create_refinancing_without_cpf_does_not_send_idempotency_key_and_retries(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post(REFI_WITHOUT_CPF_PATH).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"cotacoes": [REFI_WITHOUT_CPF_OPTION]})]
    )
    client = make_client()

    options = client.v1.simulations.create_refinancing_without_cpf(
        CreateRefinancingWithoutCpfRequest(license_plate="ABC1D23", requested_amount=25000, state="SP")
    )
    client.close()

    assert len(options) == 1
    assert route.call_count == 2
    assert all("idempotency-key" not in call.request.headers for call in route.calls)


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (404, "Fipe.VehiclePlateNotFound"),
        (404, "Store.Integration.NotFound"),
        (422, "Proposal.RequestAmountInvalid"),
        (422, "Simulation.Terms.Unavailable"),
    ],
)
def test_v1_create_refinancing_without_cpf_maps_problem_details(
    mock_router: respx.MockRouter, token_route: respx.Route, status: int, code: str
) -> None:
    route = mock_router.post(REFI_WITHOUT_CPF_PATH).mock(
        return_value=httpx.Response(status, json={"tipo": code, "titulo": "Erro", "status": status})
    )
    client = make_client()

    with pytest.raises(CredicarroApiError) as error:
        client.v1.simulations.create_refinancing_without_cpf(
            CreateRefinancingWithoutCpfRequest(license_plate="ABC1D23", requested_amount=25000, state="SP")
        )
    client.close()

    assert error.value.status_code == status
    assert error.value.error_code == code
    assert route.call_count == 1


def test_create_refinancing_without_cpf_request_masks_license_plate() -> None:
    request = CreateRefinancingWithoutCpfRequest(license_plate="ABC1D23", requested_amount=25000, state="SP")

    assert "ABC1D23" not in repr(request)
