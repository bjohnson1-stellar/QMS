"""
Welding form validation framework.

Two layers:
1. Lookup validation — check categorical values against weld_valid_* tables
2. Cross-field rules — relational constraints per form type

Used by both the extraction pipeline (validate before inserting) and
the generation pipeline (validate before outputting).
"""

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from qms.core import get_logger

logger = get_logger("qms.welding.validation")


@dataclass
class ValidationIssue:
    """A single validation finding."""
    rule_code: str
    severity: str  # "error", "warning", "info"
    message: str
    field: Optional[str] = None
    table: Optional[str] = None
    value: Any = None


@dataclass
class ValidationResult:
    """Aggregate result of validation."""
    is_valid: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0

    def add_issue(self, issue: ValidationIssue):
        self.issues.append(issue)
        if issue.severity == "error":
            self.error_count += 1
            self.is_valid = False
        elif issue.severity == "warning":
            self.warning_count += 1

    def merge(self, other: "ValidationResult"):
        for issue in other.issues:
            self.add_issue(issue)


# ---------------------------------------------------------------------------
# Lookup validation
# ---------------------------------------------------------------------------

def _check_lookup(conn: sqlite3.Connection, table: str, column: str,
                  value: Any, rule_code: str, severity: str = "error",
                  field_name: str = "") -> Optional[ValidationIssue]:
    """Check if a value exists in a lookup table."""
    if value is None:
        return None

    row = conn.execute(
        f"SELECT 1 FROM {table} WHERE {column} = ?", (value,)
    ).fetchone()

    if not row:
        return ValidationIssue(
            rule_code=rule_code,
            severity=severity,
            message=f"Value '{value}' not found in {table}.{column}",
            field=field_name or column,
            table=table,
            value=value,
        )
    return None


def validate_lookups(conn: sqlite3.Connection, data: Dict[str, Any],
                     form_type: str) -> ValidationResult:
    """
    Validate categorical values against lookup tables.

    Args:
        conn: Database connection with lookup tables populated.
        data: Extracted data dict with 'parent' and child sections.
        form_type: 'wps', 'pqr', 'wpq', 'bps', 'bpq'.

    Returns:
        ValidationResult with any lookup failures.
    """
    result = ValidationResult()
    parent = data.get("parent", {})

    # Process type validation (all form types except bps/bpq)
    if form_type in ("wps", "pqr", "wpq"):
        # Check processes array or parent process_type
        processes = data.get("processes", [])
        if processes:
            for proc in processes:
                issue = _check_lookup(
                    conn, "weld_valid_processes", "code",
                    proc.get("process_type"), "PROC-001", "error", "process_type"
                )
                if issue:
                    result.add_issue(issue)
        elif parent.get("process_type"):
            issue = _check_lookup(
                conn, "weld_valid_processes", "code",
                parent["process_type"], "PROC-001", "error", "process_type"
            )
            if issue:
                result.add_issue(issue)

    # Brazing process validation
    if form_type in ("bps",) and parent.get("brazing_process"):
        issue = _check_lookup(
            conn, "weld_valid_processes", "code",
            parent["brazing_process"], "PROC-001", "error", "brazing_process"
        )
        if issue:
            result.add_issue(issue)

    # P-number validation
    base_metals = data.get("base_metals", [])
    for bm in base_metals:
        p_num = bm.get("p_number")
        if p_num is not None:
            issue = _check_lookup(
                conn, "weld_valid_p_numbers", "p_number",
                p_num, "BASE-001", "error", "p_number"
            )
            if issue:
                result.add_issue(issue)

    # F-number validation
    filler_metals = data.get("filler_metals", [])
    for fm in filler_metals:
        f_num = fm.get("f_number")
        if f_num is not None:
            issue = _check_lookup(
                conn, "weld_valid_f_numbers", "f_number",
                f_num, "FILLER-001", "error", "f_number"
            )
            if issue:
                result.add_issue(issue)

        sfa = fm.get("sfa_spec")
        if sfa:
            issue = _check_lookup(
                conn, "weld_valid_sfa_specs", "spec_number",
                sfa, "FILLER-002", "warning", "sfa_spec"
            )
            if issue:
                result.add_issue(issue)

    # Position validation
    positions = data.get("positions", [])
    for pos in positions:
        for field_name in ("groove_positions", "fillet_positions",
                           "test_position", "positions_qualified"):
            pos_val = pos.get(field_name)
            if pos_val:
                for code in [p.strip() for p in pos_val.split(",")]:
                    if code:
                        issue = _check_lookup(
                            conn, "weld_valid_positions", "code",
                            code, "POS-001", "error", field_name
                        )
                        if issue:
                            result.add_issue(issue)

    # WPQ parent-level position check
    if form_type == "wpq":
        for field_name in ("groove_positions_qualified", "fillet_positions_qualified"):
            pos_val = parent.get(field_name)
            if pos_val:
                for code in [p.strip() for p in pos_val.split(",")]:
                    if code:
                        issue = _check_lookup(
                            conn, "weld_valid_positions", "code",
                            code, "POS-001", "error", field_name
                        )
                        if issue:
                            result.add_issue(issue)

    return result


# ---------------------------------------------------------------------------
# Range validation
# ---------------------------------------------------------------------------

def _check_range(data: Dict, min_field: str, max_field: str,
                 rule_code: str, context: str = "") -> Optional[ValidationIssue]:
    """Check that min <= max for a pair of fields."""
    min_val = data.get(min_field)
    max_val = data.get(max_field)
    if min_val is not None and max_val is not None:
        try:
            if float(min_val) > float(max_val):
                return ValidationIssue(
                    rule_code=rule_code,
                    severity="error",
                    message=f"{context}{min_field} ({min_val}) > {max_field} ({max_val})",
                    field=min_field,
                    value=f"{min_val} > {max_val}",
                )
        except (ValueError, TypeError):
            pass
    return None


def validate_ranges(data: Dict[str, Any], form_type: str) -> ValidationResult:
    """Validate all min/max pairs in the extracted data."""
    result = ValidationResult()

    range_checks: List[Tuple[str, str, str, str]] = []

    # Base metals thickness/diameter
    for bm in data.get("base_metals", []):
        for issue in [
            _check_range(bm, "thickness_min", "thickness_max", "RANGE-001", "Base metal: "),
            _check_range(bm, "diameter_min", "diameter_max", "RANGE-002", "Base metal: "),
        ]:
            if issue:
                result.add_issue(issue)

    # Electrical params
    for ep in data.get("electrical", data.get("electrical_params", [])):
        for issue in [
            _check_range(ep, "amperage_min", "amperage_max", "RANGE-003", "Electrical: "),
            _check_range(ep, "voltage_min", "voltage_max", "RANGE-004", "Electrical: "),
            _check_range(ep, "travel_speed_min", "travel_speed_max", "RANGE-005", "Electrical: "),
            _check_range(ep, "wire_feed_speed_min", "wire_feed_speed_max", "RANGE-006", "Electrical: "),
            _check_range(ep, "heat_input_min", "heat_input_max", "RANGE-007", "Electrical: "),
        ]:
            if issue:
                result.add_issue(issue)

    # Gas flow rates
    for gas in data.get("gas", []):
        for issue in [
            _check_range(gas, "shielding_flow_rate_min", "shielding_flow_rate_max", "RANGE-008", "Gas: "),
            _check_range(gas, "backing_flow_rate_min", "backing_flow_rate_max", "RANGE-009", "Gas: "),
        ]:
            if issue:
                result.add_issue(issue)

    # Preheat
    for ph in data.get("preheat", []):
        issue = _check_range(ph, "preheat_temp_min", "preheat_temp_max", "RANGE-010", "Preheat: ")
        if issue:
            result.add_issue(issue)

    # PWHT
    for pwht in data.get("pwht", []):
        for issue in [
            _check_range(pwht, "temperature_min", "temperature_max", "RANGE-011", "PWHT: "),
            _check_range(pwht, "time_min", "time_max", "RANGE-012", "PWHT: "),
        ]:
            if issue:
                result.add_issue(issue)

    # BPS technique
    for tech in data.get("technique", []):
        for issue in [
            _check_range(tech, "brazing_temp_min", "brazing_temp_max", "RANGE-013", "Brazing: "),
            _check_range(tech, "time_at_temp_min", "time_at_temp_max", "RANGE-014", "Brazing: "),
        ]:
            if issue:
                result.add_issue(issue)

    # BPS joints
    for jt in data.get("joints", []):
        issue = _check_range(jt, "joint_clearance_min", "joint_clearance_max", "RANGE-015", "Joint: ")
        if issue:
            result.add_issue(issue)

    # WPQ thickness
    parent = data.get("parent", {})
    issue = _check_range(parent, "thickness_qualified_min", "thickness_qualified_max",
                         "RANGE-016", "WPQ: ")
    if issue:
        result.add_issue(issue)

    return result


# ---------------------------------------------------------------------------
# Cross-field rules
# ---------------------------------------------------------------------------

def validate_cross_field(data: Dict[str, Any], form_type: str,
                         conn: Optional[sqlite3.Connection] = None) -> ValidationResult:
    """
    Validate cross-field consistency rules specific to each form type.
    """
    result = ValidationResult()
    parent = data.get("parent", {})

    if form_type == "wps":
        _validate_wps_cross_field(data, result)
    elif form_type == "pqr":
        _validate_pqr_cross_field(data, result)
    elif form_type == "wpq":
        _validate_wpq_cross_field(data, result, conn)

    return result


def _validate_wps_cross_field(data: Dict, result: ValidationResult):
    """WPS-specific cross-field rules."""
    # PREHEAT-001: interpass_temp_max >= preheat_temp_min
    for ph in data.get("preheat", []):
        interpass = ph.get("interpass_temp_max")
        preheat_min = ph.get("preheat_temp_min")
        if interpass is not None and preheat_min is not None:
            try:
                if float(interpass) < float(preheat_min):
                    result.add_issue(ValidationIssue(
                        "WPS-PREHEAT-001", "error",
                        f"Interpass max ({interpass}F) < preheat min ({preheat_min}F)",
                        "interpass_temp_max",
                    ))
            except (ValueError, TypeError):
                pass

    # PWHT-001: If pwht_required=0, temp/time must be null
    for pwht in data.get("pwht", []):
        if pwht.get("pwht_required") == 0:
            if pwht.get("temperature_min") or pwht.get("time_min"):
                result.add_issue(ValidationIssue(
                    "WPS-PWHT-001", "warning",
                    "PWHT not required but temperature/time values present",
                    "pwht_required",
                ))

    # GAS-001: GTAW requires shielding gas
    processes = data.get("processes", [])
    gas_entries = data.get("gas", [])
    for proc in processes:
        ptype = proc.get("process_type", "")
        seq = proc.get("process_sequence", 1)
        if "GTAW" in ptype:
            matching_gas = [g for g in gas_entries
                           if g.get("process_sequence") == seq and g.get("shielding_gas")]
            if not matching_gas:
                result.add_issue(ValidationIssue(
                    "WPS-GAS-001", "error",
                    f"GTAW process (seq {seq}) requires shielding gas but none specified",
                    "shielding_gas",
                ))

    # GAS-002: SMAW should not have shielding gas
    for proc in processes:
        ptype = proc.get("process_type", "")
        seq = proc.get("process_sequence", 1)
        if ptype == "SMAW":
            matching_gas = [g for g in gas_entries
                           if g.get("process_sequence") == seq and g.get("shielding_gas")]
            if matching_gas:
                result.add_issue(ValidationIssue(
                    "WPS-GAS-002", "warning",
                    f"SMAW process (seq {seq}) should not have shielding gas",
                    "shielding_gas",
                ))

    # ELEC-001: Current type compatibility
    electrical = data.get("electrical", [])
    for ep in electrical:
        current = ep.get("current_type", "")
        # GTAW typically uses DCEN or AC, not DCEP
        # This is a soft check — specialty applications may vary
        seq = ep.get("process_sequence", 1)
        matching_proc = [p for p in processes if p.get("process_sequence") == seq]
        if matching_proc:
            ptype = matching_proc[0].get("process_type", "")
            if ptype == "GTAW" and current == "DCEP":
                result.add_issue(ValidationIssue(
                    "WPS-ELEC-001", "warning",
                    "GTAW typically uses DCEN or AC, not DCEP",
                    "current_type",
                ))


def _validate_pqr_cross_field(data: Dict, result: ValidationResult):
    """PQR-specific cross-field rules."""
    # TENSILE-001: check test results
    for test in data.get("tensile_tests", []):
        r = test.get("result", "")
        if r and r not in ("Acceptable", "Rejected"):
            result.add_issue(ValidationIssue(
                "PQR-TENSILE-001", "warning",
                f"Tensile test result '{r}' should be 'Acceptable' or 'Rejected'",
                "result", "weld_pqr_tensile_tests",
            ))

    # BEND-001: Bend test results
    for test in data.get("bend_tests", []):
        r = test.get("result", "")
        if r and r not in ("Acceptable", "Rejected"):
            result.add_issue(ValidationIssue(
                "PQR-BEND-001", "error",
                f"Bend test result '{r}' must be 'Acceptable' or 'Rejected'",
                "result", "weld_pqr_bend_tests",
            ))

    # WITNESS-001: Should have personnel
    personnel = data.get("personnel", [])
    if not personnel:
        result.add_issue(ValidationIssue(
            "PQR-WITNESS-001", "warning",
            "PQR should have at least one witness or examiner",
            "personnel",
        ))


def _validate_wpq_cross_field(data: Dict, result: ValidationResult,
                               conn: Optional[sqlite3.Connection] = None):
    """WPQ-specific cross-field rules."""
    parent = data.get("parent", {})

    # EXP-001: expiration check
    test_date = parent.get("test_date")
    exp_date = parent.get("initial_expiration_date")
    if test_date and exp_date:
        try:
            from datetime import datetime, timedelta
            td = datetime.strptime(test_date, "%Y-%m-%d")
            ed = datetime.strptime(exp_date, "%Y-%m-%d")
            expected = td + timedelta(days=180)
            delta = abs((ed - expected).days)
            if delta > 7:  # Allow 7-day tolerance
                result.add_issue(ValidationIssue(
                    "WPQ-EXP-001", "warning",
                    f"Expiration {exp_date} differs from expected (test + 180d = {expected.strftime('%Y-%m-%d')})",
                    "initial_expiration_date",
                ))
        except (ValueError, TypeError):
            pass

    # WPS-001: WPS reference should exist
    wps_number = parent.get("wps_number")
    if wps_number and conn:
        row = conn.execute(
            "SELECT 1 FROM weld_wps WHERE wps_number = ?", (wps_number,)
        ).fetchone()
        if not row:
            result.add_issue(ValidationIssue(
                "WPQ-WPS-001", "warning",
                f"WPS '{wps_number}' not found in database",
                "wps_number",
            ))

    # TEST-001: Should have test results
    tests = data.get("tests", [])
    if not tests:
        result.add_issue(ValidationIssue(
            "WPQ-TEST-001", "warning",
            "No test results found for WPQ",
            "tests",
        ))


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------

def validate_required(data: Dict[str, Any], form_type: str) -> ValidationResult:
    """Check required fields are present and non-empty."""
    result = ValidationResult()
    parent = data.get("parent", {})

    from qms.welding.forms import get_form_definition
    form_def = get_form_definition(form_type)

    # Check identifier
    id_col = form_def.identifier_column
    if not parent.get(id_col):
        result.add_issue(ValidationIssue(
            f"{form_type.upper()}-REQ-001", "error",
            f"{id_col} is required",
            id_col, form_def.parent_table,
        ))

    # Form-type-specific required fields
    if form_type == "wps":
        if not data.get("processes"):
            result.add_issue(ValidationIssue(
                "WPS-REQ-002", "error", "At least one process is required",
                "processes",
            ))
        if not data.get("base_metals"):
            result.add_issue(ValidationIssue(
                "WPS-REQ-003", "error", "At least one base metal entry is required",
                "base_metals",
            ))
        if not data.get("filler_metals"):
            result.add_issue(ValidationIssue(
                "WPS-REQ-004", "error", "At least one filler metal entry is required",
                "filler_metals",
            ))
    elif form_type == "pqr":
        if not parent.get("test_date"):
            result.add_issue(ValidationIssue(
                "PQR-REQ-002", "error", "Test date is required",
                "test_date", "weld_pqr",
            ))
    elif form_type == "wpq":
        if not parent.get("welder_name") and not parent.get("welder_stamp"):
            result.add_issue(ValidationIssue(
                "WPQ-REQ-002", "error", "Welder name or stamp is required",
                "welder_name", "weld_wpq",
            ))
        if not parent.get("process_type"):
            result.add_issue(ValidationIssue(
                "WPQ-REQ-003", "error", "Process type is required",
                "process_type", "weld_wpq",
            ))
        if not parent.get("test_date"):
            result.add_issue(ValidationIssue(
                "WPQ-REQ-004", "error", "Test date is required",
                "test_date", "weld_wpq",
            ))
    elif form_type == "bps":
        if not parent.get("brazing_process"):
            result.add_issue(ValidationIssue(
                "BPS-REQ-002", "error", "Brazing process is required",
                "brazing_process", "weld_bps",
            ))

    return result


# ---------------------------------------------------------------------------
# Main validation entry point
# ---------------------------------------------------------------------------

def validate_form_data(data: Dict[str, Any], form_type: str,
                       conn: Optional[sqlite3.Connection] = None) -> ValidationResult:
    """
    Run all validation checks on extracted form data.

    Args:
        data: Extracted data dict with 'parent' and child sections.
        form_type: 'wps', 'pqr', 'wpq', 'bps', 'bpq'.
        conn: Database connection (for lookup and cross-ref validation).

    Returns:
        ValidationResult with all issues found.
    """
    result = ValidationResult()

    # 1. Required fields
    result.merge(validate_required(data, form_type))

    # 2. Range checks
    result.merge(validate_ranges(data, form_type))

    # 3. Lookup validation (requires DB connection)
    if conn:
        result.merge(validate_lookups(conn, data, form_type))

    # 4. Cross-field rules
    result.merge(validate_cross_field(data, form_type, conn))

    logger.info(
        "Validation %s: %d errors, %d warnings",
        "FAILED" if not result.is_valid else "PASSED",
        result.error_count,
        result.warning_count,
    )

    return result
