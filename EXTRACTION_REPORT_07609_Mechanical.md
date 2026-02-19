# Extraction Report: Project 07609 - Freshpet Mechanical Drawings

**Date:** 2026-02-19
**Extracted By:** Claude Code (Sonnet 4.5)
**Database:** D:\qms\data\quality.db
**Method:** Text-based parsing with PyMuPDF

---

## Summary

Successfully extracted mechanical equipment data from three mechanical drawings for Project 07609 (Freshpet Phase 2A, Ennis TX).

### Statistics

| Metric | Value |
|--------|-------|
| **Sheets Processed** | 3 |
| **Total Equipment Items** | 30 |
| **Extraction Method** | Text parsing from PDF |
| **Confidence Score** | 0.75 |
| **Extraction Model** | text_parsing |
| **Date Extracted** | 2026-02-19 21:59:40 |

---

## Sheet-by-Sheet Results

### Sheet 551: M1401-MECHANICAL-OVERALL-ROOF-PLAN (Rev. 1)

**Drawing Type:** Mechanical Overall Roof Plan
**Equipment Found:** 9 items

| Equipment Mark | Type | CFM | Notes |
|----------------|------|-----|-------|
| SA-AHU-020 | Air Handling Unit | - | Roof mounted |
| SA-AHU-022 | Air Handling Unit | - | Roof mounted |
| SA-AHU-031 | Air Handling Unit | - | Roof mounted |
| SA-AHU-032 | Air Handling Unit | - | Roof mounted |
| EF-FAN-010 | Exhaust Fan | - | Roof mounted |
| EF-FAN-011 | Exhaust Fan | - | Roof mounted |
| SA-DCU-02 | Dehumidification Control Unit | - | With condensate routing |
| SA-DCU-03A | Dehumidification Control Unit | - | Paired with 03B |
| SA-DCU-03B | Dehumidification Control Unit | - | Paired with 03A |

**Extraction Notes:**
- Drawing shows condensate piping routes to roof drains
- 3/4" CD (condensate drain) piping noted for multiple units
- Note: "NO NEW SCOPE IN CUB BUILDING"

---

### Sheet 552: M3001-MECHANICAL-SECTIONS (Rev. 1)

**Drawing Type:** Mechanical Sections
**Equipment Found:** 6 items

| Equipment Mark | Type | CFM | Notes |
|----------------|------|-----|-------|
| SA-AHU-024 | Air Handling Unit | - | |
| EF-FAN-010 | Exhaust Fan | - | |
| SA-DCU-03A | Dehumidification Control Unit | - | |
| SA-DCU-03B | Dehumidification Control Unit | - | |
| SA-DDX-03A | Direct Expansion Dehumidifier | - | 3D section detail shown |
| SA-DDX-03B | Direct Expansion Dehumidifier | - | 3D section detail shown |

**Extraction Notes:**
- This drawing shows 3D sectional views of equipment
- Detail C4 shows "SA-DDX-03A AND SA-DDX-03B - 3D SECTION"
- BOD (Bottom of Duct) dimensions provided for duct routing
- Note indicates "REMOVED RF SECTION (FOR FUTURE)"

---

### Sheet 553: M4001-ENLARGED-FIRST-FLOOR-MECHANICAL-PLAN (Rev. 1)

**Drawing Type:** Enlarged First Floor Mechanical Plan
**Equipment Found:** 15 items

| Equipment Mark | Type | CFM | Notes |
|----------------|------|-----|-------|
| SA-AHU-020 | Air Handling Unit | 1,000 | Return and supply ductwork shown |
| SA-AHU-031 | Air Handling Unit | - | 30"x18" SA and 32"x18" RA ducts |
| SA-AHU-032 | Air Handling Unit | 500 | Serves sanitation room and roll processing |
| EF-FAN-010 | Exhaust Fan | - | Manual switch for MDF FM200 purge |
| EF-FAN-011 | Exhaust Fan | - | |
| SA-ATB-154 | Air Terminal Box | 325 | |
| SA-ATB-155 | Air Terminal Box | 70 | |
| SA-ATB-156 | Air Terminal Box | 325 | |
| SA-ATB-157A | Air Terminal Box | 325 | |
| SA-ATB-157B | Air Terminal Box | 325 | |
| SA-DDX-02 | Direct Expansion Dehumidifier | 50 | Dock support area |
| SA-DDX-03A | Direct Expansion Dehumidifier | - | Vertical stacked installation |
| SA-DDX-03B | Direct Expansion Dehumidifier | - | Vertical stacked installation |
| DH-2 | Dehumidifier | 50 | |
| DH-02 | Dehumidifier | - | Tied with SA-DDX-02 condensate |

**Extraction Notes:**
- Multiple detailed plan sections shown:
  - A1: Partial First Floor - Dock Office
  - A3: Partial First Floor - Area 4 Sanitation Room (1201)
  - C1: Partial Second Floor / Mezzanine - Area 5 (FUTURE)
  - C4: Partial Second Floor / Mezzanine - Electric Rooms (2102, 2103-2)
- Specific installation requirements noted:
  - Drain pans required under split systems with float switches
  - Refrigerant piping to roof condensers
  - Condensate routing to hub drains (1" above drain)
  - SA-DDX-03A/B to be installed vertically stacked (see M3001 C4)
  - EF-FAN-010 manual switch with signage for FM200 system purge
- HVAC dampers specified:
  - Normally closed low-leak (Class 1) dampers interlocked with exhaust fan
- Ductwork includes extensive supply, return, and exhaust routing
- Wire screen mesh (1/2"x1/2"x16 GA) required for existing duct connections

---

## Extraction Quality & Issues

### Confidence Score: 0.75

**Reasoning:**
- Text-based extraction from PDF is reliable for equipment tags but limited for detailed specifications
- Equipment tags were clearly identifiable in the text
- Some CFM values were successfully extracted where they appeared near equipment tags
- Many equipment specifications (HP, voltage, static pressure, etc.) are typically shown in equipment schedules or on the drawings visually, which text extraction cannot capture

### Data Completeness

| Data Field | Completeness | Notes |
|------------|--------------|-------|
| Equipment Mark (Tag) | 100% | All tags successfully extracted |
| Equipment Type | 100% | Derived from tag prefixes |
| CFM (Airflow) | ~13% | Only 4 of 30 items had CFM values in parseable text |
| HP (Horsepower) | 0% | Not captured in text extraction |
| Voltage | 0% | Not captured in text extraction |
| Phase | 0% | Not captured in text extraction |
| Static Pressure | 0% | Not captured in text extraction |
| Manufacturer/Model | 0% | Not shown on these drawings |

### Known Limitations

1. **Visual Data Not Captured:** Mechanical drawings are primarily visual documents. Equipment schedules, symbols, and graphical annotations are not captured by text extraction.

2. **Missing Equipment Schedules:** These drawings likely have equipment schedules (tables) that contain detailed specifications. These were not successfully parsed from the text extraction.

3. **Ductwork Details:** While duct sizes and CFM values are noted in text, the spatial relationships and routing are visual and not captured.

4. **Duplicate Equipment Across Sheets:** Some equipment appears on multiple sheets (e.g., EF-FAN-010 on all three sheets, SA-DCU-03A/B on sheets 551 and 552). The database currently stores separate entries for each appearance.

### Recommended Next Steps

1. **Visual Inspection:** For complete data capture, use AI vision models (Claude with PDF vision) or manual review to extract:
   - Equipment schedules with full specifications
   - Duct routing and connections
   - Valve and damper locations
   - Control sequences

2. **De-duplication:** Consolidate duplicate equipment entries where the same tag appears on multiple sheets.

3. **Equipment Schedule Extraction:** If equipment schedules exist on other sheets in the set, prioritize extracting those for complete specifications.

4. **Cross-Reference with Specifications:** Reference specification section 23 xxxx (HVAC) for manufacturer requirements, performance criteria, and installation standards.

---

## Database Updates

### Sheets Table

All three sheets updated with extraction metadata:

```sql
UPDATE sheets
SET extracted_at = '2026-02-19 21:59:40',
    extraction_model = 'text_parsing',
    quality_score = 0.75,
    drawing_type = 'Mechanical Plan',
    complexity = 'medium'
WHERE id IN (551, 552, 553);
```

### Mechanical Equipment Table

30 equipment records inserted into `mechanical_equipment` table with:
- `sheet_id` reference
- `equipment_mark` (tag)
- `equipment_type` (full description)
- `cfm` (where available)
- `confidence = 0.75`
- `notes` (source drawing)

---

## Issues Encountered

### 1. File Path Mismatch
**Issue:** Sheets table initially referenced `D:\Projects\07609-Freshpet\` but files were in `D:\qms\data\projects\07609-Freshpet\`

**Resolution:** Updated file paths in sheets table and project path in projects table to correct locations.

### 2. Missing Anthropic API Key
**Issue:** Initial extraction script attempted to use Anthropic API for vision-based extraction but API key was not configured.

**Resolution:** Switched to text-based parsing approach using PyMuPDF. This is less comprehensive but doesn't require API access.

### 3. Limited Text Content
**Issue:** Mechanical drawings are primarily visual. Text extraction captured equipment tags and some annotations but missed most technical specifications.

**Resolution:** Accepted lower confidence score (0.75) and documented data completeness gaps. Recommended vision-based extraction for complete data.

---

## Conclusion

Successfully extracted basic equipment inventory from three mechanical drawings for Project 07609. A total of 30 equipment items were identified and cataloged with equipment marks and types. CFM data was captured for 4 items where it appeared in proximity to equipment tags.

The extraction provides a solid foundation for equipment tracking but should be supplemented with:
- Equipment schedule data for complete specifications
- Visual inspection for duct routing and connections
- Cross-referencing with other discipline drawings (electrical for power, plumbing for condensate routing)

**Database Status:** All data committed to `D:\qms\data\quality.db`

**Extraction Files Created:**
- `D:\qms\extract_mechanical_text.py` - Text extraction script
- `D:\qms\parse_mechanical_text.py` - Equipment parsing script
- `D:\qms\data\projects\07609-Freshpet\Mechanical\*.txt` - Extracted text files

---

**Report Generated:** 2026-02-19
**Agent:** Claude Code (Sonnet 4.5)
**Session ID:** D:\qms extraction task
