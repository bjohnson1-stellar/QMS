"""
License import specification — column definitions, matching, and categorization.

Defines how spreadsheet data maps to the state_licenses table, reusing the
shared imports/ engine (same pattern as workforce/import_specs.py).
"""

from typing import Any, Dict, List, Optional, Tuple

import sqlite3

from qms.imports.specs import ActionItem, ColumnDef, ImportSpec


# ---------------------------------------------------------------------------
# Column definitions (10 fields)
# ---------------------------------------------------------------------------

LICENSE_COLUMNS = [
    ColumnDef(
        name="state_code", label="State", type="text", required=True,
        aliases=["state", "st", "state abbreviation", "state_abbreviation",
                 "license state", "license_state"],
    ),
    ColumnDef(
        name="license_type", label="License Type", type="text", required=True,
        aliases=["type", "lic type", "lic_type", "license_type",
                 "classification", "license classification"],
    ),
    ColumnDef(
        name="license_number", label="License Number", type="text", required=True,
        aliases=["license #", "license_number", "lic #", "lic num", "lic_num",
                 "number", "license no", "lic no", "cert number", "cert #",
                 "certificate number"],
    ),
    ColumnDef(
        name="holder_name", label="Holder Name", type="text", required=True,
        aliases=["name", "holder", "company", "company name", "company_name",
                 "licensee", "holder_name", "entity name", "entity"],
    ),
    ColumnDef(
        name="holder_type", label="Holder Type", type="text",
        aliases=["type of holder", "holder_type", "entity type", "entity_type"],
    ),
    ColumnDef(
        name="employee_id", label="Employee", type="fk_lookup",
        aliases=["employee", "emp", "employee name", "employee_name",
                 "emp name", "emp_name"],
        fk_table="employees", fk_display="last_name", fk_id="id",
    ),
    ColumnDef(
        name="issued_date", label="Issued Date", type="date",
        aliases=["issued", "issue date", "issue_date", "date issued",
                 "date_issued", "effective date", "effective_date"],
    ),
    ColumnDef(
        name="expiration_date", label="Expiration Date", type="date",
        aliases=["expiration", "expires", "expiry", "expiry date",
                 "expiry_date", "exp date", "exp_date", "date expires",
                 "renewal date", "renewal_date"],
    ),
    ColumnDef(
        name="status", label="Status", type="text",
        aliases=["license status", "lic status", "license_status"],
    ),
    ColumnDef(
        name="notes", label="Notes", type="text",
        aliases=["comments", "remarks", "comment", "remark", "description"],
    ),
]


# ---------------------------------------------------------------------------
# Match function — 2-level duplicate detection
# ---------------------------------------------------------------------------

def match_license(
    conn: sqlite3.Connection, record: Dict[str, Any]
) -> Tuple[Optional[Dict], Optional[str]]:
    """Find existing license using 2-level matching.

    Returns:
        (existing_dict, match_method) or (None, None)
    """
    # Level 1: license_number + state_code (exact)
    lic_num = record.get("license_number")
    state = record.get("state_code")
    if lic_num and state:
        row = conn.execute(
            """SELECT * FROM state_licenses
               WHERE license_number = ? AND state_code = ?""",
            (str(lic_num).strip(), str(state).strip().upper()),
        ).fetchone()
        if row:
            return dict(row), "license_number+state"

    # Level 2: holder_name + license_type + state_code (case-insensitive)
    holder = record.get("holder_name")
    lic_type = record.get("license_type")
    if holder and lic_type and state:
        row = conn.execute(
            """SELECT * FROM state_licenses
               WHERE LOWER(holder_name) = LOWER(?)
                 AND LOWER(license_type) = LOWER(?)
                 AND state_code = ?""",
            (str(holder).strip(), str(lic_type).strip(),
             str(state).strip().upper()),
        ).fetchone()
        if row:
            return dict(row), "name+type+state"

    return None, None


# ---------------------------------------------------------------------------
# Categorize function
# ---------------------------------------------------------------------------

_COMPARE_FIELDS = [
    "holder_name", "holder_type", "license_type", "license_number",
    "state_code", "issued_date", "expiration_date", "status", "notes",
]


def categorize_license(
    record: Dict[str, Any],
    existing: Optional[Dict[str, Any]],
    match_method: Optional[str],
    row_index: int,
) -> ActionItem:
    """Determine action type for an import row."""
    display_data = {k: v for k, v in record.items() if not k.startswith("_")}

    if existing is None:
        return ActionItem(
            row_index=row_index,
            action_type="insert",
            record_data=display_data,
            reason="New license (no match found)",
        )

    # Name-only match (level 2) → flag for review
    if match_method == "name+type+state":
        changes = _compute_changes(record, existing)
        return ActionItem(
            row_index=row_index,
            action_type="flag",
            record_data=display_data,
            existing_data=existing,
            match_method=match_method,
            changes=changes if changes else None,
            reason="Matched by name+type+state — verify license number",
        )

    # Exact match — compute diff
    changes = _compute_changes(record, existing)

    if not changes:
        return ActionItem(
            row_index=row_index,
            action_type="skip",
            record_data=display_data,
            existing_data=existing,
            match_method=match_method,
            reason=f"No changes (matched by {match_method})",
        )

    return ActionItem(
        row_index=row_index,
        action_type="update",
        record_data=display_data,
        existing_data=existing,
        match_method=match_method,
        changes=changes,
        reason=f"{len(changes)} field(s) changed (matched by {match_method})",
    )


def _compute_changes(
    record: Dict[str, Any], existing: Dict[str, Any]
) -> Dict[str, list]:
    """Compare import record against existing DB record."""
    changes = {}
    for field in _COMPARE_FIELDS:
        new_val = record.get(field)
        if new_val is None:
            continue

        old_val = existing.get(field)
        new_str = str(new_val).strip() if new_val is not None else ""
        old_str = str(old_val).strip() if old_val is not None else ""

        if new_str.lower() != old_str.lower():
            changes[field] = [old_val, new_val]

    return changes


# ---------------------------------------------------------------------------
# Execute function
# ---------------------------------------------------------------------------

def execute_license_action(
    conn: sqlite3.Connection, item: ActionItem, executed_by: str
):
    """Apply a single import action to the state_licenses table."""
    from qms.licenses.db import create_license, update_license

    data = item.record_data
    action = item.action_type

    # Default holder_type if not provided
    holder_type = data.get("holder_type", "company")
    if holder_type not in ("company", "employee"):
        holder_type = "company"

    if action == "insert":
        create_license(
            conn,
            holder_type=holder_type,
            employee_id=data.get("employee_id"),
            state_code=data["state_code"],
            license_type=data["license_type"],
            license_number=data["license_number"],
            holder_name=data["holder_name"],
            issued_date=data.get("issued_date"),
            expiration_date=data.get("expiration_date"),
            status=data.get("status", "active"),
            notes=data.get("notes"),
            created_by=executed_by,
        )

    elif action == "update":
        lic_id = item.existing_data["id"]
        updates = {}
        for field, (_, new_val) in (item.changes or {}).items():
            updates[field] = new_val
        if updates:
            update_license(conn, lic_id, **updates)

    elif action == "flag":
        # Flagged items that are approved get treated as updates
        if item.existing_data and item.changes:
            lic_id = item.existing_data["id"]
            updates = {}
            for field, (_, new_val) in item.changes.items():
                updates[field] = new_val
            if updates:
                update_license(conn, lic_id, **updates)


# ---------------------------------------------------------------------------
# Build the spec
# ---------------------------------------------------------------------------

def get_license_import_spec() -> ImportSpec:
    """Return the licenses import specification."""
    return ImportSpec(
        name="licenses",
        label="License Import",
        module="licenses",
        target_table="state_licenses",
        columns=LICENSE_COLUMNS,
        match_fn=match_license,
        categorize_fn=categorize_license,
        detect_missing_fn=None,  # No separation detection for licenses
        execute_fn=execute_license_action,
    )
