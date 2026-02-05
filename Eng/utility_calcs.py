"""
Underfloor Warming & Utility Calculations Module
==================================================

Extracted from: Underfloor_Warming_Template.xlsx, Sump_tank_volume.xlsx,
                114592399PressureTestingandPurgingCalculator1.xls,
                63938910NitrogenCalculationAirgas.xls

Calculates:
1. Underfloor warming (UFW) system design
2. Sump/containment tank volume
3. Pressure testing nitrogen requirements
4. Nitrogen purge calculations

Standards Reference:
    IIAR guidance for underfloor warming
    ASHRAE Handbook - Refrigeration (frost heave prevention)
"""

import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict


# ==============================================================================
# UNDERFLOOR WARMING
# ==============================================================================

@dataclass
class UFWDesignResult:
    """Underfloor warming system design results."""
    # Input summary
    num_tubes: int = 0
    avg_loop_length_ft: float = 0
    max_loop_length_ft: float = 0
    header_size_in: float = 3.0
    header_length_ft: float = 0
    
    # Flow
    flow_per_loop_gpm: float = 3.0
    total_flow_gpm: float = 0
    header_adequate: bool = True
    
    # Glycol
    glycol_type: str = "30% PG"
    supply_temp_f: float = 50.0
    return_temp_f: float = 40.0
    
    # Heat load
    floor_area_ft2: float = 0
    heat_load_btuh: float = 0  # Rule of thumb: 3 BTU/ft²
    
    # Pressure drop
    tubing_pd_psi_per_100ft: float = 1.4
    total_pd_ft_head: float = 0
    
    notes: List[str] = field(default_factory=list)


def design_ufw_system(floor_area_ft2: float,
                       num_tubes: int = None,
                       avg_loop_length_ft: float = 875,
                       max_loop_length_ft: float = 1000,
                       header_length_ft: float = 200,
                       glycol_type: str = "30% PG",
                       supply_temp_f: float = 50,
                       return_temp_f: float = 40,
                       flow_per_loop_gpm: float = 3.0,
                       heat_load_btu_per_ft2: float = 3.0) -> UFWDesignResult:
    """
    Design an underfloor warming (UFW) system.
    
    From Underfloor_Warming_Template.xlsx:
        Rule of thumb: 3 BTU/ft² for underfloor warming
        Flow: 3 GPM per loop (1" CTS HDPE tubing)
        Max loop length: 1000 ft
        
    Header sizing (steel pipe):
        2" header: max 38 GPM (12 loops)
        3" header: max 113 GPM (37 loops)
        4" header: max 235 GPM (78 loops)
    
    Header sizing (Aquatherm):
        2" header: max 52 GPM (17 loops)
        3" header: max 135 GPM (45 loops)
        4" header: max 405 GPM (135 loops)
    
    Args:
        floor_area_ft2: Total floor area requiring UFW (ft²)
        num_tubes: Number of heating tubes/loops
        avg_loop_length_ft: Average loop length (ft)
        max_loop_length_ft: Maximum single loop length (ft)
        header_length_ft: Total header length (ft)
        glycol_type: Glycol specification (e.g., "30% PG")
        supply_temp_f: Supply glycol temperature (°F)
        return_temp_f: Return glycol temperature (°F)
        flow_per_loop_gpm: Flow rate per loop (GPM)
        heat_load_btu_per_ft2: Design heat load per ft² (BTU/hr·ft²)
        
    Returns:
        UFWDesignResult with system design parameters
    """
    # Estimate tubes if not provided (based on floor area and loop length)
    if num_tubes is None:
        # Typical tube spacing: 12" on center
        # Length of tubing needed ≈ floor_area / spacing
        total_tubing_ft = floor_area_ft2  # ~1 ft of tube per ft² at 12" spacing
        num_tubes = max(1, int(math.ceil(total_tubing_ft / avg_loop_length_ft)))
    
    total_flow = num_tubes * flow_per_loop_gpm
    heat_load = floor_area_ft2 * heat_load_btu_per_ft2
    
    # Header sizing
    steel_header_limits = {2: 38, 3: 113, 4: 235}  # GPM
    header_size = 3  # Default
    header_adequate = True
    
    for size in sorted(steel_header_limits.keys()):
        if steel_header_limits[size] >= total_flow:
            header_size = size
            break
    else:
        header_size = 4
        if total_flow > 235:
            header_adequate = False
    
    # Pressure drop (from template)
    tubing_pd = 1.4  # psi per 100 ft for 1" CTS HDPE at 3 GPM
    
    # Total pressure drop estimate
    # Tubing: longest loop × 1.4/100
    # Components: inline separator (2 ft), suction diffuser (2.31 ft), HEX (~27 ft)
    tubing_pd_ft = (max_loop_length_ft * tubing_pd / 100) * 2.31  # Convert psi to ft head
    component_pd_ft = 2.0 + 2.31 + 27.0  # From template
    total_pd = tubing_pd_ft + component_pd_ft
    
    result = UFWDesignResult(
        num_tubes=num_tubes,
        avg_loop_length_ft=avg_loop_length_ft,
        max_loop_length_ft=max_loop_length_ft,
        header_size_in=header_size,
        header_length_ft=header_length_ft,
        flow_per_loop_gpm=flow_per_loop_gpm,
        total_flow_gpm=total_flow,
        header_adequate=header_adequate,
        glycol_type=glycol_type,
        supply_temp_f=supply_temp_f,
        return_temp_f=return_temp_f,
        floor_area_ft2=floor_area_ft2,
        heat_load_btuh=heat_load,
        tubing_pd_psi_per_100ft=tubing_pd,
        total_pd_ft_head=total_pd,
    )
    
    if not header_adequate:
        result.notes.append(f"Total flow {total_flow:.0f} GPM exceeds 4\" header limit. Use multiple skids.")
    
    if max_loop_length_ft > 1000:
        result.notes.append("WARNING: Loop length exceeds 1000 ft maximum recommended.")
    
    return result


# ==============================================================================
# SUMP TANK VOLUME
# ==============================================================================

@dataclass
class SumpTankResult:
    """Sump/containment tank volume calculation."""
    footprint_length_ft: float
    footprint_width_ft: float
    plan_area_ft2: float
    
    equipment_water_volume_ft3: float = 0
    pipe_volume_ft3: float = 0
    total_volume_ft3: float = 0
    total_volume_gallons: float = 0
    
    required_depth_ft: float = 0
    notes: List[str] = field(default_factory=list)


def sump_tank_volume(length_ft: float, width_ft: float,
                      equipment_list: List[Dict] = None,
                      pipe_sections: List[Dict] = None,
                      freeboard_factor: float = 1.10) -> SumpTankResult:
    """
    Calculate sump/containment tank volume.
    
    From Sump_tank_volume.xlsx:
        Plan Area = Length × Width
        Equipment water volume from shipping/operating weight difference
        Water volume (ft³) = (Operating WT - Shipping WT) / 62.4
        Pipe volumes = π/4 × D² × L for each section
    
    Args:
        length_ft: Tank length (ft)
        width_ft: Tank width (ft)
        equipment_list: List of equipment dicts with:
            "name": equipment name
            "shipping_weight_lb": dry weight
            "operating_weight_lb": wet weight
        pipe_sections: List of pipe dicts with:
            "nps": nominal pipe size (inches)
            "length_ft": length (feet)
            "schedule": pipe schedule
        freeboard_factor: Safety/freeboard multiplier (default 1.10 = 10%)
        
    Returns:
        SumpTankResult with volumes
    """
    plan_area = length_ft * width_ft
    
    result = SumpTankResult(
        footprint_length_ft=length_ft,
        footprint_width_ft=width_ft,
        plan_area_ft2=plan_area,
    )
    
    # Equipment water volume
    if equipment_list:
        for equip in equipment_list:
            shipping = equip.get("shipping_weight_lb", 0)
            operating = equip.get("operating_weight_lb", 0)
            water_weight = operating - shipping
            water_volume = water_weight / 62.4  # lb / (lb/ft³) = ft³
            result.equipment_water_volume_ft3 += max(0, water_volume)
    
    # Pipe volumes
    if pipe_sections:
        for pipe in pipe_sections:
            nps = pipe.get("nps", 0)
            length = pipe.get("length_ft", 0)
            if nps > 0 and length > 0:
                # Get pipe OD for volume calc
                od_in = nps  # Approximate for large pipe
                if nps in PIPE_ID_MAP:
                    od_in = PIPE_ID_MAP[nps]
                volume = math.pi / 4 * (od_in / 12) ** 2 * length
                result.pipe_volume_ft3 += volume
    
    result.total_volume_ft3 = (result.equipment_water_volume_ft3 + result.pipe_volume_ft3) * freeboard_factor
    result.total_volume_gallons = result.total_volume_ft3 * 7.481
    
    if plan_area > 0:
        result.required_depth_ft = result.total_volume_ft3 / plan_area
    
    return result


# Pipe OD lookup for volume calculations
PIPE_ID_MAP = {
    0.5: 0.840, 0.75: 1.050, 1.0: 1.315, 1.25: 1.660,
    1.5: 1.900, 2.0: 2.375, 2.5: 2.875, 3.0: 3.500,
    4.0: 4.500, 5.0: 5.563, 6.0: 6.625, 8.0: 8.625,
    10.0: 10.750, 12.0: 12.750, 14.0: 14.000, 16.0: 16.000,
    18.0: 18.000, 20.0: 20.000, 24.0: 24.000,
}


# ==============================================================================
# PRESSURE TESTING & NITROGEN CALCULATIONS
# ==============================================================================

@dataclass
class NitrogenCalcResult:
    """Nitrogen volume calculation for pressure testing or purging."""
    # Pipe info
    pipe_diameter_in: float
    pipe_length_ft: float
    
    # Volumes
    pipe_volume_ft3: float = 0
    pipe_volume_gallons: float = 0
    
    # Nitrogen requirements
    test_pressure_psig: float = 0
    atmospheric_pressure_psia: float = 14.696
    pressure_ratio: float = 0  # (test + atm) / atm
    nitrogen_volume_scf: float = 0  # Standard cubic feet at STP
    
    # Cylinder/trailer requirements
    cylinders_200cf: int = 0   # 200 CF cylinder count
    cylinders_300cf: int = 0   # 300 CF cylinder count
    tube_trailers: int = 0     # 45,000 CF tube trailer count
    
    notes: List[str] = field(default_factory=list)


def nitrogen_for_pressure_test(pipe_diameter_in: float, pipe_length_ft: float,
                                test_pressure_psig: float,
                                atmospheric_psia: float = 14.696) -> NitrogenCalcResult:
    """
    Calculate nitrogen required for pressure testing a pipe.
    
    From 114592399PressureTestingandPurgingCalculator1.xls:
        Volume = π/4 × (D/12)² × L
        N2 (SCF) = Volume × (test_pressure + atm) / atm
    
    From 63938910NitrogenCalculationAirgas.xls:
        Cylinder sizes: 200 CF, 300 CF
        Tube trailer: 45,000 CF
    
    Args:
        pipe_diameter_in: Pipe inside diameter (inches)
        pipe_length_ft: Pipe length (feet)
        test_pressure_psig: Test pressure (psig)
        atmospheric_psia: Atmospheric pressure (default 14.696 psia)
        
    Returns:
        NitrogenCalcResult with nitrogen requirements
    """
    # Pipe volume
    diameter_ft = pipe_diameter_in / 12.0
    volume_ft3 = math.pi / 4 * diameter_ft ** 2 * pipe_length_ft
    volume_gal = volume_ft3 * 7.481
    
    # Pressure ratio
    ratio = (test_pressure_psig + atmospheric_psia) / atmospheric_psia
    
    # Nitrogen volume at standard conditions
    n2_scf = volume_ft3 * ratio
    
    # Cylinder counts
    cyl_200 = math.ceil(n2_scf / 200)
    cyl_300 = math.ceil(n2_scf / 300)
    trailers = math.ceil(n2_scf / 45000)
    
    return NitrogenCalcResult(
        pipe_diameter_in=pipe_diameter_in,
        pipe_length_ft=pipe_length_ft,
        pipe_volume_ft3=volume_ft3,
        pipe_volume_gallons=volume_gal,
        test_pressure_psig=test_pressure_psig,
        atmospheric_pressure_psia=atmospheric_psia,
        pressure_ratio=ratio,
        nitrogen_volume_scf=n2_scf,
        cylinders_200cf=cyl_200,
        cylinders_300cf=cyl_300,
        tube_trailers=trailers,
    )


def nitrogen_for_purge(pipe_sections: List[Dict],
                        purge_volumes: int = 3) -> NitrogenCalcResult:
    """
    Calculate nitrogen for purging multiple pipe sections.
    
    Standard practice: purge with 3 volume changes of nitrogen.
    
    Args:
        pipe_sections: List of dicts with "diameter_in" and "length_ft"
        purge_volumes: Number of volume changes (default 3)
        
    Returns:
        NitrogenCalcResult with total nitrogen requirements
    """
    total_ft3 = 0
    for section in pipe_sections:
        d_ft = section["diameter_in"] / 12.0
        vol = math.pi / 4 * d_ft ** 2 * section["length_ft"]
        total_ft3 += vol
    
    n2_scf = total_ft3 * purge_volumes
    
    return NitrogenCalcResult(
        pipe_diameter_in=0,  # Multiple pipes
        pipe_length_ft=0,
        pipe_volume_ft3=total_ft3,
        pipe_volume_gallons=total_ft3 * 7.481,
        nitrogen_volume_scf=n2_scf,
        cylinders_200cf=math.ceil(n2_scf / 200),
        cylinders_300cf=math.ceil(n2_scf / 300),
        tube_trailers=math.ceil(n2_scf / 45000),
        notes=[f"Purge calculation: {purge_volumes} volume changes"]
    )


# ==============================================================================
# BAC COIL ESTIMATOR
# From BAC_Coil_Rating.xls
# ==============================================================================

@dataclass
class CoilEstimate:
    """BAC evaporator coil size estimate."""
    tons_required: float
    evap_temp_f: float
    td_f: float
    air_temp_rise_f: float
    
    approx_airflow_cfm: float = 0
    face_area_required_ft2: float = 0
    target_face_velocity_fpm: float = 0
    coil_material: str = "SS/AL"
    
    notes: List[str] = field(default_factory=list)


def estimate_bac_coil(tons: float, evap_temp_f: float, td_f: float = 14.0,
                       air_temp_rise_f: float = 9.0,
                       target_face_velocity_fpm: float = 1100.0,
                       coil_material: str = "SS/AL") -> CoilEstimate:
    """
    Estimate BAC evaporator coil size.
    
    From BAC_Coil_Rating.xls ESTIMATOR sheet:
        Airflow = (Tons × 12000) / (1.08 × air_temp_rise × 60)
        Face Area = Airflow / target_face_velocity
    
    Args:
        tons: Required cooling capacity (tons)
        evap_temp_f: Evaporating temperature (°F)
        td_f: Temperature difference (°F)
        air_temp_rise_f: Air temperature rise through coil (°F)
        target_face_velocity_fpm: Target face velocity (ft/min)
        coil_material: Coil material (e.g., "SS/AL", "CU/AL")
        
    Returns:
        CoilEstimate with sizing parameters
    """
    # Airflow calculation
    # Q = tons × 12000 BTU/hr
    # CFM = Q / (1.08 × ΔT_air) / 60 ... simplified
    # Actually from spreadsheet: CFM ≈ Q / (ρ × Cp × ΔT) where ρ ≈ 0.075 lb/ft³
    btuh = tons * 12000
    if air_temp_rise_f > 0:
        cfm = btuh / (1.08 * air_temp_rise_f * 60)
        # Corrected formula: CFM = BTU/hr / (0.075 × 0.24 × 60 × ΔT)
        cfm = btuh / (0.075 * 0.24 * 60 * air_temp_rise_f)
    else:
        cfm = 0
    
    face_area = cfm / target_face_velocity_fpm if target_face_velocity_fpm > 0 else 0
    
    return CoilEstimate(
        tons_required=tons,
        evap_temp_f=evap_temp_f,
        td_f=td_f,
        air_temp_rise_f=air_temp_rise_f,
        approx_airflow_cfm=cfm,
        face_area_required_ft2=face_area,
        target_face_velocity_fpm=target_face_velocity_fpm,
        coil_material=coil_material,
    )


# ==============================================================================
# SECONDARY COOLANT PIPING (from Pipeworks spreadsheets)
# ==============================================================================

def glycol_pipe_volume(pipe_sections: List[Dict]) -> float:
    """
    Calculate total pipe volume for glycol charge calculation.
    
    From Pipeworks_Carbon_Steel_Pipe.XLS "Charge" sheet.
    
    Args:
        pipe_sections: List of dicts with "nps", "length_ft", "schedule"
        
    Returns:
        Total volume in gallons
    """
    total_gal = 0
    for section in pipe_sections:
        nps = section.get("nps", 0)
        length = section.get("length_ft", 0)
        
        if nps in PIPE_ID_MAP:
            od = PIPE_ID_MAP[nps]
            # Use approximate ID (OD - 2× typical wall)
            wall = 0.15 if nps <= 2 else 0.25 if nps <= 6 else 0.35
            id_in = od - 2 * wall
        else:
            id_in = nps * 0.9  # rough approximation
        
        vol_ft3 = math.pi / 4 * (id_in / 12) ** 2 * length
        total_gal += vol_ft3 * 7.481
    
    return total_gal


def expansion_tank_size(system_volume_gal: float, glycol_pct: float = 30,
                         min_temp_f: float = 40, max_temp_f: float = 120) -> float:
    """
    Estimate expansion tank size for glycol system.
    
    From Pipeworks spreadsheets "Expansion Tank" sheet.
    Expansion coefficient varies with glycol concentration and temperature.
    
    Typical expansion: ~4-8% of system volume for 30% PG systems.
    
    Args:
        system_volume_gal: Total system volume (gallons)
        glycol_pct: Glycol concentration (%)
        min_temp_f: Minimum system temperature (°F)
        max_temp_f: Maximum system temperature (°F)
        
    Returns:
        Recommended expansion tank size in gallons
    """
    # Expansion coefficient approximation
    # PG at 30%: ~0.00035 per °F
    delta_t = max_temp_f - min_temp_f
    expansion_coeff = 0.00035 * (1 + glycol_pct / 100)  # Higher concentration = more expansion
    
    expansion_volume = system_volume_gal * expansion_coeff * delta_t
    
    # Tank should be ~2× expansion volume (to allow for acceptance volume)
    tank_size = expansion_volume * 2.0
    
    return tank_size


# ==============================================================================
# CARBON vs STAINLESS STEEL COST COMPARISON
# From Carbon_v_SS_price_comparison.xlsx
# ==============================================================================

def pipe_cost_comparison(nps: float, length_ft: float, schedule_carbon: str = "80",
                          include_insulation: bool = True) -> Dict:
    """
    Compare carbon steel vs stainless steel pipe cost.
    
    From Carbon_v_SS_price_comparison.xlsx - approximate unit prices.
    
    Args:
        nps: Nominal pipe size
        length_ft: Linear feet
        schedule_carbon: Carbon steel schedule
        include_insulation: Include insulation cost
        
    Returns:
        Dict with cost comparison
    """
    # Approximate unit prices per foot (from spreadsheet, 2014 pricing)
    carbon_price = {1: 3.78, 1.25: 2.95, 1.5: 4.56, 2: 2.33, 4: 5.30, 6: 9.31, 8: 14.02, 10: 21.19, 12: 25.76}
    ss_price = {1: 4.08, 1.25: 4.08, 1.5: 4.87, 2: 4.47, 4: 8.84, 6: 13.03, 8: 13.03, 10: 15.63, 12: 17.79}
    
    c_unit = carbon_price.get(nps, nps * 2.0)
    s_unit = ss_price.get(nps, nps * 3.0)
    
    # Carbon needs primer/paint, SS does not need painting
    primer_factor = 1.2  # 20% for primer on carbon
    
    carbon_total = length_ft * c_unit * primer_factor
    ss_total = length_ft * s_unit
    
    return {
        "nps": nps,
        "length_ft": length_ft,
        "carbon_cost": round(carbon_total, 2),
        "stainless_cost": round(ss_total, 2),
        "difference": round(ss_total - carbon_total, 2),
        "ss_premium_pct": round((ss_total / carbon_total - 1) * 100, 1) if carbon_total > 0 else 0,
        "note": "2014 approximate pricing - verify current costs",
    }
