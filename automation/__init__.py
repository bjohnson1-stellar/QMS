"""
QMS Automation Module

Generic JSON-based request processing: scans incoming directory for JSON files,
routes by "type" field to registered handlers, logs results.
"""

from qms.automation.dispatcher import (
    get_processing_log,
    process_all,
    process_file,
    register_handler,
)

__all__ = [
    "process_all",
    "process_file",
    "register_handler",
    "get_processing_log",
]
