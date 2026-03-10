"""
QMS Quality Documents Module

Quality manual content management system:
modules, sections, subsections, content blocks,
procedures, forms, templates, records.

M3 quality programs and M4 SOPs with categories,
scope tags, intake pipeline, and revision history.
"""

from qms.qualitydocs.loader import (
    find_xml_files,
    get_manual_summary,
    get_module_detail,
    get_section_content,
    load_module_from_file,
    load_modules_from_files,
    search_content,
)

from qms.qualitydocs.db import (
    list_programs,
    get_program,
    create_program,
    list_categories,
    get_category,
    create_category,
    seed_programs,
    seed_categories,
    list_sops,
    get_sop,
    create_sop,
    approve_sop,
    publish_sop,
    search_sops,
    add_sop_history,
    get_sop_history,
    create_intake,
    update_intake,
    get_intake,
    list_intakes,
)

__all__ = [
    # Loader (M1/M2)
    "find_xml_files",
    "get_manual_summary",
    "get_module_detail",
    "get_section_content",
    "load_module_from_file",
    "load_modules_from_files",
    "search_content",
    # Programs (M3)
    "list_programs",
    "get_program",
    "create_program",
    # Categories (M4)
    "list_categories",
    "get_category",
    "create_category",
    "seed_programs",
    "seed_categories",
    # SOPs (M4)
    "list_sops",
    "get_sop",
    "create_sop",
    "approve_sop",
    "publish_sop",
    "search_sops",
    # History
    "add_sop_history",
    "get_sop_history",
    # Intake
    "create_intake",
    "update_intake",
    "get_intake",
    "list_intakes",
]
