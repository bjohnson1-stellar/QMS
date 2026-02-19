# Refrigeration Drawing Extraction System

## Overview

The refrigeration extraction system extracts structured data from refrigeration plan drawings (P&IDs, plans, isometrics) and stores it in the QMS database for tracking, validation, and reporting.

## Components

### 1. Extractor Module
**File:** `pipeline/refrigeration_extractor.py`

Implements the extraction pipeline for refrigeration drawings:
- Vision-based PDF reading using Claude Sonnet
- Structured prompt for extracting lines, equipment, and instruments
- JSON response parsing and validation
- Database storage with confidence tracking

### 2. Database Schema

Three main tables for extracted data:

#### LINES Table
Stores refrigerant piping information:
- `line_number` - Line tag (LS-101, LD-202, LHG-301, etc.)
- `size` - Pipe diameter (2", 4", 6", etc.)
- `service` - Line service (SUCTION, DISCHARGE, LIQUID, HOT GAS, DEFROST)
- `material` - Pipe material spec (SCH 40 SMLS STL, SCH 80, etc.)
- `spec_class` - Specification class (NH3-A, etc.)
- `refrigerant` - Refrigerant type (NH3, R-507, R-404A, etc.)
- `from_location` - Start point or equipment connection
- `to_location` - End point or equipment connection
- `confidence` - Extraction confidence score (0.0-1.0)

#### EQUIPMENT Table
Stores refrigeration equipment:
- `tag` - Equipment tag (COMP-1, EVAP-101, COND-201, REC-1, etc.)
- `equipment_type` - Type (COMPRESSOR, EVAPORATOR, CONDENSER, RECEIVER, etc.)
- `description` - Equipment description or name
- `confidence` - Extraction confidence score

#### INSTRUMENTS Table
Stores instrumentation and control devices:
- `tag` - Instrument tag (PT-101, TT-202, LT-301, PSV-401, etc.)
- `instrument_type` - Type (PRESSURE TRANSMITTER, TEMPERATURE TRANSMITTER, etc.)
- `service` - Associated service or equipment
- `loop_number` - Control loop number
- `location` - Physical location
- `extraction_notes` - Additional notes or observations
- `confidence` - Extraction confidence score

## Extraction Process

### Step 1: Classify Drawing
```python
# Determine drawing type from drawing number
drawing_type = "Refrigeration Plan"
if "ISO" in drawing_number.upper():
    drawing_type = "Isometric"
elif "PLAN" in drawing_number.upper():
    drawing_type = "Refrigeration Plan"
elif "SECTION" in drawing_number.upper():
    drawing_type = "Section/Detail"
```

### Step 2: Read with Vision Model
```python
# Encode PDF to base64
pdf_base64 = _encode_pdf_for_vision(pdf_path)

# Build extraction prompt
prompt = _build_extraction_prompt(drawing_number, drawing_type)

# Call Claude vision API
response = _call_claude_vision(pdf_base64, prompt, model="sonnet")
```

### Step 3: Parse and Validate
```python
# Parse JSON response
data = _parse_extraction_response(response)

# Populate result
result.lines = data.get("lines", [])
result.equipment = data.get("equipment", [])
result.instruments = data.get("instruments", [])
result.confidence = data.get("confidence", 0.7)
```

### Step 4: Store in Database
```python
# Update sheet record
conn.execute("""
    UPDATE sheets
    SET extracted_at = CURRENT_TIMESTAMP,
        extraction_model = ?,
        quality_score = ?,
        complexity = ?
    WHERE id = ?
""", (model, confidence, complexity, sheet_id))

# Insert lines, equipment, instruments
# (See _store_extraction function for details)
```

## Line Number Parsing

Standard refrigerant line numbering conventions:

### Line Service Prefixes
- `LS` - Liquid Suction
- `LD` - Liquid Discharge
- `LHG` - Liquid Hot Gas
- `SR` - Suction Riser
- `DR` - Discharge Riser
- `DF` - Defrost

### Example Line Numbers
```
LS-101    → Liquid Suction line 101
LD-202    → Liquid Discharge line 202
LHG-301   → Liquid Hot Gas line 301
SR-404    → Suction Riser 404
```

## Equipment Tag Parsing

Standard equipment tag format: `TYPE-NUMBER`

### Equipment Type Prefixes
- `COMP` - Compressor
- `EVAP` - Evaporator / Unit Cooler
- `COND` - Condenser
- `REC` - Receiver
- `VES` - Pressure Vessel
- `PMP` - Pump

### Example Equipment Tags
```
COMP-1     → Compressor 1
EVAP-101   → Evaporator 101
COND-201   → Condenser 201
REC-1      → Receiver 1
```

## Instrument Tag Parsing

Standard instrument tag format: `MEASUREMENT-NUMBER`

### Instrument Type Prefixes
- `PT` - Pressure Transmitter
- `TT` - Temperature Transmitter
- `LT` - Level Transmitter
- `FT` - Flow Transmitter
- `PSV` - Pressure Safety Valve
- `PRV` - Pressure Relief Valve
- `PCV` - Pressure Control Valve
- `TCV` - Temperature Control Valve

### Example Instrument Tags
```
PT-101     → Pressure Transmitter 101
TT-202     → Temperature Transmitter 202
LT-301     → Level Transmitter 301
PSV-401    → Pressure Safety Valve 401
```

## Confidence Scoring

Confidence factors for extracted data:

| Factor | Impact |
|--------|--------|
| Clear text, high resolution | +0.2 |
| Standard format/nomenclature | +0.1 |
| Consistent with other data | +0.1 |
| Partial/unclear text | -0.2 |
| Non-standard format | -0.1 |
| Conflicting information | -0.2 |

Base confidence: 0.7
Range: 0.0 - 1.0

Items with confidence < 0.6 should be flagged for manual review.

## Usage Examples

### Extract Single Sheet
```python
from pathlib import Path
from qms.pipeline.refrigeration_extractor import extract_refrigeration_drawing

result = extract_refrigeration_drawing(
    sheet_id=595,
    pdf_path=Path("D:/qms/data/projects/07609-Freshpet/Refrigeration/R1310.1-Rev.1.pdf"),
    drawing_number="R1310.1-REFRIGERATION-PLAN-DUCT-FLOOR-OVERALL",
    model="sonnet",
    dry_run=False
)

print(f"Status: {result.status}")
print(f"Lines: {len(result.lines)}")
print(f"Equipment: {len(result.equipment)}")
print(f"Instruments: {len(result.instruments)}")
```

### Extract Batch
```python
from qms.pipeline.refrigeration_extractor import extract_batch

results = extract_batch(
    sheet_ids=[595, 596, 597],
    model="sonnet",
    dry_run=False
)

# Print summary
for r in results:
    print(f"{r.drawing_number}: {r.status} ({len(r.lines)} lines)")
```

## Model Selection

| Drawing Type | Model | Rationale |
|--------------|-------|-----------|
| Simple Plan | Sonnet | Moderate complexity, fast processing |
| Complex Plan | Sonnet | Many items, good balance speed/accuracy |
| Isometric | Sonnet | Detailed routing, weld information |
| Equipment Schedule | Haiku | Mainly tabular data |
| Title Block | Haiku | Simple text extraction |

## Error Handling

### Unreadable Area
- Note in extraction_notes
- Reduce confidence score
- Flag item for manual review

### Ambiguous Value
- Store best guess
- Mark with low confidence
- Add note describing ambiguity

### Missing Required Field
- Leave NULL in database
- Add validation note
- Flag for review

### Duplicate Tag
- Store both occurrences
- Create conflict record
- Alert for resolution

## Output Format

Example extraction summary:
```
Extraction: R1310.1 Rev 1 (07609-Freshpet/Refrigeration)
================================================
Drawing Type: Refrigeration Plan
Complexity: medium
Model Used: sonnet

Extracted:
- Lines: 12 (avg confidence: 0.89)
- Equipment: 8 (avg confidence: 0.93)
- Instruments: 15 (avg confidence: 0.87)

Flagged for Review:
- Line LS-??: Could not read line number (confidence: 0.45)
- Instrument PT-10?: Tag partially obscured (confidence: 0.55)

Quality Score: 0.88
Processing Time: 12.5s
```

## Requirements

### Python Dependencies
```bash
pip install anthropic>=0.25.0
```

### Environment Variables
```bash
# Set Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."  # Linux/Mac
setx ANTHROPIC_API_KEY "sk-ant-..."   # Windows
```

### Database Tables
Requires the following tables (created by schema migrations):
- `sheets` - Drawing metadata
- `lines` - Extracted refrigerant lines
- `equipment` - Extracted equipment
- `instruments` - Extracted instruments
- `extraction_notes` (optional) - Additional notes

## Integration Points

### With Pipeline Module
```python
# Add to pipeline/cli.py
@app.command()
def extract_refrigeration(
    sheet_ids: List[int],
    model: str = "sonnet",
    dry_run: bool = False
):
    """Extract data from refrigeration drawings."""
    from qms.pipeline.refrigeration_extractor import extract_batch
    results = extract_batch(sheet_ids, model, dry_run)
    # Print summary...
```

### With Projects Module
```python
# Query extracted data for a project
from qms.core import get_db

with get_db() as conn:
    lines = conn.execute("""
        SELECT l.* FROM lines l
        JOIN sheets s ON s.id = l.sheet_id
        JOIN projects p ON p.id = s.project_id
        WHERE p.number = '07609'
    """).fetchall()
```

### With Engineering Module
```python
# Validate extracted line sizes against calculations
from qms.engineering.validators import validate_line_sizing

validation = validate_line_sizing(
    project_number="07609",
    extracted_lines=lines
)
```

## Future Enhancements

### Phase 2: Advanced Extraction
- [ ] Extract valve specifications and sizing
- [ ] Extract weld requirements from isometrics
- [ ] Extract bill of materials
- [ ] Cross-reference with equipment schedules
- [ ] Detect and resolve conflicts across drawings

### Phase 3: Validation & QC
- [ ] Compare extracted data against engineering calculations
- [ ] Validate line sizes against ASHRAE/IIAR standards
- [ ] Check for missing instruments or safety devices
- [ ] Verify material specs against project specifications
- [ ] Flag non-standard configurations

### Phase 4: Reporting
- [ ] Generate line lists with materials
- [ ] Create instrument lists for procurement
- [ ] Produce equipment summaries by area
- [ ] Export to construction management systems
- [ ] Generate QA/QC checklists

## Related Documentation

- `.planning/extractor-agent.md` - General extraction agent design
- `pipeline/schema.sql` - Database schema definitions
- `engineering/validators.py` - Engineering validation rules
- `CLAUDE.md` - Main project documentation
