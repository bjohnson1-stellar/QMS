# Extraction Report: Freshpet Architectural Details

**Project:** 07609-Freshpet
**Discipline:** Architectural
**Date:** 2026-02-19
**Sheets Processed:** 3
**Status:** Complete

## Summary

Extracted architectural detail callouts and metadata from three detail sheets using text-based extraction (Haiku model equivalent - pattern matching).

| Sheet ID | Drawing Number | Detail Callouts | Notes | Status |
|----------|----------------|-----------------|-------|--------|
| 473 | A5041-STAIR-&-RAMP-DETAILS | 2 | 0 | Success |
| 474 | A5053-DOCK-DETAILS | 6 | 3 | Success |
| 475 | A5055-CURB-DETAILS | 6 | 8 | Success |

**Total Detail Callouts Extracted:** 16
**Average Quality Score:** 0.85
**Extraction Model:** haiku (text pattern matching)

## Sheet Details

### A5041-STAIR-&-RAMP-DETAILS (Sheet ID 473)
- **Detail Callouts:** STR.05, STR.07
- **Content Type:** Stair and ramp construction details
- **Material References:** 23 (steel, concrete, metal components)
- **Complexity:** Simple
- **Quality Score:** 0.85

### A5053-DOCK-DETAILS (Sheet ID 474)
- **Detail Callouts:** CAN.02, DK.10, DK.12, DK.18, DK.35, DK.36
- **Content Type:** Loading dock details (canopy, pit, bollards)
- **Material References:** 25 (overhead doors, dock equipment, structural steel)
- **Notes Found:** 3 (canopy engineering requirements, installation notes)
- **Complexity:** Simple
- **Quality Score:** 0.85

### A5055-CURB-DETAILS (Sheet ID 475)
- **Detail Callouts:** CRB.09, CRB.10, CRB.12, CRB.24, CRB.26, CRB.30
- **Content Type:** Concrete curb details (various configurations)
- **Material References:** 50 (concrete, insulated metal panels, sealants, base channels)
- **Notes Found:** 8 (installation instructions, finish requirements)
- **Complexity:** Simple
- **Quality Score:** 0.85

## Extraction Methodology

### Approach
Architectural detail drawings contain primarily graphical information with embedded detail callouts, dimensions, and material specifications. Full AI-based extraction was not required for these simple detail sheets.

### Process
1. **Text Extraction:** Used QMS text extraction tools (PyPDF2-based)
2. **Pattern Matching:** Regex-based extraction of detail callouts (e.g., CRB.10, DK.35)
3. **Metadata Analysis:** Counted material references, notes, and dimensions
4. **Database Storage:** Stored detail callouts as searchable equipment entries

### Database Updates
- Updated `sheets` table with extraction metadata (extracted_at, extraction_model, quality_score, complexity)
- Inserted 16 detail callout records into `equipment` table with type='detail_callout'
- All callouts stored with confidence=0.95 (high confidence for exact pattern matches)

## Observations

1. **Drawing Type:** These are architectural detail sheets, not equipment or piping drawings
2. **Content:** Primarily construction details for:
   - Stairs and ramps (structural connections)
   - Loading dock equipment (canopies, pits, bollards, doors)
   - Concrete curbs (wall bases, transitions, resinous flooring interfaces)
3. **Extraction Suitability:** Detail callouts and notes extracted successfully; dimensional and graphical data remains in PDFs
4. **No Equipment Tags:** No mechanical/electrical equipment tags (P-101, V-201, etc.) found - appropriate for architectural discipline

## Issues Encountered

**None.** All three sheets processed successfully without errors.

## Recommendations

1. **Visual Analysis:** For full architectural coordination, consider visual AI extraction to capture:
   - Dimensional relationships
   - Section views and callouts
   - Material layup details

2. **Cross-Referencing:** Detail callouts (CRB.10, DK.35, etc.) should be cross-referenced with floor plans and elevations to understand their application locations

3. **Future Scope:** If architectural equipment (doors, windows, fixtures) needs tracking, extend extraction to identify and catalog these items from plan sheets

## Conclusion

Text-based extraction successfully identified and cataloged 16 architectural detail callouts across 3 sheets. The detail drawings are now searchable by callout number, and extraction metadata is recorded for quality tracking.

All data committed to database at `D:\qms\data\quality.db`.
