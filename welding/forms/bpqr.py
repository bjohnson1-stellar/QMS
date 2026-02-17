"""BPQR (Brazer Performance Qualification) — ASME QB-484 form definition."""

import re
from typing import Any, Dict, List, Optional

from qms.welding.forms.base import BaseFormDefinition, FieldMapping, ValidationRule


class BPQRFormDefinition(BaseFormDefinition):

    @property
    def form_type(self) -> str:
        return "bpqr"

    @property
    def asme_form(self) -> str:
        return "QB-484"

    @property
    def parent_table(self) -> str:
        return "weld_bpqr"

    @property
    def child_tables(self) -> List[str]:
        return ["weld_bpqr_tests"]

    @property
    def identifier_column(self) -> str:
        return "bpqr_number"

    def parse_identifier_from_filename(self, filename: str) -> Optional[str]:
        name = re.sub(r"\.(pdf|xlsx?)$", "", filename, flags=re.I)
        name = re.sub(r"^BPQR[-_]?", "", name, flags=re.I).strip()
        name = re.sub(r"[-_]?[Rr]ev[-_]?\w+$", "", name)
        return name if name else None

    def get_extraction_prompt(self, raw_text: str, valid_values: Dict[str, List[str]]) -> str:
        return f"""Extract all data from this ASME QB-484 Brazer Performance Qualification (BPQR) form.

This is the brazing equivalent of a WPQ — it qualifies a PERSON (brazer)
to perform brazing under a specific BPS. It documents that the brazer
demonstrated the ability to produce sound brazed joints.

Return a JSON object:

{{
  "parent": {{
    "bpqr_number": "string — BPQR identifier (construct from brazer stamp + BPS if not explicit)",
    "revision": "string or '0'",
    "brazer_name": "string — full name of brazer",
    "brazer_stamp": "string — brazer ID/stamp number",
    "bps_number": "string — BPS used for qualification",
    "brazing_process": "TB, FB, IB, RB, DB, IRB",
    "p_number_base": integer or null,
    "f_number": integer or null,
    "thickness_qualified_min": number in inches or null,
    "thickness_qualified_max": number in inches or null,
    "positions_qualified": "string — comma-separated positions",
    "test_date": "YYYY-MM-DD",
    "initial_expiration_date": "YYYY-MM-DD or null (typically test_date + 6 months)",
    "current_expiration_date": "YYYY-MM-DD or null",
    "status": "active or expired",
    "witness_name": "string or null",
    "witness_stamp": "string or null"
  }},
  "tests": [
    {{
      "test_type": "visual, peel, section, tension, macro, etc.",
      "specimen_number": "string or null",
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
- BPQR identifies the BRAZER (not the procedure like BPQ/BPS)
- Extract brazer name/stamp from the form even if in header/title
- If expiration date is not on the form, calculate as test_date + 180 days
- Multiple test types may appear — capture all
- Dates in YYYY-MM-DD format

PDF TEXT:
{raw_text}"""

    def get_validation_rules(self) -> List[ValidationRule]:
        return [
            ValidationRule("BPQR-REQ-001", "BPQR number is required", "error", "required"),
            ValidationRule("BPQR-REQ-002", "Brazer name or stamp is required", "error", "required"),
            ValidationRule("BPQR-REQ-003", "Brazing process is required", "error", "required"),
            ValidationRule("BPQR-REQ-004", "Test date is required", "error", "required"),
            ValidationRule("BPQR-PROC-001", "Brazing process must be valid (TB, FB, IB, RB, DB, IRB)", "error", "lookup"),
            ValidationRule("BPQR-EXP-001", "expiration_date should be test_date + 180 days", "warning", "cross-field"),
            ValidationRule("BPQR-BPS-001", "BPS reference should exist in database", "warning", "cross-field"),
            ValidationRule("BPQR-TEST-001", "At least one test result should be present", "warning", "cross-field"),
        ]

    def get_field_mapping(self) -> List[FieldMapping]:
        return [
            FieldMapping("bpqr_number", "bpqr_number", "weld_bpqr", "text", True),
            FieldMapping("revision", "revision", "weld_bpqr", "text"),
            FieldMapping("brazer_name", "brazer_name", "weld_bpqr", "text"),
            FieldMapping("brazer_stamp", "brazer_stamp", "weld_bpqr", "text"),
            FieldMapping("bps_number", "bps_number", "weld_bpqr", "text"),
            FieldMapping("brazing_process", "brazing_process", "weld_bpqr", "text", True),
            FieldMapping("p_number_base", "p_number_base", "weld_bpqr", "integer"),
            FieldMapping("f_number", "f_number", "weld_bpqr", "integer"),
            FieldMapping("thickness_qualified_min", "thickness_qualified_min", "weld_bpqr", "real"),
            FieldMapping("thickness_qualified_max", "thickness_qualified_max", "weld_bpqr", "real"),
            FieldMapping("positions_qualified", "positions_qualified", "weld_bpqr", "text"),
            FieldMapping("test_date", "test_date", "weld_bpqr", "date"),
            FieldMapping("initial_expiration_date", "initial_expiration_date", "weld_bpqr", "date"),
            FieldMapping("current_expiration_date", "current_expiration_date", "weld_bpqr", "date"),
            FieldMapping("status", "status", "weld_bpqr", "text"),
            FieldMapping("witness_name", "witness_name", "weld_bpqr", "text"),
            FieldMapping("test_type", "test_type", "weld_bpqr_tests", "text"),
            FieldMapping("results", "results", "weld_bpqr_tests", "text"),
            FieldMapping("result", "result", "weld_bpqr_tests", "text"),
        ]

    def get_template_mapping(self) -> Dict[str, str]:
        return {
            "weld_bpqr.bpqr_number": "B2",
            "weld_bpqr.brazer_name": "B4",
            "weld_bpqr.brazer_stamp": "F4",
            "weld_bpqr.bps_number": "B6",
            "weld_bpqr.brazing_process": "F6",
            "weld_bpqr.p_number_base": "B8",
            "weld_bpqr.f_number": "D8",
            "weld_bpqr.thickness_qualified_min": "B10",
            "weld_bpqr.thickness_qualified_max": "D10",
            "weld_bpqr.positions_qualified": "B12",
            "weld_bpqr.test_date": "B14",
            "weld_bpqr.current_expiration_date": "D14",
            "weld_bpqr.witness_name": "B16",
            "weld_bpqr.witness_stamp": "D16",
        }
