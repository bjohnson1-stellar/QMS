-- SQL Fixes for Validation Issues
-- Project 07645 (Vital Farms)
-- Generated: 2026-02-03

-- ============================================================================
-- FIX 1: Normalize item_type to lowercase
-- ============================================================================

-- Preview items that will be changed
SELECT item_type, COUNT(*) as count
FROM spec_items
WHERE spec_id IN (SELECT id FROM specifications WHERE project_id = 2)
  AND item_type != LOWER(item_type)
GROUP BY item_type
ORDER BY count DESC;

-- Apply normalization (uncomment to execute)
-- UPDATE spec_items
-- SET item_type = LOWER(item_type)
-- WHERE spec_id IN (SELECT id FROM specifications WHERE project_id = 2);

-- ============================================================================
-- FIX 2: Consolidate test-related types
-- ============================================================================

-- Map test_req -> test
-- UPDATE spec_items
-- SET item_type = 'test'
-- WHERE item_type = 'test_req'
--   AND spec_id IN (SELECT id FROM specifications WHERE project_id = 2);

-- Map test_requirement -> test
-- UPDATE spec_items
-- SET item_type = 'test'
-- WHERE item_type = 'test_requirement'
--   AND spec_id IN (SELECT id FROM specifications WHERE project_id = 2);

-- ============================================================================
-- FIX 3: Fix revision format (space -> underscore)
-- ============================================================================

-- Preview specs with space in revision
SELECT id, spec_number, revision
FROM specifications
WHERE project_id = 2
  AND revision LIKE 'Rev %';

-- Apply fix (uncomment to execute)
-- UPDATE specifications
-- SET revision = REPLACE(revision, 'Rev ', 'Rev_')
-- WHERE project_id = 2
--   AND revision LIKE 'Rev %';

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check item_type distribution after normalization
SELECT item_type, COUNT(*) as count
FROM spec_items
WHERE spec_id IN (SELECT id FROM specifications WHERE project_id = 2)
GROUP BY item_type
ORDER BY count DESC;

-- Check revision formats after fix
SELECT DISTINCT revision
FROM specifications
WHERE project_id = 2
ORDER BY revision;

-- Verify no case inconsistencies remain
SELECT LOWER(item_type) as normalized,
       COUNT(DISTINCT item_type) as variant_count,
       GROUP_CONCAT(DISTINCT item_type) as variants
FROM spec_items
WHERE spec_id IN (SELECT id FROM specifications WHERE project_id = 2)
GROUP BY LOWER(item_type)
HAVING COUNT(DISTINCT item_type) > 1;

-- ============================================================================
-- QUALITY MONITORING QUERIES
-- ============================================================================

-- Specs below quality threshold
SELECT spec_number, title, quality_score,
       (SELECT COUNT(*) FROM spec_items WHERE spec_id = s.id) as item_count
FROM specifications s
WHERE project_id = 2
  AND quality_score < 0.92
ORDER BY quality_score ASC;

-- Specs with unusually low item counts
SELECT spec_number, title, quality_score,
       (SELECT COUNT(*) FROM spec_items WHERE spec_id = s.id) as item_count
FROM specifications s
WHERE project_id = 2
  AND (SELECT COUNT(*) FROM spec_items WHERE spec_id = s.id) < 6
ORDER BY item_count ASC;

-- Item type distribution summary
SELECT 
    CASE
        WHEN item_type IN ('procedure', 'PROCEDURE') THEN 'procedure'
        WHEN item_type IN ('code_reference', 'CODE_REFERENCE') THEN 'code_reference'
        WHEN item_type IN ('material', 'MATERIAL') THEN 'material'
        WHEN item_type IN ('test', 'TEST', 'test_req', 'test_requirement') THEN 'test'
        WHEN item_type IN ('dimensional', 'DIMENSIONAL') THEN 'dimensional'
        ELSE item_type
    END as normalized_type,
    COUNT(*) as count
FROM spec_items
WHERE spec_id IN (SELECT id FROM specifications WHERE project_id = 2)
GROUP BY normalized_type
ORDER BY count DESC;
