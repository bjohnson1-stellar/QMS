"""
Refrigeration Discipline Calculator

Implements DisciplineCalculator for industrial refrigeration calculations.
Wraps refrig_calc library modules for line sizing, relief valves, pumps,
ventilation, and charge calculations.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

from qms.engineering.base import DisciplineCalculator, CalculationResult
from qms.engineering.refrig_calc import (
    LineSizing,
    LineSizingResult,
    ReliefValveSizer,
    RefrigerantRelief,
    ReliefScenario,
    PumpCalculator,
    MachineRoomVentilation,
    RoomDimensions,
    VentilationStandard,
    ChargeCalculator,
    VesselDimensions,
    VesselOrientation,
    get_refrigerant,
)


@dataclass
class RefrigerationResult(CalculationResult):
    """Extended calculation result with refrigeration-specific output data."""

    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        # Flatten data into top-level for convenience
        d.update(self.data)
        return d


# ---------------------------------------------------------------------------
# Module-level run_*() functions (used by CLI and validators directly)
# ---------------------------------------------------------------------------

def run_line_sizing(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run line sizing calculation.

    Params:
        capacity_tons: Refrigeration capacity (tons)
        suction_temp: Suction temperature (F)
        condensing_temp: Condensing temperature (F)
        length: Pipe length (ft)
        line_type: 'dry', 'wet', 'liquid', 'discharge'
        refrigerant: Refrigerant name
        num_90_elbows: Number of 90-degree elbows
        num_45_elbows: Number of 45-degree elbows
        num_tees: Number of tees
        num_valves: Number of valves
        recirculation_rate: Recirculation rate

    Returns:
        Dict with sizing results.
    """
    refrigerant = params.get('refrigerant', 'NH3')
    sizer = LineSizing(refrigerant)

    capacity = params.get('capacity_tons', 100)
    suction_temp = params.get('suction_temp', 28)
    condensing_temp = params.get('condensing_temp', 95)
    length = params.get('length', 100)
    line_type = params.get('line_type', 'dry')
    num_90 = params.get('num_90_elbows', 0)
    num_45 = params.get('num_45_elbows', 0)
    num_tees = params.get('num_tees', 0)
    num_valves = params.get('num_valves', 0)
    recirc = params.get('recirculation_rate', 1.0)

    if line_type in ('dry', 'wet'):
        result = sizer.size_suction_line(
            capacity_tons=capacity,
            suction_temp=suction_temp,
            condensing_temp=condensing_temp,
            total_length=length,
            num_90_elbows=num_90,
            num_45_elbows=num_45,
            num_tees=num_tees,
            num_valves=num_valves,
            recirculation_rate=recirc,
            line_type=line_type,
        )
    elif line_type == 'discharge':
        result = sizer.size_discharge_line(
            capacity_tons=capacity,
            discharge_temp=suction_temp + 100,  # Approximate superheat
            condensing_temp=condensing_temp,
            total_length=length,
            num_90_elbows=num_90,
            num_45_elbows=num_45,
            num_tees=num_tees,
            num_valves=num_valves,
        )
    else:  # liquid
        result = sizer.size_liquid_line(
            capacity_tons=capacity,
            liquid_temp=condensing_temp - 10,  # Subcooled
            condensing_temp=condensing_temp,
            total_length=length,
            num_90_elbows=num_90,
            num_45_elbows=num_45,
            num_tees=num_tees,
            num_valves=num_valves,
            recirculation_rate=recirc,
        )

    return asdict(result)


def run_relief_valve(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run relief valve sizing calculation.

    Params:
        volume_cuft: Vessel volume (ft3)
        set_pressure_psig: Set pressure (psig)
        refrigerant: Refrigerant name
        vessel_diameter_in: Vessel diameter (optional)
        vessel_length_in: Vessel length (optional)
        insulation: Insulation type

    Returns:
        Dict with relief valve sizing results.
    """
    sizer = ReliefValveSizer()

    refrig_map = {
        'NH3': RefrigerantRelief.NH3,
        'R22': RefrigerantRelief.R22,
        'R404A': RefrigerantRelief.R404A,
        'R507': RefrigerantRelief.R507,
        'CO2': RefrigerantRelief.CO2,
    }
    refrigerant = params.get('refrigerant', 'NH3').upper()
    refrig_enum = refrig_map.get(refrigerant, RefrigerantRelief.NH3)

    result = sizer.size_vessel_relief(
        vessel_volume_cuft=params.get('volume_cuft', 100),
        refrigerant=refrig_enum,
        set_pressure_psig=params.get('set_pressure_psig', 250),
        vessel_diameter_in=params.get('vessel_diameter_in'),
        vessel_length_in=params.get('vessel_length_in'),
        insulation=params.get('insulation', 'bare'),
    )

    return asdict(result)


def run_pump(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run pump sizing calculation.

    Params:
        capacity_tons: Refrigeration capacity (tons)
        recirculation_rate: Recirculation rate
        suction_temp: Suction temperature (F)
        static_head_ft: Static head (ft)
        pipe_length_ft: Pipe length (ft)

    Returns:
        Dict with pump sizing results.
    """
    calc = PumpCalculator()

    result = calc.size_recirculation_pump(
        capacity_tons=params.get('capacity_tons', 100),
        recirculation_rate=params.get('recirculation_rate', 4.0),
        suction_temp=params.get('suction_temp', 28),
        static_head_ft=params.get('static_head_ft', 10),
        pipe_length_ft=params.get('pipe_length_ft', 100),
    )

    return asdict(result)


def run_ventilation(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run machine room ventilation calculation.

    Params:
        length_ft: Room length (ft)
        width_ft: Room width (ft)
        height_ft: Room height (ft)
        refrigerant_charge_lb: Refrigerant charge (lb)
        standard: 'iiar' or 'ashrae'

    Returns:
        Dict with ventilation requirements.
    """
    room = RoomDimensions(
        length=params.get('length_ft', 30),
        width=params.get('width_ft', 20),
        height=params.get('height_ft', 12),
    )

    standard = params.get('standard', 'iiar').lower()
    if standard == 'ashrae':
        std = VentilationStandard.ASHRAE_15
    else:
        std = VentilationStandard.IIAR_2

    calc = MachineRoomVentilation(standard=std)

    result = calc.calculate(
        room=room,
        system_charge=params.get('refrigerant_charge_lb', 1000),
    )

    return asdict(result)


def run_charge(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run refrigerant charge calculation.

    Params:
        volume_cuft: Component volume (ft3)
        component_type: 'vessel', 'coil', 'piping'
        refrigerant: Refrigerant name
        temperature: Operating temperature (F)
        liquid_percent: Liquid fill percentage

    Returns:
        Dict with charge calculation results.
    """
    refrigerant = params.get('refrigerant', 'NH3')
    refrig_props = get_refrigerant(refrigerant)

    volume = params.get('volume_cuft', 10)
    temp = params.get('temperature', 28)
    liquid_pct = params.get('liquid_percent', 80) / 100.0
    component_type = params.get('component_type', 'vessel')

    # Get properties for calculation
    props = refrig_props.get_properties_at_temp(temp)
    liquid_vol = volume * liquid_pct
    vapor_vol = volume * (1 - liquid_pct)

    liquid_charge = liquid_vol * props.liquid_density
    vapor_charge = vapor_vol * props.vapor_density
    total = liquid_charge + vapor_charge

    return {
        'total_charge_lb': total,
        'liquid_charge_lb': liquid_charge,
        'vapor_charge_lb': vapor_charge,
        'volume_cuft': volume,
        'temperature_f': temp,
        'liquid_percent': liquid_pct * 100,
        'component_type': component_type,
        'refrigerant': refrigerant,
    }


# ---------------------------------------------------------------------------
# DisciplineCalculator implementation
# ---------------------------------------------------------------------------

_CALC_DISPATCH = {
    'line-sizing': run_line_sizing,
    'relief-valve': run_relief_valve,
    'pump': run_pump,
    'ventilation': run_ventilation,
    'charge': run_charge,
}


class RefrigerationCalculator(DisciplineCalculator):
    """Refrigeration discipline calculator implementing the DisciplineCalculator ABC."""

    @property
    def discipline_name(self) -> str:
        return "refrigeration"

    def available_calculations(self) -> List[str]:
        return list(_CALC_DISPATCH.keys())

    def run_calculation(
        self, calculation_type: str, params: Dict[str, Any]
    ) -> CalculationResult:
        """
        Dispatch to the appropriate run_*() function.

        Args:
            calculation_type: One of 'line-sizing', 'relief-valve', 'pump',
                              'ventilation', 'charge'.
            params: Input parameters dict.

        Returns:
            RefrigerationResult with data populated.

        Raises:
            ValueError: If calculation_type is unknown.
        """
        func = _CALC_DISPATCH.get(calculation_type)
        if func is None:
            raise ValueError(
                f"Unknown calculation type: {calculation_type}. "
                f"Available: {', '.join(self.available_calculations())}"
            )

        data = func(params)

        return RefrigerationResult(
            calculation_type=calculation_type,
            data=data,
        )
