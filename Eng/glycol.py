"""
Secondary Coolant Properties Module
====================================

Properties and calculations for secondary coolants:
- Propylene glycol
- Ethylene glycol
- Calcium chloride brine
- Sodium chloride brine
- Potassium formate

Includes freeze point, viscosity, specific heat, and system design.
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class CoolantType(Enum):
    """Types of secondary coolants."""
    PROPYLENE_GLYCOL = "propylene_glycol"
    ETHYLENE_GLYCOL = "ethylene_glycol"
    CALCIUM_CHLORIDE = "calcium_chloride"
    SODIUM_CHLORIDE = "sodium_chloride"
    POTASSIUM_FORMATE = "potassium_formate"


@dataclass
class CoolantProperties:
    """Properties of a secondary coolant at specific conditions."""
    coolant_type: str
    concentration: float        # % by weight
    temperature: float          # °F
    freeze_point: float         # °F
    specific_gravity: float     # dimensionless
    density: float              # lb/ft³
    specific_heat: float        # BTU/lb-°F
    viscosity: float            # cP
    thermal_conductivity: float # BTU/hr-ft-°F


@dataclass
class GlycolSystemResult:
    """Results from glycol system calculation."""
    coolant_type: str
    concentration_percent: float
    freeze_point: float
    flow_rate_gpm: float
    velocity_fps: float
    pressure_drop_ft_hd: float
    pump_hp: float
    heat_transfer_penalty: float
    pipe_size_in: float
    notes: List[str]


class SecondaryRefrigerantCalculator:
    """
    Secondary coolant property and system calculator.
    
    Example:
        >>> calc = SecondaryRefrigerantCalculator()
        >>> props = calc.get_properties(
        ...     coolant_type=CoolantType.PROPYLENE_GLYCOL,
        ...     concentration=30,
        ...     temperature=25
        ... )
        >>> print(f"Freeze point: {props.freeze_point}°F")
    """
    
    # Propylene glycol properties by concentration (% by weight)
    # (concentration, freeze_point, sg_at_60F, specific_heat)
    PROPYLENE_GLYCOL_DATA = {
        0:  (32.0, 1.000, 1.00),
        10: (26.0, 1.010, 0.98),
        20: (18.0, 1.020, 0.95),
        25: (12.0, 1.025, 0.93),
        30: (5.0, 1.030, 0.91),
        35: (-3.0, 1.035, 0.89),
        40: (-12.0, 1.040, 0.87),
        45: (-23.0, 1.045, 0.85),
        50: (-35.0, 1.050, 0.83),
        55: (-50.0, 1.052, 0.81),
        60: (-65.0, 1.055, 0.79),
    }
    
    # Ethylene glycol properties by concentration
    ETHYLENE_GLYCOL_DATA = {
        0:  (32.0, 1.000, 1.00),
        10: (26.0, 1.013, 0.97),
        20: (17.0, 1.027, 0.93),
        25: (11.0, 1.034, 0.91),
        30: (4.0, 1.041, 0.88),
        35: (-5.0, 1.048, 0.85),
        40: (-15.0, 1.055, 0.82),
        45: (-27.0, 1.062, 0.79),
        50: (-40.0, 1.069, 0.76),
        55: (-55.0, 1.076, 0.74),
        60: (-70.0, 1.083, 0.72),
    }
    
    # Calcium chloride brine properties
    CACL2_DATA = {
        0:  (32.0, 1.000, 1.00),
        10: (20.0, 1.085, 0.88),
        15: (10.0, 1.130, 0.82),
        20: (-5.0, 1.175, 0.76),
        25: (-30.0, 1.223, 0.70),
        29: (-58.0, 1.270, 0.65),  # Eutectic
    }
    
    # Sodium chloride brine properties
    NACL_DATA = {
        0:  (32.0, 1.000, 1.00),
        5:  (27.0, 1.034, 0.94),
        10: (20.0, 1.070, 0.88),
        15: (12.0, 1.108, 0.82),
        20: (2.0, 1.146, 0.77),
        23: (-6.0, 1.175, 0.73),  # Eutectic
    }
    
    # Viscosity multipliers (vs water) by temperature
    VISCOSITY_TEMP_FACTOR = {
        # (temp_F): multiplier
        60: 1.0,
        40: 1.5,
        20: 2.5,
        0: 4.5,
        -20: 8.0,
        -40: 15.0,
    }
    
    def __init__(self):
        pass
    
    def get_properties(
        self,
        coolant_type: CoolantType,
        concentration: float,
        temperature: float,
    ) -> CoolantProperties:
        """
        Get coolant properties at specified conditions.
        
        Args:
            coolant_type: Type of coolant
            concentration: Concentration (% by weight)
            temperature: Operating temperature (°F)
        
        Returns:
            CoolantProperties dataclass
        """
        # Get base data for coolant type
        if coolant_type == CoolantType.PROPYLENE_GLYCOL:
            data = self.PROPYLENE_GLYCOL_DATA
        elif coolant_type == CoolantType.ETHYLENE_GLYCOL:
            data = self.ETHYLENE_GLYCOL_DATA
        elif coolant_type == CoolantType.CALCIUM_CHLORIDE:
            data = self.CACL2_DATA
        elif coolant_type == CoolantType.SODIUM_CHLORIDE:
            data = self.NACL_DATA
        else:
            # Default to propylene glycol
            data = self.PROPYLENE_GLYCOL_DATA
        
        # Interpolate properties
        freeze_point, sg, cp = self._interpolate_properties(data, concentration)
        
        # Adjust specific gravity for temperature
        sg_adjusted = sg * (1 - 0.0003 * (temperature - 60))
        
        # Density
        density = sg_adjusted * 62.4  # lb/ft³
        
        # Viscosity (cP)
        viscosity = self._calculate_viscosity(coolant_type, concentration, temperature)
        
        # Thermal conductivity
        k_water = 0.36  # BTU/hr-ft-°F at 60°F
        k_factor = 1 - 0.005 * concentration  # Reduces with concentration
        thermal_conductivity = k_water * k_factor
        
        return CoolantProperties(
            coolant_type=coolant_type.value,
            concentration=concentration,
            temperature=temperature,
            freeze_point=freeze_point,
            specific_gravity=sg_adjusted,
            density=density,
            specific_heat=cp,
            viscosity=viscosity,
            thermal_conductivity=thermal_conductivity,
        )
    
    def required_concentration(
        self,
        coolant_type: CoolantType,
        lowest_temperature: float,
        safety_margin: float = 10,
    ) -> float:
        """
        Determine required concentration for operating temperature.
        
        Args:
            coolant_type: Type of coolant
            lowest_temperature: Lowest expected operating temperature (°F)
            safety_margin: Safety margin below freeze point (°F)
        
        Returns:
            Required concentration (% by weight)
        """
        target_freeze = lowest_temperature - safety_margin
        
        # Get data for coolant type
        if coolant_type == CoolantType.PROPYLENE_GLYCOL:
            data = self.PROPYLENE_GLYCOL_DATA
        elif coolant_type == CoolantType.ETHYLENE_GLYCOL:
            data = self.ETHYLENE_GLYCOL_DATA
        elif coolant_type == CoolantType.CALCIUM_CHLORIDE:
            data = self.CACL2_DATA
        elif coolant_type == CoolantType.SODIUM_CHLORIDE:
            data = self.NACL_DATA
        else:
            data = self.PROPYLENE_GLYCOL_DATA
        
        # Find concentration that gives required freeze point
        for conc in sorted(data.keys()):
            fp, _, _ = data[conc]
            if fp <= target_freeze:
                return conc
        
        return max(data.keys())  # Maximum concentration
    
    def size_glycol_system(
        self,
        coolant_type: CoolantType,
        capacity_tons: float,
        supply_temp: float,
        return_temp: float,
        pipe_length_ft: float,
        num_elbows: int = 10,
    ) -> GlycolSystemResult:
        """
        Size a glycol/brine piping system.
        
        Args:
            coolant_type: Type of coolant
            capacity_tons: Required cooling capacity (tons)
            supply_temp: Supply temperature (°F)
            return_temp: Return temperature (°F)
            pipe_length_ft: Total equivalent pipe length (ft)
            num_elbows: Number of elbows
        
        Returns:
            GlycolSystemResult with system sizing
        """
        notes = []
        
        # Determine required concentration
        concentration = self.required_concentration(coolant_type, supply_temp)
        
        # Get properties at average temperature
        avg_temp = (supply_temp + return_temp) / 2
        props = self.get_properties(coolant_type, concentration, avg_temp)
        
        notes.append(f"Freeze point: {props.freeze_point}°F")
        
        # Temperature difference
        delta_t = return_temp - supply_temp
        if delta_t <= 0:
            delta_t = 10
            notes.append("Warning: Using default 10°F temperature range")
        
        # Required flow rate
        # Q = m_dot * Cp * ΔT
        heat_load_btu_hr = capacity_tons * 12000
        mass_flow_lb_hr = heat_load_btu_hr / (props.specific_heat * delta_t)
        vol_flow_gpm = mass_flow_lb_hr / (props.density * 60 / 7.48)
        
        notes.append(f"Flow rate: {vol_flow_gpm:.1f} GPM")
        
        # Size pipe for 4-8 ft/s velocity
        target_velocity = 6  # ft/s
        pipe_area_sqin = vol_flow_gpm / (7.48 * target_velocity / 60) / (144 / 7.48)
        pipe_diameter = math.sqrt(4 * pipe_area_sqin * vol_flow_gpm * 60 / (math.pi * target_velocity * 7.48 * 144))
        
        # Select standard pipe size
        pipe_size = self._select_pipe_size(vol_flow_gpm)
        
        # Calculate actual velocity
        pipe_id = self._get_pipe_id(pipe_size)
        pipe_area_sqft = math.pi * (pipe_id / 12) ** 2 / 4
        velocity = (vol_flow_gpm / 7.48 / 60) / pipe_area_sqft
        
        # Pressure drop calculation
        # Using Darcy-Weisbach with friction factor
        reynolds = (velocity * pipe_id / 12 * props.density) / (props.viscosity * 0.000672)
        
        # Friction factor (turbulent flow approximation)
        if reynolds > 2300:
            f = 0.25 / (math.log10(5.74 / reynolds ** 0.9)) ** 2
        else:
            f = 64 / reynolds if reynolds > 0 else 0.04
        
        # Equivalent length for fittings
        eq_length = pipe_length_ft + num_elbows * 30 * pipe_id / 12
        
        # Head loss (ft of fluid)
        head_loss = f * (eq_length / (pipe_id / 12)) * (velocity ** 2) / (2 * 32.2)
        
        # Pump power
        pump_efficiency = 0.6
        pump_hp = (vol_flow_gpm * head_loss * props.specific_gravity) / (3960 * pump_efficiency)
        
        # Heat transfer penalty vs water
        # Glycol has lower heat transfer coefficient
        ht_penalty = 1 - (props.thermal_conductivity / 0.36) * (1 / props.specific_heat)
        
        return GlycolSystemResult(
            coolant_type=coolant_type.value,
            concentration_percent=concentration,
            freeze_point=props.freeze_point,
            flow_rate_gpm=vol_flow_gpm,
            velocity_fps=velocity,
            pressure_drop_ft_hd=head_loss,
            pump_hp=pump_hp,
            heat_transfer_penalty=ht_penalty,
            pipe_size_in=pipe_size,
            notes=notes,
        )
    
    def _interpolate_properties(self, data: Dict, concentration: float) -> Tuple[float, float, float]:
        """Interpolate properties from data table."""
        concs = sorted(data.keys())
        
        if concentration <= concs[0]:
            return data[concs[0]]
        if concentration >= concs[-1]:
            return data[concs[-1]]
        
        for i, c in enumerate(concs):
            if c >= concentration:
                c_low, c_high = concs[i-1], c
                fp_low, sg_low, cp_low = data[c_low]
                fp_high, sg_high, cp_high = data[c_high]
                
                f = (concentration - c_low) / (c_high - c_low)
                
                fp = fp_low + f * (fp_high - fp_low)
                sg = sg_low + f * (sg_high - sg_low)
                cp = cp_low + f * (cp_high - cp_low)
                
                return fp, sg, cp
        
        return data[concs[-1]]
    
    def _calculate_viscosity(
        self,
        coolant_type: CoolantType,
        concentration: float,
        temperature: float,
    ) -> float:
        """Calculate viscosity in cP."""
        # Base viscosity at 60°F (water = 1.0 cP)
        base_viscosity = {
            CoolantType.PROPYLENE_GLYCOL: 1.0 + 0.15 * concentration,
            CoolantType.ETHYLENE_GLYCOL: 1.0 + 0.10 * concentration,
            CoolantType.CALCIUM_CHLORIDE: 1.0 + 0.08 * concentration,
            CoolantType.SODIUM_CHLORIDE: 1.0 + 0.05 * concentration,
        }
        
        visc_60 = base_viscosity.get(coolant_type, 2.0)
        
        # Temperature correction
        temp_factor = 1.0
        for temp, factor in sorted(self.VISCOSITY_TEMP_FACTOR.items(), reverse=True):
            if temperature <= temp:
                temp_factor = factor
                break
        
        return visc_60 * temp_factor
    
    def _select_pipe_size(self, flow_gpm: float) -> float:
        """Select pipe size for flow rate."""
        # Target 4-8 ft/s velocity
        sizes = {
            10: 1.0,
            25: 1.5,
            50: 2.0,
            90: 2.5,
            140: 3.0,
            230: 4.0,
            400: 5.0,
            600: 6.0,
            1000: 8.0,
            1600: 10.0,
            2500: 12.0,
        }
        
        for max_flow, size in sorted(sizes.items()):
            if flow_gpm <= max_flow:
                return size
        
        return 12.0
    
    def _get_pipe_id(self, nominal_size: float) -> float:
        """Get pipe inside diameter (inches) for schedule 40."""
        pipe_id = {
            0.5: 0.622, 0.75: 0.824, 1.0: 1.049, 1.25: 1.380,
            1.5: 1.610, 2.0: 2.067, 2.5: 2.469, 3.0: 3.068,
            4.0: 4.026, 5.0: 5.047, 6.0: 6.065, 8.0: 7.981,
            10.0: 10.020, 12.0: 11.938,
        }
        return pipe_id.get(nominal_size, nominal_size * 0.9)


def freeze_point(coolant: str, concentration: float) -> float:
    """
    Quick freeze point lookup.
    
    Args:
        coolant: "propylene_glycol", "ethylene_glycol", etc.
        concentration: % by weight
    
    Returns:
        Freeze point (°F)
    """
    calc = SecondaryRefrigerantCalculator()
    
    coolant_types = {
        "propylene_glycol": CoolantType.PROPYLENE_GLYCOL,
        "ethylene_glycol": CoolantType.ETHYLENE_GLYCOL,
        "pg": CoolantType.PROPYLENE_GLYCOL,
        "eg": CoolantType.ETHYLENE_GLYCOL,
    }
    
    ct = coolant_types.get(coolant.lower(), CoolantType.PROPYLENE_GLYCOL)
    props = calc.get_properties(ct, concentration, 60)
    
    return props.freeze_point


def glycol_concentration_for_temp(coolant: str, min_temp: float, margin: float = 10) -> float:
    """
    Get required glycol concentration for operating temperature.
    
    Args:
        coolant: "propylene_glycol" or "ethylene_glycol"
        min_temp: Minimum operating temperature (°F)
        margin: Safety margin (°F)
    
    Returns:
        Required concentration (% by weight)
    """
    calc = SecondaryRefrigerantCalculator()
    
    coolant_types = {
        "propylene_glycol": CoolantType.PROPYLENE_GLYCOL,
        "ethylene_glycol": CoolantType.ETHYLENE_GLYCOL,
        "pg": CoolantType.PROPYLENE_GLYCOL,
        "eg": CoolantType.ETHYLENE_GLYCOL,
    }
    
    ct = coolant_types.get(coolant.lower(), CoolantType.PROPYLENE_GLYCOL)
    
    return calc.required_concentration(ct, min_temp, margin)
