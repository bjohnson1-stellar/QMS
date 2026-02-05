# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`refrig_calc` is a pure Python library (zero external dependencies) for industrial refrigeration system design and analysis. Calculations are extracted from professional engineering spreadsheets and implement IIAR, ASHRAE, ASME, EPA, and NFPA standards.

**Python 3.8+ required.**

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run all tests
python -m pytest tests/test_refrig_calc.py -v

# Run single test
python -m pytest tests/test_refrig_calc.py::test_nh3_properties -v

# Run tests without pytest
python tests/test_refrig_calc.py

# Format code
black .

# Type checking
mypy *.py

# Run example
python examples/complete_system_analysis.py
```

## Architecture

### Module Pattern

Each calculation module follows a consistent structure:
1. **Calculator class** - Full calculation methods (e.g., `LineSizing`, `ChargeCalculator`)
2. **Result dataclass** - Structured output (e.g., `LineSizingResult`, `ChargeResult`)
3. **Enum types** - Configuration options (e.g., `DefrostType`, `VesselOrientation`)
4. **Quick functions** - Simplified wrappers for estimates (e.g., `quick_load_estimate()`)
5. **Data tables** - Embedded lookup data (e.g., `PIPE_DATA`, `PRODUCT_DATA`)

### Properties Module (properties.py)

Core thermodynamic data provider using table interpolation:
- Base class: `RefrigerantProperties` with `_temp_table`/`_press_table` lookups
- Implementations: `NH3Properties`, `CO2Properties`, `R22Properties`, `R404aProperties`, `R449AProperties`, `R507Properties`
- Factory: `get_refrigerant('NH3')` returns appropriate class (accepts aliases like 'R717')

### Naming Conflict

Two `RoomDimensions` classes exist:
- `RoomDimensions` - from ventilation module (for machine rooms)
- `LoadRoomDimensions` - from loads module (for cold storage rooms)

Import the correct one based on your calculation type.

### Unexported Modules

These modules are complete but not yet in `__init__.py` exports:

| Module | Purpose | Source Spreadsheet |
|--------|---------|-------------------|
| `pipe_stress.py` | Hoop stress, branch reinforcement per ASME B31.5 | Pipe_Hoop_Stress_Calculation.xlsx |
| `pipe_supports.py` | Pipe weights, support stands, slope calcs | PipeWeights.xlsx, Stand_Worksheet*.xlsx |
| `room_load.py` | Detailed room load calcs per ASHRAE | Room_Load1.xlsm |
| `safety_relief_valve.py` | Extended SRV sizing (IIAR-2, ASHRAE 15, CMC) | SRV7.7.xlsm |
| `utility_calcs.py` | Underfloor warming, sump tanks, N2 purge | Underfloor_Warming_Template.xlsx |
| `vertical_riser.py` | Suction riser sizing with oil return | Vertical_Suction_Sizing_VPS.xls |

Import directly: `from refrig_calc.pipe_stress import PipeStressCalculator`

## Units

All calculations use **US/Imperial units**:
- Temperature: °F
- Pressure: psia/psig
- Length: feet/inches
- Mass: lb
- Flow: GPM, CFM
- Capacity: tons (refrigeration), BTU/hr
- Power: HP

Conversions available in `utils` module (e.g., `utils.f_to_c()`, `utils.psi_to_bar()`).

## Testing

Tests validate against **engineering-reasonable ranges** rather than exact values:
```python
assert 30 < props.pressure_psia < 35  # Not exact due to interpolation tolerances
```

This reflects acceptable tolerances in thermodynamic calculations.

## Standards Reference

| Standard | Usage |
|----------|-------|
| IIAR Bulletin 110 | Relief valve sizing |
| IIAR-2 | Equipment design, machine room ventilation |
| ASHRAE 15 | Refrigeration safety |
| ASHRAE Handbook - Refrigeration | Property data, load calculations |
| ASME B31.5 | Refrigeration piping, stress, supports |
| ASME BPVC | Pressure vessel requirements |

Preserve standards compliance when modifying calculations.

## Known Issues

- Version mismatch: `setup.py` shows 1.0.0, `__init__.py` shows 2.0.0
