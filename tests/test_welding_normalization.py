"""Tests for WPQ number normalization and creation pathway consistency."""

import pytest
from qms.welding.migrations import (
    _normalize_wpq_number,
    migrate_normalize_wpq_numbers,
)
from qms.welding.registration import add_initial_wpq


class TestNormalizeWPQNumber:
    """Test the _normalize_wpq_number() pure function."""

    def test_already_canonical(self):
        assert _normalize_wpq_number("B15-CS-01-P1-SMAW") == "B15-CS-01-P1-SMAW"

    def test_strip_whitespace(self):
        assert _normalize_wpq_number("  B15-CS-01  ") == "B15-CS-01"

    def test_uppercase(self):
        assert _normalize_wpq_number("b15-cs-01-p1-smaw") == "B15-CS-01-P1-SMAW"

    def test_equals_to_hyphen(self):
        assert _normalize_wpq_number("B15=CS=01") == "B15-CS-01"

    def test_underscore_to_hyphen(self):
        assert _normalize_wpq_number("B15_CS_01") == "B15-CS-01"

    def test_p8_p1_preserved(self):
        """The intentional P8_P1 underscore must NOT become P8-P1."""
        result = _normalize_wpq_number("M03-DM-01-P8_P1-GTAW")
        assert result == "M03-DM-01-P8_P1-GTAW"

    def test_p8_p1_case_insensitive(self):
        result = _normalize_wpq_number("m03-dm-01-p8_p1-gtaw")
        assert "P8_P1" in result

    def test_collapse_double_hyphens(self):
        assert _normalize_wpq_number("B15--CS--01") == "B15-CS-01"

    def test_strip_trailing_hyphen(self):
        assert _normalize_wpq_number("B15-CS-01-") == "B15-CS-01"

    def test_process_separator_underscore(self):
        """GTAW_SMAW should become GTAW/SMAW."""
        result = _normalize_wpq_number("B15-CS-02-P1-GTAW_SMAW")
        assert result == "B15-CS-02-P1-GTAW/SMAW"

    def test_process_separator_space(self):
        """GTAW SMAW should become GTAW/SMAW."""
        result = _normalize_wpq_number("B15-CS-02-P1-GTAW SMAW")
        assert result == "B15-CS-02-P1-GTAW/SMAW"

    def test_process_separator_already_slash(self):
        """GTAW/SMAW should stay GTAW/SMAW."""
        result = _normalize_wpq_number("B15-CS-02-P1-GTAW/SMAW")
        assert result == "B15-CS-02-P1-GTAW/SMAW"

    def test_mixed_separators(self):
        """Multiple separator issues in one string."""
        result = _normalize_wpq_number(" b-15=cs_03--p1- ")
        assert result == "B-15-CS-03-P1"

    def test_empty_string(self):
        assert _normalize_wpq_number("") == ""

    def test_triple_hyphens(self):
        assert _normalize_wpq_number("A---B") == "A-B"


class TestMigrateNormalizeWPQNumbers:
    """Test the WPQ normalization migration."""

    def _seed_wpq(self, conn, wpq_number, process="SMAW"):
        conn.execute(
            "INSERT INTO weld_welder_registry (employee_number, first_name, last_name, status) "
            "VALUES (?, 'Test', 'Welder', 'active')",
            (f"E-{wpq_number[:6]}",),
        )
        welder_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conn.execute(
            "INSERT INTO weld_wpq (wpq_number, welder_id, process_type, status) "
            "VALUES (?, ?, ?, 'active')",
            (wpq_number, welder_id, process),
        )
        conn.commit()

    def test_normalizes_underscores(self, memory_db):
        self._seed_wpq(memory_db, "B_15_CS_01")
        migrate_normalize_wpq_numbers(memory_db)

        row = memory_db.execute(
            "SELECT wpq_number FROM weld_wpq WHERE wpq_number = 'B-15-CS-01'"
        ).fetchone()
        assert row is not None

    def test_preserves_p8_p1(self, memory_db):
        self._seed_wpq(memory_db, "M03-DM-01-P8_P1-GTAW", process="GTAW")
        migrate_normalize_wpq_numbers(memory_db)

        row = memory_db.execute(
            "SELECT wpq_number FROM weld_wpq WHERE wpq_number LIKE '%P8_P1%'"
        ).fetchone()
        assert row is not None, "P8_P1 should be preserved"

    def test_idempotent(self, memory_db):
        self._seed_wpq(memory_db, "B_15_CS_01")
        migrate_normalize_wpq_numbers(memory_db)
        migrate_normalize_wpq_numbers(memory_db)

        count = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_wpq WHERE wpq_number = 'B-15-CS-01'"
        ).fetchone()["n"]
        assert count == 1

    def test_collision_logged_not_overwritten(self, memory_db):
        """Two raw values normalizing to the same string should not collide."""
        self._seed_wpq(memory_db, "B-15-CS-01")  # Already canonical
        self._seed_wpq(memory_db, "B_15_CS_01")  # Would normalize to same

        migrate_normalize_wpq_numbers(memory_db)

        # Both should still exist (the collision was skipped)
        count = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_wpq"
        ).fetchone()["n"]
        assert count == 2

    def test_empty_table(self, memory_db):
        """Should not error on empty table."""
        migrate_normalize_wpq_numbers(memory_db)

    def test_already_canonical_untouched(self, memory_db):
        self._seed_wpq(memory_db, "B15-CS-01-P1-SMAW")
        migrate_normalize_wpq_numbers(memory_db)

        row = memory_db.execute(
            "SELECT wpq_number FROM weld_wpq WHERE wpq_number = 'B15-CS-01-P1-SMAW'"
        ).fetchone()
        assert row is not None


class TestWPQCreationPathwayConsistency:
    """Test that all WPQ creation pathways produce consistent formats."""

    def test_registration_with_wps(self, mock_db):
        """Registration pathway should use stamp-wps format when WPS known."""
        mock_db.execute(
            "INSERT INTO weld_welder_registry (id, employee_number, first_name, last_name, "
            "welder_stamp, status) VALUES (1, 'E001', 'John', 'Baker', 'B15', 'active')"
        )
        mock_db.commit()

        result = add_initial_wpq(
            mock_db,
            welder_id=1,
            welder_stamp="B15",
            process_type="GTAW",
            wps_number="CS-03-P1-GTAW",
        )
        assert not result["errors"]
        assert result["wpq_number"] == "B15-CS-03-P1-GTAW"

    def test_registration_without_wps(self, mock_db):
        """Registration pathway should fall back to stamp-process when no WPS."""
        mock_db.execute(
            "INSERT INTO weld_welder_registry (id, employee_number, first_name, last_name, "
            "welder_stamp, status) VALUES (1, 'E001', 'John', 'Baker', 'B15', 'active')"
        )
        mock_db.commit()

        result = add_initial_wpq(
            mock_db,
            welder_id=1,
            welder_stamp="B15",
            process_type="SMAW",
        )
        assert not result["errors"]
        assert result["wpq_number"] == "B15-SMAW"
