"""
Evaporator Selection and Sizing Module
======================================

Calculate and select evaporators/air coolers for:
- Cold storage rooms
- Blast freezers
- Process cooling

Includes capacity corrections for altitude, entering air temp, and humidity.
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class EvaporatorType(Enum):
    """Types of evaporators."""
    UNIT_COOLER = "unit_cooler"
    PENTHOUSE = "penthouse"
    REACH_IN = "reach_in"
    BLAST = "blast"
    SPIRAL = "spiral"
    PLATE = "plate"
    SHELL_TUBE = "shell_tube"


class DefrostType(Enum):
    """Defrost methods."""
    AIR = "air"           # Off-cycle/air defrost
    ELECTRIC = "electric"
    HOT_GAS = "hot_gas"
    WATER = "water"
    GLYCOL = "glycol"


class FinSpacing(Enum):
    """Fin spacing options."""
    FPI_2 = 2    # 2 fins per inch - low temp freezers
    FPI_3 = 3    # 3 FPI - freezers
    FPI_4 = 4    # 4 FPI - coolers/freezers
    FPI_6 = 6    # 6 FPI - coolers
    FPI_8 = 8    # 8 FPI - coolers, high humidity
    FPI_10 = 10  # 10 FPI - process cooling


@dataclass
class EvaporatorSpecs:
    """Evaporator specifications."""
    model: str
    capacity_tons: float        # Rated capacity (tons)
    rated_td: float            # Rated TD (°F)
    rated_suction_temp: float  # Rated SST (°F)
    cfm: float                 # Airflow (CFM)
    fan_hp: float              # Total fan motor HP
    num_fans: int              # Number of fans
    face_area_sqft: float      # Coil face area (ft²)
    fin_spacing: int           # Fins per inch
    defrost_type: DefrostType
    defrost_kw: float = 0      # Electric defrost kW
    coil_volume_cuft: float = 0  # Internal volume


@dataclass
class EvaporatorResult:
    """Results from evaporator selection/sizing."""
    required_capacity_tons: float
    corrected_capacity_tons: float
    num_units: int
    capacity_per_unit_tons: float
    total_cfm: float
    total_fan_hp: float
    face_velocity_fpm: float
    air_throws_ft: float
    defrost_kw_total: float
    estimated_charge_lb: float
    td_applied: float
    notes: List[str]


class EvaporatorCalculator:
    """
    Evaporator selection and capacity calculator.
    
    Example:
        >>> calc = EvaporatorCalculator()
        >>> result = calc.select_unit_coolers(
        ...     load_tons=25,
        ...     room_temp=35,
        ...     suction_temp=25,
        ...     room_length=100,
        ...     room_width=50,
        ...     room_height=20
        ... )
        >>> print(f"Units required: {result.num_units}")
    """
    
    # TD recommendations by application
    RECOMMENDED_TD = {
        # (min_temp, max_temp): TD
        (-60, -30): 8,   # Ultra-low freezers
        (-30, -10): 10,  # Low temp freezers
        (-10, 15): 10,   # Freezers
        (15, 32): 10,    # Sharp freeze
        (32, 38): 10,    # High humidity coolers
        (38, 45): 12,    # Medium humidity coolers
        (45, 55): 15,    # Low humidity coolers
        (55, 70): 20,    # Process/dock
    }
    
    # Air throw distances by fan diameter (feet)
    AIR_THROW = {
        12: 35,   # 12" fan
        14: 45,
        16: 55,
        18: 65,
        20: 75,
        22: 85,
        24: 100,
        26: 110,
        28: 120,
        30: 130,
    }
    
    # Altitude correction factors
    ALTITUDE_FACTORS = {
        0: 1.00,
        1000: 0.97,
        2000: 0.93,
        3000: 0.90,
        4000: 0.87,
        5000: 0.83,
        6000: 0.80,
        7000: 0.77,
        8000: 0.74,
        10000: 0.69,
    }
    
    def __init__(self):
        pass
    
    def select_unit_coolers(
        self,
        load_tons: float,
        room_temp: float,
        suction_temp: float,
        room_length: float,
        room_width: float,
        room_height: float,
        altitude_ft: float = 0,
        relative_humidity: float = 85,
        product_type: str = "packaged",
        max_units: int = 8,
        td_override: float = None,
        defrost_type: DefrostType = None,
    ) -> EvaporatorResult:
        """
        Select unit coolers for a cold storage room.
        
        Args:
            load_tons: Required refrigeration load (tons)
            room_temp: Room design temperature (°F)
            suction_temp: Suction temperature (°F)
            room_length: Room length (ft)
            room_width: Room width (ft)
            room_height: Room height (ft)
            altitude_ft: Installation altitude (ft)
            relative_humidity: Design RH (%)
            product_type: "packaged", "open", "produce"
            max_units: Maximum number of units
            td_override: Override TD selection (°F)
            defrost_type: Defrost method
        
        Returns:
            EvaporatorResult with selection details
        """
        notes = []
        
        # Determine TD
        if td_override:
            td = td_override
        else:
            td = self._get_recommended_td(room_temp)
        
        # Verify TD is achievable
        max_td = room_temp - suction_temp
        if td > max_td:
            td = max_td - 2
            notes.append(f"TD reduced to {td}°F based on SST")
        
        # Determine defrost type
        if defrost_type is None:
            if room_temp >= 35:
                defrost_type = DefrostType.AIR
            elif room_temp >= 0:
                defrost_type = DefrostType.ELECTRIC
            else:
                defrost_type = DefrostType.HOT_GAS
        
        # Apply correction factors
        altitude_factor = self._get_altitude_factor(altitude_ft)
        td_factor = td / 10  # Base TD is 10°F
        
        # Total correction
        correction = altitude_factor * td_factor
        
        # Required rating at standard conditions
        required_rating = load_tons / correction
        
        # Determine number of units based on throw distance
        num_units = self._determine_unit_count(
            room_length, room_width, room_height, max_units
        )
        
        capacity_per_unit = required_rating / num_units
        
        # Size estimates
        cfm_per_ton = 400 if room_temp < 32 else 500
        total_cfm = required_rating * cfm_per_ton
        cfm_per_unit = total_cfm / num_units
        
        # Fan sizing (estimate)
        fan_hp_per_unit = cfm_per_unit / 2500  # ~2500 CFM per HP
        total_fan_hp = fan_hp_per_unit * num_units
        
        # Face area and velocity
        face_area_per_unit = cfm_per_unit / 500  # Target 500 FPM
        total_face_area = face_area_per_unit * num_units
        face_velocity = total_cfm / total_face_area if total_face_area > 0 else 500
        
        # Air throw estimate
        air_throw = self._estimate_throw(cfm_per_unit)
        
        # Defrost load
        if defrost_type == DefrostType.ELECTRIC:
            defrost_kw = capacity_per_unit * 3  # ~3 kW per ton
        elif defrost_type == DefrostType.HOT_GAS:
            defrost_kw = 0  # Refrigerant-based
        else:
            defrost_kw = 0
        
        # Charge estimate (varies by refrigerant and coil design)
        # Rough estimate: 2-4 lb per ton for NH3 DX, higher for flooded
        charge_per_unit = capacity_per_unit * 3  # lb
        
        return EvaporatorResult(
            required_capacity_tons=load_tons,
            corrected_capacity_tons=required_rating,
            num_units=num_units,
            capacity_per_unit_tons=capacity_per_unit,
            total_cfm=total_cfm,
            total_fan_hp=total_fan_hp,
            face_velocity_fpm=face_velocity,
            air_throws_ft=air_throw,
            defrost_kw_total=defrost_kw * num_units,
            estimated_charge_lb=charge_per_unit * num_units,
            td_applied=td,
            notes=notes,
        )
    
    def capacity_correction(
        self,
        rated_capacity: float,
        rated_td: float,
        rated_sst: float,
        actual_td: float,
        actual_sst: float = None,
        altitude_ft: float = 0,
    ) -> float:
        """
        Calculate corrected evaporator capacity.
        
        Args:
            rated_capacity: Catalog rated capacity (tons or MBH)
            rated_td: Rated TD (°F)
            rated_sst: Rated suction temperature (°F)
            actual_td: Actual operating TD (°F)
            actual_sst: Actual suction temperature (°F)
            altitude_ft: Installation altitude (ft)
        
        Returns:
            Corrected capacity in same units as input
        """
        # TD correction (approximately linear)
        td_factor = actual_td / rated_td
        
        # Altitude correction
        altitude_factor = self._get_altitude_factor(altitude_ft)
        
        # SST correction (if provided)
        sst_factor = 1.0
        if actual_sst is not None:
            # Capacity changes ~1-2% per °F of SST change
            sst_diff = actual_sst - rated_sst
            sst_factor = 1 + (sst_diff * 0.015)
        
        return rated_capacity * td_factor * altitude_factor * sst_factor
    
    def _get_recommended_td(self, room_temp: float) -> float:
        """Get recommended TD for room temperature."""
        for (min_t, max_t), td in self.RECOMMENDED_TD.items():
            if min_t <= room_temp < max_t:
                return td
        return 10  # Default
    
    def _get_altitude_factor(self, altitude: float) -> float:
        """Get altitude correction factor."""
        altitudes = sorted(self.ALTITUDE_FACTORS.keys())
        
        if altitude <= altitudes[0]:
            return self.ALTITUDE_FACTORS[altitudes[0]]
        if altitude >= altitudes[-1]:
            return self.ALTITUDE_FACTORS[altitudes[-1]]
        
        # Interpolate
        for i, alt in enumerate(altitudes):
            if alt >= altitude:
                alt_low = altitudes[i-1]
                alt_high = alt
                f = (altitude - alt_low) / (alt_high - alt_low)
                return self.ALTITUDE_FACTORS[alt_low] + \
                       f * (self.ALTITUDE_FACTORS[alt_high] - self.ALTITUDE_FACTORS[alt_low])
        
        return 1.0
    
    def _determine_unit_count(
        self,
        length: float,
        width: float,
        height: float,
        max_units: int,
    ) -> int:
        """Determine number of evaporator units based on room geometry."""
        # Calculate required throw
        # Units typically mounted along length, throwing across width
        required_throw = width / 2  # Throw to center
        
        # Estimate fan diameter needed
        fan_dia = 18  # Default
        for dia, throw in sorted(self.AIR_THROW.items()):
            if throw >= required_throw:
                fan_dia = dia
                break
        
        # Spacing between units
        unit_spacing = self.AIR_THROW.get(fan_dia, 60) * 0.8
        
        # Number of units along length
        num_units = max(2, int(length / unit_spacing) + 1)
        
        return min(num_units, max_units)
    
    def _estimate_throw(self, cfm: float) -> float:
        """Estimate air throw distance from CFM."""
        # Rough correlation
        if cfm < 3000:
            return 40
        elif cfm < 6000:
            return 60
        elif cfm < 10000:
            return 80
        elif cfm < 15000:
            return 100
        else:
            return 120
    
    def fin_spacing_recommendation(
        self,
        room_temp: float,
        relative_humidity: float = 85,
        product: str = "packaged",
    ) -> int:
        """
        Recommend fin spacing for application.
        
        Args:
            room_temp: Room temperature (°F)
            relative_humidity: Design RH (%)
            product: "packaged", "open_product", "produce"
        
        Returns:
            Recommended fins per inch (FPI)
        """
        if room_temp < -20:
            return 2  # Very low temp - minimize frost
        elif room_temp < 0:
            return 3
        elif room_temp < 28:
            return 4
        elif room_temp < 35:
            if relative_humidity > 90 or product == "produce":
                return 4
            return 6
        elif room_temp < 45:
            if product == "produce":
                return 6
            return 8
        else:
            return 10
    
    def defrost_sizing(
        self,
        capacity_tons: float,
        room_temp: float,
        defrost_type: DefrostType,
    ) -> Dict:
        """
        Size defrost system for evaporator.
        
        Returns:
            Dict with defrost specs
        """
        result = {
            'defrost_type': defrost_type.value,
            'electric_kw': 0,
            'hot_gas_lb_hr': 0,
            'defrost_duration_min': 30,
            'drip_time_min': 10,
            'defrosts_per_day': 2,
        }
        
        if room_temp >= 35:
            result['defrosts_per_day'] = 0  # Air defrost
            result['defrost_type'] = 'air'
            return result
        
        if defrost_type == DefrostType.ELECTRIC:
            # 2.5-4 kW per ton of evaporator capacity
            result['electric_kw'] = capacity_tons * 3
            result['defrost_duration_min'] = 30
            
        elif defrost_type == DefrostType.HOT_GAS:
            # Hot gas flow rate
            result['hot_gas_lb_hr'] = capacity_tons * 20  # Approximate
            result['defrost_duration_min'] = 20
        
        # Defrost frequency
        if room_temp < -20:
            result['defrosts_per_day'] = 4
        elif room_temp < 0:
            result['defrosts_per_day'] = 3
        else:
            result['defrosts_per_day'] = 2
        
        return result


def quick_evaporator_sizing(
    load_tons: float,
    room_temp: float,
    td: float = None,
) -> Dict:
    """
    Quick evaporator sizing estimate.
    
    Args:
        load_tons: Required load (tons)
        room_temp: Room temperature (°F)
        td: TD override (°F)
    
    Returns:
        Dict with sizing estimates
    """
    if td is None:
        if room_temp < 0:
            td = 10
        elif room_temp < 35:
            td = 10
        else:
            td = 12
    
    cfm_per_ton = 400 if room_temp < 32 else 500
    
    return {
        'load_tons': load_tons,
        'td_deg_f': td,
        'estimated_cfm': load_tons * cfm_per_ton,
        'estimated_fan_hp': load_tons * cfm_per_ton / 2500,
        'estimated_face_area_sqft': load_tons * cfm_per_ton / 500,
        'estimated_coil_mbh': load_tons * 12,
    }
