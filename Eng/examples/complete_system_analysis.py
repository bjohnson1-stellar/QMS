#!/usr/bin/env python3
"""
Example: Complete Refrigeration System Analysis
===============================================

This example demonstrates using the refrig_calc library to:
1. Size suction and liquid lines
2. Calculate system refrigerant charge
3. Determine machine room ventilation requirements
4. Analyze potential release scenarios
"""

import sys
sys.path.insert(0, '..')

from refrig_calc import (
    NH3Properties,
    LineSizing,
    ChargeCalculator,
    VesselDimensions,
    VesselOrientation,
    CoilType,
    MachineRoomVentilation,
    RoomDimensions,
    NH3ReleaseCalculator,
    utils,
)
from refrig_calc.charge import calculate_system_charge


def main():
    print("=" * 70)
    print("REFRIGERATION SYSTEM ANALYSIS EXAMPLE")
    print("=" * 70)
    
    # System parameters
    system_capacity = 500  # tons
    suction_temp = 28      # °F
    condensing_temp = 95   # °F
    
    # =========================================================================
    # 1. REFRIGERANT PROPERTIES
    # =========================================================================
    print("\n" + "=" * 70)
    print("1. AMMONIA PROPERTIES AT OPERATING CONDITIONS")
    print("=" * 70)
    
    nh3 = NH3Properties()
    
    # Properties at suction conditions
    suction_props = nh3.get_properties_at_temp(suction_temp)
    print(f"\nSuction conditions ({suction_temp}°F):")
    print(f"  Pressure: {suction_props.pressure_psia:.2f} psia ({utils.psia_to_psig(suction_props.pressure_psia):.2f} psig)")
    print(f"  Liquid density: {suction_props.liquid_density:.2f} lb/ft³")
    print(f"  Vapor density: {suction_props.vapor_density:.4f} lb/ft³")
    print(f"  Latent heat: {suction_props.latent_heat:.1f} BTU/lb")
    
    # Properties at condensing conditions
    cond_props = nh3.get_properties_at_temp(condensing_temp)
    print(f"\nCondensing conditions ({condensing_temp}°F):")
    print(f"  Pressure: {cond_props.pressure_psia:.2f} psia ({utils.psia_to_psig(cond_props.pressure_psia):.2f} psig)")
    print(f"  Liquid density: {cond_props.liquid_density:.2f} lb/ft³")
    print(f"  Vapor density: {cond_props.vapor_density:.4f} lb/ft³")
    
    # =========================================================================
    # 2. LINE SIZING
    # =========================================================================
    print("\n" + "=" * 70)
    print("2. LINE SIZING CALCULATIONS")
    print("=" * 70)
    
    sizing = LineSizing('NH3')
    
    # Size main suction header
    suction_result = sizing.size_suction_line(
        capacity_tons=system_capacity,
        suction_temp=suction_temp,
        condensing_temp=condensing_temp,
        total_length=200,
        num_90_elbows=6,
        num_45_elbows=2,
        line_type='dry',
    )
    
    print(f"\nMain Suction Header ({system_capacity} TR, {suction_temp}°F):")
    print(f"  Recommended size: {suction_result.nominal_size}\"")
    print(f"  Velocity: {suction_result.velocity:.1f} ft/s")
    print(f"  Pressure drop: {suction_result.pressure_drop_per_100ft:.3f} psi/100ft")
    print(f"  Total pressure drop: {suction_result.total_pressure_drop:.3f} psi")
    print(f"  Temperature drop: {suction_result.total_temp_drop:.2f}°F")
    print(f"  Reynolds number: {suction_result.reynolds_number:,.0f}")
    
    # Size liquid line
    liquid_result = sizing.size_liquid_line(
        capacity_tons=system_capacity,
        liquid_temp=85,
        condensing_temp=condensing_temp,
        total_length=150,
        num_90_elbows=4,
        recirculation_rate=4.0,  # 4:1 recirculation
    )
    
    print(f"\nHigh Pressure Liquid Line:")
    print(f"  Recommended size: {liquid_result.nominal_size}\"")
    print(f"  Velocity: {liquid_result.velocity:.2f} ft/s")
    print(f"  Pressure drop: {liquid_result.total_pressure_drop:.2f} psi")
    
    # Size discharge line
    discharge_result = sizing.size_discharge_line(
        capacity_tons=system_capacity,
        discharge_temp=180,
        condensing_temp=condensing_temp,
        total_length=100,
        num_90_elbows=4,
    )
    
    print(f"\nDischarge (Hot Gas) Line:")
    print(f"  Recommended size: {discharge_result.nominal_size}\"")
    print(f"  Velocity: {discharge_result.velocity:.1f} ft/s")
    print(f"  Pressure drop: {discharge_result.total_pressure_drop:.2f} psi")
    
    # =========================================================================
    # 3. CHARGE CALCULATIONS
    # =========================================================================
    print("\n" + "=" * 70)
    print("3. REFRIGERANT CHARGE CALCULATIONS")
    print("=" * 70)
    
    calc = ChargeCalculator('NH3')
    charges = []
    
    # Low pressure receiver
    lpr_vessel = VesselDimensions(diameter=60, length=144)
    lpr_charge = calc.vessel_charge(
        vessel=lpr_vessel,
        orientation=VesselOrientation.HORIZONTAL,
        operating_temp=suction_temp,
        operating_level=0.4,
    )
    charges.append(lpr_charge)
    print(f"\nLow Pressure Receiver (60\" × 144\"):")
    print(f"  Liquid charge: {lpr_charge.liquid_charge:.1f} lb")
    print(f"  Vapor charge: {lpr_charge.vapor_charge:.1f} lb")
    print(f"  Total charge: {lpr_charge.total_charge:.1f} lb")
    
    # Evaporator coils (assume 10 units @ 50 TR each)
    for i in range(10):
        coil_charge = calc.coil_charge(
            capacity_tons=50,
            suction_temp=suction_temp,
            coil_type=CoilType.RECIRCULATED,
            recirculation_rate=4.0,
        )
        charges.append(coil_charge)
    
    total_coil_charge = sum(c.total_charge for c in charges[1:11])
    print(f"\nEvaporator Coils (10 × 50 TR):")
    print(f"  Total coil charge: {total_coil_charge:.1f} lb")
    
    # Piping
    suction_pipe = calc.pipe_charge(
        pipe_size=suction_result.nominal_size,
        length=suction_result.total_length,
        pipe_type='suction_wet',
        temperature=suction_temp,
        recirculation_rate=4.0,
    )
    charges.append(suction_pipe)
    print(f"\nSuction Piping ({suction_result.nominal_size}\" × {suction_result.total_length:.0f}'):")
    print(f"  Charge: {suction_pipe.total_charge:.1f} lb")
    
    liquid_pipe = calc.pipe_charge(
        pipe_size=liquid_result.nominal_size,
        length=liquid_result.total_length,
        pipe_type='liquid',
        temperature=85,
    )
    charges.append(liquid_pipe)
    print(f"\nLiquid Piping ({liquid_result.nominal_size}\" × {liquid_result.total_length:.0f}'):")
    print(f"  Charge: {liquid_pipe.total_charge:.1f} lb")
    
    # Condenser
    condenser_charge = calc.condenser_charge(
        capacity_tons=system_capacity * 1.2,  # 20% oversized
        condensing_temp=condensing_temp,
        condenser_type='evaporative',
        receiver_size=500,  # gallons
    )
    charges.append(condenser_charge)
    print(f"\nEvaporative Condenser:")
    print(f"  Charge: {condenser_charge.total_charge:.1f} lb")
    
    # Total system charge
    system_charge = calculate_system_charge(charges)
    print(f"\n{'='*50}")
    print(f"TOTAL SYSTEM CHARGE: {system_charge.total_charge:,.1f} lb")
    print(f"{'='*50}")
    
    # =========================================================================
    # 4. VENTILATION CALCULATIONS
    # =========================================================================
    print("\n" + "=" * 70)
    print("4. MACHINE ROOM VENTILATION")
    print("=" * 70)
    
    vent = MachineRoomVentilation()
    room = RoomDimensions(width=50, length=80, height=20)
    
    vent_result = vent.calculate(
        room=room,
        system_charge=system_charge.total_charge,
        motor_hp=250,  # Total compressor HP
        motor_efficiency=0.92,
        outdoor_design_temp=95,
        indoor_design_temp=104,
    )
    
    print(f"\nMachine Room ({room.width}' × {room.length}' × {room.height}'):")
    print(f"  Volume: {room.volume:,} ft³")
    print(f"  System charge: {system_charge.total_charge:,.0f} lb")
    print(f"\nVentilation Requirements:")
    print(f"  Emergency exhaust: {vent_result.emergency_cfm:,.0f} CFM")
    print(f"  Normal ventilation: {vent_result.normal_cfm:,.0f} CFM")
    print(f"  Air changes (emergency): {vent_result.air_changes_per_hour:.1f} ACH")
    print(f"\nHeat Load Analysis:")
    print(f"  Motor heat: {vent_result.motor_heat_btu_hr:,.0f} BTU/hr")
    print(f"  Transmission heat: {vent_result.transmission_heat_btu_hr:,.0f} BTU/hr")
    print(f"  Total heat load: {vent_result.heat_load_btu_hr:,.0f} BTU/hr")
    print(f"\nFan Requirements:")
    print(f"  Number of fans: {vent_result.num_fans_required}")
    print(f"  Fan size: {vent_result.fan_size_cfm:,.0f} CFM each")
    
    # =========================================================================
    # 5. RELEASE SCENARIO ANALYSIS
    # =========================================================================
    print("\n" + "=" * 70)
    print("5. AMMONIA RELEASE ANALYSIS")
    print("=" * 70)
    
    release_calc = NH3ReleaseCalculator()
    
    # Scenario: 1/4" hole in liquid line
    release_result = release_calc.iiar_flashing_release(
        hole_diameter=0.25,
        system_temp=condensing_temp,
        leak_duration=15,
        room_volume=room.volume,
        exhaust_rate=vent_result.emergency_cfm,
    )
    
    print(f"\nScenario: 1/4\" hole in liquid line at {condensing_temp}°F")
    print(f"  Vapor release rate: {release_result.vapor_release_rate_lb_min:.2f} lb/min")
    print(f"  Total released (15 min): {release_result.mass_released_lb:.1f} lb")
    print(f"  Indoor concentration: {release_result.indoor_concentration_ppm:,.0f} ppm")
    
    # Check against exposure limits
    print(f"\nExposure Limit Comparison:")
    print(f"  TLV (25 ppm): {'EXCEEDED' if release_result.indoor_concentration_ppm > 25 else 'OK'}")
    print(f"  IDLH (300 ppm): {'EXCEEDED' if release_result.indoor_concentration_ppm > 300 else 'OK'}")
    
    # Required exhaust to meet 40 ppm outdoor target
    required_exhaust = release_calc.calculate_required_exhaust(
        vapor_release_rate=release_result.vapor_release_rate_lb_min,
        target_outdoor_ppm=40,
    )
    print(f"\nRequired exhaust for 40 ppm outdoor: {required_exhaust:,.0f} CFM")
    
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
