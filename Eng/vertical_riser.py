"""
Vertical Suction Riser Sizing Module
======================================

Extracted from: Vertical_Suction_Sizing_VPS.xls (VPS-2010 by David J. Ross)

Calculates vertical piping system (VPS) design for:
- Suction riser sizing with oil return velocity
- DT (temperature difference) penalty from pressure drop
- Liquid column reserve calculation
- Liquid line sizing for recirculated systems

Based on IIAR 2010 methodology and the VPS program.

Key Formulas:
    Suction velocity: V = mass_flow / (ρ_vapor × A_pipe)
    DT penalty: ΔT = Δp / (dP/dT at suction)
    Liquid column reserve: t = V_pipe / Q_liquid (seconds)
    Pressure drop: Δp per Darcy-Weisbach with Moody friction factor
"""

import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict


# ==============================================================================
# NH3 SATURATION PROPERTIES FOR RISER SIZING
# Key properties at common suction temperatures
# ==============================================================================

# {suction_temp_F: (pressure_psia, vapor_density_lb_ft3, liquid_density_lb_ft3,
#                    dp_dt_psi_per_F, latent_heat_btu_lb)}
NH3_RISER_PROPS = {
    -60: (5.55, 0.0205, 43.93, 0.18, 581.0),
    -50: (7.67, 0.0275, 43.38, 0.24, 576.0),
    -40: (10.41, 0.0363, 42.83, 0.31, 571.0),
    -30: (13.90, 0.0475, 42.26, 0.40, 565.0),
    -20: (18.30, 0.0612, 41.68, 0.50, 559.0),
    -10: (23.74, 0.0781, 41.08, 0.63, 553.0),
    0:   (30.42, 0.0986, 40.46, 0.78, 546.0),
    10:  (38.51, 0.1232, 39.82, 0.96, 539.0),
    20:  (48.21, 0.1528, 39.15, 1.17, 531.0),
    28:  (57.65, 0.1810, 38.58, 1.37, 524.0),
    30:  (59.74, 0.1874, 38.46, 1.42, 523.0),
    40:  (73.32, 0.2284, 37.74, 1.71, 514.0),
}


@dataclass
class RiserSizingResult:
    """Vertical suction riser sizing results."""
    # Input summary
    design_type: str = ""           # "Recirculated" or "DX"
    evaporator_config: str = ""     # "one evaporator", "multiple"
    capacity_tons: float = 0
    suction_temp_f: float = 0
    overfeed_rate: float = 4.0      # Recirculation ratio
    evaporator_pd_psi: float = 0.5  # Evaporator pressure drop
    
    # Physical info
    net_liquid_column_ft: float = 0
    net_suction_column_ft: float = 0
    total_liquid_length_ft: float = 0
    
    # Suction line results
    suction_nps: float = 0
    suction_velocity_fps: float = 0
    suction_pd_psi_per_100ft: float = 0
    suction_pd_calculated_psi: float = 0
    dt_penalty_f: float = 0
    calculated_sst_f: float = 0
    
    # Liquid line results
    liquid_nps: float = 0
    liquid_velocity_fps: float = 0
    liquid_pd_psi: float = 0
    liquid_column_reserve_sec: float = 0
    
    # Mass flow
    vapor_mass_flow_lb_min: float = 0
    
    notes: List[str] = field(default_factory=list)


def _interpolate_props(temp_f: float) -> tuple:
    """Interpolate NH3 properties at a given temperature."""
    temps = sorted(NH3_RISER_PROPS.keys())
    
    if temp_f <= temps[0]:
        return NH3_RISER_PROPS[temps[0]]
    if temp_f >= temps[-1]:
        return NH3_RISER_PROPS[temps[-1]]
    
    for i in range(len(temps) - 1):
        if temps[i] <= temp_f <= temps[i + 1]:
            t1, t2 = temps[i], temps[i + 1]
            frac = (temp_f - t1) / (t2 - t1)
            p1 = NH3_RISER_PROPS[t1]
            p2 = NH3_RISER_PROPS[t2]
            return tuple(p1[j] + frac * (p2[j] - p1[j]) for j in range(5))
    
    return NH3_RISER_PROPS[temps[-1]]


# Pipe data for riser calculations {NPS: (ID_inches, area_ft2)}
RISER_PIPE_DATA = {
    1.0:  (1.049, 0.006),
    1.25: (1.380, 0.0104),
    1.5:  (1.610, 0.0141),
    2.0:  (2.067, 0.0233),
    2.5:  (2.469, 0.0332),
    3.0:  (3.068, 0.0513),
    4.0:  (4.026, 0.0884),
    5.0:  (5.047, 0.1389),
    6.0:  (6.065, 0.2006),
    8.0:  (7.981, 0.3474),
    10.0: (10.020, 0.5476),
    12.0: (11.938, 0.7773),
}


def size_vertical_suction_riser(capacity_tons: float,
                                  suction_temp_f: float,
                                  net_suction_height_ft: float,
                                  total_eq_length_ft: float = 100,
                                  overfeed_rate: float = 4.0,
                                  evaporator_pd_psi: float = 0.5,
                                  max_velocity_fps: float = 100,
                                  max_dt_penalty_f: float = 2.0) -> RiserSizingResult:
    """
    Size a vertical suction riser for a recirculated ammonia system.
    
    From VPS-2010 (Vertical_Suction_Sizing_VPS.xls):
        1. Calculate vapor mass flow from capacity and latent heat
        2. Size riser for minimum oil entrainment velocity
        3. Calculate pressure drop and DT penalty
        4. Verify DT penalty is within acceptable limits
    
    Minimum velocity for oil return in vertical risers:
        NH3 suction risers typically need 1500-4000 fpm (25-67 fps)
        depending on pipe size and oil quantity.
    
    Args:
        capacity_tons: Design capacity (tons of refrigeration)
        suction_temp_f: Saturated suction temperature (°F)
        net_suction_height_ft: Net vertical riser height (ft)
        total_eq_length_ft: Total equivalent length including fittings (ft)
        overfeed_rate: Recirculation ratio (e.g., 4:1)
        evaporator_pd_psi: Evaporator pressure drop (psi)
        max_velocity_fps: Maximum acceptable suction velocity (fps)
        max_dt_penalty_f: Maximum acceptable DT penalty (°F)
        
    Returns:
        RiserSizingResult with line sizing details
    """
    props = _interpolate_props(suction_temp_f)
    pressure_psia, rho_vapor, rho_liquid, dp_dt, latent_heat = props
    
    # Mass flow rate
    # Q = capacity × 12000 BTU/hr / latent_heat = lb/hr
    # Convert to lb/min
    mass_flow_lb_hr = capacity_tons * 12000.0 / latent_heat
    mass_flow_lb_min = mass_flow_lb_hr / 60.0
    
    result = RiserSizingResult(
        design_type="Recirculated",
        capacity_tons=capacity_tons,
        suction_temp_f=suction_temp_f,
        overfeed_rate=overfeed_rate,
        evaporator_pd_psi=evaporator_pd_psi,
        net_suction_column_ft=net_suction_height_ft,
        vapor_mass_flow_lb_min=mass_flow_lb_min,
    )
    
    # Size suction riser
    # Try each size and find the one that gives acceptable velocity and DT
    best_size = None
    
    for nps in sorted(RISER_PIPE_DATA.keys()):
        pipe_id, pipe_area = RISER_PIPE_DATA[nps]
        
        # Velocity = mass_flow / (density × area)
        # Volume flow = mass_flow_lb_min / (rho_vapor × 60) in ft³/sec
        volume_flow_fps = mass_flow_lb_min / (rho_vapor * 60.0)  # ft³/sec
        velocity = volume_flow_fps / pipe_area  # ft/sec
        
        if velocity > max_velocity_fps:
            continue  # Too fast
        
        # Pressure drop per 100 ft (simplified Darcy-Weisbach)
        # Δp ≈ f × L × ρ × V² / (2 × D × 144 × gc)
        # Simplified: using chart-based correlation
        f_moody = 0.020  # Typical for steel pipe
        pd_per_100 = (f_moody * 100.0 * rho_vapor * velocity ** 2) / (2 * (pipe_id / 12.0) * 144 * 32.2)
        
        # Calculated pressure drop for actual length
        pd_calc = pd_per_100 * total_eq_length_ft / 100.0
        
        # Add static head for vertical riser (two-phase)
        # Static pd = height × (ρ_vapor × (1-void) + ρ_liquid × void_liquid) / 144
        # For wet suction at overfeed_rate, approximate void fraction
        void_fraction = 0.95  # Mostly vapor in riser
        static_pd = net_suction_height_ft * rho_vapor * (1 - void_fraction) / 144.0
        
        total_pd = pd_calc + static_pd
        
        # DT penalty
        dt_penalty = total_pd / dp_dt if dp_dt > 0 else 0
        
        # Select smallest pipe that meets criteria
        if velocity >= 15.0 and dt_penalty <= max_dt_penalty_f:
            result.suction_nps = nps
            result.suction_velocity_fps = velocity
            result.suction_pd_psi_per_100ft = pd_per_100
            result.suction_pd_calculated_psi = total_pd
            result.dt_penalty_f = dt_penalty
            result.calculated_sst_f = suction_temp_f + dt_penalty
            best_size = nps
            break
    
    if best_size is None:
        # Use largest available
        nps = max(RISER_PIPE_DATA.keys())
        pipe_id, pipe_area = RISER_PIPE_DATA[nps]
        volume_flow_fps = mass_flow_lb_min / (rho_vapor * 60.0)
        velocity = volume_flow_fps / pipe_area
        result.suction_nps = nps
        result.suction_velocity_fps = velocity
        result.notes.append(f"WARNING: Could not meet DT penalty limit with available pipe sizes.")
    
    # Size liquid line
    # Liquid flow = capacity_tons × 12000 / latent_heat × overfeed_rate / (60 × rho_liquid)
    liquid_volume_gpm = (mass_flow_lb_min * overfeed_rate) / (rho_liquid / 7.481)
    
    for nps in sorted(RISER_PIPE_DATA.keys()):
        pipe_id, pipe_area = RISER_PIPE_DATA[nps]
        liq_velocity = (liquid_volume_gpm / 7.481 / 60) / pipe_area
        
        if liq_velocity <= 3.0:  # Max ~3 fps for liquid
            result.liquid_nps = nps
            result.liquid_velocity_fps = liq_velocity
            
            # Column reserve (seconds of liquid supply in pipe)
            pipe_volume_ft3 = pipe_area * net_suction_height_ft
            flow_ft3_per_sec = liquid_volume_gpm / 7.481 / 60
            if flow_ft3_per_sec > 0:
                result.liquid_column_reserve_sec = pipe_volume_ft3 / flow_ft3_per_sec
            break
    
    return result


# ==============================================================================
# QUICK FUNCTIONS
# ==============================================================================

def quick_riser_size(tons: float, sst_f: float, height_ft: float = 12.0) -> str:
    """
    Quick vertical suction riser sizing.
    
    Returns a summary string with recommended pipe size.
    """
    result = size_vertical_suction_riser(tons, sst_f, height_ft)
    return (f"Suction riser: {result.suction_nps}\" NPS @ {result.suction_velocity_fps:.1f} fps, "
            f"DT penalty: {result.dt_penalty_f:.2f}°F | "
            f"Liquid line: {result.liquid_nps}\" NPS @ {result.liquid_velocity_fps:.2f} fps")
