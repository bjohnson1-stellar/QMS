"""BPQR (Brazer Performance Qualification) form definition.

NOTE on ASME naming: Real-world forms are typically titled "BPQ" or
"Brazer Performance Qualification" even though our internal schema uses
"bpqr" to distinguish from the procedure qualification record (weld_bpq).
The classifier should route documents with brazer name/stamp fields here.
"""

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
        # Handle both BPQ and BPQR prefixes — real forms use "BPQ" for person quals
        name = re.sub(r"^(BPQR|BPQ)[-_]?", "", name, flags=re.I).strip()
        # Strip leading "B-" identification numbers (e.g., "B-33 - BPS-...")
        m = re.match(r"^(B-\d+)", name)
        if m:
            return m.group(1)
        name = re.sub(r"[-_]?[Rr]ev[-_]?\w+$", "", name)
        return name if name else None

    def get_extraction_prompt(self, raw_text: str, valid_values: Dict[str, List[str]]) -> str:
        return f"""Extract all data from this Brazer Performance Qualification (BPQ) form.

This qualifies a PERSON (brazer) — the brazing equivalent of a WPQ.
The form has two data columns: "Actual Values" (what was used on the test coupon)
and "Range Qualified" (what the brazer is now qualified to do).

Return a JSON object:

{{
  "parent": {{
    "bpqr_number": "string — Identification No. (e.g. B-33)",
    "revision": "string or '0'",
    "brazer_name": "string — full name of brazer/operator",
    "brazer_stamp": "string — brazer ID number, or same as bpqr_number if not separate",
    "bps_number": "string — BPS followed during brazing",
    "test_date": "YYYY-MM-DD — date coupon was brazed",

    "brazing_process": "string — e.g. 'Torch Brazing (TB) - Manual'",
    "torch_type": "Manual Torch, Mechanical, or null",

    "coupon_base_metal_1": "string — first base metal spec (e.g. 'ASTM B280 (Copper Tubing, ACR Type L)')",
    "coupon_base_metal_2": "string — second base metal spec or null",
    "coupon_form": "Plate or Pipe/Tube",
    "coupon_diameter": "string — pipe/tube diameter or null (e.g. '2-1/8')",
    "coupon_thickness": number in inches or null,

    "p_number_actual": "string — actual P-number range (e.g. '107 TO 107')",
    "aws_bm_number_actual": "string — actual AWS BM-number range (e.g. '300 TO 300')",
    "joint_type": "string — actual joint type (e.g. 'Socket (lap) - Tube/fitting')",
    "overlap_length": number in inches or null,
    "joint_clearance": number in inches or null,

    "p_number_base": integer — qualified P-number,
    "aws_bm_number": "string — qualified AWS BM-number range or null",
    "f_number": integer — qualified F-number,
    "filler_sfa_spec": "string — e.g. 'AWS A5.8'",
    "filler_aws_class": "string — e.g. 'BCuP-5'",
    "filler_product_form": "string — e.g. '0.050 x XX Rod'",
    "thickness_qualified_min": number in inches or null,
    "thickness_qualified_max": number in inches or null,
    "diameter_qualified_min": number in inches or null,
    "diameter_qualified_max": number in inches or null,
    "joint_type_qualified": "string — qualified joint type or null",
    "overlap_qualified": "string — e.g. '4X Mat. Thickness up to 2.5\"'",
    "positions_qualified": "string — e.g. 'All Positions'",

    "status": "active or expired",
    "lab_name": "string — testing lab name or null",
    "lab_test_number": "string — lab test/report number or null",
    "organization": "string — certifying organization",
    "certified_by": "string — name and title of certifier",
    "certified_date": "YYYY-MM-DD — certification date"
  }},
  "tests": [
    {{
      "test_type": "peel, section, tension, transverse_bend, longitudinal_bend",
      "test_standard": "QB-462.3, QB-462.1, QB-462.2(a), QB-462.2(b), etc.",
      "position": "string — e.g. 'Horizontal T1/T2', 'Vertical P1/P2'",
      "result": "Accept or Reject",
      "examiner_name": "string or null",
      "examiner_company": "string or null",
      "examiner_date": "YYYY-MM-DD or null"
    }}
  ]
}}

RULES:
- Use null for missing values
- This form qualifies a BRAZER (person), not a procedure
- The "Actual Values" column records what was used on the test coupon
- The "Range Qualified" column defines the brazer's qualification scope
- Create a separate test entry for each position/result row in the testing matrix
- Mechanical test checkboxes (Peel, Section, Tension) indicate which tests were performed
- Dates in YYYY-MM-DD format
- All dimensions in inches
- The Identification No. is the bpqr_number (e.g. "B-33")
- brazer_stamp may equal bpqr_number if no separate stamp field exists
- Parse lab info from "Mechanical Tests Conducted by" and "Lab Test No." fields

PDF TEXT:
{raw_text}"""

    def get_validation_rules(self) -> List[ValidationRule]:
        return [
            ValidationRule("BPQR-REQ-001", "BPQR number is required", "error", "required"),
            ValidationRule("BPQR-REQ-002", "Brazer name is required", "error", "required"),
            ValidationRule("BPQR-REQ-003", "Brazing process is required", "error", "required"),
            ValidationRule("BPQR-REQ-004", "Test date is required", "error", "required"),
            ValidationRule("BPQR-REQ-005", "At least one base metal spec is required", "error", "required"),
            ValidationRule("BPQR-PROC-001", "Brazing process must contain valid type (TB, FB, IB, RB, DB, IRB)", "error", "lookup"),
            ValidationRule("BPQR-THICK-001", "thickness_qualified_min <= thickness_qualified_max", "error", "range"),
            ValidationRule("BPQR-DIA-001", "diameter_qualified_min <= diameter_qualified_max", "error", "range"),
            ValidationRule("BPQR-BPS-001", "BPS reference should exist in database", "warning", "cross-field"),
            ValidationRule("BPQR-TEST-001", "At least one test result should be present", "warning", "cross-field"),
            ValidationRule("BPQR-CERT-001", "Certification fields should be complete", "warning", "cross-field"),
        ]

    def get_field_mapping(self) -> List[FieldMapping]:
        return [
            # Identity
            FieldMapping("bpqr_number", "bpqr_number", "weld_bpqr", "text", True),
            FieldMapping("revision", "revision", "weld_bpqr", "text"),
            FieldMapping("brazer_name", "brazer_name", "weld_bpqr", "text", True),
            FieldMapping("brazer_stamp", "brazer_stamp", "weld_bpqr", "text"),
            FieldMapping("bps_number", "bps_number", "weld_bpqr", "text"),
            FieldMapping("test_date", "test_date", "weld_bpqr", "date", True),
            # Process
            FieldMapping("brazing_process", "brazing_process", "weld_bpqr", "text", True),
            FieldMapping("torch_type", "torch_type", "weld_bpqr", "text"),
            # Coupon base metals
            FieldMapping("coupon_base_metal_1", "coupon_base_metal_1", "weld_bpqr", "text"),
            FieldMapping("coupon_base_metal_2", "coupon_base_metal_2", "weld_bpqr", "text"),
            FieldMapping("coupon_form", "coupon_form", "weld_bpqr", "text"),
            FieldMapping("coupon_diameter", "coupon_diameter", "weld_bpqr", "text"),
            FieldMapping("coupon_thickness", "coupon_thickness", "weld_bpqr", "real"),
            # Actual values
            FieldMapping("p_number_actual", "p_number_actual", "weld_bpqr", "text"),
            FieldMapping("aws_bm_number_actual", "aws_bm_number_actual", "weld_bpqr", "text"),
            FieldMapping("joint_type", "joint_type", "weld_bpqr", "text"),
            FieldMapping("overlap_length", "overlap_length", "weld_bpqr", "real"),
            FieldMapping("joint_clearance", "joint_clearance", "weld_bpqr", "real"),
            # Range qualified
            FieldMapping("p_number_base", "p_number_base", "weld_bpqr", "integer"),
            FieldMapping("aws_bm_number", "aws_bm_number", "weld_bpqr", "text"),
            FieldMapping("f_number", "f_number", "weld_bpqr", "integer"),
            FieldMapping("filler_sfa_spec", "filler_sfa_spec", "weld_bpqr", "text"),
            FieldMapping("filler_aws_class", "filler_aws_class", "weld_bpqr", "text"),
            FieldMapping("filler_product_form", "filler_product_form", "weld_bpqr", "text"),
            FieldMapping("thickness_qualified_min", "thickness_qualified_min", "weld_bpqr", "real"),
            FieldMapping("thickness_qualified_max", "thickness_qualified_max", "weld_bpqr", "real"),
            FieldMapping("diameter_qualified_min", "diameter_qualified_min", "weld_bpqr", "real"),
            FieldMapping("diameter_qualified_max", "diameter_qualified_max", "weld_bpqr", "real"),
            FieldMapping("joint_type_qualified", "joint_type_qualified", "weld_bpqr", "text"),
            FieldMapping("overlap_qualified", "overlap_qualified", "weld_bpqr", "text"),
            FieldMapping("positions_qualified", "positions_qualified", "weld_bpqr", "text"),
            # Status / certification
            FieldMapping("status", "status", "weld_bpqr", "text"),
            FieldMapping("lab_name", "lab_name", "weld_bpqr", "text"),
            FieldMapping("lab_test_number", "lab_test_number", "weld_bpqr", "text"),
            FieldMapping("organization", "organization", "weld_bpqr", "text"),
            FieldMapping("certified_by", "certified_by", "weld_bpqr", "text"),
            FieldMapping("certified_date", "certified_date", "weld_bpqr", "date"),
            # Tests
            FieldMapping("test_type", "test_type", "weld_bpqr_tests", "text"),
            FieldMapping("test_standard", "test_standard", "weld_bpqr_tests", "text"),
            FieldMapping("position", "position", "weld_bpqr_tests", "text"),
            FieldMapping("result", "result", "weld_bpqr_tests", "text"),
        ]

    def get_template_mapping(self) -> Dict[str, str]:
        return {
            # Header
            "weld_bpqr.bpqr_number": "G2",
            "weld_bpqr.brazer_name": "C2",
            "weld_bpqr.bps_number": "C4",
            "weld_bpqr.test_date": "G4",
            "weld_bpqr.coupon_base_metal_1": "C5",
            "weld_bpqr.coupon_base_metal_2": "C6",
            # Actual values column
            "weld_bpqr.brazing_process": "C8",
            "weld_bpqr.torch_type": "C9",
            "weld_bpqr.p_number_actual": "C10",
            "weld_bpqr.aws_bm_number_actual": "C11",
            "weld_bpqr.coupon_diameter": "C12",
            "weld_bpqr.coupon_thickness": "C13",
            "weld_bpqr.joint_type": "C14",
            "weld_bpqr.overlap_length": "C15",
            "weld_bpqr.joint_clearance": "C16",
            "weld_bpqr.filler_sfa_spec": "C17",
            "weld_bpqr.filler_aws_class": "C18",
            "weld_bpqr.f_number": "C19",
            "weld_bpqr.filler_product_form": "C20",
            # Range qualified column
            "weld_bpqr.positions_qualified": "G21",
            "weld_bpqr.thickness_qualified_min": "G13",
            "weld_bpqr.thickness_qualified_max": "H13",
            "weld_bpqr.diameter_qualified_min": "G12",
            "weld_bpqr.diameter_qualified_max": "H12",
            # Certification
            "weld_bpqr.organization": "C30",
            "weld_bpqr.certified_by": "C31",
            "weld_bpqr.certified_date": "G31",
        }
