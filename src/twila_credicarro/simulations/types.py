from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Optional

from .._internal.enum_support import build_name_table, enum_from_name, enum_from_value
from .._internal.masking import masked_repr


class SimulationType(IntEnum):
    """`tipo` da simulação (por nome: `Financing`, `Refinancing`, `AmountSimulation`)."""

    FINANCING = 1
    REFINANCING = 2
    AMOUNT_SIMULATION = 3
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "SimulationType":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "SimulationType":
        return enum_from_name(_SIMULATION_TYPE_NAMES, value, cls.UNKNOWN)


_SIMULATION_TYPE_NAMES = build_name_table(SimulationType)


@dataclass(frozen=True)
class FinancingRangeOption:
    """Entrada mínima para um prazo (`opcoes_por_prazo`)."""

    term: int
    minimum_down_payment: float


@dataclass(frozen=True)
class RefinancingRangeOption:
    """Faixa refinanciável para um prazo (`opcoes_por_prazo`)."""

    term: int
    minimum_amount: float
    maximum_amount: float


@masked_repr(cpf=("cpf",), secret=("license_plate",))
@dataclass(frozen=True)
class CreateFinancingSimulationRequest:
    """`POST v2/proposal/simulation/financing`. O cliente precisa estar cadastrado antes.

    `commission_return` (`retornoComissao`) é opcional; quando enviado, precisa estar na faixa `Financing` da loja
    (veja `get_commission_returns`).
    """

    cpf: str
    license_plate: str
    vehicle_amount: float
    down_payment: float
    state: str
    is_zero_km: bool
    store_cnpj: str
    commission_return: Optional[int] = None


@masked_repr(cpf=("cpf",), secret=("license_plate",))
@dataclass(frozen=True)
class CreateRefinancingSimulationRequest:
    """`POST v2/proposal/simulation/refinancing`. O valor precisa estar na faixa refinanciável da placa.

    `commission_return` (`retornoComissao`) é opcional; quando enviado, precisa estar na faixa `Refinancing` da loja
    (veja `get_commission_returns`).
    """

    cpf: str
    license_plate: str
    requested_amount: float
    store_cnpj: str
    commission_return: Optional[int] = None


class CommissionReturnTarget(IntEnum):
    """A quem a faixa de retorno de comissão se aplica (`alvo`: `Store` ou `Organization`)."""

    STORE = 1
    ORGANIZATION = 2
    UNKNOWN = -1

    @classmethod
    def from_wire_name(cls, value: object) -> "CommissionReturnTarget":
        return enum_from_name(_COMMISSION_RETURN_TARGET_NAMES, value, cls.UNKNOWN)


_COMMISSION_RETURN_TARGET_NAMES = build_name_table(CommissionReturnTarget)


@dataclass(frozen=True)
class CommissionReturn:
    """Faixa de retorno de comissão da loja. A simulação valida pela faixa com `target` `STORE`."""

    type: SimulationType
    target: CommissionReturnTarget
    minimum_return: int
    maximum_return: int
    allows_default_rate: bool


@dataclass(frozen=True)
class SimulationOption:
    """Uma opção (um prazo) de simulação. Use `simulation_id` ao criar a proposta."""

    simulation_id: str
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
    approximate_daily_retention: Optional[float] = None


@dataclass(frozen=True)
class SimulationTransaction:
    total_credit: Optional[float] = None
    total_debit: Optional[float] = None


@dataclass(frozen=True)
class SimulationRates:
    """Taxa mensal e anual (`juros` e `cet`)."""

    monthly_rate: Optional[float] = None
    annual_rate: Optional[float] = None


@dataclass(frozen=True)
class SimulationIof:
    amount: Optional[float] = None
    rate: Optional[float] = None


@masked_repr(secret=("license_plate",))
@dataclass(frozen=True)
class SimulationVehicle:
    brand: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    year: Optional[int] = None
    value: Optional[float] = None
    license_plate: Optional[str] = None
    is_zero_km: Optional[bool] = None
    chassis: Optional[str] = None
    renavam: Optional[str] = None
    color: Optional[str] = None


@masked_repr(cpf=("customer_cpf",))
@dataclass(frozen=True)
class Simulation:
    """Simulação consultada (`SimulationResponse`)."""

    simulation_id: str
    term: Optional[int] = None
    installment_amount: Optional[float] = None
    requested_amount: Optional[float] = None
    down_payment: Optional[float] = None
    asset_amount: Optional[float] = None
    tac_amount: Optional[float] = None
    negotiated_interest_rate: Optional[float] = None
    registration_amount: Optional[float] = None
    state: Optional[str] = None
    type: SimulationType = SimulationType.UNKNOWN
    type_name: Optional[str] = None
    transaction: Optional[SimulationTransaction] = None
    interest: Optional[SimulationRates] = None
    cet: Optional[SimulationRates] = None
    iof: Optional[SimulationIof] = None
    vehicle: Optional[SimulationVehicle] = None
    customer_cpf: Optional[str] = None
    created_at: Optional[datetime] = None
