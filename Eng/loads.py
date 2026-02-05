"""
Refrigeration Load Calculation Module
=====================================

Calculate refrigeration loads for:
- Cold storage rooms (coolers and freezers)
- Blast freezers
- Process cooling
- Docks and staging areas

Based on ASHRAE Handbook - Refrigeration methods.
"""

import math
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum


class ProductType(Enum):
    """Common product types with thermal properties."""
    BEEF = "beef"
    PORK = "pork"
    POULTRY = "poultry"
    FISH = "fish"
    DAIRY = "dairy"
    EGGS = "eggs"
    FRUITS = "fruits"
    VEGETABLES = "vegetables"
    ICE_CREAM = "ice_cream"
    FROZEN_FOOD = "frozen_food"
    BEVERAGES = "beverages"
    CUSTOM = "custom"


@dataclass
class ProductProperties:
    """Thermal properties of stored products."""
    name: str
    specific_heat_above_freezing: float  # BTU/lb-°F
    specific_heat_below_freezing: float  # BTU/lb-°F
    latent_heat_of_fusion: float         # BTU/lb
    freezing_point: float                # °F
    respiration_heat_32f: float = 0      # BTU/lb-day at 32°F
    respiration_heat_40f: float = 0      # BTU/lb-day at 40°F
    density: float = 40                  # lb/ft³ storage density


# Product property database (from ASHRAE)
PRODUCT_DATA = {
    ProductType.BEEF: ProductProperties("Beef", 0.77, 0.40, 100, 28, 0, 0, 45),
    ProductType.PORK: ProductProperties("Pork", 0.68, 0.38, 86, 28, 0, 0, 42),
    ProductType.POULTRY: ProductProperties("Poultry", 0.79, 0.42, 106, 27, 0, 0, 35),
    ProductType.FISH: ProductProperties("Fish", 0.82, 0.43, 110, 28, 0, 0, 50),
    ProductType.DAIRY: ProductProperties("Dairy Products", 0.93, 0.49, 124, 31, 0, 0, 65),
    ProductType.EGGS: ProductProperties("Eggs", 0.73, 0.40, 96, 28, 0, 0, 45),
    ProductType.FRUITS: ProductProperties("Fruits (average)", 0.90, 0.45, 121, 30, 0.035, 0.065, 35),
    ProductType.VEGETABLES: ProductProperties("Vegetables (average)", 0.92, 0.46, 123, 30, 0.04, 0.075, 30),
    ProductType.ICE_CREAM: ProductProperties("Ice Cream", 0.78, 0.45, 95, 21, 0, 0, 38),
    ProductType.FROZEN_FOOD: ProductProperties("Frozen Foods", 0.75, 0.42, 100, 28, 0, 0, 35),
    ProductType.BEVERAGES: ProductProperties("Beverages", 0.95, 0.48, 128, 30, 0, 0, 60),
}


@dataclass
class RoomDimensions:
    """Cold storage room dimensions."""
    length: float  # ft
    width: float   # ft
    height: float  # ft
    
    @property
    def floor_area(self) -> float:
        return self.length * self.width
    
    @property
    def volume(self) -> float:
        return self.length * self.width * self.height
    
    @property
    def wall_area(self) -> float:
        return 2 * self.height * (self.length + self.width)
    
    @property
    def ceiling_area(self) -> float:
        return self.length * self.width
    
    @property
    def total_surface_area(self) -> float:
        return self.wall_area + 2 * self.floor_area


@dataclass
class LoadResult:
    """Results from load calculation."""
    transmission_load: float      # BTU/hr
    infiltration_load: float      # BTU/hr
    product_load: float           # BTU/hr
    respiration_load: float       # BTU/hr
    equipment_load: float         # BTU/hr
    lighting_load: float          # BTU/hr
    personnel_load: float         # BTU/hr
    defrost_load: float          # BTU/hr
    safety_factor_load: float    # BTU/hr
    total_load: float            # BTU/hr
    total_tons: float            # Tons of refrigeration
    
    def __str__(self) -> str:
        pct = lambda x: x/self.total_load*100 if self.total_load > 0 else 0
        return f"""
Refrigeration Load Summary
==========================
Transmission:    {self.transmission_load:>12,.0f} BTU/hr ({pct(self.transmission_load):>5.1f}%)
Infiltration:    {self.infiltration_load:>12,.0f} BTU/hr ({pct(self.infiltration_load):>5.1f}%)
Product:         {self.product_load:>12,.0f} BTU/hr ({pct(self.product_load):>5.1f}%)
Respiration:     {self.respiration_load:>12,.0f} BTU/hr ({pct(self.respiration_load):>5.1f}%)
Equipment:       {self.equipment_load:>12,.0f} BTU/hr ({pct(self.equipment_load):>5.1f}%)
Lighting:        {self.lighting_load:>12,.0f} BTU/hr ({pct(self.lighting_load):>5.1f}%)
Personnel:       {self.personnel_load:>12,.0f} BTU/hr ({pct(self.personnel_load):>5.1f}%)
Defrost:         {self.defrost_load:>12,.0f} BTU/hr ({pct(self.defrost_load):>5.1f}%)
Safety Factor:   {self.safety_factor_load:>12,.0f} BTU/hr
-----------------------------------------
TOTAL:           {self.total_load:>12,.0f} BTU/hr
                 {self.total_tons:>12.1f} Tons
"""


class RefrigerationLoadCalculator:
    """
    Refrigeration load calculator for cold storage facilities.
    
    Example:
        >>> calc = RefrigerationLoadCalculator()
        >>> room = RoomDimensions(length=100, width=50, height=20)
        >>> result = calc.calculate_cooler_load(
        ...     room=room,
        ...     inside_temp=35,
        ...     outside_temp=95,
        ...     product_load_lb_day=50000
        ... )
        >>> print(f"Total load: {result.total_tons:.1f} tons")
    """
    
    # Infiltration air changes per day based on room volume (with strip curtain)
    AIR_CHANGES = {
        1000: 28, 2000: 20, 5000: 14, 10000: 9.5, 20000: 7.0,
        50000: 5.0, 100000: 3.5, 200000: 2.5, 500000: 1.5,
    }
    
    # Personnel heat load (BTU/hr per person) by temperature
    PERSONNEL_HEAT = {50: 720, 40: 840, 35: 900, 32: 950, 20: 1050, 0: 1200, -20: 1400}
    
    def calculate_cooler_load(
        self,
        room: RoomDimensions,
        inside_temp: float,
        outside_temp: float = 95,
        product_type: ProductType = ProductType.FROZEN_FOOD,
        product_load_lb_day: float = 0,
        product_entering_temp: float = None,
        wall_r_value: float = 25,
        ceiling_r_value: float = 30,
        floor_r_value: float = 20,
        floor_temp: float = 50,
        lighting_watts_per_sqft: float = 1.0,
        lighting_hours: float = 8,
        num_personnel: int = 2,
        personnel_hours: float = 8,
        forklift_hp: float = 5,
        forklift_hours: float = 4,
        has_strip_curtain: bool = True,
        num_defrost: int = 2,
        defrost_kw: float = 0,
        safety_factor: float = 0.10,
    ) -> LoadResult:
        """Calculate total refrigeration load for a cooler or freezer."""
        
        product = PRODUCT_DATA.get(product_type, PRODUCT_DATA[ProductType.FROZEN_FOOD])
        
        if product_entering_temp is None:
            product_entering_temp = 35 if inside_temp < 32 else outside_temp - 10
        
        # 1. Transmission load
        transmission = self._calc_transmission(
            room, inside_temp, outside_temp, floor_temp,
            wall_r_value, ceiling_r_value, floor_r_value
        )
        
        # 2. Infiltration load
        infiltration = self._calc_infiltration(
            room.volume, inside_temp, outside_temp, has_strip_curtain
        )
        
        # 3. Product load
        product_load = self._calc_product_load(
            product_load_lb_day, product, inside_temp, product_entering_temp
        )
        
        # 4. Respiration load
        respiration = self._calc_respiration(product, inside_temp, room.volume)
        
        # 5. Equipment load
        equipment = forklift_hp * 2545 * 0.9 * forklift_hours / 24
        
        # 6. Lighting load
        lighting = room.floor_area * lighting_watts_per_sqft * 3.41 * lighting_hours / 24
        
        # 7. Personnel load
        heat_per_person = self._get_personnel_heat(inside_temp)
        personnel = num_personnel * heat_per_person * personnel_hours / 24
        
        # 8. Defrost load
        defrost = defrost_kw * 3412 * 0.5 * num_defrost * 0.5 / 24 if defrost_kw > 0 else 0
        
        # Total
        subtotal = transmission + infiltration + product_load + respiration + equipment + lighting + personnel + defrost
        safety = subtotal * safety_factor
        total = subtotal + safety
        
        return LoadResult(
            transmission_load=transmission,
            infiltration_load=infiltration,
            product_load=product_load,
            respiration_load=respiration,
            equipment_load=equipment,
            lighting_load=lighting,
            personnel_load=personnel,
            defrost_load=defrost,
            safety_factor_load=safety,
            total_load=total,
            total_tons=total / 12000,
        )
    
    def _calc_transmission(self, room, inside_temp, outside_temp, floor_temp, wall_r, ceiling_r, floor_r):
        """Calculate transmission heat load."""
        wall_dt = outside_temp - inside_temp
        ceiling_dt = (outside_temp + 20) - inside_temp  # Solar gain
        floor_dt = max(0, floor_temp - inside_temp)
        
        q_walls = (room.wall_area / wall_r) * wall_dt
        q_ceiling = (room.ceiling_area / ceiling_r) * ceiling_dt
        q_floor = (room.floor_area / floor_r) * floor_dt
        
        return q_walls + q_ceiling + q_floor
    
    def _calc_infiltration(self, volume, inside_temp, outside_temp, has_curtain):
        """Calculate infiltration load."""
        # Get air changes
        air_changes = 5.0
        for v, ac in sorted(self.AIR_CHANGES.items()):
            if volume <= v:
                air_changes = ac
                break
        
        if not has_curtain:
            air_changes *= 1.5
        
        # Enthalpy difference approximation
        temp_diff = outside_temp - inside_temp
        delta_h = 15 + 0.3 * temp_diff if inside_temp >= 32 else 20 + 0.4 * temp_diff
        
        infil_mass = volume * air_changes * 0.075  # lb/day
        return infil_mass * delta_h / 24
    
    def _calc_product_load(self, lb_day, product, final_temp, entering_temp):
        """Calculate product cooling/freezing load."""
        if lb_day <= 0:
            return 0
        
        load = 0
        fp = product.freezing_point
        
        if final_temp >= fp:
            # Cooling only
            load = lb_day * product.specific_heat_above_freezing * (entering_temp - final_temp)
        else:
            if entering_temp > fp:
                load += lb_day * product.specific_heat_above_freezing * (entering_temp - fp)
            load += lb_day * product.latent_heat_of_fusion
            load += lb_day * product.specific_heat_below_freezing * (fp - final_temp)
        
        return load / 24
    
    def _calc_respiration(self, product, temp, volume):
        """Calculate respiration heat for produce."""
        if product.respiration_heat_32f == 0:
            return 0
        
        if temp <= 32:
            rate = product.respiration_heat_32f
        elif temp >= 40:
            rate = product.respiration_heat_40f
        else:
            rate = product.respiration_heat_32f + (product.respiration_heat_40f - product.respiration_heat_32f) * (temp - 32) / 8
        
        stored_lb = volume * 0.5 * product.density
        return stored_lb * rate / 24
    
    def _get_personnel_heat(self, temp):
        """Get personnel heat output for temperature."""
        for t, heat in sorted(self.PERSONNEL_HEAT.items(), reverse=True):
            if temp <= t:
                return heat
        return 720


class BlastFreezerCalculator:
    """Blast freezer load calculator for batch operations."""
    
    def calculate_blast_load(
        self,
        product_lb: float,
        product_type: ProductType,
        initial_temp: float,
        final_temp: float,
        pull_down_hours: float,
        room_length: float = 20,
        room_width: float = 15,
        room_height: float = 12,
        ambient_temp: float = 95,
        wall_r_value: float = 35,
    ) -> Dict:
        """
        Calculate blast freezer load.
        
        Args:
            product_lb: Total product weight (lb)
            product_type: Product type
            initial_temp: Starting product temperature (°F)
            final_temp: Target temperature (°F)
            pull_down_hours: Required freezing time (hours)
        
        Returns:
            Dict with load breakdown
        """
        product = PRODUCT_DATA.get(product_type, PRODUCT_DATA[ProductType.BEEF])
        fp = product.freezing_point
        
        # Total heat to remove
        total_btu = 0
        if initial_temp > fp:
            total_btu += product_lb * product.specific_heat_above_freezing * (initial_temp - fp)
        if initial_temp > fp and final_temp < fp:
            total_btu += product_lb * product.latent_heat_of_fusion
        if final_temp < fp:
            start = min(initial_temp, fp)
            total_btu += product_lb * product.specific_heat_below_freezing * (start - final_temp)
        
        product_rate = total_btu / pull_down_hours
        
        # Transmission
        room = RoomDimensions(room_length, room_width, room_height)
        avg_temp = (initial_temp + final_temp) / 2
        transmission = (room.total_surface_area / wall_r_value) * (ambient_temp - avg_temp)
        
        # Fan heat estimate
        estimated_tons = (product_rate + transmission) / 12000
        fan_heat = estimated_tons * 0.15 * 2545
        
        total = product_rate + transmission + fan_heat
        design = total * 1.15
        
        return {
            'product_heat_btu': total_btu,
            'product_rate_btu_hr': product_rate,
            'transmission_btu_hr': transmission,
            'fan_heat_btu_hr': fan_heat,
            'total_btu_hr': total,
            'design_btu_hr': design,
            'design_tons': design / 12000,
        }


def quick_load_estimate(floor_area: float, inside_temp: float, application: str = "storage") -> float:
    """
    Quick load estimate using rules of thumb.
    
    Args:
        floor_area: Room floor area (ft²)
        inside_temp: Design temperature (°F)
        application: "storage", "processing", or "dock"
    
    Returns:
        Estimated load in tons
    """
    # BTU/hr per ft² by temperature and application
    loads = {
        "storage": {50: 15, 40: 20, 35: 25, 32: 30, 0: 35, -10: 40, -20: 45},
        "processing": {50: 35, 40: 45, 35: 55, 32: 65},
        "dock": {50: 25, 40: 35, 35: 40},
    }
    
    table = loads.get(application, loads["storage"])
    btu_per_sqft = 25  # Default
    
    for temp, load in sorted(table.items(), reverse=True):
        if inside_temp <= temp:
            btu_per_sqft = load
            break
    
    return floor_area * btu_per_sqft / 12000
