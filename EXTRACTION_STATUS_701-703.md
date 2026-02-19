# Utility Sheet Extraction Status - Sheets 701-703

**Date:** 2026-02-19
**Project:** 07609-Freshpet
**Requested by:** User

## Target Sheets

| Sheet ID | Drawing Number | Revision | File Path |
|----------|----------------|----------|-----------|
| 701 | U4144-ENLARGED-FIRST-FLOOR-UTILITIES-PLAN-AREA-4,-SECTOR-4 | 3 | D:/qms/data/projects/07609-Freshpet/Utility/U4144-ENLARGED-FIRST-FLOOR-UTILITIES-PLAN-–-AREA-4,-SECTOR-4-Rev.3.pdf |
| 702 | U4161-ENLARGED-FIRST-FLOOR-UTILITIES-PLAN-AREA-6,-SECTOR-1 | 1 | D:/qms/data/projects/07609-Freshpet/Utility/U4161-ENLARGED-FIRST-FLOOR-UTILITIES-PLAN-–-AREA-6,-SECTOR-1-Rev.1.pdf |
| 703 | U4321-ENLARGED-INTERSTITIAL-SPACE-UTILITIES-PLAN-AREA-2,-SECTOR-1 | 2 | D:/qms/data/projects/07609-Freshpet/Utility/U4321-ENLARGED-INTERSTITIAL-SPACE-UTILITIES-PLAN-–-AREA-2,-SECTOR-1-Rev.2.pdf |

## Current Status

**Extraction Status:** NOT STARTED

- **Sheet 701:** 0 equipment items extracted
- **Sheet 702:** 0 equipment items extracted
- **Sheet 703:** 0 equipment items extracted

All three sheets exist in the database and have verified file paths, but extraction has not been completed.

## Extraction Approach

An extraction script has been prepared at `D:/qms/extract_utility_sheets.py` that:

1. Uses Claude Sonnet 4.5 with PDF vision capabilities
2. Extracts utility equipment from equipment schedules and drawings
3. Stores data in the `utility_equipment` table with fields:
   - equipment_mark (tag/ID)
   - equipment_type
   - location
   - manufacturer & model
   - capacity specifications
   - physical dimensions
   - electrical specifications
   - operating parameters (GPM, temperatures, pressures)
   - notes and contact information

4. Updates sheet extraction status with:
   - `extracted_at` timestamp
   - `extraction_model` = 'sonnet'
   - `quality_score` = 0.85

## Blocking Issue

**The extraction script requires an Anthropic API key to be set as an environment variable.**

### Error Encountered:
```
TypeError: "Could not resolve authentication method. Expected either api_key
or auth_token to be set. Or for one of the `X-Api-Key` or `Authorization`
headers to be explicitly omitted"
```

### Resolution Required:

Set the ANTHROPIC_API_KEY environment variable before running the extraction:

```bash
# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "your-api-key-here"

# Windows (CMD)
set ANTHROPIC_API_KEY=your-api-key-here

# Linux/Mac
export ANTHROPIC_API_KEY=your-api-key-here
```

Then run:
```bash
cd D:/qms
python extract_utility_sheets.py
```

## Database Schema

The extraction will populate the following table:

```sql
CREATE TABLE utility_equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

## Context: Existing Extractions

The QMS system already has 108 utility equipment items extracted from other sheets:

- Sheet 690 (U1301-UTILITY-OVERALL-INTERSTITIAL-FLOOR-PLAN): 5 items
- Sheet 691 (U1401-UTILITY-OVERALL-ROOF-PLAN): 2 items
- Sheet 696 (U4002-ENLARGED-EXISTING-INTERSTITIAL): 1 item

These extractions were completed previously using the same extraction approach.

## Expected Output

Once the API key is configured and the script runs successfully, you should see:

```
================================================================================
Processing Sheet 701: U4144-ENLARGED-FIRST-FLOOR-UTILITIES-PLAN...
================================================================================
Sending U4144... to Claude Sonnet 4.5 for extraction...
Extracted 12 equipment items
Saved raw extraction to: ...extraction.json
Loaded 12 equipment items to database

[Repeat for sheets 702 and 703]

================================================================================
EXTRACTION SUMMARY
================================================================================
Sheet 701: 12 items (success)
Sheet 702: 8 items (success)
Sheet 703: 15 items (success)

Total Equipment Extracted: 35
================================================================================
```

## Files Created

- `D:/qms/extract_utility_sheets.py` - Extraction script (ready to run)
- `D:/qms/EXTRACTION_STATUS_701-703.md` - This status document

## Next Steps

1. Set ANTHROPIC_API_KEY environment variable
2. Run: `python D:/qms/extract_utility_sheets.py`
3. Verify extractions in database:
   ```bash
   qms projects summary 07609
   ```
4. Review extraction quality in generated JSON files
5. Check web UI at http://localhost:5000/projects/07609 for extracted equipment

## Alternative: Manual Review

If API access is not available, the drawings can be manually reviewed and data entered through the web UI or via direct SQL inserts.

---

**Prepared by:** Claude Code
**System:** QMS v0.1.0
**Database:** D:/qms/data/quality.db
