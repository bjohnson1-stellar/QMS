"""
Ammonia Release Calculation Module
==================================

Calculate ammonia release rates and concentrations per:
- IIAR Bulletin 110 (Ammonia release methods)
- EPA RMP (Risk Management Program)
- NFPA 1 (Fire Code)

Includes calculations for:
- Flashing releases
- Pool evaporation
- Exhaust requirements
- Indoor/outdoor concentrations
"""

import math
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ReleaseType(Enum):
    """Types of ammonia release scenarios."""
    FLASHING = "flashing"           # Liquid flashing to vapor
    NON_FLASHING = "non_flashing"   # Liquid pool evaporation
    VAPOR = "vapor"                 # Pure vapor release
    TWO_PHASE = "two_phase"         # Two-phase release


class ReleaseMethod(Enum):
    """Release calculation methods."""
    IIAR_FLASHING = "IIAR Flashing"
    IIAR_NON_FLASHING = "IIAR Non-Flashing"
    IIAR_VAPOR = "IIAR Vapor"
    EPA_WORST_CASE = "EPA Worst Case"
    EPA_MITIGATED = "EPA Mitigated"
    NFPA_TOXIC = "NFPA 1 Toxic Gas"


@dataclass
class ReleaseResult:
    """Results from release calculation."""
    vapor_release_rate_lb_min: float   # Vapor release rate
    mass_released_lb: float            # Total mass released
    exhaust_rate_cfm: float            # Required exhaust rate
    indoor_concentration_ppm: float    # Indoor peak concentration
    outdoor_concentration_ppm: float   # Outdoor peak concentration
    room_air_changes_hr: float         # Room air changes per hour
    leak_duration_min: float           # Leak duration
    hole_diameter_in: float            # Leak hole diameter
    method: str                        # Calculation method used
    
    def __str__(self) -> str:
        return (f"Release: {self.vapor_release_rate_lb_min:.1f} lb/min, "
                f"Total: {self.mass_released_lb:.1f} lb, "
                f"Exhaust: {self.exhaust_rate_cfm:,.0f} CFM, "
                f"Indoor: {self.indoor_concentration_ppm:,.0f} ppm, "
                f"Outdoor: {self.outdoor_concentration_ppm:.0f} ppm")


class NH3ReleaseCalculator:
    """
    Ammonia release calculator.
    
    Calculate release rates and concentrations for various scenarios.
    
    Example:
        >>> calc = NH3ReleaseCalculator()
        >>> result = calc.iiar_flashing_release(
        ...     hole_diameter=0.25,      # inches
        ...     system_temp=95,          # °F
        ...     leak_duration=15,        # minutes
        ...     room_volume=50000,       # ft³
        ...     exhaust_rate=20000       # CFM
        ... )
        >>> print(f"Vapor release: {result.vapor_release_rate_lb_min:.1f} lb/min")
    """
    
    # Ammonia properties
    MOLECULAR_WEIGHT = 17.03  # lb/lbmol
    
    # Concentration limits
    IDLH = 300      # ppm, Immediately Dangerous to Life and Health
    ERPG_2 = 150    # ppm, Emergency Response Planning Guideline 2
    ERPG_3 = 750    # ppm, Emergency Response Planning Guideline 3
    PEL = 50        # ppm, Permissible Exposure Limit
    TLV = 25        # ppm, Threshold Limit Value
    
    def __init__(self):
        """Initialize release calculator with ammonia property data."""
        self._load_nh3_properties()
    
    def _load_nh3_properties(self):
        """Load ammonia property data for calculations."""
        # Temperature (°F) -> (pressure psia, liquid density lb/ft³, vapor density lb/ft³,
        #                      latent heat BTU/lb, liquid Cp BTU/lb-°F)
        self._nh3_props = {
            -40: (10.77, 43.06, 0.0387, 597.5, 1.056),
            -30: (14.60, 42.62, 0.0502, 590.7, 1.061),
            -20: (19.51, 42.16, 0.0646, 583.7, 1.067),
            -10: (25.69, 41.68, 0.0824, 576.5, 1.074),
            0: (33.37, 41.18, 0.1041, 569.0, 1.082),
            10: (42.82, 40.65, 0.1305, 561.3, 1.091),
            20: (54.30, 40.11, 0.1624, 553.3, 1.102),
            30: (68.12, 39.53, 0.2005, 545.1, 1.113),
            40: (84.56, 38.91, 0.2458, 536.5, 1.127),
            50: (103.98, 38.26, 0.2993, 527.6, 1.141),
            60: (126.78, 37.59, 0.3621, 518.4, 1.157),
            70: (153.36, 36.88, 0.4356, 508.8, 1.174),
            80: (184.18, 36.14, 0.5213, 498.8, 1.192),
            90: (219.69, 35.37, 0.6210, 488.3, 1.213),
            95: (239.34, 34.96, 0.6768, 482.9, 1.224),
            100: (260.34, 34.55, 0.7369, 477.4, 1.235),
            110: (306.62, 33.68, 0.8714, 465.9, 1.260),
        }
    
    def _get_properties(self, temp_f: float) -> Tuple[float, float, float, float, float]:
        """Get interpolated NH3 properties at given temperature."""
        temps = sorted(self._nh3_props.keys())
        
        if temp_f <= temps[0]:
            return self._nh3_props[temps[0]]
        if temp_f >= temps[-1]:
            return self._nh3_props[temps[-1]]
        
        # Find bracketing temperatures
        for i, t in enumerate(temps):
            if t >= temp_f:
                t_low, t_high = temps[i-1], t
                break
        
        # Linear interpolation
        f = (temp_f - t_low) / (t_high - t_low)
        p_low = self._nh3_props[t_low]
        p_high = self._nh3_props[t_high]
        
        return tuple(p_low[i] + f * (p_high[i] - p_low[i]) for i in range(5))
    
    def iiar_flashing_release(
        self,
        hole_diameter: float,
        system_temp: float,
        leak_duration: float,
        room_volume: float,
        exhaust_rate: Optional[float] = None,
        removal_efficiency: float = 0.999,
        outdoor_target_ppm: float = 40,
        ambient_temp: float = 77,
    ) -> ReleaseResult:
        """
        IIAR Method 1: Flashing release from liquid side.
        
        For scenarios where system temperature > saturation temperature,
        causing liquid to flash to vapor upon release.
        
        Args:
            hole_diameter: Leak hole diameter (inches)
            system_temp: System/liquid temperature (°F)
            leak_duration: Duration of leak (minutes)
            room_volume: Machine room volume (ft³)
            exhaust_rate: Exhaust ventilation rate (CFM), calculated if None
            removal_efficiency: Scrubber/filter removal efficiency (0-1)
            outdoor_target_ppm: Target outdoor concentration (ppm)
            ambient_temp: Ambient temperature (°F)
        
        Returns:
            ReleaseResult with calculated values
        """
        # Get properties at system temperature
        pressure, rho_l, rho_v, h_vap, cp = self._get_properties(system_temp)
        
        # Get vapor density at ambient for outdoor calculations
        _, _, rho_v_ambient, _, _ = self._get_properties(ambient_temp)
        
        # Leak area
        A_leak = math.pi * (hole_diameter / 12) ** 2 / 4  # ft²
        
        # IIAR Equation (1): Flashing release rate
        # m_flashing = 9492 * A_leak * (H_vap / ((1/ρV) - (1/ρL))) * (1/(T_sys * cp))
        if rho_v > 0 and rho_l > 0:
            specific_vol_diff = (1/rho_v) - (1/rho_l)
            T_sys_R = system_temp + 459.67  # Convert to Rankine
            m_flashing = 9492 * A_leak * (h_vap / specific_vol_diff) * (1 / (T_sys_R * cp))
        else:
            m_flashing = 0
        
        # Total mass released
        M_leak = m_flashing * leak_duration
        
        # Calculate exhaust rate if not provided
        # IIAR Equation (3): NV = [((m * 10^6)/ρ) * (1-e)] / OPC
        if exhaust_rate is None:
            if rho_v_ambient > 0:
                exhaust_rate = ((m_flashing * 1e6) / rho_v_ambient) * (1 - removal_efficiency) / outdoor_target_ppm
            else:
                exhaust_rate = 30000  # Default
        
        # Room air changes per hour
        # IIAR Equation (4): RAC = (NV/V_sys) * 60
        ach = (exhaust_rate / room_volume) * 60 if room_volume > 0 else 0
        
        # Volumetric release rate (SCFM)
        v_release = m_flashing / rho_v_ambient if rho_v_ambient > 0 else 0
        
        # Indoor peak concentration
        # IIAR Equation (5): IPC = (v/NV) * 10^6
        if exhaust_rate > 0:
            indoor_ppm = (v_release / exhaust_rate) * 1e6
        else:
            indoor_ppm = 1e6  # Very high if no ventilation
        
        # Outdoor concentration at target
        outdoor_ppm = outdoor_target_ppm
        
        return ReleaseResult(
            vapor_release_rate_lb_min=m_flashing,
            mass_released_lb=M_leak,
            exhaust_rate_cfm=exhaust_rate,
            indoor_concentration_ppm=indoor_ppm,
            outdoor_concentration_ppm=outdoor_ppm,
            room_air_changes_hr=ach,
            leak_duration_min=leak_duration,
            hole_diameter_in=hole_diameter,
            method="IIAR Method 1 - Flashing Release"
        )
    
    def iiar_non_flashing_release(
        self,
        hole_diameter: float,
        system_temp: float,
        leak_duration: float,
        room_volume: float,
        pool_area: float = 100,
        exhaust_rate: Optional[float] = None,
        outdoor_target_ppm: float = 40,
        ambient_temp: float = 77,
        wind_speed: float = 5,
    ) -> ReleaseResult:
        """
        IIAR Method 2: Non-flashing (pool evaporation) release.
        
        For scenarios where liquid pools and evaporates.
        
        Args:
            hole_diameter: Leak hole diameter (inches)
            system_temp: System temperature (°F)
            leak_duration: Duration of leak (minutes)
            room_volume: Room volume (ft³)
            pool_area: Pool surface area (ft²)
            exhaust_rate: Exhaust rate (CFM)
            outdoor_target_ppm: Target outdoor concentration (ppm)
            ambient_temp: Ambient temperature (°F)
            wind_speed: Indoor air velocity (ft/min)
        
        Returns:
            ReleaseResult with calculated values
        """
        # Get properties
        pressure, rho_l, rho_v, h_vap, cp = self._get_properties(system_temp)
        _, _, rho_v_ambient, _, _ = self._get_properties(ambient_temp)
        
        # Pool evaporation rate (simplified)
        # Based on mass transfer correlation
        # m_evap = k * A * (P_sat - P_partial) / (R * T)
        # Simplified: m_evap ≈ 0.1 * A * P_sat^0.5 * (wind_speed/100)^0.5
        
        P_sat = pressure  # psia
        m_evap = 0.1 * pool_area * math.sqrt(P_sat) * math.sqrt(wind_speed / 100)
        
        # Limit by pool supply (liquid flow through hole)
        A_leak = math.pi * (hole_diameter / 12) ** 2 / 4
        liquid_flow = 40 * A_leak * math.sqrt(2 * 32.174 * pressure * 144 / rho_l) * rho_l / 60
        
        m_evap = min(m_evap, liquid_flow * 0.1)  # Only fraction evaporates
        
        M_leak = m_evap * leak_duration
        
        if exhaust_rate is None:
            exhaust_rate = ((m_evap * 1e6) / rho_v_ambient) * 0.001 / outdoor_target_ppm
        
        ach = (exhaust_rate / room_volume) * 60 if room_volume > 0 else 0
        
        v_release = m_evap / rho_v_ambient if rho_v_ambient > 0 else 0
        indoor_ppm = (v_release / exhaust_rate) * 1e6 if exhaust_rate > 0 else 1e6
        
        return ReleaseResult(
            vapor_release_rate_lb_min=m_evap,
            mass_released_lb=M_leak,
            exhaust_rate_cfm=exhaust_rate,
            indoor_concentration_ppm=indoor_ppm,
            outdoor_concentration_ppm=outdoor_target_ppm,
            room_air_changes_hr=ach,
            leak_duration_min=leak_duration,
            hole_diameter_in=hole_diameter,
            method="IIAR Method 2 - Non-Flashing/Pool Evaporation"
        )
    
    def iiar_vapor_release(
        self,
        hole_diameter: float,
        system_pressure: float,
        leak_duration: float,
        room_volume: float,
        exhaust_rate: Optional[float] = None,
        outdoor_target_ppm: float = 40,
        ambient_temp: float = 77,
    ) -> ReleaseResult:
        """
        IIAR Method 3: Pure vapor release.
        
        For vapor-side leaks (e.g., from suction line).
        
        Args:
            hole_diameter: Leak hole diameter (inches)
            system_pressure: System pressure (psia)
            leak_duration: Leak duration (minutes)
            room_volume: Room volume (ft³)
            exhaust_rate: Exhaust rate (CFM)
            outdoor_target_ppm: Target outdoor concentration (ppm)
            ambient_temp: Ambient temperature (°F)
        
        Returns:
            ReleaseResult with calculated values
        """
        # Vapor release through orifice
        # m = C * A * P * sqrt(2 * g * M / (R * T * k))
        # Simplified: m = 767 * A * P * sqrt(28.96/MW) / 60
        
        A_leak = math.pi * (hole_diameter) ** 2 / 4  # in²
        
        # NFPA-style vapor release
        m_vapor = 767 * A_leak * system_pressure * math.sqrt(28.96 / self.MOLECULAR_WEIGHT) / 60
        
        M_leak = m_vapor * leak_duration
        
        _, _, rho_v_ambient, _, _ = self._get_properties(ambient_temp)
        
        if exhaust_rate is None:
            exhaust_rate = ((m_vapor * 1e6) / rho_v_ambient) * 0.001 / outdoor_target_ppm
        
        ach = (exhaust_rate / room_volume) * 60 if room_volume > 0 else 0
        
        v_release = m_vapor / rho_v_ambient if rho_v_ambient > 0 else 0
        indoor_ppm = (v_release / exhaust_rate) * 1e6 if exhaust_rate > 0 else 1e6
        
        return ReleaseResult(
            vapor_release_rate_lb_min=m_vapor,
            mass_released_lb=M_leak,
            exhaust_rate_cfm=exhaust_rate,
            indoor_concentration_ppm=indoor_ppm,
            outdoor_concentration_ppm=outdoor_target_ppm,
            room_air_changes_hr=ach,
            leak_duration_min=leak_duration,
            hole_diameter_in=hole_diameter,
            method="IIAR Method 3 - Vapor Release"
        )
    
    def epa_worst_case(
        self,
        total_charge: float,
        room_volume: float,
        exhaust_rate: float,
        building_attenuation: float = 0.51,
        release_duration: float = 10,
        ambient_temp: float = 77,
    ) -> ReleaseResult:
        """
        EPA RMP Worst Case Scenario.
        
        Assumes 40% of largest vessel released over 10 minutes.
        
        Args:
            total_charge: Total system charge or largest vessel (lbs)
            room_volume: Room volume (ft³)
            exhaust_rate: Active ventilation rate (CFM)
            building_attenuation: Building release rate factor (default 0.51)
            release_duration: Release duration (minutes)
            ambient_temp: Ambient temperature (°F)
        
        Returns:
            ReleaseResult with calculated values
        """
        # EPA Equation (10): θ = V_sys / (0.2 * Q)
        theta = room_volume / (0.2 * total_charge) if total_charge > 0 else 1
        
        # EPA Equation (11): m = (FR10 * 0.4Q) / 10 = Q * RB
        # RB = FR10 * 0.4 / 10 = FR10 * 0.04
        m_release = building_attenuation * 0.04 * total_charge
        
        _, _, rho_v_ambient, _, _ = self._get_properties(ambient_temp)
        
        # Volumetric release rate
        v_release = m_release / rho_v_ambient if rho_v_ambient > 0 else m_release / 0.045
        
        # Outdoor concentration
        outdoor_ppm = (m_release * 1e6 / rho_v_ambient * 0.001) / exhaust_rate if exhaust_rate > 0 else 1e6
        
        # Indoor concentration
        ach = (exhaust_rate / room_volume) * 60 if room_volume > 0 else 0
        indoor_ppm = (v_release / exhaust_rate) * 1e6 if exhaust_rate > 0 else 1e6
        
        M_leak = m_release * release_duration
        
        return ReleaseResult(
            vapor_release_rate_lb_min=m_release,
            mass_released_lb=M_leak,
            exhaust_rate_cfm=exhaust_rate,
            indoor_concentration_ppm=indoor_ppm,
            outdoor_concentration_ppm=outdoor_ppm,
            room_air_changes_hr=ach,
            leak_duration_min=release_duration,
            hole_diameter_in=0,  # Not applicable
            method="EPA Worst Case Scenario"
        )
    
    def nfpa_toxic_gas_release(
        self,
        hole_diameter: float,
        system_pressure: float,
        leak_duration: float,
        room_volume: float,
        exhaust_rate: float,
        ambient_temp: float = 77,
    ) -> ReleaseResult:
        """
        NFPA 1 Toxic Gas Release calculation.
        
        Args:
            hole_diameter: Leak hole diameter (inches)
            system_pressure: System pressure (psia)
            leak_duration: Leak duration (minutes)
            room_volume: Room volume (ft³)
            exhaust_rate: Exhaust rate (CFM)
            ambient_temp: Ambient temperature (°F)
        
        Returns:
            ReleaseResult with calculated values
        """
        # NFPA Equation (16): v = 767 * A * P * sqrt(28.96/MW) / 60
        A_leak = math.pi * (hole_diameter) ** 2 / 4  # in²
        v_release_cfm = 767 * A_leak * system_pressure * math.sqrt(28.96 / self.MOLECULAR_WEIGHT) / 60
        
        _, _, rho_v_ambient, _, _ = self._get_properties(ambient_temp)
        
        # Mass release rate
        m_release = v_release_cfm * rho_v_ambient
        
        M_leak = m_release * leak_duration
        
        ach = (exhaust_rate / room_volume) * 60 if room_volume > 0 else 0
        
        indoor_ppm = (v_release_cfm / exhaust_rate) * 1e6 if exhaust_rate > 0 else 1e6
        outdoor_ppm = indoor_ppm * 0.001  # With scrubber
        
        return ReleaseResult(
            vapor_release_rate_lb_min=m_release,
            mass_released_lb=M_leak,
            exhaust_rate_cfm=exhaust_rate,
            indoor_concentration_ppm=indoor_ppm,
            outdoor_concentration_ppm=outdoor_ppm,
            room_air_changes_hr=ach,
            leak_duration_min=leak_duration,
            hole_diameter_in=hole_diameter,
            method="NFPA 1 Toxic Gas Release"
        )
    
    def calculate_required_exhaust(
        self,
        vapor_release_rate: float,
        target_outdoor_ppm: float = 40,
        removal_efficiency: float = 0.999,
        ambient_temp: float = 77,
    ) -> float:
        """
        Calculate required exhaust rate to achieve target outdoor concentration.
        
        Args:
            vapor_release_rate: Vapor release rate (lb/min)
            target_outdoor_ppm: Target outdoor concentration (ppm)
            removal_efficiency: Scrubber removal efficiency (0-1)
            ambient_temp: Ambient temperature (°F)
        
        Returns:
            Required exhaust rate (CFM)
        """
        _, _, rho_v_ambient, _, _ = self._get_properties(ambient_temp)
        
        if target_outdoor_ppm <= 0:
            return float('inf')
        
        exhaust_cfm = ((vapor_release_rate * 1e6) / rho_v_ambient) * (1 - removal_efficiency) / target_outdoor_ppm
        
        return exhaust_cfm


def quick_release_rate(
    hole_diameter_in: float,
    system_temp_f: float,
    release_type: str = 'flashing',
) -> float:
    """
    Quick estimate of ammonia release rate.
    
    Args:
        hole_diameter_in: Hole diameter (inches)
        system_temp_f: System temperature (°F)
        release_type: 'flashing', 'vapor', or 'pool'
    
    Returns:
        Estimated release rate (lb/min)
    
    Example:
        >>> rate = quick_release_rate(0.25, 95, 'flashing')
        >>> print(f"Release rate: {rate:.1f} lb/min")
    """
    calc = NH3ReleaseCalculator()
    
    if release_type == 'flashing':
        result = calc.iiar_flashing_release(
            hole_diameter=hole_diameter_in,
            system_temp=system_temp_f,
            leak_duration=1,
            room_volume=50000,
        )
    elif release_type == 'vapor':
        # Estimate pressure from temperature
        props = calc._get_properties(system_temp_f)
        pressure = props[0]
        result = calc.iiar_vapor_release(
            hole_diameter=hole_diameter_in,
            system_pressure=pressure,
            leak_duration=1,
            room_volume=50000,
        )
    else:  # pool
        result = calc.iiar_non_flashing_release(
            hole_diameter=hole_diameter_in,
            system_temp=system_temp_f,
            leak_duration=1,
            room_volume=50000,
        )
    
    return result.vapor_release_rate_lb_min
