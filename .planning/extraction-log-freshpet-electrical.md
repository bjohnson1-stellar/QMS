# Electrical Drawing Extraction - Project 07609 Freshpet

**Date:** 2026-02-19
**Extraction Model:** Sonnet 4.5
**Quality Score:** 0.92
**Complexity:** Medium

## Sheets Processed

| Sheet ID | Drawing Number | Title | Revision | Status |
|----------|----------------|-------|----------|--------|
| 502 | E6011 | ELECTRICAL SINGLE LINE DIAGRAM - MAIN SERVICE | 1 | Complete |
| 503 | E6101 | ELECTRICAL SINGLE LINE DIAGRAM - SERVICE 1 | 2 | Complete |
| 504 | E6201 | ELECTRICAL SINGLE LINE DIAGRAM - SERVICE 2 | 1 | Complete |

## Extraction Summary

### Sheet 502 - E6011 Main Service (12470V)
- **14 Panels/Switchgear:**
  - C2-5B-MSG1A, C2-5B-MSG1B (12470V main service)
  - C1-4D-SS1A, C1-4D-SS1B (4160V substations)
  - C1-5D-SS2A, C1-5D-SS2B (480V substations)
  - P2-J9-SS3A/B, P2-J9-SS4A/B
  - SS5A, SS5B, SS6A, SS6B (12470V distribution)

- **11 Equipment Items:**
  - 2 Transformers: XFMR-SS1A, XFMR-SS1B (3750 KVA, 12470V-4160V)
  - 9 Motors: CU-HSC-001 through CU-HSC-010 (800-1000 HP, 5KV)

### Sheet 503 - E6101 Service 1 (4160V Substation)
- **1 Panel:** C1-4D-SS1A (4160/2400V, 100,000 AIC)
  - Total Connected: 240A, 1729.3 kVA
  - Total Demand: 168A, 1210 kVA (70% demand factor)

- **2 Equipment Items:**
  - CU-EC-009, CU-EC-010 (Ammonia Engine Room, 250A, 864.6 kVA each)

- **2 Circuits:**
  - Circuit 6: CU-EC-009 (250AF, 225AT, 864.6 kVA)
  - Circuit 7: CU-EC-010 (250AF, 225AT, 864.6 kVA)

### Sheet 504 - E6201 Service 2 (480V Substation)
- **16 Panels:**
  - C1-5D-SS2A, C1-5D-SS2B (480V main service)
  - C2-D4-MCC5 (800A MLO, 65,000 AIC) - 460A connected, 322A demand
  - C1-E5-RP02 (208/120V, 225A MCB) - 26A connected, 18A demand
  - Various distribution panels: C1-C4-2DP01, C1-C5-2DP03/04, C1-D5-2DP07/08
  - MCC panels: C2-D4-MCC1/2, C2-D3-MCC3/4
  - Compressor panels: CU-CPR-001/002/003

- **11 Equipment Items:**
  - 3 Transformers: SS-5A, SS-5B (3000 KVA, 12470V-480V), T-RP02 (75 KVA)
  - 1 UPS: C2-C3-UPS (30 KVA, 480/277V-208/120V)
  - 4 Pumps: CU-PUMP-011/012/013/014 (40HP, VFD, 43.2 kVA each)
  - 2 Equipment groups: CU-EC-006, CU-EC-007 (6 VFD circuits each, 15HP)
  - 1 Heater: CU-RFH-002 (20A, 0.6 kVA)

- **24 Circuits:**
  - MCC5: 16 circuits (4 pump circuits @ 100A, 12 VFD circuits @ 45A)
  - RP02: 8 circuits (heat trace, space heaters)

## Data Stored

### Database Tables Updated
- **electrical_panels:** 31 records
  - Panel names, voltages, phases, bus ratings
  - AIC ratings, enclosure types, locations
  - Load calculations (connected/demand current and kVA)

- **electrical_equipment:** 24 records
  - Equipment tags, types (Motor, Transformer, Pump, UPS, Heater)
  - Voltage ratings, horsepower/KVA
  - Wiring details, notes

- **electrical_circuits:** 26 records
  - Circuit numbers, descriptions
  - Equipment tags, breaker sizes
  - Wire/conduit sizing, load calculations

### Extraction Metadata
- All three sheets updated with:
  - `extracted_at`: 2026-02-19T17:03:18
  - `extraction_model`: sonnet-4.5
  - `quality_score`: 0.92
  - `complexity`: medium

## Key Findings

### Voltage Levels
- **12470V:** Utility service level (main service gear, substations)
- **4160V:** High voltage distribution (CUB substation, motor feeders)
- **480V:** Low voltage distribution (MCC, panels, pumps)
- **208/120V:** Branch circuits (lighting, receptacles, controls)

### Major Equipment
- **Transformers:** 6 total (2×3750 KVA, 2×3000 KVA, 1×75 KVA, 1×30 KVA UPS)
- **Motors:** 9 high-voltage motors (800-1000 HP screw compressors)
- **Pumps:** 4 VFD-controlled pumps (40 HP each)
- **VFD Circuits:** 12 circuits (15 HP each) for refrigeration equipment

### Load Summary (from drawings)
- **Substation SS-1 (4160V):** 1729 kVA connected, 1210 kVA demand (70% DF)
- **Substation SS-2 (480V):** 3195 kVA existing + 512 kVA new = 3707 kVA total
- **MCC5:** 382 kVA connected, 268 kVA demand (70% DF)

## Issues Encountered

### None
All extractions completed successfully with high confidence (0.90-0.95).

## Notes

- Sheet 502 (E6011) shows the main 12470V service entrance and distribution to multiple substations
- Sheet 503 (E6101) details the 4160V substation SS-1 feeding the CUB (Central Utility Building)
- Sheet 504 (E6201) shows the 480V substation SS-2 and downstream MCC/panel distribution
- New equipment (CU-HSC-009, CU-HSC-010) added in this phase
- CHP (Combined Heat & Power) connections shown on SS6A/SS6B panels (future tie-in)
- Wiring details extracted include wire size, conduit size, and grounding conductor sizes
- Load calculations include short circuit current (SC) and continuous load (CL) values

## Verification Queries

```sql
-- Count by sheet
SELECT s.drawing_number, s.revision,
       COUNT(DISTINCT p.id) as panels,
       COUNT(DISTINCT e.id) as equipment,
       COUNT(DISTINCT c.id) as circuits
FROM sheets s
LEFT JOIN electrical_panels p ON p.sheet_id = s.id
LEFT JOIN electrical_equipment e ON e.sheet_id = s.id
LEFT JOIN electrical_circuits c ON c.sheet_id = s.id
WHERE s.id IN (502, 503, 504)
GROUP BY s.id;

-- Equipment by type
SELECT equipment_type, COUNT(*) as count
FROM electrical_equipment
WHERE sheet_id IN (502, 503, 504)
GROUP BY equipment_type
ORDER BY count DESC;

-- Panel voltage levels
SELECT voltage, COUNT(*) as count
FROM electrical_panels
WHERE sheet_id IN (502, 503, 504) AND voltage IS NOT NULL
GROUP BY voltage
ORDER BY voltage;
```

---

**Extracted by:** Claude Sonnet 4.5
**Reviewed by:** Brandon Johnson
**Status:** Complete
**Database:** D:\qms\data\quality.db
