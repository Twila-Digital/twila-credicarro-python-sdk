from typing import Optional

from .._internal.http.api_request_executor import ApiRequestExecutor
from .._internal.http.query_string import paged_path
from .._internal.mapping.paged_mapper import paged_result_from_wire
from .._internal.mapping.proposal_mapper import (
    create_proposal_request_to_wire,
    deposit_account_to_wire,
    document_upload_to_wire,
    proposal_details_to_public,
    proposal_id_to_public,
    proposal_summary_to_public,
    vehicle_details_to_wire,
)
from .._internal.mapping.wire import as_dict
from .._internal.path import Identifier, path_segment
from ..paged_result import ListRequest, PagedResult
from .types import (
    CreateProposalRequest,
    DepositAccount,
    ProposalDetails,
    ProposalDocumentUpload,
    ProposalSummary,
    VehicleDetails,
)


class ProposalsClient:
    """Propostas da API v2. Para as rotas v1, veja `client.v1.proposals`."""

    def __init__(
        self, executor: ApiRequestExecutor, document_upload_attempt_timeout_ms: int, max_retry_attempts: int
    ) -> None:
        self._executor = executor
        self._document_upload_attempt_timeout_ms = document_upload_attempt_timeout_ms
        self._document_upload_total_timeout_ms = document_upload_attempt_timeout_ms * max(1, max_retry_attempts)

    def create(self, request: CreateProposalRequest) -> str:
        """Cria a proposta de uma simulação (`POST v2/proposal`) e devolve o `id_proposta`."""
        response = self._executor.post("v2/proposal", create_proposal_request_to_wire(request))
        ApiRequestExecutor.ensure_success(response)

        return proposal_id_to_public(response.body)

    def get(self, proposal_id: Identifier) -> ProposalDetails:
        """Consulta o retrato atual da proposta (`GET v2/proposal/{id}`)."""
        response = self._executor.get(f"v2/proposal/{path_segment(proposal_id)}")
        ApiRequestExecutor.ensure_success(response)

        return proposal_details_to_public(as_dict(response.body, "a proposta"))

    def send_vehicle_details(self, proposal_id: Identifier, details: VehicleDetails) -> None:
        """Envia os dados do veículo (`204`), aceitos na etapa `DADOS_VEICULO`. Pode ser repetido."""
        response = self._executor.post(
            f"v2/proposal/{path_segment(proposal_id)}/vehicle-detail", vehicle_details_to_wire(details)
        )
        ApiRequestExecutor.ensure_success(response)

    def send_deposit_account(self, proposal_id: Identifier, account: DepositAccount) -> None:
        """Envia a conta de recebimento de um refinanciamento (`204`). Enviar de novo substitui a conta."""
        response = self._executor.post(
            f"v2/proposal/{path_segment(proposal_id)}/deposit-account", deposit_account_to_wire(account)
        )
        ApiRequestExecutor.ensure_success(response)

    def upload_document(
        self,
        proposal_id: Identifier,
        upload: ProposalDocumentUpload,
        idempotency_key: Optional[str] = None,
    ) -> None:
        """Envia um documento (`204`), um arquivo por chamada.

        A `Idempotency-Key` é obrigatória na API. Recomenda-se gravar uma chave por envio no seu sistema e passá-la
        aqui; use uma chave NOVA ao reenviar um documento recusado. Sem `idempotency_key`, o SDK gera uma e a
        reaproveita em todas as tentativas desta chamada.
        """
        response = self._executor.post(
            f"v2/proposal/{path_segment(proposal_id)}/document",
            document_upload_to_wire(upload),
            attempt_timeout_ms=self._document_upload_attempt_timeout_ms,
            idempotency_key=idempotency_key,
            total_timeout_ms=self._document_upload_total_timeout_ms,
        )
        ApiRequestExecutor.ensure_success(response)

    def list(self, request: Optional[ListRequest] = None) -> PagedResult[ProposalSummary]:
        """Lista as propostas do parceiro, paginadas (`GET v1/proposal`)."""
        request = request or ListRequest()

        path = paged_path("v1/proposal", request.page, request.page_size)
        response = self._executor.get(path)
        ApiRequestExecutor.ensure_success(response)

        return paged_result_from_wire(response.body, proposal_summary_to_public)
