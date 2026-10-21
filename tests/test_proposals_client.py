import json
from typing import Any

import httpx
import respx

from conftest import make_client
from twila_credicarro import (
    ActionOwner,
    BiometryStatus,
    CreateProposalRequest,
    DepositAccount,
    DepositAccountType,
    DocumentStatus,
    DocumentType,
    ListRequest,
    ProposalStatus,
    ProposalStep,
    ProposalType,
    StepSituation,
    VehicleDetails,
)

PROPOSAL_ID = "bea8d060-f93d-48eb-b6c4-45f64483cdd9"
SIMULATION_ID = "123e4567-e89b-12d3-a456-426614174000"

DETAILS: dict[str, Any] = {
    "id_proposta": PROPOSAL_ID,
    "numero": 171020250001,
    "id_simulacao": SIMULATION_ID,
    "enum_status": 2,
    "status": "APROVADA",
    "tipo": "Refinancing",
    "data_criacao": "2026-10-12T14:05:08.984-03:00",
    "motivo_recusa": None,
    "link_biometria": "https://onboarding.exemplo.com/sessao/abc123",
    "comprador": {
        "cpf": "12345678909",
        "enum_biometria": 3,
        "biometria": "APROVADA",
        "status_ativo": {
            "enum_etapa": 7,
            "etapa": "CORRECAO_DOCUMENTOS",
            "enum_situacao": 4,
            "situacao": "PENDENTE_CORRECAO",
            "enum_responsavel_acao": 2,
            "responsavel_acao": "INTEGRADOR",
        },
        "etapas_concluidas": [
            {"enum_etapa": 1, "etapa": "PROPOSTA_CRIADA", "data": "2026-10-12T14:05:08-03:00"},
            {"enum_etapa": 4, "etapa": "ANALISE_BIOMETRIA", "data": "2026-10-12T14:20:00.1234567Z"},
        ],
        "documentos": [
            {"enum_tipo": 1, "tipo": "CNH", "enum_status": 2, "status": "INVALIDO", "motivo": "Documento ilegível"},
            {"enum_tipo": 5, "tipo": "COMPROVANTE_RESIDENCIA", "enum_status": 1, "status": "VALIDO"},
        ],
    },
    "loja": {
        "cnpj": "11222333000181",
        "status_ativo": {
            "enum_etapa": 6,
            "etapa": "ENVIO_DOCUMENTOS",
            "enum_situacao": 1,
            "situacao": "AGUARDANDO_ENVIO",
            "enum_responsavel_acao": 2,
            "responsavel_acao": "INTEGRADOR",
        },
        "etapas_concluidas": [],
        "documentos": [
            {"enum_tipo": 8, "tipo": "LAUDO_ECV", "enum_status": 5, "status": "PENDENTE"},
            {"enum_tipo": 6, "tipo": "DOCUMENTO_VEICULO", "enum_status": 5, "status": "PENDENTE"},
            {"enum_tipo": 99, "tipo": "OUTRO", "enum_status": 1, "status": "VALIDO"},
        ],
    },
}


def test_create_returns_proposal_id(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post("v2/proposal").mock(return_value=httpx.Response(201, json={"id_proposta": PROPOSAL_ID}))
    client = make_client()

    proposal_id = client.proposals.create(CreateProposalRequest(cpf="12345678909", simulation_id=SIMULATION_ID))
    client.close()

    assert proposal_id == PROPOSAL_ID
    assert json.loads(route.calls.last.request.content) == {"cpf": "12345678909", "simulacaoId": SIMULATION_ID}
    assert route.calls.last.request.headers["idempotency-key"]


def test_get_maps_the_full_details(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(return_value=httpx.Response(200, json=DETAILS))
    client = make_client()

    details = client.proposals.get(PROPOSAL_ID)
    client.close()

    assert details.id == PROPOSAL_ID
    assert details.number == 171020250001
    assert details.simulation_id == SIMULATION_ID
    assert details.status is ProposalStatus.APPROVED
    assert details.status_raw == 2
    assert details.status_name == "APROVADA"
    assert details.type is ProposalType.REFINANCING
    assert details.created_at is not None and details.created_at.utcoffset() is not None
    assert details.refusal_reason is None
    assert details.biometry_link == "https://onboarding.exemplo.com/sessao/abc123"
    assert details.seller is None

    buyer = details.buyer
    assert buyer is not None
    assert buyer.document == "12345678909"
    assert buyer.biometry is BiometryStatus.APPROVED
    assert (buyer.biometry_raw, buyer.biometry_name) == (3, "APROVADA")
    assert buyer.active_step is not None
    assert buyer.active_step.step is ProposalStep.DOCUMENT_CORRECTION
    assert buyer.active_step.situation is StepSituation.PENDING_CORRECTION
    assert buyer.active_step.action_owner is ActionOwner.INTEGRATOR
    assert (buyer.active_step.step_raw, buyer.active_step.step_name) == (7, "CORRECAO_DOCUMENTOS")
    assert [step.step for step in buyer.completed_steps] == [
        ProposalStep.PROPOSAL_CREATED,
        ProposalStep.BIOMETRY_ANALYSIS,
    ]
    assert buyer.completed_steps[1].date is not None
    assert buyer.documents[0].type is DocumentType.CNH
    assert buyer.documents[0].status is DocumentStatus.INVALID
    assert buyer.documents[0].reason == "Documento ilegível"
    assert buyer.documents[1].reason is None

    store = details.store
    assert store is not None
    assert store.document == "11222333000181"
    assert store.biometry is None
    assert store.documents[2].type is DocumentType.UNKNOWN
    assert store.documents[2].type_raw == 99
    assert store.documents[2].type_name == "OUTRO"


def test_get_pending_actions_only_for_the_integrator(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(return_value=httpx.Response(200, json=DETAILS))
    client = make_client()

    actions = client.proposals.get(PROPOSAL_ID).get_pending_actions()
    client.close()

    assert [(a.participant.value, a.step, a.kind.value) for a in actions] == [
        ("COMPRADOR", ProposalStep.DOCUMENT_CORRECTION, "CorrectDocuments"),
        ("LOJA", ProposalStep.DOCUMENT_SUBMISSION, "SendDocuments"),
    ]
    assert actions[0].document_types == (DocumentType.CNH,)
    assert actions[1].document_types == (DocumentType.ECV_REPORT, DocumentType.VEHICLE_DOCUMENT)


def test_send_vehicle_details(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post(f"v2/proposal/{PROPOSAL_ID}/vehicle-detail").mock(return_value=httpx.Response(204))
    client = make_client()

    result = client.proposals.send_vehicle_details(
        PROPOSAL_ID,
        VehicleDetails(renavam="12345678900", chassis="9BWZZZ377VT004251", license_plate="ABC1D23", color="PRATA"),
    )
    client.close()

    assert result is None
    assert json.loads(route.calls.last.request.content) == {
        "renavam": "12345678900",
        "chassi": "9BWZZZ377VT004251",
        "placa": "ABC1D23",
        "cor": "PRATA",
    }


def test_send_deposit_account(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post(f"v2/proposal/{PROPOSAL_ID}/deposit-account").mock(return_value=httpx.Response(204))
    client = make_client()

    client.proposals.send_deposit_account(
        PROPOSAL_ID,
        DepositAccount(
            holder_cpf="12345678909",
            bank_code="001",
            branch="1234",
            branch_digit="5",
            account_number="123456",
            account_digit="7",
            account_type=DepositAccountType.SAVINGS,
        ),
    )
    client.close()

    assert json.loads(route.calls.last.request.content) == {
        "cpfTitular": "12345678909",
        "codigoBanco": "001",
        "agencia": "1234",
        "digitoAgencia": "5",
        "conta": "123456",
        "digitoConta": "7",
        "tipoConta": "POUPANCA",
    }


def test_account_types_wire_values() -> None:
    assert [item.value for item in DepositAccountType] == ["CORRENTE", "POUPANCA", "PAGAMENTO"]


def test_list_proposals_maps_summaries(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.get("v1/proposal").mock(
        return_value=httpx.Response(
            200,
            json={
                "itens": [
                    {
                        "id_proposta": PROPOSAL_ID,
                        "numero": 171020250001,
                        "id_simulacao": SIMULATION_ID,
                        "tipo": "Financing",
                        "status": "ManualAnalysis",
                        "comprador": {"cpf": "123.456.789-01"},
                        "vendedor": {"cpf": "987.654.321-00"},
                        "data_criacao": "2025-10-17T19:05:08.984Z",
                    },
                    {"id_proposta": SIMULATION_ID, "tipo": "Outro", "status": "Novo", "comprador": {"cpf": "1"}},
                ],
                "pagina": {"tem_proximo": False, "tem_anterior": True, "numero": 2, "tamanho": 15, "total": 17},
            },
        )
    )
    client = make_client()

    page = client.proposals.list(ListRequest(page=2, page_size=15))
    client.close()

    params = route.calls.last.request.url.params
    assert (params["pagina_inicial"], params["limite"]) == ("2", "15")
    assert (page.has_next, page.has_previous, page.page, page.page_size, page.total_count) == (
        False,
        True,
        2,
        15,
        17,
    )
    first, second = page.items
    assert first.status is ProposalStatus.MANUAL_ANALYSIS
    assert first.status_name == "ManualAnalysis"
    assert first.type is ProposalType.FINANCING
    assert (first.buyer_cpf, first.seller_cpf) == ("123.456.789-01", "987.654.321-00")
    assert second.status is ProposalStatus.UNKNOWN
    assert second.status_name == "Novo"
    assert second.type is ProposalType.UNKNOWN
    assert second.seller_cpf is None
