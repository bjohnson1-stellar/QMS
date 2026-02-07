# Support Plan Extraction Report
## Project 07308-BIRDCAGE - Sheets 125-127

**Date:** 2026-02-05
**Extractor Agent:** Claude Sonnet 4.5
**Status:** READY FOR EXTRACTION

---

## Target Sheets

### Sheet 125
- **Drawing Number:** RS14010-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-1
- **Revision:** 5
- **File Path:** D:\Projects\07308-BIRDCAGE\Refrigeration\RS14010-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-1-Rev.5.pdf
- **Type:** Support Plan Drawing (Roof Area)
- **Status:** Pending Extraction

### Sheet 126
- **Drawing Number:** RS14020-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-2
- **Revision:** 5
- **File Path:** D:\Projects\07308-BIRDCAGE\Refrigeration\RS14020-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-2-Rev.5.pdf
- **Type:** Support Plan Drawing (Roof Area)
- **Status:** Pending Extraction

### Sheet 127
- **Drawing Number:** RS14030-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-3
- **Revision:** 5
- **File Path:** D:\Projects\07308-BIRDCAGE\Refrigeration\RS14030-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-3-Rev.5.pdf
- **Type:** Support Plan Drawing (Roof Area)
- **Status:** Pending Extraction

---

## Extraction Requirements

### Data to Extract

#### 1. Individual Support Tags (from plan view)
For each support marker shown on the drawing:
- Support tag/mark (e.g., RS-101, RS-102, etc.)
- Support type if indicated
- Detail reference (e.g., "Detail A", "Typ. Det. 1")
- Location/grid reference
- Pipe size supported
- Special notes or annotations

**Storage:** Insert into `support_details` table with:
- `sheet_id`: 125, 126, or 127
- `detail_type`: Support type
- `detail_label`: Support tag
- `member_size`: Pipe size
- `notes`: Location, detail reference, and other notes combined
- `confidence`: 0.0-1.0 based on clarity

#### 2. Typical Support Details (from detail callouts)
For each typical support detail shown:
- Detail label/number
- Support type description
- Structural member type (angle, channel, threaded rod, etc.)
- Member size (L2x2x1/4, 3/4" rod, etc.)
- Load capacity if shown
- Dimensional requirements
- Material specifications

**Storage:** Insert into `support_details` table with:
- `sheet_id`: 125, 126, or 127
- `detail_type`: Support category
- `detail_label`: Detail identifier
- `member_type`: Structural member type
- `member_size`: Size specification
- `max_load_lbs`: Load capacity if available
- `notes`: Additional specifications
- `confidence`: 0.0-1.0 based on clarity

---

## Extraction Script

**Location:** D:/extract_supports.py

**Note:** The script requires the ANTHROPIC_API_KEY environment variable to be set for API access.

### To run the extraction:

```bash
# Set API key (Windows)
set ANTHROPIC_API_KEY=your_key_here

# Run extraction
cd D:/
python extract_supports.py
```

### Current Script Configuration:
- **Target Sheets:** 119, 120, 121 (modified by user)
- **Model:** claude-sonnet-4-20250514
- **Max Tokens:** 16,000
- **Database:** D:/quality.db

### To extract sheets 125-127:
Update line 19 in extract_supports.py:
```python
SHEET_IDS = [125, 126, 127]
```

And update line 244:
```python
print(f"Drawing Type: Refrigeration Support Plans - Roof Areas")
```

And update line 303:
```python
WHERE s.id IN (125, 126, 127)
```

---

## Database Schema

### support_details Table

```sql
CREATE TABLE support_details (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    detail_type TEXT,           -- Support category
    detail_label TEXT,          -- Tag or detail identifier
    member_type TEXT,           -- Structural member type
    member_size TEXT,           -- Size specification
    max_load_lbs INTEGER,       -- Load capacity
    width_or_span_ft REAL,      -- Dimensional info
    rod_size TEXT,              -- Rod diameter if applicable
    back_to_back TEXT,          -- Y/N for back-to-back config
    notes TEXT,                 -- Additional specifications
    confidence REAL DEFAULT 1.0 -- Extraction confidence
);
```

---

## Expected Outputs

### Per Sheet:
- Support tags extracted: 20-50 (estimated)
- Typical details extracted: 5-15 (estimated)
- Average confidence: > 0.85 (target)
- Quality score: > 0.80 (target)

### Database Updates:
1. Insert support_details records for each sheet
2. Update sheets table:
   - `extracted_at`: Timestamp
   - `extraction_model`: "claude-sonnet-4-20250514"
   - `quality_score`: Overall extraction quality
   - `drawing_type`: "support_plan"
   - `complexity`: "medium"

### Console Output Example:
```
================================================================================
EXTRACTOR AGENT - REFRIGERATION SUPPORT PLAN EXTRACTION
================================================================================
Project: 07308-BIRDCAGE
Drawing Type: Refrigeration Support Plans - Roof Areas
Model: claude-sonnet-4-20250514
Sheets to process: 3

Processing: RS14010-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-1
File: D:\Projects\07308-BIRDCAGE\Refrigeration\RS14010-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-1-Rev.5.pdf
  ✓ Extracted 42 supports, 8 typical details
  Quality Score: 0.87
  Tokens: 12,543 in / 2,156 out

[... similar for sheets 126, 127 ...]

================================================================================
EXTRACTION COMPLETE
================================================================================
Total Supports Extracted: 126
Total Typical Details: 24
Total Input Tokens: 37,629
Total Output Tokens: 6,468

Database: D:/quality.db

Details by Sheet:
  Sheet 125 (RS14010-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-1): 50 items
  Sheet 126 (RS14020-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-2): 53 items
  Sheet 127 (RS14030-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-3): 47 items
```

---

## Verification Queries

After extraction, verify results with:

```sql
-- Count by sheet
SELECT
    s.drawing_number,
    COUNT(sd.id) as total_details,
    AVG(sd.confidence) as avg_confidence
FROM sheets s
LEFT JOIN support_details sd ON sd.sheet_id = s.id
WHERE s.id IN (125, 126, 127)
GROUP BY s.id
ORDER BY s.id;

-- View sample data
SELECT
    s.drawing_number,
    sd.detail_label,
    sd.detail_type,
    sd.member_type,
    sd.member_size,
    sd.max_load_lbs,
    sd.notes,
    sd.confidence
FROM support_details sd
JOIN sheets s ON s.id = sd.sheet_id
WHERE s.id IN (125, 126, 127)
ORDER BY s.id, sd.detail_label
LIMIT 20;

-- Check extraction metadata
SELECT
    id,
    drawing_number,
    extracted_at,
    extraction_model,
    quality_score,
    drawing_type,
    complexity
FROM sheets
WHERE id IN (125, 126, 127);
```

---

## Next Steps

1. **Set API Key:** Configure ANTHROPIC_API_KEY environment variable
2. **Update Script:** Modify sheet IDs to [125, 126, 127] if needed
3. **Run Extraction:** Execute `python D:/extract_supports.py`
4. **Verify Results:** Run verification queries
5. **Review Flags:** Check any low-confidence extractions

---

## Notes

- The extraction script uses Claude Sonnet 4 for optimal balance of speed and accuracy
- Support plan drawings are classified as "medium" complexity
- Expected quality score: 0.80-0.90
- Typical extraction time: 2-3 minutes per sheet
- Token usage: ~12,000-15,000 input tokens per sheet

---

## Related Sheets

Similar support plan drawings in the same project:
- Sheets 119-124: Interstitial Area Support Plans (RS13040-RS13100)
- Sheets 125-127: Roof Area Support Plans (RS14010-RS14030) **[THESE SHEETS]**

These drawings follow the same format and extraction approach.
