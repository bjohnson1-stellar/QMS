"""
Refrigerant Properties Module
=============================

Thermodynamic properties for industrial refrigerants including:
- Ammonia (NH3/R717)
- CO2 (R744)
- R22
- R404a
- R449A
- R507

All properties based on ASHRAE data tables.
"""

import math
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import bisect


@dataclass
class SaturationProperties:
    """Saturation properties at a given temperature or pressure."""
    temperature_f: float
    pressure_psia: float
    liquid_density: float  # lb/ft³
    vapor_density: float   # lb/ft³
    liquid_enthalpy: float = 0.0  # BTU/lb
    vapor_enthalpy: float = 0.0   # BTU/lb
    latent_heat: float = 0.0      # BTU/lb
    liquid_viscosity: float = 0.0  # lbm/ft-hr
    vapor_viscosity: float = 0.0   # lbm/ft-hr
    liquid_cp: float = 0.0        # BTU/lb-°F
    vapor_cp: float = 0.0         # BTU/lb-°F
    liquid_k: float = 0.0         # BTU/hr-ft-°F (thermal conductivity)
    vapor_k: float = 0.0          # BTU/hr-ft-°F
    surface_tension: float = 0.0  # lbf/ft


class RefrigerantProperties:
    """Base class for refrigerant thermodynamic properties."""
    
    def __init__(self, name: str, molecular_weight: float):
        self.name = name
        self.molecular_weight = molecular_weight
        self._temp_table: Dict[float, SaturationProperties] = {}
        self._press_table: Dict[float, SaturationProperties] = {}
        self._temps_sorted: list = []
        self._press_sorted: list = []
    
    def get_properties_at_temp(self, temp_f: float) -> SaturationProperties:
        """Get saturation properties at a given temperature (°F)."""
        return self._interpolate_by_temp(temp_f)
    
    def get_properties_at_pressure(self, pressure_psia: float) -> SaturationProperties:
        """Get saturation properties at a given pressure (psia)."""
        return self._interpolate_by_pressure(pressure_psia)
    
    def saturation_pressure(self, temp_f: float) -> float:
        """Get saturation pressure (psia) at a given temperature (°F)."""
        props = self.get_properties_at_temp(temp_f)
        return props.pressure_psia
    
    def saturation_temperature(self, pressure_psia: float) -> float:
        """Get saturation temperature (°F) at a given pressure (psia)."""
        props = self.get_properties_at_pressure(pressure_psia)
        return props.temperature_f
    
    def liquid_density(self, temp_f: float) -> float:
        """Get liquid density (lb/ft³) at saturation temperature."""
        return self.get_properties_at_temp(temp_f).liquid_density
    
    def vapor_density(self, temp_f: float) -> float:
        """Get vapor density (lb/ft³) at saturation temperature."""
        return self.get_properties_at_temp(temp_f).vapor_density
    
    def latent_heat(self, temp_f: float) -> float:
        """Get latent heat of vaporization (BTU/lb) at saturation temperature."""
        return self.get_properties_at_temp(temp_f).latent_heat
    
    def _interpolate_by_temp(self, temp_f: float) -> SaturationProperties:
        """Interpolate properties by temperature."""
        if not self._temps_sorted:
            raise ValueError("No temperature data loaded")
        
        # Clamp to valid range
        temp_f = max(min(temp_f, self._temps_sorted[-1]), self._temps_sorted[0])
        
        # Find bracketing temperatures
        idx = bisect.bisect_left(self._temps_sorted, temp_f)
        
        if idx == 0:
            return self._temp_table[self._temps_sorted[0]]
        if idx >= len(self._temps_sorted):
            return self._temp_table[self._temps_sorted[-1]]
        
        t_low = self._temps_sorted[idx - 1]
        t_high = self._temps_sorted[idx]
        
        if t_high == t_low:
            return self._temp_table[t_low]
        
        # Linear interpolation factor
        f = (temp_f - t_low) / (t_high - t_low)
        
        p_low = self._temp_table[t_low]
        p_high = self._temp_table[t_high]
        
        return SaturationProperties(
            temperature_f=temp_f,
            pressure_psia=p_low.pressure_psia + f * (p_high.pressure_psia - p_low.pressure_psia),
            liquid_density=p_low.liquid_density + f * (p_high.liquid_density - p_low.liquid_density),
            vapor_density=p_low.vapor_density + f * (p_high.vapor_density - p_low.vapor_density),
            liquid_enthalpy=p_low.liquid_enthalpy + f * (p_high.liquid_enthalpy - p_low.liquid_enthalpy),
            vapor_enthalpy=p_low.vapor_enthalpy + f * (p_high.vapor_enthalpy - p_low.vapor_enthalpy),
            latent_heat=p_low.latent_heat + f * (p_high.latent_heat - p_low.latent_heat),
            liquid_viscosity=p_low.liquid_viscosity + f * (p_high.liquid_viscosity - p_low.liquid_viscosity),
            vapor_viscosity=p_low.vapor_viscosity + f * (p_high.vapor_viscosity - p_low.vapor_viscosity),
            liquid_cp=p_low.liquid_cp + f * (p_high.liquid_cp - p_low.liquid_cp),
            vapor_cp=p_low.vapor_cp + f * (p_high.vapor_cp - p_low.vapor_cp),
            liquid_k=p_low.liquid_k + f * (p_high.liquid_k - p_low.liquid_k),
            vapor_k=p_low.vapor_k + f * (p_high.vapor_k - p_low.vapor_k),
            surface_tension=p_low.surface_tension + f * (p_high.surface_tension - p_low.surface_tension),
        )
    
    def _interpolate_by_pressure(self, pressure_psia: float) -> SaturationProperties:
        """Interpolate properties by pressure."""
        if not self._press_sorted:
            # Fall back to temperature table and search by pressure
            for t in self._temps_sorted:
                props = self._temp_table[t]
                if abs(props.pressure_psia - pressure_psia) < 0.5:
                    return props
            # Binary search approach
            low_idx, high_idx = 0, len(self._temps_sorted) - 1
            while high_idx - low_idx > 1:
                mid_idx = (low_idx + high_idx) // 2
                mid_press = self._temp_table[self._temps_sorted[mid_idx]].pressure_psia
                if mid_press < pressure_psia:
                    low_idx = mid_idx
                else:
                    high_idx = mid_idx
            
            t_low = self._temps_sorted[low_idx]
            t_high = self._temps_sorted[high_idx]
            p_low = self._temp_table[t_low]
            p_high = self._temp_table[t_high]
            
            if p_high.pressure_psia == p_low.pressure_psia:
                return p_low
            
            f = (pressure_psia - p_low.pressure_psia) / (p_high.pressure_psia - p_low.pressure_psia)
            f = max(0, min(1, f))
            
            return SaturationProperties(
                temperature_f=p_low.temperature_f + f * (p_high.temperature_f - p_low.temperature_f),
                pressure_psia=pressure_psia,
                liquid_density=p_low.liquid_density + f * (p_high.liquid_density - p_low.liquid_density),
                vapor_density=p_low.vapor_density + f * (p_high.vapor_density - p_low.vapor_density),
                liquid_enthalpy=p_low.liquid_enthalpy + f * (p_high.liquid_enthalpy - p_low.liquid_enthalpy),
                vapor_enthalpy=p_low.vapor_enthalpy + f * (p_high.vapor_enthalpy - p_low.vapor_enthalpy),
                latent_heat=p_low.latent_heat + f * (p_high.latent_heat - p_low.latent_heat),
                liquid_viscosity=p_low.liquid_viscosity + f * (p_high.liquid_viscosity - p_low.liquid_viscosity),
                vapor_viscosity=p_low.vapor_viscosity + f * (p_high.vapor_viscosity - p_low.vapor_viscosity),
                liquid_cp=p_low.liquid_cp + f * (p_high.liquid_cp - p_low.liquid_cp),
                vapor_cp=p_low.vapor_cp + f * (p_high.vapor_cp - p_low.vapor_cp),
                liquid_k=p_low.liquid_k + f * (p_high.liquid_k - p_low.liquid_k),
                vapor_k=p_low.vapor_k + f * (p_high.vapor_k - p_low.vapor_k),
                surface_tension=p_low.surface_tension + f * (p_high.surface_tension - p_low.surface_tension),
            )
        
        # Use pressure table if available
        pressure_psia = max(min(pressure_psia, self._press_sorted[-1]), self._press_sorted[0])
        idx = bisect.bisect_left(self._press_sorted, pressure_psia)
        
        if idx == 0:
            return self._press_table[self._press_sorted[0]]
        if idx >= len(self._press_sorted):
            return self._press_table[self._press_sorted[-1]]
        
        p_low = self._press_sorted[idx - 1]
        p_high = self._press_sorted[idx]
        
        f = (pressure_psia - p_low) / (p_high - p_low) if p_high != p_low else 0
        
        props_low = self._press_table[p_low]
        props_high = self._press_table[p_high]
        
        return SaturationProperties(
            temperature_f=props_low.temperature_f + f * (props_high.temperature_f - props_low.temperature_f),
            pressure_psia=pressure_psia,
            liquid_density=props_low.liquid_density + f * (props_high.liquid_density - props_low.liquid_density),
            vapor_density=props_low.vapor_density + f * (props_high.vapor_density - props_low.vapor_density),
            liquid_enthalpy=props_low.liquid_enthalpy + f * (props_high.liquid_enthalpy - props_low.liquid_enthalpy),
            vapor_enthalpy=props_low.vapor_enthalpy + f * (props_high.vapor_enthalpy - props_low.vapor_enthalpy),
            latent_heat=props_low.latent_heat + f * (props_high.latent_heat - props_low.latent_heat),
            liquid_viscosity=props_low.liquid_viscosity + f * (props_high.liquid_viscosity - props_low.liquid_viscosity),
            vapor_viscosity=props_low.vapor_viscosity + f * (props_high.vapor_viscosity - props_low.vapor_viscosity),
            liquid_cp=props_low.liquid_cp + f * (props_high.liquid_cp - props_low.liquid_cp),
            vapor_cp=props_low.vapor_cp + f * (props_high.vapor_cp - props_low.vapor_cp),
            liquid_k=props_low.liquid_k + f * (props_high.liquid_k - props_low.liquid_k),
            vapor_k=props_low.vapor_k + f * (props_high.vapor_k - props_low.vapor_k),
            surface_tension=props_low.surface_tension + f * (props_high.surface_tension - props_low.surface_tension),
        )


class NH3Properties(RefrigerantProperties):
    """
    Ammonia (NH3/R717) thermodynamic properties.
    
    Data from ASHRAE Handbook - Fundamentals.
    Valid range: -100°F to 200°F
    
    Example:
        >>> nh3 = NH3Properties()
        >>> props = nh3.get_properties_at_temp(0)
        >>> print(f"Pressure at 0°F: {props.pressure_psia:.2f} psia")
        Pressure at 0°F: 30.42 psia
    """
    
    def __init__(self):
        super().__init__("Ammonia", molecular_weight=17.03)
        self._load_data()
    
    def _load_data(self):
        """Load NH3 saturation property data from ASHRAE tables."""
        # Data extracted from engineering spreadsheets
        # Format: (temp_F, pressure_psia, liquid_density, vapor_density, 
        #          h_liquid, h_vapor, latent_heat, mu_liquid, mu_vapor,
        #          cp_liquid, cp_vapor, k_liquid, k_vapor, surface_tension)
        
        data = [
            (-60, 5.539, 43.91, 0.0223, -20.91, 589.69, 610.60, 0.820, 0.0183, 1.051, 0.501, 0.3625, 0.00902, 0.00230),
            (-55, 6.598, 43.70, 0.0257, -15.70, 591.67, 607.37, 0.787, 0.0185, 1.051, 0.505, 0.3584, 0.00919, 0.00225),
            (-50, 7.807, 43.49, 0.0295, -10.47, 593.64, 604.11, 0.754, 0.0187, 1.052, 0.509, 0.3542, 0.00936, 0.00220),
            (-45, 9.188, 43.28, 0.0338, -5.22, 595.59, 600.81, 0.722, 0.0189, 1.054, 0.514, 0.3500, 0.00954, 0.00215),
            (-40, 10.77, 43.06, 0.0387, 0.00, 597.52, 597.52, 0.692, 0.0191, 1.056, 0.519, 0.3458, 0.00972, 0.00210),
            (-35, 12.56, 42.84, 0.0441, 5.28, 599.42, 594.14, 0.662, 0.0194, 1.058, 0.524, 0.3416, 0.00990, 0.00205),
            (-30, 14.60, 42.62, 0.0502, 10.59, 601.30, 590.71, 0.633, 0.0196, 1.061, 0.530, 0.3373, 0.01009, 0.00200),
            (-25, 16.91, 42.39, 0.0570, 15.92, 603.15, 587.23, 0.605, 0.0198, 1.064, 0.536, 0.3330, 0.01028, 0.00195),
            (-20, 19.51, 42.16, 0.0646, 21.28, 604.97, 583.69, 0.578, 0.0200, 1.067, 0.543, 0.3287, 0.01048, 0.00190),
            (-15, 22.43, 41.92, 0.0730, 26.66, 606.76, 580.10, 0.553, 0.0202, 1.070, 0.550, 0.3244, 0.01068, 0.00185),
            (-10, 25.69, 41.68, 0.0824, 32.06, 608.52, 576.46, 0.528, 0.0205, 1.074, 0.557, 0.3200, 0.01089, 0.00180),
            (-5, 29.33, 41.43, 0.0927, 37.49, 610.25, 572.76, 0.505, 0.0207, 1.078, 0.565, 0.3156, 0.01110, 0.00175),
            (0, 33.37, 41.18, 0.1041, 42.94, 611.94, 568.99, 0.482, 0.0209, 1.082, 0.574, 0.3112, 0.01132, 0.00170),
            (5, 37.86, 40.92, 0.1167, 48.42, 613.59, 565.17, 0.461, 0.0212, 1.087, 0.583, 0.3068, 0.01154, 0.00165),
            (10, 42.82, 40.65, 0.1305, 53.92, 615.21, 561.29, 0.440, 0.0214, 1.091, 0.593, 0.3024, 0.01177, 0.00160),
            (15, 48.29, 40.38, 0.1457, 59.45, 616.79, 557.34, 0.420, 0.0217, 1.096, 0.603, 0.2979, 0.01201, 0.00155),
            (20, 54.30, 40.11, 0.1624, 65.01, 618.33, 553.32, 0.401, 0.0219, 1.102, 0.614, 0.2934, 0.01225, 0.00150),
            (25, 60.90, 39.82, 0.1806, 70.59, 619.83, 549.24, 0.383, 0.0222, 1.107, 0.626, 0.2889, 0.01250, 0.00145),
            (28, 65.35, 39.63, 0.1930, 74.15, 620.71, 546.56, 0.371, 0.0223, 1.111, 0.634, 0.2859, 0.01267, 0.00142),
            (30, 68.12, 39.53, 0.2005, 76.20, 621.28, 545.08, 0.365, 0.0224, 1.113, 0.638, 0.2844, 0.01276, 0.00140),
            (35, 75.99, 39.22, 0.2222, 81.84, 622.68, 540.84, 0.349, 0.0227, 1.120, 0.652, 0.2799, 0.01302, 0.00135),
            (40, 84.56, 38.91, 0.2458, 87.51, 624.03, 536.52, 0.333, 0.0229, 1.127, 0.666, 0.2753, 0.01329, 0.00130),
            (45, 93.87, 38.59, 0.2715, 93.21, 625.32, 532.11, 0.318, 0.0232, 1.134, 0.681, 0.2708, 0.01357, 0.00125),
            (50, 103.98, 38.26, 0.2993, 98.94, 626.56, 527.62, 0.303, 0.0235, 1.141, 0.697, 0.2662, 0.01386, 0.00120),
            (55, 114.93, 37.93, 0.3295, 104.70, 627.75, 523.05, 0.290, 0.0238, 1.149, 0.714, 0.2616, 0.01416, 0.00115),
            (60, 126.78, 37.59, 0.3621, 110.49, 628.88, 518.39, 0.277, 0.0240, 1.157, 0.732, 0.2570, 0.01447, 0.00110),
            (65, 139.57, 37.24, 0.3974, 116.32, 629.95, 513.63, 0.264, 0.0243, 1.165, 0.751, 0.2524, 0.01479, 0.00105),
            (70, 153.36, 36.88, 0.4356, 122.18, 630.96, 508.78, 0.252, 0.0246, 1.174, 0.771, 0.2478, 0.01512, 0.00100),
            (75, 168.21, 36.52, 0.4768, 128.08, 631.90, 503.82, 0.241, 0.0249, 1.183, 0.793, 0.2432, 0.01546, 0.00095),
            (80, 184.18, 36.14, 0.5213, 134.02, 632.78, 498.76, 0.230, 0.0252, 1.192, 0.816, 0.2386, 0.01581, 0.00090),
            (85, 201.32, 35.76, 0.5693, 139.99, 633.58, 493.59, 0.220, 0.0255, 1.202, 0.840, 0.2339, 0.01618, 0.00085),
            (90, 219.69, 35.37, 0.6210, 146.01, 634.31, 488.30, 0.210, 0.0258, 1.213, 0.866, 0.2292, 0.01656, 0.00080),
            (95, 239.34, 34.96, 0.6768, 152.06, 634.97, 482.91, 0.201, 0.0261, 1.224, 0.894, 0.2246, 0.01696, 0.00075),
            (100, 260.34, 34.55, 0.7369, 158.17, 635.54, 477.37, 0.192, 0.0264, 1.235, 0.924, 0.2199, 0.01737, 0.00070),
            (105, 282.75, 34.12, 0.8016, 164.32, 636.03, 471.71, 0.183, 0.0268, 1.247, 0.956, 0.2152, 0.01780, 0.00065),
            (110, 306.62, 33.68, 0.8714, 170.52, 636.43, 465.91, 0.175, 0.0271, 1.260, 0.990, 0.2105, 0.01825, 0.00060),
        ]
        
        for row in data:
            temp_f = row[0]
            props = SaturationProperties(
                temperature_f=temp_f,
                pressure_psia=row[1],
                liquid_density=row[2],
                vapor_density=row[3],
                liquid_enthalpy=row[4],
                vapor_enthalpy=row[5],
                latent_heat=row[6],
                liquid_viscosity=row[7],
                vapor_viscosity=row[8],
                liquid_cp=row[9],
                vapor_cp=row[10],
                liquid_k=row[11],
                vapor_k=row[12],
                surface_tension=row[13],
            )
            self._temp_table[temp_f] = props
        
        self._temps_sorted = sorted(self._temp_table.keys())
        
        # Extended density data for charge calculations (-100°F to 200°F)
        extended_density_data = [
            (-100, 45.4672, 0.00549), (-95, 45.2803, 0.00667), (-90, 45.0911, 0.00806),
            (-85, 44.8997, 0.00968), (-80, 44.7061, 0.01156), (-75, 44.5103, 0.01369),
            (-70, 44.3124, 0.01611), (-65, 44.1124, 0.01884), (-60, 43.9103, 0.02190),
            (-55, 43.7061, 0.02532), (-50, 43.4999, 0.02912), (-45, 43.2916, 0.03334),
            (-40, 43.0813, 0.03801), (-35, 42.869, 0.04316), (-30, 42.6547, 0.04883),
            (-25, 42.4384, 0.05506), (-20, 42.2202, 0.06188), (-15, 41.9999, 0.06934),
            (-10, 41.7777, 0.07749), (-5, 41.5536, 0.08636), (0, 41.3275, 0.09601),
            (5, 41.0994, 0.10648), (10, 40.8694, 0.11782), (15, 40.6374, 0.13009),
            (20, 40.4035, 0.14335), (25, 40.1676, 0.15766), (30, 39.9297, 0.17308),
            (35, 39.6899, 0.18969), (40, 39.448, 0.20755), (45, 39.2041, 0.22676),
            (50, 38.9582, 0.24738), (55, 38.7102, 0.26951), (60, 38.4602, 0.29324),
            (65, 38.208, 0.31867), (70, 37.9538, 0.34590), (75, 37.6974, 0.37504),
            (80, 37.4389, 0.40622), (85, 37.1782, 0.43957), (90, 36.9153, 0.47523),
            (95, 36.6501, 0.51334), (100, 36.3827, 0.55407), (105, 36.1129, 0.59759),
            (110, 35.8408, 0.64409), (115, 35.5662, 0.69377), (120, 35.2892, 0.74685),
            (125, 35.0097, 0.80357), (130, 34.7277, 0.86419), (135, 34.4431, 0.92897),
            (140, 34.1558, 0.99823), (145, 33.8658, 1.07229), (150, 33.5730, 1.15152),
        ]
        
        # Add extended data (primarily for density lookups)
        for temp_f, liq_dens, vap_dens in extended_density_data:
            if temp_f not in self._temp_table:
                # Estimate other properties or use nearest neighbor
                self._temp_table[temp_f] = SaturationProperties(
                    temperature_f=temp_f,
                    pressure_psia=self._estimate_pressure(temp_f),
                    liquid_density=liq_dens,
                    vapor_density=vap_dens,
                )
        
        self._temps_sorted = sorted(self._temp_table.keys())
    
    def _estimate_pressure(self, temp_f: float) -> float:
        """Estimate saturation pressure using Antoine equation approximation."""
        # Antoine equation constants for ammonia (approximate)
        # log10(P) = A - B/(C + T)
        # Using SI units internally then converting
        temp_c = (temp_f - 32) * 5 / 9
        temp_k = temp_c + 273.15
        
        # Approximate coefficients
        A = 4.86886
        B = 1113.928
        C = -10.409
        
        try:
            log_p_bar = A - B / (temp_k + C)
            p_bar = 10 ** log_p_bar
            p_psia = p_bar * 14.5038
            return p_psia
        except:
            return 30.0  # Default fallback


class CO2Properties(RefrigerantProperties):
    """
    Carbon Dioxide (CO2/R744) thermodynamic properties.
    
    Note: CO2 has a critical point at 87.8°F, 1070 psia.
    Subcritical operation typical below 87°F.
    """
    
    def __init__(self):
        super().__init__("Carbon Dioxide", molecular_weight=44.01)
        self._load_data()
    
    def _load_data(self):
        """Load CO2 saturation property data."""
        # CO2 saturation data (subcritical region)
        # Format: (temp_F, pressure_psia, liquid_density, vapor_density)
        data = [
            (-60, 104.1, 73.5, 1.15),
            (-50, 130.8, 71.8, 1.45),
            (-40, 162.6, 70.0, 1.82),
            (-30, 200.0, 68.1, 2.26),
            (-20, 243.5, 66.1, 2.78),
            (-10, 293.8, 63.9, 3.40),
            (0, 351.5, 61.6, 4.14),
            (10, 417.2, 59.1, 5.02),
            (20, 491.6, 56.3, 6.07),
            (30, 575.4, 53.2, 7.35),
            (40, 669.5, 49.6, 8.94),
            (50, 774.8, 45.4, 11.0),
            (60, 892.6, 40.1, 14.0),
            (70, 1024.0, 32.8, 19.0),
            (80, 1055.0, 26.0, 26.0),  # Near critical
        ]
        
        for row in data:
            temp_f = row[0]
            props = SaturationProperties(
                temperature_f=temp_f,
                pressure_psia=row[1],
                liquid_density=row[2],
                vapor_density=row[3],
            )
            self._temp_table[temp_f] = props
        
        self._temps_sorted = sorted(self._temp_table.keys())


class R22Properties(RefrigerantProperties):
    """R22 (HCFC-22) thermodynamic properties."""
    
    def __init__(self):
        super().__init__("R22", molecular_weight=86.47)
        self._load_data()
    
    def _load_data(self):
        """Load R22 saturation property data."""
        data = [
            (-40, 15.3, 86.8, 0.65),
            (-30, 20.6, 85.2, 0.86),
            (-20, 27.2, 83.5, 1.11),
            (-10, 35.1, 81.8, 1.42),
            (0, 44.7, 79.9, 1.79),
            (10, 56.1, 78.0, 2.23),
            (20, 69.5, 76.0, 2.75),
            (30, 85.1, 73.9, 3.35),
            (40, 103.0, 71.6, 4.05),
            (50, 123.6, 69.2, 4.86),
            (60, 147.0, 66.6, 5.80),
            (70, 173.4, 63.9, 6.89),
            (80, 202.9, 60.9, 8.15),
            (90, 235.9, 57.6, 9.62),
            (100, 272.4, 53.9, 11.4),
            (110, 312.9, 49.7, 13.5),
            (120, 357.5, 44.7, 16.2),
        ]
        
        for row in data:
            temp_f = row[0]
            props = SaturationProperties(
                temperature_f=temp_f,
                pressure_psia=row[1],
                liquid_density=row[2],
                vapor_density=row[3],
            )
            self._temp_table[temp_f] = props
        
        self._temps_sorted = sorted(self._temp_table.keys())


class R507Properties(RefrigerantProperties):
    """R507 (R507A) thermodynamic properties."""
    
    def __init__(self):
        super().__init__("R507", molecular_weight=98.86)
        self._load_data()
    
    def _load_data(self):
        """Load R507 saturation property data."""
        data = [
            (-60, 8.7, 88.1, 0.40),
            (-50, 12.2, 86.4, 0.55),
            (-40, 16.7, 84.6, 0.74),
            (-30, 22.5, 82.7, 0.98),
            (-20, 29.7, 80.7, 1.28),
            (-10, 38.5, 78.6, 1.64),
            (0, 49.2, 76.4, 2.07),
            (10, 61.8, 74.0, 2.59),
            (20, 76.7, 71.5, 3.21),
            (30, 94.1, 68.9, 3.93),
            (40, 114.1, 66.0, 4.78),
            (50, 137.0, 62.9, 5.78),
            (60, 162.9, 59.6, 6.94),
            (70, 192.1, 55.9, 8.31),
            (80, 224.7, 51.9, 9.93),
            (90, 261.1, 47.3, 11.9),
            (100, 301.3, 42.0, 14.3),
        ]
        
        for row in data:
            temp_f = row[0]
            props = SaturationProperties(
                temperature_f=temp_f,
                pressure_psia=row[1],
                liquid_density=row[2],
                vapor_density=row[3],
            )
            self._temp_table[temp_f] = props
        
        self._temps_sorted = sorted(self._temp_table.keys())


class R404aProperties(RefrigerantProperties):
    """R404A thermodynamic properties."""
    
    def __init__(self):
        super().__init__("R404A", molecular_weight=97.60)
        self._load_data()
    
    def _load_data(self):
        """Load R404A saturation property data."""
        data = [
            (-60, 9.1, 86.9, 0.42),
            (-50, 12.8, 85.1, 0.58),
            (-40, 17.4, 83.3, 0.78),
            (-30, 23.4, 81.3, 1.03),
            (-20, 30.9, 79.2, 1.34),
            (-10, 40.0, 77.0, 1.72),
            (0, 51.0, 74.7, 2.18),
            (10, 64.0, 72.2, 2.73),
            (20, 79.4, 69.6, 3.38),
            (30, 97.3, 66.8, 4.14),
            (40, 117.9, 63.8, 5.04),
            (50, 141.4, 60.5, 6.10),
            (60, 168.0, 56.9, 7.35),
            (70, 197.9, 53.0, 8.83),
            (80, 231.4, 48.6, 10.6),
            (90, 268.6, 43.5, 12.8),
            (100, 309.8, 37.5, 15.6),
        ]
        
        for row in data:
            temp_f = row[0]
            props = SaturationProperties(
                temperature_f=temp_f,
                pressure_psia=row[1],
                liquid_density=row[2],
                vapor_density=row[3],
            )
            self._temp_table[temp_f] = props
        
        self._temps_sorted = sorted(self._temp_table.keys())


class R449AProperties(RefrigerantProperties):
    """R449A thermodynamic properties (replacement for R22/R404A)."""
    
    def __init__(self):
        super().__init__("R449A", molecular_weight=87.20)
        self._load_data()
    
    def _load_data(self):
        """Load R449A saturation property data."""
        data = [
            (-40, 14.8, 83.5, 0.68),
            (-30, 20.1, 81.7, 0.91),
            (-20, 26.8, 79.8, 1.19),
            (-10, 34.9, 77.8, 1.53),
            (0, 44.8, 75.7, 1.95),
            (10, 56.5, 73.4, 2.44),
            (20, 70.4, 71.0, 3.03),
            (30, 86.6, 68.4, 3.72),
            (40, 105.4, 65.7, 4.53),
            (50, 127.0, 62.7, 5.49),
            (60, 151.6, 59.4, 6.61),
            (70, 179.4, 55.9, 7.93),
            (80, 210.6, 51.9, 9.49),
            (90, 245.6, 47.4, 11.4),
            (100, 284.5, 42.2, 13.7),
        ]
        
        for row in data:
            temp_f = row[0]
            props = SaturationProperties(
                temperature_f=temp_f,
                pressure_psia=row[1],
                liquid_density=row[2],
                vapor_density=row[3],
            )
            self._temp_table[temp_f] = props
        
        self._temps_sorted = sorted(self._temp_table.keys())


def get_refrigerant(name: str) -> RefrigerantProperties:
    """
    Factory function to get a refrigerant properties object.
    
    Args:
        name: Refrigerant name ('NH3', 'CO2', 'R22', 'R404A', 'R449A', 'R507')
    
    Returns:
        RefrigerantProperties object for the specified refrigerant
    
    Example:
        >>> r = get_refrigerant('NH3')
        >>> print(r.saturation_pressure(0))
        33.37
    """
    refrigerants = {
        'NH3': NH3Properties,
        'R717': NH3Properties,
        'AMMONIA': NH3Properties,
        'CO2': CO2Properties,
        'R744': CO2Properties,
        'R22': R22Properties,
        'R404A': R404aProperties,
        'R404': R404aProperties,
        'R449A': R449AProperties,
        'R449': R449AProperties,
        'R507': R507Properties,
        'R507A': R507Properties,
    }
    
    name_upper = name.upper().replace('-', '').replace(' ', '')
    
    if name_upper not in refrigerants:
        raise ValueError(f"Unknown refrigerant: {name}. Available: {list(set(refrigerants.values()))}")
    
    return refrigerants[name_upper]()
