from dataclasses import dataclass
from datetime import date, datetime
from enum import IntEnum
from typing import Optional, Union

from .._internal.datetime_parsing import to_iso_string
from .._internal.enum_support import build_name_table, enum_from_name, enum_from_value
from .._internal.masking import masked_repr

DateLike = Union[str, date, datetime]

__all__ = [
    "CreateCustomerRequest",
    "CustomerAddress",
    "DateLike",
    "OccupationType",
    "ProfessionalData",
    "UpsertCustomerRequest",
    "to_iso_string",
]


class OccupationType(IntEnum):
    """`tipoOcupacao`."""

    RETIRED = 1
    PENSIONER = 2
    EMPLOYEE = 3
    SELF_EMPLOYED = 4
    FREELANCER = 6
    BUSINESS_OWNER = 7
    UNKNOWN = -1

    @classmethod
    def from_wire_value(cls, value: object) -> "OccupationType":
        return enum_from_value(cls, value, cls.UNKNOWN)

    @classmethod
    def from_wire_name(cls, value: object) -> "OccupationType":
        return enum_from_name(_OCCUPATION_NAMES, value, cls.UNKNOWN)


_OCCUPATION_NAMES = build_name_table(OccupationType)


@masked_repr(secret=("street", "number", "complement", "neighborhood", "city", "state", "postal_code"))
@dataclass(frozen=True)
class CustomerAddress:
    """`endereco`. `number` e `complement` são opcionais."""

    street: str
    neighborhood: str
    city: str
    state: str
    postal_code: str
    number: Optional[str] = None
    complement: Optional[str] = None


@masked_repr(secret=("monthly_income",))
@dataclass(frozen=True)
class ProfessionalData:
    """`dadosProfissionais`: ocupação e renda mensal em reais."""

    occupation: OccupationType
    monthly_income: float


@masked_repr(cpf=("cpf",), secret=("first_name", "last_name", "email", "phone_number", "date_of_birth"))
@dataclass(frozen=True)
class CreateCustomerRequest:
    """Dados pessoais. `phone_number` no formato `+55 (DD) 99999-9999`; `date_of_birth` ISO-8601 com offset."""

    cpf: str
    first_name: str
    last_name: str
    email: str
    phone_number: str
    date_of_birth: DateLike


@masked_repr(cpf=("cpf",), secret=("first_name", "last_name", "email", "phone_number", "date_of_birth"))
@dataclass(frozen=True)
class UpsertCustomerRequest:
    """Cadastro completo (`POST v1/customer/unified`)."""

    cpf: str
    first_name: str
    last_name: str
    email: str
    phone_number: str
    date_of_birth: DateLike
    address: CustomerAddress
    professional_data: ProfessionalData
