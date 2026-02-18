"""
Database loader for extracted welding form data.

Handles INSERT/UPDATE with deduplication, identifier normalization,
and transactional child record insertion.
"""

import re
import sqlite3
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger
from qms.welding.forms.base import BaseFormDefinition

logger = get_logger("qms.welding.extraction.loader")


# ---------------------------------------------------------------------------
# Record lookup
# ---------------------------------------------------------------------------

def find_existing_record(conn: sqlite3.Connection, form_def: BaseFormDefinition,
                         identifier: str) -> Optional[Dict[str, Any]]:
    """
    Find an existing record by identifier (exact match then prefix match).

    Args:
        conn: Database connection.
        form_def: Form definition for table/column info.
        identifier: Document identifier to search for.

    Returns:
        Dict of row data or None.
    """
    table = form_def.parent_table
    id_col = form_def.identifier_column

    # Exact match
    row = conn.execute(
        f"SELECT * FROM {table} WHERE {id_col} = ?", (identifier,)
    ).fetchone()
    if row:
        return dict(row)

    # Normalized match (strip whitespace, case-insensitive)
    normalized = identifier.strip().upper()
    row = conn.execute(
        f"SELECT * FROM {table} WHERE UPPER(TRIM({id_col})) = ?", (normalized,)
    ).fetchone()
    if row:
        return dict(row)

    # Prefix match (for cases like "CS-01" matching "CS-01-P1-SMAW")
    row = conn.execute(
        f"SELECT * FROM {table} WHERE {id_col} LIKE ? ORDER BY LENGTH({id_col}) LIMIT 1",
        (f"{identifier}%",)
    ).fetchone()
    if row:
        logger.info("Prefix match: '%s' -> '%s'", identifier, dict(row)[id_col])
        return dict(row)

    return None


# ---------------------------------------------------------------------------
# Child record insertion
# ---------------------------------------------------------------------------

# Maps child section names to their database table and parent FK column
CHILD_TABLE_MAP = {
    # WPS children
    "processes": ("weld_wps_processes", "wps_id"),
    "joints": ("weld_wps_joints", "wps_id"),
    "base_metals": ("weld_wps_base_metals", "wps_id"),
    "filler_metals": ("weld_wps_filler_metals", "wps_id"),
    "positions": ("weld_wps_positions", "wps_id"),
    "preheat": ("weld_wps_preheat", "wps_id"),
    "pwht": ("weld_wps_pwht", "wps_id"),
    "gas": ("weld_wps_gas", "wps_id"),
    "electrical": ("weld_wps_electrical_params", "wps_id"),
    "technique": ("weld_wps_technique", "wps_id"),
    "pqr_links": ("weld_wps_pqr_links", "wps_id"),
    # PQR children
    "tensile_tests": ("weld_pqr_tensile_tests", "pqr_id"),
    "bend_tests": ("weld_pqr_bend_tests", "pqr_id"),
    "toughness_tests": ("weld_pqr_toughness_tests", "pqr_id"),
    "other_tests": ("weld_pqr_other_tests", "pqr_id"),
    "personnel": ("weld_pqr_personnel", "pqr_id"),
    # WPQ children
    "tests": ("weld_wpq_tests", "wpq_id"),
    # BPS children
    "flux_atmosphere": ("weld_bps_flux_atmosphere", "bps_id"),
}

# Override child table mapping per form type (handles shared names like "base_metals")
FORM_CHILD_MAP = {
    "pqr": {
        "joints": ("weld_pqr_joints", "pqr_id"),
        "base_metals": ("weld_pqr_base_metals", "pqr_id"),
        "filler_metals": ("weld_pqr_filler_metals", "pqr_id"),
        "positions": ("weld_pqr_positions", "pqr_id"),
        "preheat": ("weld_pqr_preheat", "pqr_id"),
        "pwht": ("weld_pqr_pwht", "pqr_id"),
        "gas": ("weld_pqr_gas", "pqr_id"),
        "electrical": ("weld_pqr_electrical", "pqr_id"),
    },
    "bps": {
        "joints": ("weld_bps_joints", "bps_id"),
        "base_metals": ("weld_bps_base_metals", "bps_id"),
        "filler_metals": ("weld_bps_filler_metals", "bps_id"),
        "positions": ("weld_bps_positions", "bps_id"),
        "pwht": ("weld_bps_pwht", "bps_id"),
        "technique": ("weld_bps_technique", "bps_id"),
    },
    "bpq": {
        "base_metals": ("weld_bpq_base_metals", "bpq_id"),
        "filler_metals": ("weld_bpq_filler_metals", "bpq_id"),
        "tests": ("weld_bpq_tests", "bpq_id"),
    },
}


def _get_table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    """Get column names for a table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def _insert_child_rows(conn: sqlite3.Connection, table: str, fk_column: str,
                       parent_id: int, rows: List[Dict[str, Any]]) -> int:
    """
    Insert child records linked to a parent record.

    Args:
        conn: Database connection.
        table: Target child table.
        fk_column: Foreign key column name.
        parent_id: Parent record ID.
        rows: List of row dicts to insert.

    Returns:
        Number of rows inserted.
    """
    if not rows:
        return 0

    valid_columns = set(_get_table_columns(conn, table))
    count = 0

    for row_data in rows:
        # Filter to valid columns only
        filtered = {k: v for k, v in row_data.items()
                    if k in valid_columns and k not in ("id",)}
        filtered[fk_column] = parent_id

        if not filtered:
            continue

        columns = list(filtered.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_str = ", ".join(columns)
        values = [filtered[c] for c in columns]

        conn.execute(
            f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})",
            values,
        )
        count += 1

    return count


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_to_database(data: Dict[str, Any], conn: sqlite3.Connection,
                     form_def: BaseFormDefinition) -> Dict[str, Any]:
    """
    Insert or update extracted data into the database.

    Args:
        data: Extracted data dict with 'parent' and child sections.
        conn: Database connection (caller manages transaction).
        form_def: Form definition for table/column info.

    Returns:
        Dict with 'parent_id', 'action' (insert/update), 'child_counts'.
    """
    result: Dict[str, Any] = {
        "parent_id": None,
        "action": None,
        "child_counts": {},
    }

    parent_data = data.get("parent", {})
    if not parent_data:
        raise ValueError("No parent data to load")

    table = form_def.parent_table
    id_col = form_def.identifier_column
    identifier = parent_data.get(id_col)

    if not identifier:
        raise ValueError(f"Missing identifier: {id_col}")

    # Check for existing record
    existing = find_existing_record(conn, form_def, identifier)
    valid_columns = set(_get_table_columns(conn, table))

    # Filter parent data to valid columns
    filtered_parent = {k: v for k, v in parent_data.items()
                       if k in valid_columns and k not in ("id", "created_at")}

    if existing:
        # UPDATE existing record
        parent_id = existing["id"]
        set_clauses = [f"{k} = ?" for k in filtered_parent.keys()]
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        values = list(filtered_parent.values()) + [parent_id]

        conn.execute(
            f"UPDATE {table} SET {', '.join(set_clauses)} WHERE id = ?",
            values,
        )
        result["action"] = "update"
        logger.info("Updated %s: %s (id=%d)", table, identifier, parent_id)

        # Delete existing child records before re-inserting
        for child_table in form_def.child_tables:
            # Determine FK column
            fk_col = _infer_fk_column(child_table, form_def.form_type)
            if fk_col:
                conn.execute(f"DELETE FROM {child_table} WHERE {fk_col} = ?", (parent_id,))
    else:
        # INSERT new record
        columns = list(filtered_parent.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_str = ", ".join(columns)
        values = [filtered_parent[c] for c in columns]

        cursor = conn.execute(
            f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})",
            values,
        )
        parent_id = cursor.lastrowid
        result["action"] = "insert"
        logger.info("Inserted %s: %s (id=%d)", table, identifier, parent_id)

    result["parent_id"] = parent_id

    # Insert qualification derivation rows (per-code child tables)
    qualifications = data.get("_qualifications")
    if qualifications and isinstance(qualifications, dict):
        qual_table = {
            "wpq": ("weld_wpq_qualifications", "wpq_id"),
            "bpqr": ("weld_bpqr_qualifications", "bpqr_id"),
        }.get(form_type)

        if qual_table:
            q_table, q_fk = qual_table
            # Check if table exists (schema may not be migrated yet)
            try:
                cols = set(_get_table_columns(conn, q_table))
                if cols:
                    # Delete existing qualifications before re-inserting
                    conn.execute(f"DELETE FROM {q_table} WHERE {q_fk} = ?",
                                 (parent_id,))
                    q_count = 0
                    for code_id, code_data in qualifications.items():
                        filtered = {k: v for k, v in code_data.items()
                                    if k in cols and k not in ("id",)}
                        filtered[q_fk] = parent_id
                        if filtered:
                            q_columns = list(filtered.keys())
                            q_placeholders = ", ".join(["?"] * len(q_columns))
                            q_col_str = ", ".join(q_columns)
                            q_values = [filtered[c] for c in q_columns]
                            conn.execute(
                                f"INSERT INTO {q_table} ({q_col_str}) VALUES ({q_placeholders})",
                                q_values,
                            )
                            q_count += 1
                    result["child_counts"][q_table] = q_count
                    logger.info("  Inserted %d qualification rows into %s",
                                q_count, q_table)
            except Exception:
                # Table doesn't exist yet — skip silently
                pass

    # Insert child records
    form_type = form_def.form_type
    form_overrides = FORM_CHILD_MAP.get(form_type, {})

    for section_name, section_data in data.items():
        if section_name == "parent" or not isinstance(section_data, list):
            continue

        # Resolve child table and FK column
        if section_name in form_overrides:
            child_table, fk_col = form_overrides[section_name]
        elif section_name in CHILD_TABLE_MAP:
            child_table, fk_col = CHILD_TABLE_MAP[section_name]
        else:
            logger.warning("Unknown child section '%s' for form type '%s'",
                           section_name, form_type)
            continue

        count = _insert_child_rows(conn, child_table, fk_col, parent_id, section_data)
        result["child_counts"][child_table] = count
        logger.info("  Inserted %d rows into %s", count, child_table)

    return result


def _infer_fk_column(child_table: str, form_type: str) -> Optional[str]:
    """Infer the FK column name from a child table name."""
    # Pattern: weld_{form_type}_{suffix} -> {form_type}_id
    # e.g., weld_wps_processes -> wps_id
    fk_map = {
        "wps": "wps_id",
        "pqr": "pqr_id",
        "wpq": "wpq_id",
        "bps": "bps_id",
        "bpq": "bpq_id",
        "bpqr": "bpqr_id",
    }
    return fk_map.get(form_type)


# ---------------------------------------------------------------------------
# Identifier normalization
# ---------------------------------------------------------------------------

def normalize_identifiers(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Cleanup of malformed identifier values across all welding tables.

    Uses the canonical normalization from ``welding.migrations._normalize_wpq_number``
    for WPQ numbers, and applies lighter cleanup (trim, uppercase, collapse hyphens)
    to other identifier columns.

    Returns:
        Dict mapping table.column to count of records updated.
    """
    from qms.welding.migrations import _normalize_wpq_number

    updates: Dict[str, int] = {}

    # WPQ numbers get the full normalization treatment
    rows = conn.execute(
        "SELECT id, wpq_number FROM weld_wpq WHERE wpq_number IS NOT NULL"
    ).fetchall()
    wpq_count = 0
    for row in rows:
        old = row["wpq_number"]
        new = _normalize_wpq_number(old)
        if new != old:
            # Check for collision before updating
            exists = conn.execute(
                "SELECT id FROM weld_wpq WHERE wpq_number = ? AND id != ?",
                (new, row["id"]),
            ).fetchone()
            if exists:
                logger.warning(
                    "normalize_identifiers: WPQ '%s' → '%s' collides with ID %d, skipped",
                    old, new, exists["id"],
                )
                continue
            conn.execute(
                "UPDATE weld_wpq SET wpq_number = ? WHERE id = ?",
                (new, row["id"]),
            )
            wpq_count += 1
    if wpq_count:
        updates["weld_wpq.wpq_number"] = wpq_count

    # Other identifier columns: trim + uppercase + collapse hyphens
    other_columns = [
        ("weld_wps", "wps_number"),
        ("weld_pqr", "pqr_number"),
        ("weld_wpq", "wps_number"),
        ("weld_bps", "bps_number"),
        ("weld_bpq", "bpq_number"),
    ]

    for table, column in other_columns:
        count = 0

        # Trim whitespace
        cursor = conn.execute(
            f"UPDATE {table} SET {column} = TRIM({column}) "
            f"WHERE {column} != TRIM({column})"
        )
        count += cursor.rowcount

        # Uppercase
        cursor = conn.execute(
            f"UPDATE {table} SET {column} = UPPER({column}) "
            f"WHERE {column} != UPPER({column})"
        )
        count += cursor.rowcount

        # Remove double hyphens
        cursor = conn.execute(
            f"UPDATE {table} SET {column} = REPLACE({column}, '--', '-') "
            f"WHERE {column} LIKE '%--%'"
        )
        count += cursor.rowcount

        if count > 0:
            updates[f"{table}.{column}"] = count
            logger.info("Normalized %d values in %s.%s", count, table, column)

    conn.commit()
    return updates
