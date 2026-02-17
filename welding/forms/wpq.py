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

This qualifies a PERSON (welder) — it documents that a specific welder
demonstrated the ability to produce sound welds under a specific WPS.
The form has two data columns: "Actual Values" (what was used on the test coupon)
and "Range Qualified" (what the welder is now qualified to do).

Return a JSON object:

{{
  "parent": {{
    "wpq_number": "string — WPQ identifier (construct from welder stamp + WPS if not explicit)",
    "revision": "string or '0'",
    "welder_name": "string — full name of welder",
    "welder_stamp": "string — welder ID/stamp number (Identification No.)",
    "wps_number": "string — WPS followed by welder",
    "process_type": "one of: {processes}",
    "process_variation": "Manual, Semiautomatic, Machine, or Automatic",
    "test_date": "YYYY-MM-DD",

    "coupon_base_metal": "string — base metal pairing (e.g. 'P1 to P1')",
    "coupon_thickness": number in inches or null,
    "coupon_diameter": "string — pipe size (e.g. '2\" N.P.S (2.375\" OD)') or null",

    "p_number_actual": "string — actual P-number pairing (e.g. 'P-1 to P-1')",
    "backing_actual": "string — actual backing used (e.g. 'N/A Single Sided weld open root')",
    "filler_sfa_spec": "string — SFA specification (e.g. 'SFA/A5.1')",
    "filler_aws_class": "string — electrode classification (e.g. 'E6010/E7018')",
    "f_number_actual": "string — actual F-number(s) (e.g. 'F3/F4' for dual-process)",
    "consumable_insert": "string — e.g. 'N/A None'",
    "filler_type": "string — e.g. 'Coated Solid Electrodes'",
    "deposit_thickness_actual": number in inches or null,
    "test_position": "string — actual test position (e.g. '6G')",
    "backing_gas": "string — backing/fuel gas or 'N/A None'",
    "transfer_mode": "string — GMAW transfer mode or 'N/A'",
    "current_type": "string — current type/polarity (e.g. 'DCEP', 'AC', 'DCEN')",

    "p_number_base": integer from [{p_numbers}] or null,
    "p_number_filler": integer or null,
    "p_number_qualified": "string — qualified P-number range (e.g. 'P1 thru P11 & P4X')",
    "f_number": integer — primary qualified F-number,
    "f_number_qualified": "string — qualified F-number range (e.g. 'F4,F3,F2 & F1')",
    "thickness_qualified_min": number in inches or null,
    "thickness_qualified_max": number in inches or null,
    "diameter_qualified_min": number in inches or null,
    "diameter_qualified_max": number in inches or null,
    "deposit_thickness_max": number in inches or null,
    "groove_positions_qualified": "string — qualified groove positions (e.g. 'All')",
    "fillet_positions_qualified": "string or null",
    "progression": "uphill, downhill, or null",
    "backing_type": "string — qualified backing (e.g. 'Open Root or with Backing')",
    "filler_type_qualified": "string — qualified filler type or null",

    "initial_expiration_date": "YYYY-MM-DD or null (typically test_date + 6 months)",
    "current_expiration_date": "YYYY-MM-DD or null",
    "status": "active or expired",

    "witness_name": "string — Welding Supervised / Witnessed By",
    "witness_company": "string — witness company or null",
    "evaluator_name": "string — Film or Specimens Evaluated By or null",
    "evaluator_company": "string — evaluator company or null",
    "lab_name": "string — Mechanical Tests Conducted By or null",
    "lab_test_number": "string — Laboratory Test No. or null",
    "organization": "string — certifying organization",
    "certified_by": "string — certifier name or null",
    "certified_date": "YYYY-MM-DD or null"
  }},
  "tests": [
    {{
      "test_type": "visual, guided_bend, radiographic, fillet_fracture, macro, other",
      "specimen_number": "string or null",
      "bend_type": "side, face, root, transverse, or null",
      "results": "string — description of results",
      "acceptance_criteria": "string or null",
      "result": "Acceptable, Rejected, or N/A",
      "defect_description": "string — length/percent of defects for fillet tests, or null",
      "fillet_size": number in inches or null,
      "concavity_convexity": number in inches or null,
      "examiner_name": "string or null",
      "examiner_company": "string or null",
      "examiner_date": "YYYY-MM-DD or null"
    }}
  ]
}}

RULES:
- Use null for missing values, never empty strings
- WPQ identifies the WELDER (not the procedure like WPS/PQR)
- The "Actual Values" column records what was used on the test coupon
- The "Range Qualified" column defines the welder's qualification scope
- Extract welder name/stamp from the form even if in header/title
- If expiration date is not on the form, calculate as test_date + 180 days
- For dual-process tests (e.g., GTAW root + SMAW fill), filler/F-number fields
  may have dual values separated by "/" — capture as-is (e.g., "F3/F4")
- Create a separate test entry for each test type in the results section
- Guided-bend tests: create one entry per specimen (Type/Result pair)
- Radiographic, fillet fracture, macro, and visual are whole-weld assessments
- Dates in YYYY-MM-DD format, dimensions in inches
- ****** or blank fields in templates mean "to be filled in" — use null

PDF TEXT:
{raw_text}"""

    def get_validation_rules(self) -> List[ValidationRule]:
        return [
            ValidationRule("WPQ-REQ-001", "WPQ number is required", "error", "required"),
            ValidationRule("WPQ-REQ-002", "Welder name or stamp is required", "error", "required"),
            ValidationRule("WPQ-REQ-003", "Process type is required", "error", "required"),
            ValidationRule("WPQ-REQ-004", "Test date is required", "error", "required"),
            ValidationRule("WPQ-REQ-005", "WPS number is required", "error", "required"),
            ValidationRule("WPQ-PROC-001", "Process type must be valid ASME process", "error", "lookup"),
            ValidationRule("WPQ-POS-001", "Position codes must be valid", "error", "lookup"),
            ValidationRule("WPQ-THICK-001", "thickness_qualified_min <= thickness_qualified_max", "error", "range"),
            ValidationRule("WPQ-DIA-001", "diameter_qualified_min <= diameter_qualified_max when both present", "error", "range"),
            ValidationRule("WPQ-EXP-001", "expiration_date should be test_date + 180 days", "warning", "cross-field"),
            ValidationRule("WPQ-WPS-001", "WPS reference should exist in database", "warning", "cross-field"),
            ValidationRule("WPQ-TEST-001", "At least one test result should be present", "warning", "cross-field"),
            ValidationRule("WPQ-CERT-001", "Certification fields should be complete", "warning", "cross-field"),
        ]

    def get_field_mapping(self) -> List[FieldMapping]:
        return [
            # Identity
            FieldMapping("wpq_number", "wpq_number", "weld_wpq", "text", True),
            FieldMapping("revision", "revision", "weld_wpq", "text"),
            FieldMapping("welder_name", "welder_name", "weld_wpq", "text", True),
            FieldMapping("welder_stamp", "welder_stamp", "weld_wpq", "text"),
            FieldMapping("wps_number", "wps_number", "weld_wpq", "text"),
            FieldMapping("process_type", "process_type", "weld_wpq", "text", True),
            FieldMapping("process_variation", "process_variation", "weld_wpq", "text"),
            FieldMapping("test_date", "test_date", "weld_wpq", "date", True),
            # Coupon / test description
            FieldMapping("coupon_base_metal", "coupon_base_metal", "weld_wpq", "text"),
            FieldMapping("coupon_thickness", "coupon_thickness", "weld_wpq", "real"),
            FieldMapping("coupon_diameter", "coupon_diameter", "weld_wpq", "text"),
            # Actual values
            FieldMapping("p_number_actual", "p_number_actual", "weld_wpq", "text"),
            FieldMapping("backing_actual", "backing_actual", "weld_wpq", "text"),
            FieldMapping("filler_sfa_spec", "filler_sfa_spec", "weld_wpq", "text"),
            FieldMapping("filler_aws_class", "filler_aws_class", "weld_wpq", "text"),
            FieldMapping("f_number_actual", "f_number_actual", "weld_wpq", "text"),
            FieldMapping("consumable_insert", "consumable_insert", "weld_wpq", "text"),
            FieldMapping("filler_type", "filler_type", "weld_wpq", "text"),
            FieldMapping("deposit_thickness_actual", "deposit_thickness_actual", "weld_wpq", "real"),
            FieldMapping("test_position", "test_position", "weld_wpq", "text"),
            FieldMapping("backing_gas", "backing_gas", "weld_wpq", "text"),
            FieldMapping("transfer_mode", "transfer_mode", "weld_wpq", "text"),
            FieldMapping("current_type", "current_type", "weld_wpq", "text"),
            # Range qualified
            FieldMapping("p_number_base", "p_number_base", "weld_wpq", "integer"),
            FieldMapping("p_number_filler", "p_number_filler", "weld_wpq", "integer"),
            FieldMapping("p_number_qualified", "p_number_qualified", "weld_wpq", "text"),
            FieldMapping("f_number", "f_number", "weld_wpq", "integer"),
            FieldMapping("f_number_qualified", "f_number_qualified", "weld_wpq", "text"),
            FieldMapping("thickness_qualified_min", "thickness_qualified_min", "weld_wpq", "real"),
            FieldMapping("thickness_qualified_max", "thickness_qualified_max", "weld_wpq", "real"),
            FieldMapping("diameter_qualified_min", "diameter_qualified_min", "weld_wpq", "real"),
            FieldMapping("diameter_qualified_max", "diameter_qualified_max", "weld_wpq", "real"),
            FieldMapping("deposit_thickness_max", "deposit_thickness_max", "weld_wpq", "real"),
            FieldMapping("groove_positions_qualified", "groove_positions_qualified", "weld_wpq", "text"),
            FieldMapping("fillet_positions_qualified", "fillet_positions_qualified", "weld_wpq", "text"),
            FieldMapping("progression", "progression", "weld_wpq", "text"),
            FieldMapping("backing_type", "backing_type", "weld_wpq", "text"),
            FieldMapping("filler_type_qualified", "filler_type_qualified", "weld_wpq", "text"),
            # Status / dates
            FieldMapping("initial_expiration_date", "initial_expiration_date", "weld_wpq", "date"),
            FieldMapping("current_expiration_date", "current_expiration_date", "weld_wpq", "date"),
            FieldMapping("status", "status", "weld_wpq", "text"),
            # Personnel / certification
            FieldMapping("witness_name", "witness_name", "weld_wpq", "text"),
            FieldMapping("witness_company", "witness_company", "weld_wpq", "text"),
            FieldMapping("evaluator_name", "evaluator_name", "weld_wpq", "text"),
            FieldMapping("evaluator_company", "evaluator_company", "weld_wpq", "text"),
            FieldMapping("lab_name", "lab_name", "weld_wpq", "text"),
            FieldMapping("lab_test_number", "lab_test_number", "weld_wpq", "text"),
            FieldMapping("organization", "organization", "weld_wpq", "text"),
            FieldMapping("certified_by", "certified_by", "weld_wpq", "text"),
            FieldMapping("certified_date", "certified_date", "weld_wpq", "date"),
            # Tests
            FieldMapping("test_type", "test_type", "weld_wpq_tests", "text", True),
            FieldMapping("results", "results", "weld_wpq_tests", "text"),
            FieldMapping("result", "result", "weld_wpq_tests", "text"),
        ]

    def get_template_mapping(self) -> Dict[str, str]:
        return {
            # Header
            "weld_wpq.welder_name": "C4",
            "weld_wpq.welder_stamp": "M4",
            "weld_wpq.wps_number": "E6",
            "weld_wpq.coupon_base_metal": "E7",
            "weld_wpq.coupon_thickness": "N7",
            "weld_wpq.process_type": "D8",
            "weld_wpq.process_variation": "M8",
            # Actual Values column
            "weld_wpq.backing_actual": "J12",
            "weld_wpq.coupon_diameter": "J13",
            "weld_wpq.p_number_actual": "J14",
            "weld_wpq.coupon_thickness_row": "J15",
            "weld_wpq.filler_sfa_spec": "J16",
            "weld_wpq.filler_aws_class": "J17",
            "weld_wpq.f_number_actual": "J18",
            "weld_wpq.consumable_insert": "J19",
            "weld_wpq.filler_type": "J20",
            "weld_wpq.deposit_thickness_actual": "J21",
            "weld_wpq.test_position": "J22",
            "weld_wpq.progression": "J23",
            "weld_wpq.backing_gas": "J24",
            "weld_wpq.transfer_mode": "J25",
            "weld_wpq.current_type": "J26",
            # Range Qualified column
            "weld_wpq.backing_type": "O12",
            "weld_wpq.diameter_qualified_min": "O13",
            "weld_wpq.p_number_qualified": "O14",
            "weld_wpq.thickness_qualified_min": "O15",
            "weld_wpq.f_number_qualified": "O18",
            "weld_wpq.deposit_thickness_max": "O21",
            "weld_wpq.groove_positions_qualified": "O22",
            # Personnel
            "weld_wpq.evaluator_name": "F41",
            "weld_wpq.evaluator_company": "N41",
            "weld_wpq.lab_name": "F42",
            "weld_wpq.lab_test_number": "O42",
            "weld_wpq.witness_name": "F43",
            "weld_wpq.witness_company": "N43",
            # Certification
            "weld_wpq.organization": "K49",
            "weld_wpq.test_date": "B51",
            "weld_wpq.certified_by": "K51",
        }
