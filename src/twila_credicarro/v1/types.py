from dataclasses import dataclass
from typing import Optional

from .._internal.masking import masked_repr


@masked_repr(cpf=("cpf",), secret=("license_plate",))
@dataclass(frozen=True)
class CreateFinancingSimulationV1Request:
    """`POST v1/proposal/simulation/financing`: a loja é a vinculada ao parceiro (sem `cnpjLoja`)."""

    cpf: str
    license_plate: str
    vehicle_amount: float
    down_payment: float
    state: str
    is_zero_km: bool


@masked_repr(cpf=("cpf",), secret=("license_plate",))
@dataclass(frozen=True)
class CreateRefinancingSimulationV1Request:
    """`POST v1/proposal/simulation/refinancing`: a loja é a vinculada ao parceiro (sem `cnpjLoja`)."""

    cpf: str
    license_plate: str
    requested_amount: float


@masked_repr(secret=("license_plate",))
@dataclass(frozen=True)
class CreateFinancingWithoutCpfRequest:
    """`POST v1/proposal/simulation/financing/without-cpf`: sem CPF e sem cadastro de cliente.

    `down_payment` é opcional: omitido, não vai no JSON e a API usa a entrada mínima da taxa da loja.
    """

    license_plate: str
    vehicle_amount: float
    state: str
    down_payment: Optional[float] = None


@dataclass(frozen=True)
class FinancingWithoutCpfOption:
    """Uma opção (um prazo) da simulação sem CPF. Nada é gravado: não há `simulation_id` e não cria proposta."""

    requested_amount: float
    term: int
    installment_amount: float
    tac_amount: float
    boleto_amount: float
    insurance_amount: float
    iof_amount: float
    iof_rate: float
    total_credit_amount: float
    total_debt_amount: float
    monthly_cet: float
    annual_cet: float
    monthly_interest_rate: float
    annual_interest_rate: float
    minimum_down_payment: float
    approximate_daily_retention: Optional[float] = None


@masked_repr(secret=("license_plate",))
@dataclass(frozen=True)
class CreateRefinancingWithoutCpfRequest:
    """`POST v1/proposal/simulation/refinancing/without-cpf`: sem CPF e sem cadastro de cliente.

    A `state` é obrigatória: define as taxas e o custo de registro.
    """

    license_plate: str
    requested_amount: float
    state: str


@dataclass(frozen=True)
class RefinancingWithoutCpfOption:
    """Uma opção (um prazo) da simulação de refinanciamento sem CPF.

    Nada é gravado: não há `simulation_id` e não cria proposta.
    """

    requested_amount: float
    term: int
    installment_amount: float
    tac_amount: float
    boleto_amount: float
    insurance_amount: float
    iof_amount: float
    iof_rate: float
    total_credit_amount: float
    total_debt_amount: float
    monthly_cet: float
    annual_cet: float
    monthly_interest_rate: float
    annual_interest_rate: float
    minimum_amount: float
    maximum_amount: float
    approximate_daily_retention: Optional[float] = None
