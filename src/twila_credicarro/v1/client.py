from .._internal.http.api_request_executor import ApiRequestExecutor
from .._internal.http.query_string import QueryStringBuilder
from .._internal.mapping.proposal_mapper import (
    create_proposal_request_to_wire,
    proposal_id_to_public,
    proposal_summary_to_public,
)
from .._internal.mapping.simulation_mapper import (
    financing_range_to_public,
    financing_v1_request_to_wire,
    refinancing_range_to_public,
    refinancing_v1_request_to_wire,
    simulation_options_to_public,
)
from .._internal.mapping.wire import as_dict
from .._internal.path import Identifier, path_segment
from ..proposals.types import CreateProposalRequest, ProposalSummary
from ..simulations.types import FinancingRangeOption, RefinancingRangeOption, SimulationOption
from .types import CreateFinancingSimulationV1Request, CreateRefinancingSimulationV1Request


class V1SimulationsClient:
    """Simulações da API v1: sem `cnpjLoja` (a loja é a de integração vinculada ao parceiro)."""

    def __init__(self, executor: ApiRequestExecutor) -> None:
        self._executor = executor

    def get_financing_range(self, license_plate: str) -> list[FinancingRangeOption]:
        path = QueryStringBuilder().add("placa", license_plate).build("v1/proposal/simulation/range/financing")
        response = self._executor.get(path)
        ApiRequestExecutor.ensure_success(response)

        return financing_range_to_public(response.body)

    def get_refinancing_range(self, license_plate: str) -> list[RefinancingRangeOption]:
        path = QueryStringBuilder().add("placa", license_plate).build("v1/proposal/simulation/range/refinancing")
        response = self._executor.get(path)
        ApiRequestExecutor.ensure_success(response)

        return refinancing_range_to_public(response.body)

    def create_financing(self, request: CreateFinancingSimulationV1Request) -> list[SimulationOption]:
        response = self._executor.post("v1/proposal/simulation/financing", financing_v1_request_to_wire(request))
        ApiRequestExecutor.ensure_success(response)

        return simulation_options_to_public(response.body)

    def create_refinancing(self, request: CreateRefinancingSimulationV1Request) -> list[SimulationOption]:
        response = self._executor.post("v1/proposal/simulation/refinancing", refinancing_v1_request_to_wire(request))
        ApiRequestExecutor.ensure_success(response)

        return simulation_options_to_public(response.body)


class V1ProposalsClient:
    """Propostas da API v1."""

    def __init__(self, executor: ApiRequestExecutor) -> None:
        self._executor = executor

    def create(self, request: CreateProposalRequest) -> str:
        """Cria a proposta (`POST v1/proposal`) e devolve o `id_proposta`."""
        response = self._executor.post("v1/proposal", create_proposal_request_to_wire(request))
        ApiRequestExecutor.ensure_success(response)

        return proposal_id_to_public(response.body)

    def get(self, proposal_id: Identifier) -> ProposalSummary:
        """Consulta a proposta (`GET v1/proposal/{id}`)."""
        response = self._executor.get(f"v1/proposal/{path_segment(proposal_id)}")
        ApiRequestExecutor.ensure_success(response)

        return proposal_summary_to_public(as_dict(response.body, "a proposta"))


class V1Client:
    def __init__(self, executor: ApiRequestExecutor) -> None:
        self.simulations = V1SimulationsClient(executor)
        self.proposals = V1ProposalsClient(executor)
