import json
from datetime import date, datetime, timezone

import httpx
import pytest
import respx

from conftest import make_client
from twila_credicarro import (
    CreateCustomerRequest,
    CredicarroApiError,
    CredicarroBusinessRuleError,
    CustomerAddress,
    OccupationType,
    ProfessionalData,
    UpsertCustomerRequest,
)

CUSTOMER_ID = "123e4567-e89b-12d3-a456-426614174000"


def _address() -> CustomerAddress:
    return CustomerAddress(
        street="Av. Paulista",
        number="1578",
        complement="Bloco B, Apto 1203",
        neighborhood="Bela Vista",
        city="São Paulo",
        state="SP",
        postal_code="01311000",
    )


def _upsert() -> UpsertCustomerRequest:
    return UpsertCustomerRequest(
        cpf="12345678909",
        first_name="Maria",
        last_name="Souza",
        email="maria.souza@exemplo.com.br",
        phone_number="+55 (11) 99876-5432",
        date_of_birth="1990-05-20T00:00:00-03:00",
        address=_address(),
        professional_data=ProfessionalData(occupation=OccupationType.EMPLOYEE, monthly_income=6500.0),
    )


def test_upsert_maps_the_request_and_returns_customer_id(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post("v1/customer/unified").mock(
        return_value=httpx.Response(200, json={"id_cliente": CUSTOMER_ID})
    )
    client = make_client()

    customer_id = client.customers.upsert(_upsert())
    client.close()

    assert customer_id == CUSTOMER_ID
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer test-token"
    assert json.loads(request.content) == {
        "cpf": "12345678909",
        "nome": "Maria",
        "sobrenome": "Souza",
        "email": "maria.souza@exemplo.com.br",
        "celular": "+55 (11) 99876-5432",
        "dataDeNascimento": "1990-05-20T00:00:00-03:00",
        "endereco": {
            "rua": "Av. Paulista",
            "numero": "1578",
            "complemento": "Bloco B, Apto 1203",
            "bairro": "Bela Vista",
            "cidade": "São Paulo",
            "estado": "SP",
            "cep": "01311000",
        },
        "dadosProfissionais": {"tipoOcupacao": 3, "renda": 6500.0},
    }


def test_optional_address_fields_are_omitted(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post("v1/customer/address").mock(return_value=httpx.Response(202, text="Accepted"))
    client = make_client()

    client.customers.upsert_address(
        "12345678909",
        CustomerAddress(
            street="Rua A", neighborhood="Centro", city="Porto Alegre", state="RS", postal_code="90000-000"
        ),
    )
    client.close()

    body = json.loads(route.calls.last.request.content)
    assert body == {
        "cpf": "12345678909",
        "endereco": {
            "rua": "Rua A",
            "bairro": "Centro",
            "cidade": "Porto Alegre",
            "estado": "RS",
            "cep": "90000-000",
        },
    }


def test_create_sends_only_the_six_personal_fields(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    route = mock_router.post("v1/customer").mock(return_value=httpx.Response(200, json={"id_cliente": CUSTOMER_ID}))
    client = make_client()

    customer_id = client.customers.create(
        CreateCustomerRequest(
            cpf="12345678909",
            first_name="Maria",
            last_name="Souza",
            email="maria.souza@exemplo.com.br",
            phone_number="+55 (11) 99876-5432",
            date_of_birth=date(1990, 5, 20),
        )
    )
    client.close()

    body = json.loads(route.calls.last.request.content)
    assert customer_id == CUSTOMER_ID
    assert sorted(body) == ["celular", "cpf", "dataDeNascimento", "email", "nome", "sobrenome"]
    assert body["dataDeNascimento"] == "1990-05-20T00:00:00-03:00"


def test_upsert_professional_data_returns_nothing_on_202(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.post("v1/customer/professional").mock(return_value=httpx.Response(202, text="Accepted"))
    client = make_client()

    result = client.customers.upsert_professional_data(
        "12345678909", ProfessionalData(occupation=OccupationType.SELF_EMPLOYED, monthly_income=4200)
    )
    client.close()

    assert result is None
    assert json.loads(route.calls.last.request.content) == {"cpf": "12345678909", "tipoOcupacao": 4, "renda": 4200}
    assert route.calls.last.request.headers["idempotency-key"]


def test_unknown_customer_raises_api_error(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.post("v1/customer/address").mock(
        return_value=httpx.Response(
            404, json={"tipo": "Customer.Account.NotFound", "titulo": "Não encontrado", "status": 404}
        )
    )
    client = make_client()

    with pytest.raises(CredicarroApiError) as error:
        client.customers.upsert_address("12345678909", _address())
    client.close()

    assert error.value.error_code == "Customer.Account.NotFound"


def test_duplicate_cpf_conflict(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    mock_router.post("v1/customer/unified").mock(
        return_value=httpx.Response(409, json={"tipo": "Cpf.CpfAlreadyAdded", "status": 409})
    )
    client = make_client()

    with pytest.raises(CredicarroApiError) as error:
        client.customers.upsert(_upsert(), idempotency_key="chave")
    client.close()

    assert error.value.status_code == 409
    assert error.value.error_code == "Cpf.CpfAlreadyAdded"
    assert not isinstance(error.value, CredicarroBusinessRuleError)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1990-05-20T00:00:00-03:00", "1990-05-20T00:00:00-03:00"),
        (date(1990, 5, 20), "1990-05-20T00:00:00-03:00"),
        (datetime(1990, 5, 20, 8, 30), "1990-05-20T08:30:00-03:00"),
        (datetime(1990, 5, 20, 8, 30, tzinfo=timezone.utc), "1990-05-20T08:30:00+00:00"),
    ],
)
def test_date_of_birth_is_sent_with_offset(value: object, expected: str) -> None:
    from twila_credicarro._internal.datetime_parsing import to_iso_string

    assert to_iso_string(value) == expected  # type: ignore[arg-type]


def test_occupation_type_values_and_unknown_fallback() -> None:
    assert [int(item) for item in OccupationType if item is not OccupationType.UNKNOWN] == [1, 2, 3, 4, 6, 7]
    assert OccupationType.from_wire_value(5) is OccupationType.UNKNOWN
    assert OccupationType.from_wire_value(None) is OccupationType.UNKNOWN
