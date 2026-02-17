"""
Tests for welding/qualification_rules.py — multi-code qualification derivation engine.

Covers ASME IX, AWS D1.1, registry, governing logic, edge cases.
"""

import pytest
from qms.welding.qualification_rules import (
    UNLIMITED,
    ASMEIXCode,
    AWSD11Code,
    DerivationResult,
    QualificationCode,
    _parse_od,
    _parse_position,
    _has_backing,
    derive_qualified_ranges,
    get_code,
    list_codes,
    register_code,
)


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def wpq_parent_6g():
    """Typical WPQ parent data: 6G, 0.375" thick, 2.375" OD pipe."""
    return {
        "coupon_thickness": 0.375,
        "coupon_diameter": '2" N.P.S (2.375" OD)',
        "test_position": "6G",
        "backing_actual": "N/A Single Sided weld open root",
        "p_number_actual": "P-1 to P-1",
        "f_number_actual": "F3/F4",
        "deposit_thickness_actual": 0.375,
        "filler_type": "Coated Solid Electrodes",
    }


@pytest.fixture
def wpq_parent_2g():
    """WPQ: 2G plate, 0.5" thick."""
    return {
        "coupon_thickness": 0.5,
        "test_position": "2G",
        "backing_actual": "With Backing",
        "p_number_actual": "P-8 to P-8",
        "f_number_actual": "F6",
    }


@pytest.fixture
def bpqr_parent():
    """Typical BPQR parent data for brazing."""
    return {
        "coupon_thickness": 0.065,
        "coupon_diameter": "2-1/8",
        "test_position": "Vertical",
        "p_number_actual": "107 TO 107",
        "f_number": 104,
        "joint_type": "Socket",
        "overlap_length": 0.750,
    }


@pytest.fixture
def asme():
    return ASMEIXCode()


@pytest.fixture
def aws():
    return AWSD11Code()


# ===========================================================================
# Registry tests
# ===========================================================================

class TestRegistry:
    def test_list_codes_contains_builtins(self):
        codes = list_codes()
        assert "asme_ix" in codes
        assert "aws_d1_1" in codes

    def test_get_code_valid(self):
        code = get_code("asme_ix")
        assert code.code_id == "asme_ix"

    def test_get_code_invalid(self):
        with pytest.raises(ValueError, match="Unknown code"):
            get_code("nonexistent_code")

    def test_register_custom_code(self):
        class DummyCode(QualificationCode):
            @property
            def code_id(self): return "_test_dummy"
            @property
            def code_name(self): return "Test Dummy"
            @property
            def applicable_form_types(self): return ["wpq"]
            def derive_thickness(self, p, ft): return None
            def derive_diameter(self, p, ft): return None
            def derive_positions(self, p, ft, conn=None): return None
            def derive_backing(self, p, ft): return None

        register_code(DummyCode())
        assert "_test_dummy" in list_codes()
        code = get_code("_test_dummy")
        assert code.code_name == "Test Dummy"


# ===========================================================================
# Helper tests
# ===========================================================================

class TestHelpers:
    def test_parse_od_with_nps_and_od(self):
        assert _parse_od('2" N.P.S (2.375" OD)') == pytest.approx(2.375)

    def test_parse_od_fraction(self):
        assert _parse_od("2-7/8") == pytest.approx(2.875)

    def test_parse_od_simple_fraction(self):
        assert _parse_od("7/8") == pytest.approx(0.875)

    def test_parse_od_plain_number(self):
        assert _parse_od("24") == pytest.approx(24.0)

    def test_parse_od_float(self):
        assert _parse_od("2.375") == pytest.approx(2.375)

    def test_parse_od_none(self):
        assert _parse_od(None) is None

    def test_parse_od_empty(self):
        assert _parse_od("") is None

    def test_parse_position(self):
        assert _parse_position("6g") == "6G"
        assert _parse_position("  2G  ") == "2G"
        assert _parse_position(None) is None

    def test_has_backing_open_root(self):
        assert _has_backing({"backing_actual": "N/A Single Sided weld open root"}) is False

    def test_has_backing_with(self):
        assert _has_backing({"backing_actual": "With Backing"}) is True

    def test_has_backing_none_str(self):
        assert _has_backing({"backing_actual": "N/A None"}) is False

    def test_has_backing_empty(self):
        assert _has_backing({"backing_actual": ""}) is True  # default


# ===========================================================================
# ASME IX — Thickness (QW-452.1)
# ===========================================================================

class TestASMEThickness:
    def test_very_thin_coupon(self, asme):
        """t < 1/16": qualified range = (t, t)"""
        result = asme.derive_thickness({"coupon_thickness": 0.04}, "wpq")
        assert result is not None
        t_min, t_max, ref = result
        assert t_min == pytest.approx(0.04)
        assert t_max == pytest.approx(0.04)
        assert "QW-452.1" in ref

    def test_medium_coupon(self, asme):
        """1/16 <= t < 3/8: qualified = (1/16, 2t)"""
        result = asme.derive_thickness({"coupon_thickness": 0.154}, "wpq")
        t_min, t_max, ref = result
        assert t_min == pytest.approx(1 / 16)
        assert t_max == pytest.approx(0.308)
        assert "QW-452.1" in ref

    def test_thick_coupon(self, asme):
        """t >= 3/8: qualified = (1/16, unlimited)"""
        result = asme.derive_thickness({"coupon_thickness": 0.5}, "wpq")
        t_min, t_max, ref = result
        assert t_min == pytest.approx(1 / 16)
        assert t_max == UNLIMITED

    def test_boundary_three_eighths(self, asme):
        """t == 3/8 exactly: hits the >= 3/8 branch."""
        result = asme.derive_thickness({"coupon_thickness": 0.375}, "wpq")
        _, t_max, _ = result
        assert t_max == UNLIMITED

    def test_missing_thickness(self, asme):
        result = asme.derive_thickness({}, "wpq")
        assert result is None

    def test_brazing_thickness(self, asme):
        """QB-452.1 brazing rules differ at 3/16 boundary."""
        result = asme.derive_thickness({"coupon_thickness": 0.1}, "bpqr")
        t_min, t_max, ref = result
        assert t_min == pytest.approx(1 / 16)
        assert t_max == pytest.approx(0.2)
        assert "QB-452.1" in ref


# ===========================================================================
# ASME IX — Diameter (QW-452.3)
# ===========================================================================

class TestASMEDiameter:
    def test_small_pipe(self, asme):
        """OD < 1": qualified = (OD, 1")"""
        result = asme.derive_diameter({"coupon_diameter": "0.75"}, "wpq")
        d_min, d_max, ref = result
        assert d_min == pytest.approx(0.75)
        assert d_max == pytest.approx(1.0)

    def test_medium_pipe(self, asme):
        """1" <= OD < 2-7/8": qualified = (1", unlimited)"""
        result = asme.derive_diameter({"coupon_diameter": '2" N.P.S (2.375" OD)'}, "wpq")
        d_min, d_max, ref = result
        assert d_min == pytest.approx(1.0)
        assert d_max == UNLIMITED

    def test_large_pipe(self, asme):
        """OD >= 2-7/8": qualified = (2-7/8", unlimited)"""
        result = asme.derive_diameter({"coupon_diameter": "24"}, "wpq")
        d_min, d_max, _ = result
        assert d_min == pytest.approx(2.875)
        assert d_max == UNLIMITED

    def test_boundary_2_875(self, asme):
        result = asme.derive_diameter({"coupon_diameter": "2-7/8"}, "wpq")
        d_min, _, _ = result
        assert d_min == pytest.approx(2.875)

    def test_missing_diameter(self, asme):
        result = asme.derive_diameter({}, "wpq")
        assert result is None


# ===========================================================================
# ASME IX — Positions (QW-461.9)
# ===========================================================================

class TestASMEPositions:
    def test_6g_qualifies_all(self, asme):
        result = asme.derive_positions({"test_position": "6G"}, "wpq")
        groove, fillet, ref = result
        assert groove == "All"
        assert fillet == "All"
        assert "QW-461" in ref

    def test_2g_groove_and_fillet(self, asme):
        result = asme.derive_positions({"test_position": "2G"}, "wpq")
        groove, fillet, ref = result
        assert "1G" in groove and "2G" in groove
        assert "1F" in fillet and "2F" in fillet

    def test_1g_groove_only(self, asme):
        result = asme.derive_positions({"test_position": "1G"}, "wpq")
        groove, fillet, _ = result
        assert groove == "1G"
        assert fillet == "1F"

    def test_fillet_only_position(self, asme):
        result = asme.derive_positions({"test_position": "2F"}, "wpq")
        groove, fillet, _ = result
        assert groove == "N/A"
        assert "1F" in fillet and "2F" in fillet

    def test_missing_position(self, asme):
        result = asme.derive_positions({}, "wpq")
        assert result is None

    def test_brazing_elevated_position(self, asme):
        result = asme.derive_positions({"test_position": "Vertical"}, "bpqr")
        positions, _, ref = result
        assert positions == "All"
        assert "QB-461" in ref


# ===========================================================================
# ASME IX — Backing (QW-402.4)
# ===========================================================================

class TestASMEBacking:
    def test_without_backing(self, asme):
        parent = {"backing_actual": "N/A Single Sided weld open root"}
        result = asme.derive_backing(parent, "wpq")
        bt, ref = result
        assert bt == "With or Without"

    def test_with_backing(self, asme):
        parent = {"backing_actual": "With Backing"}
        result = asme.derive_backing(parent, "wpq")
        bt, ref = result
        assert bt == "With Only"

    def test_brazing_no_backing(self, asme):
        result = asme.derive_backing({}, "bpqr")
        assert result is None


# ===========================================================================
# ASME IX — Supplemental (P/F numbers, deposit)
# ===========================================================================

class TestASMESupplemental:
    def test_p_number_cascade_low(self, asme):
        result = asme.derive_supplemental(
            {"p_number_actual": "P-1 to P-1"}, "wpq"
        )
        assert "p_number_qualified" in result
        val, ref = result["p_number_qualified"]
        assert "P-1 thru P-11" in val
        assert "QW-423" in ref

    def test_p_number_high(self, asme):
        result = asme.derive_supplemental(
            {"p_number_actual": "P-34"}, "wpq"
        )
        val, _ = result["p_number_qualified"]
        assert val == "P-34"

    def test_f_number_cascade(self, asme):
        result = asme.derive_supplemental(
            {"f_number_actual": "F4"}, "wpq"
        )
        val, ref = result["f_number_qualified"]
        assert "F4" in val and "F3" in val and "F2" in val and "F1" in val
        assert "QW-433" in ref

    def test_f_number_dual(self, asme):
        result = asme.derive_supplemental(
            {"f_number_actual": "F3/F4"}, "wpq"
        )
        val, _ = result["f_number_qualified"]
        # Max is F4, so qualifies F4, F3, F2, F1
        assert "F4" in val

    def test_deposit_thickness(self, asme):
        result = asme.derive_supplemental(
            {"deposit_thickness_actual": 0.375}, "wpq"
        )
        val, ref = result["deposit_thickness_max"]
        assert val == pytest.approx(0.75)
        assert "QW-452.5" in ref

    def test_filler_type(self, asme):
        result = asme.derive_supplemental(
            {"filler_type": "Coated Solid Electrodes"}, "wpq"
        )
        val, _ = result["filler_type_qualified"]
        assert val == "Coated Solid Electrodes"

    def test_bpqr_joint_overlap(self, asme):
        result = asme.derive_supplemental(
            {"joint_type": "Socket", "overlap_length": 0.75}, "bpqr"
        )
        assert "joint_type_qualified" in result
        assert "overlap_qualified" in result


# ===========================================================================
# AWS D1.1 — Thickness (Table 6.11)
# ===========================================================================

class TestAWSThickness:
    def test_thin_coupon(self, aws):
        """t < 3/8": qualified = (1/8, 2t)"""
        result = aws.derive_thickness({"coupon_thickness": 0.25}, "wpq")
        t_min, t_max, ref = result
        assert t_min == pytest.approx(1 / 8)
        assert t_max == pytest.approx(0.5)
        assert "Table 6.11" in ref

    def test_medium_coupon(self, aws):
        """3/8 <= t < 1": qualified = (1/8, 2t)"""
        result = aws.derive_thickness({"coupon_thickness": 0.5}, "wpq")
        t_min, t_max, _ = result
        assert t_min == pytest.approx(1 / 8)
        assert t_max == pytest.approx(1.0)

    def test_thick_coupon(self, aws):
        """t >= 1": qualified = (1/8, unlimited)"""
        result = aws.derive_thickness({"coupon_thickness": 1.5}, "wpq")
        t_min, t_max, _ = result
        assert t_min == pytest.approx(1 / 8)
        assert t_max == UNLIMITED

    def test_missing(self, aws):
        assert aws.derive_thickness({}, "wpq") is None


# ===========================================================================
# AWS D1.1 — Diameter (Table 6.11)
# ===========================================================================

class TestAWSDiameter:
    def test_small_pipe(self, aws):
        result = aws.derive_diameter({"coupon_diameter": "2.375"}, "wpq")
        d_min, d_max, _ = result
        assert d_min == pytest.approx(2.375)
        assert d_max == pytest.approx(4.75)

    def test_medium_pipe(self, aws):
        result = aws.derive_diameter({"coupon_diameter": "8"}, "wpq")
        d_min, d_max, _ = result
        assert d_min == pytest.approx(4.0)
        assert d_max == UNLIMITED

    def test_large_pipe(self, aws):
        result = aws.derive_diameter({"coupon_diameter": "36"}, "wpq")
        d_min, d_max, _ = result
        assert d_min == pytest.approx(4.0)
        assert d_max == UNLIMITED


# ===========================================================================
# AWS D1.1 — Positions (Table 6.10)
# ===========================================================================

class TestAWSPositions:
    def test_6g_all(self, aws):
        result = aws.derive_positions({"test_position": "6G"}, "wpq")
        groove, fillet, ref = result
        assert groove == "All"
        assert fillet == "All"
        assert "Table 6.10" in ref

    def test_3g_positions(self, aws):
        result = aws.derive_positions({"test_position": "3G"}, "wpq")
        groove, fillet, _ = result
        assert "1G" in groove and "3G" in groove
        assert "1F" in fillet and "2F" in fillet and "3F" in fillet


# ===========================================================================
# AWS D1.1 — Backing
# ===========================================================================

class TestAWSBacking:
    def test_without(self, aws):
        bt, ref = aws.derive_backing(
            {"backing_actual": "open root"}, "wpq"
        )
        assert bt == "With or Without"
        assert "Clause 6" in ref

    def test_with(self, aws):
        bt, _ = aws.derive_backing(
            {"backing_actual": "With Backing"}, "wpq"
        )
        assert bt == "With Only"


# ===========================================================================
# AWS D1.1 — Not applicable to BPQR
# ===========================================================================

class TestAWSApplicability:
    def test_not_applicable_to_bpqr(self, aws):
        assert "bpqr" not in aws.applicable_form_types


# ===========================================================================
# Orchestrator — derive_qualified_ranges
# ===========================================================================

class TestOrchestrator:
    def test_wpq_full_derivation(self, wpq_parent_6g):
        data = {"parent": wpq_parent_6g}
        result = derive_qualified_ranges(data, "wpq")

        assert "asme_ix" in result.per_code
        assert "aws_d1_1" in result.per_code
        assert len(result.rules_fired) > 0
        assert len(result.warnings) == 0

    def test_governing_thickness(self, wpq_parent_6g):
        """Governing thickness should be max(mins), min(maxes)."""
        data = {"parent": wpq_parent_6g}
        result = derive_qualified_ranges(data, "wpq")

        asme_t_min = result.per_code["asme_ix"]["thickness_qualified_min"]
        aws_t_min = result.per_code["aws_d1_1"]["thickness_qualified_min"]

        gov_min = result.governing["thickness_qualified_min"]
        assert gov_min == pytest.approx(max(asme_t_min, aws_t_min))

    def test_governing_diameter(self, wpq_parent_6g):
        data = {"parent": wpq_parent_6g}
        result = derive_qualified_ranges(data, "wpq")

        asme_d_max = result.per_code["asme_ix"]["diameter_qualified_max"]
        aws_d_max = result.per_code["aws_d1_1"]["diameter_qualified_max"]

        gov_max = result.governing["diameter_qualified_max"]
        assert gov_max == pytest.approx(min(asme_d_max, aws_d_max))

    def test_governing_positions_all(self, wpq_parent_6g):
        """6G qualifies All for both codes."""
        data = {"parent": wpq_parent_6g}
        result = derive_qualified_ranges(data, "wpq")
        assert result.governing["groove_positions_qualified"] == "All"

    def test_governing_backing_without(self, wpq_parent_6g):
        """Open root = With or Without for both codes."""
        data = {"parent": wpq_parent_6g}
        result = derive_qualified_ranges(data, "wpq")
        assert result.governing["backing_type"] == "With or Without"

    def test_governing_backing_with_only(self, wpq_parent_2g):
        """With backing = most restrictive is 'With Only'."""
        data = {"parent": wpq_parent_2g}
        result = derive_qualified_ranges(data, "wpq")
        assert result.governing["backing_type"] == "With Only"

    def test_bpqr_only_asme(self, bpqr_parent):
        """BPQR should only have ASME IX, not AWS D1.1."""
        data = {"parent": bpqr_parent}
        result = derive_qualified_ranges(data, "bpqr")

        assert "asme_ix" in result.per_code
        assert "aws_d1_1" not in result.per_code

    def test_specific_codes_filter(self, wpq_parent_6g):
        """Only run specified codes."""
        data = {"parent": wpq_parent_6g}
        result = derive_qualified_ranges(data, "wpq", codes=("asme_ix",))

        assert "asme_ix" in result.per_code
        assert "aws_d1_1" not in result.per_code

    def test_empty_parent(self):
        result = derive_qualified_ranges({"parent": {}}, "wpq")
        # Empty dict is falsy, so hits the early "no parent data" guard
        assert any("No parent data" in w for w in result.warnings)

    def test_no_parent(self):
        result = derive_qualified_ranges({}, "wpq")
        assert "No parent data" in result.warnings[0]

    def test_invalid_code_id(self, wpq_parent_6g):
        data = {"parent": wpq_parent_6g}
        result = derive_qualified_ranges(data, "wpq", codes=("bogus",))
        assert any("Unknown" in w for w in result.warnings)

    def test_inapplicable_code_warning(self, bpqr_parent):
        data = {"parent": bpqr_parent}
        result = derive_qualified_ranges(data, "bpqr", codes=("aws_d1_1",))
        assert any("not applicable" in w for w in result.warnings)

    def test_p_number_in_governing(self, wpq_parent_6g):
        data = {"parent": wpq_parent_6g}
        result = derive_qualified_ranges(data, "wpq")
        # P-number comes from ASME IX only (AWS D1.1 doesn't set it)
        assert "p_number_qualified" in result.governing
        assert "P-1 thru P-11" in result.governing["p_number_qualified"]

    def test_f_number_in_governing(self, wpq_parent_6g):
        data = {"parent": wpq_parent_6g}
        result = derive_qualified_ranges(data, "wpq")
        assert "f_number_qualified" in result.governing
        assert "F4" in result.governing["f_number_qualified"]

    def test_deposit_thickness_in_governing(self, wpq_parent_6g):
        data = {"parent": wpq_parent_6g}
        result = derive_qualified_ranges(data, "wpq")
        assert result.governing["deposit_thickness_max"] == pytest.approx(0.75)

    def test_rules_fired_audit_trail(self, wpq_parent_6g):
        data = {"parent": wpq_parent_6g}
        result = derive_qualified_ranges(data, "wpq")
        assert len(result.rules_fired) >= 8  # At least 4 fields × 2 codes

    def test_unsupported_form_type(self):
        result = derive_qualified_ranges({"parent": {"coupon_thickness": 0.5}}, "wps")
        assert any("No applicable" in w for w in result.warnings)


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_thickness_at_exact_boundary_1_16(self, asme):
        """1/16 is in the medium range, not the thin range."""
        result = asme.derive_thickness({"coupon_thickness": 1 / 16}, "wpq")
        t_min, t_max, ref = result
        assert t_min == pytest.approx(1 / 16)
        assert t_max == pytest.approx(2 * (1 / 16))
        assert "(b)" in ref

    def test_diameter_at_exact_1_inch(self, asme):
        """1" is in the medium range."""
        result = asme.derive_diameter({"coupon_diameter": "1.0"}, "wpq")
        d_min, _, _ = result
        assert d_min == pytest.approx(1.0)

    def test_unparseable_diameter(self, asme):
        result = asme.derive_diameter({"coupon_diameter": "N/A Plate"}, "wpq")
        assert result is None

    def test_zero_thickness(self, asme):
        result = asme.derive_thickness({"coupon_thickness": 0}, "wpq")
        t_min, t_max, _ = result
        assert t_min == pytest.approx(0)
        assert t_max == pytest.approx(0)

    def test_string_thickness(self, asme):
        """Thickness stored as string should still work."""
        result = asme.derive_thickness({"coupon_thickness": "0.375"}, "wpq")
        assert result is not None
        _, t_max, _ = result
        assert t_max == UNLIMITED

    def test_od_with_unicode_quotes(self):
        """Handle fancy quotes in OD string."""
        assert _parse_od('2.375\u201d OD') == pytest.approx(2.375)
