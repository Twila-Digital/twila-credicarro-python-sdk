from typing import Any

from ...customers.types import (
    CreateCustomerRequest,
    CustomerAddress,
    ProfessionalData,
    UpsertCustomerRequest,
    to_iso_string,
)


def address_to_wire(address: CustomerAddress) -> dict[str, Any]:
    wire: dict[str, Any] = {
        "rua": address.street,
        "bairro": address.neighborhood,
        "cidade": address.city,
        "estado": address.state,
        "cep": address.postal_code,
    }
    if address.number is not None:
        wire["numero"] = address.number
    if address.complement is not None:
        wire["complemento"] = address.complement
    return wire


def professional_data_to_wire(data: ProfessionalData) -> dict[str, Any]:
    return {"tipoOcupacao": int(data.occupation), "renda": data.monthly_income}


def create_customer_request_to_wire(request: CreateCustomerRequest) -> dict[str, Any]:
    return {
        "cpf": request.cpf,
        "nome": request.first_name,
        "sobrenome": request.last_name,
        "email": request.email,
        "celular": request.phone_number,
        "dataDeNascimento": to_iso_string(request.date_of_birth),
    }


def upsert_customer_request_to_wire(request: UpsertCustomerRequest) -> dict[str, Any]:
    wire = create_customer_request_to_wire(
        CreateCustomerRequest(
            cpf=request.cpf,
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            phone_number=request.phone_number,
            date_of_birth=request.date_of_birth,
        )
    )
    wire["endereco"] = address_to_wire(request.address)
    wire["dadosProfissionais"] = professional_data_to_wire(request.professional_data)
    return wire


def upsert_address_request_to_wire(cpf: str, address: CustomerAddress) -> dict[str, Any]:
    return {"cpf": cpf, "endereco": address_to_wire(address)}


def upsert_professional_request_to_wire(cpf: str, data: ProfessionalData) -> dict[str, Any]:
    return {"cpf": cpf, **professional_data_to_wire(data)}
