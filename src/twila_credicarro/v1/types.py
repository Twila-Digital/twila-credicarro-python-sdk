from dataclasses import dataclass

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
