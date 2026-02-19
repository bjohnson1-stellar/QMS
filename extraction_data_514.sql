-- Extraction for Sheet 514: EL1121 Area 2
-- Update sheet metadata
UPDATE sheets
SET drawing_type = 'lighting_plan',
    complexity = 'medium',
    extracted_at = datetime('now'),
    extraction_model = 'sonnet',
    quality_score = 0.87,
    title = 'PARTIAL FIRST FLOOR LIGHTING PLAN - AREA 2'
WHERE id = 514;

-- Insert lighting fixtures
INSERT INTO electrical_lighting_fixtures (sheet_id, fixture_type, location, mounting_height, qty, confidence) VALUES
(514, 'P1A', 'Sanitation/Utility/Warehouse', NULL, 12, 0.92),
(514, 'P1B', 'Receiving Docks', NULL, 6, 0.90),
(514, 'P1C', 'Corridors/Docks', NULL, 3, 0.88),
(514, 'S1A', 'Switching Controls', NULL, 20, 0.85),
(514, 'W1A', 'Wall-mounted', '10''-0" AFF', 5, 0.95),
(514, 'W2A', 'Wall-mounted', '14''-0" AFF', 3, 0.95),
(514, 'W1B', 'Wall-mounted', '20''-0" AFF', 4, 0.95),
(514, 'X3A', 'Exit/Emergency', NULL, 4, 0.90),
(514, 'X4A', 'Exit/Emergency', NULL, 5, 0.90),
(514, 'G1A', 'General', NULL, 2, 0.85),
(514, 'G2A', 'General', NULL, 2, 0.85),
(514, 'M1S', 'Mechanical Space', NULL, 2, 0.88),
(514, 'C1B', 'Under Platform', NULL, 6, 0.90),
(514, 'R1A', 'Recessed', NULL, 3, 0.88);

-- Insert circuits
INSERT INTO electrical_circuits (sheet_id, circuit_number, wire_size, conduit_size, notes, confidence) VALUES
(514, 'P2-Q14-5LTG2B/6', '1-#10, 1-#10, 1-#10G', '3/4"C', 'Lighting circuit', 0.95),
(514, 'P2-Q14-5LTG2B-11', '1-#8, 1-#8, 1-#8G', '3/4"C', 'Lighting circuit', 0.95),
(514, 'P2-Q14-5LTG2B/1', '1-#10, 1-#10, 1-#10G', '3/4"C', 'Lighting circuit', 0.95),
(514, 'P2-Q11-5UPS3A/8', '1-#10, 1-#10, 1-#10G', '3/4"C', 'UPS circuit', 0.95),
(514, 'P2-Q11-5UPS3A-10', NULL, NULL, 'UPS circuit', 0.75),
(514, 'P2-Q14-5LTG2B/18', NULL, NULL, 'Lighting circuit', 0.75),
(514, 'P2-Q11-5UPS3A-22', '1-#12, 1-#12, 1-#12G', '3/4"C', 'UPS circuit', 0.95);
