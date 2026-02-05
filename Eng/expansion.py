"""
Expansion Device Sizing Module
==============================

Size and select expansion devices:
- Thermostatic expansion valves (TXV/TEV)
- Electronic expansion valves (EEV)
- Float valves (high side and low side)
- Hand expansion valves (HEV)
- Orifices and restrictors

Based on manufacturer sizing procedures and ASHRAE methods.
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ExpansionDeviceType(Enum):
    """Types of expansion devices."""
    TXV = "txv"              # Thermostatic expansion valve
    EEV = "eev"              # Electronic expansion valve
    FLOAT_HIGH = "float_high"  # High side float
    FLOAT_LOW = "float_low"    # Low side float
    HEV = "hev"              # Hand expansion valve
    ORIFICE = "orifice"      # Fixed orifice
    CAPILLARY = "capillary"  # Capillary tube


class RefrigerantType(Enum):
    """Refrigerant types for sizing."""
    NH3 = "nh3"
    R22 = "r22"
    R404A = "r404a"
    R507 = "r507"
    R134A = "r134a"
    R410A = "r410a"
    CO2 = "co2"


@dataclass
class ExpansionValveResult:
    """Results from expansion device sizing."""
    device_type: str
    rated_capacity_tons: float
    selected_capacity_tons: float
    port_size: str
    cv_or_orifice: float
    pressure_drop_psi: float
    liquid_temp: float
    evaporator_temp: float
    notes: List[str]


class ExpansionDeviceCalculator:
    """
    Expansion device sizing calculator.
    
    Example:
        >>> calc = ExpansionDeviceCalculator()
        >>> result = calc.size_txv(
        ...     capacity_tons=50,
        ...     refrigerant=RefrigerantType.NH3,
        ...     liquid_temp=85,
        ...     evaporator_temp=20,
        ...     condensing_temp=95
        ... )
        >>> print(f"Selected capacity: {result.selected_capacity_tons} tons")
    """
    
    # TXV capacity correction factors for liquid temperature
    # Base: liquid at condensing temp
    TXV_LIQUID_CORRECTION = {
        # Subcooling (°F): correction factor
        0: 1.00,
        5: 1.04,
        10: 1.08,
        15: 1.12,
        20: 1.16,
        25: 1.20,
        30: 1.24,
        40: 1.32,
        50: 1.40,
    }
    
    # TXV capacity vs pressure drop (normalized)
    # Rated at 100 psi drop typically
    TXV_PRESSURE_CORRECTION = {
        50: 0.71,
        75: 0.87,
        100: 1.00,
        125: 1.12,
        150: 1.22,
        175: 1.32,
        200: 1.41,
        250: 1.58,
        300: 1.73,
    }
    
    # NH3 TXV standard sizes (tons at -20°F SST, 95°F liquid)
    NH3_TXV_SIZES = {
        'A': 0.6, 'B': 1.0, 'C': 1.5, 'D': 2.5, 'E': 4,
        'F': 6, 'G': 10, 'H': 15, 'J': 25, 'K': 40,
        'L': 60, 'M': 85, 'N': 120, 'P': 170,
    }
    
    # Float valve orifice sizes (diameter in inches)
    FLOAT_ORIFICE_SIZES = [
        0.125, 0.156, 0.188, 0.219, 0.250, 0.281, 0.313, 0.344,
        0.375, 0.438, 0.500, 0.563, 0.625, 0.750, 0.875, 1.000,
        1.125, 1.250, 1.375, 1.500, 1.750, 2.000,
    ]
    
    def __init__(self):
        pass
    
    def size_txv(
        self,
        capacity_tons: float,
        refrigerant: RefrigerantType,
        liquid_temp: float,
        evaporator_temp: float,
        condensing_temp: float,
        liquid_pressure_psi: float = None,
        evaporator_pressure_psi: float = None,
        superheat: float = 10,
    ) -> ExpansionValveResult:
        """
        Size thermostatic expansion valve (TXV).
        
        Args:
            capacity_tons: Required capacity (tons)
            refrigerant: Refrigerant type
            liquid_temp: Liquid temperature entering valve (°F)
            evaporator_temp: Evaporator saturation temperature (°F)
            condensing_temp: Condensing temperature (°F)
            liquid_pressure_psi: Liquid pressure (psia) - calculated if not given
            evaporator_pressure_psi: Evaporator pressure (psia)
            superheat: Desired superheat (°F)
        
        Returns:
            ExpansionValveResult with sizing details
        """
        notes = []
        
        # Calculate pressures if not provided
        if liquid_pressure_psi is None:
            liquid_pressure_psi = self._get_saturation_pressure(refrigerant, condensing_temp)
        
        if evaporator_pressure_psi is None:
            evaporator_pressure_psi = self._get_saturation_pressure(refrigerant, evaporator_temp)
        
        # Pressure drop across valve
        pressure_drop = liquid_pressure_psi - evaporator_pressure_psi
        notes.append(f"Pressure drop: {pressure_drop:.1f} psi")
        
        # Subcooling
        subcooling = condensing_temp - liquid_temp
        notes.append(f"Subcooling: {subcooling:.1f}°F")
        
        # Get correction factors
        liquid_correction = self._interpolate(self.TXV_LIQUID_CORRECTION, subcooling)
        pressure_correction = self._interpolate(self.TXV_PRESSURE_CORRECTION, pressure_drop)
        
        # Evaporator temperature correction
        # TXV capacity typically rated at specific SST (e.g., -20°F for NH3)
        base_sst = -20 if refrigerant == RefrigerantType.NH3 else 40
        sst_correction = 1 + (evaporator_temp - base_sst) * 0.01
        
        # Total correction
        total_correction = liquid_correction * pressure_correction * sst_correction
        notes.append(f"Total correction factor: {total_correction:.2f}")
        
        # Required rated capacity
        required_rated = capacity_tons / total_correction
        
        # Select valve size
        if refrigerant == RefrigerantType.NH3:
            selected_size, selected_capacity = self._select_nh3_txv(required_rated)
        else:
            # Generic sizing
            selected_size = "See manufacturer"
            selected_capacity = required_rated * 1.1  # 10% oversizing
        
        return ExpansionValveResult(
            device_type="TXV",
            rated_capacity_tons=capacity_tons,
            selected_capacity_tons=selected_capacity,
            port_size=selected_size,
            cv_or_orifice=0,  # TXV doesn't use Cv
            pressure_drop_psi=pressure_drop,
            liquid_temp=liquid_temp,
            evaporator_temp=evaporator_temp,
            notes=notes,
        )
    
    def size_eev(
        self,
        capacity_tons: float,
        refrigerant: RefrigerantType,
        liquid_temp: float,
        evaporator_temp: float,
        condensing_temp: float,
        turndown_ratio: float = 10,
    ) -> ExpansionValveResult:
        """
        Size electronic expansion valve (EEV).
        
        Args:
            capacity_tons: Maximum required capacity (tons)
            refrigerant: Refrigerant type
            liquid_temp: Liquid temperature (°F)
            evaporator_temp: Evaporator saturation temperature (°F)
            condensing_temp: Condensing temperature (°F)
            turndown_ratio: Required turndown ratio
        
        Returns:
            ExpansionValveResult
        """
        notes = []
        
        # Calculate pressures
        liquid_p = self._get_saturation_pressure(refrigerant, condensing_temp)
        evap_p = self._get_saturation_pressure(refrigerant, evaporator_temp)
        pressure_drop = liquid_p - evap_p
        
        # EEVs are typically selected for max capacity with turndown
        # Size at 80% of max opening for margin
        design_capacity = capacity_tons / 0.8
        notes.append(f"Design capacity at 80% opening: {design_capacity:.1f} tons")
        
        # Minimum capacity
        min_capacity = capacity_tons / turndown_ratio
        notes.append(f"Minimum capacity ({turndown_ratio}:1 turndown): {min_capacity:.2f} tons")
        
        # Calculate approximate Cv
        # Q = Cv * sqrt(ΔP / SG)
        # Simplified for refrigerant
        cv = self._calculate_cv(capacity_tons, refrigerant, pressure_drop)
        notes.append(f"Required Cv: {cv:.2f}")
        
        return ExpansionValveResult(
            device_type="EEV",
            rated_capacity_tons=capacity_tons,
            selected_capacity_tons=design_capacity,
            port_size=f"Cv={cv:.2f}",
            cv_or_orifice=cv,
            pressure_drop_psi=pressure_drop,
            liquid_temp=liquid_temp,
            evaporator_temp=evaporator_temp,
            notes=notes,
        )
    
    def size_float_valve(
        self,
        capacity_tons: float,
        refrigerant: RefrigerantType,
        liquid_temp: float,
        vessel_pressure_psi: float,
        supply_pressure_psi: float,
        valve_type: str = "high_side",
    ) -> ExpansionValveResult:
        """
        Size float valve (high side or low side).
        
        Args:
            capacity_tons: Required capacity (tons)
            refrigerant: Refrigerant type
            liquid_temp: Liquid temperature (°F)
            vessel_pressure_psi: Vessel operating pressure (psia)
            supply_pressure_psi: Supply liquid pressure (psia)
            valve_type: "high_side" or "low_side"
        
        Returns:
            ExpansionValveResult
        """
        notes = []
        
        pressure_drop = supply_pressure_psi - vessel_pressure_psi
        notes.append(f"Available pressure drop: {pressure_drop:.1f} psi")
        
        # Calculate required orifice area
        # Q = A * C * sqrt(2 * g * ΔP * ρ / 144)
        # Simplified liquid flow formula
        
        liquid_density = self._get_liquid_density(refrigerant, liquid_temp)
        latent_heat = self._get_latent_heat(refrigerant, liquid_temp)
        
        # Mass flow rate
        mass_flow_lb_hr = capacity_tons * 12000 / latent_heat  # lb/hr
        mass_flow_lb_min = mass_flow_lb_hr / 60
        
        # Volume flow
        vol_flow_cfm = mass_flow_lb_min / liquid_density
        vol_flow_gpm = vol_flow_cfm * 7.48
        
        # Orifice sizing (coefficient ~ 0.65 for sharp edge)
        cd = 0.65
        # A = Q / (Cd * sqrt(2gΔP/ρ))
        area_sqin = (mass_flow_lb_min / 60) / (cd * math.sqrt(2 * 32.2 * pressure_drop * liquid_density / 144))
        diameter_in = math.sqrt(4 * area_sqin / math.pi)
        
        # Select standard orifice size
        selected_orifice = self._select_orifice_size(diameter_in)
        notes.append(f"Calculated orifice: {diameter_in:.3f}\"")
        notes.append(f"Selected orifice: {selected_orifice:.3f}\"")
        
        return ExpansionValveResult(
            device_type=f"Float Valve ({valve_type})",
            rated_capacity_tons=capacity_tons,
            selected_capacity_tons=capacity_tons,
            port_size=f"{selected_orifice:.3f}\" orifice",
            cv_or_orifice=selected_orifice,
            pressure_drop_psi=pressure_drop,
            liquid_temp=liquid_temp,
            evaporator_temp=0,
            notes=notes,
        )
    
    def size_hand_expansion_valve(
        self,
        capacity_tons: float,
        refrigerant: RefrigerantType,
        liquid_temp: float,
        pressure_drop_psi: float,
    ) -> ExpansionValveResult:
        """
        Size hand expansion valve (HEV).
        
        Args:
            capacity_tons: Required capacity (tons)
            refrigerant: Refrigerant type
            liquid_temp: Liquid temperature (°F)
            pressure_drop_psi: Available pressure drop (psi)
        
        Returns:
            ExpansionValveResult
        """
        notes = []
        
        # Calculate Cv required
        cv = self._calculate_cv(capacity_tons, refrigerant, pressure_drop_psi)
        
        # Oversize by 50% for manual valve
        selected_cv = cv * 1.5
        notes.append(f"Required Cv: {cv:.2f}")
        notes.append(f"Selected Cv (150%): {selected_cv:.2f}")
        
        # Estimate port size
        port_size = self._cv_to_port_size(selected_cv)
        notes.append(f"Estimated port: {port_size}")
        
        return ExpansionValveResult(
            device_type="HEV",
            rated_capacity_tons=capacity_tons,
            selected_capacity_tons=capacity_tons * 1.5,
            port_size=port_size,
            cv_or_orifice=selected_cv,
            pressure_drop_psi=pressure_drop_psi,
            liquid_temp=liquid_temp,
            evaporator_temp=0,
            notes=notes,
        )
    
    def size_orifice(
        self,
        flow_rate_gpm: float,
        pressure_drop_psi: float,
        specific_gravity: float = 0.7,
    ) -> float:
        """
        Size a flow orifice.
        
        Args:
            flow_rate_gpm: Required flow rate (GPM)
            pressure_drop_psi: Design pressure drop (psi)
            specific_gravity: Liquid specific gravity
        
        Returns:
            Orifice diameter (inches)
        """
        # Q = Cd * A * sqrt(2 * g * h)
        # For liquid: Q (GPM) = 29.84 * Cd * d² * sqrt(ΔP / SG)
        cd = 0.65  # Sharp-edge orifice coefficient
        
        # d² = Q / (29.84 * Cd * sqrt(ΔP/SG))
        d_squared = flow_rate_gpm / (29.84 * cd * math.sqrt(pressure_drop_psi / specific_gravity))
        diameter = math.sqrt(d_squared)
        
        return self._select_orifice_size(diameter)
    
    def _select_nh3_txv(self, required_tons: float) -> Tuple[str, float]:
        """Select NH3 TXV from standard sizes."""
        for size, capacity in sorted(self.NH3_TXV_SIZES.items(), key=lambda x: x[1]):
            if capacity >= required_tons:
                return size, capacity
        
        # Largest size
        return 'P', 170
    
    def _select_orifice_size(self, calculated_dia: float) -> float:
        """Select standard orifice size."""
        for size in self.FLOAT_ORIFICE_SIZES:
            if size >= calculated_dia:
                return size
        return self.FLOAT_ORIFICE_SIZES[-1]
    
    def _calculate_cv(
        self,
        capacity_tons: float,
        refrigerant: RefrigerantType,
        pressure_drop: float,
    ) -> float:
        """Calculate required Cv for refrigerant flow."""
        # Get refrigerant properties
        latent_heat = self._get_latent_heat(refrigerant, 32)
        liquid_density = self._get_liquid_density(refrigerant, 32)
        sg = liquid_density / 62.4  # Specific gravity vs water
        
        # Mass flow rate
        mass_flow_lb_hr = capacity_tons * 12000 / latent_heat
        
        # Volume flow rate
        vol_flow_gpm = (mass_flow_lb_hr / 60) / (liquid_density / 7.48)
        
        # Cv = Q / sqrt(ΔP / SG)
        cv = vol_flow_gpm / math.sqrt(pressure_drop / sg) if pressure_drop > 0 else 0
        
        return cv
    
    def _cv_to_port_size(self, cv: float) -> str:
        """Estimate port size from Cv."""
        # Rough correlation: Cv ≈ 14 * d² for globe valves
        d_squared = cv / 14
        d = math.sqrt(d_squared) if d_squared > 0 else 0.25
        
        # Round to nearest standard size
        sizes = [0.25, 0.375, 0.5, 0.625, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
        for size in sizes:
            if d <= size:
                return f"{size}\""
        return "3\""
    
    def _get_saturation_pressure(self, refrigerant: RefrigerantType, temp: float) -> float:
        """Get saturation pressure for refrigerant at temperature."""
        # Simplified correlations
        if refrigerant == RefrigerantType.NH3:
            # Antoine equation approximation for NH3
            return 10 ** (7.36 - 1617 / (temp + 460)) * 14.696
        elif refrigerant in [RefrigerantType.R22, RefrigerantType.R404A, RefrigerantType.R507]:
            # Generic HFC approximation
            return 10 ** (6.9 - 1200 / (temp + 460)) * 14.696
        else:
            return 100  # Default
    
    def _get_liquid_density(self, refrigerant: RefrigerantType, temp: float) -> float:
        """Get liquid density (lb/ft³)."""
        densities = {
            RefrigerantType.NH3: 40 - 0.05 * (temp - 32),
            RefrigerantType.R22: 80 - 0.1 * (temp - 32),
            RefrigerantType.R404A: 70 - 0.1 * (temp - 32),
            RefrigerantType.R507: 68 - 0.1 * (temp - 32),
        }
        return densities.get(refrigerant, 50)
    
    def _get_latent_heat(self, refrigerant: RefrigerantType, temp: float) -> float:
        """Get latent heat of vaporization (BTU/lb)."""
        latent = {
            RefrigerantType.NH3: 550 - 0.5 * (temp + 40),
            RefrigerantType.R22: 85 - 0.1 * temp,
            RefrigerantType.R404A: 70 - 0.08 * temp,
            RefrigerantType.R507: 68 - 0.08 * temp,
        }
        return max(latent.get(refrigerant, 80), 30)
    
    def _interpolate(self, table: Dict, value: float) -> float:
        """Linear interpolation in a table."""
        keys = sorted(table.keys())
        
        if value <= keys[0]:
            return table[keys[0]]
        if value >= keys[-1]:
            return table[keys[-1]]
        
        for i, k in enumerate(keys):
            if k >= value:
                k_low, k_high = keys[i-1], k
                v_low, v_high = table[k_low], table[k_high]
                f = (value - k_low) / (k_high - k_low)
                return v_low + f * (v_high - v_low)
        
        return table[keys[-1]]


def quick_txv_size(capacity_tons: float, refrigerant: str = "NH3") -> str:
    """Quick TXV size estimate for NH3."""
    calc = ExpansionDeviceCalculator()
    if refrigerant.upper() == "NH3":
        for size, cap in sorted(calc.NH3_TXV_SIZES.items(), key=lambda x: x[1]):
            if cap >= capacity_tons * 1.1:
                return f"Size {size} ({cap} tons)"
    return "See manufacturer"
