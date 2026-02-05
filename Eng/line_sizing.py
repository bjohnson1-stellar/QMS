"""
Line Sizing Module
==================

Calculate pipe sizes for refrigerant lines including:
- Suction lines (wet and dry)
- Discharge (hot gas) lines  
- Liquid lines
- Two-phase lines

Based on ASHRAE and IIAR guidelines.
"""

import math
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from .properties import RefrigerantProperties, NH3Properties, get_refrigerant


class PipeSchedule(Enum):
    """Standard pipe schedules."""
    SCH_40 = "Schedule 40"
    SCH_80 = "Schedule 80"
    SCH_10 = "Schedule 10"
    SCH_10S = "Schedule 10S"
    CS_150 = "Carbon Steel 150#"
    CS_300 = "Carbon Steel 300#"


@dataclass
class PipeData:
    """Standard pipe dimensions."""
    nominal_size: float  # inches
    schedule: str
    outer_diameter: float  # inches
    inner_diameter: float  # inches
    wall_thickness: float  # inches
    weight_per_foot: float  # lb/ft
    
    @property
    def inner_area_ft2(self) -> float:
        """Inner cross-sectional area in ft²."""
        return math.pi * (self.inner_diameter / 12) ** 2 / 4
    
    @property
    def inner_area_in2(self) -> float:
        """Inner cross-sectional area in in²."""
        return math.pi * self.inner_diameter ** 2 / 4


# Standard pipe dimensions (Schedule 40, commonly used for refrigeration)
PIPE_DATA = {
    0.5: PipeData(0.5, "SCH40", 0.840, 0.622, 0.109, 0.85),
    0.75: PipeData(0.75, "SCH40", 1.050, 0.824, 0.113, 1.13),
    1.0: PipeData(1.0, "SCH40", 1.315, 1.049, 0.133, 1.68),
    1.25: PipeData(1.25, "SCH40", 1.660, 1.380, 0.140, 2.27),
    1.5: PipeData(1.5, "SCH40", 1.900, 1.610, 0.145, 2.72),
    2.0: PipeData(2.0, "SCH40", 2.375, 2.067, 0.154, 3.65),
    2.5: PipeData(2.5, "SCH40", 2.875, 2.469, 0.203, 5.79),
    3.0: PipeData(3.0, "SCH40", 3.500, 3.068, 0.216, 7.58),
    4.0: PipeData(4.0, "SCH40", 4.500, 4.026, 0.237, 10.79),
    5.0: PipeData(5.0, "SCH40", 5.563, 5.047, 0.258, 14.62),
    6.0: PipeData(6.0, "SCH40", 6.625, 6.065, 0.280, 18.97),
    8.0: PipeData(8.0, "SCH40", 8.625, 7.981, 0.322, 28.55),
    10.0: PipeData(10.0, "SCH40", 10.750, 10.020, 0.365, 40.48),
    12.0: PipeData(12.0, "SCH40", 12.750, 11.938, 0.406, 53.52),
    14.0: PipeData(14.0, "SCH40", 14.000, 13.126, 0.437, 63.30),
    16.0: PipeData(16.0, "SCH40", 16.000, 15.000, 0.500, 82.77),
    18.0: PipeData(18.0, "SCH40", 18.000, 16.876, 0.562, 104.67),
    20.0: PipeData(20.0, "SCH40", 20.000, 18.814, 0.593, 122.91),
    24.0: PipeData(24.0, "SCH40", 24.000, 22.626, 0.687, 171.17),
}

# Standard pipe sizes in order
STANDARD_SIZES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 24.0]

# Equivalent lengths for fittings (in pipe diameters)
FITTING_EQ_LENGTH = {
    '90_elbow': 30,         # 90° elbow, standard radius
    '90_elbow_lr': 20,      # 90° elbow, long radius
    '45_elbow': 16,         # 45° elbow
    'tee_thru': 20,         # Tee, flow through run
    'tee_branch': 60,       # Tee, flow through branch
    'gate_valve': 8,        # Gate valve, fully open
    'globe_valve': 340,     # Globe valve, fully open
    'angle_valve': 150,     # Angle valve
    'check_valve': 100,     # Check valve, swing type
    'ball_valve': 3,        # Ball valve, fully open
    'butterfly_valve': 20,  # Butterfly valve
}


@dataclass
class LineSizingResult:
    """Results from line sizing calculation."""
    nominal_size: float          # inches
    inner_diameter: float        # inches
    velocity: float              # ft/s
    pressure_drop_per_100ft: float  # psi/100ft
    temp_drop_per_100ft: float   # °F/100ft
    total_pressure_drop: float   # psi
    total_temp_drop: float       # °F
    total_length: float          # ft (including equivalent lengths)
    mass_flow_rate: float        # lb/min
    reynolds_number: float
    friction_factor: float
    

class LineSizing:
    """
    Refrigerant line sizing calculator.
    
    Calculates pipe sizes based on:
    - Capacity (tons of refrigeration)
    - Line type (suction, discharge, liquid)
    - Operating temperatures
    - Allowable pressure/temperature drop
    
    Example:
        >>> sizing = LineSizing('NH3')
        >>> result = sizing.size_suction_line(
        ...     capacity_tons=100,
        ...     suction_temp=20,
        ...     condensing_temp=95,
        ...     total_length=150,
        ...     num_90_elbows=4,
        ...     line_type='dry'
        ... )
        >>> print(f"Recommended size: {result.nominal_size}\" at {result.velocity:.1f} ft/s")
    """
    
    # Recommended velocity limits (ft/s)
    VELOCITY_LIMITS = {
        'suction_dry': {'min': 15, 'max': 60, 'typical': 40},
        'suction_wet': {'min': 10, 'max': 30, 'typical': 20},
        'discharge': {'min': 15, 'max': 50, 'typical': 35},
        'liquid': {'min': 2, 'max': 6, 'typical': 4},
        'liquid_gravity': {'min': 0.5, 'max': 2, 'typical': 1},
    }
    
    # Recommended pressure drop limits (psi/100ft)
    PRESSURE_DROP_LIMITS = {
        'suction': {'max': 0.5, 'typical': 0.25},
        'discharge': {'max': 2.0, 'typical': 1.0},
        'liquid': {'max': 3.0, 'typical': 1.5},
    }
    
    def __init__(self, refrigerant: Union[str, RefrigerantProperties] = 'NH3'):
        """
        Initialize line sizing calculator.
        
        Args:
            refrigerant: Refrigerant name or RefrigerantProperties object
        """
        if isinstance(refrigerant, str):
            self.refrigerant = get_refrigerant(refrigerant)
        else:
            self.refrigerant = refrigerant
    
    def size_suction_line(
        self,
        capacity_tons: float,
        suction_temp: float,
        condensing_temp: float,
        total_length: float,
        num_90_elbows: int = 0,
        num_45_elbows: int = 0,
        num_tees: int = 0,
        num_valves: int = 0,
        recirculation_rate: float = 1.0,
        line_type: str = 'dry',
        max_velocity: Optional[float] = None,
        max_pressure_drop: Optional[float] = None,
    ) -> LineSizingResult:
        """
        Size a suction line.
        
        Args:
            capacity_tons: Refrigeration capacity in tons
            suction_temp: Suction temperature (°F)
            condensing_temp: Condensing temperature (°F)
            total_length: Straight pipe length (ft)
            num_90_elbows: Number of 90° elbows
            num_45_elbows: Number of 45° elbows
            num_tees: Number of tees (branch flow)
            num_valves: Number of valves
            recirculation_rate: Recirculation rate for wet suction (default 1.0)
            line_type: 'dry' for superheated vapor, 'wet' for two-phase
            max_velocity: Maximum allowable velocity (ft/s)
            max_pressure_drop: Maximum allowable pressure drop (psi/100ft)
        
        Returns:
            LineSizingResult with recommended pipe size and flow parameters
        """
        # Get refrigerant properties
        props = self.refrigerant.get_properties_at_temp(suction_temp)
        props_cond = self.refrigerant.get_properties_at_temp(condensing_temp)
        
        # Calculate mass flow rate
        # Q (BTU/hr) = tons * 12000
        # Mass flow (lb/hr) = Q / latent_heat
        q_btu_hr = capacity_tons * 12000
        latent_heat = props_cond.vapor_enthalpy - props.liquid_enthalpy
        if latent_heat <= 0:
            latent_heat = props.latent_heat if props.latent_heat > 0 else 500
        
        mass_flow_lb_hr = q_btu_hr / latent_heat
        mass_flow_lb_min = mass_flow_lb_hr / 60
        
        # Adjust for recirculation if wet suction
        if line_type == 'wet' and recirculation_rate > 1:
            mass_flow_lb_min *= recirculation_rate
        
        # Get density
        if line_type == 'dry':
            density = props.vapor_density
        else:
            # Two-phase density estimate
            quality = 1 / recirculation_rate if recirculation_rate > 0 else 0.5
            density = 1 / (quality / props.vapor_density + (1 - quality) / props.liquid_density)
        
        # Calculate volumetric flow rate
        vol_flow_cfm = mass_flow_lb_min / density
        
        # Set velocity limits
        if max_velocity is None:
            if line_type == 'dry':
                max_velocity = self.VELOCITY_LIMITS['suction_dry']['max']
            else:
                max_velocity = self.VELOCITY_LIMITS['suction_wet']['max']
        
        if max_pressure_drop is None:
            max_pressure_drop = self.PRESSURE_DROP_LIMITS['suction']['max']
        
        # Find suitable pipe size
        for size in STANDARD_SIZES:
            pipe = PIPE_DATA[size]
            
            # Calculate velocity
            area_ft2 = pipe.inner_area_ft2
            velocity = vol_flow_cfm / (area_ft2 * 60)  # ft/s
            
            # Calculate equivalent length
            eq_length = self._calculate_equivalent_length(
                pipe.inner_diameter, num_90_elbows, num_45_elbows, num_tees, num_valves
            )
            total_eq_length = total_length + eq_length
            
            # Calculate pressure drop
            pressure_drop_100ft, reynolds, friction = self._calculate_pressure_drop(
                mass_flow_lb_min, pipe.inner_diameter, density, 
                props.vapor_viscosity if line_type == 'dry' else props.liquid_viscosity
            )
            
            # Calculate temperature drop
            temp_drop_100ft = self._estimate_temp_drop(pressure_drop_100ft, props)
            
            # Check if this size meets criteria
            if velocity <= max_velocity and pressure_drop_100ft <= max_pressure_drop:
                total_pressure_drop = pressure_drop_100ft * total_eq_length / 100
                total_temp_drop = temp_drop_100ft * total_eq_length / 100
                
                return LineSizingResult(
                    nominal_size=size,
                    inner_diameter=pipe.inner_diameter,
                    velocity=velocity,
                    pressure_drop_per_100ft=pressure_drop_100ft,
                    temp_drop_per_100ft=temp_drop_100ft,
                    total_pressure_drop=total_pressure_drop,
                    total_temp_drop=total_temp_drop,
                    total_length=total_eq_length,
                    mass_flow_rate=mass_flow_lb_min,
                    reynolds_number=reynolds,
                    friction_factor=friction,
                )
        
        # Return largest size if none meet criteria
        pipe = PIPE_DATA[STANDARD_SIZES[-1]]
        area_ft2 = pipe.inner_area_ft2
        velocity = vol_flow_cfm / (area_ft2 * 60)
        eq_length = self._calculate_equivalent_length(
            pipe.inner_diameter, num_90_elbows, num_45_elbows, num_tees, num_valves
        )
        pressure_drop_100ft, reynolds, friction = self._calculate_pressure_drop(
            mass_flow_lb_min, pipe.inner_diameter, density,
            props.vapor_viscosity if line_type == 'dry' else props.liquid_viscosity
        )
        temp_drop_100ft = self._estimate_temp_drop(pressure_drop_100ft, props)
        
        return LineSizingResult(
            nominal_size=STANDARD_SIZES[-1],
            inner_diameter=pipe.inner_diameter,
            velocity=velocity,
            pressure_drop_per_100ft=pressure_drop_100ft,
            temp_drop_per_100ft=temp_drop_100ft,
            total_pressure_drop=pressure_drop_100ft * (total_length + eq_length) / 100,
            total_temp_drop=temp_drop_100ft * (total_length + eq_length) / 100,
            total_length=total_length + eq_length,
            mass_flow_rate=mass_flow_lb_min,
            reynolds_number=reynolds,
            friction_factor=friction,
        )
    
    def size_discharge_line(
        self,
        capacity_tons: float,
        discharge_temp: float,
        condensing_temp: float,
        total_length: float,
        num_90_elbows: int = 0,
        num_45_elbows: int = 0,
        num_tees: int = 0,
        num_valves: int = 0,
        max_velocity: Optional[float] = None,
        max_pressure_drop: Optional[float] = None,
    ) -> LineSizingResult:
        """
        Size a discharge (hot gas) line.
        
        Args:
            capacity_tons: Refrigeration capacity in tons
            discharge_temp: Discharge temperature (°F)
            condensing_temp: Condensing temperature (°F)
            total_length: Straight pipe length (ft)
            num_90_elbows: Number of 90° elbows
            num_45_elbows: Number of 45° elbows
            num_tees: Number of tees
            num_valves: Number of valves
            max_velocity: Maximum allowable velocity (ft/s)
            max_pressure_drop: Maximum allowable pressure drop (psi/100ft)
        
        Returns:
            LineSizingResult with recommended pipe size
        """
        props = self.refrigerant.get_properties_at_temp(condensing_temp)
        
        # Calculate mass flow rate
        q_btu_hr = capacity_tons * 12000
        latent_heat = props.latent_heat if props.latent_heat > 0 else 500
        mass_flow_lb_min = q_btu_hr / latent_heat / 60
        
        # Discharge line uses superheated vapor density at condensing pressure
        # Approximate as saturated vapor at condensing temp (conservative)
        density = props.vapor_density
        vol_flow_cfm = mass_flow_lb_min / density
        
        if max_velocity is None:
            max_velocity = self.VELOCITY_LIMITS['discharge']['max']
        if max_pressure_drop is None:
            max_pressure_drop = self.PRESSURE_DROP_LIMITS['discharge']['max']
        
        for size in STANDARD_SIZES:
            pipe = PIPE_DATA[size]
            area_ft2 = pipe.inner_area_ft2
            velocity = vol_flow_cfm / (area_ft2 * 60)
            
            eq_length = self._calculate_equivalent_length(
                pipe.inner_diameter, num_90_elbows, num_45_elbows, num_tees, num_valves
            )
            
            pressure_drop_100ft, reynolds, friction = self._calculate_pressure_drop(
                mass_flow_lb_min, pipe.inner_diameter, density, props.vapor_viscosity
            )
            
            if velocity <= max_velocity and pressure_drop_100ft <= max_pressure_drop:
                total_eq_length = total_length + eq_length
                return LineSizingResult(
                    nominal_size=size,
                    inner_diameter=pipe.inner_diameter,
                    velocity=velocity,
                    pressure_drop_per_100ft=pressure_drop_100ft,
                    temp_drop_per_100ft=0,  # Discharge temp drop not typically calculated
                    total_pressure_drop=pressure_drop_100ft * total_eq_length / 100,
                    total_temp_drop=0,
                    total_length=total_eq_length,
                    mass_flow_rate=mass_flow_lb_min,
                    reynolds_number=reynolds,
                    friction_factor=friction,
                )
        
        # Return largest
        pipe = PIPE_DATA[STANDARD_SIZES[-1]]
        area_ft2 = pipe.inner_area_ft2
        velocity = vol_flow_cfm / (area_ft2 * 60)
        eq_length = self._calculate_equivalent_length(
            pipe.inner_diameter, num_90_elbows, num_45_elbows, num_tees, num_valves
        )
        pressure_drop_100ft, reynolds, friction = self._calculate_pressure_drop(
            mass_flow_lb_min, pipe.inner_diameter, density, props.vapor_viscosity
        )
        
        return LineSizingResult(
            nominal_size=STANDARD_SIZES[-1],
            inner_diameter=pipe.inner_diameter,
            velocity=velocity,
            pressure_drop_per_100ft=pressure_drop_100ft,
            temp_drop_per_100ft=0,
            total_pressure_drop=pressure_drop_100ft * (total_length + eq_length) / 100,
            total_temp_drop=0,
            total_length=total_length + eq_length,
            mass_flow_rate=mass_flow_lb_min,
            reynolds_number=reynolds,
            friction_factor=friction,
        )
    
    def size_liquid_line(
        self,
        capacity_tons: float,
        liquid_temp: float,
        condensing_temp: float,
        total_length: float,
        num_90_elbows: int = 0,
        num_45_elbows: int = 0,
        num_tees: int = 0,
        num_valves: int = 0,
        recirculation_rate: float = 1.0,
        max_velocity: Optional[float] = None,
        max_pressure_drop: Optional[float] = None,
    ) -> LineSizingResult:
        """
        Size a liquid line.
        
        Args:
            capacity_tons: Refrigeration capacity in tons
            liquid_temp: Liquid temperature (°F)
            condensing_temp: Condensing temperature (°F)
            total_length: Straight pipe length (ft)
            num_90_elbows: Number of 90° elbows
            num_45_elbows: Number of 45° elbows
            num_tees: Number of tees
            num_valves: Number of valves
            recirculation_rate: Liquid recirculation rate (for pumped systems)
            max_velocity: Maximum allowable velocity (ft/s)
            max_pressure_drop: Maximum allowable pressure drop (psi/100ft)
        
        Returns:
            LineSizingResult with recommended pipe size
        """
        props = self.refrigerant.get_properties_at_temp(liquid_temp)
        props_cond = self.refrigerant.get_properties_at_temp(condensing_temp)
        
        # Calculate mass flow rate
        q_btu_hr = capacity_tons * 12000
        latent_heat = props_cond.latent_heat if props_cond.latent_heat > 0 else 500
        mass_flow_lb_min = q_btu_hr / latent_heat / 60 * recirculation_rate
        
        density = props.liquid_density
        vol_flow_cfm = mass_flow_lb_min / density
        
        if max_velocity is None:
            max_velocity = self.VELOCITY_LIMITS['liquid']['max']
        if max_pressure_drop is None:
            max_pressure_drop = self.PRESSURE_DROP_LIMITS['liquid']['max']
        
        for size in STANDARD_SIZES:
            pipe = PIPE_DATA[size]
            area_ft2 = pipe.inner_area_ft2
            velocity = vol_flow_cfm / (area_ft2 * 60)
            
            eq_length = self._calculate_equivalent_length(
                pipe.inner_diameter, num_90_elbows, num_45_elbows, num_tees, num_valves
            )
            
            pressure_drop_100ft, reynolds, friction = self._calculate_pressure_drop(
                mass_flow_lb_min, pipe.inner_diameter, density, props.liquid_viscosity
            )
            
            if velocity <= max_velocity and pressure_drop_100ft <= max_pressure_drop:
                total_eq_length = total_length + eq_length
                return LineSizingResult(
                    nominal_size=size,
                    inner_diameter=pipe.inner_diameter,
                    velocity=velocity,
                    pressure_drop_per_100ft=pressure_drop_100ft,
                    temp_drop_per_100ft=0,
                    total_pressure_drop=pressure_drop_100ft * total_eq_length / 100,
                    total_temp_drop=0,
                    total_length=total_eq_length,
                    mass_flow_rate=mass_flow_lb_min,
                    reynolds_number=reynolds,
                    friction_factor=friction,
                )
        
        # Return largest
        pipe = PIPE_DATA[STANDARD_SIZES[-1]]
        area_ft2 = pipe.inner_area_ft2
        velocity = vol_flow_cfm / (area_ft2 * 60)
        eq_length = self._calculate_equivalent_length(
            pipe.inner_diameter, num_90_elbows, num_45_elbows, num_tees, num_valves
        )
        pressure_drop_100ft, reynolds, friction = self._calculate_pressure_drop(
            mass_flow_lb_min, pipe.inner_diameter, density, props.liquid_viscosity
        )
        
        return LineSizingResult(
            nominal_size=STANDARD_SIZES[-1],
            inner_diameter=pipe.inner_diameter,
            velocity=velocity,
            pressure_drop_per_100ft=pressure_drop_100ft,
            temp_drop_per_100ft=0,
            total_pressure_drop=pressure_drop_100ft * (total_length + eq_length) / 100,
            total_temp_drop=0,
            total_length=total_length + eq_length,
            mass_flow_rate=mass_flow_lb_min,
            reynolds_number=reynolds,
            friction_factor=friction,
        )
    
    def _calculate_equivalent_length(
        self,
        pipe_diameter: float,
        num_90: int,
        num_45: int,
        num_tees: int,
        num_valves: int,
    ) -> float:
        """Calculate equivalent length of fittings in feet."""
        eq_length = 0
        d_ft = pipe_diameter / 12
        
        eq_length += num_90 * FITTING_EQ_LENGTH['90_elbow'] * d_ft
        eq_length += num_45 * FITTING_EQ_LENGTH['45_elbow'] * d_ft
        eq_length += num_tees * FITTING_EQ_LENGTH['tee_branch'] * d_ft
        eq_length += num_valves * FITTING_EQ_LENGTH['gate_valve'] * d_ft
        
        return eq_length
    
    def _calculate_pressure_drop(
        self,
        mass_flow_lb_min: float,
        diameter_in: float,
        density: float,
        viscosity: float,
    ) -> Tuple[float, float, float]:
        """
        Calculate pressure drop using Darcy-Weisbach equation.
        
        Returns:
            Tuple of (pressure_drop_psi_per_100ft, reynolds_number, friction_factor)
        """
        # Convert units
        diameter_ft = diameter_in / 12
        area_ft2 = math.pi * diameter_ft ** 2 / 4
        
        # Velocity in ft/s
        vol_flow_cfs = mass_flow_lb_min / density / 60
        velocity = vol_flow_cfs / area_ft2
        
        # Reynolds number
        # Re = ρVD/μ, with μ in lbm/ft-hr, need to convert
        viscosity_lb_ft_s = viscosity / 3600  # Convert from lb/ft-hr to lb/ft-s
        if viscosity_lb_ft_s > 0:
            reynolds = density * velocity * diameter_ft / viscosity_lb_ft_s
        else:
            reynolds = 100000  # Assume turbulent
        
        # Friction factor (Colebrook-White approximation for steel pipe)
        roughness = 0.00015  # ft, for commercial steel
        rel_roughness = roughness / diameter_ft
        
        if reynolds < 2300:
            # Laminar flow
            friction = 64 / reynolds if reynolds > 0 else 0.04
        else:
            # Turbulent flow - use Swamee-Jain approximation
            friction = 0.25 / (math.log10(rel_roughness / 3.7 + 5.74 / reynolds ** 0.9)) ** 2
        
        # Darcy-Weisbach: ΔP = f * (L/D) * (ρV²/2)
        # For 100 ft: ΔP = f * (100/D) * (ρV²/2) / 144 (convert to psi)
        pressure_drop_100ft = friction * (100 / diameter_ft) * (density * velocity ** 2 / 2) / 144 / 32.174
        
        return pressure_drop_100ft, reynolds, friction
    
    def _estimate_temp_drop(self, pressure_drop: float, props) -> float:
        """Estimate temperature drop corresponding to pressure drop."""
        # Approximate using Clausius-Clapeyron
        # dT/dP ≈ T * v_fg / h_fg
        # For ammonia, approximately 2°F per psi at low temperatures
        if props.latent_heat > 0 and props.pressure_psia > 0:
            # More accurate calculation
            v_fg = 1 / props.vapor_density - 1 / props.liquid_density
            T_abs = props.temperature_f + 459.67  # Rankine
            dT_dP = T_abs * v_fg / (props.latent_heat * 778.16)  # Convert BTU to ft-lbf
            return pressure_drop * dT_dP * 144  # Convert psi to lbf/ft²
        else:
            # Fallback estimate
            return pressure_drop * 2  # Rough estimate: 2°F per psi


def calculate_velocity(
    mass_flow_lb_min: float,
    pipe_size: float,
    density: float,
) -> float:
    """
    Calculate velocity in a pipe.
    
    Args:
        mass_flow_lb_min: Mass flow rate (lb/min)
        pipe_size: Nominal pipe size (inches)
        density: Fluid density (lb/ft³)
    
    Returns:
        Velocity in ft/s
    """
    pipe = PIPE_DATA.get(pipe_size)
    if pipe is None:
        raise ValueError(f"Invalid pipe size: {pipe_size}")
    
    vol_flow_cfs = mass_flow_lb_min / density / 60
    velocity = vol_flow_cfs / pipe.inner_area_ft2
    
    return velocity
