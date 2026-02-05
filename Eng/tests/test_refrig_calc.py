#!/usr/bin/env python3
"""
Unit Tests for refrig_calc library
==================================

Run with: python -m pytest tests/test_refrig_calc.py -v
Or simply: python tests/test_refrig_calc.py
"""

import sys
import math
sys.path.insert(0, '..')

from refrig_calc import (
    NH3Properties,
    LineSizing,
    ChargeCalculator,
    VesselDimensions,
    VesselOrientation,
    MachineRoomVentilation,
    RoomDimensions,
    NH3ReleaseCalculator,
    utils,
)
from refrig_calc.properties import get_refrigerant, CO2Properties, R22Properties


def test_nh3_properties():
    """Test NH3 saturation properties."""
    nh3 = NH3Properties()
    
    # Test at 0°F
    props = nh3.get_properties_at_temp(0)
    assert 30 < props.pressure_psia < 35, f"Unexpected pressure at 0°F: {props.pressure_psia}"
    assert 40 < props.liquid_density < 42, f"Unexpected liquid density: {props.liquid_density}"
    
    # Test at 28°F (common suction temp)
    props = nh3.get_properties_at_temp(28)
    assert 60 < props.pressure_psia < 70, f"Unexpected pressure at 28°F: {props.pressure_psia}"
    
    # Test at 95°F (common condensing temp)
    props = nh3.get_properties_at_temp(95)
    assert 230 < props.pressure_psia < 250, f"Unexpected pressure at 95°F: {props.pressure_psia}"
    
    print("✓ NH3 properties tests passed")


def test_refrigerant_factory():
    """Test refrigerant factory function."""
    nh3 = get_refrigerant('NH3')
    assert isinstance(nh3, NH3Properties)
    
    r717 = get_refrigerant('R717')
    assert isinstance(r717, NH3Properties)
    
    co2 = get_refrigerant('CO2')
    assert isinstance(co2, CO2Properties)
    
    r22 = get_refrigerant('R22')
    assert isinstance(r22, R22Properties)
    
    print("✓ Refrigerant factory tests passed")


def test_line_sizing():
    """Test line sizing calculations."""
    sizing = LineSizing('NH3')
    
    # Size a suction line
    result = sizing.size_suction_line(
        capacity_tons=100,
        suction_temp=28,
        condensing_temp=95,
        total_length=150,
        num_90_elbows=4,
        line_type='dry',
    )
    
    # Should recommend a reasonable pipe size
    assert 4 <= result.nominal_size <= 12, f"Unexpected pipe size: {result.nominal_size}"
    
    # Velocity should be within limits (15-60 ft/s for dry suction)
    assert 15 <= result.velocity <= 60, f"Velocity out of range: {result.velocity}"
    
    # Pressure drop should be reasonable
    assert 0 < result.total_pressure_drop < 5, f"Pressure drop unusual: {result.total_pressure_drop}"
    
    print("✓ Line sizing tests passed")


def test_charge_calculations():
    """Test refrigerant charge calculations."""
    calc = ChargeCalculator('NH3')
    
    # Test vessel charge
    vessel = VesselDimensions(diameter=48, length=120)
    result = calc.vessel_charge(
        vessel=vessel,
        orientation=VesselOrientation.HORIZONTAL,
        operating_temp=28,
        operating_level=0.5,
    )
    
    # Charge should be positive
    assert result.total_charge > 0, "Charge should be positive"
    assert result.liquid_charge > 0, "Liquid charge should be positive"
    assert result.vapor_charge >= 0, "Vapor charge should be non-negative"
    
    # Total should equal liquid + vapor
    assert abs(result.total_charge - (result.liquid_charge + result.vapor_charge)) < 0.1
    
    print("✓ Charge calculation tests passed")


def test_ventilation():
    """Test ventilation calculations."""
    vent = MachineRoomVentilation()
    room = RoomDimensions(width=40, length=60, height=16)
    
    result = vent.calculate(
        room=room,
        system_charge=5000,
        motor_hp=150,
        outdoor_design_temp=95,
    )
    
    # Emergency CFM should be substantial for 5000 lb charge
    assert result.emergency_cfm > 10000, f"Emergency CFM seems low: {result.emergency_cfm}"
    
    # Air changes should be reasonable
    assert result.air_changes_per_hour >= 20, f"ACH seems low: {result.air_changes_per_hour}"
    
    print("✓ Ventilation tests passed")


def test_nh3_release():
    """Test ammonia release calculations."""
    calc = NH3ReleaseCalculator()
    
    result = calc.iiar_flashing_release(
        hole_diameter=0.25,
        system_temp=95,
        leak_duration=15,
        room_volume=50000,
        exhaust_rate=20000,
    )
    
    # Release rate should be positive
    assert result.vapor_release_rate_lb_min > 0, "Release rate should be positive"
    
    # Total mass should equal rate × time
    expected_mass = result.vapor_release_rate_lb_min * result.leak_duration_min
    assert abs(result.mass_released_lb - expected_mass) < 0.1
    
    print("✓ NH3 release tests passed")


def test_utils():
    """Test utility functions."""
    # Temperature conversions
    assert abs(utils.fahrenheit_to_celsius(32) - 0) < 0.01
    assert abs(utils.fahrenheit_to_celsius(212) - 100) < 0.01
    assert abs(utils.celsius_to_fahrenheit(0) - 32) < 0.01
    
    # Pressure conversions
    assert abs(utils.psia_to_psig(14.696) - 0) < 0.01
    assert abs(utils.psig_to_psia(0) - 14.696) < 0.01
    
    # Capacity conversions
    assert abs(utils.tons_to_btu_hr(1) - 12000) < 0.01
    assert abs(utils.btu_hr_to_tons(12000) - 1) < 0.01
    
    # Flow calculations
    ach = utils.air_changes_per_hour(1000, 60000)
    assert abs(ach - 1.0) < 0.01
    
    print("✓ Utility tests passed")


def test_pipe_volume():
    """Test pipe volume calculations."""
    # 2" pipe, 100 ft
    volume = utils.pipe_volume(2.067, 100)
    
    # Expected: π × (2.067/12)² / 4 × 100 ≈ 2.33 ft³
    expected = math.pi * (2.067/12)**2 / 4 * 100
    assert abs(volume - expected) < 0.01, f"Volume mismatch: {volume} vs {expected}"
    
    print("✓ Pipe volume tests passed")


def test_cylinder_volumes():
    """Test cylinder volume calculations."""
    # Cylinder: 48" diameter, 120" length
    volume = utils.cylinder_volume(48, 120)
    
    # Expected: π × 24² × 120 / 1728 ≈ 125.66 ft³
    expected = math.pi * 24**2 * 120 / 1728
    assert abs(volume - expected) < 0.1, f"Volume mismatch: {volume} vs {expected}"
    
    print("✓ Cylinder volume tests passed")


def test_horizontal_partial_fill():
    """Test partial fill calculation for horizontal cylinder."""
    # 48" diameter, 120" length, 50% full
    full_volume = utils.cylinder_volume(48, 120)
    half_volume = utils.horizontal_cylinder_partial_volume(48, 120, 24)
    
    # Half full should be approximately half the total (exact for semicircle)
    assert abs(half_volume - full_volume/2) < 1, f"Half fill mismatch: {half_volume} vs {full_volume/2}"
    
    print("✓ Horizontal partial fill tests passed")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("RUNNING REFRIG_CALC LIBRARY TESTS")
    print("="*60 + "\n")
    
    test_nh3_properties()
    test_refrigerant_factory()
    test_line_sizing()
    test_charge_calculations()
    test_ventilation()
    test_nh3_release()
    test_utils()
    test_pipe_volume()
    test_cylinder_volumes()
    test_horizontal_partial_fill()
    
    print("\n" + "="*60)
    print("ALL TESTS PASSED ✓")
    print("="*60 + "\n")


if __name__ == '__main__':
    run_all_tests()
