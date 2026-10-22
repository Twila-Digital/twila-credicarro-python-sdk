"""Sample standalone: do cadastro do cliente à proposta, sem framework.

Variáveis de ambiente: CREDICARRO_CLIENT_ID, CREDICARRO_CLIENT_SECRET e CREDICARRO_STORE_CNPJ.
"""

import os

from twila_credicarro import (
    CreateFinancingSimulationRequest,
    CreateProposalRequest,
    CredicarroApiError,
    CredicarroClient,
    CredicarroClientOptions,
    CredicarroEnvironment,
    CustomerAddress,
    OccupationType,
    ProfessionalData,
    UpsertCustomerRequest,
)


def main() -> None:
    with CredicarroClient(
        CredicarroClientOptions(
            client_id=os.environ["CREDICARRO_CLIENT_ID"],
            client_secret=os.environ["CREDICARRO_CLIENT_SECRET"],
            environment=CredicarroEnvironment.STAGING,
        )
    ) as client:
        cpf = "12345678909"

        client.customers.upsert(
            UpsertCustomerRequest(
                cpf=cpf,
                first_name="Maria",
                last_name="Souza",
                email="maria.souza@exemplo.com.br",
                phone_number="+55 (11) 99876-5432",
                date_of_birth="1990-05-20T00:00:00-03:00",
                address=CustomerAddress(
                    street="Av. Paulista",
                    number="1578",
                    neighborhood="Bela Vista",
                    city="São Paulo",
                    state="SP",
                    postal_code="01311000",
                ),
                professional_data=ProfessionalData(occupation=OccupationType.EMPLOYEE, monthly_income=6500.0),
            )
        )

        try:
            opcoes = client.simulations.create_financing(
                CreateFinancingSimulationRequest(
                    cpf=cpf,
                    license_plate="ABC1D23",
                    vehicle_amount=45000,
                    down_payment=9000,
                    state="SP",
                    is_zero_km=False,
                    store_cnpj=os.environ["CREDICARRO_STORE_CNPJ"],
                )
            )
        except CredicarroApiError as error:
            print(f"Simulação recusada ({error.status_code} {error.error_code}): {error}")
            return

        for opcao in opcoes:
            print(f"{opcao.term}x de {opcao.installment_amount} (CET a.m. {opcao.monthly_cet}%)")

        proposal_id = client.proposals.create(CreateProposalRequest(cpf=cpf, simulation_id=opcoes[0].simulation_id))
        proposta = client.proposals.get(proposal_id)

        print(f"Proposta {proposta.number}: {proposta.status.name}")
        for acao in proposta.get_pending_actions():
            print(f"  - {acao.participant.value}: {acao.kind.value} {[tipo.name for tipo in acao.document_types]}")


if __name__ == "__main__":
    main()
