from typing import Optional

from .._internal.http.api_request_executor import ApiRequestExecutor
from .._internal.mapping.customer_mapper import (
    create_customer_request_to_wire,
    upsert_address_request_to_wire,
    upsert_customer_request_to_wire,
    upsert_professional_request_to_wire,
)
from .._internal.mapping.wire import as_dict, req_str
from .types import CreateCustomerRequest, CustomerAddress, ProfessionalData, UpsertCustomerRequest


class CustomersClient:
    def __init__(self, executor: ApiRequestExecutor) -> None:
        self._executor = executor

    def upsert(self, request: UpsertCustomerRequest, idempotency_key: Optional[str] = None) -> str:
        """Cria ou atualiza o cliente com dados completos (`POST v1/customer/unified`) e devolve o `id_cliente`.

        Sem `idempotency_key` (o padrão) a rota faz upsert: cria, ou atualiza se o CPF já existe — e, por isso,
        a chamada NÃO é repetida em caso de falha e o SDK NÃO gera chave automática. Com `idempotency_key` a rota
        só cria (CPF existente => `409` `Cpf.CpfAlreadyAdded`) e a chamada passa a ser repetida com a mesma chave.
        """
        response = self._executor.post(
            "v1/customer/unified", upsert_customer_request_to_wire(request), idempotency_key=idempotency_key
        )
        ApiRequestExecutor.ensure_success(response)

        return req_str(as_dict(response.body, "a resposta do cadastro"), "id_cliente")

    def create(self, request: CreateCustomerRequest) -> str:
        """Cria um cliente só com os dados pessoais (`POST v1/customer`) e devolve o `id_cliente`."""
        response = self._executor.post("v1/customer", create_customer_request_to_wire(request))
        ApiRequestExecutor.ensure_success(response)

        return req_str(as_dict(response.body, "a resposta do cadastro"), "id_cliente")

    def upsert_address(self, cpf: str, address: CustomerAddress) -> None:
        """Cria ou atualiza o endereço de um cliente existente (`202`, sem corpo)."""
        response = self._executor.post("v1/customer/address", upsert_address_request_to_wire(cpf, address))
        ApiRequestExecutor.ensure_success(response)

    def upsert_professional_data(self, cpf: str, data: ProfessionalData) -> None:
        """Cria ou atualiza ocupação e renda de um cliente existente (`202`, sem corpo)."""
        response = self._executor.post("v1/customer/professional", upsert_professional_request_to_wire(cpf, data))
        ApiRequestExecutor.ensure_success(response)
