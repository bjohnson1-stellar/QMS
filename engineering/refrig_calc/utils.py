"""
Utilities Module
================

Common utility functions for refrigeration calculations including:
- Unit conversions
- Pressure-temperature conversions
- Flow rate calculations
- Engineering constants
"""

import math
from typing import Dict, Optional, Tuple, Union


# ============================================================================
# ENGINEERING CONSTANTS
# ============================================================================

# Gravitational acceleration
G = 32.174  # ft/s²
G_C = 32.174  # lbm-ft/lbf-s² (gravitational constant)

# Gas constant
R_UNIVERSAL = 1545.35  # ft-lbf/(lbmol-°R)
R_AIR = 53.35  # ft-lbf/(lbm-°R)

# Conversion factors
BTU_PER_HP_HR = 2545  # BTU/hr per horsepower
BTU_PER_KW = 3412.14  # BTU/hr per kW
TON_BTU_HR = 12000    # BTU/hr per ton of refrigeration

# Standard conditions
STANDARD_TEMP_F = 70
STANDARD_PRESSURE_PSIA = 14.696


# ============================================================================
# TEMPERATURE CONVERSIONS
# ============================================================================

def fahrenheit_to_celsius(temp_f: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (temp_f - 32) * 5 / 9


def celsius_to_fahrenheit(temp_c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return temp_c * 9 / 5 + 32


def fahrenheit_to_rankine(temp_f: float) -> float:
    """Convert Fahrenheit to Rankine (absolute)."""
    return temp_f + 459.67


def celsius_to_kelvin(temp_c: float) -> float:
    """Convert Celsius to Kelvin (absolute)."""
    return temp_c + 273.15


def rankine_to_fahrenheit(temp_r: float) -> float:
    """Convert Rankine to Fahrenheit."""
    return temp_r - 459.67


def kelvin_to_celsius(temp_k: float) -> float:
    """Convert Kelvin to Celsius."""
    return temp_k - 273.15


# ============================================================================
# PRESSURE CONVERSIONS
# ============================================================================

def psia_to_psig(psia: float) -> float:
    """Convert absolute pressure to gauge pressure."""
    return psia - 14.696


def psig_to_psia(psig: float) -> float:
    """Convert gauge pressure to absolute pressure."""
    return psig + 14.696


def psia_to_bar(psia: float) -> float:
    """Convert psia to bar."""
    return psia * 0.0689476


def bar_to_psia(bar: float) -> float:
    """Convert bar to psia."""
    return bar / 0.0689476


def psia_to_kpa(psia: float) -> float:
    """Convert psia to kPa."""
    return psia * 6.89476


def kpa_to_psia(kpa: float) -> float:
    """Convert kPa to psia."""
    return kpa / 6.89476


def psia_to_mpa(psia: float) -> float:
    """Convert psia to MPa."""
    return psia * 0.00689476


def inhg_to_psia(inhg: float) -> float:
    """Convert inches of mercury to psia."""
    return inhg * 0.4912


def psia_to_inhg(psia: float) -> float:
    """Convert psia to inches of mercury."""
    return psia / 0.4912


def ft_h2o_to_psi(ft_h2o: float) -> float:
    """Convert feet of water column to psi."""
    return ft_h2o * 0.4335


def psi_to_ft_h2o(psi: float) -> float:
    """Convert psi to feet of water column."""
    return psi / 0.4335


# ============================================================================
# LENGTH CONVERSIONS
# ============================================================================

def feet_to_meters(ft: float) -> float:
    """Convert feet to meters."""
    return ft * 0.3048


def meters_to_feet(m: float) -> float:
    """Convert meters to feet."""
    return m / 0.3048


def inches_to_mm(inches: float) -> float:
    """Convert inches to millimeters."""
    return inches * 25.4


def mm_to_inches(mm: float) -> float:
    """Convert millimeters to inches."""
    return mm / 25.4


def inches_to_feet(inches: float) -> float:
    """Convert inches to feet."""
    return inches / 12


def feet_to_inches(feet: float) -> float:
    """Convert feet to inches."""
    return feet * 12


# ============================================================================
# VOLUME CONVERSIONS
# ============================================================================

def cubic_feet_to_gallons(cf: float) -> float:
    """Convert cubic feet to US gallons."""
    return cf * 7.48052


def gallons_to_cubic_feet(gal: float) -> float:
    """Convert US gallons to cubic feet."""
    return gal / 7.48052


def cubic_feet_to_liters(cf: float) -> float:
    """Convert cubic feet to liters."""
    return cf * 28.3168


def liters_to_cubic_feet(liters: float) -> float:
    """Convert liters to cubic feet."""
    return liters / 28.3168


def cubic_inches_to_cubic_feet(ci: float) -> float:
    """Convert cubic inches to cubic feet."""
    return ci / 1728


def cubic_feet_to_cubic_inches(cf: float) -> float:
    """Convert cubic feet to cubic inches."""
    return cf * 1728


# ============================================================================
# MASS CONVERSIONS
# ============================================================================

def pounds_to_kg(lb: float) -> float:
    """Convert pounds to kilograms."""
    return lb * 0.453592


def kg_to_pounds(kg: float) -> float:
    """Convert kilograms to pounds."""
    return kg / 0.453592


# ============================================================================
# FLOW RATE CONVERSIONS
# ============================================================================

def cfm_to_m3_hr(cfm: float) -> float:
    """Convert CFM to m³/hr."""
    return cfm * 1.699


def m3_hr_to_cfm(m3_hr: float) -> float:
    """Convert m³/hr to CFM."""
    return m3_hr / 1.699


def gpm_to_lpm(gpm: float) -> float:
    """Convert gallons per minute to liters per minute."""
    return gpm * 3.78541


def lpm_to_gpm(lpm: float) -> float:
    """Convert liters per minute to gallons per minute."""
    return lpm / 3.78541


def lb_hr_to_kg_hr(lb_hr: float) -> float:
    """Convert lb/hr to kg/hr."""
    return lb_hr * 0.453592


def kg_hr_to_lb_hr(kg_hr: float) -> float:
    """Convert kg/hr to lb/hr."""
    return kg_hr / 0.453592


# ============================================================================
# ENERGY CONVERSIONS
# ============================================================================

def btu_to_kj(btu: float) -> float:
    """Convert BTU to kJ."""
    return btu * 1.05506


def kj_to_btu(kj: float) -> float:
    """Convert kJ to BTU."""
    return kj / 1.05506


def btu_hr_to_kw(btu_hr: float) -> float:
    """Convert BTU/hr to kW."""
    return btu_hr / 3412.14


def kw_to_btu_hr(kw: float) -> float:
    """Convert kW to BTU/hr."""
    return kw * 3412.14


def tons_to_kw(tons: float) -> float:
    """Convert tons of refrigeration to kW."""
    return tons * 3.5168


def kw_to_tons(kw: float) -> float:
    """Convert kW to tons of refrigeration."""
    return kw / 3.5168


def tons_to_btu_hr(tons: float) -> float:
    """Convert tons of refrigeration to BTU/hr."""
    return tons * 12000


def btu_hr_to_tons(btu_hr: float) -> float:
    """Convert BTU/hr to tons of refrigeration."""
    return btu_hr / 12000


def hp_to_kw(hp: float) -> float:
    """Convert horsepower to kW."""
    return hp * 0.7457


def kw_to_hp(kw: float) -> float:
    """Convert kW to horsepower."""
    return kw / 0.7457


def hp_to_btu_hr(hp: float) -> float:
    """Convert horsepower to BTU/hr."""
    return hp * 2545


# ============================================================================
# DENSITY CONVERSIONS
# ============================================================================

def lb_ft3_to_kg_m3(lb_ft3: float) -> float:
    """Convert lb/ft³ to kg/m³."""
    return lb_ft3 * 16.0185


def kg_m3_to_lb_ft3(kg_m3: float) -> float:
    """Convert kg/m³ to lb/ft³."""
    return kg_m3 / 16.0185


# ============================================================================
# VELOCITY CONVERSIONS
# ============================================================================

def fps_to_mps(fps: float) -> float:
    """Convert feet per second to meters per second."""
    return fps * 0.3048


def mps_to_fps(mps: float) -> float:
    """Convert meters per second to feet per second."""
    return mps / 0.3048


def fpm_to_mps(fpm: float) -> float:
    """Convert feet per minute to meters per second."""
    return fpm * 0.00508


def mps_to_fpm(mps: float) -> float:
    """Convert meters per second to feet per minute."""
    return mps / 0.00508


# ============================================================================
# REFRIGERATION CALCULATIONS
# ============================================================================

def refrigeration_effect(
    enthalpy_in: float,
    enthalpy_out: float,
) -> float:
    """
    Calculate refrigeration effect.
    
    Args:
        enthalpy_in: Enthalpy entering evaporator (BTU/lb)
        enthalpy_out: Enthalpy leaving evaporator (BTU/lb)
    
    Returns:
        Refrigeration effect (BTU/lb)
    """
    return enthalpy_out - enthalpy_in


def mass_flow_rate(
    capacity_tons: float,
    refrigeration_effect: float,
) -> float:
    """
    Calculate refrigerant mass flow rate.
    
    Args:
        capacity_tons: Refrigeration capacity (tons)
        refrigeration_effect: Refrigeration effect (BTU/lb)
    
    Returns:
        Mass flow rate (lb/hr)
    """
    if refrigeration_effect <= 0:
        return 0
    return capacity_tons * 12000 / refrigeration_effect


def volumetric_flow_rate(
    mass_flow_lb_hr: float,
    specific_volume_ft3_lb: float,
) -> float:
    """
    Calculate volumetric flow rate.
    
    Args:
        mass_flow_lb_hr: Mass flow rate (lb/hr)
        specific_volume_ft3_lb: Specific volume (ft³/lb)
    
    Returns:
        Volumetric flow rate (CFM)
    """
    return mass_flow_lb_hr * specific_volume_ft3_lb / 60


def compressor_power(
    mass_flow_lb_hr: float,
    work_of_compression: float,
    efficiency: float = 0.75,
) -> float:
    """
    Calculate compressor power requirement.
    
    Args:
        mass_flow_lb_hr: Mass flow rate (lb/hr)
        work_of_compression: Work of compression (BTU/lb)
        efficiency: Overall compressor efficiency
    
    Returns:
        Power requirement (HP)
    """
    if efficiency <= 0:
        efficiency = 0.75
    return mass_flow_lb_hr * work_of_compression / (efficiency * 2545)


def cop_refrigeration(
    refrigeration_effect: float,
    work_of_compression: float,
) -> float:
    """
    Calculate Coefficient of Performance for refrigeration.
    
    Args:
        refrigeration_effect: Refrigeration effect (BTU/lb)
        work_of_compression: Work of compression (BTU/lb)
    
    Returns:
        COP (dimensionless)
    """
    if work_of_compression <= 0:
        return 0
    return refrigeration_effect / work_of_compression


def heat_rejection(
    capacity_tons: float,
    compressor_hp: float,
) -> float:
    """
    Calculate heat rejection at condenser.
    
    Args:
        capacity_tons: Refrigeration capacity (tons)
        compressor_hp: Compressor motor HP
    
    Returns:
        Heat rejection (BTU/hr)
    """
    # Heat rejection = Refrigeration load + Compressor heat
    refrigeration_load = capacity_tons * 12000
    compressor_heat = compressor_hp * 2545
    return refrigeration_load + compressor_heat


# ============================================================================
# PIPE AND VESSEL CALCULATIONS
# ============================================================================

def pipe_cross_section_area(diameter_in: float) -> float:
    """
    Calculate pipe cross-sectional area.
    
    Args:
        diameter_in: Pipe inside diameter (inches)
    
    Returns:
        Cross-sectional area (ft²)
    """
    return math.pi * (diameter_in / 12) ** 2 / 4


def pipe_volume(diameter_in: float, length_ft: float) -> float:
    """
    Calculate pipe internal volume.
    
    Args:
        diameter_in: Pipe inside diameter (inches)
        length_ft: Pipe length (feet)
    
    Returns:
        Volume (ft³)
    """
    return pipe_cross_section_area(diameter_in) * length_ft


def cylinder_volume(diameter_in: float, length_in: float) -> float:
    """
    Calculate cylinder volume.
    
    Args:
        diameter_in: Cylinder diameter (inches)
        length_in: Cylinder length (inches)
    
    Returns:
        Volume (ft³)
    """
    return math.pi * (diameter_in / 2) ** 2 * length_in / 1728


def elliptical_head_volume(diameter_in: float, ratio: float = 2.0) -> float:
    """
    Calculate elliptical head volume.
    
    Args:
        diameter_in: Head diameter (inches)
        ratio: Ellipse ratio (default 2:1)
    
    Returns:
        Volume (ft³)
    """
    # For 2:1 elliptical head, depth = D/4
    depth = diameter_in / (2 * ratio)
    # Volume = 2/3 * π * a² * b (for half ellipsoid)
    a = diameter_in / 2  # radius
    b = depth
    volume_in3 = 2 / 3 * math.pi * a ** 2 * b
    return volume_in3 / 1728


def hemispherical_head_volume(diameter_in: float) -> float:
    """
    Calculate hemispherical head volume.
    
    Args:
        diameter_in: Head diameter (inches)
    
    Returns:
        Volume (ft³)
    """
    radius = diameter_in / 2
    volume_in3 = 2 / 3 * math.pi * radius ** 3
    return volume_in3 / 1728


def horizontal_cylinder_partial_volume(
    diameter_in: float,
    length_in: float,
    fill_height_in: float,
) -> float:
    """
    Calculate partial volume of horizontal cylinder.
    
    Args:
        diameter_in: Cylinder diameter (inches)
        length_in: Cylinder length (inches)
        fill_height_in: Liquid fill height from bottom (inches)
    
    Returns:
        Liquid volume (ft³)
    """
    r = diameter_in / 2
    h = fill_height_in
    
    if h <= 0:
        return 0
    if h >= diameter_in:
        return cylinder_volume(diameter_in, length_in)
    
    # Area of circular segment
    theta = 2 * math.acos((r - h) / r)
    segment_area = r ** 2 * (theta - math.sin(theta)) / 2
    
    volume_in3 = segment_area * length_in
    return volume_in3 / 1728


# ============================================================================
# FLUID DYNAMICS
# ============================================================================

def reynolds_number(
    velocity_fps: float,
    diameter_ft: float,
    density_lb_ft3: float,
    viscosity_lb_ft_hr: float,
) -> float:
    """
    Calculate Reynolds number.
    
    Args:
        velocity_fps: Fluid velocity (ft/s)
        diameter_ft: Pipe diameter (ft)
        density_lb_ft3: Fluid density (lb/ft³)
        viscosity_lb_ft_hr: Dynamic viscosity (lbm/ft-hr)
    
    Returns:
        Reynolds number (dimensionless)
    """
    viscosity_lb_ft_s = viscosity_lb_ft_hr / 3600
    if viscosity_lb_ft_s <= 0:
        return 1e6  # Assume turbulent
    return density_lb_ft3 * velocity_fps * diameter_ft / viscosity_lb_ft_s


def friction_factor_laminar(reynolds: float) -> float:
    """
    Calculate Darcy friction factor for laminar flow.
    
    Args:
        reynolds: Reynolds number
    
    Returns:
        Friction factor
    """
    if reynolds <= 0:
        return 0.04
    return 64 / reynolds


def friction_factor_turbulent(
    reynolds: float,
    relative_roughness: float = 0.0001,
) -> float:
    """
    Calculate Darcy friction factor for turbulent flow (Swamee-Jain).
    
    Args:
        reynolds: Reynolds number
        relative_roughness: Pipe roughness / diameter
    
    Returns:
        Friction factor
    """
    if reynolds <= 2300:
        return friction_factor_laminar(reynolds)
    
    # Swamee-Jain equation
    term = relative_roughness / 3.7 + 5.74 / reynolds ** 0.9
    return 0.25 / (math.log10(term)) ** 2


def pressure_drop_darcy(
    friction_factor: float,
    length_ft: float,
    diameter_ft: float,
    velocity_fps: float,
    density_lb_ft3: float,
) -> float:
    """
    Calculate pressure drop using Darcy-Weisbach equation.
    
    Args:
        friction_factor: Darcy friction factor
        length_ft: Pipe length (ft)
        diameter_ft: Pipe diameter (ft)
        velocity_fps: Fluid velocity (ft/s)
        density_lb_ft3: Fluid density (lb/ft³)
    
    Returns:
        Pressure drop (psi)
    """
    # ΔP = f * (L/D) * (ρ * V² / 2) / gc / 144
    delta_p = friction_factor * (length_ft / diameter_ft) * \
              (density_lb_ft3 * velocity_fps ** 2 / 2) / G_C / 144
    return delta_p


def velocity_from_flow(
    flow_rate_cfm: float,
    diameter_in: float,
) -> float:
    """
    Calculate velocity from volumetric flow rate.
    
    Args:
        flow_rate_cfm: Volumetric flow rate (CFM)
        diameter_in: Pipe inside diameter (inches)
    
    Returns:
        Velocity (ft/s)
    """
    area_ft2 = pipe_cross_section_area(diameter_in)
    if area_ft2 <= 0:
        return 0
    return flow_rate_cfm / (area_ft2 * 60)


# ============================================================================
# AIR CALCULATIONS
# ============================================================================

def sensible_heat_air(
    cfm: float,
    delta_t: float,
) -> float:
    """
    Calculate sensible heat for air.
    
    Q = 1.08 × CFM × ΔT
    
    Args:
        cfm: Air flow rate (CFM)
        delta_t: Temperature difference (°F)
    
    Returns:
        Heat transfer (BTU/hr)
    """
    return 1.08 * cfm * delta_t


def latent_heat_air(
    cfm: float,
    delta_w: float,
) -> float:
    """
    Calculate latent heat for air.
    
    Q = 0.68 × CFM × Δw
    
    Args:
        cfm: Air flow rate (CFM)
        delta_w: Humidity ratio difference (grains/lb)
    
    Returns:
        Heat transfer (BTU/hr)
    """
    return 0.68 * cfm * delta_w


def total_heat_air(
    cfm: float,
    delta_h: float,
) -> float:
    """
    Calculate total heat for air.
    
    Q = 4.5 × CFM × Δh
    
    Args:
        cfm: Air flow rate (CFM)
        delta_h: Enthalpy difference (BTU/lb)
    
    Returns:
        Heat transfer (BTU/hr)
    """
    return 4.5 * cfm * delta_h


def air_changes_per_hour(
    cfm: float,
    room_volume_ft3: float,
) -> float:
    """
    Calculate air changes per hour.
    
    Args:
        cfm: Air flow rate (CFM)
        room_volume_ft3: Room volume (ft³)
    
    Returns:
        Air changes per hour (ACH)
    """
    if room_volume_ft3 <= 0:
        return 0
    return cfm * 60 / room_volume_ft3


def cfm_from_ach(
    ach: float,
    room_volume_ft3: float,
) -> float:
    """
    Calculate CFM from air changes per hour.
    
    Args:
        ach: Air changes per hour
        room_volume_ft3: Room volume (ft³)
    
    Returns:
        Air flow rate (CFM)
    """
    return ach * room_volume_ft3 / 60


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def interpolate_linear(
    x: float,
    x1: float,
    x2: float,
    y1: float,
    y2: float,
) -> float:
    """
    Linear interpolation between two points.
    
    Args:
        x: Value to interpolate at
        x1, x2: Known x values
        y1, y2: Known y values
    
    Returns:
        Interpolated y value
    """
    if x2 == x1:
        return y1
    return y1 + (x - x1) * (y2 - y1) / (x2 - x1)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(value, max_val))


def round_to_nearest(value: float, increment: float) -> float:
    """Round a value to the nearest increment."""
    if increment <= 0:
        return value
    return round(value / increment) * increment
