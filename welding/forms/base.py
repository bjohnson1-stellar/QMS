"""
Base form definition ABC for ASME Section IX / QB welding forms.

Each form type (WPS, PQR, WPQ, BPS, BPQ) implements this ABC to define:
- Target database tables and field mappings
- Extraction prompts for AI-based PDF parsing
- Validation rules for cross-field consistency
- Template mappings for form generation
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ValidationRule:
    """A single validation rule with code, description, and check function name."""
    code: str
    description: str
    severity: str = "error"  # "error", "warning", "info"
    category: str = "general"  # "range", "lookup", "cross-field", "required"


@dataclass
class FieldMapping:
    """Maps a source field to a database column."""
    source_field: str
    db_column: str
    db_table: str
    data_type: str = "text"  # "text", "integer", "real", "date", "boolean"
    required: bool = False
    transform: Optional[str] = None  # name of transform function


class BaseFormDefinition(ABC):
    """Abstract base for ASME form type definitions."""

    @property
    @abstractmethod
    def form_type(self) -> str:
        """Short identifier: 'wps', 'pqr', 'wpq', 'bps', 'bpq'."""

    @property
    @abstractmethod
    def asme_form(self) -> str:
        """ASME form number: 'QW-482', 'QW-483', etc."""

    @property
    @abstractmethod
    def parent_table(self) -> str:
        """Primary database table: 'weld_wps', 'weld_pqr', etc."""

    @property
    @abstractmethod
    def child_tables(self) -> List[str]:
        """Related child tables for this form type."""

    @property
    @abstractmethod
    def identifier_column(self) -> str:
        """Column name for the unique identifier (e.g., 'wps_number')."""

    @abstractmethod
    def get_extraction_prompt(self, raw_text: str, valid_values: Dict[str, List[str]]) -> str:
        """
        Build the AI extraction prompt for this form type.

        Args:
            raw_text: Raw text extracted from PDF.
            valid_values: Dict of valid lookup values for constrained fields.

        Returns:
            Prompt string for the AI model.
        """

    @abstractmethod
    def get_validation_rules(self) -> List[ValidationRule]:
        """Return list of validation rules for this form type."""

    @abstractmethod
    def get_field_mapping(self) -> List[FieldMapping]:
        """
        Return mapping from extracted fields to database columns.
        Used by the loader to insert data into the correct tables.
        """

    @abstractmethod
    def get_template_mapping(self) -> Dict[str, str]:
        """
        Return mapping from DB columns to template cells/fields.
        Used by the generator to fill Excel/PDF templates.
        Keys: 'db_table.column' format.
        Values: cell reference (Excel) or field name (PDF).
        """

    def parse_identifier_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract document identifier from filename.
        Default implementation returns None (override per form type).
        """
        return None

    def get_expected_json_structure(self) -> Dict[str, Any]:
        """
        Return the expected JSON structure for extraction responses.
        Used to validate AI model output before database insertion.
        """
        structure: Dict[str, Any] = {"parent": {}, "children": {}}

        for fm in self.get_field_mapping():
            if fm.db_table == self.parent_table:
                structure["parent"][fm.db_column] = fm.data_type
            else:
                if fm.db_table not in structure["children"]:
                    structure["children"][fm.db_table] = {}
                structure["children"][fm.db_table][fm.db_column] = fm.data_type

        return structure
