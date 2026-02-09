"""
Refrigerant Charge Calculation Module
=====================================

Calculate refrigerant charge for:
- Vessels (horizontal and vertical)
- Evaporator coils (flooded, recirculated, DX)
- Condensers
- Piping (liquid, suction, discharge)
- Heat exchangers

Based on IIAR and ASHRAE guidelines.
"""

import math
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from .properties import RefrigerantProperties, NH3Properties, get_refrigerant


class VesselOrientation(Enum):
    """Vessel orientation types."""
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class CoilType(Enum):
    """Evaporator coil types."""
    FLOODED = "flooded"
    RECIRCULATED = "recirculated"
    TOP_FEED = "top_feed"
    BOTTOM_FEED = "bottom_feed"
    DX = "dx"


class HeadType(Enum):
    """Vessel head types."""
    ELLIPTICAL_2_1 = "2:1 elliptical"
    HEMISPHERICAL = "hemispherical"
    FLAT = "flat"
    DISHED = "dished"


@dataclass
class VesselDimensions:
    """Vessel physical dimensions."""
    diameter: float          # inches
    length: float            # inches (shell length, not including heads)
    head_type: HeadType = HeadType.ELLIPTICAL_2_1
    wall_thickness: float = 0.375  # inches
    
    @property
    def internal_diameter(self) -> float:
        """Internal diameter in inches."""
        return self.diameter - 2 * self.wall_thickness
    
    @property
    def head_depth(self) -> float:
        """Head depth in inches for 2:1 elliptical heads."""
        if self.head_type == HeadType.ELLIPTICAL_2_1:
            return self.internal_diameter / 4
        elif self.head_type == HeadType.HEMISPHERICAL:
            return self.internal_diameter / 2
        else:
            return 0
    
    @property
    def total_length(self) -> float:
        """Total vessel length including heads (inches)."""
        return self.length + 2 * self.head_depth


@dataclass
class ChargeResult:
    """Results from charge calculation."""
    liquid_charge: float      # lb
    vapor_charge: float       # lb
    total_charge: float       # lb
    liquid_volume: float      # ft³
    vapor_volume: float       # ft³
    total_volume: float       # ft³
    fill_percentage: float    # %
    description: str = ""


class ChargeCalculator:
    """
    Refrigerant charge calculator.
    
    Calculate refrigerant inventory for various system components.
    
    Example:
        >>> calc = ChargeCalculator('NH3')
        >>> vessel = VesselDimensions(diameter=48, length=120)
        >>> result = calc.vessel_charge(
        ...     vessel=vessel,
        ...     orientation=VesselOrientation.HORIZONTAL,
        ...     operating_temp=28,
        ...     operating_level=0.5
        ... )
        >>> print(f"Total charge: {result.total_charge:.1f} lb")
    """
    
    # Standard vessel head dimensions (diameter -> head depth for 2:1 elliptical)
    HEAD_DEPTHS = {
        24: 6.0, 30: 7.5, 36: 9.0, 42: 10.5, 48: 12.0, 54: 13.5,
        60: 15.0, 66: 16.5, 72: 18.0, 78: 19.5, 84: 21.0, 90: 22.5,
        96: 24.0, 102: 25.5, 108: 27.0, 114: 28.5, 120: 30.0, 126: 31.5,
        132: 33.0, 138: 34.5, 144: 36.0, 156: 39.0,
    }
    
    # Standard wall thicknesses by MAWP
    WALL_THICKNESS = {
        '150psig': {24: 0.25, 30: 0.25, 36: 0.3125, 42: 0.375, 48: 0.4375, 
                    54: 0.5, 60: 0.5, 66: 0.5625, 72: 0.625, 84: 0.75},
        '250psig': {24: 0.3125, 30: 0.375, 36: 0.4375, 42: 0.5, 48: 0.5625,
                    54: 0.625, 60: 0.6875, 66: 0.75, 72: 0.8125, 84: 0.9375},
        '300psig': {24: 0.375, 30: 0.4375, 36: 0.5, 42: 0.5625, 48: 0.625,
                    54: 0.6875, 60: 0.75, 66: 0.8125, 72: 0.875, 84: 1.0},
    }
    
    def __init__(self, refrigerant: Union[str, RefrigerantProperties] = 'NH3'):
        """
        Initialize charge calculator.
        
        Args:
            refrigerant: Refrigerant name or RefrigerantProperties object
        """
        if isinstance(refrigerant, str):
            self.refrigerant = get_refrigerant(refrigerant)
        else:
            self.refrigerant = refrigerant
    
    def vessel_charge(
        self,
        vessel: VesselDimensions,
        orientation: VesselOrientation,
        operating_temp: float,
        operating_level: float = 0.5,
        surge_level: float = 0.75,
        mawp: str = '250psig',
    ) -> ChargeResult:
        """
        Calculate refrigerant charge in a vessel.
        
        Args:
            vessel: VesselDimensions object
            orientation: HORIZONTAL or VERTICAL
            operating_temp: Operating temperature (°F)
            operating_level: Normal liquid level (fraction of diameter, 0-1)
            surge_level: Surge liquid level (fraction of diameter, 0-1)
            mawp: Maximum allowable working pressure
        
        Returns:
            ChargeResult with charge breakdown
        """
        # Get properties
        props = self.refrigerant.get_properties_at_temp(operating_temp)
        rho_l = props.liquid_density
        rho_v = props.vapor_density
        
        # Get wall thickness
        diameter_key = min(self.WALL_THICKNESS.get(mawp, {}).keys(), 
                          key=lambda x: abs(x - vessel.diameter), default=None)
        if diameter_key and mawp in self.WALL_THICKNESS:
            wall_thickness = self.WALL_THICKNESS[mawp].get(diameter_key, vessel.wall_thickness)
        else:
            wall_thickness = vessel.wall_thickness
        
        # Internal dimensions
        d_int = vessel.diameter - 2 * wall_thickness
        r_int = d_int / 2
        
        # Head volume (2:1 elliptical)
        head_depth = d_int / 4
        head_volume = 2 * (2 * math.pi * head_depth ** 3 / 3) / 1728  # Two heads, ft³
        
        if orientation == VesselOrientation.HORIZONTAL:
            # Horizontal vessel calculations
            liquid_volume, vapor_volume = self._horizontal_vessel_volumes(
                d_int, vessel.length, head_depth, operating_level
            )
        else:
            # Vertical vessel calculations
            liquid_volume, vapor_volume = self._vertical_vessel_volumes(
                d_int, vessel.length, head_depth, operating_level
            )
        
        # Calculate charges
        liquid_charge = liquid_volume * rho_l
        vapor_charge = vapor_volume * rho_v
        total_charge = liquid_charge + vapor_charge
        total_volume = liquid_volume + vapor_volume
        
        fill_pct = operating_level * 100
        
        return ChargeResult(
            liquid_charge=liquid_charge,
            vapor_charge=vapor_charge,
            total_charge=total_charge,
            liquid_volume=liquid_volume,
            vapor_volume=vapor_volume,
            total_volume=total_volume,
            fill_percentage=fill_pct,
            description=f"{vessel.diameter}\" x {vessel.length}\" {orientation.value} vessel at {operating_temp}°F, {fill_pct:.0f}% full"
        )
    
    def _horizontal_vessel_volumes(
        self,
        diameter: float,
        length: float,
        head_depth: float,
        level: float,
    ) -> Tuple[float, float]:
        """Calculate liquid and vapor volumes for horizontal vessel."""
        r = diameter / 2
        h = level * diameter  # Liquid height from bottom
        
        # Shell liquid area (circular segment)
        if level <= 0:
            shell_liquid_area = 0
        elif level >= 1:
            shell_liquid_area = math.pi * r ** 2
        else:
            # Area of circular segment
            theta = 2 * math.acos((r - h) / r)
            shell_liquid_area = r ** 2 * (theta - math.sin(theta)) / 2
        
        shell_total_area = math.pi * r ** 2
        shell_vapor_area = shell_total_area - shell_liquid_area
        
        # Shell volumes (convert to ft³)
        shell_liquid_vol = shell_liquid_area * length / 1728
        shell_vapor_vol = shell_vapor_area * length / 1728
        
        # Head volumes (approximate for partial fill)
        # For 2:1 elliptical head at partial fill
        head_total_vol = 2 * (2 * math.pi * (head_depth) ** 3 / 3) / 1728
        head_liquid_vol = head_total_vol * (level ** 2) * (3 - 2 * level)  # Approximate
        head_vapor_vol = head_total_vol - head_liquid_vol
        
        liquid_volume = shell_liquid_vol + head_liquid_vol
        vapor_volume = shell_vapor_vol + head_vapor_vol
        
        return liquid_volume, vapor_volume
    
    def _vertical_vessel_volumes(
        self,
        diameter: float,
        length: float,
        head_depth: float,
        level: float,
    ) -> Tuple[float, float]:
        """Calculate liquid and vapor volumes for vertical vessel."""
        r = diameter / 2
        total_height = length + 2 * head_depth
        liquid_height = level * total_height
        
        # Cross-sectional area
        area = math.pi * r ** 2
        
        # Bottom head volume
        bottom_head_vol = 2 * math.pi * head_depth ** 3 / 3 / 1728
        
        if liquid_height <= head_depth:
            # Liquid only in bottom head
            fill_ratio = liquid_height / head_depth
            liquid_volume = bottom_head_vol * fill_ratio ** 2 * (3 - 2 * fill_ratio)
        elif liquid_height <= head_depth + length:
            # Liquid in bottom head + part of shell
            liquid_volume = bottom_head_vol
            shell_liquid_height = liquid_height - head_depth
            liquid_volume += area * shell_liquid_height / 1728
        else:
            # Liquid in bottom head + shell + part of top head
            liquid_volume = bottom_head_vol
            liquid_volume += area * length / 1728
            top_height = liquid_height - head_depth - length
            fill_ratio = top_height / head_depth
            top_head_liquid = bottom_head_vol * fill_ratio ** 2 * (3 - 2 * fill_ratio)
            liquid_volume += top_head_liquid
        
        # Total volume
        total_volume = 2 * bottom_head_vol + area * length / 1728
        vapor_volume = total_volume - liquid_volume
        
        return liquid_volume, vapor_volume
    
    def coil_charge(
        self,
        capacity_tons: float,
        suction_temp: float,
        coil_type: CoilType = CoilType.RECIRCULATED,
        tube_diameter: float = 0.625,  # inches
        tube_length: float = 10.0,     # ft per circuit
        num_circuits: int = 1,
        recirculation_rate: float = 4.0,
    ) -> ChargeResult:
        """
        Calculate refrigerant charge in an evaporator coil.
        
        Args:
            capacity_tons: Coil capacity (tons)
            suction_temp: Suction temperature (°F)
            coil_type: Type of coil (flooded, recirculated, DX)
            tube_diameter: Tube inside diameter (inches)
            tube_length: Length per circuit (ft)
            num_circuits: Number of circuits
            recirculation_rate: Recirculation rate (for recirculated coils)
        
        Returns:
            ChargeResult with charge breakdown
        """
        props = self.refrigerant.get_properties_at_temp(suction_temp)
        rho_l = props.liquid_density
        rho_v = props.vapor_density
        
        # Calculate tube volume
        tube_area = math.pi * (tube_diameter / 12) ** 2 / 4  # ft²
        tube_volume = tube_area * tube_length * num_circuits  # ft³
        
        # Determine liquid fraction based on coil type
        if coil_type == CoilType.FLOODED:
            liquid_fraction = 0.85  # Typically 85% flooded
        elif coil_type in [CoilType.RECIRCULATED, CoilType.TOP_FEED, CoilType.BOTTOM_FEED]:
            # Two-phase flow
            quality = 1 / recirculation_rate if recirculation_rate > 0 else 0.25
            # Void fraction using Zivi correlation
            slip_ratio = (rho_l / rho_v) ** (1/3)
            alpha = 1 / (1 + ((1 - quality) / quality) * (rho_v / rho_l) * slip_ratio)
            liquid_fraction = 1 - alpha
        else:  # DX
            liquid_fraction = 0.15  # Mostly vapor
        
        liquid_volume = tube_volume * liquid_fraction
        vapor_volume = tube_volume * (1 - liquid_fraction)
        
        liquid_charge = liquid_volume * rho_l
        vapor_charge = vapor_volume * rho_v
        total_charge = liquid_charge + vapor_charge
        
        return ChargeResult(
            liquid_charge=liquid_charge,
            vapor_charge=vapor_charge,
            total_charge=total_charge,
            liquid_volume=liquid_volume,
            vapor_volume=vapor_volume,
            total_volume=tube_volume,
            fill_percentage=liquid_fraction * 100,
            description=f"{capacity_tons} ton {coil_type.value} coil at {suction_temp}°F"
        )
    
    def pipe_charge(
        self,
        pipe_size: float,
        length: float,
        pipe_type: str,
        temperature: float,
        recirculation_rate: float = 1.0,
    ) -> ChargeResult:
        """
        Calculate refrigerant charge in piping.
        
        Args:
            pipe_size: Nominal pipe size (inches)
            length: Pipe length (ft)
            pipe_type: 'liquid', 'suction_dry', 'suction_wet', 'discharge'
            temperature: Operating temperature (°F)
            recirculation_rate: Recirculation rate for wet suction
        
        Returns:
            ChargeResult with charge breakdown
        """
        props = self.refrigerant.get_properties_at_temp(temperature)
        rho_l = props.liquid_density
        rho_v = props.vapor_density
        
        # Standard pipe internal diameters (Schedule 40)
        pipe_id = {
            0.5: 0.622, 0.75: 0.824, 1: 1.049, 1.25: 1.38, 1.5: 1.61,
            2: 2.067, 2.5: 2.469, 3: 3.068, 4: 4.026, 5: 5.047,
            6: 6.065, 8: 7.981, 10: 10.02, 12: 11.938,
        }.get(pipe_size, pipe_size * 0.9)  # Approximate if not found
        
        # Calculate pipe volume
        area = math.pi * (pipe_id / 12) ** 2 / 4  # ft²
        volume = area * length  # ft³
        
        # Determine liquid fraction
        if pipe_type == 'liquid':
            liquid_fraction = 1.0
        elif pipe_type == 'suction_dry' or pipe_type == 'discharge':
            liquid_fraction = 0.0
        elif pipe_type == 'suction_wet':
            quality = 1 / recirculation_rate if recirculation_rate > 0 else 0.25
            slip_ratio = (rho_l / rho_v) ** (1/3)
            alpha = 1 / (1 + ((1 - quality) / quality) * (rho_v / rho_l) * slip_ratio)
            liquid_fraction = 1 - alpha
        else:
            liquid_fraction = 0.5  # Default
        
        liquid_volume = volume * liquid_fraction
        vapor_volume = volume * (1 - liquid_fraction)
        
        liquid_charge = liquid_volume * rho_l
        vapor_charge = vapor_volume * rho_v
        total_charge = liquid_charge + vapor_charge
        
        return ChargeResult(
            liquid_charge=liquid_charge,
            vapor_charge=vapor_charge,
            total_charge=total_charge,
            liquid_volume=liquid_volume,
            vapor_volume=vapor_volume,
            total_volume=volume,
            fill_percentage=liquid_fraction * 100,
            description=f"{pipe_size}\" x {length}ft {pipe_type} pipe at {temperature}°F"
        )
    
    def condenser_charge(
        self,
        capacity_tons: float,
        condensing_temp: float,
        condenser_type: str = 'evaporative',
        receiver_size: float = 0,  # gallons
    ) -> ChargeResult:
        """
        Calculate refrigerant charge in a condenser.
        
        Args:
            capacity_tons: Condenser capacity (tons)
            condensing_temp: Condensing temperature (°F)
            condenser_type: 'evaporative', 'air_cooled', 'shell_tube'
            receiver_size: Integral receiver size (gallons)
        
        Returns:
            ChargeResult with charge breakdown
        """
        props = self.refrigerant.get_properties_at_temp(condensing_temp)
        rho_l = props.liquid_density
        rho_v = props.vapor_density
        
        # Estimate condenser volume based on type and capacity
        # These are rough estimates - actual values vary by manufacturer
        if condenser_type == 'evaporative':
            # ~0.4 lb/ton for vapor, ~0.8 lb/ton for liquid
            vapor_charge = capacity_tons * 0.4
            liquid_charge = capacity_tons * 0.8
        elif condenser_type == 'air_cooled':
            vapor_charge = capacity_tons * 0.3
            liquid_charge = capacity_tons * 0.5
        else:  # shell_tube
            vapor_charge = capacity_tons * 0.2
            liquid_charge = capacity_tons * 1.0
        
        # Add receiver charge
        if receiver_size > 0:
            receiver_vol = receiver_size / 7.48  # Convert gallons to ft³
            liquid_charge += receiver_vol * rho_l * 0.8  # 80% full
        
        vapor_volume = vapor_charge / rho_v if rho_v > 0 else 0
        liquid_volume = liquid_charge / rho_l if rho_l > 0 else 0
        total_charge = liquid_charge + vapor_charge
        total_volume = liquid_volume + vapor_volume
        
        return ChargeResult(
            liquid_charge=liquid_charge,
            vapor_charge=vapor_charge,
            total_charge=total_charge,
            liquid_volume=liquid_volume,
            vapor_volume=vapor_volume,
            total_volume=total_volume,
            fill_percentage=liquid_volume / total_volume * 100 if total_volume > 0 else 0,
            description=f"{capacity_tons} ton {condenser_type} condenser at {condensing_temp}°F"
        )


def calculate_system_charge(components: List[ChargeResult]) -> ChargeResult:
    """
    Sum up total system charge from multiple components.
    
    Args:
        components: List of ChargeResult objects
    
    Returns:
        Combined ChargeResult for entire system
    """
    total_liquid = sum(c.liquid_charge for c in components)
    total_vapor = sum(c.vapor_charge for c in components)
    total_liquid_vol = sum(c.liquid_volume for c in components)
    total_vapor_vol = sum(c.vapor_volume for c in components)
    total_volume = total_liquid_vol + total_vapor_vol
    
    descriptions = [c.description for c in components if c.description]
    
    return ChargeResult(
        liquid_charge=total_liquid,
        vapor_charge=total_vapor,
        total_charge=total_liquid + total_vapor,
        liquid_volume=total_liquid_vol,
        vapor_volume=total_vapor_vol,
        total_volume=total_volume,
        fill_percentage=total_liquid_vol / total_volume * 100 if total_volume > 0 else 0,
        description=f"System total: {len(components)} components"
    )
