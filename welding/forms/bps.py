"""BPS (Brazing Procedure Specification) — ASME QB-482 form definition."""

import re
from typing import Any, Dict, List, Optional

from qms.welding.forms.base import BaseFormDefinition, FieldMapping, ValidationRule


class BPSFormDefinition(BaseFormDefinition):

    @property
    def form_type(self) -> str:
        return "bps"

    @property
    def asme_form(self) -> str:
        return "QB-482"

    @property
    def parent_table(self) -> str:
        return "weld_bps"

    @property
    def child_tables(self) -> List[str]:
        return [
            "weld_bps_joints",
            "weld_bps_base_metals",
            "weld_bps_filler_metals",
            "weld_bps_flux_atmosphere",
            "weld_bps_positions",
            "weld_bps_pwht",
            "weld_bps_technique",
        ]

    @property
    def identifier_column(self) -> str:
        return "bps_number"

    def parse_identifier_from_filename(self, filename: str) -> Optional[str]:
        name = re.sub(r"\.(pdf|xlsx?)$", "", filename, flags=re.I)
        name = re.sub(r"^BPS[-_]?", "", name, flags=re.I).strip()
        name = re.sub(r"[-_]?[Rr]ev[-_]?\w+$", "", name)
        return name if name else None

    def get_extraction_prompt(self, raw_text: str, valid_values: Dict[str, List[str]]) -> str:
        return f"""Extract all data from this ASME QB-482 Brazing Procedure Specification (BPS) form.

Return a JSON object:

{{
  "parent": {{
    "bps_number": "string — BPS identifier",
    "revision": "string",
    "revision_date": "YYYY-MM-DD or null",
    "title": "string or null",
    "description": "string or null",
    "brazing_process": "TB, FB, IB, RB, DB, IRB",
    "status": "active or draft",
    "effective_date": "YYYY-MM-DD or null",
    "prepared_by": "string or null",
    "approved_by": "string or null",
    "approved_date": "YYYY-MM-DD or null"
  }},
  "joints": [
    {{
      "joint_type": "butt, lap, scarf, etc.",
      "joint_clearance_min": number in inches or null,
      "joint_clearance_max": number in inches or null,
      "joint_overlap": number or null,
      "joint_details": "string or null"
    }}
  ],
  "base_metals": [
    {{
      "metal_sequence": 1,
      "p_number": integer or null,
      "material_spec": "string",
      "material_form": "pipe, tube, plate, fitting",
      "thickness_range": "string — e.g. 0.035 to 0.500"
    }}
  ],
  "filler_metals": [
    {{
      "f_number": integer or null,
      "sfa_spec": "SFA-5.8 (brazing)",
      "aws_class": "string — e.g. BAg-1, BCuP-5",
      "filler_form": "wire, preform, paste, ring",
      "filler_application": "face feed, preplace, etc."
    }}
  ],
  "flux_atmosphere": [
    {{
      "flux_type": "string or null",
      "flux_application": "string or null",
      "atmosphere_type": "string — vacuum, inert, reducing, none",
      "atmosphere_gas": "string or null",
      "dew_point_max": number in F or null
    }}
  ],
  "positions": [
    {{
      "positions_qualified": "string",
      "flow_direction": "uphill, downhill, horizontal, or null"
    }}
  ],
  "pwht": [
    {{
      "pbht_required": 0 or 1,
      "temperature": number in F or null,
      "time_at_temp": number in minutes or null
    }}
  ],
  "technique": [
    {{
      "brazing_temp_min": number in F,
      "brazing_temp_max": number in F,
      "time_at_temp_min": number in minutes or null,
      "time_at_temp_max": number in minutes or null,
      "heating_method": "torch, furnace, induction, etc.",
      "cooling_method": "air, furnace, quench, or null",
      "technique_details": "string or null"
    }}
  ]
}}

RULES:
- Use null for missing values
- Brazing processes differ from welding — lower temperatures, filler flows by capillary action
- SFA-5.8 covers brazing filler metals (BAg, BCuP, BNi classes)
- Joint clearance is critical for brazing (typically 0.001-0.005 inches)

PDF TEXT:
{raw_text}"""

    def get_validation_rules(self) -> List[ValidationRule]:
        return [
            ValidationRule("BPS-REQ-001", "BPS number is required", "error", "required"),
            ValidationRule("BPS-REQ-002", "Brazing process is required", "error", "required"),
            ValidationRule("BPS-REQ-003", "At least one base metal entry is required", "error", "required"),
            ValidationRule("BPS-PROC-001", "Brazing process must be valid (TB, FB, IB, RB, DB, IRB)", "error", "lookup"),
            ValidationRule("BPS-BASE-001", "P-number must exist in lookup table", "warning", "lookup"),
            ValidationRule("BPS-TEMP-001", "Brazing temp_min <= temp_max", "error", "range"),
            ValidationRule("BPS-CLEAR-001", "Joint clearance_min <= clearance_max", "error", "range"),
        ]

    def get_field_mapping(self) -> List[FieldMapping]:
        return [
            FieldMapping("bps_number", "bps_number", "weld_bps", "text", True),
            FieldMapping("revision", "revision", "weld_bps", "text"),
            FieldMapping("brazing_process", "brazing_process", "weld_bps", "text"),
            FieldMapping("status", "status", "weld_bps", "text"),
            FieldMapping("prepared_by", "prepared_by", "weld_bps", "text"),
            FieldMapping("approved_by", "approved_by", "weld_bps", "text"),
            FieldMapping("p_number", "p_number", "weld_bps_base_metals", "integer"),
            FieldMapping("material_spec", "material_spec", "weld_bps_base_metals", "text"),
            FieldMapping("f_number", "f_number", "weld_bps_filler_metals", "integer"),
            FieldMapping("sfa_spec", "sfa_spec", "weld_bps_filler_metals", "text"),
            FieldMapping("aws_class", "aws_class", "weld_bps_filler_metals", "text"),
            FieldMapping("brazing_temp_min", "brazing_temp_min", "weld_bps_technique", "real"),
            FieldMapping("brazing_temp_max", "brazing_temp_max", "weld_bps_technique", "real"),
        ]

    def get_template_mapping(self) -> Dict[str, str]:
        return {
            "weld_bps.bps_number": "B2",
            "weld_bps.revision": "F2",
            "weld_bps.brazing_process": "B4",
            "weld_bps_base_metals.p_number": "B8",
            "weld_bps_base_metals.material_spec": "D8",
            "weld_bps_filler_metals.sfa_spec": "B11",
            "weld_bps_filler_metals.aws_class": "D11",
            "weld_bps_technique.brazing_temp_min": "B14",
            "weld_bps_technique.brazing_temp_max": "D14",
            "weld_bps_technique.heating_method": "B16",
        }
