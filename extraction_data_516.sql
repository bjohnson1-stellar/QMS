-- Extraction for Sheet 516: EL1161 Area 6
-- Update sheet metadata
UPDATE sheets
SET drawing_type = 'lighting_plan',
    complexity = 'medium',
    extracted_at = datetime('now'),
    extraction_model = 'sonnet',
    quality_score = 0.89,
    title = 'PARTIAL FIRST FLOOR LIGHTING PLAN - AREA 6'
WHERE id = 516;

-- Insert lighting fixtures
INSERT INTO electrical_lighting_fixtures (sheet_id, fixture_type, location, mounting_height, qty, confidence) VALUES
(516, 'P1C', 'Corridors/Cold Storage', NULL, 40, 0.92),
(516, 'P1B', 'General/Packaging Areas', NULL, 50, 0.90),
(516, 'S1B', 'Switching Controls', NULL, 10, 0.85),
(516, 'W1A', 'Wall-mounted', '10''-0" AFF', 4, 0.95),
(516, 'W1B', 'Wall-mounted', '20''-0" AFF', 6, 0.95),
(516, 'W2A', 'Wall-mounted', '14''-0" AFF', 3, 0.95),
(516, 'W2A', 'Wall-mounted High Bay', '25''-0" AFF', 3, 0.95),
(516, 'X3A', 'Exit/Emergency', NULL, 4, 0.90),
(516, 'X4A', 'Exit/Emergency', NULL, 12, 0.90),
(516, 'G1B', 'General', NULL, 4, 0.85),
(516, 'G2A', 'General', NULL, 4, 0.85),
(516, 'F1A', 'Freezer-rated', 'Inclusion Freezer/Cooler', 5, 0.92);

-- Insert circuits
INSERT INTO electrical_circuits (sheet_id, circuit_number, wire_size, conduit_size, notes, confidence) VALUES
(516, 'P2-H14-5LTG2C/4', NULL, NULL, 'Lighting circuit @ 20''-0" AFF', 0.85),
(516, 'P2-H14-5LTG2C/19', NULL, NULL, 'Lighting circuit', 0.75),
(516, 'P2-H14-5LTG2C/2', NULL, NULL, 'Lighting circuit', 0.75),
(516, 'P2-H14-5LTG2C-3', '1-#10, 1-#10, 1-#10G', '3/4"C', 'Lighting circuit', 0.95),
(516, 'P2-Q11-5UPS3A/17', '1-#10, 1-#10, 1-#10G', '3/4"C', 'UPS circuit', 0.95),
(516, 'P2-Q11-5UPS3A/19', '1-#8, 1-#8, 1-#8G', '3/4"C', 'UPS circuit', 0.95),
(516, 'P2-Q14-5LTG2B/28', '1-#8, 1-#8, 1-#8G', '3/4"C', 'Lighting circuit', 0.95),
(516, 'P2-Q14-5LTG2B/26', '1-#12, 1-#12, 1-#12G', '3/4"C', 'Lighting circuit', 0.95),
(516, 'P2-Q14-5LTG2B/24', '1-#12, 1-#12, 1-#12G', '3/4"C', 'Lighting circuit', 0.95),
(516, 'P2-Q14-5LTG2B/27', '1-#12, 1-#12, 1-#12G', '3/4"C', 'Lighting circuit', 0.95),
(516, 'P2-Q11-5UPS3A/26', '1-#10, 1-#10, 1-#10G', '3/4"C', 'UPS circuit', 0.95),
(516, 'P2-Q14-5LTG2B/25', '1-#12, 1-#12, 1-#12G', '3/4"C', 'Lighting circuit', 0.95),
(516, 'P2-Q14-5LTG2B/23', '1-#12, 1-#12, 1-#12G', '3/4"C', 'Lighting circuit', 0.95),
(516, 'P2-Q11-5UPS3A-21', '1-#12, 1-#12, 1-#12G', '3/4"C', 'UPS circuit, circuited to existing', 0.95),
(516, 'P2-Q11-5UPS3A-14', '1-#8, 1-#8, 1-#8G', '3/4"C', 'UPS circuit', 0.95);
