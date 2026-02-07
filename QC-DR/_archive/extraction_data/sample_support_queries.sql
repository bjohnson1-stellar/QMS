-- Sample SQL Queries for Refrigeration Support Data
-- Project 07308-BIRDCAGE Support Details Database
-- Extracted from sheets R50211, R50220, R50221

-- ============================================================================
-- 1. FIND APPROPRIATE TRAPEZE HANGER FOR LOAD
-- ============================================================================
-- Example: Need to support 5,000 lbs of pipe at 4 ft width

SELECT
    detail_label as "Hanger Type",
    member_size as "Angle Size",
    rod_size as "Rod Size",
    max_load_lbs as "Max Load (lbs)",
    back_to_back as "Back-to-Back",
    notes
FROM support_details
WHERE detail_type IN ('trapeze_hanger', 'trapeze_hanger_3rod')
  AND max_load_lbs >= 5000
  AND width_or_span_ft = 4.0
ORDER BY max_load_lbs;

-- ============================================================================
-- 2. SELECT HANGER ROD SIZE FOR LOAD
-- ============================================================================
-- Example: Need rod to support 3,500 lbs

SELECT
    rod_size as "Rod Diameter",
    max_load_lbs as "Max Load (lbs)",
    member_size as "Thread Type",
    notes
FROM support_details
WHERE detail_type = 'hanger_rod'
  AND max_load_lbs >= 3500
ORDER BY max_load_lbs
LIMIT 1;

-- ============================================================================
-- 3. PIPE STAND UPRIGHT SELECTION
-- ============================================================================
-- Example: Need stand to support 10,000 lbs at 2 ft spacing

SELECT
    detail_label as "Type",
    member_type as "Member",
    member_size as "Size",
    max_load_lbs as "Max Load (lbs)",
    width_or_span_ft as "Spacing (ft)",
    notes
FROM support_details
WHERE detail_type IN ('pipe_stand_upright', 'pipe_stand_pipe_upright')
  AND max_load_lbs >= 10000
  AND (width_or_span_ft = 2.0 OR width_or_span_ft IS NULL)
ORDER BY max_load_lbs;

-- ============================================================================
-- 4. MATERIAL TAKEOFF - COUNT BY TYPE
-- ============================================================================
-- Get count of each support type extracted

SELECT
    detail_type as "Support Type",
    COUNT(*) as "Count",
    AVG(confidence) as "Avg Confidence"
FROM support_details
WHERE sheet_id IN (49, 50, 51)
GROUP BY detail_type
ORDER BY COUNT(*) DESC;

-- ============================================================================
-- 5. LOAD CAPACITY RANGES BY SUPPORT TYPE
-- ============================================================================

SELECT
    detail_type as "Support Type",
    COUNT(*) as "Variants",
    MIN(max_load_lbs) as "Min Load (lbs)",
    MAX(max_load_lbs) as "Max Load (lbs)",
    AVG(max_load_lbs) as "Avg Load (lbs)"
FROM support_details
WHERE max_load_lbs IS NOT NULL
GROUP BY detail_type
ORDER BY "Max Load (lbs)" DESC;

-- ============================================================================
-- 6. FIND SUPPORTS BY MEMBER SIZE
-- ============================================================================
-- Example: Show all supports using L4x4x3/8 angles

SELECT
    detail_type as "Type",
    detail_label as "Label",
    max_load_lbs as "Max Load (lbs)",
    width_or_span_ft as "Width/Span (ft)",
    notes
FROM support_details
WHERE member_size = 'L4x4x3/8'
ORDER BY detail_type, max_load_lbs;

-- ============================================================================
-- 7. CROSS-REFERENCE SHEETS AND SUPPORTS
-- ============================================================================

SELECT
    s.drawing_number as "Drawing",
    s.title as "Title",
    s.revision as "Rev",
    COUNT(sd.id) as "Details Extracted",
    s.quality_score as "Quality",
    s.extracted_at as "Extracted"
FROM sheets s
LEFT JOIN support_details sd ON sd.sheet_id = s.id
WHERE s.id IN (49, 50, 51)
GROUP BY s.id
ORDER BY s.id;

-- ============================================================================
-- 8. SPECIALTY SUPPORTS REFERENCE
-- ============================================================================

SELECT
    detail_type as "Type",
    detail_label as "Label/Model",
    member_size as "Specification",
    notes as "Description"
FROM support_details
WHERE detail_type IN ('clevis_hanger', 'riser_support', 'cmu_wall_support')
ORDER BY detail_type;

-- ============================================================================
-- 9. BACK-TO-BACK CONFIGURATIONS
-- ============================================================================
-- Show which hangers have back-to-back angles for higher loads

SELECT
    detail_label as "Type",
    member_size as "Angle Size",
    max_load_lbs as "Max Load (lbs)",
    rod_size as "Rod Size",
    back_to_back as "B2B",
    notes
FROM support_details
WHERE detail_type LIKE 'trapeze_hanger%'
ORDER BY back_to_back DESC, max_load_lbs;

-- ============================================================================
-- 10. BASE SUPPORT SELECTION
-- ============================================================================
-- Example: Need base for 3,000 lbs load

SELECT
    detail_label as "Type",
    member_size as "Sleeper Size",
    max_load_lbs as "Max Load (lbs)",
    notes
FROM support_details
WHERE detail_type = 'pipe_stand_base'
  AND max_load_lbs >= 3000
ORDER BY max_load_lbs;

-- ============================================================================
-- 11. SUPPORT EFFICIENCY ANALYSIS
-- ============================================================================
-- Calculate load capacity per unit weight (relative efficiency)
-- Note: Actual weights would need to be added to fully implement this

SELECT
    detail_type as "Type",
    detail_label as "Label",
    member_size as "Size",
    max_load_lbs as "Capacity (lbs)",
    CASE member_size
        WHEN 'L2x2x1/4' THEN max_load_lbs / 3.19  -- lbs per foot of angle
        WHEN 'L3x3x1/4' THEN max_load_lbs / 4.9
        WHEN 'L4x4x1/4' THEN max_load_lbs / 6.6
        WHEN 'L4x4x3/8' THEN max_load_lbs / 9.8
        WHEN 'L5x5x3/8' THEN max_load_lbs / 12.3
        ELSE NULL
    END as "Efficiency Ratio"
FROM support_details
WHERE detail_type LIKE 'trapeze_hanger%'
  AND max_load_lbs IS NOT NULL
ORDER BY "Efficiency Ratio" DESC;

-- ============================================================================
-- 12. LOW CONFIDENCE ITEMS FOR REVIEW
-- ============================================================================

SELECT
    s.drawing_number as "Drawing",
    sd.detail_type as "Type",
    sd.detail_label as "Label",
    sd.confidence as "Confidence",
    sd.notes as "Notes"
FROM support_details sd
JOIN sheets s ON s.id = sd.sheet_id
WHERE sd.confidence < 0.95
  AND sd.sheet_id IN (49, 50, 51)
ORDER BY sd.confidence, s.id;

-- ============================================================================
-- 13. COMPLETE SUPPORT CATALOG
-- ============================================================================

SELECT
    s.drawing_number as "Source",
    sd.detail_type as "Category",
    sd.detail_label as "Type/Label",
    sd.member_type as "Member",
    sd.member_size as "Size",
    sd.max_load_lbs as "Capacity (lbs)",
    sd.width_or_span_ft as "Width/Span (ft)",
    sd.rod_size as "Rod",
    sd.notes as "Notes"
FROM support_details sd
JOIN sheets s ON s.id = sd.sheet_id
WHERE sd.sheet_id IN (49, 50, 51)
ORDER BY sd.detail_type, sd.max_load_lbs;

-- ============================================================================
-- 14. EXPORT FOR ENGINEERING CALCULATIONS
-- ============================================================================
-- Create simplified table for load analysis

CREATE VIEW IF NOT EXISTS support_capacities AS
SELECT
    detail_type,
    detail_label,
    member_size,
    max_load_lbs,
    width_or_span_ft,
    rod_size,
    CASE WHEN back_to_back = 'Y' THEN 1 ELSE 0 END as is_back_to_back
FROM support_details
WHERE max_load_lbs IS NOT NULL
ORDER BY detail_type, max_load_lbs;

-- ============================================================================
-- 15. COMPARE 2-ROD VS 3-ROD TRAPEZE EFFICIENCY
-- ============================================================================

SELECT
    CASE
        WHEN detail_type = 'trapeze_hanger' THEN '2-Rod'
        WHEN detail_type = 'trapeze_hanger_3rod' THEN '3-Rod'
    END as "Configuration",
    member_size as "Angle Size",
    back_to_back as "Back-to-Back",
    max_load_lbs as "Capacity (lbs)",
    rod_size as "Rod Size"
FROM support_details
WHERE detail_type LIKE 'trapeze_hanger%'
  AND member_size = 'L4x4x3/8'
  AND back_to_back = 'Y'
ORDER BY detail_type;

-- ============================================================================
-- NOTES
-- ============================================================================
-- All loads are maximum capacities - apply appropriate safety factors
-- Values are for pipe only - do not apply to concentrated loads (valves, flanges)
-- Supports designed specifically for refrigeration piping
-- Refer to original drawings (R50211, R50220, R50221 Rev 3) for complete details
-- All supports assume proper installation per specifications
-- Galvanized finish required for corrosion protection
-- Field welds require cold-galvanized paint touch-up
