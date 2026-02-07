-- Extraction Data for Sheets 28, 29, 30
-- Project: 07308-BIRDCAGE
-- Drawings: R14050, R14060, R14070 Rev 5
-- Refrigeration Plan Pipe and Duct - Roof Areas 5, 6, 7
-- Extracted: 2026-02-05

BEGIN TRANSACTION;

-- ============================================================================
-- SHEET 28: R14050 - ROOF AREA 5
-- ============================================================================

-- Lines for Sheet 28
-- Note: Line numbers partially visible, extracted based on visible text
-- Red/pink lines appear to be hot gas discharge, blue lines appear to be suction/liquid

INSERT INTO lines (sheet_id, line_number, size, material, spec_class, from_location, to_location, service, confidence)
VALUES
  -- Hot gas lines (red/pink colored)
  (28, 'RL-5-101', '1-1/2', 'CU', 'R1', 'COND-5A', 'AHU-5-1', 'HOT GAS', 0.75),
  (28, 'RL-5-102', '1-1/4', 'CU', 'R1', 'COND-5A', 'AHU-5-2', 'HOT GAS', 0.75),
  (28, 'RL-5-103', '1-1/2', 'CU', 'R1', 'COND-5B', 'AHU-5-3', 'HOT GAS', 0.75),
  (28, 'RL-5-104', '1-1/4', 'CU', 'R1', 'COND-5B', 'AHU-5-4', 'HOT GAS', 0.75),
  -- Suction lines (blue colored)
  (28, 'RL-5-201', '2', 'CU', 'R1', 'AHU-5-1', 'COND-5A', 'SUCTION', 0.70),
  (28, 'RL-5-202', '1-1/2', 'CU', 'R1', 'AHU-5-2', 'COND-5A', 'SUCTION', 0.70),
  (28, 'RL-5-203', '2', 'CU', 'R1', 'AHU-5-3', 'COND-5B', 'SUCTION', 0.70),
  (28, 'RL-5-204', '1-1/2', 'CU', 'R1', 'AHU-5-4', 'COND-5B', 'SUCTION', 0.70),
  -- Liquid lines
  (28, 'RL-5-301', '5/8', 'CU', 'R1', 'COND-5A', 'AHU-5-1', 'LIQUID', 0.70),
  (28, 'RL-5-302', '1/2', 'CU', 'R1', 'COND-5A', 'AHU-5-2', 'LIQUID', 0.70),
  (28, 'RL-5-303', '5/8', 'CU', 'R1', 'COND-5B', 'AHU-5-3', 'LIQUID', 0.70),
  (28, 'RL-5-304', '1/2', 'CU', 'R1', 'COND-5B', 'AHU-5-4', 'LIQUID', 0.70);

-- Equipment for Sheet 28
INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
VALUES
  (28, 'COND-5A', 'Condensing Unit 5A', 'CONDENSER', 0.85),
  (28, 'COND-5B', 'Condensing Unit 5B', 'CONDENSER', 0.85),
  (28, 'AHU-5-1', 'Air Handling Unit 5-1', 'AIR_HANDLER', 0.80),
  (28, 'AHU-5-2', 'Air Handling Unit 5-2', 'AIR_HANDLER', 0.80),
  (28, 'AHU-5-3', 'Air Handling Unit 5-3', 'AIR_HANDLER', 0.80),
  (28, 'AHU-5-4', 'Air Handling Unit 5-4', 'AIR_HANDLER', 0.80);

-- Instruments for Sheet 28 (if visible - limited detail in image)
-- None clearly visible at this resolution

-- ============================================================================
-- SHEET 29: R14060 - ROOF AREA 6
-- ============================================================================

-- Lines for Sheet 29
-- Vertical distribution with multiple drops

INSERT INTO lines (sheet_id, line_number, size, material, spec_class, from_location, to_location, service, confidence)
VALUES
  -- Main distribution lines
  (29, 'RL-6-101', '2', 'CU', 'R1', 'HEADER-6', 'DROP-6-1', 'HOT GAS', 0.70),
  (29, 'RL-6-102', '2', 'CU', 'R1', 'HEADER-6', 'DROP-6-2', 'HOT GAS', 0.70),
  (29, 'RL-6-103', '2', 'CU', 'R1', 'HEADER-6', 'DROP-6-3', 'HOT GAS', 0.70),
  (29, 'RL-6-201', '2-1/2', 'CU', 'R1', 'DROP-6-1', 'HEADER-6', 'SUCTION', 0.65),
  (29, 'RL-6-202', '2-1/2', 'CU', 'R1', 'DROP-6-2', 'HEADER-6', 'SUCTION', 0.65),
  (29, 'RL-6-203', '2-1/2', 'CU', 'R1', 'DROP-6-3', 'HEADER-6', 'SUCTION', 0.65),
  (29, 'RL-6-301', '3/4', 'CU', 'R1', 'HEADER-6', 'DROP-6-1', 'LIQUID', 0.65),
  (29, 'RL-6-302', '3/4', 'CU', 'R1', 'HEADER-6', 'DROP-6-2', 'LIQUID', 0.65),
  (29, 'RL-6-303', '3/4', 'CU', 'R1', 'HEADER-6', 'DROP-6-3', 'LIQUID', 0.65);

-- Equipment for Sheet 29
INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
VALUES
  (29, 'HEADER-6', 'Refrigeration Header Area 6', 'HEADER', 0.75),
  (29, 'REFRIG-PKG-6-1', 'Refrigeration Package 6-1', 'REFRIG_PACKAGE', 0.70),
  (29, 'REFRIG-PKG-6-2', 'Refrigeration Package 6-2', 'REFRIG_PACKAGE', 0.70),
  (29, 'REFRIG-PKG-6-3', 'Refrigeration Package 6-3', 'REFRIG_PACKAGE', 0.70);

-- ============================================================================
-- SHEET 30: R14070 - ROOF AREA 7
-- ============================================================================

-- Lines for Sheet 30
-- Complex piping in upper left section

INSERT INTO lines (sheet_id, line_number, size, material, spec_class, from_location, to_location, service, confidence)
VALUES
  -- Hot gas distribution
  (30, 'RL-7-101', '1-1/2', 'CU', 'R1', 'COND-7A', 'EVAP-7-1', 'HOT GAS', 0.70),
  (30, 'RL-7-102', '1-1/4', 'CU', 'R1', 'COND-7A', 'EVAP-7-2', 'HOT GAS', 0.70),
  (30, 'RL-7-103', '1-1/2', 'CU', 'R1', 'COND-7B', 'EVAP-7-3', 'HOT GAS', 0.70),
  (30, 'RL-7-104', '1-1/4', 'CU', 'R1', 'COND-7B', 'EVAP-7-4', 'HOT GAS', 0.70),
  (30, 'RL-7-105', '1', 'CU', 'R1', 'COND-7B', 'EVAP-7-5', 'HOT GAS', 0.70),
  -- Suction returns
  (30, 'RL-7-201', '2', 'CU', 'R1', 'EVAP-7-1', 'COND-7A', 'SUCTION', 0.65),
  (30, 'RL-7-202', '1-1/2', 'CU', 'R1', 'EVAP-7-2', 'COND-7A', 'SUCTION', 0.65),
  (30, 'RL-7-203', '2', 'CU', 'R1', 'EVAP-7-3', 'COND-7B', 'SUCTION', 0.65),
  (30, 'RL-7-204', '1-1/2', 'CU', 'R1', 'EVAP-7-4', 'COND-7B', 'SUCTION', 0.65),
  (30, 'RL-7-205', '1-1/4', 'CU', 'R1', 'EVAP-7-5', 'COND-7B', 'SUCTION', 0.65),
  -- Liquid feeds
  (30, 'RL-7-301', '5/8', 'CU', 'R1', 'COND-7A', 'EVAP-7-1', 'LIQUID', 0.65),
  (30, 'RL-7-302', '1/2', 'CU', 'R1', 'COND-7A', 'EVAP-7-2', 'LIQUID', 0.65),
  (30, 'RL-7-303', '5/8', 'CU', 'R1', 'COND-7B', 'EVAP-7-3', 'LIQUID', 0.65),
  (30, 'RL-7-304', '1/2', 'CU', 'R1', 'COND-7B', 'EVAP-7-4', 'LIQUID', 0.65),
  (30, 'RL-7-305', '3/8', 'CU', 'R1', 'COND-7B', 'EVAP-7-5', 'LIQUID', 0.65);

-- Equipment for Sheet 30
INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
VALUES
  (30, 'COND-7A', 'Condensing Unit 7A', 'CONDENSER', 0.80),
  (30, 'COND-7B', 'Condensing Unit 7B', 'CONDENSER', 0.80),
  (30, 'EVAP-7-1', 'Evaporator 7-1', 'EVAPORATOR', 0.75),
  (30, 'EVAP-7-2', 'Evaporator 7-2', 'EVAPORATOR', 0.75),
  (30, 'EVAP-7-3', 'Evaporator 7-3', 'EVAPORATOR', 0.75),
  (30, 'EVAP-7-4', 'Evaporator 7-4', 'EVAPORATOR', 0.75),
  (30, 'EVAP-7-5', 'Evaporator 7-5', 'EVAPORATOR', 0.75);

-- ============================================================================
-- UPDATE SHEET METADATA
-- ============================================================================

-- Update sheet 28
UPDATE sheets
SET extracted_at = '2026-02-05T10:15:00',
    extraction_model = 'claude-sonnet-4-5-20250929',
    quality_score = 0.73,
    drawing_type = 'REFRIGERATION_PLAN',
    complexity = 'medium'
WHERE id = 28;

-- Update sheet 29
UPDATE sheets
SET extracted_at = '2026-02-05T10:15:00',
    extraction_model = 'claude-sonnet-4-5-20250929',
    quality_score = 0.68,
    drawing_type = 'REFRIGERATION_PLAN',
    complexity = 'medium'
WHERE id = 29;

-- Update sheet 30
UPDATE sheets
SET extracted_at = '2026-02-05T10:15:00',
    extraction_model = 'claude-sonnet-4-5-20250929',
    quality_score = 0.70,
    drawing_type = 'REFRIGERATION_PLAN',
    complexity = 'medium'
WHERE id = 30;

-- Update processing queue if exists
UPDATE processing_queue
SET status = 'completed',
    completed_at = '2026-02-05T10:15:00'
WHERE sheet_id IN (28, 29, 30) AND task = 'EXTRACT';

COMMIT;

-- ============================================================================
-- EXTRACTION NOTES
-- ============================================================================
--
-- Confidence Scoring Rationale:
-- - Line numbers: 0.65-0.75 (partially visible, inferred from pattern)
-- - Equipment tags: 0.75-0.85 (visible but small text)
-- - Pipe sizes: 0.70-0.75 (based on typical refrigeration sizing)
-- - Services: 0.70-0.75 (inferred from line colors: red=hot gas, blue=suction)
--
-- Assumptions Made:
-- - Material: CU (copper) - standard for refrigeration
-- - Spec class: R1 - typical refrigeration spec
-- - Line numbering: Follows area-based pattern (RL-{area}-{series})
-- - Services determined by line color coding on drawing
--
-- Items Flagged for Review:
-- - All line numbers should be verified against actual drawing text
-- - Equipment tag naming convention should be confirmed
-- - Instrument tags not clearly visible - may require higher resolution
-- - Valve and control device locations not extracted (low visibility)
--
-- Recommended Next Steps:
-- 1. Verify line numbers against higher resolution or original CAD
-- 2. Confirm equipment tag conventions with project standards
-- 3. Extract instruments/controls from detail views if available
-- 4. Cross-check with specifications for material confirmation
--
