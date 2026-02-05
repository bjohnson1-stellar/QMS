# Refrigeration Engineering Calculations Library

A comprehensive Python library for industrial refrigeration system design and analysis.

## Version 2.0.0

## Installation

```bash
pip install refrig_calc
# or
python setup.py install
```

## Modules Overview

| Module | Description |
|--------|-------------|
| `properties` | Thermodynamic properties for NH3, CO2, R22, R404a, R449A, R507 |
| `line_sizing` | Pipe sizing for suction, discharge, and liquid lines |
| `charge` | Refrigerant charge calculations for vessels, coils, and piping |
| `ventilation` | Machine room ventilation per IIAR-2 and ASHRAE 15 |
| `release` | Ammonia release calculations per IIAR, EPA, NFPA methods |
| `loads` | Refrigeration load calculations for cold storage |
| `evaporator` | Evaporator selection and capacity correction |
| `condenser` | Condenser sizing for evaporative and air-cooled |
| `expansion` | TXV, EEV, float valve, and orifice sizing |
| `glycol` | Secondary coolant properties and system design |
| `relief_valve` | Pressure relief valve sizing per ASME/IIAR |
| `pumps` | Pump sizing for refrigerant and glycol systems |
| `utils` | Unit conversions and common calculations |

---

## Quick Start Examples

### Refrigeration Load Calculation

```python
from refrig_calc import RefrigerationLoadCalculator, ProductType
from refrig_calc.loads import RoomDimensions

# Define room
room = RoomDimensions(length=100, width=50, height=20)

# Calculate load
calc = RefrigerationLoadCalculator()
result = calc.calculate_cooler_load(
    room=room,
    inside_temp=35,
    outside_temp=95,
    product_type=ProductType.BEEF,
    product_load_lb_day=50000,
)

print(result)
# Output shows transmission, infiltration, product, equipment loads
# Total: XX.X tons
```

### Line Sizing

```python
from refrig_calc import LineSizing, get_refrigerant

nh3 = get_refrigerant('NH3')
sizer = LineSizing(nh3)

result = sizer.size_suction_line(
    capacity_tons=100,
    suction_temp=-10,
    equivalent_length=200,
)

print(f"Pipe size: {result.pipe_size}\"")
print(f"Velocity: {result.velocity:.1f} ft/s")
print(f"Pressure drop: {result.pressure_drop:.3f} psi/100ft")
```

### Evaporator Selection

```python
from refrig_calc import EvaporatorCalculator, DefrostType

calc = EvaporatorCalculator()
result = calc.select_unit_coolers(
    load_tons=50,
    room_temp=35,
    suction_temp=25,
    room_length=100,
    room_width=50,
    room_height=20,
    defrost_type=DefrostType.ELECTRIC,
)

print(f"Number of units: {result.num_units}")
print(f"Capacity per unit: {result.capacity_per_unit_tons:.1f} tons")
print(f"Total CFM: {result.total_cfm:.0f}")
```

### Condenser Sizing

```python
from refrig_calc import CondenserCalculator

calc = CondenserCalculator()
result = calc.size_evaporative_condenser(
    refrigeration_tons=500,
    compressor_hp=750,
    condensing_temp=95,
    wet_bulb_temp=78,
)

print(f"Heat rejection: {result.heat_rejection_mbh:.0f} MBH")
print(f"Required capacity: {result.required_capacity_mbh:.0f} MBH")
print(f"Number of units: {result.num_units}")
```

### Expansion Device Sizing

```python
from refrig_calc import ExpansionDeviceCalculator, RefrigerantType

calc = ExpansionDeviceCalculator()
result = calc.size_txv(
    capacity_tons=50,
    refrigerant=RefrigerantType.NH3,
    liquid_temp=85,
    evaporator_temp=20,
    condensing_temp=95,
)

print(f"Selected TXV: {result.port_size}")
print(f"Pressure drop: {result.pressure_drop_psi:.0f} psi")
```

### Glycol System Design

```python
from refrig_calc import SecondaryRefrigerantCalculator, CoolantType

calc = SecondaryRefrigerantCalculator()

# Get required concentration
conc = calc.required_concentration(
    coolant_type=CoolantType.PROPYLENE_GLYCOL,
    lowest_temperature=20,
    safety_margin=10,
)
print(f"Required concentration: {conc}%")

# Get properties
props = calc.get_properties(
    coolant_type=CoolantType.PROPYLENE_GLYCOL,
    concentration=30,
    temperature=25,
)
print(f"Freeze point: {props.freeze_point}°F")
print(f"Specific heat: {props.specific_heat} BTU/lb-°F")

# Size system
result = calc.size_glycol_system(
    coolant_type=CoolantType.PROPYLENE_GLYCOL,
    capacity_tons=100,
    supply_temp=25,
    return_temp=35,
    pipe_length_ft=500,
)
print(f"Flow rate: {result.flow_rate_gpm:.0f} GPM")
print(f"Pump HP: {result.pump_hp:.1f}")
```

### Relief Valve Sizing

```python
from refrig_calc import ReliefValveSizer, RefrigerantRelief

sizer = ReliefValveSizer()
result = sizer.size_vessel_relief(
    vessel_volume_cuft=100,
    refrigerant=RefrigerantRelief.NH3,
    set_pressure_psig=250,
    vessel_diameter_in=48,
    vessel_length_in=120,
    insulation='insulated_2in',
)

print(f"Orifice: {result.selected_orifice}")
print(f"Inlet/Outlet: {result.inlet_size} x {result.outlet_size}")
print(f"Relieving capacity: {result.relieving_capacity_lb_hr:.0f} lb/hr")
```

### Pump Sizing

```python
from refrig_calc import PumpCalculator

calc = PumpCalculator()
result = calc.size_recirculation_pump(
    capacity_tons=200,
    recirculation_rate=4,
    suction_temp=-10,
    refrigerant="NH3",
    static_head_ft=15,
    pipe_length_ft=200,
)

print(f"Flow rate: {result.flow_rate_gpm:.0f} GPM")
print(f"Total head: {result.total_head_ft:.0f} ft")
print(f"Motor HP: {result.motor_hp}")
print(f"NPSH available: {result.npsh_available_ft:.1f} ft")
print(f"NPSH required: {result.npsh_required_ft:.1f} ft")
```

### Charge Calculation

```python
from refrig_calc import ChargeCalculator, VesselDimensions, VesselOrientation

calc = ChargeCalculator('NH3')
vessel = VesselDimensions(
    diameter=48,
    length=120,
    orientation=VesselOrientation.HORIZONTAL,
)

result = calc.vessel_charge(
    vessel=vessel,
    liquid_level_percent=80,
    temperature=95,
)

print(f"Liquid charge: {result.liquid_charge:.0f} lb")
print(f"Vapor charge: {result.vapor_charge:.0f} lb")
print(f"Total charge: {result.total_charge:.0f} lb")
```

### Machine Room Ventilation

```python
from refrig_calc import MachineRoomVentilation, RoomDimensions

room = RoomDimensions(width=40, length=60, height=20)
vent = MachineRoomVentilation()

result = vent.calculate(
    room=room,
    refrigerant_charge=5000,
    motor_hp_total=500,
    ambient_temp=95,
)

print(f"Emergency exhaust: {result.emergency_cfm:.0f} CFM")
print(f"Normal ventilation: {result.normal_cfm:.0f} CFM")
print(f"Air changes/hour: {result.air_changes_per_hour:.1f}")
```

### NH3 Release Analysis

```python
from refrig_calc import NH3ReleaseCalculator

calc = NH3ReleaseCalculator()
result = calc.iiar_flashing_release(
    hole_diameter_in=0.25,
    liquid_temp=95,
    liquid_pressure_psig=180,
)

print(f"Release rate: {result.vapor_release_rate:.2f} lb/min")
print(f"Required exhaust: {result.exhaust_cfm:.0f} CFM")
```

---

## Quick Functions

For rapid estimates without creating calculator objects:

```python
from refrig_calc import (
    quick_load_estimate,
    quick_evaporator_sizing,
    quick_heat_rejection,
    quick_txv_size,
    freeze_point,
    glycol_concentration_for_temp,
    quick_vessel_relief,
    quick_pump_hp,
    quick_release_rate,
)

# Load estimate (tons)
tons = quick_load_estimate(5000, 35, "storage")  # ft², °F, type

# Evaporator sizing
evap = quick_evaporator_sizing(50, 35)  # tons, room temp

# Heat rejection (MBH)
hr = quick_heat_rejection(100, 150)  # refrig tons, compressor HP

# TXV size
txv = quick_txv_size(25, "NH3")  # tons, refrigerant

# Glycol freeze point
fp = freeze_point("propylene_glycol", 30)  # type, concentration %

# Required glycol concentration
conc = glycol_concentration_for_temp("pg", 20)  # type, min temp °F

# Relief valve orifice
rv = quick_vessel_relief(100, 250, "NH3")  # ft³, psig, refrigerant

# Pump HP
hp = quick_pump_hp(100, 50)  # GPM, ft head
```

---

## Unit Conversions (utils module)

```python
from refrig_calc import utils

# Temperature
utils.f_to_c(95)        # 35°C
utils.c_to_f(0)         # 32°F

# Pressure
utils.psi_to_bar(100)   # 6.89 bar
utils.bar_to_psi(10)    # 145 psi

# Flow
utils.gpm_to_lpm(100)   # 378.5 LPM
utils.cfm_to_m3hr(1000) # 1699 m³/hr

# Power
utils.hp_to_kw(100)     # 74.6 kW
utils.tons_to_kw(100)   # 351.7 kW

# Refrigeration calculations
utils.refrigeration_effect(h_out=620, h_in=150)  # BTU/lb
utils.mass_flow_rate(capacity_btu=1200000, ref_effect=470)  # lb/hr
```

---

## Standards Compliance

- **IIAR** - International Institute of Ammonia Refrigeration
  - Bulletin 110 (Relief devices)
  - IIAR-2 (Equipment, design, installation)
  
- **ASHRAE** - American Society of Heating, Refrigerating and Air-Conditioning Engineers
  - Standard 15 (Safety standard for refrigeration systems)
  - Handbook - Refrigeration
  
- **ASME** - American Society of Mechanical Engineers
  - Boiler and Pressure Vessel Code
  
- **EPA** - Environmental Protection Agency
  - RMP (Risk Management Program)
  
- **NFPA** - National Fire Protection Association
  - NFPA 1 (Fire Code)

---

## Library Statistics

- **12 calculation modules**
- **81 exported functions/classes**
- **Zero external dependencies** (pure Python)
- **Complete type hints and docstrings**

---

## License

For professional engineering use. Verify all calculations with appropriate standards and qualified engineers.
