# Extraction Report: Sheets 619-621 (Freshpet Refrigeration Supports)

**Date:** 2026-02-19
**Project:** 07609-Freshpet
**Discipline:** Refrigeration
**Sheet Type:** Detail Drawings - Pipe Supports

## Summary

Extraction attempted for three refrigeration support detail sheets but could not be completed due to technical limitations.

## Sheets Targeted

| Sheet ID | Drawing Number | Revision | File Path | Status |
|----------|---------------|----------|-----------|--------|
| 619 | R5210.1-REFRIGERATION-DETAILS-SUPPORTS | 1 | D:\qms\data\projects\07609-Freshpet\Refrigeration\R5210.1-REFRIGERATION-DETAILS-SUPPORTS-Rev.1.pdf | Not Extracted |
| 620 | R5211.1-REFRIGERATION-DETAILS-SUPPORTS | 1 | D:\qms\data\projects\07609-Freshpet\Refrigeration\R5211.1-REFRIGERATION-DETAILS-SUPPORTS-Rev.1.pdf | Not Extracted |
| 621 | R5220.1-REFRIGERATION-DETAILS-SUPPORTS | 1 | D:\qms\data\projects\07609-Freshpet\Refrigeration\R5220.1-REFRIGERATION-DETAILS-SUPPORTS-Rev.1.pdf | Not Extracted |

## Issues Encountered

### 1. Image-Based PDFs (No Text Layer)
All three PDFs are scanned images with no embedded text layer:
- R5210.1: 1 page, 0 characters of extractable text
- R5211.1: 1 page, 0 characters of extractable text
- R5220.1: 1 page, 0 characters of extractable text

**Impact:** Standard text extraction using PyMuPDF returns empty results.

**Resolution Required:** One of the following approaches:
- OCR preprocessing using Tesseract or similar
- Use Claude's vision capabilities with PDF-to-image conversion
- Request text-embedded versions of the drawings from the design team

### 2. API Authentication
The extraction script requires Anthropic API credentials that are not configured in this environment.

**Error:** `"Could not resolve authentication method. Expected either api_key or auth_token to be set."`

**Resolution:** Set `ANTHROPIC_API_KEY` environment variable or configure API credentials.

## Extraction Script Created

Created `D:\qms\extract_freshpet_supports.py` implementing the standard extraction pipeline:

### Process Flow
1. **Extract text from PDF** (using PyMuPDF)
2. **Classify drawing type** → "Detail (Supports)"
3. **Build extraction prompt** for support details
4. **Run extraction** with Claude Sonnet
5. **Parse JSON response**
6. **Calculate confidence scores**
7. **Store to database**:
   - `lines` table
   - `equipment` table
   - `instruments` table
   - Update `sheets` table with extraction metadata

### Expected Extraction Data

Based on the drawing type (Refrigeration Details - Supports), the extraction would capture:

#### Lines/Piping
- Line number/designation
- Pipe size
- Material (CS, SS, SCH number)
- Service (ammonia liquid, vapor, etc.)
- Support mounting details

#### Equipment/Components
- Tag numbers (if labeled)
- Equipment type (support, hanger, clamp, bracket, spring hanger, rod hanger, etc.)
- Descriptions
- Size/specifications
- Material specifications

#### Instruments/Controls
- Tag numbers (PT-xxx, FT-xxx, etc.)
- Instrument types
- Service/function
- Mounting locations

#### Structural/Support Elements
- Beam/column sizes
- Hanger rod specifications
- Spring constants
- Load capacities
- Installation notes

## Database Schema Used

### Lines Table
```sql
CREATE TABLE lines (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    line_number TEXT NOT NULL,
    size TEXT,
    material TEXT,
    spec_class TEXT,
    from_location TEXT,
    to_location TEXT,
    service TEXT,
    confidence REAL DEFAULT 1.0,
    pipe_material TEXT,
    pipe_spec TEXT,
    refrigerant TEXT,
    normalized_size TEXT
);
```

### Equipment Table
```sql
CREATE TABLE equipment (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    tag TEXT NOT NULL,
    description TEXT,
    equipment_type TEXT,
    confidence REAL DEFAULT 1.0
);
```

### Instruments Table
```sql
CREATE TABLE instruments (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    tag TEXT NOT NULL,
    instrument_type TEXT,
    loop_number TEXT,
    confidence REAL DEFAULT 1.0,
    service TEXT,
    description TEXT,
    location TEXT,
    drawing_number TEXT,
    extraction_notes TEXT,
    created_at TEXT
);
```

### Sheets Table Updates
```sql
UPDATE sheets
SET extracted_at = CURRENT_TIMESTAMP,
    extraction_model = 'sonnet',
    quality_score = <calculated>,
    drawing_type = 'Detail',
    complexity = 'simple',
    extraction_notes = <installation notes>
WHERE id IN (619, 620, 621);
```

## Confidence Scoring

The extraction pipeline calculates confidence scores using:

### Base Confidence
- Default: 0.7 for each extracted item
- Adjusted based on:
  - Text clarity (+0.2 for clear, legible text)
  - Standard formatting (+0.1 for recognized patterns)
  - Cross-referencing (+0.1 for items matching other sheets)
  - Partial/unclear text (-0.2)
  - Non-standard format (-0.1)

### Overall Quality Score
- Calculated as average of all item confidences
- Stored in `sheets.quality_score` field
- Range: 0.0 - 1.0

## Model Selection Rationale

### Chosen: Claude Sonnet 4.5
- **Drawing Type:** Detail drawings with moderate complexity
- **Content:** Structural supports, pipe hangers, installation details
- **Expected Items:** 10-30 components per sheet
- **Reasoning:**
  - Haiku: Too simple for technical details and measurements
  - Sonnet: Appropriate for moderate technical content ✓
  - Opus: Overkill for support details (costly, slower)

## Next Steps

To complete the extraction:

1. **Enable Vision-Based Extraction**
   - Convert PDFs to images (PNG/JPEG)
   - Use Claude's vision capabilities to read scanned drawings
   - Update extraction script to handle image inputs

2. **OR: Request OCR-Processed Versions**
   - Ask design team for text-embedded PDFs
   - Use Acrobat Pro OCR or similar to add text layer
   - Re-run extraction with text-based approach

3. **Configure API Credentials**
   - Set `ANTHROPIC_API_KEY` environment variable
   - Or configure in QMS config.yaml

4. **Run Extraction**
   ```bash
   cd D:\qms
   python extract_freshpet_supports.py
   ```

5. **Verify Results**
   ```sql
   SELECT COUNT(*) FROM lines WHERE sheet_id IN (619, 620, 621);
   SELECT COUNT(*) FROM equipment WHERE sheet_id IN (619, 620, 621);
   SELECT COUNT(*) FROM instruments WHERE sheet_id IN (619, 620, 621);
   ```

## Extraction Agent Process (Per Instructions)

The extraction follows the agent pattern from `.planning/agents/02_extractor.md`:

### 1. Get Work Queue
```sql
SELECT s.* FROM sheets s
WHERE s.id IN (619, 620, 621)
ORDER BY s.id;
```

### 2. For Each Sheet

#### a. Classify Drawing
- **Type:** Detail (Supports)
- **Complexity:** Simple (detail sheets typically have fewer items than P&IDs)
- **Model:** Sonnet (moderate complexity)

#### b. Read with Model
- Extract all visible components
- Identify line numbers, equipment tags, support types
- Capture installation notes and specifications

#### c. Extract Data by Type
Following detail drawing extraction pattern:
- **Lines:** Pipe runs shown in details with sizes, materials
- **Equipment:** Support hardware (hangers, brackets, clamps, springs)
- **Instruments:** Any instrumentation mounted on supports
- **Notes:** Installation requirements, load specifications, material callouts

#### d. Validate Extractions
- Check for required fields (at minimum: tag or identifier)
- Verify reasonable values (e.g., pipe sizes are standard)
- Calculate confidence scores
- Flag low-confidence items

#### e. Store in Database
See schema details above.

#### f. Update Sheet Status
Mark as extracted with timestamp, model used, quality score.

## Current Database State

```sql
-- Pre-extraction state
SELECT id, drawing_number, extracted_at, quality_score
FROM sheets
WHERE id IN (619, 620, 621);
```

Result:
```
619|R5210.1-REFRIGERATION-DETAILS-SUPPORTS|NULL|NULL
620|R5211.1-REFRIGERATION-DETAILS-SUPPORTS|NULL|NULL
621|R5220.1-REFRIGERATION-DETAILS-SUPPORTS|NULL|NULL
```

**Status:** Ready for extraction once technical issues are resolved.

## Files Created

1. **D:\qms\extract_freshpet_supports.py** - Extraction script
2. **D:\qms\extraction_report_sheets_619-621.md** - This report

## Recommendations

1. **Short-term:** Use vision-enabled extraction approach for scanned drawings
2. **Long-term:** Request text-embedded PDFs from design consultants
3. **Quality:** Manual review of support details recommended (safety-critical components)
4. **Cross-reference:** Compare extracted supports against P&ID pipe runs for completeness

---

**Report Generated:** 2026-02-19 16:59 CST
**System:** QMS Drawing Extraction Pipeline
**Package:** D:\qms v0.1.0
