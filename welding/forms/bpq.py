"""BPQ (Brazing Performance Qualification) — ASME QB-483/484 form definition."""

import re
from typing import Any, Dict, List, Optional

from qms.welding.forms.base import BaseFormDefinition, FieldMapping, ValidationRule


class BPQFormDefinition(BaseFormDefinition):

    @property
    def form_type(self) -> str:
        return "bpq"

    @property
    def asme_form(self) -> str:
        return "QB-483/484"

    @property
    def parent_table(self) -> str:
        return "weld_bpq"

    @property
    def child_tables(self) -> List[str]:
        return [
            "weld_bpq_base_metals",
            "weld_bpq_filler_metals",
            "weld_bpq_tests",
        ]

    @property
    def identifier_column(self) -> str:
        return "bpq_number"

    def parse_identifier_from_filename(self, filename: str) -> Optional[str]:
        name = re.sub(r"\.(pdf|xlsx?)$", "", filename, flags=re.I)
        name = re.sub(r"^(BPQ|BPQR)[-_]?", "", name, flags=re.I).strip()
        return name if name else None

    def get_extraction_prompt(self, raw_text: str, valid_values: Dict[str, List[str]]) -> str:
        return f"""Extract all data from this ASME QB-483/484 Brazing Performance Qualification (BPQ) form.

This form qualifies a brazer (person) similar to how WPQ qualifies a welder.
It may also be a Brazing Procedure Qualification Record (BPQR) — extract both.

Return a JSON object:

{{
  "parent": {{
    "bpq_number": "string — BPQ/BPQR identifier",
    "revision": "string or '0'",
    "bps_number": "string — supporting BPS number",
    "test_date": "YYYY-MM-DD",
    "status": "active",
    "coupon_id": "string or null",
    "witness_name": "string or null",
    "witness_company": "string or null",
    "lab_name": "string or null",
    "lab_report_number": "string or null"
  }},
  "base_metals": [
    {{
      "metal_sequence": 1,
      "p_number": integer or null,
      "material_spec": "string",
      "thickness": number in inches or null,
      "heat_number": "string or null"
    }}
  ],
  "filler_metals": [
    {{
      "f_number": integer or null,
      "sfa_spec": "SFA-5.8",
      "aws_class": "BAg-1, BCuP-5, etc.",
      "lot_number": "string or null"
    }}
  ],
  "tests": [
    {{
      "test_type": "visual, peel, section, tension, etc.",
      "specimen_number": "string or null",
      "acceptance_criteria": "string or null",
      "result": "Acceptable or Rejected"
    }}
  ]
}}

Also check if this is a BPQR (brazer performance record — similar to WPQ for welders).
If BPQR fields are present (brazer_name, brazer_stamp, positions_qualified, expiration),
add them to the parent object as additional fields.

RULES:
- Use null for missing values
- Dates in YYYY-MM-DD format
- Capture ALL test results

PDF TEXT:
{raw_text}"""

    def get_validation_rules(self) -> List[ValidationRule]:
        return [
            ValidationRule("BPQ-REQ-001", "BPQ number is required", "error", "required"),
            ValidationRule("BPQ-REQ-002", "Test date is required", "error", "required"),
            ValidationRule("BPQ-BASE-001", "P-number should exist in lookup table", "warning", "lookup"),
            ValidationRule("BPQ-TEST-001", "At least one test result should be present", "warning", "cross-field"),
        ]

    def get_field_mapping(self) -> List[FieldMapping]:
        return [
            FieldMapping("bpq_number", "bpq_number", "weld_bpq", "text", True),
            FieldMapping("revision", "revision", "weld_bpq", "text"),
            FieldMapping("bps_number", "bps_number", "weld_bpq", "text"),
            FieldMapping("test_date", "test_date", "weld_bpq", "date"),
            FieldMapping("status", "status", "weld_bpq", "text"),
            FieldMapping("witness_name", "witness_name", "weld_bpq", "text"),
            FieldMapping("p_number", "p_number", "weld_bpq_base_metals", "integer"),
            FieldMapping("material_spec", "material_spec", "weld_bpq_base_metals", "text"),
            FieldMapping("f_number", "f_number", "weld_bpq_filler_metals", "integer"),
            FieldMapping("sfa_spec", "sfa_spec", "weld_bpq_filler_metals", "text"),
            FieldMapping("test_type", "test_type", "weld_bpq_tests", "text"),
            FieldMapping("result", "result", "weld_bpq_tests", "text"),
        ]

    def get_template_mapping(self) -> Dict[str, str]:
        return {
            "weld_bpq.bpq_number": "B2",
            "weld_bpq.bps_number": "F2",
            "weld_bpq.test_date": "H2",
            "weld_bpq_base_metals.p_number": "B8",
            "weld_bpq_base_metals.material_spec": "D8",
            "weld_bpq_filler_metals.sfa_spec": "B11",
            "weld_bpq_filler_metals.aws_class": "D11",
            "weld_bpq_tests.test_type": "B14",
            "weld_bpq_tests.result": "F14",
        }
