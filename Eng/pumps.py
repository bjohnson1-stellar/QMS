"""
Pump Sizing Module
==================

Size and select pumps for refrigeration systems:
- Liquid refrigerant recirculation pumps
- Glycol/brine circulation pumps
- Condenser water pumps

Includes NPSH calculations and system curves.
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class PumpType(Enum):
    """Types of pumps."""
    CENTRIFUGAL = "centrifugal"
    HERMETIC = "hermetic"
    CANNED = "canned"
    REGENERATIVE = "regenerative"


class FluidType(Enum):
    """Fluid being pumped."""
    NH3_LIQUID = "nh3_liquid"
    GLYCOL = "glycol"
    BRINE = "brine"
    WATER = "water"
    R22_LIQUID = "r22_liquid"


@dataclass
class PumpResult:
    """Results from pump sizing."""
    flow_rate_gpm: float
    total_head_ft: float
    hydraulic_hp: float
    brake_hp: float
    motor_hp: float
    npsh_required_ft: float
    npsh_available_ft: float
    pump_efficiency: float
    specific_speed: float
    impeller_dia_in: float
    notes: List[str]


@dataclass 
class SystemCurvePoint:
    """Point on system curve."""
    flow_gpm: float
    head_ft: float


class PumpCalculator:
    """
    Pump sizing and selection calculator.
    
    Example:
        >>> calc = PumpCalculator()
        >>> result = calc.size_recirculation_pump(
        ...     capacity_tons=200,
        ...     recirculation_rate=4,
        ...     suction_temp=-10,
        ...     static_head_ft=15,
        ...     pipe_length_ft=200
        ... )
        >>> print(f"Motor HP: {result.motor_hp}")
    """
    
    # Standard motor HP sizes
    MOTOR_SIZES = [0.5, 0.75, 1, 1.5, 2, 3, 5, 7.5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200]
    
    # Pump efficiency curves (approximate) by specific speed
    EFFICIENCY_BY_NS = {
        500: 0.45,
        1000: 0.60,
        1500: 0.72,
        2000: 0.78,
        2500: 0.82,
        3000: 0.84,
        4000: 0.82,
        5000: 0.78,
    }
    
    # Pipe friction factors (ft head loss per 100 ft at 1 GPM) - schedule 40
    PIPE_FRICTION = {
        # Size (in): C factor for Hazen-Williams
        1: 150, 1.25: 150, 1.5: 150, 2: 150, 2.5: 150,
        3: 150, 4: 150, 6: 150, 8: 150,
    }
    
    def __init__(self):
        pass
    
    def size_recirculation_pump(
        self,
        capacity_tons: float,
        recirculation_rate: float,
        suction_temp: float,
        refrigerant: str = "NH3",
        static_head_ft: float = 10,
        pipe_length_ft: float = 200,
        pipe_size_in: float = None,
        num_elbows: int = 10,
        num_valves: int = 5,
        vessel_pressure_psig: float = None,
        liquid_level_above_pump_ft: float = 3,
    ) -> PumpResult:
        """
        Size a liquid refrigerant recirculation pump.
        
        Args:
            capacity_tons: Evaporator capacity (tons)
            recirculation_rate: Recirculation ratio (typically 3-6)
            suction_temp: Suction/vessel temperature (°F)
            refrigerant: Refrigerant type
            static_head_ft: Static discharge head (ft)
            pipe_length_ft: Pipe length (ft)
            pipe_size_in: Pipe size (inches) - auto-sized if None
            num_elbows: Number of elbows
            num_valves: Number of valves
            vessel_pressure_psig: Vessel pressure (psig)
            liquid_level_above_pump_ft: NPSH margin (ft)
        
        Returns:
            PumpResult with sizing details
        """
        notes = []
        
        # Get refrigerant properties
        props = self._get_refrigerant_props(refrigerant, suction_temp)
        density = props['density']
        vapor_pressure = props['vapor_pressure']
        latent_heat = props['latent_heat']
        
        if vessel_pressure_psig is None:
            vessel_pressure_psig = vapor_pressure - 14.7
        
        # Calculate flow rate
        # Mass flow = Capacity * 12000 / (latent_heat * (1 - 1/recirc))
        mass_flow_lb_hr = capacity_tons * 12000 / latent_heat * recirculation_rate
        vol_flow_gpm = mass_flow_lb_hr / (density * 60 / 7.48)
        
        notes.append(f"Mass flow: {mass_flow_lb_hr:.0f} lb/hr")
        notes.append(f"Volume flow: {vol_flow_gpm:.1f} GPM")
        
        # Auto-size pipe if not specified
        if pipe_size_in is None:
            pipe_size_in = self._select_pipe_size(vol_flow_gpm, target_velocity=5)
            notes.append(f"Auto-selected pipe: {pipe_size_in}\"")
        
        # Calculate friction head
        friction_head = self._calculate_friction_head(
            flow_gpm=vol_flow_gpm,
            pipe_size_in=pipe_size_in,
            length_ft=pipe_length_ft,
            num_elbows=num_elbows,
            num_valves=num_valves,
            specific_gravity=density / 62.4,
        )
        
        # Total head
        total_head = static_head_ft + friction_head
        notes.append(f"Friction head: {friction_head:.1f} ft")
        notes.append(f"Total head: {total_head:.1f} ft")
        
        # Calculate power
        sg = density / 62.4
        hydraulic_hp = vol_flow_gpm * total_head * sg / 3960
        
        # Estimate pump efficiency
        specific_speed = self._calculate_specific_speed(vol_flow_gpm, total_head, 3500)
        efficiency = self._estimate_efficiency(specific_speed)
        
        brake_hp = hydraulic_hp / efficiency
        
        # Select motor size
        motor_hp = self._select_motor_size(brake_hp)
        
        # NPSH calculations
        npsh_required = self._estimate_npsh_required(vol_flow_gpm, specific_speed)
        
        # NPSH available
        vessel_pressure_ft = vessel_pressure_psig * 144 / density
        vapor_pressure_ft = (vapor_pressure - 14.7) * 144 / density
        npsh_available = liquid_level_above_pump_ft + vessel_pressure_ft - vapor_pressure_ft
        
        notes.append(f"NPSHA: {npsh_available:.1f} ft")
        notes.append(f"NPSHR: {npsh_required:.1f} ft")
        
        if npsh_available < npsh_required + 2:
            notes.append("WARNING: Low NPSH margin!")
        
        # Estimate impeller diameter
        impeller_dia = self._estimate_impeller_dia(vol_flow_gpm, total_head)
        
        return PumpResult(
            flow_rate_gpm=vol_flow_gpm,
            total_head_ft=total_head,
            hydraulic_hp=hydraulic_hp,
            brake_hp=brake_hp,
            motor_hp=motor_hp,
            npsh_required_ft=npsh_required,
            npsh_available_ft=npsh_available,
            pump_efficiency=efficiency,
            specific_speed=specific_speed,
            impeller_dia_in=impeller_dia,
            notes=notes,
        )
    
    def size_glycol_pump(
        self,
        capacity_tons: float,
        supply_temp: float,
        return_temp: float,
        glycol_concentration: float,
        static_head_ft: float = 20,
        pipe_length_ft: float = 500,
        pipe_size_in: float = None,
    ) -> PumpResult:
        """
        Size a glycol circulation pump.
        
        Args:
            capacity_tons: Cooling capacity (tons)
            supply_temp: Glycol supply temperature (°F)
            return_temp: Glycol return temperature (°F)
            glycol_concentration: Glycol % by weight
            static_head_ft: Static head (ft)
            pipe_length_ft: Total pipe length (ft)
            pipe_size_in: Pipe size (inches)
        
        Returns:
            PumpResult
        """
        notes = []
        
        # Glycol properties
        sg = 1.0 + 0.001 * glycol_concentration
        cp = 1.0 - 0.004 * glycol_concentration  # BTU/lb-°F
        density = sg * 62.4  # lb/ft³
        
        # Temperature difference
        delta_t = return_temp - supply_temp
        if delta_t <= 0:
            delta_t = 10
            notes.append("Using default 10°F temperature range")
        
        # Flow rate
        heat_load = capacity_tons * 12000  # BTU/hr
        mass_flow = heat_load / (cp * delta_t)  # lb/hr
        vol_flow_gpm = mass_flow / (density * 60 / 7.48)
        
        notes.append(f"Flow rate: {vol_flow_gpm:.1f} GPM")
        
        # Auto-size pipe
        if pipe_size_in is None:
            pipe_size_in = self._select_pipe_size(vol_flow_gpm, target_velocity=6)
        
        # Friction head (glycol has higher viscosity)
        viscosity_factor = 1 + 0.02 * glycol_concentration
        friction_head = self._calculate_friction_head(
            flow_gpm=vol_flow_gpm,
            pipe_size_in=pipe_size_in,
            length_ft=pipe_length_ft,
            num_elbows=20,
            num_valves=10,
            specific_gravity=sg,
        ) * viscosity_factor
        
        total_head = static_head_ft + friction_head
        
        # Power
        hydraulic_hp = vol_flow_gpm * total_head * sg / 3960
        specific_speed = self._calculate_specific_speed(vol_flow_gpm, total_head, 1750)
        efficiency = self._estimate_efficiency(specific_speed)
        brake_hp = hydraulic_hp / efficiency
        motor_hp = self._select_motor_size(brake_hp)
        
        return PumpResult(
            flow_rate_gpm=vol_flow_gpm,
            total_head_ft=total_head,
            hydraulic_hp=hydraulic_hp,
            brake_hp=brake_hp,
            motor_hp=motor_hp,
            npsh_required_ft=5,
            npsh_available_ft=20,  # Typically not critical for glycol
            pump_efficiency=efficiency,
            specific_speed=specific_speed,
            impeller_dia_in=self._estimate_impeller_dia(vol_flow_gpm, total_head),
            notes=notes,
        )
    
    def calculate_system_curve(
        self,
        static_head_ft: float,
        design_flow_gpm: float,
        design_friction_head_ft: float,
        num_points: int = 10,
    ) -> List[SystemCurvePoint]:
        """
        Calculate system curve points.
        
        Friction loss varies with flow squared.
        
        Args:
            static_head_ft: Static head (constant)
            design_flow_gpm: Design flow rate
            design_friction_head_ft: Friction loss at design flow
            num_points: Number of curve points
        
        Returns:
            List of SystemCurvePoint
        """
        points = []
        
        for i in range(num_points + 1):
            flow = design_flow_gpm * i / num_points
            # Friction varies with flow²
            if design_flow_gpm > 0:
                friction = design_friction_head_ft * (flow / design_flow_gpm) ** 2
            else:
                friction = 0
            total_head = static_head_ft + friction
            points.append(SystemCurvePoint(flow, total_head))
        
        return points
    
    def affinity_laws(
        self,
        base_flow_gpm: float,
        base_head_ft: float,
        base_hp: float,
        base_speed_rpm: float,
        new_speed_rpm: float = None,
        new_impeller_dia: float = None,
        base_impeller_dia: float = None,
    ) -> Dict:
        """
        Calculate new pump performance using affinity laws.
        
        Args:
            base_flow_gpm: Base flow rate
            base_head_ft: Base head
            base_hp: Base horsepower
            base_speed_rpm: Base speed (RPM)
            new_speed_rpm: New speed (RPM)
            new_impeller_dia: New impeller diameter
            base_impeller_dia: Base impeller diameter
        
        Returns:
            Dict with new flow, head, and power
        """
        # Speed ratio
        if new_speed_rpm and base_speed_rpm:
            ratio = new_speed_rpm / base_speed_rpm
        elif new_impeller_dia and base_impeller_dia:
            ratio = new_impeller_dia / base_impeller_dia
        else:
            ratio = 1.0
        
        new_flow = base_flow_gpm * ratio
        new_head = base_head_ft * ratio ** 2
        new_hp = base_hp * ratio ** 3
        
        return {
            'flow_gpm': new_flow,
            'head_ft': new_head,
            'hp': new_hp,
            'ratio': ratio,
        }
    
    def _get_refrigerant_props(self, refrigerant: str, temp: float) -> Dict:
        """Get refrigerant properties."""
        # Simplified property tables
        if refrigerant.upper() == "NH3":
            density = 42 - 0.08 * (temp + 40)  # lb/ft³
            vapor_pressure = 30 + 2.5 * (temp + 40)  # psia (approximate)
            latent_heat = 550 - 0.5 * (temp + 40)  # BTU/lb
        elif refrigerant.upper() in ["R22", "R404A", "R507"]:
            density = 75 - 0.15 * (temp + 40)
            vapor_pressure = 50 + 3 * (temp + 40)
            latent_heat = 70 - 0.1 * (temp + 40)
        else:
            density = 50
            vapor_pressure = 50
            latent_heat = 80
        
        return {
            'density': max(density, 20),
            'vapor_pressure': max(vapor_pressure, 15),
            'latent_heat': max(latent_heat, 30),
        }
    
    def _select_pipe_size(self, flow_gpm: float, target_velocity: float = 5) -> float:
        """Select pipe size for target velocity."""
        # A = Q / V
        # D = sqrt(4A/π)
        flow_cfs = flow_gpm / 7.48 / 60
        area_sqft = flow_cfs / target_velocity
        diameter_ft = math.sqrt(4 * area_sqft / math.pi)
        diameter_in = diameter_ft * 12
        
        # Standard sizes
        sizes = [1, 1.25, 1.5, 2, 2.5, 3, 4, 6, 8, 10, 12]
        for size in sizes:
            if size >= diameter_in:
                return size
        return 12
    
    def _calculate_friction_head(
        self,
        flow_gpm: float,
        pipe_size_in: float,
        length_ft: float,
        num_elbows: int,
        num_valves: int,
        specific_gravity: float = 1.0,
    ) -> float:
        """Calculate friction head loss."""
        if flow_gpm <= 0 or pipe_size_in <= 0:
            return 0
        
        # Pipe ID (schedule 40)
        pipe_ids = {1: 1.049, 1.25: 1.380, 1.5: 1.610, 2: 2.067, 2.5: 2.469,
                   3: 3.068, 4: 4.026, 6: 6.065, 8: 7.981, 10: 10.02, 12: 11.94}
        pipe_id = pipe_ids.get(pipe_size_in, pipe_size_in * 0.9)
        
        # Velocity (ft/s)
        area_sqft = math.pi * (pipe_id / 12) ** 2 / 4
        velocity = (flow_gpm / 7.48 / 60) / area_sqft
        
        # Equivalent length for fittings
        eq_length_elbow = 30 * pipe_id / 12
        eq_length_valve = 10 * pipe_id / 12
        total_eq_length = length_ft + num_elbows * eq_length_elbow + num_valves * eq_length_valve
        
        # Hazen-Williams (C=150 for steel)
        # h_f = 10.67 * L * Q^1.85 / (C^1.85 * d^4.87)
        c = 150
        h_f = 10.67 * total_eq_length * (flow_gpm ** 1.85) / (c ** 1.85 * (pipe_id ** 4.87))
        
        return h_f
    
    def _calculate_specific_speed(self, flow_gpm: float, head_ft: float, rpm: float) -> float:
        """Calculate pump specific speed."""
        if head_ft <= 0:
            return 1000
        return rpm * math.sqrt(flow_gpm) / (head_ft ** 0.75)
    
    def _estimate_efficiency(self, specific_speed: float) -> float:
        """Estimate pump efficiency from specific speed."""
        # Interpolate from table
        ns_values = sorted(self.EFFICIENCY_BY_NS.keys())
        
        if specific_speed <= ns_values[0]:
            return self.EFFICIENCY_BY_NS[ns_values[0]]
        if specific_speed >= ns_values[-1]:
            return self.EFFICIENCY_BY_NS[ns_values[-1]]
        
        for i, ns in enumerate(ns_values):
            if ns >= specific_speed:
                ns_low, ns_high = ns_values[i-1], ns
                eff_low = self.EFFICIENCY_BY_NS[ns_low]
                eff_high = self.EFFICIENCY_BY_NS[ns_high]
                f = (specific_speed - ns_low) / (ns_high - ns_low)
                return eff_low + f * (eff_high - eff_low)
        
        return 0.70
    
    def _estimate_npsh_required(self, flow_gpm: float, specific_speed: float) -> float:
        """Estimate NPSH required."""
        # Rough correlation: NPSHR increases with flow
        # NPSHR ≈ 5 + Q/200 for typical centrifugal pumps
        return 5 + flow_gpm / 200
    
    def _estimate_impeller_dia(self, flow_gpm: float, head_ft: float) -> float:
        """Estimate impeller diameter."""
        # Rough estimate: D ∝ sqrt(H) at constant speed
        # Typical 6-12 inch range for most industrial pumps
        return 6 + math.sqrt(head_ft) / 3
    
    def _select_motor_size(self, required_hp: float) -> float:
        """Select standard motor size."""
        for size in self.MOTOR_SIZES:
            if size >= required_hp * 1.1:  # 10% margin
                return size
        return self.MOTOR_SIZES[-1]


def quick_pump_hp(flow_gpm: float, head_ft: float, sg: float = 1.0, efficiency: float = 0.65) -> float:
    """Quick pump HP calculation."""
    return flow_gpm * head_ft * sg / (3960 * efficiency)


def recirculation_flow(capacity_tons: float, recirc_rate: float = 4, latent_heat: float = 500) -> float:
    """Calculate recirculation pump flow rate (GPM) for NH3."""
    mass_flow = capacity_tons * 12000 / latent_heat * recirc_rate
    density = 40  # Approximate NH3 liquid density
    return mass_flow / (density * 60 / 7.48)
