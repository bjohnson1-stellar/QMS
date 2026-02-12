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
    get_next_stamp,
    validate_registration,
    register_new_welder,
    add_initial_wpq,
    register_batch,
)
from qms.welding.export_lookups import export_lookups
from qms.welding.cert_requests import (
    process_cert_request,
    list_cert_requests,
    get_cert_request_detail,
    enter_coupon_result,
    assign_wpq_from_coupon,
    schedule_retest,
    approve_cert_request,
)

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
    "get_next_stamp",
    "validate_registration",
    "register_new_welder",
    "add_initial_wpq",
    "register_batch",
    # export
    "export_lookups",
    # cert requests
    "process_cert_request",
    "list_cert_requests",
    "get_cert_request_detail",
    "enter_coupon_result",
    "assign_wpq_from_coupon",
    "schedule_retest",
    "approve_cert_request",
]
