-- ============================================================================
-- WELDING MODULE SCHEMA MIGRATION V2
-- ============================================================================
-- Enhancement: Production weld tracking, notifications, dashboard views
--
-- Run: sqlite3 d:\quality.db < D:\QC-DR\schema-welding-v2.sql
-- ============================================================================

-- ============================================================================
-- 1. ALTER EXISTING TABLES - Add Excel import fields to welder registry
-- ============================================================================

-- Check if columns exist before adding (SQLite doesn't support IF NOT EXISTS for ALTER)
-- We use PRAGMA to check and ignore errors on existing columns

-- Add Excel-specific fields to welder registry
ALTER TABLE weld_welder_registry ADD COLUMN preferred_name TEXT;
ALTER TABLE weld_welder_registry ADD COLUMN display_name TEXT;
ALTER TABLE weld_welder_registry ADD COLUMN business_unit TEXT;
ALTER TABLE weld_welder_registry ADD COLUMN running_total_welds INTEGER DEFAULT 0;
ALTER TABLE weld_welder_registry ADD COLUMN total_welds_tested INTEGER DEFAULT 0;
ALTER TABLE weld_welder_registry ADD COLUMN welds_passed INTEGER DEFAULT 0;
ALTER TABLE weld_welder_registry ADD COLUMN welds_failed INTEGER DEFAULT 0;
ALTER TABLE weld_welder_registry ADD COLUMN excel_row_hash TEXT;

-- ============================================================================
-- 2. NEW TABLES - Production Welds, Notifications, NDT Results
-- ============================================================================

-- Production Weld Tracking (enables automatic continuity)
-- Each production weld creates a continuity record automatically
CREATE TABLE IF NOT EXISTS weld_production_welds (
    id INTEGER PRIMARY KEY,
    welder_id INTEGER NOT NULL REFERENCES weld_welder_registry(id),
    weld_number TEXT,                           -- Site weld number if tracked
    project_number TEXT,                        -- Job/Project number
    process_type TEXT NOT NULL,                 -- SMAW, GTAW, GMAW, etc.
    wps_number TEXT,                            -- WPS used
    pipe_size TEXT,                             -- e.g., "NPS6", "2"
    position TEXT,                              -- 1G, 2G, 5G, 6G, etc.
    weld_date DATE NOT NULL,
    status TEXT DEFAULT 'complete',             -- complete, rejected, cut_out
    counts_for_continuity INTEGER DEFAULT 1,    -- 0 if rejected/cut_out
    week_ending DATE,                           -- For weekly batch imports
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    notes TEXT,

    -- Prevent duplicate imports for same welder/project/week
    UNIQUE(welder_id, project_number, week_ending) ON CONFLICT REPLACE
);

CREATE INDEX IF NOT EXISTS idx_prod_weld_welder ON weld_production_welds(welder_id);
CREATE INDEX IF NOT EXISTS idx_prod_weld_date ON weld_production_welds(weld_date);
CREATE INDEX IF NOT EXISTS idx_prod_weld_project ON weld_production_welds(project_number);
CREATE INDEX IF NOT EXISTS idx_prod_weld_week ON weld_production_welds(week_ending);
CREATE INDEX IF NOT EXISTS idx_prod_weld_process ON weld_production_welds(process_type);

-- Notification Rules (configurable thresholds)
CREATE TABLE IF NOT EXISTS weld_notification_rules (
    id INTEGER PRIMARY KEY,
    rule_name TEXT UNIQUE NOT NULL,             -- e.g., 'wpq_expiration_30d'
    notification_type TEXT NOT NULL,            -- expiration_warning, continuity_at_risk
    entity_type TEXT NOT NULL,                  -- wpq, bpqr, continuity
    days_before INTEGER NOT NULL,               -- Days before event to notify
    priority TEXT DEFAULT 'normal',             -- urgent, high, normal, low
    repeat_interval_days INTEGER,               -- Re-notify after this many days
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default notification rules
INSERT OR IGNORE INTO weld_notification_rules (rule_name, notification_type, entity_type, days_before, priority, repeat_interval_days)
VALUES
    ('wpq_expiration_30d', 'expiration_warning', 'wpq', 30, 'normal', 7),
    ('wpq_expiration_14d', 'expiration_warning', 'wpq', 14, 'high', 3),
    ('wpq_expiration_7d', 'expiration_warning', 'wpq', 7, 'urgent', 1),
    ('bpqr_expiration_30d', 'expiration_warning', 'bpqr', 30, 'normal', 7),
    ('bpqr_expiration_14d', 'expiration_warning', 'bpqr', 14, 'high', 3),
    ('bpqr_expiration_7d', 'expiration_warning', 'bpqr', 7, 'urgent', 1),
    ('continuity_at_risk_30d', 'continuity_at_risk', 'continuity', 30, 'high', 7);

-- Notification System
CREATE TABLE IF NOT EXISTS weld_notifications (
    id INTEGER PRIMARY KEY,
    notification_type TEXT NOT NULL,            -- expiration_warning, continuity_at_risk
    entity_type TEXT NOT NULL,                  -- wpq, bpqr, continuity
    entity_id INTEGER NOT NULL,                 -- ID in source table (wpq_id, bpqr_id, welder_id)
    rule_id INTEGER REFERENCES weld_notification_rules(id),
    priority TEXT DEFAULT 'normal',             -- urgent, high, normal, low
    due_date DATE,                              -- When the event occurs
    days_until_due INTEGER,                     -- Calculated days remaining
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT DEFAULT 'active',               -- active, acknowledged, resolved, auto_resolved
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMP,
    resolved_by TEXT,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate active notifications for same entity/type/rule
    UNIQUE(entity_type, entity_id, rule_id, status) ON CONFLICT REPLACE
);

CREATE INDEX IF NOT EXISTS idx_notif_status ON weld_notifications(status);
CREATE INDEX IF NOT EXISTS idx_notif_type ON weld_notifications(notification_type);
CREATE INDEX IF NOT EXISTS idx_notif_priority ON weld_notifications(priority);
CREATE INDEX IF NOT EXISTS idx_notif_due ON weld_notifications(due_date);

-- NDT Results (foundation for future weld quality tracking)
CREATE TABLE IF NOT EXISTS weld_ndt_results (
    id INTEGER PRIMARY KEY,
    production_weld_id INTEGER REFERENCES weld_production_welds(id),
    welder_id INTEGER REFERENCES weld_welder_registry(id),
    ndt_type TEXT NOT NULL,                     -- VT, PT, MT, RT, UT
    test_date DATE NOT NULL,
    result TEXT NOT NULL,                       -- Accept, Reject
    report_number TEXT,
    defect_type TEXT,                           -- Porosity, Lack of Fusion, etc.
    examiner_name TEXT,
    examiner_level TEXT,                        -- I, II, III
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ndt_weld ON weld_ndt_results(production_weld_id);
CREATE INDEX IF NOT EXISTS idx_ndt_welder ON weld_ndt_results(welder_id);
CREATE INDEX IF NOT EXISTS idx_ndt_result ON weld_ndt_results(result);
CREATE INDEX IF NOT EXISTS idx_ndt_date ON weld_ndt_results(test_date);

-- ============================================================================
-- 3. AUTOMATIC CONTINUITY TRIGGER
-- ============================================================================
-- When a production weld is added, auto-extend the WPQ expiration date
-- for matching process type

DROP TRIGGER IF EXISTS tr_production_weld_continuity;

CREATE TRIGGER tr_production_weld_continuity
AFTER INSERT ON weld_production_welds
WHEN NEW.counts_for_continuity = 1
BEGIN
    -- Update WPQ expiration dates for matching welder/process
    UPDATE weld_wpq
    SET current_expiration_date = DATE(NEW.weld_date, '+6 months'),
        updated_at = CURRENT_TIMESTAMP
    WHERE welder_id = NEW.welder_id
      AND process_type = NEW.process_type
      AND status = 'active'
      AND (current_expiration_date IS NULL
           OR current_expiration_date < DATE(NEW.weld_date, '+6 months'));

    -- Also create/update continuity log entry
    INSERT INTO weld_continuity_log (welder_id, process_type, activity_date, project_number, description)
    VALUES (NEW.welder_id, NEW.process_type, NEW.weld_date, NEW.project_number,
            'Auto-logged from production weld')
    ON CONFLICT DO NOTHING;
END;

-- Also auto-resolve expiration notifications when continuity is extended
DROP TRIGGER IF EXISTS tr_auto_resolve_notifications;

CREATE TRIGGER tr_auto_resolve_notifications
AFTER UPDATE OF current_expiration_date ON weld_wpq
WHEN NEW.current_expiration_date > OLD.current_expiration_date
BEGIN
    UPDATE weld_notifications
    SET status = 'auto_resolved',
        resolved_at = CURRENT_TIMESTAMP,
        resolved_by = 'SYSTEM'
    WHERE entity_type = 'wpq'
      AND entity_id = NEW.id
      AND status = 'active'
      AND due_date <= NEW.current_expiration_date;
END;

-- ============================================================================
-- 4. DASHBOARD VIEWS
-- ============================================================================

-- 4.1 Welder Dashboard Overview
DROP VIEW IF EXISTS v_weld_dashboard_welders;
CREATE VIEW v_weld_dashboard_welders AS
SELECT
    wr.id,
    wr.welder_stamp,
    wr.employee_number,
    COALESCE(wr.display_name, wr.last_name || ', ' || wr.first_name) as name,
    wr.status as employment_status,
    wr.department,
    wr.business_unit,
    -- WPQ counts
    (SELECT COUNT(*) FROM weld_wpq WHERE welder_id = wr.id AND status = 'active') as active_wpq_count,
    (SELECT COUNT(*) FROM weld_wpq WHERE welder_id = wr.id AND status = 'active'
     AND current_expiration_date < DATE('now')) as expired_wpq_count,
    (SELECT COUNT(*) FROM weld_wpq WHERE welder_id = wr.id AND status = 'active'
     AND current_expiration_date BETWEEN DATE('now') AND DATE('now', '+30 days')) as expiring_wpq_count,
    -- Process qualifications (comma-separated)
    (SELECT GROUP_CONCAT(process_type, ', ') FROM
     (SELECT DISTINCT process_type FROM weld_wpq WHERE welder_id = wr.id AND status = 'active')) as qualified_processes,
    -- Last activity
    (SELECT MAX(weld_date) FROM weld_production_welds WHERE welder_id = wr.id) as last_weld_date,
    (SELECT MAX(activity_date) FROM weld_continuity_log WHERE welder_id = wr.id) as last_continuity_date,
    -- Statistics
    COALESCE(wr.running_total_welds, 0) as total_welds,
    COALESCE(wr.welds_passed, 0) as welds_passed,
    COALESCE(wr.welds_failed, 0) as welds_failed,
    CASE
        WHEN COALESCE(wr.total_welds_tested, 0) = 0 THEN NULL
        ELSE ROUND(COALESCE(wr.welds_passed, 0) * 100.0 / wr.total_welds_tested, 1)
    END as pass_rate_pct
FROM weld_welder_registry wr
WHERE wr.status = 'active';

-- 4.2 Expiration Dashboard Summary
DROP VIEW IF EXISTS v_weld_dashboard_expirations;
CREATE VIEW v_weld_dashboard_expirations AS
WITH expiration_buckets AS (
    SELECT
        'wpq' as entity_type,
        CASE
            WHEN current_expiration_date < DATE('now') THEN 'expired'
            WHEN current_expiration_date < DATE('now', '+7 days') THEN '7d'
            WHEN current_expiration_date < DATE('now', '+30 days') THEN '30d'
            WHEN current_expiration_date < DATE('now', '+90 days') THEN '90d'
            ELSE 'ok'
        END as bucket,
        COUNT(*) as count
    FROM weld_wpq
    WHERE status = 'active'
    GROUP BY bucket
    UNION ALL
    SELECT
        'bpqr' as entity_type,
        CASE
            WHEN current_expiration_date < DATE('now') THEN 'expired'
            WHEN current_expiration_date < DATE('now', '+7 days') THEN '7d'
            WHEN current_expiration_date < DATE('now', '+30 days') THEN '30d'
            WHEN current_expiration_date < DATE('now', '+90 days') THEN '90d'
            ELSE 'ok'
        END as bucket,
        COUNT(*) as count
    FROM weld_bpqr
    WHERE status = 'active'
    GROUP BY bucket
)
SELECT
    entity_type,
    SUM(CASE WHEN bucket = 'expired' THEN count ELSE 0 END) as expired,
    SUM(CASE WHEN bucket = '7d' THEN count ELSE 0 END) as expiring_7d,
    SUM(CASE WHEN bucket = '30d' THEN count ELSE 0 END) as expiring_30d,
    SUM(CASE WHEN bucket = '90d' THEN count ELSE 0 END) as expiring_90d,
    SUM(CASE WHEN bucket = 'ok' THEN count ELSE 0 END) as current,
    SUM(count) as total
FROM expiration_buckets
GROUP BY entity_type;

-- 4.3 Process Coverage Dashboard
DROP VIEW IF EXISTS v_weld_dashboard_process_coverage;
CREATE VIEW v_weld_dashboard_process_coverage AS
SELECT
    process_type,
    COUNT(DISTINCT welder_id) as qualified_welders,
    COUNT(DISTINCT CASE WHEN status = 'active'
          AND (current_expiration_date IS NULL OR current_expiration_date >= DATE('now'))
          THEN welder_id END) as current_welders,
    COUNT(DISTINCT CASE WHEN status = 'active'
          AND current_expiration_date < DATE('now')
          THEN welder_id END) as expired_welders,
    COUNT(*) as total_wpqs,
    MIN(current_expiration_date) as earliest_expiration,
    MAX(current_expiration_date) as latest_expiration
FROM weld_wpq
WHERE status = 'active'
GROUP BY process_type
ORDER BY qualified_welders DESC;

-- 4.4 Active Notifications Dashboard
DROP VIEW IF EXISTS v_weld_dashboard_notifications;
CREATE VIEW v_weld_dashboard_notifications AS
SELECT
    n.id,
    n.notification_type,
    n.entity_type,
    n.priority,
    n.title,
    n.message,
    n.due_date,
    n.days_until_due,
    n.status,
    n.created_at,
    -- Join to get welder info (use explicit table aliases to avoid ambiguity)
    CASE n.entity_type
        WHEN 'wpq' THEN (SELECT wr.welder_stamp FROM weld_welder_registry wr
                         JOIN weld_wpq wpq ON wr.id = wpq.welder_id
                         WHERE wpq.id = n.entity_id)
        WHEN 'bpqr' THEN (SELECT wr.welder_stamp FROM weld_welder_registry wr
                          JOIN weld_bpqr bpqr ON wr.id = bpqr.welder_id
                          WHERE bpqr.id = n.entity_id)
        WHEN 'continuity' THEN (SELECT wr.welder_stamp FROM weld_welder_registry wr
                                WHERE wr.id = n.entity_id)
    END as welder_stamp,
    CASE n.entity_type
        WHEN 'wpq' THEN (SELECT wr.display_name FROM weld_welder_registry wr
                         JOIN weld_wpq wpq ON wr.id = wpq.welder_id
                         WHERE wpq.id = n.entity_id)
        WHEN 'bpqr' THEN (SELECT wr.display_name FROM weld_welder_registry wr
                          JOIN weld_bpqr bpqr ON wr.id = bpqr.welder_id
                          WHERE bpqr.id = n.entity_id)
        WHEN 'continuity' THEN (SELECT wr.display_name FROM weld_welder_registry wr
                                WHERE wr.id = n.entity_id)
    END as welder_name
FROM weld_notifications n
WHERE n.status = 'active'
ORDER BY
    CASE n.priority
        WHEN 'urgent' THEN 1
        WHEN 'high' THEN 2
        WHEN 'normal' THEN 3
        ELSE 4
    END,
    n.due_date;

-- 4.5 Continuity Status View (calculated from production welds)
DROP VIEW IF EXISTS v_weld_continuity_auto_status;
CREATE VIEW v_weld_continuity_auto_status AS
SELECT
    wr.id as welder_id,
    wr.welder_stamp,
    COALESCE(wr.display_name, wr.last_name || ', ' || wr.first_name) as name,
    pw.process_type,
    MAX(pw.weld_date) as last_production_weld,
    DATE(MAX(pw.weld_date), '+6 months') as continuity_expires,
    CAST(JULIANDAY(DATE(MAX(pw.weld_date), '+6 months')) - JULIANDAY(DATE('now')) AS INTEGER) as days_remaining,
    CASE
        WHEN MAX(pw.weld_date) IS NULL THEN 'NO_ACTIVITY'
        WHEN DATE(MAX(pw.weld_date), '+6 months') < DATE('now') THEN 'LAPSED'
        WHEN DATE(MAX(pw.weld_date), '+6 months') < DATE('now', '+30 days') THEN 'AT_RISK'
        ELSE 'CURRENT'
    END as continuity_status,
    COUNT(*) as welds_last_6mo,
    GROUP_CONCAT(DISTINCT pw.project_number) as projects
FROM weld_welder_registry wr
LEFT JOIN weld_production_welds pw ON wr.id = pw.welder_id
    AND pw.weld_date >= DATE('now', '-6 months')
    AND pw.counts_for_continuity = 1
WHERE wr.status = 'active'
GROUP BY wr.id, pw.process_type
HAVING pw.process_type IS NOT NULL OR MAX(pw.weld_date) IS NULL;

-- 4.6 Welder Full Qualification Matrix (enhanced)
DROP VIEW IF EXISTS v_weld_welder_full_matrix;
CREATE VIEW v_weld_welder_full_matrix AS
SELECT
    wr.id as welder_id,
    wr.welder_stamp,
    COALESCE(wr.display_name, wr.last_name || ', ' || wr.first_name) as name,
    wr.department,
    wr.status as employment_status,
    wpq.wpq_number,
    wpq.process_type,
    wpq.wps_number,
    wpq.p_number_base as p_number,
    wpq.f_number,
    wpq.groove_positions_qualified,
    wpq.fillet_positions_qualified,
    wpq.backing_type,
    wpq.thickness_qualified_min || ' - ' || wpq.thickness_qualified_max as thickness_range,
    wpq.diameter_qualified_min as min_diameter,
    wpq.test_date,
    wpq.current_expiration_date as expires,
    CAST(JULIANDAY(wpq.current_expiration_date) - JULIANDAY(DATE('now')) AS INTEGER) as days_until_expiration,
    CASE
        WHEN wpq.current_expiration_date < DATE('now') THEN 'EXPIRED'
        WHEN wpq.current_expiration_date < DATE('now', '+7 days') THEN 'URGENT'
        WHEN wpq.current_expiration_date < DATE('now', '+30 days') THEN 'EXPIRING'
        ELSE 'CURRENT'
    END as expiration_status,
    wpq.status as wpq_status
FROM weld_welder_registry wr
JOIN weld_wpq wpq ON wr.id = wpq.welder_id
ORDER BY wr.welder_stamp, wpq.process_type;

-- ============================================================================
-- 5. IMPORT TRACKING VIEW
-- ============================================================================

DROP VIEW IF EXISTS v_weld_import_summary;
CREATE VIEW v_weld_import_summary AS
SELECT
    DATE(created_at) as import_date,
    document_type,
    action,
    COUNT(*) as count
FROM weld_intake_log
GROUP BY DATE(created_at), document_type, action
ORDER BY import_date DESC, document_type;

-- ============================================================================
-- END OF MIGRATION V2
-- ============================================================================
