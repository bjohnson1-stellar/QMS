"""
Refrigeration Engineering Calculations Library
=============================================

A comprehensive Python library for industrial refrigeration calculations,
extracted from professional engineering spreadsheets.

Modules:
--------
- properties: Thermodynamic properties for NH3, CO2, R22, R404a, R449A, R507
- line_sizing: Pipe sizing for suction, discharge, and liquid lines
- charge: Refrigerant charge calculations for vessels, coils, and piping
- ventilation: Machine room ventilation calculations per IIAR/ASHRAE
- release: Ammonia release calculations per IIAR, EPA, NFPA methods
- loads: Refrigeration load calculations for cold storage
- evaporator: Evaporator selection and sizing
- condenser: Condenser selection and sizing
- expansion: Expansion device sizing (TXV, EEV, float valves)
- glycol: Secondary coolant properties and system sizing
- relief_valve: Pressure relief valve sizing per ASME/IIAR
- pumps: Pump sizing for refrigerant and glycol systems
- utils: Common utilities and unit conversions

Author: Extracted from professional refrigeration engineering tools
"""

from .properties import (
    RefrigerantProperties, 
    NH3Properties,
    CO2Properties,
    R22Properties,
    R404aProperties,
    R449AProperties,
    R507Properties,
    SaturationProperties,
    get_refrigerant,
)
from .line_sizing import (
    LineSizing,
    LineSizingResult,
    PipeData,
    PipeSchedule,
    PIPE_DATA,
    STANDARD_SIZES,
    FITTING_EQ_LENGTH,
    calculate_velocity,
)
from .charge import (
    ChargeCalculator,
    ChargeResult,
    VesselDimensions,
    VesselOrientation,
    CoilType,
    HeadType,
    calculate_system_charge,
)
from .ventilation import (
    MachineRoomVentilation,
    VentilationResult,
    VentilationStandard,
    RoomDimensions,
    WallConstruction,
    RoomType,
    iiar_emergency_exhaust,
    air_changes_per_hour,
)
from .release import (
    NH3ReleaseCalculator,
    ReleaseResult,
    ReleaseType,
    ReleaseMethod,
    quick_release_rate,
)
from .loads import (
    RefrigerationLoadCalculator,
    BlastFreezerCalculator,
    LoadResult,
    RoomDimensions as LoadRoomDimensions,
    ProductType,
    ProductProperties,
    PRODUCT_DATA,
    quick_load_estimate,
)
from .evaporator import (
    EvaporatorCalculator,
    EvaporatorResult,
    EvaporatorType,
    DefrostType,
    FinSpacing,
    quick_evaporator_sizing,
)
from .condenser import (
    CondenserCalculator,
    CondenserResult,
    CondenserType,
    quick_heat_rejection,
    condenser_tons_to_mbh,
    mbh_to_condenser_tons,
)
from .expansion import (
    ExpansionDeviceCalculator,
    ExpansionValveResult,
    ExpansionDeviceType,
    RefrigerantType,
    quick_txv_size,
)
from .glycol import (
    SecondaryRefrigerantCalculator,
    CoolantProperties,
    CoolantType,
    GlycolSystemResult,
    freeze_point,
    glycol_concentration_for_temp,
)
from .relief_valve import (
    ReliefValveSizer,
    ReliefValveResult,
    ReliefScenario,
    RefrigerantRelief,
    quick_vessel_relief,
)
from .pumps import (
    PumpCalculator,
    PumpResult,
    PumpType,
    FluidType,
    SystemCurvePoint,
    quick_pump_hp,
    recirculation_flow,
)
from . import utils

__version__ = "2.0.0"
__all__ = [
    # Properties
    'RefrigerantProperties',
    'NH3Properties',
    'CO2Properties',
    'R22Properties',
    'R404aProperties',
    'R449AProperties',
    'R507Properties',
    'SaturationProperties',
    'get_refrigerant',
    # Line Sizing
    'LineSizing',
    'LineSizingResult',
    'PipeData',
    'PipeSchedule',
    'PIPE_DATA',
    'STANDARD_SIZES',
    'FITTING_EQ_LENGTH',
    'calculate_velocity',
    # Charge
    'ChargeCalculator',
    'ChargeResult',
    'VesselDimensions',
    'VesselOrientation',
    'CoilType',
    'HeadType',
    'calculate_system_charge',
    # Ventilation
    'MachineRoomVentilation',
    'VentilationResult',
    'VentilationStandard',
    'RoomDimensions',
    'WallConstruction',
    'RoomType',
    'iiar_emergency_exhaust',
    'air_changes_per_hour',
    # Release
    'NH3ReleaseCalculator',
    'ReleaseResult',
    'ReleaseType',
    'ReleaseMethod',
    'quick_release_rate',
    # Loads
    'RefrigerationLoadCalculator',
    'BlastFreezerCalculator',
    'LoadResult',
    'LoadRoomDimensions',
    'ProductType',
    'ProductProperties',
    'PRODUCT_DATA',
    'quick_load_estimate',
    # Evaporator
    'EvaporatorCalculator',
    'EvaporatorResult',
    'EvaporatorType',
    'DefrostType',
    'FinSpacing',
    'quick_evaporator_sizing',
    # Condenser
    'CondenserCalculator',
    'CondenserResult',
    'CondenserType',
    'quick_heat_rejection',
    'condenser_tons_to_mbh',
    'mbh_to_condenser_tons',
    # Expansion Devices
    'ExpansionDeviceCalculator',
    'ExpansionValveResult',
    'ExpansionDeviceType',
    'RefrigerantType',
    'quick_txv_size',
    # Glycol/Brine
    'SecondaryRefrigerantCalculator',
    'CoolantProperties',
    'CoolantType',
    'GlycolSystemResult',
    'freeze_point',
    'glycol_concentration_for_temp',
    # Relief Valves
    'ReliefValveSizer',
    'ReliefValveResult',
    'ReliefScenario',
    'RefrigerantRelief',
    'quick_vessel_relief',
    # Pumps
    'PumpCalculator',
    'PumpResult',
    'PumpType',
    'FluidType',
    'SystemCurvePoint',
    'quick_pump_hp',
    'recirculation_flow',
    # Utils
    'utils',
]
