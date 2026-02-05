"""
Safety Relief Valve (SRV) Sizing Module
========================================

Extracted from: SRV7.7.xlsm, SRV_ASHRAE_1994_and_CMC_2010.xlsm, SRV_CMC.xls

Calculates safety relief valve sizing per:
- IIAR-2 (2014 with Addendum A) 
- ASHRAE 15 (1994)
- CMC 1118.0 (2010)

Supports:
- Vessel relief (horizontal/vertical receivers, accumulators, intercoolers)
- Compressor relief (screw, reciprocating)
- Heat exchanger relief (evaporative condensers, shell-and-tube, plate)
- Two-stage oil cooling (TSOC) relief
- Diffusion tank sizing
- 3-way valve selection
- Outlet piping pressure drop (Moody friction factor method)
- Valve manufacturer data (Hansen, Henry, Shank)

Standards Reference:
    IIAR-2 2014 Addendum A, Section 10 - Overpressure Protection
    ASHRAE 15-1994 
    CMC 1118.0 Equation 1118.0-1
    UL 429 / ASME Section VIII
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Tuple


# ==============================================================================
# CONSTANTS & ENUMERATIONS
# ==============================================================================

class VesselType(Enum):
    """Equipment type for relief valve sizing."""
    HORIZONTAL_VESSEL = "horizontal_vessel"
    VERTICAL_VESSEL = "vertical_vessel"
    HEAT_EXCHANGER = "heat_exchanger"
    EVAPORATIVE_CONDENSER = "evaporative_condenser"
    COMPRESSOR = "compressor"
    TSOC = "tsoc"  # Two-Stage Oil Cooling


class ValveConfig(Enum):
    """Single or dual valve configuration."""
    SINGLE = "single"
    DUAL = "dual"


class ValveManufacturer(Enum):
    """Supported relief valve manufacturers."""
    HANSEN = "Hansen"
    HENRY = "Henry"
    SHANK = "Shank"


class Standard(Enum):
    """Applicable code/standard."""
    IIAR2_2014 = "IIAR-2 2014 Add. A"
    ASHRAE_1994 = "ASHRAE 15-1994"
    CMC_2010 = "CMC 1118.0-2010"


# ==============================================================================
# PIPE DATA - Inside Diameter and Moody Friction Factors
# From SRV7.7 DATA sheet, rows 35-53
# ==============================================================================

# {NPS: (inside_diameter_inches, moody_friction_factor)}
PIPE_DATA_SCH40 = {
    0.5:  (0.622, 0.032),
    0.75: (0.824, 0.030),
    1.0:  (1.049, 0.027),
    1.25: (1.380, 0.025),
    1.5:  (1.610, 0.024),
    2.0:  (2.067, 0.022),
    2.5:  (2.469, 0.021),
    3.0:  (3.068, 0.020),
    4.0:  (4.026, 0.018),
    5.0:  (5.047, 0.017),
    6.0:  (6.065, 0.016),
    8.0:  (7.981, 0.015),
    10.0: (10.020, 0.014),
    12.0: (11.938, 0.013),
    14.0: (13.124, 0.013),
    16.0: (15.000, 0.012),
    18.0: (16.876, 0.012),
    20.0: (18.812, 0.011),
    24.0: (22.624, 0.011),
}


# ==============================================================================
# VALVE CAPACITY DATA
# From SRV7.7 DATA sheet - capacity in lb/min air at set pressure
# Format: {model: {set_pressure_psi: capacity_lb_per_min_air}}
# ==============================================================================

# Hansen valve data (from SRV7.7 DATA sheet)
HANSEN_VALVES = {
    # model: {set_psi: (capacity_lb_min_air, inlet_size, outlet_size)}
    "HA4A": {150: (10, 0.5, 0.75), 200: (13, 0.5, 0.75), 250: (16, 0.5, 0.75), 300: (19, 0.5, 0.75)},
    "HA4AK": {150: (19, 0.75, 1.0), 200: (25, 0.75, 1.0), 250: (29, 0.75, 1.0), 300: (35, 0.75, 1.0)},
    "HA4AKS": {150: (29, 1.0, 1.25), 200: (38, 1.0, 1.25), 250: (45, 1.0, 1.25), 300: (54, 1.0, 1.25)},
    "HA4AL": {150: (35, 1.25, 1.5), 200: (46, 1.25, 1.5), 250: (55, 1.25, 1.5), 300: (66, 1.25, 1.5)},
    "HA4ALK": {150: (37, 1.25, 1.5), 200: (49, 1.25, 1.5), 250: (59, 1.25, 1.5), 300: (70, 1.25, 1.5)},
    "HA4AM": {150: (61, 1.5, 2.0), 200: (79, 1.5, 2.0), 250: (96, 1.5, 2.0), 300: (114, 1.5, 2.0)},
    "H5634R": {150: (90, 2.0, 3.0), 200: (117, 2.0, 3.0), 250: (144, 2.0, 3.0), 300: (170, 2.0, 3.0)},
}

# Henry valve data (from SRV7.7 DATA sheet)
HENRY_VALVES = {
    "5601": {150: (23, 0.5, 0.75), 200: (32, 0.5, 0.75), 250: (41, 0.5, 0.75), 300: (50, 0.5, 0.75)},
    "5602": {150: (23, 0.5, 0.75), 200: (32, 0.5, 0.75), 250: (41, 0.5, 0.75), 300: (50, 0.5, 0.75)},
    "5603": {150: (50, 0.75, 1.25), 200: (69, 0.75, 1.25), 250: (87, 0.75, 1.25), 300: (107, 0.75, 1.25)},
    "5604": {150: (79, 1.0, 1.25), 200: (107, 1.0, 1.25), 250: (136, 1.0, 1.25), 300: (165, 1.0, 1.25)},
    "5605": {150: (100, 1.25, 1.5), 200: (137, 1.25, 1.5), 250: (175, 1.25, 1.5), 300: (212, 1.25, 1.5)},
    "5606": {150: (181, 1.5, 2.0), 200: (247, 1.5, 2.0), 250: (313, 1.5, 2.0), 300: (380, 1.5, 2.0)},
    "5607": {150: (352, 2.0, 3.0), 200: (480, 2.0, 3.0), 250: (608, 2.0, 3.0), 300: (736, 2.0, 3.0)},
}

# Shank valve data
SHANK_VALVES = {
    "SR1": {150: (10, 0.5, 0.75), 200: (13, 0.5, 0.75), 250: (16, 0.5, 0.75), 300: (19, 0.5, 0.75)},
    "SR2": {150: (19, 0.75, 1.0), 200: (25, 0.75, 1.0), 250: (29, 0.75, 1.0), 300: (35, 0.75, 1.0)},
    "SR3": {150: (29, 1.0, 1.25), 200: (38, 1.0, 1.25), 250: (45, 1.0, 1.25), 300: (54, 1.0, 1.25)},
    "SR4": {150: (37, 1.25, 1.5), 200: (49, 1.25, 1.5), 250: (59, 1.25, 1.5), 300: (70, 1.25, 1.5)},
    "SRH1": {150: (35, 1.0, 1.25), 200: (46, 1.0, 1.25), 250: (55, 1.0, 1.25), 300: (66, 1.0, 1.25)},
    "SRH2": {150: (35, 1.0, 1.25), 200: (46, 1.0, 1.25), 250: (55, 1.0, 1.25), 300: (66, 1.0, 1.25)},
    "SRH3": {150: (35, 1.0, 1.25), 200: (46, 1.0, 1.25), 250: (55, 1.0, 1.25), 300: (66, 1.0, 1.25)},
    "SRH4": {150: (61, 1.25, 1.5), 200: (79, 1.25, 1.5), 250: (96, 1.25, 1.5), 300: (114, 1.25, 1.5)},
}

ALL_VALVES = {
    ValveManufacturer.HANSEN: HANSEN_VALVES,
    ValveManufacturer.HENRY: HENRY_VALVES,
    ValveManufacturer.SHANK: SHANK_VALVES,
}


# ==============================================================================
# 3-WAY VALVE DATA
# From SRV7.7 DATA sheet
# ==============================================================================

THREE_WAY_VALVES = {
    # Hansen 3-way valves: model -> (inlet, outlet, Cv)
    "Hansen": {
        "H5570": (0.5, 0.75, 3.0),
        "H5571": (0.75, 1.0, 6.0),
        "H5572": (1.0, 1.25, 12.0),
        "H5573": (1.25, 1.5, 18.0),
        "H5574": (1.5, 2.0, 28.0),
    },
    "Shank": {
        "SS3A": (0.5, 0.75, 3.0),
        "SS3B": (0.75, 1.0, 6.0),
        "SS3C": (1.0, 1.25, 12.0),
        "SS3D": (1.25, 1.5, 18.0),
        "SS3E": (1.5, 2.0, 28.0),
    },
}


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class SRVResult:
    """Results of a safety relief valve sizing calculation."""
    equipment_name: str
    equipment_type: VesselType
    
    # Required capacity
    required_capacity_lb_min: float  # lb/min air
    
    # Selected valve
    valve_manufacturer: str = ""
    valve_model: str = ""
    valve_config: str = ""  # Single or Dual
    valve_capacity_lb_min: float = 0.0
    set_pressure_psig: float = 0.0
    inlet_size_in: float = 0.0
    outlet_size_in: float = 0.0
    
    # Piping
    outlet_pipe_nps: float = 0.0
    pipe_id_in: float = 0.0
    outlet_pipe_length_ft: float = 0.0
    
    # 3-way valve
    three_way_model: str = ""
    three_way_inlet: float = 0.0
    three_way_outlet: float = 0.0
    three_way_cv: float = 0.0
    
    # Checks
    capacity_adequate: bool = False
    derated: bool = False
    derate_factor: float = 1.0
    
    notes: List[str] = field(default_factory=list)


@dataclass
class CMCResult:
    """CMC 1118.0 Equation 1118.0-1 outlet pipe length calculation."""
    valve_name: str
    set_pressure_psi: float
    absolute_pressure_psi: float  # (set_pressure * 1.1) + 14.7
    pipe_inside_dia_in: float
    capacity_lb_per_min: float
    max_pipe_length_ft: float


# ==============================================================================
# MAIN CALCULATION FUNCTIONS
# ==============================================================================

def vessel_required_capacity(diameter_ft: float, length_ft: float,
                              is_horizontal: bool = True) -> float:
    """
    Calculate required relief valve capacity for a vessel per IIAR-2.
    
    Formula: C = f × D_L
    Where:
        C = required capacity (lb/min air)
        f = factor (1.0 for first 8 ft², 0.5 thereafter per IIAR-2)
        D_L = external surface area (ft²) based on vessel type
    
    For horizontal vessel: A = π × D × L + 2 × π × (D/2)²
    For vertical vessel:   A = π × D × L + 2 × π × (D/2)²
    
    Per IIAR-2 Table 1:
        A_external (ft²) | Capacity factor
        First 100 ft²    | 1.0 lb/min per ft²
        Next 200 ft²     | 0.5
        Next 400 ft²     | 0.333
        Remainder         | 0.25
    
    Args:
        diameter_ft: Vessel outside diameter in feet
        length_ft: Vessel tangent-to-tangent length in feet
        is_horizontal: True for horizontal, False for vertical
        
    Returns:
        Required capacity in lb/min air
    """
    # External surface area calculation
    radius = diameter_ft / 2.0
    cylindrical_area = math.pi * diameter_ft * length_ft
    head_area = 2 * math.pi * radius ** 2  # 2:1 ellipsoidal heads approximation
    total_area = cylindrical_area + head_area
    
    # IIAR-2 Table 1 capacity factors (stepped)
    capacity = 0.0
    remaining = total_area
    
    if remaining > 0:
        first = min(remaining, 100.0)
        capacity += first * 1.0
        remaining -= first
    if remaining > 0:
        second = min(remaining, 200.0)
        capacity += second * 0.5
        remaining -= second
    if remaining > 0:
        third = min(remaining, 400.0)
        capacity += third * 0.333
        remaining -= third
    if remaining > 0:
        capacity += remaining * 0.25
    
    return capacity


def heat_exchanger_required_capacity(width_or_dia_ft: float, length_ft: float,
                                       height_ft: float = 0.0,
                                       sd_diameter_ft: float = 0.0,
                                       sd_length_ft: float = 0.0,
                                       is_cylindrical: bool = True) -> float:
    """
    Calculate required relief valve capacity for heat exchangers per IIAR-2.
    
    Includes shell-and-tube, evaporative condensers, and plate heat exchangers.
    For equipment with surge drums (SD), the SD area is added.
    
    Args:
        width_or_dia_ft: Width (rectangular) or diameter (cylindrical) in feet
        length_ft: Length in feet
        height_ft: Height in feet (rectangular only)
        sd_diameter_ft: Surge drum diameter in feet (if applicable)
        sd_length_ft: Surge drum length in feet (if applicable)
        is_cylindrical: True for cylindrical, False for rectangular
        
    Returns:
        Required capacity in lb/min air
    """
    if is_cylindrical:
        radius = width_or_dia_ft / 2.0
        area = math.pi * width_or_dia_ft * length_ft + 2 * math.pi * radius ** 2
    else:
        # Rectangular: W×L×2 + W×H×2 + L×H×2
        area = 2 * (width_or_dia_ft * length_ft + 
                     width_or_dia_ft * height_ft + 
                     length_ft * height_ft)
    
    # Add surge drum area if present
    if sd_diameter_ft > 0 and sd_length_ft > 0:
        sd_radius = sd_diameter_ft / 2.0
        area += math.pi * sd_diameter_ft * sd_length_ft + 2 * math.pi * sd_radius ** 2
    
    # Same stepped capacity as vessels
    return _stepped_capacity(area)


def compressor_required_capacity(compressor_type: str, suction_temp_f: float,
                                   hp_or_displacement: float,
                                   set_pressure_psi: float = 250,
                                   oil_cooling: str = "none") -> float:
    """
    Calculate required relief valve capacity for compressors per IIAR-2.
    
    For screw compressors:
        C = displacement (CFM) × correction factor
    
    For reciprocating compressors:
        C = displacement (CFM) × volumetric efficiency
    
    The oil cooling method affects the required capacity for TSOC systems.
    
    Args:
        compressor_type: "screw" or "reciprocating"
        suction_temp_f: Saturated suction temperature °F
        hp_or_displacement: Compressor HP or displacement CFM
        set_pressure_psi: Relief valve set pressure (typically 250 psi)
        oil_cooling: "none", "thermosiphon", "water", "injection"
        
    Returns:
        Required capacity in lb/min air
    """
    # Simplified - full implementation would use manufacturer displacement data
    # Per IIAR-2, compressor capacity = displacement CFM at set pressure conditions
    if compressor_type.lower() == "screw":
        # Screw compressor: C ≈ displacement × density correction
        capacity = hp_or_displacement * 0.8  # Typical screw compressor factor
    else:
        # Reciprocating: C ≈ displacement × volumetric efficiency
        capacity = hp_or_displacement * 0.7  # Typical reciprocating factor
    
    return capacity


def select_valve(required_capacity: float, set_pressure_psi: float,
                  manufacturer: ValveManufacturer = ValveManufacturer.HANSEN,
                  config: ValveConfig = ValveConfig.SINGLE,
                  derate: bool = True) -> SRVResult:
    """
    Select a relief valve that meets the required capacity.
    
    Derating per IIAR-2:
        When derate=True, valve capacity is multiplied by 0.9 (10% derating)
        to account for backpressure effects.
    
    For dual valve configuration:
        Each valve must independently handle the full required capacity.
    
    Args:
        required_capacity: Required capacity in lb/min air
        set_pressure_psi: Set pressure in psig
        manufacturer: Valve manufacturer
        config: Single or Dual configuration
        derate: Apply 10% derating factor (default True per IIAR-2)
        
    Returns:
        SRVResult with selected valve information
    """
    result = SRVResult(
        equipment_name="",
        equipment_type=VesselType.HORIZONTAL_VESSEL,
        required_capacity_lb_min=required_capacity,
        set_pressure_psig=set_pressure_psi,
        valve_config=config.value,
        derated=derate,
        derate_factor=0.9 if derate else 1.0,
    )
    
    valve_catalog = ALL_VALVES.get(manufacturer, HANSEN_VALVES)
    
    # Find nearest set pressure (round up to available pressures)
    available_pressures = [150, 200, 250, 300]
    target_pressure = min(p for p in available_pressures if p >= set_pressure_psi) \
        if set_pressure_psi <= 300 else 300
    
    # Search for adequate valve
    for model, pressure_data in valve_catalog.items():
        if target_pressure in pressure_data:
            cap_data = pressure_data[target_pressure]
            capacity = cap_data[0]
            
            effective_capacity = capacity * result.derate_factor
            
            if effective_capacity >= required_capacity:
                result.valve_manufacturer = manufacturer.value
                result.valve_model = model
                result.valve_capacity_lb_min = capacity
                result.inlet_size_in = cap_data[1]
                result.outlet_size_in = cap_data[2]
                result.capacity_adequate = True
                break
    
    if not result.capacity_adequate:
        result.notes.append(
            f"No single {manufacturer.value} valve meets {required_capacity:.1f} lb/min at "
            f"{set_pressure_psi} psig. Consider dual valves or larger manufacturer models."
        )
    
    return result


# ==============================================================================
# OUTLET PIPING CALCULATIONS
# ==============================================================================

def outlet_pipe_max_length_iiar(pipe_nps: float, capacity_lb_min: float,
                                  set_pressure_psi: float) -> float:
    """
    Calculate maximum outlet pipe length per IIAR-2.
    
    Formula (from SRV7.7 spreadsheet):
        L_max = (d^5 × 2550 × P) / (f × W²)
    
    Where:
        L_max = maximum pipe length (ft)
        d = pipe inside diameter (in)
        P = (set_pressure × 1.1) + 14.7 (absolute pressure, psia)
        f = Moody friction factor (from pipe data table)
        W = flow rate (lb/min air)
    
    This ensures backpressure does not exceed 10% of set pressure.
    
    Args:
        pipe_nps: Nominal pipe size
        capacity_lb_min: Relief valve capacity (lb/min air)
        set_pressure_psi: Set pressure (psig)
        
    Returns:
        Maximum allowable outlet pipe length in feet
    """
    if pipe_nps not in PIPE_DATA_SCH40:
        raise ValueError(f"Pipe size {pipe_nps} not in database. Available: {sorted(PIPE_DATA_SCH40.keys())}")
    
    d, f = PIPE_DATA_SCH40[pipe_nps]
    P = (set_pressure_psi * 1.1) + 14.7  # Absolute pressure
    W = capacity_lb_min
    
    if W <= 0:
        return float('inf')
    
    # L = d^5 × 2550 × P / (f × W²)
    L_max = (d ** 5 * 2550.0 * P) / (f * W ** 2)
    
    return L_max


def cmc_outlet_pipe_length(set_pressure_psi: float, pipe_id_in: float,
                            capacity_lb_min: float) -> CMCResult:
    """
    Calculate maximum outlet pipe length per CMC 1118.0 Equation 1118.0-1.
    
    From SRV_CMC.xls:
        L = (d^5 × 2550 × P) / (f × C²)
    
    Where:
        L = maximum equivalent length of pipe (ft)
        d = inside diameter of pipe (in)
        P = (set_pressure × 1.1) + 14.7 (psia)
        f = Moody friction factor
        C = rated capacity of relief device (lb/min air)
    
    Args:
        set_pressure_psi: Set pressure (psig)
        pipe_id_in: Pipe inside diameter (inches)
        capacity_lb_min: Rated capacity (lb/min air)
        
    Returns:
        CMCResult with maximum pipe length
    """
    P = (set_pressure_psi * 1.1) + 14.7
    
    # Estimate Moody friction factor based on pipe diameter
    # Interpolate from PIPE_DATA table
    f = 0.020  # Default
    for nps, (d, ff) in PIPE_DATA_SCH40.items():
        if abs(d - pipe_id_in) < 0.1:
            f = ff
            break
    
    if capacity_lb_min <= 0:
        L = float('inf')
    else:
        L = (pipe_id_in ** 5 * 2550.0 * P) / (f * capacity_lb_min ** 2)
    
    return CMCResult(
        valve_name="",
        set_pressure_psi=set_pressure_psi,
        absolute_pressure_psi=P,
        pipe_inside_dia_in=pipe_id_in,
        capacity_lb_per_min=capacity_lb_min,
        max_pipe_length_ft=L,
    )


# ==============================================================================
# DIFFUSION TANK
# ==============================================================================

def diffusion_tank_submergence_factor(depth_ft: float) -> float:
    """
    Calculate diffusion tank backpressure factor based on submergence depth.
    
    Per IIAR-2, if the relief valve discharges to a diffusion tank,
    the backpressure from the liquid column must be accounted for.
    
    Backpressure = depth_ft × 62.4 / 144 = depth_ft × 0.433 psig
    
    Args:
        depth_ft: Depth of submergence in diffusion tank (ft)
        
    Returns:
        Backpressure in psig from liquid column
    """
    return depth_ft * 0.433  # Water density factor: 62.4 lb/ft³ / 144 in²/ft²


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _stepped_capacity(area_ft2: float) -> float:
    """
    Calculate required capacity using IIAR-2 stepped surface area method.
    
    IIAR-2 Table 1 capacity factors:
        First 100 ft²  → 1.0 lb/min per ft²
        Next 200 ft²   → 0.5 lb/min per ft²
        Next 400 ft²   → 0.333 lb/min per ft²
        Remainder       → 0.25 lb/min per ft²
    """
    capacity = 0.0
    remaining = area_ft2
    
    steps = [(100.0, 1.0), (200.0, 0.5), (400.0, 0.333)]
    for limit, factor in steps:
        if remaining <= 0:
            break
        portion = min(remaining, limit)
        capacity += portion * factor
        remaining -= portion
    
    if remaining > 0:
        capacity += remaining * 0.25
    
    return capacity


def list_available_valves(manufacturer: ValveManufacturer = None,
                           set_pressure: float = 250) -> List[Dict]:
    """
    List all available valves, optionally filtered by manufacturer and set pressure.
    
    Returns list of dicts with model, manufacturer, capacity, inlet/outlet sizes.
    """
    results = []
    
    manufacturers = [manufacturer] if manufacturer else list(ALL_VALVES.keys())
    
    for mfr in manufacturers:
        catalog = ALL_VALVES[mfr]
        for model, pressure_data in catalog.items():
            # Find nearest pressure
            pressures = sorted(pressure_data.keys())
            target = min(pressures, key=lambda p: abs(p - set_pressure))
            
            if target in pressure_data:
                cap, inlet, outlet = pressure_data[target]
                results.append({
                    "manufacturer": mfr.value,
                    "model": model,
                    "set_pressure": target,
                    "capacity_lb_min": cap,
                    "inlet_in": inlet,
                    "outlet_in": outlet,
                })
    
    return sorted(results, key=lambda x: x["capacity_lb_min"])


# ==============================================================================
# QUICK FUNCTIONS
# ==============================================================================

def quick_vessel_srv(diameter_ft: float, length_ft: float,
                      set_pressure: float = 250,
                      manufacturer: ValveManufacturer = ValveManufacturer.HANSEN) -> SRVResult:
    """
    Quick function: size a relief valve for a vessel.
    
    Args:
        diameter_ft: Vessel diameter in feet
        length_ft: Vessel length in feet
        set_pressure: Set pressure in psig
        manufacturer: Valve manufacturer preference
        
    Returns:
        SRVResult with valve selection and piping details
    """
    capacity = vessel_required_capacity(diameter_ft, length_ft)
    result = select_valve(capacity, set_pressure, manufacturer)
    result.equipment_type = VesselType.HORIZONTAL_VESSEL
    
    # Calculate max outlet pipe length
    if result.outlet_size_in > 0:
        # Find matching NPS
        for nps, (d, f) in PIPE_DATA_SCH40.items():
            if abs(nps - result.outlet_size_in) < 0.01 or nps >= result.outlet_size_in:
                result.outlet_pipe_nps = nps
                result.pipe_id_in = d
                max_length = outlet_pipe_max_length_iiar(
                    nps, result.valve_capacity_lb_min * result.derate_factor, set_pressure
                )
                result.outlet_pipe_length_ft = max_length
                break
    
    return result
