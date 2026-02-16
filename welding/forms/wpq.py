"""WPQ (Welder Performance Qualification) — ASME QW-484 form definition."""

import re
from typing import Any, Dict, List, Optional

from qms.welding.forms.base import BaseFormDefinition, FieldMapping, ValidationRule


class WPQFormDefinition(BaseFormDefinition):

    @property
    def form_type(self) -> str:
        return "wpq"

    @property
    def asme_form(self) -> str:
        return "QW-484"

    @property
    def parent_table(self) -> str:
        return "weld_wpq"

    @property
    def child_tables(self) -> List[str]:
        return ["weld_wpq_tests"]

    @property
    def identifier_column(self) -> str:
        return "wpq_number"

    def parse_identifier_from_filename(self, filename: str) -> Optional[str]:
        name = re.sub(r"\.(pdf|xlsx?)$", "", filename, flags=re.I)
        # Try to extract welder name and process from filename
        # Common patterns: "LastName FirstName - WPS.pdf", "STAMP-WPQ-001.pdf"
        name = re.sub(r"^WPQ[-_]?", "", name, flags=re.I).strip()
        return name if name else None

    def get_extraction_prompt(self, raw_text: str, valid_values: Dict[str, List[str]]) -> str:
        processes = ", ".join(valid_values.get("processes", []))
        positions = ", ".join(valid_values.get("positions", []))
        p_numbers = ", ".join(valid_values.get("p_numbers", []))

        return f"""Extract all data from this ASME QW-484 Welder Performance Qualification (WPQ) form.

This is a welder qualification test record. It documents that a specific welder
demonstrated the ability to produce sound welds under a specific WPS.

Return a JSON object:

{{
  "parent": {{
    "wpq_number": "string — WPQ identifier (construct from welder stamp + WPS if not explicit)",
    "revision": "string or '0'",
    "welder_name": "string — full name of welder",
    "welder_stamp": "string — welder ID/stamp number",
    "wps_number": "string — WPS used for qualification",
    "process_type": "one of: {processes}",
    "p_number_base": integer from [{p_numbers}] or null,
    "p_number_filler": integer or null,
    "f_number": integer or null,
    "thickness_qualified_min": number in inches or null,
    "thickness_qualified_max": number in inches or null,
    "diameter_qualified_min": number in inches or null,
    "groove_positions_qualified": "comma-separated from [{positions}]",
    "fillet_positions_qualified": "comma-separated or null",
    "progression": "uphill, downhill, or null",
    "backing_type": "with backing, without backing, or null",
    "test_date": "YYYY-MM-DD",
    "initial_expiration_date": "YYYY-MM-DD or null (typically test_date + 6 months)",
    "current_expiration_date": "YYYY-MM-DD or null",
    "status": "active or expired",
    "witness_name": "string or null",
    "witness_stamp": "string or null"
  }},
  "tests": [
    {{
      "test_type": "visual, bend, RT, macro, fillet_break, etc.",
      "specimen_number": "string or null",
      "bend_type": "side, face, root, or null",
      "results": "string — description of results",
      "acceptance_criteria": "string or null",
      "result": "Acceptable or Rejected",
      "examiner_name": "string or null",
      "examiner_date": "YYYY-MM-DD or null"
    }}
  ]
}}

RULES:
- Use null for missing values
- WPQ identifies the WELDER (not the procedure like WPS/PQR)
- Extract welder name/stamp from the form even if in header/title
- If expiration date is not on the form, calculate as test_date + 180 days
- Multiple test types may appear (visual, bend, RT, etc.) — capture all
- For certs in welder folders, the folder name often contains the welder name

PDF TEXT:
{raw_text}"""

    def get_validation_rules(self) -> List[ValidationRule]:
        return [
            ValidationRule("WPQ-REQ-001", "WPQ number is required", "error", "required"),
            ValidationRule("WPQ-REQ-002", "Welder name or stamp is required", "error", "required"),
            ValidationRule("WPQ-REQ-003", "Process type is required", "error", "required"),
            ValidationRule("WPQ-REQ-004", "Test date is required", "error", "required"),
            ValidationRule("WPQ-PROC-001", "Process type must be valid", "error", "lookup"),
            ValidationRule("WPQ-POS-001", "Position codes must be valid", "error", "lookup"),
            ValidationRule("WPQ-EXP-001", "expiration_date should be test_date + 180 days", "warning", "cross-field"),
            ValidationRule("WPQ-WPS-001", "WPS reference should exist in database", "warning", "cross-field"),
            ValidationRule("WPQ-TEST-001", "At least one test result should be present", "warning", "cross-field"),
        ]

    def get_field_mapping(self) -> List[FieldMapping]:
        return [
            FieldMapping("wpq_number", "wpq_number", "weld_wpq", "text", True),
            FieldMapping("revision", "revision", "weld_wpq", "text"),
            FieldMapping("welder_name", "welder_name", "weld_wpq", "text"),
            FieldMapping("welder_stamp", "welder_stamp", "weld_wpq", "text"),
            FieldMapping("wps_number", "wps_number", "weld_wpq", "text"),
            FieldMapping("process_type", "process_type", "weld_wpq", "text", True),
            FieldMapping("p_number_base", "p_number_base", "weld_wpq", "integer"),
            FieldMapping("f_number", "f_number", "weld_wpq", "integer"),
            FieldMapping("thickness_qualified_min", "thickness_qualified_min", "weld_wpq", "real"),
            FieldMapping("thickness_qualified_max", "thickness_qualified_max", "weld_wpq", "real"),
            FieldMapping("diameter_qualified_min", "diameter_qualified_min", "weld_wpq", "real"),
            FieldMapping("groove_positions_qualified", "groove_positions_qualified", "weld_wpq", "text"),
            FieldMapping("fillet_positions_qualified", "fillet_positions_qualified", "weld_wpq", "text"),
            FieldMapping("test_date", "test_date", "weld_wpq", "date"),
            FieldMapping("initial_expiration_date", "initial_expiration_date", "weld_wpq", "date"),
            FieldMapping("current_expiration_date", "current_expiration_date", "weld_wpq", "date"),
            FieldMapping("status", "status", "weld_wpq", "text"),
            FieldMapping("witness_name", "witness_name", "weld_wpq", "text"),
            FieldMapping("test_type", "test_type", "weld_wpq_tests", "text", True),
            FieldMapping("results", "results", "weld_wpq_tests", "text"),
            FieldMapping("result", "result", "weld_wpq_tests", "text"),
        ]

    def get_template_mapping(self) -> Dict[str, str]:
        return {
            "weld_wpq.wpq_number": "B2",
            "weld_wpq.welder_name": "B4",
            "weld_wpq.welder_stamp": "F4",
            "weld_wpq.wps_number": "B6",
            "weld_wpq.process_type": "F6",
            "weld_wpq.p_number_base": "B8",
            "weld_wpq.f_number": "D8",
            "weld_wpq.thickness_qualified_min": "B10",
            "weld_wpq.thickness_qualified_max": "D10",
            "weld_wpq.diameter_qualified_min": "F10",
            "weld_wpq.groove_positions_qualified": "B12",
            "weld_wpq.fillet_positions_qualified": "D12",
            "weld_wpq.progression": "F12",
            "weld_wpq.test_date": "B14",
            "weld_wpq.current_expiration_date": "D14",
            "weld_wpq.witness_name": "B16",
            "weld_wpq.witness_stamp": "D16",
        }
