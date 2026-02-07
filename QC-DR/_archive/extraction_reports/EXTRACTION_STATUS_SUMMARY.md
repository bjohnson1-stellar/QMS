# Extraction Status Summary
## Project 07308-BIRDCAGE Support Plan Drawings

**Generated:** 2026-02-05
**Database:** D:/quality.db

---

## Requested Extraction: Sheets 125-127

### Current Status: NOT EXTRACTED

| Sheet ID | Drawing Number | Rev | File Path | Status |
|----------|---------------|-----|-----------|--------|
| 125 | RS14010-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-1 | 5 | D:\Projects\07308-BIRDCAGE\Refrigeration\RS14010-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-1-Rev.5.pdf | Pending |
| 126 | RS14020-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-2 | 5 | D:\Projects\07308-BIRDCAGE\Refrigeration\RS14020-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-2-Rev.5.pdf | Pending |
| 127 | RS14030-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-3 | 5 | D:\Projects\07308-BIRDCAGE\Refrigeration\RS14030-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-3-Rev.5.pdf | Pending |

**Total Details Currently in Database:** 0

---

## Prerequisites for Extraction

### 1. API Key Configuration
The extraction script requires the Anthropic API key to be configured:

**Windows:**
```cmd
set ANTHROPIC_API_KEY=your_api_key_here
```

**PowerShell:**
```powershell
$env:ANTHROPIC_API_KEY="your_api_key_here"
```

**Permanent (System Environment Variable):**
1. Open System Properties > Advanced > Environment Variables
2. Add new User or System variable:
   - Name: `ANTHROPIC_API_KEY`
   - Value: `your_api_key_here`

### 2. Python Dependencies
Ensure all required packages are installed:
```bash
pip install anthropic sqlite3
```

### 3. File Access
Verify PDF files are accessible:
```cmd
dir "D:\Projects\07308-BIRDCAGE\Refrigeration\RS14*Rev.5.pdf"
```

---

## Extraction Script Configuration

**Script Location:** D:/extract_supports.py

### Current Configuration (Modified by User):
```python
SHEET_IDS = [119, 120, 121]  # Interstitial Areas 4-6
```

### Required Changes for Sheets 125-127:

**Line 19:** Update sheet IDs
```python
SHEET_IDS = [125, 126, 127]  # Roof Areas 1-3
```

**Line 244:** Update description
```python
print(f"Drawing Type: Refrigeration Support Plans - Roof Areas 1-3")
```

**Line 303:** Update query filter
```python
WHERE s.id IN (125, 126, 127)
```

---

## Execution Steps

### Step 1: Configure API Key
```cmd
set ANTHROPIC_API_KEY=your_key_here
```

### Step 2: Update Script Configuration
Edit D:/extract_supports.py with the changes noted above, or create a separate script for sheets 125-127.

### Step 3: Run Extraction
```cmd
cd D:/
python extract_supports.py
```

### Step 4: Verify Results
```sql
-- Check extraction status
SELECT id, drawing_number, extracted_at, quality_score
FROM sheets
WHERE id IN (125, 126, 127);

-- Count extracted details
SELECT s.id, s.drawing_number, COUNT(sd.id) as detail_count
FROM sheets s
LEFT JOIN support_details sd ON sd.sheet_id = s.id
WHERE s.id IN (125, 126, 127)
GROUP BY s.id;
```

---

## Expected Results

### Extraction Metrics:
- **Processing Time:** 2-3 minutes per sheet (6-9 minutes total)
- **Support Tags per Sheet:** 20-50 (estimated)
- **Typical Details per Sheet:** 5-15 (estimated)
- **Total Items Expected:** 75-195
- **Target Quality Score:** > 0.80
- **Target Confidence:** > 0.85

### Database Changes:
1. **support_details table:**
   - INSERT 75-195 new records
   - Tags linked to sheet_id 125, 126, 127

2. **sheets table updates:**
   - `extracted_at`: Current timestamp
   - `extraction_model`: "claude-sonnet-4-20250514"
   - `quality_score`: 0.80-0.95
   - `drawing_type`: "support_plan"
   - `complexity`: "medium"

---

## Data Structure

### Support Tags (Plan View Markers)
Stored in `support_details` with:
- `sheet_id`: 125, 126, or 127
- `detail_type`: Support type (hanger, guide, anchor, etc.)
- `detail_label`: Support tag (RS-101, RS-102, etc.)
- `member_size`: Pipe size supported
- `notes`: "Location: [grid], Detail: [ref], [other notes]"
- `confidence`: 0.0-1.0

### Typical Support Details (Detail Callouts)
Stored in `support_details` with:
- `sheet_id`: 125, 126, or 127
- `detail_type`: Support category
- `detail_label`: Detail identifier
- `member_type`: Structural member (angle, channel, rod)
- `member_size`: Size spec (L2x2x1/4, 3/4" rod, etc.)
- `max_load_lbs`: Capacity rating
- `notes`: Additional specifications
- `confidence`: 0.0-1.0

---

## Troubleshooting

### Issue: "ANTHROPIC_API_KEY environment variable not set"
**Solution:** Set the environment variable as shown in Prerequisites section

### Issue: "File not found"
**Solution:** Verify PDF paths:
```cmd
dir "D:\Projects\07308-BIRDCAGE\Refrigeration\RS14*.pdf"
```

### Issue: "No JSON found in response"
**Solution:** This indicates the PDF may not have extracted properly. Check:
1. PDF is not corrupted
2. PDF contains readable text (not scanned images)
3. Model has sufficient context (increase max_tokens if needed)

### Issue: Low confidence scores
**Solution:** Review flagged items manually:
```sql
SELECT * FROM support_details
WHERE sheet_id IN (125, 126, 127)
AND confidence < 0.6
ORDER BY confidence;
```

---

## Alternative: Manual Extraction Template

If automated extraction cannot be completed, use this template for manual entry:

```python
# Manual extraction template for Sheet 125
sheet_125_supports = [
    {
        'sheet_id': 125,
        'detail_type': 'hanger',
        'detail_label': 'RS-101',
        'member_size': '6"',
        'notes': 'Location: Grid A-1, Detail: A',
        'confidence': 1.0
    },
    # ... continue for all visible support tags
]

# Typical details
sheet_125_details = [
    {
        'sheet_id': 125,
        'detail_type': 'adjustable_hanger',
        'detail_label': 'Detail A',
        'member_type': 'threaded_rod',
        'member_size': '3/4"',
        'max_load_lbs': 1000,
        'notes': 'For 4" to 8" pipe',
        'confidence': 1.0
    },
    # ... continue for all typical details
]
```

Then insert using:
```python
import sqlite3
conn = sqlite3.connect('D:/quality.db')
cursor = conn.cursor()

for item in sheet_125_supports + sheet_125_details:
    cursor.execute("""
        INSERT INTO support_details
        (sheet_id, detail_type, detail_label, member_type, member_size,
         max_load_lbs, notes, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item['sheet_id'],
        item['detail_type'],
        item['detail_label'],
        item.get('member_type'),
        item.get('member_size'),
        item.get('max_load_lbs'),
        item['notes'],
        item['confidence']
    ))

conn.commit()
conn.close()
```

---

## Summary

**Ready to Extract:** Yes, with API key configuration
**Script Available:** D:/extract_supports.py
**Sheets Status:** Not yet extracted (0 details in database)
**Action Required:** Set API key and run extraction script

For detailed extraction specifications, see: D:/EXTRACTION_REPORT_SHEETS_125-127.md
