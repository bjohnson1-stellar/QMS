"""Tests for NH3 thermodynamic properties against ASHRAE reference values.

All expected values come from the data table in
qms/engineering/refrig_calc/properties.py (NH3Properties._load_data).
"""

from qms.engineering.refrig_calc import (
    NH3Properties, CO2Properties, R22Properties,
    R404aProperties, R449AProperties, R507Properties,
    get_refrigerant,
)


class TestNH3SaturationPressure:
    def test_at_0f(self):
        assert abs(NH3Properties().saturation_pressure(0) - 33.37) < 0.01

    def test_at_minus40f(self):
        assert abs(NH3Properties().saturation_pressure(-40) - 10.77) < 0.01

    def test_at_28f(self):
        assert abs(NH3Properties().saturation_pressure(28) - 65.35) < 0.01

    def test_at_minus60f(self):
        assert abs(NH3Properties().saturation_pressure(-60) - 5.539) < 0.01

    def test_at_110f(self):
        assert abs(NH3Properties().saturation_pressure(110) - 306.62) < 0.01


class TestNH3Density:
    def test_liquid_at_0f(self):
        assert abs(NH3Properties().liquid_density(0) - 41.18) < 0.01

    def test_vapor_at_0f(self):
        assert abs(NH3Properties().vapor_density(0) - 0.1041) < 0.001

    def test_liquid_at_minus20f(self):
        assert abs(NH3Properties().liquid_density(-20) - 42.16) < 0.01

    def test_vapor_at_minus20f(self):
        assert abs(NH3Properties().vapor_density(-20) - 0.0646) < 0.001


class TestNH3LatentHeat:
    def test_at_0f(self):
        assert abs(NH3Properties().latent_heat(0) - 568.99) < 0.1

    def test_at_minus40f(self):
        assert abs(NH3Properties().latent_heat(-40) - 597.52) < 0.1

    def test_at_110f(self):
        assert abs(NH3Properties().latent_heat(110) - 465.91) < 0.1


class TestNH3Interpolation:
    def test_midpoint_between_25_and_28(self):
        """Interpolated pressure at 26.5F should be between table values at 25F and 28F."""
        props = NH3Properties().get_properties_at_temp(26.5)
        assert 60.90 < props.pressure_psia < 65.35

    def test_clamped_below_range(self):
        """Temperatures below the data range should clamp to lowest entry."""
        nh3 = NH3Properties()
        low = nh3._temps_sorted[0]
        props = nh3.get_properties_at_temp(-500)
        assert props.temperature_f == low

    def test_clamped_above_range(self):
        """Temperatures above the data range should clamp to highest entry."""
        nh3 = NH3Properties()
        high = nh3._temps_sorted[-1]
        props = nh3.get_properties_at_temp(1000)
        assert props.temperature_f == high


class TestGetRefrigerant:
    def test_nh3(self):
        refrig = get_refrigerant("NH3")
        assert isinstance(refrig, NH3Properties)

    def test_case_insensitive(self):
        refrig = get_refrigerant("nh3")
        assert refrig.name == "Ammonia"

    def test_co2(self):
        refrig = get_refrigerant("CO2")
        assert isinstance(refrig, CO2Properties)


class TestAllRefrigerantClasses:
    def test_all_have_data(self):
        for cls in [NH3Properties, CO2Properties, R22Properties,
                    R404aProperties, R449AProperties, R507Properties]:
            instance = cls()
            assert len(instance._temps_sorted) > 5, (
                f"{cls.__name__} has insufficient temperature data"
            )

    def test_nh3_name_and_mw(self):
        nh3 = NH3Properties()
        assert nh3.name == "Ammonia"
        assert nh3.molecular_weight == 17.03
