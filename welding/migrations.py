"""
Welding Module Migrations

Incremental data corrections and schema migrations for the welding module.
Follows the same idempotent pattern as projects/migrations.py.

All migration functions are safe to run repeatedly (idempotent).
"""

import re
import sqlite3
from qms.core import get_logger

logger = get_logger("qms.welding.migrations")


# ---------------------------------------------------------------------------
# Helpers (same pattern as projects/migrations.py)
# ---------------------------------------------------------------------------

def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row["n"] > 0


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


# ---------------------------------------------------------------------------
# WPS Number Corrections
# ---------------------------------------------------------------------------

# PDF-verified corrections for truncated WPS numbers.
# Keys = current (wrong) value in DB, Values = correct full name.
WPS_CORRECTIONS = {
    "CS-02":         "CS-02-P1-GTAW/SMAW",
    "CS-03-P1-":     "CS-03-P1-GTAW",
    "CS-04-P1-":     "CS-04-P1-SMAW-Low Temp",
    "CS-05":         "CS-05-P1-GTAW/SMAW-Low Temp",
    "DM-01-P8_P1-":  "DM-01-P8_P1-GTAW",
}

# Tables that store wps_number as a text column and need cascading updates.
# weld_wps is the source — the rest are downstream references.
_WPS_CASCADE_TABLES = [
    "weld_pqr",
    "weld_wpq",
    "weld_continuity_log",
    "weld_production_welds",
    "weld_cert_request_coupons",
]

# SS-02-P8- has two entries (Solar Flux vs Fusion) — cannot auto-fix.
_SS02_AMBIGUOUS = "SS-02-P8-"
_SS03_UNKNOWN = "SS-03-P8-"


def migrate_fix_wps_numbers(conn: sqlite3.Connection) -> None:
    """
    Correct truncated WPS numbers using PDF-verified values.

    Updates weld_wps first, then cascades to all downstream tables
    that reference wps_number as a text field.
    """
    if not _table_exists(conn, "weld_wps"):
        return

    fixed = 0
    for old_number, new_number in WPS_CORRECTIONS.items():
        # Check if this correction is still needed
        row = conn.execute(
            "SELECT id FROM weld_wps WHERE wps_number = ?", (old_number,)
        ).fetchone()
        if not row:
            continue

        # Check the corrected value doesn't already exist (would violate UNIQUE)
        existing = conn.execute(
            "SELECT id FROM weld_wps WHERE wps_number = ?", (new_number,)
        ).fetchone()
        if existing:
            logger.warning(
                "WPS correction skipped: '%s' → '%s' (target already exists as ID %d)",
                old_number, new_number, existing["id"],
            )
            continue

        # Update source table
        conn.execute(
            "UPDATE weld_wps SET wps_number = ? WHERE wps_number = ?",
            (new_number, old_number),
        )
        logger.info("WPS corrected: '%s' → '%s'", old_number, new_number)

        # Cascade to downstream tables
        for table in _WPS_CASCADE_TABLES:
            if not _table_exists(conn, table):
                continue
            cursor = conn.execute(
                f"UPDATE {table} SET wps_number = ? WHERE wps_number = ?",
                (new_number, old_number),
            )
            if cursor.rowcount > 0:
                logger.info(
                    "  Cascaded to %s: %d row(s) updated", table, cursor.rowcount
                )

        fixed += 1

    # Flag SS-02 ambiguity — add notes if column exists
    if _column_exists(conn, "weld_wps", "notes"):
        ss02_rows = conn.execute(
            "SELECT id, wps_number FROM weld_wps WHERE wps_number = ?",
            (_SS02_AMBIGUOUS,),
        ).fetchall()
        if len(ss02_rows) >= 2:
            for row in ss02_rows:
                conn.execute(
                    "UPDATE weld_wps SET notes = COALESCE(notes, '') || "
                    "CASE WHEN notes IS NULL OR notes = '' THEN '' ELSE '; ' END || "
                    "'NEEDS DISAMBIGUATION: Solar Flux vs Fusion variant — see Session 4 fix-wps command' "
                    "WHERE id = ? AND (notes IS NULL OR notes NOT LIKE '%NEEDS DISAMBIGUATION%')",
                    (row["id"],),
                )
            if ss02_rows:
                logger.warning(
                    "SS-02-P8-: %d entries need manual disambiguation (Solar Flux vs Fusion)",
                    len(ss02_rows),
                )

    # Log warning for SS-03
    ss03_exists = conn.execute(
        "SELECT COUNT(*) AS n FROM weld_wps WHERE wps_number = ?",
        (_SS03_UNKNOWN,),
    ).fetchone()
    if ss03_exists["n"] > 0:
        logger.warning("SS-03-P8-: pending investigation, left as-is")

    if fixed:
        conn.commit()
        logger.info("WPS number corrections complete: %d fixed", fixed)
    else:
        logger.debug("WPS number corrections: nothing to fix (already applied)")


# ---------------------------------------------------------------------------
# WPQ Number Normalization
# ---------------------------------------------------------------------------

# Pattern for the intentional P8_P1 underscore in dissimilar metal WPS names.
_P8_P1_PATTERN = re.compile(r"P8_P1", re.IGNORECASE)

# Process separators that should become forward-slash.
# Matches underscore, space, or hyphen between two process names.
_PROCESS_SEP_PATTERN = re.compile(r"(GTAW|SMAW|GMAW|FCAW|SAW)[\s_\-](GTAW|SMAW|GMAW|FCAW|SAW)")


def _normalize_wpq_number(raw: str) -> str:
    """
    Normalise a WPQ (or WPS) number string to a canonical form.

    Rules applied in order:
    1. Strip whitespace, uppercase
    2. Replace ``=`` with ``-``
    3. Replace ``_`` with ``-`` **except** the ``P8_P1`` dissimilar-metal token
    4. Collapse ``--`` to ``-``, strip trailing ``-``
    5. Standardize process separators to ``/`` (e.g. ``GTAW_SMAW`` → ``GTAW/SMAW``)

    Args:
        raw: Raw identifier string from the database.

    Returns:
        Normalised identifier string.
    """
    s = raw.strip().upper()

    # = → -
    s = s.replace("=", "-")

    # Protect P8_P1 by replacing it with a placeholder
    s = _P8_P1_PATTERN.sub("P8\x00P1", s)

    # _ → -
    s = s.replace("_", "-")

    # Restore P8_P1
    s = s.replace("P8\x00P1", "P8_P1")

    # Collapse double-hyphens and strip trailing hyphen
    while "--" in s:
        s = s.replace("--", "-")
    s = s.rstrip("-")

    # Standardise process separators: GTAW-SMAW or GTAW SMAW → GTAW/SMAW
    s = _PROCESS_SEP_PATTERN.sub(r"\1/\2", s)

    return s


def migrate_normalize_wpq_numbers(conn: sqlite3.Connection) -> None:
    """
    Normalize all WPQ numbers in the database to a canonical format.

    Applies ``_normalize_wpq_number()`` to every ``weld_wpq.wpq_number``.
    Detects collisions (two raw values normalising to the same string)
    and logs them for manual review rather than silently overwriting.
    """
    if not _table_exists(conn, "weld_wpq"):
        return

    rows = conn.execute(
        "SELECT id, wpq_number FROM weld_wpq WHERE wpq_number IS NOT NULL"
    ).fetchall()

    if not rows:
        return

    # Build old → new mapping, detect collisions
    updates = []           # (id, old, new)
    seen: dict[str, int] = {}  # normalized → first id
    collisions = []

    for row in rows:
        old = row["wpq_number"]
        new = _normalize_wpq_number(old)
        if new == old:
            # Already canonical — still track for collision detection
            seen.setdefault(new, row["id"])
            continue

        if new in seen:
            collisions.append((row["id"], old, new, seen[new]))
            continue

        seen[new] = row["id"]
        updates.append((row["id"], old, new))

    for wpq_id, old, new in updates:
        # Final safety: ensure target doesn't already exist
        exists = conn.execute(
            "SELECT id FROM weld_wpq WHERE wpq_number = ? AND id != ?",
            (new, wpq_id),
        ).fetchone()
        if exists:
            logger.warning(
                "WPQ normalization collision: '%s' → '%s' (conflicts with ID %d), skipped",
                old, new, exists["id"],
            )
            continue

        conn.execute(
            "UPDATE weld_wpq SET wpq_number = ? WHERE id = ?",
            (new, wpq_id),
        )
        logger.debug("WPQ normalized: '%s' → '%s' (ID %d)", old, new, wpq_id)

    for wpq_id, old, new, conflict_id in collisions:
        logger.warning(
            "WPQ normalization collision: ID %d '%s' → '%s' conflicts with ID %d, skipped",
            wpq_id, old, new, conflict_id,
        )

    if updates:
        conn.commit()
        logger.info(
            "WPQ normalization complete: %d updated, %d collisions skipped",
            len(updates), len(collisions),
        )
    else:
        logger.debug("WPQ normalization: nothing to normalize")


# ---------------------------------------------------------------------------
# PQR Import
# ---------------------------------------------------------------------------

# Known PQR records extracted from raw PDF documents.
# Each tuple: (pqr_number, test_date, wps_number, notes)
_KNOWN_PQRS = [
    # Legacy generic format
    ("1-6G-3",      None,         None,                    "Legacy PQR — generic numbering"),
    ("1-6G-8",      None,         None,                    "Legacy PQR — supports SS-02 (Fusion variant)"),
    ("1-6G-8A",     None,         None,                    "Legacy PQR — variant A"),
    ("1-6G-8SF",    None,         None,                    "Legacy PQR — Solar Flux variant"),
    ("1-6G-8SFA",   None,         None,                    "Legacy PQR — Solar Flux variant A"),
    ("1-6G-12",     None,         "DM-01-P8_P1-GTAW",     "Legacy PQR — supports DM-01"),
    # Legacy descriptive format
    ("A53-NPS6-6G-6010-7018-3",      None, "CS-01-P1-SMAW",           "Legacy PQR — A53 pipe, SMAW"),
    ("A106-NPS2-6G-ER70S-7018",      None, "CS-02-P1-GTAW/SMAW",     "Legacy PQR — A106 2\" pipe"),
    ("A106-NPS6-6G-ER70S-7018",      None, "CS-02-P1-GTAW/SMAW",     "Legacy PQR — A106 6\" pipe"),
    ("A333-NPS6-6G-6010-7018",       None, "CS-01-P1-SMAW",           "Legacy PQR — A333 low-temp, SMAW"),
    ("A333-NPS6-6G-8010-8018",       None, "CS-04-P1-SMAW-Low Temp",  "Legacy PQR — A333 low-temp, 8010/8018"),
    ("A333-NPS2-6G-ER80S-8018",      None, "CS-05-P1-GTAW/SMAW-Low Temp", "Legacy PQR — A333 2\" low-temp"),
    ("A333-NPS6-6G-ER80S-E8018",     None, "CS-05-P1-GTAW/SMAW-Low Temp", "Legacy PQR — A333 6\" low-temp"),
    # New format (may already exist)
    ("CS-03-P1-GTAW",   None, "CS-03-P1-GTAW",           "PQR mirrors WPS — CS GTAW"),
    ("SS-01-P8-GTAW",   None, "SS-01-P8-GTAW",           "PQR mirrors WPS — SS GTAW"),
]


def migrate_import_known_pqrs(conn: sqlite3.Connection) -> None:
    """
    Import known PQR records that were extracted from raw PDF documents.

    Uses INSERT OR IGNORE on the UNIQUE pqr_number constraint, so
    this is safe to run repeatedly.
    """
    if not _table_exists(conn, "weld_pqr"):
        return

    inserted = 0
    for pqr_number, test_date, wps_number, notes in _KNOWN_PQRS:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO weld_pqr
               (pqr_number, test_date, wps_number, status, notes)
               VALUES (?, ?, ?, 'active', ?)""",
            (pqr_number, test_date, wps_number, notes),
        )
        if cursor.rowcount > 0:
            inserted += 1
            logger.debug("Imported PQR: %s", pqr_number)

    if inserted:
        conn.commit()
        logger.info("PQR import complete: %d new record(s)", inserted)
    else:
        logger.debug("PQR import: all records already exist")


# ---------------------------------------------------------------------------
# WPS ↔ PQR Cross-Reference Links
# ---------------------------------------------------------------------------

# Map of WPS number → list of supporting PQR numbers (from PDF review).
_WPS_PQR_MAP = {
    "CS-01-P1-SMAW": [
        "A53-NPS6-6G-6010-7018-3",
        "A333-NPS6-6G-6010-7018",
    ],
    "CS-02-P1-GTAW/SMAW": [
        "A106-NPS2-6G-ER70S-7018",
        "A106-NPS6-6G-ER70S-7018",
    ],
    "CS-03-P1-GTAW": [
        "CS-03-P1-GTAW",
    ],
    "CS-04-P1-SMAW-Low Temp": [
        "A333-NPS6-6G-8010-8018",
    ],
    "CS-05-P1-GTAW/SMAW-Low Temp": [
        "A333-NPS2-6G-ER80S-8018",
        "A333-NPS6-6G-ER80S-E8018",
    ],
    "DM-01-P8_P1-GTAW": [
        "1-6G-12",
    ],
    "SS-01-P8-GTAW": [
        "SS-01-P8-GTAW",
    ],
    # SS-02 links deferred until disambiguation (Session 4)
}


def migrate_populate_wps_pqr_links(conn: sqlite3.Connection) -> None:
    """
    Populate the weld_wps_pqr_links cross-reference table.

    Looks up wps_id and pqr_id by number. Uses INSERT OR IGNORE
    on the UNIQUE(wps_id, pqr_id) constraint for idempotency.
    Falls back to pqr_number text when pqr_id can't be resolved.
    """
    if not _table_exists(conn, "weld_wps_pqr_links"):
        return
    if not _table_exists(conn, "weld_wps"):
        return

    linked = 0
    for wps_number, pqr_numbers in _WPS_PQR_MAP.items():
        wps_row = conn.execute(
            "SELECT id FROM weld_wps WHERE wps_number = ?", (wps_number,)
        ).fetchone()
        if not wps_row:
            logger.warning("WPS-PQR link: WPS '%s' not found, skipping", wps_number)
            continue
        wps_id = wps_row["id"]

        for pqr_number in pqr_numbers:
            pqr_row = conn.execute(
                "SELECT id FROM weld_pqr WHERE pqr_number = ?", (pqr_number,)
            ).fetchone()
            pqr_id = pqr_row["id"] if pqr_row else None

            cursor = conn.execute(
                """INSERT OR IGNORE INTO weld_wps_pqr_links
                   (wps_id, pqr_id, pqr_number, qualification_scope)
                   VALUES (?, ?, ?, 'supporting')""",
                (wps_id, pqr_id, pqr_number),
            )
            if cursor.rowcount > 0:
                linked += 1
                logger.debug(
                    "Linked WPS '%s' → PQR '%s' (pqr_id=%s)",
                    wps_number, pqr_number, pqr_id,
                )

    if linked:
        conn.commit()
        logger.info("WPS-PQR links populated: %d new link(s)", linked)
    else:
        logger.debug("WPS-PQR links: all links already exist")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_welding_migrations(conn: sqlite3.Connection) -> None:
    """Run all welding module migrations in dependency order."""
    migrate_fix_wps_numbers(conn)
    migrate_normalize_wpq_numbers(conn)
    migrate_import_known_pqrs(conn)
    migrate_populate_wps_pqr_links(conn)
