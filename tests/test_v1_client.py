import json
from typing import Any

import httpx
import respx

from conftest import make_client
from twila_credicarro import (
    CreateFinancingSimulationV1Request,
    CreateProposalRequest,
    CreateRefinancingSimulationV1Request,
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
