"""
Tests for the form-field extraction module.

Tests the QW-484 form field → database column mapping, numeric parsing,
test record extraction, and WPQ number generation.
"""

import pytest
from qms.welding.extraction.form_fields import (
    extract_wpq_form_fields,
    has_form_fields,
    _parse_float,
    _parse_thickness_range,
    _parse_diameter_range,
    _clean,
    _normalize_date,
    _map_parent_fields,
    _extract_tests,
)


# ---------------------------------------------------------------------------
# Numeric parsing
# ---------------------------------------------------------------------------

class TestParseFloat:
    def test_simple_decimal(self):
        assert _parse_float(".218") == 0.218

    def test_double_dot(self):
        """Double-dot artifact from PDF form: ..218 → 0.218."""
        assert _parse_float("..218") == 0.218

    def test_with_units(self):
        assert _parse_float('.436" Max.') == 0.436

    def test_integer(self):
        assert _parse_float("6") == 6.0

    def test_empty(self):
        assert _parse_float("") is None

    def test_no_number(self):
        assert _parse_float("N/A") is None

    def test_negative(self):
        assert _parse_float("-20") == -20.0


class TestParseThicknessRange:
    def test_standard_range(self):
        assert _parse_thickness_range('.0625" to .436"') == (0.0625, 0.436)

    def test_max_only(self):
        assert _parse_thickness_range('.436" Max.') == (None, 0.436)

    def test_empty(self):
        assert _parse_thickness_range("") == (None, None)

    def test_single_value(self):
        assert _parse_thickness_range('.218"') == (None, 0.218)

    def test_no_numbers(self):
        assert _parse_thickness_range("N/A") == (None, None)


class TestParseDiameterRange:
    def test_over_pattern(self):
        """'Over 1" Diameter' → min=1.0, max=unlimited."""
        mn, mx = _parse_diameter_range('Over 1" Diameter')
        assert mn == 1.0
        assert mx is None

    def test_range_to_unlimited(self):
        mn, mx = _parse_diameter_range('2.875" to Unlimited')
        assert mn == 2.875
        assert mx is None

    def test_numeric_range(self):
        mn, mx = _parse_diameter_range('2.375" to 6.625"')
        assert mn == 2.375
        assert mx == 6.625

    def test_empty(self):
        assert _parse_diameter_range("") == (None, None)


# ---------------------------------------------------------------------------
# Date normalization
# ---------------------------------------------------------------------------

class TestNormalizeDate:
    def test_us_format(self):
        assert _normalize_date("6/2/2022") == "2022-06-02"

    def test_padded_us_format(self):
        assert _normalize_date("03/03/2025") == "2025-03-03"

    def test_iso_format(self):
        assert _normalize_date("2022-06-02") == "2022-06-02"

    def test_empty(self):
        assert _normalize_date("") is None

    def test_none(self):
        assert _normalize_date(None) is None


# ---------------------------------------------------------------------------
# Parent field mapping
# ---------------------------------------------------------------------------

class TestMapParentFields:
    """Test the full QW-484 form field → DB column mapping."""

    @pytest.fixture
    def sample_fields(self):
        """Realistic QW-484 form field values."""
        return {
            "Test Description": "Austin Anderson",
            "Identification No": "A-9",
            "1": " CS-01-P1-SMAW ",
            "2": "P1 to P1",
            "Welding Processes": "SMAW",
            "Type": "Manual",
            "Thickness": "..218",
            "Actual Values 1": "N/A-Single Sided Weld -Open Root",
            "Actual Values 2": '2" N.P.S. (2.375" O.D.)',
            "Actual Values 3": "P-1 to P-1",
            "Actual Values 4": '.218"',
            "Actual Values 5": "SFA / A 5.1",
            "Actual Values 6": "E6010 / E7018",
            "Actual Values 7": "F3 / F4",
            "Actual Values 8": "N/A/ None",
            "Actual Values 9": "Coated Solid Electrodes",
            "Actual Values 10": ".218",
            "Actual Values 11": "6G",
            "Actual Values 12": "Uphill",
            "Actual Values 13": "N/A-None",
            "Actual Values 14": "N/A",
            "Actual Values 15": "DCEP",
            "Range Qualified 1": "Open Root or with Backing",
            "Range Qualified 2": 'Over 1" Diameter',
            "Range Qualified 3": "P1 thru P 11 & P 4X",
            "Range Qualified 4": '.0625" to .436"',
            "1_2": "F4, F3, F2, & F1",
            "3": "Coated Solid Electrodes",
            "4": '.436" Max.',
            "5": "All",
            "6": "Uphill",
            "1_3": "Jonathan Robertson",
            "Company": "**Team Inc.",
            "2_3": "N/A",
            "Laboratory Test No": "1136-001963-05",
            "Welding Supervised Witnessed By": "Jared Brownfield",
            "Company_2": "Stellar Group, The",
            "Organization": "Stellar Group, The",
            "Date": "6/2/2022",
            "By": "Phil Turner",
        }

    def test_welder_identity(self, sample_fields):
        parent = _map_parent_fields(sample_fields)
        assert parent["welder_name"] == "Austin Anderson"
        assert parent["welder_stamp"] == "A-9"

    def test_wps_cleaned(self, sample_fields):
        parent = _map_parent_fields(sample_fields)
        assert parent["wps_number"] == "CS-01-P1-SMAW"

    def test_wps_combo_process(self):
        """WPS with parenthetical filler info is cleaned correctly."""
        fields = {
            "1": " CS-02-P1- GTAW /SMAW          (ER70S-2 / E7018) ",
            "Test Description": "Test",
            "Identification No": "T-1",
            "Welding Processes": "GTAW/SMAW",
        }
        parent = _map_parent_fields(fields)
        assert parent["wps_number"] == "CS-02-P1-GTAW/SMAW"

    def test_coupon_data(self, sample_fields):
        parent = _map_parent_fields(sample_fields)
        assert parent["coupon_base_metal"] == "P1 to P1"
        assert parent["coupon_thickness"] == 0.218
        assert parent["coupon_diameter"] == '2" N.P.S. (2.375" O.D.)'
        assert parent["process_type"] == "SMAW"
        assert parent["process_variation"] == "Manual"

    def test_actual_values(self, sample_fields):
        parent = _map_parent_fields(sample_fields)
        assert parent["backing_actual"] == "N/A-Single Sided Weld -Open Root"
        assert parent["p_number_actual"] == "P-1 to P-1"
        assert parent["filler_sfa_spec"] == "SFA / A 5.1"
        assert parent["filler_aws_class"] == "E6010 / E7018"
        assert parent["f_number_actual"] == "F3 / F4"
        assert parent["deposit_thickness_actual"] == 0.218
        assert parent["test_position"] == "6G"
        assert parent["progression"] == "Uphill"
        assert parent["current_type"] == "DCEP"

    def test_range_qualified(self, sample_fields):
        parent = _map_parent_fields(sample_fields)
        assert parent["backing_type"] == "Open Root or with Backing"
        assert parent["diameter_qualified_min"] == 1.0
        assert parent["diameter_qualified_max"] is None  # unlimited
        assert parent["p_number_qualified"] == "P1 thru P 11 & P 4X"
        assert parent["thickness_qualified_min"] == 0.0625
        assert parent["thickness_qualified_max"] == 0.436
        assert parent["f_number_qualified"] == "F4, F3, F2, & F1"
        assert parent["deposit_thickness_max"] == 0.436
        assert parent["groove_positions_qualified"] == "All"

    def test_personnel(self, sample_fields):
        parent = _map_parent_fields(sample_fields)
        assert parent["evaluator_name"] == "Jonathan Robertson"
        assert parent["evaluator_company"] == "**Team Inc."
        assert parent["witness_company"] == "Stellar Group, The"
        assert parent["lab_test_number"] == "1136-001963-05"
        assert parent["certified_by"] == "Phil Turner"

    def test_date_normalized(self, sample_fields):
        parent = _map_parent_fields(sample_fields)
        assert parent["test_date"] == "2022-06-02"
        assert parent["certified_date"] == "2022-06-02"

    def test_wpq_number_generated(self, sample_fields):
        parent = _map_parent_fields(sample_fields)
        assert parent["wpq_number"] == "A-9-CS-01-P1-SMAW"

    def test_wpq_number_fallback_process(self):
        """Without WPS, WPQ number falls back to stamp-process."""
        fields = {
            "Test Description": "Test",
            "Identification No": "B-5",
            "Welding Processes": "GTAW",
        }
        parent = _map_parent_fields(fields)
        assert parent["wpq_number"] == "B-5-GTAW"

    def test_empty_strings_become_none(self, sample_fields):
        """Empty string values should be stored as None."""
        parent = _map_parent_fields(sample_fields)
        for k, v in parent.items():
            if isinstance(v, str):
                assert v != "", f"Field '{k}' should be None, not empty string"


# ---------------------------------------------------------------------------
# Test result extraction
# ---------------------------------------------------------------------------

class TestExtractTests:
    def test_visual_result(self):
        fields = {"undefined": "Acceptable"}
        tests = _extract_tests(fields)
        assert len(tests) == 1
        assert tests[0]["test_type"] == "visual"
        assert tests[0]["result"] == "Acceptable"

    def test_no_results(self):
        fields = {}
        tests = _extract_tests(fields)
        assert tests == []

    def test_bend_test_rows(self):
        fields = {
            "TypeRow1": "Root",
            "ResultRow1": "Acceptable",
            "TypeRow1_2": "Face",
            "ResultRow1_2": "Acceptable",
        }
        tests = _extract_tests(fields)
        assert len(tests) == 2
        assert tests[0]["test_type"] == "guided_bend"
        assert tests[0]["bend_type"] == "root"
        assert tests[1]["bend_type"] == "face"

    def test_fillet_fracture(self):
        fields = {
            "Fillet Weld  Fracture Test": "Pass",
            "Length and Percent of Defects": "None",
        }
        tests = _extract_tests(fields)
        assert any(t["test_type"] == "fillet_fracture" for t in tests)

    def test_macro_exam(self):
        fields = {
            "Macro Exam": "Acceptable",
            "Fillet Sizein": "3/16",
            "Concavity  Convexity in": "0.02",
        }
        tests = _extract_tests(fields)
        macro = [t for t in tests if t["test_type"] == "macro"]
        assert len(macro) == 1
        assert macro[0]["concavity_convexity"] == 0.02

    def test_other_tests(self):
        fields = {"Other Tests": "Hardness test per ASTM E92"}
        tests = _extract_tests(fields)
        assert any(t["test_type"] == "other" for t in tests)


# ---------------------------------------------------------------------------
# Integration test with real-ish data
# ---------------------------------------------------------------------------

class TestFormFieldPipeline:
    """Test the form-field fast path through the pipeline."""

    def test_pipeline_loads_to_db(self, mock_db):
        """Form-field data can be loaded through the standard loader."""
        from qms.welding.extraction.loader import load_to_database
        from qms.welding.forms import get_form_definition

        form_def = get_form_definition("wpq")
        data = {
            "parent": {
                "wpq_number": "T-1-CS-01-P1-SMAW",
                "welder_name": "Test Welder",
                "welder_stamp": "T-1",
                "wps_number": "CS-01-P1-SMAW",
                "process_type": "SMAW",
                "process_variation": "Manual",
                "test_position": "6G",
                "test_date": "2024-01-15",
                "status": "active",
            },
            "tests": [
                {"test_type": "visual", "result": "Acceptable"},
                {"test_type": "guided_bend", "bend_type": "root",
                 "result": "Acceptable"},
            ],
        }

        result = load_to_database(data, mock_db, form_def)
        assert result["action"] == "insert"
        assert result["parent_id"] is not None
        assert result["child_counts"]["weld_wpq_tests"] == 2

        # Verify data in DB
        row = mock_db.execute(
            "SELECT * FROM weld_wpq WHERE wpq_number = 'T-1-CS-01-P1-SMAW'"
        ).fetchone()
        assert row is not None
        assert row["welder_name"] == "Test Welder"
        assert row["test_position"] == "6G"

        tests = mock_db.execute(
            "SELECT * FROM weld_wpq_tests WHERE wpq_id = ?",
            (result["parent_id"],)
        ).fetchall()
        assert len(tests) == 2

    def test_pipeline_handles_update(self, mock_db):
        """Re-extracting the same WPQ updates rather than duplicates."""
        from qms.welding.extraction.loader import load_to_database
        from qms.welding.forms import get_form_definition

        form_def = get_form_definition("wpq")
        data = {
            "parent": {
                "wpq_number": "T-1-CS-01-P1-SMAW",
                "welder_name": "Test Welder",
                "process_type": "SMAW",
                "status": "active",
            },
            "tests": [{"test_type": "visual", "result": "Acceptable"}],
        }

        # First insert
        load_to_database(data, mock_db, form_def)

        # Update with new data
        data["parent"]["welder_name"] = "Test Welder Updated"
        result = load_to_database(data, mock_db, form_def)
        assert result["action"] == "update"

        # Should still be only 1 record
        count = mock_db.execute(
            "SELECT COUNT(*) AS n FROM weld_wpq"
        ).fetchone()["n"]
        assert count == 1

        row = mock_db.execute(
            "SELECT welder_name FROM weld_wpq WHERE wpq_number = 'T-1-CS-01-P1-SMAW'"
        ).fetchone()
        assert row["welder_name"] == "Test Welder Updated"
