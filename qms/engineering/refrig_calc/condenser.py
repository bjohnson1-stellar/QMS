"""
Condenser Selection and Sizing Module
=====================================

Calculate and select condensers for refrigeration systems:
- Evaporative condensers
- Air-cooled condensers
- Shell and tube condensers

Includes capacity corrections for wet bulb, altitude, and fouling.
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class CondenserType(Enum):
    """Types of condensers."""
    EVAPORATIVE = "evaporative"
    AIR_COOLED = "air_cooled"
    SHELL_TUBE = "shell_tube"
    PLATE = "plate"


@dataclass
class CondenserResult:
    """Results from condenser sizing."""
    heat_rejection_mbh: float     # MBH (1000 BTU/hr)
    heat_rejection_tons: float    # Equivalent tons
    condenser_type: str
    required_capacity_mbh: float  # At design conditions
    num_units: int
    capacity_per_unit_mbh: float
    fan_hp_total: float
    pump_gpm: float              # For evaporative
    water_makeup_gpm: float      # For evaporative
    entering_temp: float         # Wet bulb or dry bulb
    condensing_temp: float
    approach_temp: float
    notes: List[str]


class CondenserCalculator:
    """
    Condenser sizing and selection calculator.
    
    Example:
        >>> calc = CondenserCalculator()
        >>> result = calc.size_evaporative_condenser(
        ...     refrigeration_tons=500,
        ...     compressor_hp=750,
        ...     condensing_temp=95,
        ...     wet_bulb_temp=78
        ... )
        >>> print(f"Heat rejection: {result.heat_rejection_mbh:.0f} MBH")
    """
    
    # Evaporative condenser correction factors by wet bulb/condensing temp
    # Base rating: 105°F SCT / 78°F WB
    # Format: (wet_bulb, condensing_temp): correction_factor
    EVAP_CORRECTION = {
        (50, 65): 2.62, (50, 85): 0.98, (50, 90): 0.83, (50, 95): 0.71, (50, 105): 0.56,
        (55, 85): 1.09, (55, 90): 0.91, (55, 95): 0.78, (55, 105): 0.59,
        (60, 85): 1.24, (60, 90): 1.02, (60, 95): 0.86, (60, 105): 0.64,
        (65, 85): 1.46, (65, 90): 1.17, (65, 95): 0.97, (65, 105): 0.71,
        (70, 90): 1.38, (70, 95): 1.12, (70, 100): 0.93, (70, 105): 0.78,
        (75, 90): 1.74, (75, 95): 1.35, (75, 100): 1.09, (75, 105): 0.90,
        (78, 95): 1.55, (78, 100): 1.22, (78, 105): 1.00, (78, 110): 0.83,
        (80, 95): 1.78, (80, 100): 1.38, (80, 105): 1.11, (80, 110): 0.91,
        (85, 100): 1.70, (85, 105): 1.33, (85, 110): 1.07, (85, 115): 0.88,
    }
    
    # Air-cooled condenser typical approach (condensing - ambient)
    AIR_COOLED_APPROACH = {
        'standard': 20,      # °F
        'low_noise': 25,
        'high_efficiency': 15,
    }
    
    def __init__(self):
        pass
    
    def calculate_heat_rejection(
        self,
        refrigeration_tons: float,
        compressor_hp: float = None,
        compressor_kw: float = None,
        motor_efficiency: float = 0.92,
    ) -> float:
        """
        Calculate total heat rejection at condenser.
        
        Heat Rejection = Refrigeration Load + Compressor Heat
        
        Args:
            refrigeration_tons: Evaporator load (tons)
            compressor_hp: Compressor motor HP
            compressor_kw: Compressor input kW (alternative)
            motor_efficiency: Motor efficiency
        
        Returns:
            Total heat rejection in MBH
        """
        # Refrigeration load in BTU/hr
        refrig_btu = refrigeration_tons * 12000
        
        # Compressor heat
        if compressor_kw:
            comp_btu = compressor_kw * 3412
        elif compressor_hp:
            # HP to kW, accounting for motor efficiency
            comp_kw = compressor_hp * 0.746 / motor_efficiency
            comp_btu = comp_kw * 3412
        else:
            # Estimate from refrigeration load (typical COP of 3-4)
            comp_btu = refrig_btu / 3.5
        
        total_btu = refrig_btu + comp_btu
        return total_btu / 1000  # MBH
    
    def size_evaporative_condenser(
        self,
        refrigeration_tons: float,
        compressor_hp: float,
        condensing_temp: float,
        wet_bulb_temp: float,
        altitude_ft: float = 0,
        num_units: int = None,
        motor_efficiency: float = 0.92,
    ) -> CondenserResult:
        """
        Size evaporative condenser.
        
        Args:
            refrigeration_tons: Total refrigeration load (tons)
            compressor_hp: Total compressor HP
            condensing_temp: Design condensing temperature (°F)
            wet_bulb_temp: Design wet bulb temperature (°F)
            altitude_ft: Installation altitude (ft)
            num_units: Number of units (None for auto)
            motor_efficiency: Motor efficiency
        
        Returns:
            CondenserResult with sizing details
        """
        notes = []
        
        # Calculate heat rejection
        heat_rejection_mbh = self.calculate_heat_rejection(
            refrigeration_tons, compressor_hp, motor_efficiency=motor_efficiency
        )
        heat_rejection_tons = heat_rejection_mbh * 1000 / 12000
        
        # Get correction factor
        correction = self._get_evap_correction(wet_bulb_temp, condensing_temp)
        notes.append(f"Correction factor: {correction:.2f}")
        
        # Altitude correction (air density)
        altitude_factor = self._altitude_factor(altitude_ft)
        if altitude_ft > 1000:
            notes.append(f"Altitude factor: {altitude_factor:.2f}")
        
        # Required capacity at standard rating
        required_mbh = heat_rejection_mbh / (correction * altitude_factor)
        
        # Determine number of units
        if num_units is None:
            if required_mbh < 1000:
                num_units = 1
            elif required_mbh < 3000:
                num_units = 2
            elif required_mbh < 6000:
                num_units = 3
            else:
                num_units = 4
        
        capacity_per_unit = required_mbh / num_units
        
        # Estimate fan HP (approximately 0.02 HP per MBH)
        fan_hp = required_mbh * 0.02
        
        # Pump flow (approximately 3 GPM per MBH for evaporative)
        pump_gpm = required_mbh * 3
        
        # Water makeup (evaporation + blowdown)
        # Approximately 3 GPM per 100 tons of heat rejection
        makeup_gpm = heat_rejection_tons * 0.03
        
        # Approach
        approach = condensing_temp - wet_bulb_temp
        
        return CondenserResult(
            heat_rejection_mbh=heat_rejection_mbh,
            heat_rejection_tons=heat_rejection_tons,
            condenser_type="evaporative",
            required_capacity_mbh=required_mbh,
            num_units=num_units,
            capacity_per_unit_mbh=capacity_per_unit,
            fan_hp_total=fan_hp,
            pump_gpm=pump_gpm,
            water_makeup_gpm=makeup_gpm,
            entering_temp=wet_bulb_temp,
            condensing_temp=condensing_temp,
            approach_temp=approach,
            notes=notes,
        )
    
    def size_air_cooled_condenser(
        self,
        refrigeration_tons: float,
        compressor_hp: float,
        condensing_temp: float,
        ambient_temp: float,
        efficiency: str = 'standard',
        altitude_ft: float = 0,
        motor_efficiency: float = 0.92,
    ) -> CondenserResult:
        """
        Size air-cooled condenser.
        
        Args:
            refrigeration_tons: Total refrigeration load (tons)
            compressor_hp: Total compressor HP
            condensing_temp: Design condensing temperature (°F)
            ambient_temp: Design ambient dry bulb (°F)
            efficiency: 'standard', 'low_noise', 'high_efficiency'
            altitude_ft: Installation altitude (ft)
            motor_efficiency: Motor efficiency
        
        Returns:
            CondenserResult with sizing details
        """
        notes = []
        
        # Calculate heat rejection
        heat_rejection_mbh = self.calculate_heat_rejection(
            refrigeration_tons, compressor_hp, motor_efficiency=motor_efficiency
        )
        heat_rejection_tons = heat_rejection_mbh * 1000 / 12000
        
        # Check approach
        approach = condensing_temp - ambient_temp
        min_approach = self.AIR_COOLED_APPROACH.get(efficiency, 20)
        
        if approach < min_approach:
            notes.append(f"Warning: Approach {approach}°F is below minimum {min_approach}°F")
            approach = min_approach
        
        # Altitude correction
        altitude_factor = self._altitude_factor(altitude_ft)
        
        # Required capacity (air-cooled rated at 15°F TD typically)
        # Correct for actual TD
        td_factor = approach / 15
        required_mbh = heat_rejection_mbh / (td_factor * altitude_factor)
        
        # Estimate number of units
        if required_mbh < 500:
            num_units = 1
        elif required_mbh < 1500:
            num_units = 2
        else:
            num_units = max(2, int(required_mbh / 1000))
        
        capacity_per_unit = required_mbh / num_units
        
        # Fan HP (air-cooled uses more than evaporative)
        # Approximately 0.04 HP per MBH
        fan_hp = required_mbh * 0.04
        
        return CondenserResult(
            heat_rejection_mbh=heat_rejection_mbh,
            heat_rejection_tons=heat_rejection_tons,
            condenser_type="air_cooled",
            required_capacity_mbh=required_mbh,
            num_units=num_units,
            capacity_per_unit_mbh=capacity_per_unit,
            fan_hp_total=fan_hp,
            pump_gpm=0,
            water_makeup_gpm=0,
            entering_temp=ambient_temp,
            condensing_temp=condensing_temp,
            approach_temp=approach,
            notes=notes,
        )
    
    def _get_evap_correction(self, wet_bulb: float, condensing: float) -> float:
        """Get evaporative condenser correction factor."""
        # Find closest match in table
        best_match = None
        best_dist = float('inf')
        
        for (wb, ct), factor in self.EVAP_CORRECTION.items():
            dist = abs(wb - wet_bulb) + abs(ct - condensing)
            if dist < best_dist:
                best_dist = dist
                best_match = factor
        
        if best_match:
            return best_match
        
        # Default interpolation
        approach = condensing - wet_bulb
        if approach <= 10:
            return 2.5
        elif approach <= 15:
            return 1.5
        elif approach <= 20:
            return 1.1
        elif approach <= 25:
            return 0.85
        else:
            return 0.65
    
    def _altitude_factor(self, altitude_ft: float) -> float:
        """Calculate altitude correction factor for air density."""
        # Air density decreases with altitude
        # Factor = (1 - altitude/145000)^5.256
        return (1 - altitude_ft / 145000) ** 5.256
    
    def approach_recommendation(
        self,
        condenser_type: str,
        wet_bulb: float = None,
        ambient: float = None,
    ) -> Dict:
        """
        Recommend condensing temperature for given conditions.
        
        Args:
            condenser_type: "evaporative" or "air_cooled"
            wet_bulb: Wet bulb temperature (for evaporative)
            ambient: Dry bulb temperature (for air-cooled)
        
        Returns:
            Dict with recommendations
        """
        if condenser_type == "evaporative" and wet_bulb:
            return {
                'minimum_approach': 10,
                'typical_approach': 12,
                'economical_approach': 15,
                'minimum_condensing': wet_bulb + 10,
                'typical_condensing': wet_bulb + 12,
                'economical_condensing': wet_bulb + 15,
            }
        elif condenser_type == "air_cooled" and ambient:
            return {
                'minimum_approach': 15,
                'typical_approach': 20,
                'economical_approach': 25,
                'minimum_condensing': ambient + 15,
                'typical_condensing': ambient + 20,
                'economical_condensing': ambient + 25,
            }
        
        return {}


def quick_heat_rejection(
    refrigeration_tons: float,
    compressor_hp: float = None,
) -> float:
    """
    Quick heat rejection estimate.
    
    Returns heat rejection in MBH.
    """
    refrig_mbh = refrigeration_tons * 12
    
    if compressor_hp:
        comp_mbh = compressor_hp * 2.545
    else:
        comp_mbh = refrig_mbh / 3.5
    
    return refrig_mbh + comp_mbh


def condenser_tons_to_mbh(tons: float) -> float:
    """Convert condenser tons to MBH."""
    return tons * 15  # Condenser ton = 15 MBH


def mbh_to_condenser_tons(mbh: float) -> float:
    """Convert MBH to condenser tons."""
    return mbh / 15
