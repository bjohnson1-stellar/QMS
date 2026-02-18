"""
Integration tests for welding naming normalization.

End-to-end tests that verify the complete migration pipeline,
multi-pathway WPQ creation consistency, and cross-reference integrity.
"""

import pytest
from qms.welding.migrations import (
    run_welding_migrations,
    _normalize_wpq_number,
    WPS_CORRECTIONS,
    _KNOWN_PQRS,
    _WPS_PQR_MAP,
)
from qms.welding.registration import (
    get_next_stamp,
    register_new_welder,
    add_initial_wpq,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_full_wps_set(conn):
    """Seed all WPS records used in the migration (pre-correction names)."""
    wps_records = [
        "CS-01-P1-SMAW",
        "CS-02",           # Will be corrected
        "CS-03-P1-",       # Will be corrected
        "CS-04-P1-",       # Will be corrected
        "CS-05",           # Will be corrected
        "DM-01-P8_P1-",   # Will be corrected
        "SS-01-P8-GTAW",
        "SS-02-P8-",       # Ambiguous — left alone
        "SS-03-P8-",       # Unknown — left alone
    ]
    for wps in wps_records:
        conn.execute(
            "INSERT OR IGNORE INTO weld_wps (wps_number, revision, status) "
            "VALUES (?, '0', 'active')",
            (wps,),
        )
    conn.commit()


def _seed_welder(conn, employee_number, first_name, last_name, stamp=None):
    """Seed a welder, optionally with a specific stamp."""
    conn.execute(
        "INSERT INTO weld_welder_registry "
        "(employee_number, first_name, last_name, welder_stamp, status) "
        "VALUES (?, ?, ?, ?, 'active')",
        (employee_number, first_name, last_name, stamp),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM weld_welder_registry WHERE employee_number = ?",
        (employee_number,),
    ).fetchone()["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEndToEndMigration:
    """Test the complete migration pipeline from raw → migrated → verified."""

    def test_full_pipeline(self, memory_db):
        """Run all migrations with realistic seed data and verify final state."""
        _seed_full_wps_set(memory_db)

        # Add a WPQ referencing an old WPS name (should be cascaded)
        welder_id = _seed_welder(memory_db, "E001", "John", "Baker", "B-15")
        memory_db.execute(
            "INSERT INTO weld_wpq (wpq_number, welder_id, wps_number, process_type, status) "
            "VALUES ('B-15-CS-02', ?, 'CS-02', 'GTAW/SMAW', 'active')",
            (welder_id,),
        )
        memory_db.commit()

        # Run full migration
        run_welding_migrations(memory_db)

        # Verify WPS corrections
        for old, new in WPS_CORRECTIONS.items():
            old_row = memory_db.execute(
                "SELECT id FROM weld_wps WHERE wps_number = ?", (old,)
            ).fetchone()
            assert old_row is None, f"Old WPS '{old}' should be corrected"

            new_row = memory_db.execute(
                "SELECT id FROM weld_wps WHERE wps_number = ?", (new,)
            ).fetchone()
            assert new_row is not None, f"Corrected WPS '{new}' should exist"

        # Verify WPQ cascade
        wpq = memory_db.execute(
            "SELECT wps_number FROM weld_wpq WHERE welder_id = ?", (welder_id,)
        ).fetchone()
        assert wpq["wps_number"] == "CS-02-P1-GTAW/SMAW"

        # Verify PQR import
        pqr_count = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_pqr"
        ).fetchone()["n"]
        assert pqr_count == len(_KNOWN_PQRS)

        # Verify WPS-PQR links
        link_count = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_wps_pqr_links"
        ).fetchone()["n"]
        expected_links = sum(len(v) for v in _WPS_PQR_MAP.values())
        assert link_count == expected_links

        # Verify ambiguous WPS left alone
        ss02 = memory_db.execute(
            "SELECT wps_number FROM weld_wps WHERE wps_number = 'SS-02-P8-'"
        ).fetchone()
        assert ss02 is not None

    def test_idempotent_full_pipeline(self, memory_db):
        """Running the full migration twice should produce identical results."""
        _seed_full_wps_set(memory_db)

        run_welding_migrations(memory_db)
        first_wps = memory_db.execute(
            "SELECT wps_number FROM weld_wps ORDER BY wps_number"
        ).fetchall()
        first_pqr = memory_db.execute(
            "SELECT pqr_number FROM weld_pqr ORDER BY pqr_number"
        ).fetchall()
        first_links = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_wps_pqr_links"
        ).fetchone()["n"]

        run_welding_migrations(memory_db)
        second_wps = memory_db.execute(
            "SELECT wps_number FROM weld_wps ORDER BY wps_number"
        ).fetchall()
        second_pqr = memory_db.execute(
            "SELECT pqr_number FROM weld_pqr ORDER BY pqr_number"
        ).fetchall()
        second_links = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_wps_pqr_links"
        ).fetchone()["n"]

        assert [r["wps_number"] for r in first_wps] == [r["wps_number"] for r in second_wps]
        assert [r["pqr_number"] for r in first_pqr] == [r["pqr_number"] for r in second_pqr]
        assert first_links == second_links


class TestWPQPathwayConsistency:
    """Test that all 3 WPQ creation pathways produce consistent formats."""

    def test_registration_pathway(self, mock_db):
        """Pathway 2: Registration creates {stamp}-{wps_number}."""
        welder_id = _seed_welder(mock_db, "E100", "John", "Martinez", "M01")

        result = add_initial_wpq(
            mock_db,
            welder_id=welder_id,
            welder_stamp="M01",
            process_type="GTAW",
            wps_number="CS-03-P1-GTAW",
        )
        assert not result["errors"]
        assert result["wpq_number"] == "M01-CS-03-P1-GTAW"

    def test_registration_fallback(self, mock_db):
        """Without WPS, registration falls back to {stamp}-{process}."""
        welder_id = _seed_welder(mock_db, "E100", "John", "Martinez", "M01")

        result = add_initial_wpq(
            mock_db,
            welder_id=welder_id,
            welder_stamp="M01",
            process_type="SMAW",
        )
        assert not result["errors"]
        assert result["wpq_number"] == "M01-SMAW"

    def test_all_pathways_normalizable(self):
        """All expected WPQ formats should survive normalization unchanged."""
        expected_formats = [
            "M01-CS-03-P1-GTAW",              # Registration with WPS
            "M01-SMAW",                         # Registration without WPS
            "B15-CS-01-P1-SMAW",               # Import with WPS
            "B15-ORIG-CODE",                    # Import fallback
            "J03-WCR-001-C1-GTAW",             # Cert request fallback
        ]
        for fmt in expected_formats:
            normalized = _normalize_wpq_number(fmt)
            assert normalized == fmt, f"'{fmt}' changed to '{normalized}'"


class TestStampGenerationIntegration:
    """Test stamp generation with realistic scenarios."""

    def test_multiple_same_initial(self, memory_db):
        """Multiple welders with same last initial get sequential stamps."""
        welders = [
            ("E001", "Bob", "Baker"),
            ("E002", "Bill", "Brown"),
            ("E003", "Beth", "Barnes"),
        ]
        stamps = []
        for emp, first, last in welders:
            stamp = get_next_stamp(memory_db, last_name=last)
            memory_db.execute(
                "INSERT INTO weld_welder_registry "
                "(employee_number, first_name, last_name, welder_stamp, status) "
                "VALUES (?, ?, ?, ?, 'active')",
                (emp, first, last, stamp),
            )
            memory_db.commit()
            stamps.append(stamp)

        assert stamps == ["B01", "B02", "B03"]

    def test_mixed_initials(self, memory_db):
        """Different last initials should have independent sequences."""
        pairs = [
            ("E001", "Alice", "Adams"),   # A01
            ("E002", "Bob", "Baker"),     # B01
            ("E003", "Amy", "Anderson"),  # A02
            ("E004", "Bill", "Brown"),    # B02
        ]
        stamps = []
        for emp, first, last in pairs:
            stamp = get_next_stamp(memory_db, last_name=last)
            memory_db.execute(
                "INSERT INTO weld_welder_registry "
                "(employee_number, first_name, last_name, welder_stamp, status) "
                "VALUES (?, ?, ?, ?, 'active')",
                (emp, first, last, stamp),
            )
            memory_db.commit()
            stamps.append(stamp)

        assert stamps == ["A01", "B01", "A02", "B02"]

    def test_register_new_welder_auto_stamp(self, mock_db):
        """register_new_welder with auto_stamp should use last initial."""
        result = register_new_welder(
            mock_db,
            employee_number="E500",
            first_name="Carlos",
            last_name="Garcia",
            auto_stamp=True,
        )
        assert not result["errors"]
        assert result["stamp"] == "G01"

    def test_legacy_stamps_respected(self, memory_db):
        """New stamps should continue after existing legacy B-15 format."""
        # Seed legacy stamps
        for i, emp in enumerate(["E001", "E002", "E003"], start=1):
            memory_db.execute(
                "INSERT INTO weld_welder_registry "
                "(employee_number, first_name, last_name, welder_stamp, status) "
                "VALUES (?, 'Test', 'Baker', ?, 'active')",
                (emp, f"B-{i}"),
            )
        memory_db.commit()

        stamp = get_next_stamp(memory_db, last_name="Brown")
        assert stamp == "B04"  # Continues after B-3


class TestPQRCrossReferenceRoundTrip:
    """Test PQR cross-reference data integrity."""

    def test_wps_to_pqr_lookup(self, memory_db):
        """Can look up supporting PQRs for a given WPS."""
        _seed_full_wps_set(memory_db)
        run_welding_migrations(memory_db)

        # CS-02-P1-GTAW/SMAW should have 2 supporting PQRs
        links = memory_db.execute("""
            SELECT l.pqr_number
            FROM weld_wps_pqr_links l
            JOIN weld_wps w ON w.id = l.wps_id
            WHERE w.wps_number = 'CS-02-P1-GTAW/SMAW'
            ORDER BY l.pqr_number
        """).fetchall()

        pqr_numbers = [r["pqr_number"] for r in links]
        assert pqr_numbers == [
            "A106-NPS2-6G-ER70S-7018",
            "A106-NPS6-6G-ER70S-7018",
        ]

    def test_pqr_to_wps_reverse_lookup(self, memory_db):
        """Can look up which WPS a PQR supports."""
        _seed_full_wps_set(memory_db)
        run_welding_migrations(memory_db)

        # PQR 1-6G-12 should support DM-01-P8_P1-GTAW
        link = memory_db.execute("""
            SELECT w.wps_number
            FROM weld_wps_pqr_links l
            JOIN weld_wps w ON w.id = l.wps_id
            WHERE l.pqr_number = '1-6G-12'
        """).fetchone()
        assert link is not None
        assert link["wps_number"] == "DM-01-P8_P1-GTAW"

    def test_pqr_links_have_ids(self, memory_db):
        """Links should resolve both wps_id and pqr_id when records exist."""
        _seed_full_wps_set(memory_db)
        run_welding_migrations(memory_db)

        nulls = memory_db.execute("""
            SELECT COUNT(*) AS n FROM weld_wps_pqr_links
            WHERE pqr_id IS NULL
        """).fetchone()["n"]
        # All PQRs are imported, so all links should have pqr_id
        assert nulls == 0


class TestNormalizationIdempotency:
    """Test that normalization is idempotent — running twice changes nothing."""

    def test_normalize_function_idempotent(self):
        """Applying normalization twice should produce the same result."""
        test_values = [
            "B_15_CS_01",
            "  b-15=cs=03--p1-  ",
            "M03-DM-01-P8_P1-GTAW",
            "B15-CS-02-P1-GTAW_SMAW",
            "ALREADY-CANONICAL",
        ]
        for raw in test_values:
            first = _normalize_wpq_number(raw)
            second = _normalize_wpq_number(first)
            assert first == second, f"Not idempotent: '{raw}' → '{first}' → '{second}'"

    def test_migration_idempotent(self, memory_db):
        """Running WPQ normalization migration twice should not change data."""
        # Seed a WPQ with a dirty number
        memory_db.execute(
            "INSERT INTO weld_welder_registry "
            "(employee_number, first_name, last_name, status) "
            "VALUES ('E001', 'Test', 'User', 'active')"
        )
        welder_id = memory_db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        memory_db.execute(
            "INSERT INTO weld_wpq (wpq_number, welder_id, process_type, status) "
            "VALUES ('B_15_CS_01', ?, 'SMAW', 'active')",
            (welder_id,),
        )
        memory_db.commit()

        run_welding_migrations(memory_db)
        wpq_after_first = memory_db.execute(
            "SELECT wpq_number FROM weld_wpq WHERE welder_id = ?",
            (welder_id,),
        ).fetchone()["wpq_number"]

        run_welding_migrations(memory_db)
        wpq_after_second = memory_db.execute(
            "SELECT wpq_number FROM weld_wpq WHERE welder_id = ?",
            (welder_id,),
        ).fetchone()["wpq_number"]

        assert wpq_after_first == wpq_after_second == "B-15-CS-01"
