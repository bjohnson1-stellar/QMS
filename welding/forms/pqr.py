"""PQR (Procedure Qualification Record) — ASME QW-483 form definition."""

import re
from typing import Any, Dict, List, Optional

from qms.welding.forms.base import BaseFormDefinition, FieldMapping, ValidationRule


class PQRFormDefinition(BaseFormDefinition):

    @property
    def form_type(self) -> str:
        return "pqr"

    @property
    def asme_form(self) -> str:
        return "QW-483"

    @property
    def parent_table(self) -> str:
        return "weld_pqr"

    @property
    def child_tables(self) -> List[str]:
        return [
            "weld_pqr_joints",
            "weld_pqr_base_metals",
            "weld_pqr_filler_metals",
            "weld_pqr_positions",
            "weld_pqr_preheat",
            "weld_pqr_pwht",
            "weld_pqr_gas",
            "weld_pqr_electrical",
            "weld_pqr_tensile_tests",
            "weld_pqr_bend_tests",
            "weld_pqr_toughness_tests",
            "weld_pqr_other_tests",
            "weld_pqr_personnel",
        ]

    @property
    def identifier_column(self) -> str:
        return "pqr_number"

    def parse_identifier_from_filename(self, filename: str) -> Optional[str]:
        name = re.sub(r"\.(pdf|xlsx?)$", "", filename, flags=re.I)
        name = re.sub(r"^PQR[-_]?", "", name, flags=re.I).strip()
        name = re.sub(r"[-_]?[Rr]ev[-_]?\w+$", "", name)
        return name if name else None

    def get_extraction_prompt(self, raw_text: str, valid_values: Dict[str, List[str]]) -> str:
        processes = ", ".join(valid_values.get("processes", []))
        p_numbers = ", ".join(valid_values.get("p_numbers", []))

        return f"""Extract all data from this ASME QW-483 Procedure Qualification Record (PQR) form.

Return a JSON object with these sections:

{{
  "parent": {{
    "pqr_number": "string — PQR identifier",
    "revision": "string — revision number/letter",
    "wps_number": "string — supporting WPS number",
    "coupon_id": "string or null",
    "test_date": "YYYY-MM-DD",
    "witness_name": "string or null",
    "witness_company": "string or null",
    "witness_stamp": "string or null",
    "lab_name": "string or null",
    "lab_report_number": "string or null",
    "status": "active",
    "prepared_by": "string or null",
    "prepared_date": "YYYY-MM-DD or null"
  }},
  "joints": [
    {{
      "joint_type": "butt, tee, etc.",
      "groove_type": "V, bevel, etc.",
      "groove_angle": number or null,
      "root_opening": number or null,
      "root_face": number or null,
      "backing_type": "string or null",
      "backing_material": "string or null"
    }}
  ],
  "base_metals": [
    {{
      "metal_sequence": 1,
      "p_number": integer from [{p_numbers}],
      "group_number": integer or null,
      "material_spec": "string",
      "material_grade": "string or null",
      "thickness": number in inches,
      "diameter": number in inches or null,
      "heat_number": "string or null"
    }}
  ],
  "filler_metals": [
    {{
      "process_sequence": 1,
      "f_number": integer,
      "a_number": integer or null,
      "sfa_spec": "string",
      "aws_class": "string",
      "filler_diameter": "string",
      "trade_name": "string or null",
      "heat_lot": "string or null"
    }}
  ],
  "positions": [
    {{
      "test_position": "e.g. 6G, 2G",
      "progression": "uphill, downhill, or null"
    }}
  ],
  "preheat": [
    {{
      "preheat_temp": number in F or null,
      "interpass_temp_max": number in F or null
    }}
  ],
  "pwht": [
    {{
      "pwht_performed": 0 or 1,
      "temperature": number in F or null,
      "time_at_temp": number in hours or null
    }}
  ],
  "gas": [
    {{
      "process_sequence": 1,
      "shielding_gas": "string",
      "shielding_flow_rate": number in CFH or null,
      "backing_gas": "string or null",
      "backing_flow_rate": number or null
    }}
  ],
  "electrical": [
    {{
      "process_sequence": 1,
      "pass_number": "string — e.g. 1, 2, root, fill",
      "process_type": "one of: {processes}",
      "current_type": "DCEP, DCEN, AC",
      "amperage": number,
      "voltage": number,
      "travel_speed": number or null,
      "wire_feed_speed": number or null,
      "heat_input": number or null,
      "filler_diameter": "string",
      "transfer_mode": "string or null"
    }}
  ],
  "tensile_tests": [
    {{
      "specimen_number": "string",
      "width": number or null,
      "thickness": number or null,
      "area": number or null,
      "ultimate_load": number or null,
      "ultimate_tensile_strength": number,
      "failure_location": "string — weld, HAZ, base metal",
      "acceptance_criteria": "string or null",
      "result": "Acceptable or Rejected"
    }}
  ],
  "bend_tests": [
    {{
      "specimen_number": "string",
      "bend_type": "side, face, root, transverse",
      "mandrel_diameter": number or null,
      "bend_angle": number or null,
      "discontinuities": "string or null",
      "max_discontinuity_size": number or null,
      "result": "Acceptable or Rejected"
    }}
  ],
  "toughness_tests": [
    {{
      "specimen_number": "string",
      "test_type": "Charpy V-notch, etc.",
      "location": "weld, HAZ",
      "test_temperature": number in F,
      "energy_absorbed": number in ft-lbs,
      "lateral_expansion": number or null,
      "shear_percent": number or null,
      "result": "Acceptable or Rejected"
    }}
  ],
  "other_tests": [
    {{
      "test_type": "macro, hardness, fillet weld, etc.",
      "description": "string",
      "acceptance_criteria": "string",
      "result": "Acceptable or Rejected"
    }}
  ],
  "personnel": [
    {{
      "role": "welder, witness, examiner",
      "name": "string",
      "stamp_or_id": "string or null",
      "company": "string or null",
      "date": "YYYY-MM-DD or null"
    }}
  ]
}}

RULES:
- Use null for missing values
- All temperatures in Fahrenheit, dimensions in inches
- Dates in YYYY-MM-DD format
- PQR records the ACTUAL values used (not ranges like WPS)
- Capture ALL test results including pass/fail

PDF TEXT:
{raw_text}"""

    def get_validation_rules(self) -> List[ValidationRule]:
        return [
            ValidationRule("PQR-REQ-001", "PQR number is required", "error", "required"),
            ValidationRule("PQR-REQ-002", "Test date is required", "error", "required"),
            ValidationRule("PQR-REQ-003", "At least one base metal entry is required", "error", "required"),
            ValidationRule("PQR-PROC-001", "Process type must be valid", "error", "lookup"),
            ValidationRule("PQR-BASE-001", "P-number must exist in lookup table", "error", "lookup"),
            ValidationRule("PQR-FILLER-001", "F-number must exist in lookup table", "error", "lookup"),
            ValidationRule("PQR-TENSILE-001", "Tensile UTS must be >= material minimum", "warning", "cross-field"),
            ValidationRule("PQR-BEND-001", "Bend test results must be Acceptable or Rejected", "error", "cross-field"),
            ValidationRule("PQR-WITNESS-001", "PQR should have at least one witness", "warning", "cross-field"),
        ]

    def get_field_mapping(self) -> List[FieldMapping]:
        return [
            FieldMapping("pqr_number", "pqr_number", "weld_pqr", "text", True),
            FieldMapping("revision", "revision", "weld_pqr", "text"),
            FieldMapping("wps_number", "wps_number", "weld_pqr", "text"),
            FieldMapping("test_date", "test_date", "weld_pqr", "date"),
            FieldMapping("witness_name", "witness_name", "weld_pqr", "text"),
            FieldMapping("lab_name", "lab_name", "weld_pqr", "text"),
            FieldMapping("status", "status", "weld_pqr", "text"),
            FieldMapping("p_number", "p_number", "weld_pqr_base_metals", "integer"),
            FieldMapping("material_spec", "material_spec", "weld_pqr_base_metals", "text"),
            FieldMapping("thickness", "thickness", "weld_pqr_base_metals", "real"),
            FieldMapping("f_number", "f_number", "weld_pqr_filler_metals", "integer"),
            FieldMapping("sfa_spec", "sfa_spec", "weld_pqr_filler_metals", "text"),
            FieldMapping("aws_class", "aws_class", "weld_pqr_filler_metals", "text"),
            FieldMapping("test_position", "test_position", "weld_pqr_positions", "text"),
            FieldMapping("ultimate_tensile_strength", "ultimate_tensile_strength", "weld_pqr_tensile_tests", "real"),
            FieldMapping("bend_type", "bend_type", "weld_pqr_bend_tests", "text"),
            FieldMapping("result", "result", "weld_pqr_bend_tests", "text"),
        ]

    def get_template_mapping(self) -> Dict[str, str]:
        return {
            "weld_pqr.pqr_number": "B2",
            "weld_pqr.wps_number": "F2",
            "weld_pqr.test_date": "H2",
            "weld_pqr_base_metals.p_number": "B8",
            "weld_pqr_base_metals.material_spec": "D8",
            "weld_pqr_base_metals.thickness": "F8",
            "weld_pqr_filler_metals.sfa_spec": "B11",
            "weld_pqr_filler_metals.aws_class": "D11",
            "weld_pqr_filler_metals.f_number": "F11",
            "weld_pqr_positions.test_position": "B14",
            "weld_pqr_tensile_tests.ultimate_tensile_strength": "B20",
            "weld_pqr_tensile_tests.result": "F20",
            "weld_pqr_bend_tests.bend_type": "B22",
            "weld_pqr_bend_tests.result": "F22",
        }
