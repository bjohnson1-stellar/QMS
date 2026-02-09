"""
QMS Quality Documents Module

Quality manual content management system:
modules, sections, subsections, content blocks,
procedures, forms, templates, records.
"""

from qms.qualitydocs.loader import (
    find_xml_files,
    get_manual_summary,
    get_module_detail,
    load_module_from_file,
    load_modules_from_files,
    search_content,
)

__all__ = [
    "find_xml_files",
    "get_manual_summary",
    "get_module_detail",
    "load_module_from_file",
    "load_modules_from_files",
    "search_content",
]
