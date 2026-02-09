"""
QMS References Module

Reference standards library: extraction, clause management,
full-text search, and procedure linking.
"""

from qms.references.extractor import (
    detect_block_type,
    detect_publisher,
    extract_and_load,
    extract_text_from_pdf,
    get_reference,
    list_clauses,
    list_references,
    load_to_database,
    parse_clauses,
    search_clauses,
    search_content,
    split_into_blocks,
)

__all__ = [
    "detect_block_type",
    "detect_publisher",
    "extract_and_load",
    "extract_text_from_pdf",
    "get_reference",
    "list_clauses",
    "list_references",
    "load_to_database",
    "parse_clauses",
    "search_clauses",
    "search_content",
    "split_into_blocks",
]
