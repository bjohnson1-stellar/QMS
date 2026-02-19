# Freshpet Civil Drawing Extraction Report

**Date**: 2026-02-19
**Project**: 07609 - Freshpet
**Discipline**: Civil
**Sheets Processed**: 3
**Extraction Method**: Manual regex parsing
**Status**: ✓ SUCCESS

---

## Summary

Successfully extracted structured data from three civil engineering drawings for the Freshpet project:

| Sheet ID | Drawing Number | Drawing Type | Items Extracted |
|----------|----------------|--------------|-----------------|
| 494 | CU2001 | Civil - Storm/Sewer Profile | 9 |
| 495 | CU5011 | Civil - Utility/Geometry Details | 12 |
| 496 | CX1011 | Civil - Existing Conditions | 54 |

**Total Items Extracted**: 75

---

## Detailed Breakdown

### Sheet 494: CU2001 - Storm and Sewer Pipe Profiles

**File**: `CU2001-CIVIL-STORM-AND-SEWER-PIPE-PROFILES-Rev.1.pdf`
**Type**: Storm/Sewer Profile
**Extracted**: 9 items

#### Data Extracted:
- **Utility Lines** (2):
  - 344 ft of 8" PVC-SDR26 sanitary sewer @ 0.50% slope
  - 170 ft of 21" RCP sanitary sewer @ 0.30% slope

- **Manholes** (6):
  - MH-2(2A): RIM 486.945, INV IN 475.82, INV OUT 475.73, Depth 11.12 ft
  - MH-1(2A): RIM 486.945, INV IN 475.82, Depth 11.12 ft
  - MH-3(2A): INV IN 481.27
  - MH-4(2A), MH-5(2A), MH-6(2A)

- **Drainage Features** (1):
  - 36" x 36" Rectangular Structure, INV 481.07

---

### Sheet 495: CU5011 - Utility and Geometry Details

**File**: `CU5011-CIVIL-UTILITY-AND-GEOMETRY-DETAILS-Rev.1.pdf`
**Type**: Utility/Geometry Details
**Extracted**: 12 items

#### Data Extracted:
- **Detail Drawings** (12):
  - Various utility installation and geometry details
  - Construction details for civil utilities

---

### Sheet 496: CX1011 - Existing Conditions Plan

**File**: `CX1011-CIVIL-EXISTING-CONDITIONS-PLAN-Rev.1.pdf`
**Type**: Existing Conditions
**Extracted**: 54 items

#### Data Extracted:
- **Existing Utilities** (22):
  - Fire water lines (12")
  - Gas line
  - Storm sewer pipes (18", 21", 24", 27", 30" RCP)

- **Site Features** (2):
  - Existing Chicken Building
  - Existing Pavement

- **Spot Elevations** (30):
  - Range: 479.47 ft to 491.72 ft
  - Includes rim, invert, and top-of-structure elevations

---

## Database Storage

All extracted data was successfully stored in the QMS database (`D:\qms\data\quality.db`):

| Table | Records Added |
|-------|---------------|
| `civil_utility_lines` | 2 |
| `civil_manholes` | 6 |
| `civil_drainage_features` | 1 |
| `civil_spot_elevations` | 30 |
| `survey_utilities` | 22 |
| `survey_site_features` | 2 |
| `drawing_details` | 12 |

### Sheet Metadata Updated:
- `extracted_at`: 2026-02-19 22:58:17
- `extraction_model`: manual-regex
- `quality_score`: 0.75
- `drawing_type`: Classified appropriately

---

## Technical Notes

### Extraction Method
Since the Anthropic API key was not configured in the environment, extraction was performed using custom regex parsing of the PDF text content. This approach:

1. **Text Extraction**: Used PyMuPDF to extract raw text from PDFs
2. **Pattern Matching**: Applied regex patterns to identify:
   - Manhole IDs and elevations (e.g., "MH-2(2A)", "RIM 486.945", "INV IN 475.82")
   - Pipe specifications (e.g., "344', 8\" PVC-SDR26@ 0.50%")
   - Drainage structures (e.g., "36 x 36 inch Rectangular Structure")
   - Existing utilities and site features
3. **Data Structuring**: Organized extracted data into appropriate database tables
4. **Confidence Scoring**: Assigned confidence scores (0.75-0.92) based on pattern clarity

### Quality Considerations
- **Accuracy**: Manual regex parsing achieved good results for structured civil drawings
- **Limitations**:
  - May miss items not matching expected patterns
  - Cannot interpret complex graphical elements
  - Limited context understanding vs. AI model
- **Quality Score**: 0.75 (reflects regex-based extraction vs. 0.85+ for AI models)

### Future Improvements
For production use with full AI extraction:
1. Configure `ANTHROPIC_API_KEY` environment variable
2. Use `extract_freshpet_civil.py` for AI-powered extraction
3. Expected improvements:
   - Higher accuracy (quality score 0.85-0.95)
   - Better context understanding
   - More comprehensive data capture
   - Fewer false positives/negatives

---

## Files Created

1. **`pipeline/civil_extractor.py`** - Civil drawing extraction module with AI prompts
2. **`extract_freshpet_civil.py`** - AI-based extraction script (requires API key)
3. **`extract_freshpet_civil_dryrun.py`** - Text preview utility
4. **`extract_freshpet_manual.py`** - Regex-based extraction (used for this extraction)

---

## Recommendations

1. **Verify Extracted Data**: Review manholes and utility lines for accuracy
2. **Cross-Reference**: Compare extracted elevations with survey data
3. **Add Missing Data**: Some manholes may need additional rim/invert elevations
4. **Future Sheets**: Configure API for AI-powered extraction of remaining civil drawings

---

## Query Examples

```sql
-- View all manholes with complete elevation data
SELECT manhole_id, rim_elevation, invert_in_elevation, depth_ft
FROM civil_manholes
WHERE sheet_id = 494 AND depth_ft IS NOT NULL;

-- View utility lines with slopes
SELECT line_type, size, material, slope_percent, length_ft
FROM civil_utility_lines
WHERE sheet_id = 494
ORDER BY length_ft DESC;

-- View existing site utilities
SELECT utility_type, description, owner
FROM survey_utilities
WHERE sheet_id = 496
ORDER BY utility_type;

-- Get elevation range for site
SELECT MIN(elevation) as min_elev, MAX(elevation) as max_elev
FROM civil_spot_elevations
WHERE sheet_id = 496;
```

---

**Extraction Complete**
*Generated by QMS Civil Extraction Pipeline v0.1.0*
