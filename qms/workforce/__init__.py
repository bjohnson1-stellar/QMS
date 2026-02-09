"""
QMS Workforce Module

Employee registry, departments, roles, permissions, certifications,
and SIS field-location employee imports.
"""

from qms.workforce.employees import (
    add_certification,
    create_employee,
    find_employee_by_email,
    find_employee_by_name,
    find_employee_by_number,
    find_employee_by_phone,
    get_employee_permissions,
    get_expiring_certifications,
    get_next_employee_number,
    get_next_subcontractor_number,
    grant_permission,
    import_from_csv,
    import_weekly_personnel,
    rehire_employee,
    revoke_permission,
    terminate_employee,
    update_employee,
)
from qms.workforce.sis_import import (
    find_existing_employee,
    format_import_summary,
    import_employees_from_sis,
)

__all__ = [
    # employees.py -- lookups
    "find_employee_by_number",
    "find_employee_by_email",
    "find_employee_by_phone",
    "find_employee_by_name",
    # employees.py -- auto-numbering
    "get_next_employee_number",
    "get_next_subcontractor_number",
    # employees.py -- CRUD
    "create_employee",
    "update_employee",
    "terminate_employee",
    "rehire_employee",
    # employees.py -- import
    "import_weekly_personnel",
    "import_from_csv",
    # employees.py -- certifications
    "add_certification",
    "get_expiring_certifications",
    # employees.py -- permissions
    "grant_permission",
    "revoke_permission",
    "get_employee_permissions",
    # sis_import.py
    "import_employees_from_sis",
    "find_existing_employee",
    "format_import_summary",
]
