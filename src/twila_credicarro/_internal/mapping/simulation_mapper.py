from typing import Any, Optional

from ...simulations.types import (
    CommissionReturn,
    CommissionReturnTarget,
    CommissionReturnType,
    CreateFinancingSimulationRequest,
    CreateRefinancingSimulationRequest,
    FinancingRangeOption,
    RefinancingRangeOption,
    Simulation,
    SimulationIof,
    SimulationOption,
    SimulationRates,
    SimulationTransaction,
    SimulationType,
    SimulationVehicle,
)
from ...v1.types import CreateFinancingSimulationV1Request, CreateRefinancingSimulationV1Request
from ..datetime_parsing import parse_iso_datetime
from .wire import (
    as_dict,
    as_list,
    opt_bool,
    opt_dict,
    opt_float,
    opt_int,
    opt_str,
    req_float,
    req_int,
    req_str,
)


def financing_request_to_wire(request: CreateFinancingSimulationRequest) -> dict[str, Any]:
    wire: dict[str, Any] = {
        "cpf": request.cpf,
        "placa": request.license_plate,
        "valorVeiculo": request.vehicle_amount,
        "valorEntrada": request.down_payment,
        "uf": request.state,
        "isVeiculoZeroKm": request.is_zero_km,
    }
    if request.commission_return is not None:
        wire["retornoComissao"] = request.commission_return
    wire["cnpjLoja"] = request.store_cnpj
    return wire


def refinancing_request_to_wire(request: CreateRefinancingSimulationRequest) -> dict[str, Any]:
    wire: dict[str, Any] = {
        "cpf": request.cpf,
        "placa": request.license_plate,
        "valorSolicitado": request.requested_amount,
    }
    if request.commission_return is not None:
        wire["retornoComissao"] = request.commission_return
    wire["cnpjLoja"] = request.store_cnpj
    return wire


def financing_v1_request_to_wire(request: CreateFinancingSimulationV1Request) -> dict[str, Any]:
    return {
        "cpf": request.cpf,
        "placa": request.license_plate,
        "valorVeiculo": request.vehicle_amount,
        "valorEntrada": request.down_payment,
        "uf": request.state,
        "isVeiculoZeroKm": request.is_zero_km,
    }


def refinancing_v1_request_to_wire(request: CreateRefinancingSimulationV1Request) -> dict[str, Any]:
    return {
        "cpf": request.cpf,
        "placa": request.license_plate,
        "valorSolicitado": request.requested_amount,
    }


def financing_range_to_public(wire: Any) -> list[FinancingRangeOption]:
    root = as_dict(wire, "a faixa de financiamento")
    return [
        FinancingRangeOption(
            term=req_int(item, "prazo"),
            minimum_down_payment=req_float(item, "valor_minimo_entrada"),
        )
        for item in _items(root, "opcoes_por_prazo")
    ]


def refinancing_range_to_public(wire: Any) -> list[RefinancingRangeOption]:
    root = as_dict(wire, "a faixa de refinanciamento")
    return [
        RefinancingRangeOption(
            term=req_int(item, "prazo"),
            minimum_amount=req_float(item, "valor_minimo_refinanciavel"),
            maximum_amount=req_float(item, "valor_maximo_refinanciavel"),
        )
        for item in _items(root, "opcoes_por_prazo")
    ]


def commission_returns_to_public(wire: Any) -> list[CommissionReturn]:
    root = as_dict(wire, "os retornos de comissão")
    return [
        CommissionReturn(
            type=CommissionReturnType.from_wire_name(opt_str(item, "tipo")),
            target=CommissionReturnTarget.from_wire_name(opt_str(item, "alvo")),
            minimum_return=req_int(item, "retorno_minimo"),
            maximum_return=req_int(item, "retorno_maximo"),
            allow_default_rate=bool(opt_bool(item, "permite_taxa_padrao")),
        )
        for item in _items(root, "retornos_comissao")
    ]


def simulation_options_to_public(wire: Any) -> list[SimulationOption]:
    root = as_dict(wire, "a resposta da simulação")
    return [_option_to_public(item) for item in _items(root, "simulacoes")]


def simulation_to_public(wire: dict[str, Any]) -> Simulation:
    type_name = opt_str(wire, "tipo")

    return Simulation(
        simulation_id=req_str(wire, "id_simulacao"),
        term=opt_int(wire, "prazo"),
        installment_amount=opt_float(wire, "valor_parcela"),
        requested_amount=opt_float(wire, "valor_solicitado"),
        down_payment=opt_float(wire, "valor_entrada"),
        asset_amount=opt_float(wire, "valor_bem"),
        tac_amount=opt_float(wire, "valor_tac"),
        negotiated_interest_rate=opt_float(wire, "taxa_juros_negociada"),
        registration_amount=opt_float(wire, "valor_registro"),
        state=opt_str(wire, "uf"),
        type=SimulationType.from_wire_name(type_name),
        type_name=type_name,
        transaction=_transaction(opt_dict(wire, "transacao")),
        interest=_rates(opt_dict(wire, "juros"), "percentual_juros_mensal", "percentual_juros_anual"),
        cet=_rates(opt_dict(wire, "cet"), "percentual_mensal", "percentual_anual"),
        iof=_iof(opt_dict(wire, "iof")),
        vehicle=_vehicle(opt_dict(wire, "veiculo")),
        customer_cpf=_customer_cpf(opt_dict(wire, "cliente")),
        created_at=parse_iso_datetime(wire.get("data_criacao")),
    )


def _items(root: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [as_dict(item, f"um item de '{key}'") for item in as_list(root.get(key), f"'{key}'")]


def _option_to_public(wire: dict[str, Any]) -> SimulationOption:
    return SimulationOption(
        simulation_id=req_str(wire, "id_simulacao"),
        requested_amount=req_float(wire, "valor_solicitado"),
        term=req_int(wire, "prazo"),
        installment_amount=req_float(wire, "valor_parcela"),
        tac_amount=req_float(wire, "valor_tac"),
        boleto_amount=req_float(wire, "valor_boleto"),
        insurance_amount=req_float(wire, "valor_seguro"),
        iof_amount=req_float(wire, "valor_iof"),
        iof_rate=req_float(wire, "percentual_iof"),
        total_credit_amount=req_float(wire, "valor_credito_total"),
        total_debt_amount=req_float(wire, "valor_divida_total"),
        monthly_cet=req_float(wire, "percentual_cet_mensal"),
        annual_cet=req_float(wire, "percentual_cet_anual"),
        monthly_interest_rate=req_float(wire, "percentual_juros_mensal"),
        annual_interest_rate=req_float(wire, "percentual_juros_anual"),
        approximate_daily_retention=opt_float(wire, "valor_retencao_diaria_aproximado"),
    )


def _transaction(wire: Optional[dict[str, Any]]) -> Optional[SimulationTransaction]:
    if wire is None:
        return None
    return SimulationTransaction(
        total_credit=opt_float(wire, "valor_total_credito"),
        total_debit=opt_float(wire, "valor_total_debito"),
    )


def _rates(wire: Optional[dict[str, Any]], monthly_key: str, annual_key: str) -> Optional[SimulationRates]:
    if wire is None:
        return None
    return SimulationRates(monthly_rate=opt_float(wire, monthly_key), annual_rate=opt_float(wire, annual_key))


def _iof(wire: Optional[dict[str, Any]]) -> Optional[SimulationIof]:
    if wire is None:
        return None
    return SimulationIof(amount=opt_float(wire, "valor"), rate=opt_float(wire, "percentual"))


def _vehicle(wire: Optional[dict[str, Any]]) -> Optional[SimulationVehicle]:
    if wire is None:
        return None
    return SimulationVehicle(
        brand=opt_str(wire, "marca"),
        model=opt_str(wire, "modelo"),
        version=opt_str(wire, "versao"),
        year=opt_int(wire, "ano"),
        value=opt_float(wire, "valor"),
        license_plate=opt_str(wire, "placa"),
        is_zero_km=opt_bool(wire, "veiculo_zero_km"),
        chassis=opt_str(wire, "chassi"),
        renavam=opt_str(wire, "renavam"),
        color=opt_str(wire, "cor"),
    )


def _customer_cpf(wire: Optional[dict[str, Any]]) -> Optional[str]:
    if wire is None:
        return None
    return opt_str(wire, "cpf")
