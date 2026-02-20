"""
Workforce import specification — employee column definitions, matching, and categorization.

Defines how spreadsheet data maps to the employees table, reusing the existing
4-level duplicate detection from workforce.employees.
"""

from typing import Any, Dict, List, Optional, Tuple

import sqlite3

from qms.imports.specs import ActionItem, ColumnDef, ImportSpec


# ---------------------------------------------------------------------------
# Column definitions (15 fields)
# ---------------------------------------------------------------------------

EMPLOYEE_COLUMNS = [
    ColumnDef(
        name="last_name", label="Last Name", type="text", required=True,
        aliases=["surname", "family name", "family_name", "lname"],
    ),
    ColumnDef(
        name="first_name", label="First Name", type="text", required=True,
        aliases=["given name", "given_name", "forename", "fname"],
    ),
    ColumnDef(
        name="middle_initial", label="Middle Initial", type="text",
        aliases=["mi", "middle", "middle name"],
    ),
    ColumnDef(
        name="employee_number", label="Employee Number", type="text",
        aliases=["emp #", "emp num", "emp_num", "badge", "badge #",
                 "badge number", "id number", "emp no", "employee #",
                 "employee no", "employee id"],
    ),
    ColumnDef(
        name="position", label="Position", type="text",
        aliases=["title", "job title", "job_title", "designation",
                 "trade", "craft", "classification"],
    ),
    ColumnDef(
        name="email", label="Email", type="text",
        aliases=["email address", "e-mail", "work email", "work_email"],
    ),
    ColumnDef(
        name="phone", label="Phone", type="text",
        aliases=["cell", "mobile", "phone number", "contact number",
                 "cell phone", "mobile phone", "telephone"],
    ),
    ColumnDef(
        name="department_id", label="Department", type="fk_lookup",
        aliases=["dept", "department", "department name", "dept name",
                 "department_name"],
        fk_table="departments", fk_display="name", fk_id="id",
    ),
    ColumnDef(
        name="job_id", label="Job / Project", type="fk_lookup",
        aliases=["job", "job number", "job_number", "project",
                 "project number", "project_number", "job #", "project #"],
        fk_table="jobs", fk_display="job_number", fk_id="id",
    ),
    ColumnDef(
        name="role_id", label="Role", type="fk_lookup",
        aliases=["role", "role name", "role_name", "role code",
                 "role_code"],
        fk_table="roles", fk_display="role_name", fk_id="id",
    ),
    ColumnDef(
        name="status", label="Status", type="text",
        aliases=["employment status", "emp status", "employee status"],
    ),
    ColumnDef(
        name="is_employee", label="Is Employee", type="bool",
        aliases=["employee", "emp", "is_emp"],
    ),
    ColumnDef(
        name="is_subcontractor", label="Is Subcontractor", type="bool",
        aliases=["subcontractor", "sub", "contractor", "is_sub"],
    ),
    ColumnDef(
        name="current_hire_date", label="Hire Date", type="date",
        aliases=["hire date", "hire_date", "start date", "start_date",
                 "date hired", "date_hired"],
    ),
    ColumnDef(
        name="notes", label="Notes", type="text",
        aliases=["comments", "remarks", "comment", "remark"],
    ),
]


# ---------------------------------------------------------------------------
# Match function — 4-level duplicate detection
# ---------------------------------------------------------------------------

def match_employee(
    conn: sqlite3.Connection, record: Dict[str, Any]
) -> Tuple[Optional[Dict], Optional[str]]:
    """Find existing employee using 4-level matching.

    Returns:
        (existing_dict, match_method) or (None, None)
    """
    from qms.workforce.employees import (
        find_employee_by_email,
        find_employee_by_name,
        find_employee_by_number,
        find_employee_by_phone,
    )

    # Level 1: Employee number (exact)
    emp_num = record.get("employee_number")
    if emp_num:
        existing = find_employee_by_number(conn, employee_number=str(emp_num))
        if existing:
            return existing, "employee_number"

    # Level 2: Phone (digit-normalized)
    phone = record.get("phone")
    if phone:
        existing = find_employee_by_phone(conn, str(phone))
        if existing:
            return existing, "phone"

    # Level 3: Name (case-insensitive, single match only)
    last_name = record.get("last_name")
    first_name = record.get("first_name")
    if last_name and first_name:
        candidates = find_employee_by_name(conn, last_name, first_name)
        if len(candidates) == 1:
            return candidates[0], "name"

    # Level 4: Email (case-insensitive)
    email = record.get("email")
    if email:
        existing = find_employee_by_email(conn, email)
        if existing:
            return existing, "email"

    return None, None


# ---------------------------------------------------------------------------
# Categorize function
# ---------------------------------------------------------------------------

# Fields compared for UPDATE detection
_COMPARE_FIELDS = [
    "last_name", "first_name", "middle_initial", "position",
    "email", "phone", "department_id", "job_id", "role_id",
    "is_employee", "is_subcontractor", "current_hire_date", "notes",
]


def categorize_employee(
    record: Dict[str, Any],
    existing: Optional[Dict[str, Any]],
    match_method: Optional[str],
    row_index: int,
) -> ActionItem:
    """Determine action type for an import row."""
    # Clean internal keys from record_data for display
    display_data = {k: v for k, v in record.items() if not k.startswith("_")}

    if existing is None:
        # No match — new employee
        return ActionItem(
            row_index=row_index,
            action_type="insert",
            record_data=display_data,
            reason="New employee (no match found)",
        )

    # Check if terminated → reactivate candidate
    if existing.get("status") == "terminated":
        changes = _compute_changes(record, existing)
        return ActionItem(
            row_index=row_index,
            action_type="reactivate",
            record_data=display_data,
            existing_data=existing,
            match_method=match_method,
            changes=changes if changes else None,
            reason=f"Matched terminated employee by {match_method}",
        )

    # Name-only match → flag for review (fuzzy)
    if match_method == "name":
        changes = _compute_changes(record, existing)
        return ActionItem(
            row_index=row_index,
            action_type="flag",
            record_data=display_data,
            existing_data=existing,
            match_method=match_method,
            changes=changes if changes else None,
            reason="Matched by name only — verify identity",
        )

    # Compute field-level diff
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
    """Compare import record against existing DB record.

    Returns dict of {field: [old_value, new_value]} for changed fields.
    """
    changes = {}
    for field in _COMPARE_FIELDS:
        new_val = record.get(field)
        if new_val is None:
            continue  # Import didn't provide this field

        old_val = existing.get(field)

        # Normalize for comparison
        new_str = str(new_val).strip() if new_val is not None else ""
        old_str = str(old_val).strip() if old_val is not None else ""

        if new_str.lower() != old_str.lower():
            changes[field] = [old_val, new_val]

    return changes


# ---------------------------------------------------------------------------
# Separation detection
# ---------------------------------------------------------------------------

def detect_separations(
    conn: sqlite3.Connection, import_records: List[Dict[str, Any]]
) -> List[ActionItem]:
    """Find active employees NOT present in the import roster.

    Only runs if the import has 10+ records (heuristic for "full roster").
    """
    if len(import_records) < 10:
        return []

    # Build set of identifiers from import
    import_numbers = set()
    import_names = set()
    for r in import_records:
        if r.get("employee_number"):
            import_numbers.add(str(r["employee_number"]).strip())
        if r.get("last_name") and r.get("first_name"):
            import_names.add(
                (r["last_name"].strip().lower(), r["first_name"].strip().lower())
            )

    # Get all active employees
    active = conn.execute(
        "SELECT * FROM employees WHERE status = 'active'"
    ).fetchall()

    missing_items = []
    for emp in active:
        emp_dict = dict(emp)

        # Check if present in import by number
        if emp_dict.get("employee_number") and str(emp_dict["employee_number"]).strip() in import_numbers:
            continue

        # Check if present by name
        name_key = (
            (emp_dict.get("last_name") or "").strip().lower(),
            (emp_dict.get("first_name") or "").strip().lower(),
        )
        if name_key in import_names:
            continue

        # Not found in import → separation candidate
        missing_items.append(ActionItem(
            row_index=-1,  # Not from a file row
            action_type="separate",
            record_data={},
            existing_data=emp_dict,
            reason="Active in DB but not found in import roster",
        ))

    return missing_items


# ---------------------------------------------------------------------------
# Execute function
# ---------------------------------------------------------------------------

def execute_employee_action(
    conn: sqlite3.Connection, item: ActionItem, executed_by: str
):
    """Apply a single import action to the employees table."""
    from qms.workforce.employees import (
        create_employee,
        rehire_employee,
        terminate_employee,
        update_employee,
    )

    data = item.record_data
    action = item.action_type

    if action == "insert":
        create_employee(
            conn,
            last_name=data["last_name"],
            first_name=data["first_name"],
            is_employee=data.get("is_employee", True),
            is_subcontractor=data.get("is_subcontractor", False),
            current_hire_date=data.get("current_hire_date"),
            position=data.get("position"),
            department_id=data.get("department_id"),
            job_id=data.get("job_id"),
            role_id=data.get("role_id"),
            email=data.get("email"),
            phone=data.get("phone"),
            created_by=executed_by,
            middle_initial=data.get("middle_initial"),
            notes=data.get("notes"),
        )

    elif action == "update":
        emp_id = item.existing_data["id"]
        updates = {}
        for field, (_, new_val) in (item.changes or {}).items():
            updates[field] = new_val
        if updates:
            update_employee(conn, emp_id, **updates)

    elif action == "reactivate":
        emp_id = item.existing_data["id"]
        rehire_employee(conn, emp_id, new_hire_date=data.get("current_hire_date"))
        # Also apply any field changes
        updates = {}
        for field, (_, new_val) in (item.changes or {}).items():
            updates[field] = new_val
        if updates:
            update_employee(conn, emp_id, **updates)

    elif action == "separate":
        emp_id = item.existing_data["id"]
        terminate_employee(
            conn, emp_id,
            status_reason=f"Not in import roster (import by {executed_by})",
        )

    elif action == "flag":
        # Flagged items that are approved get treated as updates
        if item.existing_data and item.changes:
            emp_id = item.existing_data["id"]
            updates = {}
            for field, (_, new_val) in item.changes.items():
                updates[field] = new_val
            if updates:
                update_employee(conn, emp_id, **updates)


# ---------------------------------------------------------------------------
# Build the spec
# ---------------------------------------------------------------------------

def get_employee_import_spec() -> ImportSpec:
    """Return the workforce employee import specification."""
    return ImportSpec(
        name="employees",
        label="Employee Import",
        module="workforce",
        target_table="employees",
        columns=EMPLOYEE_COLUMNS,
        match_fn=match_employee,
        categorize_fn=categorize_employee,
        detect_missing_fn=detect_separations,
        execute_fn=execute_employee_action,
    )
