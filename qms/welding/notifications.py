"""
Welding Notification System

Generates and manages notifications for WPQ/BPQR expirations and
continuity risks. Designed to be run daily (via scheduled task) or on-demand.

Notification Types:
    - wpq_expiration: WPQ approaching expiration (30/14/7 days)
    - bpqr_expiration: BPQR approaching expiration
    - continuity_at_risk: No production welds in 5+ months
"""

import sqlite3
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger("qms.welding.notifications")


# ---------------------------------------------------------------------------
# Notification CRUD
# ---------------------------------------------------------------------------

def get_notification_rules(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Get active notification rules."""
    rows = conn.execute(
        """SELECT * FROM weld_notification_rules
           WHERE is_active = 1
           ORDER BY days_before ASC"""
    ).fetchall()
    return [dict(row) for row in rows]


def create_notification(
    conn: sqlite3.Connection,
    notification_type: str,
    entity_type: str,
    entity_id: int,
    rule_id: int,
    priority: str,
    due_date: date,
    title: str,
    message: str,
) -> Optional[int]:
    """
    Create a notification if one doesn't already exist for this entity/rule.

    Args:
        conn: Database connection
        notification_type: Type of notification
        entity_type: Type of entity (wpq, bpqr, continuity)
        entity_id: ID of the entity
        rule_id: Notification rule ID
        priority: Priority level (urgent, high, normal, low)
        due_date: When the notification is due
        title: Notification title
        message: Notification body

    Returns:
        Notification ID or None if already exists
    """
    days_until_due = (due_date - date.today()).days

    existing = conn.execute(
        """SELECT id FROM weld_notifications
           WHERE entity_type = ? AND entity_id = ? AND rule_id = ? AND status = 'active'""",
        (entity_type, entity_id, rule_id),
    ).fetchone()

    if existing:
        return None

    cursor = conn.execute(
        """INSERT INTO weld_notifications (
               notification_type, entity_type, entity_id, rule_id,
               priority, due_date, days_until_due, title, message, status
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
        (notification_type, entity_type, entity_id, rule_id,
         priority, due_date, days_until_due, title, message),
    )
    conn.commit()
    return cursor.lastrowid


def acknowledge_notification(
    conn: sqlite3.Connection,
    notification_id: int,
    acknowledged_by: str = "USER",
) -> bool:
    """
    Mark notification as acknowledged.

    Returns:
        True if notification was updated
    """
    conn.execute(
        """UPDATE weld_notifications
           SET status = 'acknowledged',
               acknowledged_by = ?,
               acknowledged_at = CURRENT_TIMESTAMP
           WHERE id = ? AND status = 'active'""",
        (acknowledged_by, notification_id),
    )
    conn.commit()
    return conn.total_changes > 0


def resolve_notification(
    conn: sqlite3.Connection,
    notification_id: int,
    resolved_by: str = "USER",
) -> bool:
    """
    Mark notification as resolved.

    Returns:
        True if notification was updated
    """
    conn.execute(
        """UPDATE weld_notifications
           SET status = 'resolved',
               resolved_by = ?,
               resolved_at = CURRENT_TIMESTAMP
           WHERE id = ? AND status IN ('active', 'acknowledged')""",
        (resolved_by, notification_id),
    )
    conn.commit()
    return conn.total_changes > 0


def cleanup_old_notifications(conn: sqlite3.Connection, days_old: int = 90) -> int:
    """
    Delete resolved notifications older than specified days.

    Args:
        conn: Database connection
        days_old: Age threshold in days

    Returns:
        Number of notifications deleted
    """
    cursor = conn.execute(
        """DELETE FROM weld_notifications
           WHERE status IN ('resolved', 'auto_resolved')
             AND resolved_at < DATE('now', '-' || ? || ' days')""",
        (days_old,),
    )
    conn.commit()
    return cursor.rowcount


def update_days_until_due(conn: sqlite3.Connection) -> int:
    """
    Refresh days_until_due for all active notifications.

    Returns:
        Number of notifications updated
    """
    cursor = conn.execute(
        """UPDATE weld_notifications
           SET days_until_due = CAST(JULIANDAY(due_date) - JULIANDAY(DATE('now')) AS INTEGER)
           WHERE status = 'active'"""
    )
    conn.commit()
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Notification generation
# ---------------------------------------------------------------------------

def generate_wpq_expiration_notifications(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Generate notifications for expiring WPQs.

    Returns:
        Dict with created and skipped counts
    """
    stats = {"created": 0, "skipped": 0}

    rules = get_notification_rules(conn)
    wpq_rules = [r for r in rules if r["entity_type"] == "wpq"]

    for rule in wpq_rules:
        rows = conn.execute(
            """SELECT
                   wpq.id,
                   wpq.wpq_number,
                   wpq.process_type,
                   wpq.current_expiration_date,
                   wr.welder_stamp,
                   wr.display_name,
                   CAST(JULIANDAY(wpq.current_expiration_date) - JULIANDAY(DATE('now'))
                        AS INTEGER) as days_remaining
               FROM weld_wpq wpq
               JOIN weld_welder_registry wr ON wpq.welder_id = wr.id
               WHERE wpq.status = 'active'
                 AND wr.status = 'active'
                 AND wpq.current_expiration_date IS NOT NULL
                 AND wpq.current_expiration_date
                     BETWEEN DATE('now') AND DATE('now', '+' || ? || ' days')""",
            (rule["days_before"],),
        ).fetchall()

        for wpq in rows:
            title = f"WPQ Expiring: {wpq['welder_stamp']} - {wpq['process_type']}"
            message = (
                f"Welder {wpq['display_name']} ({wpq['welder_stamp']}) has a "
                f"{wpq['process_type']} WPQ ({wpq['wpq_number']}) expiring on "
                f"{wpq['current_expiration_date']} ({wpq['days_remaining']} days). "
                f"Production welding will automatically extend continuity."
            )

            result = create_notification(
                conn,
                notification_type=rule["notification_type"],
                entity_type="wpq",
                entity_id=wpq["id"],
                rule_id=rule["id"],
                priority=rule["priority"],
                due_date=datetime.strptime(wpq["current_expiration_date"], "%Y-%m-%d").date(),
                title=title,
                message=message,
            )

            if result:
                stats["created"] += 1
            else:
                stats["skipped"] += 1

    return stats


def generate_bpqr_expiration_notifications(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Generate notifications for expiring BPQRs.

    Returns:
        Dict with created and skipped counts
    """
    stats = {"created": 0, "skipped": 0}

    rules = get_notification_rules(conn)
    bpqr_rules = [r for r in rules if r["entity_type"] == "bpqr"]

    for rule in bpqr_rules:
        rows = conn.execute(
            """SELECT
                   bpqr.id,
                   bpqr.bpqr_number,
                   bpqr.brazing_process,
                   bpqr.current_expiration_date,
                   wr.welder_stamp,
                   wr.display_name,
                   CAST(JULIANDAY(bpqr.current_expiration_date) - JULIANDAY(DATE('now'))
                        AS INTEGER) as days_remaining
               FROM weld_bpqr bpqr
               JOIN weld_welder_registry wr ON bpqr.welder_id = wr.id
               WHERE bpqr.status = 'active'
                 AND wr.status = 'active'
                 AND bpqr.current_expiration_date IS NOT NULL
                 AND bpqr.current_expiration_date
                     BETWEEN DATE('now') AND DATE('now', '+' || ? || ' days')""",
            (rule["days_before"],),
        ).fetchall()

        for bpqr in rows:
            title = f"BPQR Expiring: {bpqr['welder_stamp']} - {bpqr['brazing_process']}"
            message = (
                f"Brazer {bpqr['display_name']} ({bpqr['welder_stamp']}) has a "
                f"{bpqr['brazing_process']} BPQR ({bpqr['bpqr_number']}) expiring on "
                f"{bpqr['current_expiration_date']} ({bpqr['days_remaining']} days)."
            )

            result = create_notification(
                conn,
                notification_type=rule["notification_type"],
                entity_type="bpqr",
                entity_id=bpqr["id"],
                rule_id=rule["id"],
                priority=rule["priority"],
                due_date=datetime.strptime(bpqr["current_expiration_date"], "%Y-%m-%d").date(),
                title=title,
                message=message,
            )

            if result:
                stats["created"] += 1
            else:
                stats["skipped"] += 1

    return stats


def generate_continuity_at_risk_notifications(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Generate notifications for welders at risk of losing continuity.

    Checks for welders with active WPQs but no recent production welds
    within the time window defined by notification rules.

    Returns:
        Dict with created and skipped counts
    """
    stats = {"created": 0, "skipped": 0}

    rules = get_notification_rules(conn)
    continuity_rules = [r for r in rules if r["entity_type"] == "continuity"]

    # Check which continuity table is available
    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='weld_continuity_events'"
    ).fetchone()
    use_events_table = table_check is not None

    for rule in continuity_rules:
        if use_events_table:
            rows = conn.execute(
                """SELECT
                       wpq.welder_id,
                       wr.welder_stamp,
                       wr.display_name,
                       wpq.process_type,
                       MAX(ce.event_date) as last_weld_date,
                       DATE(MAX(ce.event_date), '+6 months') as continuity_expires,
                       CAST(JULIANDAY(DATE(MAX(ce.event_date), '+6 months'))
                            - JULIANDAY(DATE('now')) AS INTEGER) as days_remaining
                   FROM weld_wpq wpq
                   JOIN weld_welder_registry wr ON wpq.welder_id = wr.id
                   LEFT JOIN weld_continuity_events ce
                       ON wpq.welder_id = ce.welder_id
                   LEFT JOIN weld_continuity_event_processes ep
                       ON ce.id = ep.event_id
                       AND wpq.process_type = ep.process_type
                   WHERE wpq.status = 'active'
                     AND wr.status = 'active'
                   GROUP BY wpq.welder_id, wpq.process_type
                   HAVING last_weld_date IS NOT NULL
                     AND DATE(MAX(ce.event_date), '+6 months')
                         BETWEEN DATE('now') AND DATE('now', '+' || ? || ' days')""",
                (rule["days_before"],),
            ).fetchall()
        else:
            # Fallback to production_welds table
            rows = conn.execute(
                """SELECT
                       wpq.welder_id,
                       wr.welder_stamp,
                       wr.display_name,
                       wpq.process_type,
                       MAX(pw.weld_date) as last_weld_date,
                       DATE(MAX(pw.weld_date), '+6 months') as continuity_expires,
                       CAST(JULIANDAY(DATE(MAX(pw.weld_date), '+6 months'))
                            - JULIANDAY(DATE('now')) AS INTEGER) as days_remaining
                   FROM weld_wpq wpq
                   JOIN weld_welder_registry wr ON wpq.welder_id = wr.id
                   LEFT JOIN weld_production_welds pw
                       ON wpq.welder_id = pw.welder_id
                       AND wpq.process_type = pw.process_type
                   WHERE wpq.status = 'active'
                     AND wr.status = 'active'
                   GROUP BY wpq.welder_id, wpq.process_type
                   HAVING last_weld_date IS NOT NULL
                     AND DATE(MAX(pw.weld_date), '+6 months')
                         BETWEEN DATE('now') AND DATE('now', '+' || ? || ' days')""",
                (rule["days_before"],),
            ).fetchall()

        for row in rows:
            title = f"Continuity At Risk: {row['welder_stamp']} - {row['process_type']}"
            message = (
                f"Welder {row['display_name']} ({row['welder_stamp']}) hasn't had a "
                f"{row['process_type']} production weld since {row['last_weld_date']}. "
                f"Continuity expires {row['continuity_expires']} ({row['days_remaining']} days). "
                f"Assign to a job using this process to maintain qualification."
            )

            result = create_notification(
                conn,
                notification_type="continuity_at_risk",
                entity_type="continuity",
                entity_id=row["welder_id"],
                rule_id=rule["id"],
                priority=rule["priority"],
                due_date=datetime.strptime(row["continuity_expires"], "%Y-%m-%d").date(),
                title=title,
                message=message,
            )

            if result:
                stats["created"] += 1
            else:
                stats["skipped"] += 1

    return stats


def generate_all_notifications() -> Dict[str, Any]:
    """
    Generate all notification types.

    Opens a database connection, refreshes existing notification
    days_until_due, then generates WPQ, BPQR, and continuity notifications.

    Returns:
        Dict with per-type and total counts
    """
    total_stats: Dict[str, Any] = {
        "wpq_created": 0,
        "bpqr_created": 0,
        "continuity_created": 0,
        "total_created": 0,
        "total_skipped": 0,
    }

    with get_db() as conn:
        update_days_until_due(conn)

        wpq_stats = generate_wpq_expiration_notifications(conn)
        total_stats["wpq_created"] = wpq_stats["created"]
        total_stats["total_created"] += wpq_stats["created"]
        total_stats["total_skipped"] += wpq_stats["skipped"]

        bpqr_stats = generate_bpqr_expiration_notifications(conn)
        total_stats["bpqr_created"] = bpqr_stats["created"]
        total_stats["total_created"] += bpqr_stats["created"]
        total_stats["total_skipped"] += bpqr_stats["skipped"]

        cont_stats = generate_continuity_at_risk_notifications(conn)
        total_stats["continuity_created"] = cont_stats["created"]
        total_stats["total_created"] += cont_stats["created"]
        total_stats["total_skipped"] += cont_stats["skipped"]

    logger.info(
        "Notifications generated: %d WPQ, %d BPQR, %d continuity (%d total, %d skipped)",
        total_stats["wpq_created"],
        total_stats["bpqr_created"],
        total_stats["continuity_created"],
        total_stats["total_created"],
        total_stats["total_skipped"],
    )
    return total_stats


# ---------------------------------------------------------------------------
# Query / display helpers
# ---------------------------------------------------------------------------

def list_active_notifications(
    conn: sqlite3.Connection, limit: int = 50
) -> List[Dict[str, Any]]:
    """
    List active notifications sorted by priority and due date.

    Args:
        conn: Database connection
        limit: Maximum number of results

    Returns:
        List of notification dicts
    """
    rows = conn.execute(
        """SELECT
               n.id,
               n.notification_type,
               n.entity_type,
               n.priority,
               n.title,
               n.due_date,
               n.days_until_due,
               n.status,
               n.created_at
           FROM weld_notifications n
           WHERE n.status IN ('active', 'acknowledged')
           ORDER BY
               CASE n.priority
                   WHEN 'urgent' THEN 1
                   WHEN 'high' THEN 2
                   WHEN 'normal' THEN 3
                   ELSE 4
               END,
               n.due_date
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_notification_summary() -> Dict[str, Any]:
    """
    Get notification summary for dashboard display.

    Returns:
        Dict with by_status, by_priority, by_type, and urgent items
    """
    summary: Dict[str, Any] = {}

    with get_db(readonly=True) as conn:
        # By status
        rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM weld_notifications GROUP BY status"
        ).fetchall()
        summary["by_status"] = {row["status"]: row["count"] for row in rows}

        # By priority (active only)
        rows = conn.execute(
            """SELECT priority, COUNT(*) as count
               FROM weld_notifications WHERE status = 'active'
               GROUP BY priority"""
        ).fetchall()
        summary["by_priority"] = {row["priority"]: row["count"] for row in rows}

        # By type (active only)
        rows = conn.execute(
            """SELECT notification_type, COUNT(*) as count
               FROM weld_notifications WHERE status = 'active'
               GROUP BY notification_type"""
        ).fetchall()
        summary["by_type"] = {row["notification_type"]: row["count"] for row in rows}

        # Urgent items
        rows = conn.execute(
            """SELECT id, title, due_date, days_until_due
               FROM weld_notifications
               WHERE status = 'active' AND priority = 'urgent'
               ORDER BY due_date
               LIMIT 10"""
        ).fetchall()
        summary["urgent"] = [dict(row) for row in rows]

    return summary
