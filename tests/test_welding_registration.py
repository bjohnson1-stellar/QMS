"""Tests for welder stamp generation and registration."""

import pytest
from qms.welding.registration import get_next_stamp, register_new_welder


class TestGetNextStamp:
    """Test stamp generation with last_name-based prefixes."""

    def test_first_stamp_with_last_name(self, memory_db):
        """First stamp for a last name should be {Letter}01."""
        stamp = get_next_stamp(memory_db, last_name="Baker")
        assert stamp == "B01"

    def test_sequential_stamps(self, memory_db):
        """Subsequent stamps should increment the number."""
        # Seed existing stamps for prefix B
        memory_db.execute(
            "INSERT INTO weld_welder_registry (employee_number, first_name, last_name, "
            "welder_stamp, status) VALUES ('E001', 'Bob', 'Baker', 'B01', 'active')"
        )
        memory_db.execute(
            "INSERT INTO weld_welder_registry (employee_number, first_name, last_name, "
            "welder_stamp, status) VALUES ('E002', 'Bill', 'Brown', 'B02', 'active')"
        )
        memory_db.commit()

        stamp = get_next_stamp(memory_db, last_name="Barnes")
        assert stamp == "B03"

    def test_recognises_legacy_dash_format(self, memory_db):
        """Should recognise B-15 legacy format and continue sequence."""
        memory_db.execute(
            "INSERT INTO weld_welder_registry (employee_number, first_name, last_name, "
            "welder_stamp, status) VALUES ('E001', 'Bob', 'Baker', 'B-15', 'active')"
        )
        memory_db.commit()

        stamp = get_next_stamp(memory_db, last_name="Brown")
        assert stamp == "B16"

    def test_mixed_formats(self, memory_db):
        """Should handle mix of new and legacy formats."""
        # Legacy format
        memory_db.execute(
            "INSERT INTO weld_welder_registry (employee_number, first_name, last_name, "
            "welder_stamp, status) VALUES ('E001', 'Bob', 'Baker', 'B-10', 'active')"
        )
        # New format (higher number)
        memory_db.execute(
            "INSERT INTO weld_welder_registry (employee_number, first_name, last_name, "
            "welder_stamp, status) VALUES ('E002', 'Bill', 'Brown', 'B12', 'active')"
        )
        memory_db.commit()

        stamp = get_next_stamp(memory_db, last_name="Barnes")
        assert stamp == "B13"

    def test_different_prefixes_isolated(self, memory_db):
        """Stamps for different letters should be independent."""
        memory_db.execute(
            "INSERT INTO weld_welder_registry (employee_number, first_name, last_name, "
            "welder_stamp, status) VALUES ('E001', 'Bob', 'Baker', 'B-15', 'active')"
        )
        memory_db.execute(
            "INSERT INTO weld_welder_registry (employee_number, first_name, last_name, "
            "welder_stamp, status) VALUES ('E002', 'Jim', 'Jones', 'J-3', 'active')"
        )
        memory_db.commit()

        stamp_b = get_next_stamp(memory_db, last_name="Brown")
        stamp_j = get_next_stamp(memory_db, last_name="Johnson")
        assert stamp_b == "B16"
        assert stamp_j == "J04"

    def test_no_last_name_falls_back_to_z(self, memory_db):
        """Without last_name, should use Z prefix (backward compat)."""
        stamp = get_next_stamp(memory_db)
        assert stamp == "Z01"

    def test_z_prefix_recognises_legacy_z_format(self, memory_db):
        """Z prefix should recognise old Z-NN format."""
        memory_db.execute(
            "INSERT INTO weld_welder_registry (employee_number, first_name, last_name, "
            "welder_stamp, status) VALUES ('E001', 'Test', 'User', 'Z-05', 'active')"
        )
        memory_db.commit()

        stamp = get_next_stamp(memory_db)
        assert stamp == "Z06"

    def test_zero_padded_output(self, memory_db):
        """Output should always be zero-padded to 2 digits."""
        stamp = get_next_stamp(memory_db, last_name="Adams")
        assert stamp == "A01"
        assert len(stamp) == 3  # Letter + 2 digits

    def test_case_insensitive_last_name(self, memory_db):
        """Last name case shouldn't matter."""
        stamp_lower = get_next_stamp(memory_db, last_name="baker")
        stamp_upper = get_next_stamp(memory_db, last_name="BAKER")
        assert stamp_lower == stamp_upper == "B01"

    def test_empty_string_last_name(self, memory_db):
        """Empty string last_name should fall back to Z."""
        stamp = get_next_stamp(memory_db, last_name="")
        assert stamp == "Z01"

    def test_whitespace_last_name(self, memory_db):
        """Whitespace-only last_name should fall back to Z."""
        stamp = get_next_stamp(memory_db, last_name="   ")
        assert stamp == "Z01"


class TestRegisterNewWelderStamp:
    """Test that registration passes last_name to stamp generation."""

    def test_auto_stamp_uses_last_name(self, mock_db):
        """Auto-assigned stamp should use welder's last initial."""
        result = register_new_welder(
            mock_db,
            employee_number="E100",
            first_name="John",
            last_name="Martinez",
            auto_stamp=True,
        )
        assert not result["errors"]
        assert result["stamp"] == "M01"

    def test_auto_stamp_sequential(self, mock_db):
        """Second welder with same initial should get next number."""
        register_new_welder(
            mock_db,
            employee_number="E100",
            first_name="John",
            last_name="Martinez",
            auto_stamp=True,
        )
        result = register_new_welder(
            mock_db,
            employee_number="E101",
            first_name="Maria",
            last_name="Moore",
            auto_stamp=True,
        )
        assert not result["errors"]
        assert result["stamp"] == "M02"

    def test_manual_stamp_unchanged(self, mock_db):
        """Explicitly provided stamp should be used as-is."""
        result = register_new_welder(
            mock_db,
            employee_number="E100",
            first_name="John",
            last_name="Martinez",
            stamp="CUSTOM-01",
            auto_stamp=True,
        )
        assert not result["errors"]
        assert result["stamp"] == "CUSTOM-01"

    def test_auto_stamp_disabled(self, mock_db):
        """With auto_stamp=False and no stamp, should be None."""
        result = register_new_welder(
            mock_db,
            employee_number="E100",
            first_name="John",
            last_name="Martinez",
            auto_stamp=False,
        )
        assert not result["errors"]
        assert result["stamp"] is None
