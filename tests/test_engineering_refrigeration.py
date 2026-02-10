"""Tests for RefrigerationCalculator and the five run_*() functions."""

import pytest

from qms.engineering.refrigeration import (
    RefrigerationCalculator,
    run_line_sizing,
    run_relief_valve,
    run_pump,
    run_ventilation,
    run_charge,
)


class TestRefrigerationCalculator:
    def test_discipline_name(self):
        assert RefrigerationCalculator().discipline_name == "refrigeration"

    def test_available_calculations(self):
        calcs = RefrigerationCalculator().available_calculations()
        assert set(calcs) == {"line-sizing", "relief-valve", "pump", "ventilation", "charge"}

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown calculation type"):
            RefrigerationCalculator().run_calculation("bogus", {})

    def test_dispatch_returns_result(self):
        result = RefrigerationCalculator().run_calculation("charge", {})
        assert result.calculation_type == "charge"
        d = result.to_dict()
        assert "total_charge_lb" in d


class TestRunLineSizing:
    def test_defaults_run(self):
        result = run_line_sizing({})
        assert result is not None
        assert "nominal_size" in result or "selected_size" in result

    def test_100ton_dry_suction(self):
        result = run_line_sizing({
            "capacity_tons": 100, "suction_temp": 28,
            "condensing_temp": 95, "length": 100,
            "line_type": "dry", "refrigerant": "NH3",
        })
        assert result is not None

    def test_wet_suction(self):
        result = run_line_sizing({
            "line_type": "wet", "capacity_tons": 100, "recirculation_rate": 4.0,
        })
        assert result is not None

    def test_liquid_line(self):
        result = run_line_sizing({"line_type": "liquid", "capacity_tons": 100})
        assert result is not None

    def test_discharge_line(self):
        result = run_line_sizing({"line_type": "discharge", "capacity_tons": 100})
        assert result is not None


class TestRunReliefValve:
    def test_defaults_run(self):
        result = run_relief_valve({})
        assert "selected_orifice" in result

    def test_100cuft_250psig(self):
        result = run_relief_valve({
            "volume_cuft": 100, "set_pressure_psig": 250, "refrigerant": "NH3",
        })
        assert result["set_pressure_psig"] == 250
        assert result["num_valves"] >= 1

    def test_total_area_covers_required(self):
        result = run_relief_valve({"volume_cuft": 50, "set_pressure_psig": 300})
        total_area = result["selected_area_sqin"] * result["num_valves"]
        assert total_area >= result["required_area_sqin"]


class TestRunPump:
    def test_defaults_run(self):
        result = run_pump({})
        assert "flow_rate_gpm" in result
        assert result["flow_rate_gpm"] > 0

    def test_200ton(self):
        small = run_pump({"capacity_tons": 50})
        large = run_pump({"capacity_tons": 200})
        assert large["flow_rate_gpm"] > small["flow_rate_gpm"]


class TestRunVentilation:
    def test_defaults_run(self):
        result = run_ventilation({})
        assert "emergency_cfm" in result
        assert result["emergency_cfm"] > 0

    def test_30x20x12_room(self):
        result = run_ventilation({
            "length_ft": 30, "width_ft": 20, "height_ft": 12,
            "refrigerant_charge_lb": 1000,
        })
        assert result["emergency_cfm"] > 0

    def test_ashrae_standard(self):
        result = run_ventilation({"standard": "ashrae"})
        assert result["emergency_cfm"] > 0


class TestRunCharge:
    def test_nh3_vessel(self):
        result = run_charge({
            "volume_cuft": 20, "temperature": -20,
            "liquid_percent": 80, "refrigerant": "NH3",
            "component_type": "vessel",
        })
        assert result["total_charge_lb"] > 0
        assert result["liquid_charge_lb"] > result["vapor_charge_lb"]
        # At -20F, NH3 liquid density is 42.16 lb/ft3
        # 20 ft3 * 80% = 16 ft3 liquid => ~674.6 lb
        expected_liquid = 16 * 42.16
        assert abs(result["liquid_charge_lb"] - expected_liquid) < 1.0

    def test_returns_all_fields(self):
        result = run_charge({})
        for key in ["total_charge_lb", "liquid_charge_lb", "vapor_charge_lb",
                     "volume_cuft", "temperature_f", "liquid_percent",
                     "component_type", "refrigerant"]:
            assert key in result, f"Missing key: {key}"

    def test_vapor_charge_positive(self):
        result = run_charge({"liquid_percent": 50})
        assert result["vapor_charge_lb"] > 0
