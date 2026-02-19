# Utility Drawing Extraction Report - Project 07609 (Freshpet)

**Date:** 2026-02-19
**Agent:** Extractor Agent (Claude Sonnet 4.5)
**Status:** INCOMPLETE - API Authentication Required

## Summary

Attempted to extract structured data from three Freshpet utility drawings. The extraction process was halted due to missing Anthropic API authentication. This report documents the extraction process, database schema, and next steps.

## Target Drawings

| Sheet ID | Drawing Number | Rev | File Path |
|----------|---------------|-----|-----------|
| 707 | U4361-ENLARGED-INTERSTITIAL-SPACE-UTILITIES-PLAN-AREA-6,-SECTOR-1 | 2 | `D:\qms\data\projects\07609-Freshpet\Utility\U4361-...-Rev.2.pdf` |
| 708 | U4362-ENLARGED-INTERSTITIAL-SPACE-UTILITIES-PLAN-AREA-6,-SECTOR-2 | 1 | `D:\qms\data\projects\07609-Freshpet\Utility\U4362-...-Rev.1.pdf` |
| 709 | U4364-ENLARGED-INTERSTITIAL-SPACE-UTILITIES-PLAN-AREA-6,-SECTOR-4 | 1 | `D:\qms\data\projects\07609-Freshpet\Utility\U4364-...-Rev.1.pdf` |

All files verified to exist on disk.

## Extraction Process

### 1. Drawing Classification
- **Type:** Utility Roof Plan (Interstitial Space)
- **Discipline:** Utility
- **Expected Content:**
  - Equipment schedules (RTUs, chillers, pumps, fans)
  - Piping connections and routing
  - Equipment locations and mounting details
  - Specifications and notes

### 2. Model Selection
- **Primary Model:** Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- **Rationale:** Moderate complexity utility drawings with equipment schedules
- **Alternative:** Opus 4.6 for shadow review if confidence < 0.7

### 3. Extraction Targets

#### Equipment Data (utility_equipment table)
The extraction would capture for each piece of equipment:

**Basic Information:**
- equipment_mark: Equipment designation (e.g., "RTU-1", "CH-1", "P-1")
- equipment_type: Type (RTU, Chiller, Condenser, Pump, Fan, etc.)
- location: Physical location or area designation
- qty: Quantity (default 1)

**Manufacturer & Specifications:**
- manufacturer: Manufacturer name
- model: Model number
- capacity: Capacity rating with units (e.g., "5 TON", "100 GPM")
- specifications: Spec section reference

**Physical Properties:**
- dimensions: Overall dimensions (L x W x H) with units
- weight_lbs: Dry/shipping weight
- operating_weight_lbs: Operating weight
- design_pressure: Design pressure rating (e.g., "250 PSIG")

**Power & Electrical:**
- power_voltage: Voltage rating (e.g., "460/3/60", "208V")
- power_hp: Motor horsepower rating

**HVAC/Process Parameters:**
- gpm: Flow rate in gallons per minute
- temperature_in: Inlet temperature (°F)
- temperature_out: Outlet temperature (°F)
- pressure_drop_psi: Pressure drop across equipment
- steam_pressure_psi: Steam pressure if applicable
- flow_rate_lbs_hr: Mass flow rate
- inlet_size: Inlet pipe/connection size
- outlet_size: Outlet pipe/connection size

**Additional Details:**
- notes: Installation requirements, mounting, clearances
- contact_info: Service contact or access requirements
- confidence: Extraction confidence score (0.0-1.0)

#### Piping Connections (extraction_notes table)
For visible piping connections:
- equipment_mark: Equipment tag
- pipe_type: Service type (CW, CHW, HW, Steam, Condensate, Refrigerant)
- pipe_size: Nominal pipe size (e.g., "2\"", "3/4\"")
- material: Pipe material (Cu, CS, SS)
- insulation: Insulation type/thickness
- location: Connection point or routing notes

### 4. Database Schema

**utility_equipment** (27 columns)
```sql
CREATE TABLE utility_equipment (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER NOT NULL,
    equipment_mark TEXT NOT NULL,
    equipment_type TEXT,
    location TEXT,
    manufacturer TEXT,
    model TEXT,
    capacity TEXT,
    design_pressure TEXT,
    dimensions TEXT,
    weight_lbs INTEGER,
    operating_weight_lbs INTEGER,
    power_voltage TEXT,
    power_hp REAL,
    qty INTEGER DEFAULT 1,
    gpm REAL,
    temperature_in REAL,
    temperature_out REAL,
    pressure_drop_psi REAL,
    steam_pressure_psi REAL,
    flow_rate_lbs_hr REAL,
    inlet_size TEXT,
    outlet_size TEXT,
    specifications TEXT,
    notes TEXT,
    contact_info TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sheet_id) REFERENCES sheets(id)
);
```

**extraction_notes** (5 columns)
```sql
CREATE TABLE extraction_notes (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER,
    note_type TEXT,  -- 'piping_connection', 'extraction_note', etc.
    description TEXT,
    confidence REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sheet_id) REFERENCES sheets(id)
);
```

### 5. Extraction Workflow

```python
from qms.pipeline.utility_extractor import extract_batch

# Extract data from sheets
sheet_ids = [707, 708, 709]
results = extract_batch(sheet_ids, model='sonnet', dry_run=False)

# Results stored in:
# - utility_equipment (equipment records)
# - extraction_notes (piping connections and notes)
# - sheets.extracted_at updated
# - sheets.extraction_model = 'sonnet'
# - sheets.quality_score = avg confidence
```

## Issues Encountered

### API Authentication Error
```
Error: "Could not resolve authentication method. Expected either api_key
or auth_token to be set. Or for one of the `X-Api-Key` or `Authorization`
headers to be explicitly omitted"
```

**Root Cause:** Anthropic API key not configured in environment

**Resolution Required:**
1. Set environment variable: `ANTHROPIC_API_KEY=<your-key>`
2. Or configure in application settings
3. Restart extraction process

### Extraction Status
```
Batch complete: 0 success, 0 partial, 3 failed (of 3 total)

Sheet 707: FAILED - 0 equipment, 0 piping (3.5s)
Sheet 708: FAILED - 0 equipment, 0 piping (1.2s)
Sheet 709: FAILED - 0 equipment, 0 piping (1.2s)
```

## Database Current State

Current extraction status from database:
```sql
SELECT id, drawing_number, extracted_at, quality_score
FROM sheets
WHERE id IN (707, 708, 709);
```

| ID  | Drawing Number | Extracted At | Quality Score |
|-----|---------------|--------------|---------------|
| 707 | U4361-...     | NULL         | NULL          |
| 708 | U4362-...     | NULL         | NULL          |
| 709 | U4364-...     | NULL         | NULL          |

No equipment or notes records exist for these sheets yet.

## Reference: Successful Extractions

Other utility drawings in project 07609 have been successfully extracted:

| Drawing Number | Rev | Model | Score | Equipment Count |
|---------------|-----|-------|-------|-----------------|
| U1301-UTILITY-OVERALL-INTERSTITIAL-FLOOR-PLAN | 2 | manual-vision | 0.70 | 5 |
| U1401-UTILITY-OVERALL-ROOF-PLAN | 2 | manual-vision | 0.70 | 2 |
| U4002-ENLARGED-EXISTING-INTERSTITIAL-SPACE-UTILITIES-PLAN-TIE-IN-TO-C.H.P.-BUILDING | 1 | sonnet-4.5 | 0.88 | 1 |
| U5004-UTILITY-DETAILS | 1 | sonnet | 0.93 | 3 |
| U5005-UTILITY-DETAILS | 1 | sonnet | 0.92 | 6 |

Example equipment extracted from U5005:
- EMERGENCY SHOWER (confidence: 0.95)
- EMERGENCY SHOWER EYEWASH (confidence: 0.95)
- EMERGENCY EYE/FACE WASH (confidence: 0.95)
- THERMOSTATIC MIXING VALVE (confidence: 0.92)

## Next Steps

1. **Configure API Authentication**
   - Set `ANTHROPIC_API_KEY` environment variable
   - Verify access to Claude API (Sonnet 4.5 or Opus 4.6)

2. **Re-run Extraction**
   ```bash
   python -c "
   from qms.pipeline.utility_extractor import extract_batch
   results = extract_batch([707, 708, 709], model='sonnet')
   "
   ```

3. **Validate Results**
   - Check equipment_count > 0 for each sheet
   - Verify confidence scores >= 0.7
   - Review extraction_notes for any flags

4. **Quality Assurance**
   - Compare extracted data against PDF visually
   - Verify equipment tags match drawing
   - Check capacity/voltage values are reasonable
   - Flag low-confidence items (< 0.6) for manual review

5. **Update Processing Queue**
   ```sql
   UPDATE processing_queue
   SET status = 'completed',
       completed_at = CURRENT_TIMESTAMP
   WHERE sheet_id IN (707, 708, 709)
     AND task = 'EXTRACT';
   ```

## Expected Output Format

After successful extraction, expect results like:
```
Extraction: U4361 Rev 2 (07609-Freshpet/Utility)
================================================
Drawing Type: Utility Roof Plan
Complexity: medium
Model Used: sonnet

Extracted:
- Equipment: 8-12 items (avg confidence: 0.85-0.92)
- Piping connections: 10-15 items (avg confidence: 0.80-0.88)
- Notes: 2-5 general observations

Quality Score: 0.85-0.90

Flagged for Review:
- [Any items with confidence < 0.7]
```

## Files & Locations

- **Extraction Code:** `D:\qms\pipeline\utility_extractor.py`
- **Database:** `D:\qms\data\quality.db`
- **Drawing Files:** `D:\qms\data\projects\07609-Freshpet\Utility\`
- **This Report:** `D:\qms\EXTRACTION_REPORT_07609_UTILITY.md`

## Codebase Architecture

The extraction system follows this flow:
```
1. extract_batch(sheet_ids)
   └─> For each sheet:
       ├─ Get sheet info from database
       ├─ Read PDF file from disk
       ├─ Encode PDF to base64
       ├─ Build extraction prompt (drawing-type specific)
       ├─ Call Claude API (_call_claude_vision)
       ├─ Parse JSON response
       ├─ Store results (_store_extraction)
       │   ├─ UPDATE sheets (extracted_at, quality_score)
       │   ├─ INSERT INTO utility_equipment
       │   └─ INSERT INTO extraction_notes
       └─ Return ExtractionResult

2. Database Tables Updated:
   - sheets.extracted_at = CURRENT_TIMESTAMP
   - sheets.extraction_model = 'sonnet'
   - sheets.quality_score = avg_confidence
   - utility_equipment (one row per equipment item)
   - extraction_notes (piping connections + general notes)
```

## Conclusion

The extraction infrastructure is in place and has been successfully used on 5 other utility drawings in the same project. The process is blocked only by API authentication. Once the API key is configured, the three target drawings can be processed in approximately 15-30 seconds total, yielding structured equipment and piping data for project 07609 Area 6 Sectors 1, 2, and 4.

---
**Agent:** Claude Sonnet 4.5 (Extractor)
**Report Generated:** 2026-02-19 17:57 UTC
