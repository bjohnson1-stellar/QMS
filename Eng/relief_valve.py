"""
Pressure Relief Valve Sizing Module
====================================

Size relief valves and rupture discs per:
- ASME Boiler and Pressure Vessel Code
- IIAR Bulletin 110 (Ammonia)
- ASHRAE 15

For vessels, compressors, and system protection.
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ReliefScenario(Enum):
    """Relief valve sizing scenarios."""
    FIRE = "fire"                    # Fire exposure
    BLOCKED_OUTLET = "blocked_outlet"  # Blocked discharge
    THERMAL_EXPANSION = "thermal_expansion"  # Liquid thermal expansion
    TUBE_RUPTURE = "tube_rupture"    # Heat exchanger tube failure
    CONTROL_FAILURE = "control_failure"  # Control valve failure
    COMPRESSOR = "compressor"        # Compressor discharge


class RefrigerantRelief(Enum):
    """Refrigerants for relief valve sizing."""
    NH3 = "nh3"
    R22 = "r22"
    R404A = "r404a"
    R507 = "r507"
    CO2 = "co2"


@dataclass
class ReliefValveResult:
    """Results from relief valve sizing."""
    required_area_sqin: float
    selected_orifice: str
    selected_area_sqin: float
    set_pressure_psig: float
    relieving_capacity_lb_hr: float
    inlet_size: str
    outlet_size: str
    num_valves: int
    scenario: str
    notes: List[str]


class ReliefValveSizer:
    """
    Relief valve sizing calculator per ASME and IIAR.
    
    Example:
        >>> sizer = ReliefValveSizer()
        >>> result = sizer.size_vessel_relief(
        ...     vessel_volume_cuft=100,
        ...     refrigerant=RefrigerantRelief.NH3,
        ...     set_pressure_psig=250,
        ...     vessel_diameter_in=48,
        ...     vessel_length_in=120
        ... )
        >>> print(f"Required orifice: {result.selected_orifice}")
    """
    
    # ASME orifice designations and areas (sq in)
    ASME_ORIFICES = {
        'D': 0.110,
        'E': 0.196,
        'F': 0.307,
        'G': 0.503,
        'H': 0.785,
        'J': 1.287,
        'K': 1.838,
        'L': 2.853,
        'M': 3.600,
        'N': 4.340,
        'P': 6.380,
        'Q': 11.05,
        'R': 16.00,
        'T': 26.00,
    }
    
    # Refrigerant properties for relief valve sizing
    # (molecular_weight, Cp/Cv ratio, critical_pressure_psia)
    REFRIGERANT_PROPS = {
        RefrigerantRelief.NH3: (17.03, 1.31, 1636),
        RefrigerantRelief.R22: (86.47, 1.18, 722),
        RefrigerantRelief.R404A: (97.6, 1.10, 536),
        RefrigerantRelief.R507: (98.9, 1.09, 523),
        RefrigerantRelief.CO2: (44.01, 1.30, 1070),
    }
    
    # Fire exposure constants (ASME VIII)
    # Q = 21000 * F * A^0.82 (BTU/hr)
    # F = environmental factor
    FIRE_F_FACTORS = {
        'bare': 1.0,
        'insulated_1in': 0.3,
        'insulated_2in': 0.15,
        'insulated_4in': 0.075,
        'water_spray': 0.1,
        'underground': 0.0,
    }
    
    def __init__(self):
        pass
    
    def size_vessel_relief(
        self,
        vessel_volume_cuft: float,
        refrigerant: RefrigerantRelief,
        set_pressure_psig: float,
        vessel_diameter_in: float = None,
        vessel_length_in: float = None,
        vessel_surface_area_sqft: float = None,
        insulation: str = 'bare',
        scenario: ReliefScenario = ReliefScenario.FIRE,
    ) -> ReliefValveResult:
        """
        Size relief valve for a refrigerant vessel.
        
        Args:
            vessel_volume_cuft: Internal volume (ft³)
            refrigerant: Refrigerant type
            set_pressure_psig: Relief valve set pressure (psig)
            vessel_diameter_in: Vessel diameter (inches)
            vessel_length_in: Vessel length (inches)
            vessel_surface_area_sqft: Wetted surface area (ft²)
            insulation: Insulation type
            scenario: Relief scenario
        
        Returns:
            ReliefValveResult with sizing details
        """
        notes = []
        
        # Calculate wetted surface area if not provided
        if vessel_surface_area_sqft is None:
            if vessel_diameter_in and vessel_length_in:
                # Assume 80% wetted for horizontal vessel
                d_ft = vessel_diameter_in / 12
                l_ft = vessel_length_in / 12
                total_area = math.pi * d_ft * l_ft + 2 * math.pi * (d_ft/2)**2
                vessel_surface_area_sqft = total_area * 0.8
                notes.append(f"Calculated wetted area: {vessel_surface_area_sqft:.1f} ft²")
            else:
                # Estimate from volume (assume cylinder L=2D)
                volume_cuin = vessel_volume_cuft * 1728
                d_in = (volume_cuin * 4 / (2 * math.pi)) ** (1/3)
                d_ft = d_in / 12
                l_ft = 2 * d_ft
                vessel_surface_area_sqft = math.pi * d_ft * l_ft * 0.8
                notes.append("Estimated surface area from volume")
        
        # Get fire exposure F factor
        f_factor = self.FIRE_F_FACTORS.get(insulation, 1.0)
        notes.append(f"Environmental factor F: {f_factor}")
        
        # Calculate heat input (BTU/hr)
        # Q = 21000 * F * A^0.82 (ASME VIII UG-125)
        q_fire = 21000 * f_factor * (vessel_surface_area_sqft ** 0.82)
        notes.append(f"Heat input Q: {q_fire:,.0f} BTU/hr")
        
        # Get refrigerant properties
        mw, k, p_crit = self.REFRIGERANT_PROPS.get(
            refrigerant, 
            self.REFRIGERANT_PROPS[RefrigerantRelief.NH3]
        )
        
        # Set pressure and relieving pressure
        set_psia = set_pressure_psig + 14.7
        # Relieving pressure = 1.1 × set pressure (10% accumulation)
        relieving_psia = set_psia * 1.1
        
        # Calculate required relieving capacity (lb/hr)
        # W = Q / h_fg (approximate)
        # Use approximate latent heat based on pressure
        h_fg = self._get_latent_heat(refrigerant, relieving_psia)
        mass_flow_lb_hr = q_fire / h_fg
        notes.append(f"Required capacity: {mass_flow_lb_hr:,.0f} lb/hr")
        
        # Calculate required orifice area
        # ASME formula for gas/vapor:
        # A = W / (C * K * P * Kb * sqrt(M / (T * Z)))
        # Simplified version:
        c_factor = 0.975  # Valve coefficient
        k_d = 0.975       # Discharge coefficient
        kb = 1.0          # Backpressure correction (assume 0 backpressure)
        
        # Temperature at relieving conditions (assume saturation)
        t_rankine = self._get_sat_temp_r(refrigerant, relieving_psia)
        z = 1.0  # Compressibility factor (assume ideal)
        
        # Calculate C (gas constant factor)
        c = 520 * math.sqrt(k * (2 / (k + 1)) ** ((k + 1) / (k - 1)))
        
        # Required area (sq in)
        required_area = mass_flow_lb_hr / (
            c_factor * k_d * relieving_psia * kb * 
            math.sqrt(mw / (t_rankine * z))
        ) * 13.16
        
        notes.append(f"Required area: {required_area:.3f} sq in")
        
        # Select orifice
        selected_orifice, selected_area = self._select_orifice(required_area)
        
        # Determine inlet/outlet sizes
        inlet_size, outlet_size = self._get_connection_sizes(selected_orifice)
        
        # Number of valves needed
        num_valves = 1
        if required_area > 16.0:  # Larger than 'R' orifice
            num_valves = math.ceil(required_area / 16.0)
            selected_orifice = 'R'
            selected_area = 16.0
            notes.append(f"Requires {num_valves} valves")
        
        return ReliefValveResult(
            required_area_sqin=required_area,
            selected_orifice=selected_orifice,
            selected_area_sqin=selected_area,
            set_pressure_psig=set_pressure_psig,
            relieving_capacity_lb_hr=mass_flow_lb_hr,
            inlet_size=inlet_size,
            outlet_size=outlet_size,
            num_valves=num_valves,
            scenario=scenario.value,
            notes=notes,
        )
    
    def size_compressor_relief(
        self,
        compressor_displacement_cfm: float,
        refrigerant: RefrigerantRelief,
        set_pressure_psig: float,
        discharge_temp_f: float = 180,
    ) -> ReliefValveResult:
        """
        Size relief valve for compressor discharge.
        
        Args:
            compressor_displacement_cfm: Compressor displacement (CFM)
            refrigerant: Refrigerant type
            set_pressure_psig: Set pressure (psig)
            discharge_temp_f: Discharge temperature (°F)
        
        Returns:
            ReliefValveResult
        """
        notes = []
        
        # Get refrigerant properties
        mw, k, p_crit = self.REFRIGERANT_PROPS.get(
            refrigerant,
            self.REFRIGERANT_PROPS[RefrigerantRelief.NH3]
        )
        
        set_psia = set_pressure_psig + 14.7
        relieving_psia = set_psia * 1.1
        
        # Discharge vapor density (approximate)
        # ρ = P * MW / (10.73 * T)
        t_rankine = discharge_temp_f + 460
        density_lb_cuft = relieving_psia * mw / (10.73 * t_rankine)
        
        # Mass flow rate
        mass_flow_lb_hr = compressor_displacement_cfm * density_lb_cuft * 60
        notes.append(f"Compressor displacement: {compressor_displacement_cfm} CFM")
        notes.append(f"Relief capacity: {mass_flow_lb_hr:,.0f} lb/hr")
        
        # Calculate required area
        c = 520 * math.sqrt(k * (2 / (k + 1)) ** ((k + 1) / (k - 1)))
        k_d = 0.975
        
        required_area = mass_flow_lb_hr / (
            0.975 * k_d * relieving_psia * 
            math.sqrt(mw / (t_rankine * 1.0))
        ) * 13.16
        
        # Select orifice
        selected_orifice, selected_area = self._select_orifice(required_area)
        inlet_size, outlet_size = self._get_connection_sizes(selected_orifice)
        
        return ReliefValveResult(
            required_area_sqin=required_area,
            selected_orifice=selected_orifice,
            selected_area_sqin=selected_area,
            set_pressure_psig=set_pressure_psig,
            relieving_capacity_lb_hr=mass_flow_lb_hr,
            inlet_size=inlet_size,
            outlet_size=outlet_size,
            num_valves=1,
            scenario=ReliefScenario.COMPRESSOR.value,
            notes=notes,
        )
    
    def size_thermal_relief(
        self,
        trapped_volume_cuft: float,
        refrigerant: RefrigerantRelief,
        set_pressure_psig: float,
        initial_temp_f: float,
        max_temp_f: float,
        time_minutes: float = 30,
    ) -> ReliefValveResult:
        """
        Size relief valve for thermal expansion of trapped liquid.
        
        Args:
            trapped_volume_cuft: Liquid volume that can be trapped (ft³)
            refrigerant: Refrigerant type
            set_pressure_psig: Set pressure (psig)
            initial_temp_f: Initial liquid temperature (°F)
            max_temp_f: Maximum expected temperature (°F)
            time_minutes: Time for temperature rise (min)
        
        Returns:
            ReliefValveResult
        """
        notes = []
        
        # Liquid expansion coefficient (approximate)
        beta = 0.001  # per °F for most refrigerants
        
        # Volume expansion
        delta_t = max_temp_f - initial_temp_f
        volume_expansion_cuft = trapped_volume_cuft * beta * delta_t
        
        # Mass to relieve
        density = self._get_liquid_density(refrigerant, initial_temp_f)
        mass_to_relieve_lb = volume_expansion_cuft * density
        
        # Flow rate required
        mass_flow_lb_hr = mass_to_relieve_lb * 60 / time_minutes
        notes.append(f"Expansion volume: {volume_expansion_cuft:.4f} ft³")
        notes.append(f"Mass to relieve: {mass_to_relieve_lb:.2f} lb")
        notes.append(f"Required flow: {mass_flow_lb_hr:.1f} lb/hr")
        
        # For liquid relief, use liquid discharge formula
        set_psia = set_pressure_psig + 14.7
        backpressure_psia = 14.7
        delta_p = set_psia - backpressure_psia
        
        # A = Q / (38 * Kd * sqrt(ΔP * ρ))
        k_d = 0.65  # Liquid discharge coefficient
        required_area = mass_flow_lb_hr / (
            38 * k_d * math.sqrt(delta_p * density)
        )
        
        # Minimum thermal relief size
        if required_area < 0.05:
            required_area = 0.05
            notes.append("Minimum thermal relief size applied")
        
        selected_orifice, selected_area = self._select_orifice(required_area)
        inlet_size, outlet_size = self._get_connection_sizes(selected_orifice)
        
        return ReliefValveResult(
            required_area_sqin=required_area,
            selected_orifice=selected_orifice,
            selected_area_sqin=selected_area,
            set_pressure_psig=set_pressure_psig,
            relieving_capacity_lb_hr=mass_flow_lb_hr,
            inlet_size=inlet_size,
            outlet_size=outlet_size,
            num_valves=1,
            scenario=ReliefScenario.THERMAL_EXPANSION.value,
            notes=notes,
        )
    
    def iiar_minimum_relief(
        self,
        vessel_volume_cuft: float,
        set_pressure_psig: float,
    ) -> ReliefValveResult:
        """
        IIAR minimum relief valve sizing for NH3 vessels.
        
        Per IIAR Bulletin 110, minimum relief capacity.
        
        Args:
            vessel_volume_cuft: Vessel volume (ft³)
            set_pressure_psig: Set pressure (psig)
        
        Returns:
            ReliefValveResult
        """
        # IIAR minimum: C = 0.5 * D * L for horizontal vessels
        # Or use fire formula with bare vessel
        
        return self.size_vessel_relief(
            vessel_volume_cuft=vessel_volume_cuft,
            refrigerant=RefrigerantRelief.NH3,
            set_pressure_psig=set_pressure_psig,
            insulation='bare',
            scenario=ReliefScenario.FIRE,
        )
    
    def _select_orifice(self, required_area: float) -> Tuple[str, float]:
        """Select standard ASME orifice."""
        for orifice, area in sorted(self.ASME_ORIFICES.items(), key=lambda x: x[1]):
            if area >= required_area:
                return orifice, area
        
        # Largest standard orifice
        return 'T', 26.0
    
    def _get_connection_sizes(self, orifice: str) -> Tuple[str, str]:
        """Get typical inlet and outlet connection sizes."""
        connection_sizes = {
            'D': ('1/2"', '1"'),
            'E': ('3/4"', '1"'),
            'F': ('1"', '1-1/4"'),
            'G': ('1"', '1-1/2"'),
            'H': ('1-1/4"', '2"'),
            'J': ('1-1/2"', '2-1/2"'),
            'K': ('2"', '3"'),
            'L': ('2-1/2"', '4"'),
            'M': ('3"', '4"'),
            'N': ('3"', '4"'),
            'P': ('4"', '6"'),
            'Q': ('6"', '8"'),
            'R': ('6"', '10"'),
            'T': ('8"', '12"'),
        }
        return connection_sizes.get(orifice, ('2"', '3"'))
    
    def _get_latent_heat(self, refrigerant: RefrigerantRelief, pressure_psia: float) -> float:
        """Get approximate latent heat at pressure."""
        # Simplified correlations
        latent = {
            RefrigerantRelief.NH3: 550 - 0.2 * pressure_psia,
            RefrigerantRelief.R22: 75 - 0.02 * pressure_psia,
            RefrigerantRelief.R404A: 60 - 0.02 * pressure_psia,
            RefrigerantRelief.R507: 58 - 0.02 * pressure_psia,
            RefrigerantRelief.CO2: 100 - 0.05 * pressure_psia,
        }
        return max(latent.get(refrigerant, 80), 20)
    
    def _get_sat_temp_r(self, refrigerant: RefrigerantRelief, pressure_psia: float) -> float:
        """Get saturation temperature in Rankine."""
        # Simplified correlations (approximate)
        temps = {
            RefrigerantRelief.NH3: 400 + 0.25 * pressure_psia,
            RefrigerantRelief.R22: 420 + 0.15 * pressure_psia,
            RefrigerantRelief.R404A: 410 + 0.12 * pressure_psia,
            RefrigerantRelief.R507: 408 + 0.12 * pressure_psia,
            RefrigerantRelief.CO2: 440 + 0.08 * pressure_psia,
        }
        return temps.get(refrigerant, 450)
    
    def _get_liquid_density(self, refrigerant: RefrigerantRelief, temp_f: float) -> float:
        """Get liquid density (lb/ft³)."""
        densities = {
            RefrigerantRelief.NH3: 42 - 0.05 * temp_f,
            RefrigerantRelief.R22: 82 - 0.1 * temp_f,
            RefrigerantRelief.R404A: 70 - 0.1 * temp_f,
            RefrigerantRelief.R507: 68 - 0.1 * temp_f,
            RefrigerantRelief.CO2: 65 - 0.15 * temp_f,
        }
        return max(densities.get(refrigerant, 50), 20)


def quick_vessel_relief(
    volume_cuft: float,
    pressure_psig: float,
    refrigerant: str = "NH3",
) -> str:
    """
    Quick relief valve sizing for vessel.
    
    Returns orifice designation.
    """
    sizer = ReliefValveSizer()
    
    refrig_map = {
        "NH3": RefrigerantRelief.NH3,
        "R22": RefrigerantRelief.R22,
        "R404A": RefrigerantRelief.R404A,
        "R507": RefrigerantRelief.R507,
        "CO2": RefrigerantRelief.CO2,
    }
    
    refrig = refrig_map.get(refrigerant.upper(), RefrigerantRelief.NH3)
    
    result = sizer.size_vessel_relief(
        vessel_volume_cuft=volume_cuft,
        refrigerant=refrig,
        set_pressure_psig=pressure_psig,
    )
    
    return f"Orifice {result.selected_orifice} ({result.inlet_size} × {result.outlet_size})"
