# Support Plan Extraction Report - Sheets 119-121
## Project 07308-BIRDCAGE

### Status: Ready for Execution

---

## Sheets Queued for Extraction

| Sheet ID | Drawing Number | Revision | File Path |
|----------|---------------|----------|-----------|
| 119 | RS13040-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-4 | 6 | D:/Projects/07308-BIRDCAGE/Refrigeration/RS13040-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-4-Rev.6.pdf |
| 120 | RS13050-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-5 | 6 | D:/Projects/07308-BIRDCAGE/Refrigeration/RS13050-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-5-Rev.6.pdf |
| 121 | RS13060-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-6 | 6 | D:/Projects/07308-BIRDCAGE/Refrigeration/RS13060-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-6-Rev.6.pdf |

**File Status**: All PDFs verified and accessible (317KB, 297KB, 285KB)

---

## Extraction Script Prepared

**Script Location**: `D:/extract_supports_119_121.py`

### What It Does

1. **Reads PDF drawings** using Claude's document understanding capability
2. **Extracts support data**:
   - Individual support tags (RS-101, RS-102, etc.)
   - Support types (hanger, guide, anchor, spring)
   - Detail references
   - Grid locations
   - Pipe sizes
   - Special notes

3. **Extracts typical details**:
   - Detail labels
   - Support type descriptions
   - Member types and sizes (angle, channel, rod)
   - Load capacities
   - Dimensions and specifications

4. **Stores in database**: Inserts into `support_details` table
5. **Updates sheet metadata**: Sets extraction timestamp, model, quality score, drawing type

### Database Schema

The `support_details` table structure:
```sql
CREATE TABLE support_details (
    id INTEGER PRIMARY KEY, 
    sheet_id INTEGER REFERENCES sheets(id), 
    detail_type TEXT,           -- trapeze_hanger, hanger, clamp, etc.
    detail_label TEXT,          -- Support tag/mark
    member_type TEXT,           -- angle, channel, rod, beam
    member_size TEXT,           -- L4x4x1/4, C6x8.2, 3/4" rod
    max_load_lbs INTEGER,       -- Load capacity
    width_or_span_ft REAL,      -- Span or width dimension
    rod_size TEXT,              -- Rod diameter
    back_to_back TEXT,          -- Back-to-back configuration
    notes TEXT,                 -- Location, detail reference, notes
    confidence REAL DEFAULT 1.0 -- Extraction confidence (0.0-1.0)
)
```

---

## Requirements to Run

### API Key Required

The extraction script requires an Anthropic API key to call Claude for document analysis.

**Set the API key before running**:

```powershell
# PowerShell
$env:ANTHROPIC_API_KEY = 'your-api-key-here'

# CMD
set ANTHROPIC_API_KEY=your-api-key-here

# Linux/Mac
export ANTHROPIC_API_KEY='your-api-key-here'
```

### Python Dependencies

```bash
pip install anthropic sqlite3
```

---

## How to Run

```bash
cd D:/
python extract_supports_119_121.py
```

---

## Expected Output

```
================================================================================
EXTRACTOR AGENT - REFRIGERATION SUPPORT PLAN EXTRACTION
================================================================================
Project: 07308-BIRDCAGE
Drawing Type: Refrigeration Support Plans - Interstitial Areas 4-6
Model: claude-sonnet-4-20250514
Sheets to process: 3

Processing: RS13040-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-4
File: D:/Projects/07308-BIRDCAGE/Refrigeration/RS13040-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-4-Rev.6.pdf
  Extracted X supports, Y typical details
  Quality Score: 0.XX
  Tokens: X,XXX in / X,XXX out

Processing: RS13050-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-5
...

================================================================================
EXTRACTION COMPLETE
================================================================================
Total Supports Extracted: XX
Total Typical Details: XX
Total Input Tokens: XX,XXX
Total Output Tokens: X,XXX

Database: D:/quality.db

Details by Sheet:
  Sheet 119 (RS13040-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-4): XX items
  Sheet 120 (RS13050-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-5): XX items
  Sheet 121 (RS13060-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-6): XX items
```

---

## Database Updates

After successful extraction:

### support_details table
- New rows inserted with support tags and typical details
- Each entry linked to sheet_id
- Confidence scores assigned based on clarity

### sheets table
- `extracted_at`: Set to current timestamp
- `extraction_model`: Set to "claude-sonnet-4-20250514"
- `quality_score`: Overall extraction quality (0.0-1.0)
- `drawing_type`: Set to "support_plan"
- `complexity`: Set to "medium"

---

## Verification Queries

After extraction, verify the data:

```sql
-- Count support details by sheet
SELECT 
    s.id, 
    s.drawing_number, 
    COUNT(sd.id) as support_count
FROM sheets s
LEFT JOIN support_details sd ON sd.sheet_id = s.id
WHERE s.id IN (119, 120, 121)
GROUP BY s.id;

-- View extracted supports for sheet 119
SELECT 
    detail_type,
    detail_label,
    member_type,
    member_size,
    max_load_lbs,
    notes,
    confidence
FROM support_details
WHERE sheet_id = 119
ORDER BY detail_label;

-- Check sheet metadata updates
SELECT 
    id,
    drawing_number,
    extracted_at,
    extraction_model,
    quality_score,
    drawing_type,
    complexity
FROM sheets
WHERE id IN (119, 120, 121);
```

---

## Troubleshooting

### API Key Not Set
```
ERROR: ANTHROPIC_API_KEY environment variable not set
```
**Solution**: Set the API key in your environment as shown above

### File Not Found
```
ERROR: File not found: [path]
```
**Solution**: Verify the file path in the database matches the actual file location

### Database Locked
```
database is locked (5)
```
**Solution**: Close any other programs accessing the database, or wait a moment and retry

### JSON Parse Error
```
ERROR: No JSON found in response
```
**Solution**: Check the PDF is readable. Claude may have returned text explanation instead of JSON. Review the raw response.

---

## Next Steps

1. **Set API Key**: Configure your Anthropic API key in the environment
2. **Run Script**: Execute `python extract_supports_119_121.py`
3. **Verify Results**: Use the verification queries above to check extracted data
4. **Review Quality**: Check confidence scores and quality_score values
5. **Manual Review**: For low-confidence items, manually verify against PDFs

---

## Model Selection

**Using Claude Sonnet 4** for these drawings because:
- Support plan drawings have moderate complexity
- Need to identify support tags in plan view
- Need to extract typical detail callouts and specifications
- Balance between accuracy and cost
- Good at structured data extraction from technical drawings

---

**Report Generated**: 2026-02-05
**Database**: D:/quality.db
**Script**: D:/extract_supports_119_121.py
