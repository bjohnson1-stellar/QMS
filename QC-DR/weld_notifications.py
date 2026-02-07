#!/usr/bin/env python3
"""
Welding Notification System

Generates notifications for WPQ/BPQR expirations and continuity risks.
Designed to be run daily (via scheduled task) or on-demand.

Features:
- Generates notifications based on configurable rules
- Supports different priority levels (urgent, high, normal)
- Acknowledging and resolving notifications
- Dashboard query support

Usage:
    python weld_notifications.py                    # Generate all notifications
    python weld_notifications.py --check            # List active notifications
    python weld_notifications.py --acknowledge 123  # Acknowledge notification
    python weld_notifications.py --resolve 123      # Resolve notification
    python weld_notifications.py --cleanup          # Remove old resolved notifications
    python weld_notifications.py --summary          # Dashboard summary

Notification Types:
- wpq_expiration: WPQ approaching expiration (30/14/7 days)
- bpqr_expiration: BPQR approaching expiration
- continuity_at_risk: No production welds in 5+ months

Created: 2026-02-05
"""

import sqlite3
import sys
import argparse
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = "D:/quality.db"

# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def get_db_connection() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def get_notification_rules(conn: sqlite3.Connection) -> List[Dict]:
    """Get active notification rules."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM weld_notification_rules
        WHERE is_active = 1
        ORDER BY days_before ASC
    """)
    return [dict(row) for row in cursor.fetchall()]


def create_notification(conn: sqlite3.Connection, notification_type: str,
                        entity_type: str, entity_id: int, rule_id: int,
                        priority: str, due_date: date, title: str,
                        message: str) -> Optional[int]:
    """
    Create a notification if one doesn't already exist.
    Returns notification ID or None if already exists.
    """
    cursor = conn.cursor()

    # Calculate days until due
    days_until_due = (due_date - date.today()).days

    # Check for existing active notification for same entity/rule
    cursor.execute("""
        SELECT id FROM weld_notifications
        WHERE entity_type = ? AND entity_id = ? AND rule_id = ? AND status = 'active'
    """, (entity_type, entity_id, rule_id))

    if cursor.fetchone():
        return None  # Already exists

    # Insert new notification
    cursor.execute("""
        INSERT INTO weld_notifications (
            notification_type, entity_type, entity_id, rule_id,
            priority, due_date, days_until_due, title, message, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
    """, (notification_type, entity_type, entity_id, rule_id,
          priority, due_date, days_until_due, title, message))

    conn.commit()
    return cursor.lastrowid


def acknowledge_notification(conn: sqlite3.Connection, notification_id: int,
                             acknowledged_by: str = 'USER') -> bool:
    """Mark notification as acknowledged."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE weld_notifications
        SET status = 'acknowledged',
            acknowledged_by = ?,
            acknowledged_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'active'
    """, (acknowledged_by, notification_id))
    conn.commit()
    return cursor.rowcount > 0


def resolve_notification(conn: sqlite3.Connection, notification_id: int,
                         resolved_by: str = 'USER') -> bool:
    """Mark notification as resolved."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE weld_notifications
        SET status = 'resolved',
            resolved_by = ?,
            resolved_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status IN ('active', 'acknowledged')
    """, (resolved_by, notification_id))
    conn.commit()
    return cursor.rowcount > 0


def cleanup_old_notifications(conn: sqlite3.Connection, days_old: int = 90) -> int:
    """Delete resolved notifications older than specified days."""
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM weld_notifications
        WHERE status IN ('resolved', 'auto_resolved')
          AND resolved_at < DATE('now', '-' || ? || ' days')
    """, (days_old,))
    conn.commit()
    return cursor.rowcount


def update_days_until_due(conn: sqlite3.Connection) -> int:
    """Update days_until_due for all active notifications."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE weld_notifications
        SET days_until_due = CAST(JULIANDAY(due_date) - JULIANDAY(DATE('now')) AS INTEGER)
        WHERE status = 'active'
    """)
    conn.commit()
    return cursor.rowcount


# =============================================================================
# NOTIFICATION GENERATION
# =============================================================================

def generate_wpq_expiration_notifications(conn: sqlite3.Connection) -> Dict:
    """Generate notifications for expiring WPQs."""
    stats = {'created': 0, 'skipped': 0}

    rules = get_notification_rules(conn)
    wpq_rules = [r for r in rules if r['entity_type'] == 'wpq']

    cursor = conn.cursor()

    for rule in wpq_rules:
        # Find WPQs expiring within rule threshold
        cursor.execute("""
            SELECT
                wpq.id,
                wpq.wpq_number,
                wpq.process_type,
                wpq.current_expiration_date,
                wr.welder_stamp,
                wr.display_name,
                CAST(JULIANDAY(wpq.current_expiration_date) - JULIANDAY(DATE('now')) AS INTEGER) as days_remaining
            FROM weld_wpq wpq
            JOIN weld_welder_registry wr ON wpq.welder_id = wr.id
            WHERE wpq.status = 'active'
              AND wr.status = 'active'
              AND wpq.current_expiration_date IS NOT NULL
              AND wpq.current_expiration_date BETWEEN DATE('now') AND DATE('now', '+' || ? || ' days')
        """, (rule['days_before'],))

        for wpq in cursor.fetchall():
            title = f"WPQ Expiring: {wpq['welder_stamp']} - {wpq['process_type']}"
            message = (
                f"Welder {wpq['display_name']} ({wpq['welder_stamp']}) has a "
                f"{wpq['process_type']} WPQ ({wpq['wpq_number']}) expiring on "
                f"{wpq['current_expiration_date']} ({wpq['days_remaining']} days). "
                f"Production welding will automatically extend continuity."
            )

            result = create_notification(
                conn,
                notification_type=rule['notification_type'],
                entity_type='wpq',
                entity_id=wpq['id'],
                rule_id=rule['id'],
                priority=rule['priority'],
                due_date=datetime.strptime(wpq['current_expiration_date'], '%Y-%m-%d').date(),
                title=title,
                message=message
            )

            if result:
                stats['created'] += 1
            else:
                stats['skipped'] += 1

    return stats


def generate_bpqr_expiration_notifications(conn: sqlite3.Connection) -> Dict:
    """Generate notifications for expiring BPQRs."""
    stats = {'created': 0, 'skipped': 0}

    rules = get_notification_rules(conn)
    bpqr_rules = [r for r in rules if r['entity_type'] == 'bpqr']

    cursor = conn.cursor()

    for rule in bpqr_rules:
        cursor.execute("""
            SELECT
                bpqr.id,
                bpqr.bpqr_number,
                bpqr.brazing_process,
                bpqr.current_expiration_date,
                wr.welder_stamp,
                wr.display_name,
                CAST(JULIANDAY(bpqr.current_expiration_date) - JULIANDAY(DATE('now')) AS INTEGER) as days_remaining
            FROM weld_bpqr bpqr
            JOIN weld_welder_registry wr ON bpqr.welder_id = wr.id
            WHERE bpqr.status = 'active'
              AND wr.status = 'active'
              AND bpqr.current_expiration_date IS NOT NULL
              AND bpqr.current_expiration_date BETWEEN DATE('now') AND DATE('now', '+' || ? || ' days')
        """, (rule['days_before'],))

        for bpqr in cursor.fetchall():
            title = f"BPQR Expiring: {bpqr['welder_stamp']} - {bpqr['brazing_process']}"
            message = (
                f"Brazer {bpqr['display_name']} ({bpqr['welder_stamp']}) has a "
                f"{bpqr['brazing_process']} BPQR ({bpqr['bpqr_number']}) expiring on "
                f"{bpqr['current_expiration_date']} ({bpqr['days_remaining']} days)."
            )

            result = create_notification(
                conn,
                notification_type=rule['notification_type'],
                entity_type='bpqr',
                entity_id=bpqr['id'],
                rule_id=rule['id'],
                priority=rule['priority'],
                due_date=datetime.strptime(bpqr['current_expiration_date'], '%Y-%m-%d').date(),
                title=title,
                message=message
            )

            if result:
                stats['created'] += 1
            else:
                stats['skipped'] += 1

    return stats


def generate_continuity_at_risk_notifications(conn: sqlite3.Connection) -> Dict:
    """Generate notifications for welders at risk of losing continuity."""
    stats = {'created': 0, 'skipped': 0}

    rules = get_notification_rules(conn)
    continuity_rules = [r for r in rules if r['entity_type'] == 'continuity']

    cursor = conn.cursor()

    for rule in continuity_rules:
        # Find welders with active WPQs but no recent production welds
        # Continuity is at risk if last weld was > (6 months - rule.days_before) ago
        risk_cutoff_days = 180 - rule['days_before']  # e.g., 180-30=150 days ago

        cursor.execute("""
            SELECT
                wpq.welder_id,
                wr.welder_stamp,
                wr.display_name,
                wpq.process_type,
                MAX(pw.weld_date) as last_weld_date,
                DATE(MAX(pw.weld_date), '+6 months') as continuity_expires,
                CAST(JULIANDAY(DATE(MAX(pw.weld_date), '+6 months')) - JULIANDAY(DATE('now')) AS INTEGER) as days_remaining
            FROM weld_wpq wpq
            JOIN weld_welder_registry wr ON wpq.welder_id = wr.id
            LEFT JOIN weld_production_welds pw
                ON wpq.welder_id = pw.welder_id
                AND wpq.process_type = pw.process_type
                AND pw.counts_for_continuity = 1
            WHERE wpq.status = 'active'
              AND wr.status = 'active'
            GROUP BY wpq.welder_id, wpq.process_type
            HAVING last_weld_date IS NOT NULL
              AND DATE(MAX(pw.weld_date), '+6 months') BETWEEN DATE('now') AND DATE('now', '+' || ? || ' days')
        """, (rule['days_before'],))

        for row in cursor.fetchall():
            title = f"Continuity At Risk: {row['welder_stamp']} - {row['process_type']}"
            message = (
                f"Welder {row['display_name']} ({row['welder_stamp']}) hasn't had a "
                f"{row['process_type']} production weld since {row['last_weld_date']}. "
                f"Continuity expires {row['continuity_expires']} ({row['days_remaining']} days). "
                f"Assign to a job using this process to maintain qualification."
            )

            result = create_notification(
                conn,
                notification_type='continuity_at_risk',
                entity_type='continuity',
                entity_id=row['welder_id'],
                rule_id=rule['id'],
                priority=rule['priority'],
                due_date=datetime.strptime(row['continuity_expires'], '%Y-%m-%d').date(),
                title=title,
                message=message
            )

            if result:
                stats['created'] += 1
            else:
                stats['skipped'] += 1

    return stats


def generate_all_notifications(conn: sqlite3.Connection) -> Dict:
    """Generate all notification types."""
    total_stats = {
        'wpq_created': 0,
        'bpqr_created': 0,
        'continuity_created': 0,
        'total_created': 0,
        'total_skipped': 0,
    }

    # Update days_until_due for existing notifications
    update_days_until_due(conn)

    # WPQ Expirations
    wpq_stats = generate_wpq_expiration_notifications(conn)
    total_stats['wpq_created'] = wpq_stats['created']
    total_stats['total_created'] += wpq_stats['created']
    total_stats['total_skipped'] += wpq_stats['skipped']

    # BPQR Expirations
    bpqr_stats = generate_bpqr_expiration_notifications(conn)
    total_stats['bpqr_created'] = bpqr_stats['created']
    total_stats['total_created'] += bpqr_stats['created']
    total_stats['total_skipped'] += bpqr_stats['skipped']

    # Continuity at Risk
    cont_stats = generate_continuity_at_risk_notifications(conn)
    total_stats['continuity_created'] = cont_stats['created']
    total_stats['total_created'] += cont_stats['created']
    total_stats['total_skipped'] += cont_stats['skipped']

    return total_stats


# =============================================================================
# DISPLAY FUNCTIONS
# =============================================================================

def list_active_notifications(conn: sqlite3.Connection, limit: int = 50) -> List[Dict]:
    """List active notifications."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
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
        LIMIT ?
    """, (limit,))

    return [dict(row) for row in cursor.fetchall()]


def get_notification_summary(conn: sqlite3.Connection) -> Dict:
    """Get notification summary for dashboard."""
    cursor = conn.cursor()

    summary = {}

    # By status
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM weld_notifications
        GROUP BY status
    """)
    summary['by_status'] = {row['status']: row['count'] for row in cursor.fetchall()}

    # By priority (active only)
    cursor.execute("""
        SELECT priority, COUNT(*) as count
        FROM weld_notifications
        WHERE status = 'active'
        GROUP BY priority
    """)
    summary['by_priority'] = {row['priority']: row['count'] for row in cursor.fetchall()}

    # By type (active only)
    cursor.execute("""
        SELECT notification_type, COUNT(*) as count
        FROM weld_notifications
        WHERE status = 'active'
        GROUP BY notification_type
    """)
    summary['by_type'] = {row['notification_type']: row['count'] for row in cursor.fetchall()}

    # Urgent items
    cursor.execute("""
        SELECT id, title, due_date, days_until_due
        FROM weld_notifications
        WHERE status = 'active' AND priority = 'urgent'
        ORDER BY due_date
        LIMIT 10
    """)
    summary['urgent'] = [dict(row) for row in cursor.fetchall()]

    return summary


def print_notifications(notifications: List[Dict]):
    """Print notification list."""
    if not notifications:
        print("No active notifications")
        return

    print(f"\n{'ID':>5} {'Priority':<8} {'Type':<15} {'Days':<5} {'Title'}")
    print("-" * 80)

    for n in notifications:
        priority_marker = {
            'urgent': '!!!',
            'high': '!!',
            'normal': '.',
            'low': ''
        }.get(n['priority'], '')

        print(f"{n['id']:>5} {n['priority']:<8} {n['notification_type']:<15} "
              f"{n['days_until_due'] or 'N/A':<5} {n['title'][:45]}")


def print_summary(summary: Dict):
    """Print notification summary."""
    print("\n" + "=" * 50)
    print("NOTIFICATION SUMMARY")
    print("=" * 50)

    print("\nBy Status:")
    for status, count in summary.get('by_status', {}).items():
        print(f"  {status}: {count}")

    print("\nActive by Priority:")
    for priority, count in summary.get('by_priority', {}).items():
        marker = {'urgent': '!!!', 'high': '!!', 'normal': '.', 'low': ''}.get(priority, '')
        print(f"  {marker} {priority}: {count}")

    print("\nActive by Type:")
    for ntype, count in summary.get('by_type', {}).items():
        print(f"  {ntype}: {count}")

    if summary.get('urgent'):
        print("\nURGENT Items:")
        for item in summary['urgent']:
            print(f"  [{item['id']}] {item['title'][:50]} ({item['days_until_due']}d)")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Welding notification system')
    parser.add_argument('--check', action='store_true', help='List active notifications')
    parser.add_argument('--summary', action='store_true', help='Show notification summary')
    parser.add_argument('--acknowledge', type=int, metavar='ID', help='Acknowledge notification')
    parser.add_argument('--resolve', type=int, metavar='ID', help='Resolve notification')
    parser.add_argument('--cleanup', action='store_true', help='Remove old resolved notifications')
    parser.add_argument('--cleanup-days', type=int, default=90, help='Days for cleanup (default: 90)')

    args = parser.parse_args()

    conn = get_db_connection()

    if args.acknowledge:
        if acknowledge_notification(conn, args.acknowledge):
            print(f"Notification {args.acknowledge} acknowledged")
        else:
            print(f"Notification {args.acknowledge} not found or already acknowledged")
        conn.close()
        return

    if args.resolve:
        if resolve_notification(conn, args.resolve):
            print(f"Notification {args.resolve} resolved")
        else:
            print(f"Notification {args.resolve} not found or already resolved")
        conn.close()
        return

    if args.cleanup:
        deleted = cleanup_old_notifications(conn, args.cleanup_days)
        print(f"Cleaned up {deleted} old notifications")
        conn.close()
        return

    if args.check:
        notifications = list_active_notifications(conn)
        print_notifications(notifications)
        conn.close()
        return

    if args.summary:
        summary = get_notification_summary(conn)
        print_summary(summary)
        conn.close()
        return

    # Default: Generate notifications
    print("Generating notifications...")
    stats = generate_all_notifications(conn)

    print("\n" + "=" * 50)
    print("NOTIFICATION GENERATION SUMMARY")
    print("=" * 50)
    print(f"WPQ expirations:       {stats['wpq_created']} new")
    print(f"BPQR expirations:      {stats['bpqr_created']} new")
    print(f"Continuity at risk:    {stats['continuity_created']} new")
    print(f"Total created:         {stats['total_created']}")
    print(f"Already existed:       {stats['total_skipped']}")

    # Show summary
    summary = get_notification_summary(conn)
    print_summary(summary)

    conn.close()


if __name__ == '__main__':
    main()
