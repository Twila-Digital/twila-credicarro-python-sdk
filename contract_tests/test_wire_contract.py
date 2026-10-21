"""Contract tests: os wire types do SDK contra o `openapi.yaml` público (precisam de rede)."""

from datetime import date
from typing import Any, Callable

import pytest

from openapi_schema_fixture import (
    assert_matches_schema,
    fetch_openapi,
    operations,
    parameters,
    request_schema,
    resolve,
    response_schema,
    sample,
)
from twila_credicarro import (
    CreateCustomerRequest,
    CreateFinancingSimulationRequest,
    CreateFinancingSimulationV1Request,
    CreateProposalRequest,
    CreateRefinancingSimulationRequest,
    CreateRefinancingSimulationV1Request,
    CreateWebhookRequest,
    CustomerAddress,
    DepositAccount,
    DepositAccountType,
    DocumentFile,
    DocumentType,
    OccupationType,
    ProfessionalData,
    ProposalDocumentUpload,
    ProposalParticipant,
    UpdateWebhookRequest,
    UpsertCustomerRequest,
    VehicleDetails,
    WebhookAuthenticationType,
    WebhookStatus,
    WebhookType,
)
from twila_credicarro._internal.auth.access_token_provider import AccessTokenProvider
from twila_credicarro._internal.auth.credentials import TokenCredentials
from twila_credicarro._internal.idempotency.idempotency_classifier import (
    idempotency_key_is_mandatory,
    requires_idempotency_key,
)
from twila_credicarro._internal.mapping import customer_mapper, proposal_mapper, simulation_mapper, webhook_mapper
from twila_credicarro._internal.mapping.paged_mapper import paged_result_from_wire
from twila_credicarro._internal.mapping.wire import as_dict, req_str
from twila_credicarro.errors.problem_details import parse_problem_details

SDK_OPERATIONS = {
    ("post", "/v1/authentication/accesstoken"),
    ("post", "/v1/customer"),
    ("post", "/v1/customer/address"),
    ("post", "/v1/customer/professional"),
    ("post", "/v1/customer/unified"),
    ("get", "/v1/proposal"),
    ("post", "/v1/proposal"),
    ("get", "/v1/proposal/{propostaId}"),
    ("get", "/v1/proposal/simulation"),
    ("get", "/v1/proposal/simulation/{simulacaoId}"),
    ("get", "/v1/proposal/simulation/range/financing"),
    ("get", "/v1/proposal/simulation/range/refinancing"),
    ("post", "/v1/proposal/simulation/financing"),
    ("post", "/v1/proposal/simulation/refinancing"),
    ("post", "/v1/webhook"),
    ("get", "/v1/webhook"),
    ("put", "/v1/webhook/{webhookId}"),
    ("delete", "/v1/webhook/{webhookId}"),
    ("get", "/v2/proposal/simulation/range/financing"),
    ("get", "/v2/proposal/simulation/range/refinancing"),
    ("post", "/v2/proposal/simulation/financing"),
    ("post", "/v2/proposal/simulation/refinancing"),
    ("post", "/v2/proposal"),
    ("get", "/v2/proposal/{propostaId}"),
    ("post", "/v2/proposal/{propostaId}/vehicle-detail"),
    ("post", "/v2/proposal/{propostaId}/deposit-account"),
    ("post", "/v2/proposal/{propostaId}/document"),
}

QUERY_PARAMETERS = {
    ("get", "/v1/proposal"): {"pagina_inicial", "limite"},
    ("get", "/v1/proposal/simulation"): {"pagina_inicial", "limite"},
    ("get", "/v1/webhook"): {"pagina_inicial", "limite"},
    ("get", "/v1/proposal/simulation/range/financing"): {"placa"},
    ("get", "/v1/proposal/simulation/range/refinancing"): {"placa"},
    ("get", "/v2/proposal/simulation/range/financing"): {"placa", "cnpjLoja"},
    ("get", "/v2/proposal/simulation/range/refinancing"): {"placa", "cnpjLoja"},
}

_ADDRESS_FULL = CustomerAddress(
    street="Av. Paulista",
    number="1578",
    complement="Bloco B",
    neighborhood="Bela Vista",
    city="São Paulo",
    state="SP",
    postal_code="01311000",
)
_ADDRESS_MIN = CustomerAddress(
    street="Av. Paulista", neighborhood="Bela Vista", city="São Paulo", state="SP", postal_code="01311000"
)
_PROFESSIONAL = ProfessionalData(occupation=OccupationType.EMPLOYEE, monthly_income=6500.0)
_PERSONAL = {
    "cpf": "12345678909",
    "first_name": "Maria",
    "last_name": "Souza",
    "email": "maria.souza@exemplo.com.br",
    "phone_number": "+55 (11) 99876-5432",
    "date_of_birth": date(1990, 5, 20),
}
_UPLOAD = ProposalDocumentUpload(
    participant=ProposalParticipant.STORE,
    document_type=DocumentType.ECV_REPORT,
    file=DocumentFile.from_bytes(b"%PDF", "laudo.pdf"),
)

REQUESTS: list[tuple[str, str, dict[str, Any]]] = [
    ("post", "/v1/customer", customer_mapper.create_customer_request_to_wire(CreateCustomerRequest(**_PERSONAL))),
    (
        "post",
        "/v1/customer/unified",
        customer_mapper.upsert_customer_request_to_wire(
            UpsertCustomerRequest(**_PERSONAL, address=_ADDRESS_FULL, professional_data=_PROFESSIONAL)
        ),
    ),
    (
        "post",
        "/v1/customer/unified",
        customer_mapper.upsert_customer_request_to_wire(
            UpsertCustomerRequest(**_PERSONAL, address=_ADDRESS_MIN, professional_data=_PROFESSIONAL)
        ),
    ),
    ("post", "/v1/customer/address", customer_mapper.upsert_address_request_to_wire("12345678909", _ADDRESS_FULL)),
    ("post", "/v1/customer/address", customer_mapper.upsert_address_request_to_wire("12345678909", _ADDRESS_MIN)),
    (
        "post",
        "/v1/customer/professional",
        customer_mapper.upsert_professional_request_to_wire("12345678909", _PROFESSIONAL),
    ),
    (
        "post",
        "/v2/proposal/simulation/financing",
        simulation_mapper.financing_request_to_wire(
            CreateFinancingSimulationRequest("12345678909", "ABC1D23", 45000, 5000, "SP", False, "11222333000181")
        ),
    ),
    (
        "post",
        "/v2/proposal/simulation/refinancing",
        simulation_mapper.refinancing_request_to_wire(
            CreateRefinancingSimulationRequest("12345678909", "ABC1D23", 25000, "11222333000181")
        ),
    ),
    (
        "post",
        "/v1/proposal/simulation/financing",
        simulation_mapper.financing_v1_request_to_wire(
            CreateFinancingSimulationV1Request("12345678909", "ABC1D23", 45000, 5000, "SP", True)
        ),
    ),
    (
        "post",
        "/v1/proposal/simulation/refinancing",
        simulation_mapper.refinancing_v1_request_to_wire(
            CreateRefinancingSimulationV1Request("12345678909", "ABC1D23", 25000)
        ),
    ),
    (
        "post",
        "/v2/proposal",
        proposal_mapper.create_proposal_request_to_wire(
            CreateProposalRequest("12345678909", "bea8d060-f93d-48eb-b6c4-45f64483cdd9")
        ),
    ),
    (
        "post",
        "/v1/proposal",
        proposal_mapper.create_proposal_request_to_wire(
            CreateProposalRequest("12345678909", "bea8d060-f93d-48eb-b6c4-45f64483cdd9")
        ),
    ),
    (
        "post",
        "/v2/proposal/{propostaId}/vehicle-detail",
        proposal_mapper.vehicle_details_to_wire(VehicleDetails("12345678900", "9BWZZZ377VT004251", "ABC1D23", "PRATA")),
    ),
    *[
        (
            "post",
            "/v2/proposal/{propostaId}/deposit-account",
            proposal_mapper.deposit_account_to_wire(
                DepositAccount("12345678909", "001", "1234", "5", "123456", "7", account_type)
            ),
        )
        for account_type in DepositAccountType
    ],
    *[
        (
            "post",
            "/v2/proposal/{propostaId}/document",
            proposal_mapper.document_upload_to_wire(
                ProposalDocumentUpload(participant, DocumentType.CNH, DocumentFile.from_bytes(b"x", "a.png"))
            ),
        )
        for participant in ProposalParticipant
    ],
    ("post", "/v2/proposal/{propostaId}/document", proposal_mapper.document_upload_to_wire(_UPLOAD)),
    *[
        (
            "post",
            "/v1/webhook",
            webhook_mapper.create_webhook_request_to_wire(
                CreateWebhookRequest(WebhookType.PROPOSAL, "https://parceiro.com.br/h", auth, credential)
            ),
        )
        for auth, credential in (
            (WebhookAuthenticationType.NONE, None),
            (WebhookAuthenticationType.BASIC, "dXN1YXJpbzpzZW5oYQ=="),
            (WebhookAuthenticationType.JWT, "token"),
        )
    ],
    *[
        (
            "put",
            "/v1/webhook/{webhookId}",
            webhook_mapper.update_webhook_request_to_wire(
                UpdateWebhookRequest(WebhookType.SIMULATION, "https://parceiro.com.br/h", status)
            ),
        )
        for status in (None, WebhookStatus.ACTIVE, WebhookStatus.INACTIVE)
    ],
]


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return fetch_openapi()


def test_every_public_operation_has_an_sdk_method(spec: dict[str, Any]) -> None:
    published = set(operations(spec))

    assert published - SDK_OPERATIONS == set(), "O OpenAPI tem operações que o SDK não cobre."
    assert SDK_OPERATIONS - published == set(), "O SDK usa operações que não existem mais no OpenAPI."


def test_server_urls_match_the_sdk_environments(spec: dict[str, Any]) -> None:
    urls = {server["url"].rstrip("/") + "/" for server in spec["servers"]}

    assert urls == {
        "https://api.staging.credicarro.com.br/integration/",
        "https://api.credicarro.com.br/integration/",
    }


@pytest.mark.parametrize(("method", "path"), sorted(QUERY_PARAMETERS))
def test_query_parameters_sent_by_the_sdk_exist(spec: dict[str, Any], method: str, path: str) -> None:
    declared = {p["name"] for p in parameters(spec, operations(spec)[(method, path)]) if p["in"] == "query"}

    assert QUERY_PARAMETERS[(method, path)] <= declared


@pytest.mark.parametrize(("method", "path"), sorted(op for op in SDK_OPERATIONS if op[0] == "post"))
def test_idempotency_key_policy_matches_the_openapi(spec: dict[str, Any], method: str, path: str) -> None:
    operation = operations(spec)[(method, path)]
    header = next(
        (p for p in parameters(spec, operation) if p["in"] == "header" and p["name"] == "Idempotency-Key"), None
    )
    sdk_path = path.replace("{propostaId}", "abc").lstrip("/")

    if path == "/v1/customer/unified":
        assert header is not None
        assert requires_idempotency_key("POST", sdk_path) is False
        return

    assert (header is not None) == requires_idempotency_key("POST", sdk_path)
    if header is not None:
        assert bool(header.get("required", False)) == idempotency_key_is_mandatory("POST", sdk_path)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    REQUESTS,
    ids=[f"{method}-{path}-{index}" for index, (method, path, _) in enumerate(REQUESTS)],
)
def test_request_wire_types_match_the_request_schema(
    spec: dict[str, Any], method: str, path: str, body: dict[str, Any]
) -> None:
    schema = request_schema(spec, operations(spec)[(method, path)])

    assert schema is not None
    assert_matches_schema(spec, schema, body)


def _customer_id(wire: Any) -> str:
    return req_str(as_dict(wire, "cadastro"), "id_cliente")


def _token(wire: Any) -> float:
    class _Api:
        def generate(self, credentials: Any) -> Any:
            return wire

    provider = AccessTokenProvider(_Api(), TokenCredentials("id", "secret"))  # type: ignore[arg-type]
    provider.get_token()
    return provider._expires_at(wire)  # noqa: SLF001


def _paged_webhooks(wire: Any) -> Any:
    return paged_result_from_wire(wire, webhook_mapper.webhook_to_public)


RESPONSES: list[tuple[str, str, str, Callable[[Any], Any], frozenset[str]]] = [
    ("post", "/v1/authentication/accesstoken", "200", _token, frozenset()),
    ("post", "/v1/customer", "200", _customer_id, frozenset()),
    ("post", "/v1/customer/unified", "200", _customer_id, frozenset()),
    ("post", "/v1/proposal", "201", proposal_mapper.proposal_id_to_public, frozenset()),
    ("post", "/v2/proposal", "201", proposal_mapper.proposal_id_to_public, frozenset()),
    ("get", "/v2/proposal/{propostaId}", "200", lambda w: proposal_mapper.proposal_details_to_public(w), frozenset()),
    ("get", "/v1/proposal/{propostaId}", "200", lambda w: proposal_mapper.proposal_summary_to_public(w), frozenset()),
    (
        "get",
        "/v1/proposal",
        "200",
        lambda w: paged_result_from_wire(w, proposal_mapper.proposal_summary_to_public),
        frozenset(),
    ),
    (
        "get",
        "/v1/proposal/simulation/{simulacaoId}",
        "200",
        lambda w: simulation_mapper.simulation_to_public(w),
        frozenset(),
    ),
    (
        "get",
        "/v1/proposal/simulation",
        "200",
        lambda w: paged_result_from_wire(w, simulation_mapper.simulation_to_public),
        frozenset(),
    ),
    ("get", "/v1/proposal/simulation/range/financing", "200", simulation_mapper.financing_range_to_public, frozenset()),
    ("get", "/v2/proposal/simulation/range/financing", "200", simulation_mapper.financing_range_to_public, frozenset()),
    (
        "get",
        "/v1/proposal/simulation/range/refinancing",
        "200",
        simulation_mapper.refinancing_range_to_public,
        frozenset(),
    ),
    (
        "get",
        "/v2/proposal/simulation/range/refinancing",
        "200",
        simulation_mapper.refinancing_range_to_public,
        frozenset(),
    ),
    ("post", "/v1/proposal/simulation/financing", "201", simulation_mapper.simulation_options_to_public, frozenset()),
    ("post", "/v1/proposal/simulation/refinancing", "201", simulation_mapper.simulation_options_to_public, frozenset()),
    ("post", "/v2/proposal/simulation/financing", "201", simulation_mapper.simulation_options_to_public, frozenset()),
    ("post", "/v2/proposal/simulation/refinancing", "201", simulation_mapper.simulation_options_to_public, frozenset()),
    ("post", "/v1/webhook", "201", webhook_mapper.create_webhook_result_to_public, frozenset()),
    ("get", "/v1/webhook", "200", _paged_webhooks, frozenset()),
]


@pytest.mark.parametrize(
    ("method", "path", "status", "reader", "extra_allowed"),
    RESPONSES,
    ids=[f"{method}-{path}" for method, path, *_ in RESPONSES],
)
def test_response_readers_only_use_properties_of_the_response_schema(
    spec: dict[str, Any],
    method: str,
    path: str,
    status: str,
    reader: Callable[[Any], Any],
    extra_allowed: frozenset[str],
) -> None:
    schema = response_schema(spec, operations(spec)[(method, path)], status)
    violations: list[str] = []

    wire = sample(spec, schema, violations, "$", extra_allowed)
    result = reader(wire)

    assert result is not None
    assert violations == [], f"O SDK lê campos que não estão no schema: {violations}"


def test_problem_details_reader_only_uses_documented_fields_plus_the_standard_fallback(spec: dict[str, Any]) -> None:
    schema = resolve(spec, spec["components"]["schemas"]["ProblemDetails"])
    violations: list[str] = []

    wire = sample(spec, schema, violations, "$", frozenset({"type", "title", "detail"}))
    problem = parse_problem_details(wire)

    assert violations == []
    assert problem.type and problem.title and problem.detail and problem.field
    assert problem.errors and problem.errors[0].code
    assert set(schema["properties"]) == {"tipo", "titulo", "status", "detalhe", "campo", "erros"}


def test_enum_names_in_the_openapi_are_known_to_the_sdk(spec: dict[str, Any]) -> None:
    from twila_credicarro import (
        ActionOwner,
        BiometryStatus,
        DocumentStatus,
        ProposalStatus,
        ProposalStep,
        StepSituation,
    )

    schemas = spec["components"]["schemas"]
    participant = schemas["ProposalV2Participant"]["properties"]
    document = schemas["ProposalV2Document"]["properties"]
    active = schemas["ProposalV2ActiveStep"]["properties"]
    details = schemas["ProposalV2Response"]["properties"]

    cases = [
        (ProposalStatus, details["status"]["enum"]),
        (ProposalStep, active["etapa"]["enum"]),
        (StepSituation, active["situacao"]["enum"]),
        (ActionOwner, active["responsavel_acao"]["enum"]),
        (BiometryStatus, participant["biometria"]["enum"]),
        (DocumentStatus, document["status"]["enum"]),
        (ProposalStatus, schemas["ProposalResponse"]["properties"]["status"]["enum"]),
    ]
    for enum_class, names in cases:
        for name in names:
            assert enum_class.from_wire_name(name) is not enum_class.UNKNOWN, f"{enum_class.__name__}: {name}"  # type: ignore[attr-defined]
