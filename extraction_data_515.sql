-- Extraction for Sheet 515: EL1141 Area 4
-- Update sheet metadata
UPDATE sheets
SET drawing_type = 'lighting_plan',
    complexity = 'medium',
    extracted_at = datetime('now'),
    extraction_model = 'sonnet',
    quality_score = 0.85,
    title = 'PARTIAL FIRST FLOOR LIGHTING PLAN - AREA 4'
WHERE id = 515;

-- Insert lighting fixtures
INSERT INTO electrical_lighting_fixtures (sheet_id, fixture_type, location, mounting_height, qty, confidence) VALUES
(515, 'P1A', 'Roll Processing/Chilling', NULL, 18, 0.92),
(515, 'P1B', 'General Areas/Service Halls', NULL, 50, 0.90),
(515, 'X3A', 'Exit/Emergency', NULL, 2, 0.90),
(515, 'X4A', 'Exit/Emergency', NULL, 14, 0.90),
(515, 'W1A', 'Wall-mounted', '10''-0" AFF', 2, 0.95),
(515, 'W1B', 'Wall-mounted', '20''-0" AFF', 5, 0.95),
(515, 'C1B', 'Under Platform', NULL, 14, 0.90);

-- Insert circuits
INSERT INTO electrical_circuits (sheet_id, circuit_number, wire_size, conduit_size, notes, confidence) VALUES
(515, 'P2-H14-5LTG2C-19', NULL, NULL, 'Lighting circuit', 0.75),
(515, 'P2-Q11-5UPS3A/18', '1-#10, 1-#10, 1-#10G', '3/4"C', 'UPS circuit', 0.95),
(515, 'P2-H14-5LTG2C/22', '1-#12, 1-#12, 1-#12G', '3/4"C', 'Lighting circuit', 0.95),
(515, 'P2-Q14-5LTG2B/31', '1-#12, 1-#12, 1-#12G', '3/4"C', 'Lighting circuit', 0.95),
(515, 'P2-Q14-5LTG2B/17', '1-#12, 1-#12, 1-#12G', '3/4"C', 'Lighting circuit', 0.95);
