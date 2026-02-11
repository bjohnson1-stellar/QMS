"""
QMS Welding Module

ASME IX / AWS welding program management:
WPS, PQR, WPQ, BPS, BPQ, BPQR documents,
welder registry, continuity tracking, production welds,
NDT results, notifications, and document revision control.
"""

from qms.welding.intake import (
    classify_document,
    extract_revision,
    find_existing_document,
    get_dashboard_data,
    list_active_welders,
    process_file,
    process_inbox,
    register_welder,
)
from qms.welding.importer import (
    import_from_excel,
    parse_wpq_code,
    validate_excel,
)
from qms.welding.weekly import (
    process_weekly_import,
)
from qms.welding.notifications import (
    generate_all_notifications,
    get_notification_summary,
    list_active_notifications,
)
from qms.welding.registration import (
    add_initial_wpq,
    get_next_stamp,
    register_batch,
    register_new_welder,
    validate_registration,
)
from qms.welding.sharepoint import preview_sync_data
from qms.welding.export_lookups import export_lookups

__all__ = [
    # intake
    "classify_document",
    "extract_revision",
    "find_existing_document",
    "get_dashboard_data",
    "list_active_welders",
    "process_file",
    "process_inbox",
    "register_welder",
    # importer
    "import_from_excel",
    "parse_wpq_code",
    "validate_excel",
    # weekly
    "process_weekly_import",
    # notifications
    "generate_all_notifications",
    "get_notification_summary",
    "list_active_notifications",
    # registration
    "add_initial_wpq",
    "get_next_stamp",
    "register_batch",
    "register_new_welder",
    "validate_registration",
    # sharepoint (lazy — requires 'pip install qms[sharepoint]')
    "preview_sync_data",
    # export
    "export_lookups",
]
