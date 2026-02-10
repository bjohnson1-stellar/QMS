"""Tests for pipe size parsing, comparison logic, and line number parsing."""

from qms.engineering.base import ValidationStatus
from qms.engineering.validators import parse_pipe_size, compare_sizes, parse_line_number


class TestParsePipeSize:
    def test_with_quote(self):
        assert parse_pipe_size('4"') == 4.0

    def test_plain_number(self):
        assert parse_pipe_size("6") == 6.0

    def test_fraction_dash(self):
        assert parse_pipe_size("2-1/2") == 2.5

    def test_fraction_space(self):
        assert parse_pipe_size("1 1/2") == 1.5

    def test_simple_fraction(self):
        assert parse_pipe_size("3/4") == 0.75

    def test_empty_returns_none(self):
        assert parse_pipe_size("") is None

    def test_garbage_returns_none(self):
        assert parse_pipe_size("abc") is None

    def test_float_string(self):
        assert parse_pipe_size("2.5") == 2.5


class TestCompareSizes:
    def test_within_tolerance(self):
        status, dev, notes = compare_sizes("4", 4.0, tolerance_pct=10.0)
        assert status == ValidationStatus.PASS
        assert dev == 0.0

    def test_oversized(self):
        status, dev, notes = compare_sizes("6", 4.0, tolerance_pct=10.0)
        assert status == ValidationStatus.WARNING
        assert dev == 50.0
        assert "Oversized" in notes

    def test_undersized(self):
        status, dev, notes = compare_sizes("3", 4.0, tolerance_pct=10.0)
        assert status == ValidationStatus.FAIL
        assert dev == -25.0
        assert "UNDERSIZED" in notes

    def test_unparseable(self):
        status, dev, notes = compare_sizes("???", 4.0)
        assert status == ValidationStatus.REVIEW
        assert "Cannot parse" in notes

    def test_zero_calculated(self):
        status, dev, notes = compare_sizes("4", 0.0)
        assert status == ValidationStatus.REVIEW


class TestParseLineNumber:
    def test_full_format(self):
        result = parse_line_number("2-NH3-101-3A")
        assert result["size"] == 2.0
        assert result["refrigerant"] == "NH3"

    def test_no_refrigerant(self):
        result = parse_line_number("4-CW-201")
        assert result["size"] == 4.0
        assert result["refrigerant"] == "CW"

    def test_oversized_rejected(self):
        result = parse_line_number("50-NH3-101")
        assert result["size"] is None  # 50 > 24 not a valid pipe size

    def test_preserves_original(self):
        result = parse_line_number("6-NH3-300")
        assert result["original"] == "6-NH3-300"
