---
module: engineering
cli_name: eng
status: Complete
commands: [history, line-sizing, relief-valve, pump, ventilation, charge, validate-pipes, validate-relief]
depends_on: [core, projects]
depended_by: []
tables: [eng_calculations, eng_validations]
api_blueprint: "-"
source_dir: engineering/
schema_file: engineering/schema.sql
tags: [qms-module, calculations]
created: 2026-02-10
updated: 2026-02-10
---

# Engineering

Performs **industrial refrigeration engineering calculations** and validates drawing extractions against calculated values. Specialized for NH3 (ammonia) refrigeration systems.

## Architecture

- Uses a **Strategy pattern** with `DisciplineCalculator` (ABC) as the base class
- `RefrigerationCalculator` is the primary implementation
- Vendored `refrig_calc` package (20 modules) provides NH3 thermodynamic properties
- Validation compares [[pipeline]]-extracted values against calculations with configurable tolerances

## CLI Commands

| Command | Description |
|---------|-------------|
| `qms eng history [--limit 20]` | Show recent calculation history |
| `qms eng line-sizing` | Size refrigerant suction/discharge/liquid lines |
| `qms eng relief-valve` | Size pressure relief valves per IIAR/ASME |
| `qms eng pump` | Size refrigerant recirculation pumps |
| `qms eng ventilation` | Calculate machine room ventilation requirements |
| `qms eng charge` | Calculate refrigerant charge for a component |
| `qms eng validate-pipes <project>` | Validate pipe sizing against calculations |
| `qms eng validate-relief <project>` | Validate relief valve sizing against calculations |

## Database Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `eng_calculations` | Calculation audit trail | discipline, calculation_type, input_json, output_json, project_id, equipment_tag, line_number |
| `eng_validations` | Drawing vs calculation comparison | calculation_id, extracted_value, calculated_value, deviation_pct, status |

## Key Functions

| Function | Location | Description |
|----------|----------|-------------|
| `DisciplineCalculator` | `engineering/calculator.py` | ABC base class for calculators |
| `RefrigerationCalculator` | `engineering/refrigeration.py` | NH3 calculation implementation |
| `run_line_sizing(params)` | `engineering/` | Line sizing calculation |
| `run_relief_valve(params)` | `engineering/` | Relief valve sizing per IIAR/ASME |
| `run_pump(params)` | `engineering/` | Pump sizing calculation |
| `validate_pipe_sizing()` | `engineering/` | Compare drawing vs calculated pipe sizes |
| `validate_relief_valves()` | `engineering/` | Compare drawing vs calculated relief valves |

## Dependencies

### Depends On
- [[core]] — Database, logging
- [[projects]] — Project lookups for validation

### Depended By
None — leaf module in the dependency graph.

## Related Notes
- [[pipeline]] — Provides extracted drawing data for validation
- [[Architecture Overview]] — Calculation validation flow
