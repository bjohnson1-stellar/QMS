"""
License Notification System

Generates and manages notifications for expiring licenses, CE deadlines,
and renewal reminders. Designed to be run daily (via scheduled task) or on-demand.

Cloned from welding/notifications.py pattern.

Notification Types:
    - expiration_warning: License approaching expiration (30/60/90 days)
    - ce_deadline: CE credit period ending with incomplete hours
    - renewal_reminder: License needs renewal action (14 days)
"""

import sqlite3
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger("qms.licenses.notifications")


# ---------------------------------------------------------------------------
# Notification CRUD
# ---------------------------------------------------------------------------

def get_notification_rules(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Get active notification rules."""
    rows = conn.execute(
        """SELECT * FROM license_notification_rules
           WHERE is_active = 1
           ORDER BY days_before ASC"""
    ).fetchall()
    return [dict(row) for row in rows]


def create_notification(
    conn: sqlite3.Connection,
    notification_type: str,
    entity_type: str,
    entity_id: str,
    rule_id: int,
    priority: str,
    due_date: str,
    title: str,
    message: str,
) -> Optional[int]:
    """
    Create a notification if one doesn't already exist for this entity/rule.

    Args:
        entity_id: UUID string (matches state_licenses.id or ce_credits.id)
        due_date: ISO 8601 date string (YYYY-MM-DD)

    Returns:
        Notification ID or None if already exists
    """
    due_dt = datetime.strptime(due_date, "%Y-%m-%d").date()
    days_until_due = (due_dt - date.today()).days

    existing = conn.execute(
        """SELECT id FROM license_notifications
           WHERE entity_type = ? AND entity_id = ? AND rule_id = ? AND status = 'active'""",
        (entity_type, entity_id, rule_id),
    ).fetchone()

    if existing:
        return None

    cursor = conn.execute(
        """INSERT INTO license_notifications (
               notification_type, entity_type, entity_id, rule_id,
               priority, due_date, days_until_due, title, message, status
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
        (notification_type, entity_type, entity_id, rule_id,
         priority, due_date, days_until_due, title, message),
    )
    return cursor.lastrowid


def acknowledge_notification(
    conn: sqlite3.Connection,
    notification_id: int,
    acknowledged_by: str = "USER",
) -> bool:
    """Mark notification as acknowledged."""
    cursor = conn.execute(
        """UPDATE license_notifications
           SET status = 'acknowledged',
               acknowledged_by = ?,
               acknowledged_at = datetime('now')
           WHERE id = ? AND status = 'active'""",
        (acknowledged_by, notification_id),
    )
    return cursor.rowcount > 0


def resolve_notification(
    conn: sqlite3.Connection,
    notification_id: int,
    resolved_by: str = "USER",
) -> bool:
    """Mark notification as resolved."""
    cursor = conn.execute(
        """UPDATE license_notifications
           SET status = 'resolved',
               resolved_by = ?,
               resolved_at = datetime('now')
           WHERE id = ? AND status IN ('active', 'acknowledged')""",
        (resolved_by, notification_id),
    )
    return cursor.rowcount > 0


def cleanup_old_notifications(conn: sqlite3.Connection, days_old: int = 90) -> int:
    """Delete resolved notifications older than specified days."""
    cursor = conn.execute(
        """DELETE FROM license_notifications
           WHERE status IN ('resolved', 'auto_resolved')
             AND resolved_at < datetime('now', '-' || ? || ' days')""",
        (days_old,),
    )
    return cursor.rowcount


def update_days_until_due(conn: sqlite3.Connection) -> int:
    """Refresh days_until_due for all active notifications."""
    cursor = conn.execute(
        """UPDATE license_notifications
           SET days_until_due = CAST(JULIANDAY(due_date) - JULIANDAY(DATE('now')) AS INTEGER)
           WHERE status IN ('active', 'acknowledged')"""
    )
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Notification generation
# ---------------------------------------------------------------------------

def generate_expiration_notifications(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Generate notifications for expiring licenses.

    Queries active licenses with expiration dates within each rule's window.
    """
    stats = {"created": 0, "skipped": 0}

    rules = get_notification_rules(conn)
    exp_rules = [r for r in rules if r["notification_type"] == "expiration_warning"]

    for rule in exp_rules:
        rows = conn.execute(
            """SELECT
                   sl.id,
                   sl.holder_name,
                   sl.state_code,
                   sl.license_number,
                   sl.license_type,
                   sl.expiration_date,
                   CAST(JULIANDAY(sl.expiration_date) - JULIANDAY(DATE('now'))
                        AS INTEGER) as days_remaining
               FROM state_licenses sl
               WHERE sl.status = 'active'
                 AND sl.expiration_date IS NOT NULL
                 AND sl.expiration_date
                     BETWEEN DATE('now') AND DATE('now', '+' || ? || ' days')""",
            (rule["days_before"],),
        ).fetchall()

        for lic in rows:
            title = (
                f"License Expiring: {lic['holder_name']} "
                f"({lic['state_code']}) #{lic['license_number']}"
            )
            message = (
                f"{lic['holder_name']}'s {lic['license_type']} license "
                f"({lic['state_code']} #{lic['license_number']}) expires on "
                f"{lic['expiration_date']} ({lic['days_remaining']} days). "
                f"Submit renewal application to avoid lapse."
            )

            result = create_notification(
                conn,
                notification_type=rule["notification_type"],
                entity_type="license",
                entity_id=lic["id"],
                rule_id=rule["id"],
                priority=rule["priority"],
                due_date=lic["expiration_date"],
                title=title,
                message=message,
            )

            if result:
                stats["created"] += 1
            else:
                stats["skipped"] += 1

    return stats


def generate_ce_deadline_notifications(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Generate notifications for approaching CE deadlines with incomplete hours.

    Checks ce_requirements period end dates and compares earned vs required.
    """
    stats = {"created": 0, "skipped": 0}

    rules = get_notification_rules(conn)
    ce_rules = [r for r in rules if r["notification_type"] == "ce_deadline"]

    for rule in ce_rules:
        # Find licenses with CE requirements where the period is ending soon
        # and credits are incomplete.
        # Period end = license expiration_date (CE must be done before renewal)
        rows = conn.execute(
            """SELECT
                   sl.id as license_id,
                   sl.holder_name,
                   sl.state_code,
                   sl.license_number,
                   sl.license_type,
                   sl.expiration_date,
                   cr.hours_required,
                   COALESCE(earned.total_hours, 0) as hours_earned,
                   cr.hours_required - COALESCE(earned.total_hours, 0) as hours_needed,
                   CAST(JULIANDAY(sl.expiration_date) - JULIANDAY(DATE('now'))
                        AS INTEGER) as days_remaining
               FROM state_licenses sl
               JOIN ce_requirements cr
                   ON sl.state_code = cr.state_code
                   AND sl.license_type = cr.license_type
               LEFT JOIN (
                   SELECT license_id, SUM(hours) as total_hours
                   FROM ce_credits
                   WHERE status = 'approved'
                   GROUP BY license_id
               ) earned ON earned.license_id = sl.id
               WHERE sl.status = 'active'
                 AND sl.expiration_date IS NOT NULL
                 AND sl.expiration_date
                     BETWEEN DATE('now') AND DATE('now', '+' || ? || ' days')
                 AND COALESCE(earned.total_hours, 0) < cr.hours_required""",
            (rule["days_before"],),
        ).fetchall()

        for row in rows:
            title = (
                f"CE Deadline: {row['holder_name']} "
                f"({row['state_code']}) - {row['hours_needed']:.0f} hrs needed"
            )
            message = (
                f"{row['holder_name']}'s {row['license_type']} license "
                f"({row['state_code']} #{row['license_number']}) requires "
                f"{row['hours_required']:.0f} CE hours by {row['expiration_date']}. "
                f"Currently {row['hours_earned']:.0f} of {row['hours_required']:.0f} hours "
                f"completed — {row['hours_needed']:.0f} hours still needed "
                f"({row['days_remaining']} days remaining)."
            )

            result = create_notification(
                conn,
                notification_type=rule["notification_type"],
                entity_type="ce_credit",
                entity_id=row["license_id"],
                rule_id=rule["id"],
                priority=rule["priority"],
                due_date=row["expiration_date"],
                title=title,
                message=message,
            )

            if result:
                stats["created"] += 1
            else:
                stats["skipped"] += 1

    return stats


def generate_renewal_reminder_notifications(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Generate renewal reminders for licenses needing action.

    Targets licenses with renewal_pending status OR active licenses very
    close to expiration (within rule window).
    """
    stats = {"created": 0, "skipped": 0}

    rules = get_notification_rules(conn)
    renewal_rules = [r for r in rules if r["notification_type"] == "renewal_reminder"]

    for rule in renewal_rules:
        # Licenses in renewal_pending status (any expiration date)
        # OR active licenses within the tight window
        rows = conn.execute(
            """SELECT
                   sl.id,
                   sl.holder_name,
                   sl.state_code,
                   sl.license_number,
                   sl.license_type,
                   sl.expiration_date,
                   sl.status as license_status,
                   CASE
                       WHEN sl.expiration_date IS NOT NULL
                       THEN CAST(JULIANDAY(sl.expiration_date) - JULIANDAY(DATE('now'))
                                 AS INTEGER)
                       ELSE NULL
                   END as days_remaining
               FROM state_licenses sl
               WHERE (
                   sl.status = 'active'
                   AND sl.expiration_date IS NOT NULL
                   AND sl.expiration_date
                       BETWEEN DATE('now') AND DATE('now', '+' || ? || ' days')
               )""",
            (rule["days_before"],),
        ).fetchall()

        for lic in rows:
            title = (
                f"Renewal Needed: {lic['holder_name']} "
                f"({lic['state_code']}) #{lic['license_number']}"
            )
            days_str = f" ({lic['days_remaining']} days)" if lic["days_remaining"] is not None else ""
            message = (
                f"{lic['holder_name']}'s {lic['license_type']} license "
                f"({lic['state_code']} #{lic['license_number']}) needs renewal. "
                f"Expiration: {lic['expiration_date']}{days_str}. "
                f"Submit renewal application to the state board."
            )

            result = create_notification(
                conn,
                notification_type=rule["notification_type"],
                entity_type="license",
                entity_id=lic["id"],
                rule_id=rule["id"],
                priority=rule["priority"],
                due_date=lic["expiration_date"] or date.today().isoformat(),
                title=title,
                message=message,
            )

            if result:
                stats["created"] += 1
            else:
                stats["skipped"] += 1

    return stats


def generate_all_notifications(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Generate all notification types and refresh countdowns.

    Args:
        conn: Database connection (caller manages transaction)

    Returns:
        Dict with per-type and total counts
    """
    update_days_until_due(conn)

    exp_stats = generate_expiration_notifications(conn)
    ce_stats = generate_ce_deadline_notifications(conn)
    renewal_stats = generate_renewal_reminder_notifications(conn)

    total_stats = {
        "expiration_created": exp_stats["created"],
        "ce_created": ce_stats["created"],
        "renewal_created": renewal_stats["created"],
        "total_created": exp_stats["created"] + ce_stats["created"] + renewal_stats["created"],
        "total_skipped": exp_stats["skipped"] + ce_stats["skipped"] + renewal_stats["skipped"],
    }

    logger.info(
        "Notifications generated: %d expiration, %d CE, %d renewal (%d total, %d skipped)",
        total_stats["expiration_created"],
        total_stats["ce_created"],
        total_stats["renewal_created"],
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
    """List active notifications sorted by priority and due date."""
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
           FROM license_notifications n
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


def get_notification_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Get notification summary for dashboard display."""
    summary: Dict[str, Any] = {}

    # By status
    rows = conn.execute(
        "SELECT status, COUNT(*) as count FROM license_notifications GROUP BY status"
    ).fetchall()
    summary["by_status"] = {row["status"]: row["count"] for row in rows}

    # By priority (active only)
    rows = conn.execute(
        """SELECT priority, COUNT(*) as count
           FROM license_notifications WHERE status = 'active'
           GROUP BY priority"""
    ).fetchall()
    summary["by_priority"] = {row["priority"]: row["count"] for row in rows}

    # By type (active only)
    rows = conn.execute(
        """SELECT notification_type, COUNT(*) as count
           FROM license_notifications WHERE status = 'active'
           GROUP BY notification_type"""
    ).fetchall()
    summary["by_type"] = {row["notification_type"]: row["count"] for row in rows}

    # Urgent items
    rows = conn.execute(
        """SELECT id, title, due_date, days_until_due
           FROM license_notifications
           WHERE status = 'active' AND priority = 'urgent'
           ORDER BY due_date
           LIMIT 10"""
    ).fetchall()
    summary["urgent"] = [dict(row) for row in rows]

    return summary
