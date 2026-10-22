"""Ciclo 2: erros do endpoint de token e serialização dos modelos (a máscara vale só para repr)."""

import dataclasses
import json
import pickle
from typing import Any

import httpx
import pytest
import respx

from conftest import make_client
from twila_credicarro import (
    CreateCustomerRequest,
    CreateFinancingSimulationRequest,
    CredicarroApiError,
    CredicarroAuthenticationError,
    CredicarroBusinessRuleError,
    CredicarroClientOptions,
    CredicarroRateLimitError,
    CredicarroTimeoutError,
    CustomerAddress,
    DocumentFile,
    ProposalDetails,
    ProposalStatus,
    ProposalType,
    VehicleDetails,
)
from twila_credicarro._internal.auth.access_token_provider import AccessTokenProvider
from twila_credicarro._internal.auth.credentials import TokenCredentials
from twila_credicarro.config.client_options import resolve_client_options

PROPOSAL_ID = "bea8d060-f93d-48eb-b6c4-45f64483cdd9"


def _call_with_token_response(mock_router: respx.MockRouter, response: httpx.Response, **resilience: Any) -> Exception:
    mock_router.post("v1/authentication/accesstoken").mock(return_value=response)
    client = make_client(**resilience)
    try:
        with pytest.raises(Exception) as error:
            client.proposals.get(PROPOSAL_ID)
    finally:
        client.close()
    return error.value  # type: ignore[return-value]


@pytest.mark.parametrize("status", [400, 401])
def test_token_400_and_401_are_authentication_errors(mock_router: respx.MockRouter, status: int) -> None:
    body = {"tipo": "Integration.Authentication.InvalidCredentials", "titulo": "x", "status": status}

    error = _call_with_token_response(mock_router, httpx.Response(status, json=body))

    assert isinstance(error, CredicarroAuthenticationError)
    assert error.status_code == status
    assert "test-client-secret" not in str(error)


@pytest.mark.parametrize("status", [302, 307, 403, 404, 500, 502, 503])
def test_other_token_statuses_are_api_errors(mock_router: respx.MockRouter, status: int) -> None:
    body = {"tipo": "Algum.Tipo", "titulo": "t", "status": status}

    error = _call_with_token_response(mock_router, httpx.Response(status, json=body), max_retry_attempts=2)

    assert isinstance(error, CredicarroApiError)
    assert not isinstance(error, CredicarroAuthenticationError)
    assert error.status_code == status
    assert error.error_code == "Algum.Tipo"


def test_token_422_and_429_keep_their_specific_api_errors(mock_router: respx.MockRouter) -> None:
    assert isinstance(
        _call_with_token_response(mock_router, httpx.Response(422, json={"tipo": "X"})), CredicarroBusinessRuleError
    )
    assert isinstance(
        _call_with_token_response(
            mock_router, httpx.Response(429, headers={"Retry-After": "3600"}, json={"tipo": "X"})
        ),
        CredicarroRateLimitError,
    )


def test_token_503_is_retried_and_then_becomes_an_api_error(mock_router: respx.MockRouter) -> None:
    route = mock_router.post("v1/authentication/accesstoken").mock(return_value=httpx.Response(503))
    client = make_client()

    with pytest.raises(CredicarroApiError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert route.call_count == 3
    assert error.value.status_code == 503


def test_token_network_failure_is_a_timeout_error(mock_router: respx.MockRouter) -> None:
    mock_router.post("v1/authentication/accesstoken").mock(side_effect=httpx.ConnectError("sem rede"))
    client = make_client(max_retry_attempts=1)

    with pytest.raises(CredicarroTimeoutError):
        client.proposals.get(PROPOSAL_ID)
    client.close()



def _details() -> ProposalDetails:
    return ProposalDetails(
        id=PROPOSAL_ID,
        number=1,
        simulation_id="s",
        status=ProposalStatus.REFUSED,
        type=ProposalType.FINANCING,
        refusal_reason="Restrição cadastral",
        biometry_link="https://onboarding.exemplo.com/sessao/abc",
    )


def _customer() -> CreateCustomerRequest:
    return CreateCustomerRequest(
        "12345678909", "Maria", "Souza", "m@x.com", "+55 (11) 99876-5432", "1990-05-20T00:00:00-03:00"
    )


def test_models_pickle_round_trip_with_real_values() -> None:
    models: list[Any] = [
        _customer(),
        CustomerAddress("Av. Paulista", "Bela Vista", "São Paulo", "SP", "01311000", "1578"),
        CreateFinancingSimulationRequest("12345678909", "ABC1D23", 1, 0, "SP", False, "11222333000181"),
        VehicleDetails("12345678900", "9BWZZZ377VT004251", "ABC1D23", "PRATA"),
        _details(),
        DocumentFile.from_bytes(b"%PDF", "a.pdf"),
    ]

    for model in models:
        assert pickle.loads(pickle.dumps(model)) == model


def test_models_serialize_to_json_with_real_values() -> None:
    request = _customer()
    data = json.loads(json.dumps(dataclasses.asdict(request)))

    assert data["cpf"] == "12345678909"
    assert data["first_name"] == "Maria"
    assert data["email"] == "m@x.com"
    assert dataclasses.asdict(_details())["refusal_reason"] == "Restrição cadastral"
    assert dataclasses.replace(request, first_name="Ana").first_name == "Ana"


def test_repr_masks_but_attributes_keep_real_values() -> None:
    details = _details()
    address = CustomerAddress("Av. Paulista", "Bela Vista", "São Paulo", "SP", "01311000", "1578")
    vehicle = VehicleDetails("12345678900", "9BWZZZ377VT004251", "ABC1D23", "PRATA")

    for value, hidden in (
        (details, ("Restrição", "onboarding.exemplo.com")),
        (address, ("Paulista", "Bela Vista", "São Paulo", "01311000", "1578")),
        (vehicle, ("ABC1D23",)),
        (_customer(), ("Maria", "Souza")),
    ):
        for secret in hidden:
            assert secret not in repr(value)
    assert details.refusal_reason == "Restrição cadastral"
    assert address.street == "Av. Paulista"


def test_license_plate_is_masked_in_simulation_requests() -> None:
    request = CreateFinancingSimulationRequest("12345678909", "ABC1D23", 1, 0, "SP", False, "11222333000181")

    assert "ABC1D23" not in repr(request)
    assert request.license_plate == "ABC1D23"


def test_objects_that_hold_secrets_refuse_serialization() -> None:
    options = CredicarroClientOptions(client_id="id", client_secret="segredo")

    for obj in (options, resolve_client_options(options)):
        with pytest.raises(TypeError):
            pickle.dumps(obj)

    class Api:
        def generate(self, credentials: object) -> dict[str, Any]:
            return {"token_de_acesso": "t", "expira_em_segundos": 3600}

    provider = AccessTokenProvider(Api(), TokenCredentials("id", "segredo"))  # type: ignore[arg-type]
    provider.get_token()
    with pytest.raises(TypeError):
        pickle.dumps(provider)
    with pytest.raises(TypeError):
        pickle.dumps(TokenCredentials("id", "segredo"))
