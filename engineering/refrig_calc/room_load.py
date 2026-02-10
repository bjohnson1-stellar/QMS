"""
Room Load Calculation Module
==============================

Extracted from: Room_Load1.xlsm

Calculates cold storage room refrigeration loads including:
- Heat transmission through walls, roof, floor
- Infiltration loads (air changes + door openings)
- Supplemental loads (lighting, occupancy, motors/equipment)
- Product loads (sensible cooling, freezing, subcooling)

Based on ASHRAE Handbook - Refrigeration methodology.

Key Formulas (from Room_Load1.xlsm):
    Wall load: Q = U × A × ΔT × 24
    Infiltration (air changes): n = 596.21 × V^(-0.548) for T < 32°F
                                 n = 817.5 × V^(-0.5551) for T ≥ 32°F
    Door load: Q = V_door × ΔT × air_factor
    Lighting: Q = watts/ft² × area × 3.41
    Occupancy: Q = n_people × BTU_per_person
    Product: Q = mass × Cp × ΔT (sensible) + mass × Lf (latent)
"""

import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict


# ==============================================================================
# INSULATION CONDUCTANCE DATA (U-factors)
# ==============================================================================

# U-factors in BTU/hr·ft²·°F for panel insulation
# Based on standard polyurethane/polystyrene insulation
INSULATION_U_FACTORS = {
    # thickness_inches: U_factor
    2: 0.10,
    3: 0.067,
    4: 0.050,
    5: 0.040,
    6: 0.033,
    8: 0.025,
    10: 0.020,
    12: 0.017,
}

# Ground contact U-factors (floor over ground)
FLOOR_U_FACTORS = {
    4: 0.044,
    5: 0.036,
    6: 0.030,
    8: 0.023,
}


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class WallSection:
    """A wall section with dimensions and insulation."""
    name: str               # e.g. "North Wall 1"
    orientation: str        # N, S, E, W, Roof, Floor
    length_ft: float
    height_ft: float        # or width for roof/floor
    insulation_thickness_in: float = 4.0
    adjacent_temp_f: float = None  # None = use outside design temp
    is_floor: bool = False
    is_roof: bool = False
    
    @property
    def area_ft2(self) -> float:
        return self.length_ft * self.height_ft
    
    @property
    def u_factor(self) -> float:
        """Get U-factor based on insulation thickness."""
        if self.is_floor:
            return FLOOR_U_FACTORS.get(int(self.insulation_thickness_in), 0.030)
        thick = int(self.insulation_thickness_in)
        if thick in INSULATION_U_FACTORS:
            return INSULATION_U_FACTORS[thick]
        # Interpolate: U ≈ k / thickness, where k ≈ 0.20 for polyurethane
        return 0.20 / self.insulation_thickness_in
    
    @property
    def r_value(self) -> float:
        """R-value = insulation_thickness / k_factor. Typical k=0.16-0.20."""
        return self.insulation_thickness_in * 8.0  # R-8 per inch for polyurethane


@dataclass
class DoorOpening:
    """Door opening for infiltration calculation."""
    name: str = "Door 1"
    quantity: int = 1
    height_ft: float = 8.0
    width_ft: float = 8.0
    time_open_hr_per_day: float = 1.5
    has_strip_curtain: bool = False
    has_air_curtain: bool = False
    adjacent_temp_f: float = None  # None = outside temp


@dataclass
class ProductLoad:
    """Product cooling/freezing load."""
    name: str = "Product #1"
    weight_lb_per_day: float = 0.0
    entering_temp_f: float = 40.0
    final_temp_f: float = 0.0
    specific_heat_above_freezing: float = 0.0  # BTU/lb·°F
    specific_heat_below_freezing: float = 0.0  # BTU/lb·°F
    latent_heat_of_fusion: float = 0.0         # BTU/lb
    freezing_point_f: float = 32.0
    respiration_btu_per_lb_per_day: float = 0.0  # For produce


@dataclass
class RoomLoadResult:
    """Complete room load calculation results."""
    room_name: str = ""
    room_volume_ft3: float = 0.0
    floor_area_ft2: float = 0.0
    
    # Individual loads (BTU/day)
    wall_load_btud: float = 0.0
    roof_load_btud: float = 0.0
    floor_load_btud: float = 0.0
    infiltration_air_change_btud: float = 0.0
    infiltration_door_btud: float = 0.0
    lighting_btud: float = 0.0
    occupancy_btud: float = 0.0
    motor_btud: float = 0.0
    product_sensible_btud: float = 0.0
    product_latent_btud: float = 0.0
    product_respiration_btud: float = 0.0
    miscellaneous_btud: float = 0.0
    
    # Totals
    total_btud: float = 0.0
    safety_factor: float = 0.10  # 10% default
    total_with_safety_btud: float = 0.0
    total_btuh: float = 0.0
    total_tons: float = 0.0
    
    # Breakdown
    details: Dict[str, float] = field(default_factory=dict)


# ==============================================================================
# MAIN CALCULATION CLASS
# ==============================================================================

class RoomLoadCalculator:
    """
    Cold storage room refrigeration load calculator.
    
    Based on methodology from Room_Load1.xlsm and ASHRAE Handbook - Refrigeration.
    """
    
    def __init__(self):
        self.walls: List[WallSection] = []
        self.doors: List[DoorOpening] = []
        self.products: List[ProductLoad] = []
    
    def calculate(self, 
                  room_length_ft: float,
                  room_width_ft: float,
                  room_height_ft: float,
                  inside_temp_f: float,
                  outside_temp_f: float = 95.0,
                  outside_wb_f: float = 75.0,
                  ground_temp_f: float = 60.0,
                  wall_thickness_in: float = 4.0,
                  roof_thickness_in: float = 6.0,
                  floor_thickness_in: float = 6.0,
                  # Supplemental loads
                  lighting_watts_per_ft2: float = 0.3,
                  num_people: int = 0,
                  btu_per_person: float = 1200.0,
                  motor_hp: Dict[str, float] = None,
                  # Factors
                  operating_hours: float = 24.0,
                  safety_factor: float = 0.10,
                  ) -> RoomLoadResult:
        """
        Calculate total room refrigeration load.
        
        Args:
            room_length_ft: Room length (feet)
            room_width_ft: Room width (feet)
            room_height_ft: Room height (feet)
            inside_temp_f: Inside design temperature (°F)
            outside_temp_f: Outside design temperature (°F DB)
            outside_wb_f: Outside wet bulb (°F WB) 
            ground_temp_f: Ground temperature (°F)
            wall_thickness_in: Wall insulation thickness (inches)
            roof_thickness_in: Roof insulation thickness (inches)
            floor_thickness_in: Floor insulation thickness (inches)
            lighting_watts_per_ft2: Lighting power density
            num_people: Number of workers in room
            btu_per_person: Heat gain per person (BTU/hr)
            motor_hp: Dict of motor sizes {"1/8-1/2 Hp": count, "3/4-3 Hp": count, etc.}
            operating_hours: Hours per day room operates
            safety_factor: Safety factor (default 10%)
            
        Returns:
            RoomLoadResult with complete load breakdown
        """
        result = RoomLoadResult(safety_factor=safety_factor)
        
        floor_area = room_length_ft * room_width_ft
        volume = floor_area * room_height_ft
        result.room_volume_ft3 = volume
        result.floor_area_ft2 = floor_area
        
        # ========================================
        # 1. WALL TRANSMISSION LOADS
        # ========================================
        # Q_wall = U × A × ΔT × 24 (BTU/day)
        
        # If custom walls not defined, use room dimensions
        if not self.walls:
            delta_t_walls = outside_temp_f - inside_temp_f
            delta_t_floor = ground_temp_f - inside_temp_f
            
            # Four walls
            wall_u = INSULATION_U_FACTORS.get(int(wall_thickness_in), 0.20 / wall_thickness_in)
            
            # North + South walls (length × height)
            ns_area = 2 * room_length_ft * room_height_ft
            # East + West walls (width × height)
            ew_area = 2 * room_width_ft * room_height_ft
            
            result.wall_load_btud = (ns_area + ew_area) * wall_u * delta_t_walls * 24
            
            # Roof
            roof_u = INSULATION_U_FACTORS.get(int(roof_thickness_in), 0.20 / roof_thickness_in)
            result.roof_load_btud = floor_area * roof_u * delta_t_walls * 24
            
            # Floor
            floor_u = FLOOR_U_FACTORS.get(int(floor_thickness_in), 0.20 / floor_thickness_in)
            result.floor_load_btud = floor_area * floor_u * abs(delta_t_floor) * 24
        else:
            # Use custom wall sections
            for wall in self.walls:
                adj_temp = wall.adjacent_temp_f if wall.adjacent_temp_f is not None else outside_temp_f
                if wall.is_floor:
                    adj_temp = wall.adjacent_temp_f if wall.adjacent_temp_f is not None else ground_temp_f
                
                delta_t = abs(adj_temp - inside_temp_f)
                q = wall.u_factor * wall.area_ft2 * delta_t * 24
                
                if wall.is_roof:
                    result.roof_load_btud += q
                elif wall.is_floor:
                    result.floor_load_btud += q
                else:
                    result.wall_load_btud += q
        
        # ========================================
        # 2. INFILTRATION LOADS
        # ========================================
        # Air changes method (from Room_Load1.xlsm formula):
        #   n = 596.21 × V^(-0.548) for rooms below 32°F
        #   n = 817.5 × V^(-0.5551) for rooms at/above 32°F
        
        if volume > 0:
            if inside_temp_f < 32:
                air_changes = 596.21 * (volume ** -0.548)
            else:
                air_changes = 817.5 * (volume ** -0.5551)
            
            # Heat content of infiltration air
            # Q_inf = V × n × q_air (BTU/ft³ based on temperature difference)
            # Approximate: 1.08 × CFM × ΔT for sensible, plus moisture
            delta_t = outside_temp_f - inside_temp_f
            
            # Simplified BTU/ft³ of infiltrating air
            # From ASHRAE tables: ~ 1.5-4.5 BTU/ft³ depending on conditions
            btu_per_ft3 = 0.075 * 0.24 * delta_t  # sensible only: ρ × Cp × ΔT
            # Add latent component for cooler/freezer
            if inside_temp_f < 32:
                btu_per_ft3 += 2.5  # Approximate latent for freezer
            elif inside_temp_f < 40:
                btu_per_ft3 += 1.5  # Approximate latent for cooler
            
            result.infiltration_air_change_btud = volume * air_changes * btu_per_ft3
        
        # Door infiltration
        for door in self.doors:
            adj = door.adjacent_temp_f if door.adjacent_temp_f is not None else outside_temp_f
            door_area = door.height_ft * door.width_ft
            door_delta_t = adj - inside_temp_f
            
            # Simplified door infiltration: 
            # Q = 220 × A × sqrt(H) × ΔT × time_fraction × Df × E
            # where Df = 1.0 for no protection, 0.8 strip curtain, 0.25 air curtain
            protection_factor = 1.0
            if door.has_air_curtain:
                protection_factor = 0.25
            elif door.has_strip_curtain:
                protection_factor = 0.80
            
            time_fraction = door.time_open_hr_per_day / 24.0
            q_door = (220 * door_area * math.sqrt(door.height_ft) * 
                      abs(door_delta_t) * time_fraction * protection_factor * door.quantity)
            
            result.infiltration_door_btud += q_door
        
        # ========================================
        # 3. SUPPLEMENTAL LOADS
        # ========================================
        # Lighting: Q = watts/ft² × area × 3.41 BTU/W × hours
        result.lighting_btud = lighting_watts_per_ft2 * floor_area * 3.41 * operating_hours
        
        # Occupancy: Q = people × BTU/person × hours
        result.occupancy_btud = num_people * btu_per_person * operating_hours
        
        # Motors (from Room_Load1.xlsm formula)
        # BTU/hr by motor size range:
        #   1/8-1/2 HP: 4250 BTU/hr per motor
        #   3/4-3 HP:   3700 BTU/hr per motor  
        #   5-20 HP:    2950 BTU/hr per motor
        motor_heat_rates = {
            "1/8-1/2 Hp": 4250,
            "3/4-3 Hp": 3700,
            "5-20 Hp": 2950,
        }
        if motor_hp:
            total_motor_btuh = 0
            for size_range, count in motor_hp.items():
                rate = motor_heat_rates.get(size_range, 3700)
                total_motor_btuh += count * rate
            result.motor_btud = total_motor_btuh * operating_hours
        
        # ========================================
        # 4. PRODUCT LOADS
        # ========================================
        for product in self.products:
            if product.weight_lb_per_day <= 0:
                continue
            
            W = product.weight_lb_per_day
            T_in = product.entering_temp_f
            T_out = product.final_temp_f
            T_freeze = product.freezing_point_f
            Cp_above = product.specific_heat_above_freezing
            Cp_below = product.specific_heat_below_freezing
            Lf = product.latent_heat_of_fusion
            
            # Sensible cooling above freezing
            if T_in > T_freeze and T_out < T_freeze:
                # Cool to freezing point
                result.product_sensible_btud += W * Cp_above * (T_in - T_freeze)
                # Freeze
                result.product_latent_btud += W * Lf
                # Cool below freezing
                result.product_sensible_btud += W * Cp_below * (T_freeze - T_out)
            elif T_in > T_out:
                # No phase change
                cp = Cp_above if T_out >= T_freeze else Cp_below
                result.product_sensible_btud += W * cp * (T_in - T_out)
            
            # Respiration heat (produce)
            if product.respiration_btu_per_lb_per_day > 0:
                result.product_respiration_btud += W * product.respiration_btu_per_lb_per_day
        
        # ========================================
        # 5. TOTALS
        # ========================================
        result.total_btud = (
            result.wall_load_btud +
            result.roof_load_btud +
            result.floor_load_btud +
            result.infiltration_air_change_btud +
            result.infiltration_door_btud +
            result.lighting_btud +
            result.occupancy_btud +
            result.motor_btud +
            result.product_sensible_btud +
            result.product_latent_btud +
            result.product_respiration_btud +
            result.miscellaneous_btud
        )
        
        result.total_with_safety_btud = result.total_btud * (1 + safety_factor)
        result.total_btuh = result.total_with_safety_btud / 24.0
        result.total_tons = result.total_btuh / 12000.0
        
        return result


# ==============================================================================
# QUICK FUNCTIONS
# ==============================================================================

def quick_room_load(length_ft: float, width_ft: float, height_ft: float,
                     inside_temp_f: float, outside_temp_f: float = 95.0) -> RoomLoadResult:
    """
    Quick room load estimate using typical assumptions.
    
    Uses:
        - 4" walls, 6" roof/floor insulation
        - Standard infiltration rates
        - 0.3 W/ft² lighting
        - 10% safety factor
    """
    calc = RoomLoadCalculator()
    return calc.calculate(
        room_length_ft=length_ft,
        room_width_ft=width_ft,
        room_height_ft=height_ft,
        inside_temp_f=inside_temp_f,
        outside_temp_f=outside_temp_f,
    )


def quick_load_estimate_btu_per_ft2(inside_temp_f: float) -> float:
    """
    Rule-of-thumb load estimate in BTU/hr per ft² of floor area.
    
    Common rules of thumb:
        Cooler (35°F): 15-25 BTU/hr·ft²
        Freezer (0°F): 25-40 BTU/hr·ft²
        Blast freezer (-20°F): 50-80 BTU/hr·ft²
    """
    if inside_temp_f >= 32:
        return 20.0  # Cooler
    elif inside_temp_f >= 0:
        return 35.0  # Freezer
    elif inside_temp_f >= -20:
        return 60.0  # Blast freezer
    else:
        return 80.0  # Deep freeze
