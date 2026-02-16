"""WPS (Welding Procedure Specification) — ASME QW-482 form definition."""

import re
from typing import Any, Dict, List, Optional

from qms.welding.forms.base import BaseFormDefinition, FieldMapping, ValidationRule


class WPSFormDefinition(BaseFormDefinition):

    @property
    def form_type(self) -> str:
        return "wps"

    @property
    def asme_form(self) -> str:
        return "QW-482"

    @property
    def parent_table(self) -> str:
        return "weld_wps"

    @property
    def child_tables(self) -> List[str]:
        return [
            "weld_wps_processes",
            "weld_wps_joints",
            "weld_wps_base_metals",
            "weld_wps_filler_metals",
            "weld_wps_positions",
            "weld_wps_preheat",
            "weld_wps_pwht",
            "weld_wps_gas",
            "weld_wps_electrical_params",
            "weld_wps_technique",
            "weld_wps_pqr_links",
        ]

    @property
    def identifier_column(self) -> str:
        return "wps_number"

    def parse_identifier_from_filename(self, filename: str) -> Optional[str]:
        # Patterns: CS-01.pdf, SS-02-P8-GTAW.pdf, WPS-CS-01.pdf
        name = re.sub(r"\.(pdf|xlsx?)$", "", filename, flags=re.I)
        name = re.sub(r"^WPS[-_]?", "", name, flags=re.I).strip()
        # Clean trailing revision markers
        name = re.sub(r"[-_]?[Rr]ev[-_]?\w+$", "", name)
        return name if name else None

    def get_extraction_prompt(self, raw_text: str, valid_values: Dict[str, List[str]]) -> str:
        processes = ", ".join(valid_values.get("processes", []))
        positions = ", ".join(valid_values.get("positions", []))
        p_numbers = ", ".join(valid_values.get("p_numbers", []))

        return f"""Extract all data from this ASME QW-482 Welding Procedure Specification (WPS) form.

Return a JSON object with these sections:

{{
  "parent": {{
    "wps_number": "string — WPS identifier",
    "revision": "string — revision number/letter",
    "revision_date": "YYYY-MM-DD or null",
    "is_swps": 0 or 1,
    "swps_document_number": "string or null — if SWPS/PWPS",
    "title": "string or null",
    "description": "string or null",
    "applicable_codes": "string — ASME IX, AWS D1.1, etc.",
    "scope_of_work": "string or null",
    "status": "active or draft",
    "effective_date": "YYYY-MM-DD or null",
    "prepared_by": "string or null",
    "prepared_date": "YYYY-MM-DD or null",
    "reviewed_by": "string or null",
    "reviewed_date": "YYYY-MM-DD or null",
    "approved_by": "string or null",
    "approved_date": "YYYY-MM-DD or null"
  }},
  "processes": [
    {{
      "process_sequence": 1,
      "process_type": "one of: {processes}",
      "process_variation": "string or null",
      "layer_deposit": "string — e.g. 'root', 'fill', 'cap', 'all'"
    }}
  ],
  "joints": [
    {{
      "joint_type": "butt, corner, tee, lap, edge, branch, socket",
      "groove_type": "V, double_V, U, bevel, square, etc.",
      "groove_angle_min": number or null,
      "groove_angle_max": number or null,
      "root_opening_min": number or null,
      "root_opening_max": number or null,
      "root_face_min": number or null,
      "root_face_max": number or null,
      "backing_type": "string or null",
      "backing_material": "string or null",
      "retainers": "string or null"
    }}
  ],
  "base_metals": [
    {{
      "metal_sequence": 1,
      "p_number": integer from [{p_numbers}],
      "group_number": integer or null,
      "material_spec": "e.g. A106, A312",
      "material_grade": "e.g. Gr B, TP304",
      "material_type": "Carbon Steel, Stainless Steel, etc.",
      "thickness_min": number in inches or null,
      "thickness_max": number in inches or null,
      "diameter_min": number in inches or null,
      "diameter_max": number in inches or null,
      "s_number": integer or null
    }}
  ],
  "filler_metals": [
    {{
      "process_sequence": 1,
      "f_number": integer,
      "a_number": integer or null,
      "sfa_spec": "e.g. SFA-5.1, SFA-5.18",
      "aws_class": "e.g. E7018, ER70S-6",
      "filler_diameter": "string — e.g. 3/32, 1/8",
      "filler_form": "electrode, bare_wire, flux_cored",
      "flux_trade_name": "string or null",
      "flux_type": "string or null",
      "consumable_insert": "string or null"
    }}
  ],
  "positions": [
    {{
      "groove_positions": "comma-separated from [{positions}]",
      "fillet_positions": "comma-separated or null",
      "progression": "uphill, downhill, or null"
    }}
  ],
  "preheat": [
    {{
      "preheat_temp_min": number in F or null,
      "preheat_temp_max": number in F or null,
      "interpass_temp_max": number in F or null,
      "preheat_maintenance": "string or null",
      "preheat_method": "string or null"
    }}
  ],
  "pwht": [
    {{
      "pwht_required": 0 or 1,
      "temperature_min": number in F or null,
      "temperature_max": number in F or null,
      "time_min": number in hours or null,
      "time_max": number in hours or null,
      "heating_rate_max": number or null,
      "cooling_rate_max": number or null,
      "pwht_method": "string or null",
      "pwht_exemption": "string or null"
    }}
  ],
  "gas": [
    {{
      "process_sequence": 1,
      "shielding_gas": "e.g. Argon, Ar/CO2 75/25",
      "shielding_flow_rate_min": number in CFH or null,
      "shielding_flow_rate_max": number in CFH or null,
      "backing_gas": "string or null",
      "backing_flow_rate_min": number or null,
      "backing_flow_rate_max": number or null,
      "trailing_gas": "string or null",
      "trailing_flow_rate": number or null
    }}
  ],
  "electrical": [
    {{
      "process_sequence": 1,
      "pass_type": "root, fill, cap, all",
      "current_type": "DCEP, DCEN, AC",
      "amperage_min": number,
      "amperage_max": number,
      "voltage_min": number,
      "voltage_max": number,
      "travel_speed_min": number or null,
      "travel_speed_max": number or null,
      "wire_feed_speed_min": number or null,
      "wire_feed_speed_max": number or null,
      "heat_input_min": number or null,
      "heat_input_max": number or null,
      "transfer_mode": "string or null"
    }}
  ],
  "technique": [
    {{
      "bead_type": "stringer or weave",
      "single_or_multi_pass": "single or multi",
      "single_or_multi_layer": "single or multi",
      "interpass_cleaning": "string or null",
      "root_cleaning": "string or null",
      "peening": "string or null",
      "ctwd_min": number or null,
      "ctwd_max": number or null
    }}
  ],
  "pqr_links": [
    {{
      "pqr_number": "PQR identifier",
      "qualification_scope": "string or null"
    }}
  ]
}}

RULES:
- Use null for missing/not-applicable values, never empty strings
- All temperatures in Fahrenheit, dimensions in inches
- Dates in YYYY-MM-DD format
- For dual-process WPS (e.g., GTAW root + SMAW fill), create separate entries in processes, filler_metals, gas, and electrical arrays with matching process_sequence
- If the form is an SWPS/PWPS, set is_swps=1 and capture the AWS document number

PDF TEXT:
{raw_text}"""

    def get_validation_rules(self) -> List[ValidationRule]:
        return [
            ValidationRule("WPS-REQ-001", "WPS number is required", "error", "required"),
            ValidationRule("WPS-REQ-002", "At least one process is required", "error", "required"),
            ValidationRule("WPS-REQ-003", "At least one base metal entry is required", "error", "required"),
            ValidationRule("WPS-REQ-004", "At least one filler metal entry is required", "error", "required"),
            ValidationRule("WPS-PROC-001", "Process type must be valid ASME process", "error", "lookup"),
            ValidationRule("WPS-BASE-001", "P-number must exist in lookup table", "error", "lookup"),
            ValidationRule("WPS-FILLER-001", "F-number must exist in lookup table", "error", "lookup"),
            ValidationRule("WPS-FILLER-002", "SFA spec must exist in lookup table", "warning", "lookup"),
            ValidationRule("WPS-POS-001", "Position codes must be valid", "error", "lookup"),
            ValidationRule("WPS-RANGE-001", "thickness_min <= thickness_max", "error", "range"),
            ValidationRule("WPS-RANGE-002", "diameter_min <= diameter_max", "error", "range"),
            ValidationRule("WPS-RANGE-003", "amperage_min <= amperage_max", "error", "range"),
            ValidationRule("WPS-RANGE-004", "voltage_min <= voltage_max", "error", "range"),
            ValidationRule("WPS-PREHEAT-001", "interpass_temp_max >= preheat_temp_min", "error", "cross-field"),
            ValidationRule("WPS-PWHT-001", "If pwht_required=0, temp/time must be null", "warning", "cross-field"),
            ValidationRule("WPS-GAS-001", "GTAW requires shielding gas", "error", "cross-field"),
            ValidationRule("WPS-GAS-002", "SMAW should not have shielding gas", "warning", "cross-field"),
            ValidationRule("WPS-ELEC-001", "Current type must be compatible with process", "warning", "cross-field"),
        ]

    def get_field_mapping(self) -> List[FieldMapping]:
        mappings = [
            FieldMapping("wps_number", "wps_number", "weld_wps", "text", True),
            FieldMapping("revision", "revision", "weld_wps", "text"),
            FieldMapping("revision_date", "revision_date", "weld_wps", "date"),
            FieldMapping("is_swps", "is_swps", "weld_wps", "integer"),
            FieldMapping("title", "title", "weld_wps", "text"),
            FieldMapping("applicable_codes", "applicable_codes", "weld_wps", "text"),
            FieldMapping("status", "status", "weld_wps", "text"),
            FieldMapping("prepared_by", "prepared_by", "weld_wps", "text"),
            FieldMapping("approved_by", "approved_by", "weld_wps", "text"),
            FieldMapping("process_type", "process_type", "weld_wps_processes", "text", True),
            FieldMapping("process_sequence", "process_sequence", "weld_wps_processes", "integer"),
            FieldMapping("p_number", "p_number", "weld_wps_base_metals", "integer"),
            FieldMapping("material_spec", "material_spec", "weld_wps_base_metals", "text"),
            FieldMapping("thickness_min", "thickness_min", "weld_wps_base_metals", "real"),
            FieldMapping("thickness_max", "thickness_max", "weld_wps_base_metals", "real"),
            FieldMapping("f_number", "f_number", "weld_wps_filler_metals", "integer"),
            FieldMapping("a_number", "a_number", "weld_wps_filler_metals", "integer"),
            FieldMapping("sfa_spec", "sfa_spec", "weld_wps_filler_metals", "text"),
            FieldMapping("aws_class", "aws_class", "weld_wps_filler_metals", "text"),
            FieldMapping("groove_positions", "groove_positions", "weld_wps_positions", "text"),
            FieldMapping("fillet_positions", "fillet_positions", "weld_wps_positions", "text"),
            FieldMapping("preheat_temp_min", "preheat_temp_min", "weld_wps_preheat", "real"),
            FieldMapping("interpass_temp_max", "interpass_temp_max", "weld_wps_preheat", "real"),
            FieldMapping("shielding_gas", "shielding_gas", "weld_wps_gas", "text"),
            FieldMapping("amperage_min", "amperage_min", "weld_wps_electrical_params", "real"),
            FieldMapping("amperage_max", "amperage_max", "weld_wps_electrical_params", "real"),
            FieldMapping("voltage_min", "voltage_min", "weld_wps_electrical_params", "real"),
            FieldMapping("voltage_max", "voltage_max", "weld_wps_electrical_params", "real"),
            FieldMapping("current_type", "current_type", "weld_wps_electrical_params", "text"),
        ]
        return mappings

    def get_template_mapping(self) -> Dict[str, str]:
        return {
            "weld_wps.wps_number": "B2",
            "weld_wps.revision": "F2",
            "weld_wps.revision_date": "H2",
            "weld_wps.applicable_codes": "B4",
            "weld_wps.scope_of_work": "B5",
            "weld_wps_processes.process_type": "B7",
            "weld_wps_joints.joint_type": "B9",
            "weld_wps_joints.groove_type": "D9",
            "weld_wps_base_metals.p_number": "B12",
            "weld_wps_base_metals.material_spec": "D12",
            "weld_wps_base_metals.thickness_min": "F12",
            "weld_wps_base_metals.thickness_max": "G12",
            "weld_wps_filler_metals.sfa_spec": "B15",
            "weld_wps_filler_metals.aws_class": "D15",
            "weld_wps_filler_metals.f_number": "F15",
            "weld_wps_filler_metals.a_number": "G15",
            "weld_wps_positions.groove_positions": "B18",
            "weld_wps_positions.fillet_positions": "D18",
            "weld_wps_preheat.preheat_temp_min": "B20",
            "weld_wps_preheat.interpass_temp_max": "D20",
            "weld_wps_gas.shielding_gas": "B22",
            "weld_wps_gas.shielding_flow_rate_min": "D22",
            "weld_wps_electrical_params.current_type": "B24",
            "weld_wps_electrical_params.amperage_min": "D24",
            "weld_wps_electrical_params.amperage_max": "E24",
            "weld_wps_electrical_params.voltage_min": "F24",
            "weld_wps_electrical_params.voltage_max": "G24",
            "weld_wps_technique.bead_type": "B26",
            "weld_wps_pwht.pwht_required": "B28",
            "weld_wps_pwht.temperature_min": "D28",
            "weld_wps.prepared_by": "B30",
            "weld_wps.approved_by": "D30",
        }
