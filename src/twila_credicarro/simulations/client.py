from typing import Optional

from .._internal.http.api_request_executor import ApiRequestExecutor
from .._internal.http.query_string import QueryStringBuilder, paged_path
from .._internal.mapping.paged_mapper import paged_result_from_wire
from .._internal.mapping.simulation_mapper import (
    commission_returns_to_public,
    financing_range_to_public,
    financing_request_to_wire,
    refinancing_range_to_public,
    refinancing_request_to_wire,
    simulation_options_to_public,
    simulation_to_public,
)
from .._internal.mapping.wire import as_dict
from .._internal.path import Identifier, path_segment
from ..paged_result import ListRequest, PagedResult
from .types import (
    CommissionReturn,
    CreateFinancingSimulationRequest,
    CreateRefinancingSimulationRequest,
    FinancingRangeOption,
    RefinancingRangeOption,
    Simulation,
    SimulationOption,
)


class SimulationsClient:
    """Simulações da API v2 (com `cnpjLoja`) e consultas das simulações já criadas (`v1/proposal/simulation`)."""

    def __init__(self, executor: ApiRequestExecutor) -> None:
        self._executor = executor

    def get_financing_range(self, license_plate: str, store_cnpj: str) -> list[FinancingRangeOption]:
        """Entrada mínima por prazo para a placa e a loja (`GET v2/proposal/simulation/range/financing`)."""
        path = (
            QueryStringBuilder()
            .add("placa", license_plate)
            .add("cnpjLoja", store_cnpj)
            .build("v2/proposal/simulation/range/financing")
        )
        response = self._executor.get(path)
        ApiRequestExecutor.ensure_success(response)

        return financing_range_to_public(response.body)

    def get_refinancing_range(self, license_plate: str, store_cnpj: str) -> list[RefinancingRangeOption]:
        """Faixa refinanciável por prazo para a placa e a loja (`GET v2/proposal/simulation/range/refinancing`)."""
        path = (
            QueryStringBuilder()
            .add("placa", license_plate)
            .add("cnpjLoja", store_cnpj)
            .build("v2/proposal/simulation/range/refinancing")
        )
        response = self._executor.get(path)
        ApiRequestExecutor.ensure_success(response)

        return refinancing_range_to_public(response.body)

    def get_commission_returns(self, store_cnpj: str) -> list[CommissionReturn]:
        """Retornos de comissão configurados para a loja, por tipo de simulação
        (`GET v2/proposal/simulation/commission-returns`). Use um dos valores devolvidos em
        `commission_return` ao criar a simulação."""
        path = QueryStringBuilder().add("cnpjLoja", store_cnpj).build("v2/proposal/simulation/commission-returns")
        response = self._executor.get(path)
        ApiRequestExecutor.ensure_success(response)

        return commission_returns_to_public(response.body)

    def create_financing(self, request: CreateFinancingSimulationRequest) -> list[SimulationOption]:
        """Simula um financiamento (`POST v2/proposal/simulation/financing`), com `Idempotency-Key` automática."""
        response = self._executor.post("v2/proposal/simulation/financing", financing_request_to_wire(request))
        ApiRequestExecutor.ensure_success(response)

        return simulation_options_to_public(response.body)

    def create_refinancing(self, request: CreateRefinancingSimulationRequest) -> list[SimulationOption]:
        """Simula um refinanciamento (`POST v2/proposal/simulation/refinancing`), com `Idempotency-Key` automática."""
        response = self._executor.post("v2/proposal/simulation/refinancing", refinancing_request_to_wire(request))
        ApiRequestExecutor.ensure_success(response)

        return simulation_options_to_public(response.body)

    def get(self, simulation_id: Identifier) -> Simulation:
        """Consulta uma simulação (`GET v1/proposal/simulation/{id}`)."""
        response = self._executor.get(f"v1/proposal/simulation/{path_segment(simulation_id)}")
        ApiRequestExecutor.ensure_success(response)

        return simulation_to_public(as_dict(response.body, "a simulação"))

    def list(self, request: Optional[ListRequest] = None) -> PagedResult[Simulation]:
        """Lista as simulações do parceiro, paginadas (`GET v1/proposal/simulation`)."""
        request = request or ListRequest()

        path = paged_path("v1/proposal/simulation", request.page, request.page_size)
        response = self._executor.get(path)
        ApiRequestExecutor.ensure_success(response)

        return paged_result_from_wire(response.body, simulation_to_public)
