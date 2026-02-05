"""
Machine Room Ventilation Module
===============================

Calculate ventilation requirements for refrigeration machine rooms per:
- IIAR Bulletin 111 (Ammonia)
- ASHRAE 15
- IMC (International Mechanical Code)

Includes:
- Emergency ventilation rates
- Normal ventilation rates
- Heat load calculations
- Air change calculations
"""

import math
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum


class VentilationStandard(Enum):
    """Ventilation code standards."""
    IIAR_2 = "IIAR-2"
    IIAR_2_2014 = "IIAR-2 2014"
    ASHRAE_15 = "ASHRAE 15"
    IMC = "IMC"
    CMC_2010 = "CMC 2010"


class RoomType(Enum):
    """Machine room types."""
    ATTACHED = "attached"
    DETACHED = "detached"


@dataclass
class RoomDimensions:
    """Machine room physical dimensions."""
    width: float   # ft
    length: float  # ft
    height: float  # ft
    
    @property
    def floor_area(self) -> float:
        """Floor area in ft²."""
        return self.width * self.length
    
    @property
    def volume(self) -> float:
        """Room volume in ft³."""
        return self.width * self.length * self.height


@dataclass
class WallConstruction:
    """Wall construction details for heat load calculations."""
    area: float            # ft²
    exterior_area: float   # ft² (exposed to outdoors)
    r_value: float = 19.0  # R-value
    color: str = "light"   # 'light', 'medium', 'dark'
    
    @property
    def u_value(self) -> float:
        """U-value (BTU/hr-ft²-°F)."""
        return 1.0 / self.r_value if self.r_value > 0 else 0


@dataclass
class VentilationResult:
    """Results from ventilation calculation."""
    emergency_cfm: float           # Emergency exhaust rate
    normal_cfm: float              # Normal/continuous ventilation rate
    occupied_cfm: float            # Occupied period ventilation rate
    air_changes_per_hour: float    # ACH at emergency rate
    heat_load_btu_hr: float        # Total heat load
    motor_heat_btu_hr: float       # Heat from motors
    transmission_heat_btu_hr: float # Heat through walls/roof
    design_temp_rise: float        # °F temperature rise
    num_fans_required: int         # Number of exhaust fans
    fan_size_cfm: float            # Individual fan size
    makeup_air_cfm: float          # Required makeup air


class MachineRoomVentilation:
    """
    Machine room ventilation calculator.
    
    Calculate ventilation requirements per IIAR, ASHRAE, and building codes.
    
    Example:
        >>> vent = MachineRoomVentilation()
        >>> room = RoomDimensions(width=40, length=60, height=16)
        >>> result = vent.calculate(
        ...     room=room,
        ...     system_charge=5000,  # lbs
        ...     motor_hp=150,
        ...     outdoor_design_temp=95
        ... )
        >>> print(f"Emergency exhaust: {result.emergency_cfm:,.0f} CFM")
    """
    
    # G values for IIAR-2 calculations (ft³/min per lb)
    G_VALUES = {
        'ammonia': 0.5,      # IIAR-2 default for NH3
        'r22': 0.5,
        'r404a': 0.5,
        'r507': 0.5,
        'co2': 0.5,
    }
    
    # Heat rejection from motors (BTU/hr per HP)
    MOTOR_HEAT_FACTOR = 2545  # BTU/hr per HP (at 100% efficiency loss to room)
    
    def __init__(self, standard: VentilationStandard = VentilationStandard.IIAR_2_2014):
        """
        Initialize ventilation calculator.
        
        Args:
            standard: Ventilation code standard to use
        """
        self.standard = standard
    
    def calculate(
        self,
        room: RoomDimensions,
        system_charge: float,
        motor_hp: float = 0,
        motor_efficiency: float = 0.92,
        outdoor_design_temp: float = 95,
        indoor_design_temp: float = 104,
        refrigerant: str = 'ammonia',
        roof: Optional[WallConstruction] = None,
        walls: Optional[List[WallConstruction]] = None,
        additional_heat_load: float = 0,
        continuous_supply_cfm: float = 0,
        swamp_cooler_cfm: float = 0,
        is_detached: bool = False,
        min_outdoor_temp: float = 32,
        max_occupancy: int = 1,
    ) -> VentilationResult:
        """
        Calculate ventilation requirements.
        
        Args:
            room: RoomDimensions object
            system_charge: Total refrigerant charge (lbs)
            motor_hp: Total motor horsepower in room
            motor_efficiency: Average motor efficiency (0-1)
            outdoor_design_temp: Summer design dry bulb temperature (°F)
            indoor_design_temp: Maximum allowable room temperature (°F)
            refrigerant: Refrigerant type
            roof: WallConstruction for roof
            walls: List of WallConstruction for walls
            additional_heat_load: Additional heat load (BTU/hr)
            continuous_supply_cfm: Existing continuous supply air (CFM)
            swamp_cooler_cfm: Evaporative cooler capacity (CFM)
            is_detached: True if machine room is detached from building
            min_outdoor_temp: Winter design temperature (°F)
            max_occupancy: Maximum number of occupants
        
        Returns:
            VentilationResult with all calculated values
        """
        # Emergency ventilation rate per IIAR-2
        G = self.G_VALUES.get(refrigerant.lower(), 0.5)
        emergency_cfm = self._calculate_emergency_rate(system_charge, G, room.volume)
        
        # Calculate heat loads
        motor_heat = self._calculate_motor_heat(motor_hp, motor_efficiency)
        
        transmission_heat = self._calculate_transmission_heat(
            roof, walls, outdoor_design_temp, indoor_design_temp
        )
        
        # Solar heat gain (simplified)
        solar_heat = 0
        if roof and roof.exterior_area > 0:
            # Approximate solar heat gain
            solar_factor = {'light': 0.4, 'medium': 0.6, 'dark': 0.8}.get(roof.color, 0.5)
            solar_heat = roof.exterior_area * 20 * solar_factor  # ~20 BTU/hr-ft² base
        
        total_heat = motor_heat + transmission_heat + solar_heat + additional_heat_load
        
        # Account for evaporative cooling
        if swamp_cooler_cfm > 0:
            # Evaporative coolers provide ~20°F temperature drop
            cooling_capacity = swamp_cooler_cfm * 1.08 * 20
            total_heat = max(0, total_heat - cooling_capacity)
        
        # Normal ventilation rate based on heat load
        # Q = H / (1.08 * ΔT)
        delta_t = indoor_design_temp - outdoor_design_temp
        if delta_t > 0:
            normal_cfm = total_heat / (1.08 * delta_t)
        else:
            normal_cfm = total_heat / (1.08 * 10)  # Assume 10°F rise
        
        # Minimum normal ventilation
        min_normal_cfm = 0.5 * room.volume  # 0.5 CFM per ft³ minimum
        normal_cfm = max(normal_cfm, min_normal_cfm)
        
        # Occupied ventilation (ASHRAE 62.1)
        # 20 CFM per person + 0.06 CFM per ft²
        occupied_cfm = max_occupancy * 20 + room.floor_area * 0.06
        
        # Air changes per hour
        ach = emergency_cfm * 60 / room.volume if room.volume > 0 else 0
        
        # Design temperature rise
        if normal_cfm > 0:
            design_temp_rise = total_heat / (1.08 * normal_cfm)
        else:
            design_temp_rise = 0
        
        # Number of fans (typically size for redundancy)
        # Common fan sizes
        fan_sizes = [5000, 7500, 10000, 15000, 20000, 25000, 30000]
        
        for fan_size in fan_sizes:
            num_fans = math.ceil(emergency_cfm / fan_size)
            if num_fans <= 4:  # Reasonable number of fans
                break
        else:
            fan_size = emergency_cfm / 4
            num_fans = 4
        
        # Makeup air
        makeup_air = emergency_cfm  # Equal to exhaust
        
        return VentilationResult(
            emergency_cfm=emergency_cfm,
            normal_cfm=normal_cfm,
            occupied_cfm=occupied_cfm,
            air_changes_per_hour=ach,
            heat_load_btu_hr=total_heat,
            motor_heat_btu_hr=motor_heat,
            transmission_heat_btu_hr=transmission_heat,
            design_temp_rise=design_temp_rise,
            num_fans_required=num_fans,
            fan_size_cfm=fan_size,
            makeup_air_cfm=makeup_air,
        )
    
    def _calculate_emergency_rate(
        self,
        charge_lbs: float,
        g_factor: float,
        room_volume: float,
    ) -> float:
        """
        Calculate emergency ventilation rate per IIAR-2.
        
        Q = G × √(charge)
        
        Minimum: 30 ACH for detached, 20 ACH for attached
        """
        # IIAR-2 formula
        emergency_cfm = g_factor * math.sqrt(charge_lbs) * 1000
        
        # Check minimum air changes (30 ACH typical for emergency)
        min_cfm = room_volume * 30 / 60  # 30 ACH minimum
        
        emergency_cfm = max(emergency_cfm, min_cfm)
        
        return emergency_cfm
    
    def _calculate_motor_heat(
        self,
        motor_hp: float,
        efficiency: float,
    ) -> float:
        """Calculate heat rejection from motors."""
        if efficiency <= 0 or efficiency >= 1:
            efficiency = 0.92
        
        # Heat rejection = HP × 2545 × (1 - efficiency) / efficiency
        # This is the heat rejected to the room
        heat_rejected = motor_hp * self.MOTOR_HEAT_FACTOR * (1 - efficiency) / efficiency
        
        return heat_rejected
    
    def _calculate_transmission_heat(
        self,
        roof: Optional[WallConstruction],
        walls: Optional[List[WallConstruction]],
        outdoor_temp: float,
        indoor_temp: float,
    ) -> float:
        """Calculate heat transmission through walls and roof."""
        total_heat = 0
        delta_t = outdoor_temp - indoor_temp
        
        if roof and roof.exterior_area > 0:
            # Roof heat gain (with sol-air temperature adjustment)
            sol_air_delta = delta_t + 20  # Add ~20°F for solar on roof
            total_heat += roof.u_value * roof.exterior_area * sol_air_delta
        
        if walls:
            for wall in walls:
                if wall.exterior_area > 0:
                    # Wall heat gain
                    sol_air_factor = {'light': 5, 'medium': 10, 'dark': 15}.get(wall.color, 7)
                    wall_delta = delta_t + sol_air_factor
                    total_heat += wall.u_value * wall.exterior_area * wall_delta
        
        return total_heat
    
    def calculate_winter_heating(
        self,
        room: RoomDimensions,
        outdoor_temp: float,
        indoor_temp: float,
        motor_hp: float,
        motor_efficiency: float = 0.92,
        roof: Optional[WallConstruction] = None,
        walls: Optional[List[WallConstruction]] = None,
    ) -> float:
        """
        Calculate winter heating requirement.
        
        Args:
            room: RoomDimensions
            outdoor_temp: Winter design temperature (°F)
            indoor_temp: Minimum indoor temperature (°F)
            motor_hp: Motor HP operating in winter
            motor_efficiency: Motor efficiency
            roof: Roof construction
            walls: Wall constructions
        
        Returns:
            Required heating capacity (BTU/hr)
        """
        delta_t = indoor_temp - outdoor_temp
        
        # Heat loss through envelope
        heat_loss = 0
        
        if roof and roof.exterior_area > 0:
            heat_loss += roof.u_value * roof.exterior_area * delta_t
        
        if walls:
            for wall in walls:
                if wall.exterior_area > 0:
                    heat_loss += wall.u_value * wall.exterior_area * delta_t
        
        # Infiltration loss (assume 0.5 ACH)
        infiltration_cfm = room.volume * 0.5 / 60
        infiltration_loss = 1.08 * infiltration_cfm * delta_t
        
        total_loss = heat_loss + infiltration_loss
        
        # Motor heat gain
        motor_heat = self._calculate_motor_heat(motor_hp, motor_efficiency)
        
        # Net heating required
        net_heating = total_loss - motor_heat
        
        return max(0, net_heating)


def iiar_emergency_exhaust(
    charge_lbs: float,
    room_volume_ft3: float,
    g_factor: float = 0.5,
) -> float:
    """
    Quick calculation of IIAR emergency exhaust rate.
    
    Args:
        charge_lbs: System refrigerant charge (lbs)
        room_volume_ft3: Room volume (ft³)
        g_factor: G factor (default 0.5 for ammonia)
    
    Returns:
        Emergency exhaust rate (CFM)
    
    Example:
        >>> cfm = iiar_emergency_exhaust(5000, 50000)
        >>> print(f"Emergency exhaust: {cfm:,.0f} CFM")
    """
    # IIAR-2 formula
    cfm = g_factor * math.sqrt(charge_lbs) * 1000
    
    # Minimum 30 ACH
    min_cfm = room_volume_ft3 * 30 / 60
    
    return max(cfm, min_cfm)


def air_changes_per_hour(cfm: float, room_volume_ft3: float) -> float:
    """
    Calculate air changes per hour.
    
    Args:
        cfm: Airflow rate (CFM)
        room_volume_ft3: Room volume (ft³)
    
    Returns:
        Air changes per hour (ACH)
    """
    if room_volume_ft3 <= 0:
        return 0
    return cfm * 60 / room_volume_ft3
