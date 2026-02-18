"""Tests for welding module migrations."""

import pytest
from qms.welding.migrations import (
    migrate_fix_wps_numbers,
    migrate_import_known_pqrs,
    migrate_populate_wps_pqr_links,
    run_welding_migrations,
    WPS_CORRECTIONS,
    _WPS_CASCADE_TABLES,
    _KNOWN_PQRS,
    _WPS_PQR_MAP,
)


class TestWPSCorrections:
    """Test WPS number correction migration."""

    def _seed_wps(self, conn, wps_number, revision="0"):
        conn.execute(
            "INSERT INTO weld_wps (wps_number, revision, status) VALUES (?, ?, 'active')",
            (wps_number, revision),
        )
        conn.commit()
        return conn.execute(
            "SELECT id FROM weld_wps WHERE wps_number = ?", (wps_number,)
        ).fetchone()["id"]

    def test_corrections_applied(self, memory_db):
        """All truncated WPS numbers should be corrected."""
        for old_number in WPS_CORRECTIONS:
            self._seed_wps(memory_db, old_number)

        migrate_fix_wps_numbers(memory_db)

        for old_number, new_number in WPS_CORRECTIONS.items():
            # Old should be gone
            old = memory_db.execute(
                "SELECT id FROM weld_wps WHERE wps_number = ?", (old_number,)
            ).fetchone()
            assert old is None, f"Old WPS '{old_number}' still exists"

            # New should exist
            new = memory_db.execute(
                "SELECT id FROM weld_wps WHERE wps_number = ?", (new_number,)
            ).fetchone()
            assert new is not None, f"Corrected WPS '{new_number}' not found"

    def test_idempotent(self, memory_db):
        """Running corrections twice should not error or duplicate."""
        for old_number in WPS_CORRECTIONS:
            self._seed_wps(memory_db, old_number)

        migrate_fix_wps_numbers(memory_db)
        migrate_fix_wps_numbers(memory_db)  # Second run should be no-op

        for new_number in WPS_CORRECTIONS.values():
            count = memory_db.execute(
                "SELECT COUNT(*) AS n FROM weld_wps WHERE wps_number = ?",
                (new_number,),
            ).fetchone()["n"]
            assert count == 1, f"Expected 1 row for '{new_number}', got {count}"

    def test_cascade_to_wpq(self, memory_db):
        """WPS rename should cascade to weld_wpq records."""
        old = "CS-03-P1-"
        new = WPS_CORRECTIONS[old]

        wps_id = self._seed_wps(memory_db, old)

        # Seed a welder and WPQ referencing the old WPS number
        memory_db.execute(
            "INSERT INTO weld_welder_registry (employee_number, first_name, last_name, status) "
            "VALUES ('E001', 'Test', 'Welder', 'active')"
        )
        welder_id = memory_db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        memory_db.execute(
            "INSERT INTO weld_wpq (wpq_number, welder_id, wps_number, process_type, "
            "test_date, status) VALUES (?, ?, ?, 'GTAW', '2025-01-01', 'active')",
            (f"B15-{old}", welder_id, old),
        )
        memory_db.commit()

        migrate_fix_wps_numbers(memory_db)

        # WPQ should now reference the corrected WPS number
        wpq = memory_db.execute(
            "SELECT wps_number FROM weld_wpq WHERE welder_id = ?", (welder_id,)
        ).fetchone()
        assert wpq["wps_number"] == new

    def test_cascade_to_pqr(self, memory_db):
        """WPS rename should cascade to weld_pqr records."""
        old = "DM-01-P8_P1-"
        new = WPS_CORRECTIONS[old]

        self._seed_wps(memory_db, old)
        memory_db.execute(
            "INSERT INTO weld_pqr (pqr_number, wps_number, status) "
            "VALUES ('PQR-DM-01', ?, 'active')",
            (old,),
        )
        memory_db.commit()

        migrate_fix_wps_numbers(memory_db)

        pqr = memory_db.execute(
            "SELECT wps_number FROM weld_pqr WHERE pqr_number = 'PQR-DM-01'"
        ).fetchone()
        assert pqr["wps_number"] == new

    def test_cascade_to_cert_coupons(self, memory_db):
        """WPS rename should cascade to cert request coupons."""
        old = "CS-02"
        new = WPS_CORRECTIONS[old]

        self._seed_wps(memory_db, old)

        # Need a welder + cert request for FK
        memory_db.execute(
            "INSERT INTO weld_welder_registry (id, employee_number, first_name, last_name, status) "
            "VALUES (1, 'E001', 'Test', 'Welder', 'active')"
        )
        memory_db.execute(
            "INSERT INTO weld_cert_requests (wcr_number, welder_id, status) "
            "VALUES ('WCR-001', 1, 'pending_approval')"
        )
        wcr_id = memory_db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        memory_db.execute(
            "INSERT INTO weld_cert_request_coupons (wcr_id, coupon_number, process, wps_number, status) "
            "VALUES (?, 1, 'GTAW/SMAW', ?, 'pending')",
            (wcr_id, old),
        )
        memory_db.commit()

        migrate_fix_wps_numbers(memory_db)

        coupon = memory_db.execute(
            "SELECT wps_number FROM weld_cert_request_coupons WHERE wcr_id = ?",
            (wcr_id,),
        ).fetchone()
        assert coupon["wps_number"] == new

    def test_skip_if_target_exists(self, memory_db):
        """Should skip correction if target WPS number already exists."""
        old = "CS-03-P1-"
        new = WPS_CORRECTIONS[old]

        # Both old and new exist — should NOT overwrite
        self._seed_wps(memory_db, old)
        self._seed_wps(memory_db, new)

        migrate_fix_wps_numbers(memory_db)

        # Both should still exist (old wasn't overwritten)
        count = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_wps WHERE wps_number IN (?, ?)",
            (old, new),
        ).fetchone()["n"]
        assert count == 2

    def test_ss02_flagged_not_fixed(self, memory_db):
        """SS-02-P8- entries should be flagged, not auto-corrected."""
        self._seed_wps(memory_db, "SS-02-P8-")
        self._seed_wps(memory_db, "SS-02-P8-2")  # Second variant to avoid UNIQUE

        # Actually insert two rows with same number — need to work around UNIQUE
        # Just verify that a single SS-02-P8- is left untouched
        migrate_fix_wps_numbers(memory_db)

        row = memory_db.execute(
            "SELECT wps_number FROM weld_wps WHERE wps_number = 'SS-02-P8-'"
        ).fetchone()
        assert row is not None, "SS-02-P8- should NOT be auto-corrected"

    def test_ss03_left_as_is(self, memory_db):
        """SS-03-P8- should be left untouched."""
        self._seed_wps(memory_db, "SS-03-P8-")

        migrate_fix_wps_numbers(memory_db)

        row = memory_db.execute(
            "SELECT wps_number FROM weld_wps WHERE wps_number = 'SS-03-P8-'"
        ).fetchone()
        assert row is not None, "SS-03-P8- should be left as-is"

    def test_no_wps_table(self, memory_db):
        """Should silently return if weld_wps doesn't exist."""
        memory_db.execute("DROP TABLE IF EXISTS weld_wps_pqr_links")
        memory_db.execute("DROP TABLE IF EXISTS weld_wpq")
        memory_db.execute("DROP TABLE IF EXISTS weld_pqr")
        memory_db.execute("DROP TABLE IF EXISTS weld_wps")
        memory_db.commit()

        # Should not raise
        migrate_fix_wps_numbers(memory_db)


class TestPQRImport:
    """Test PQR record import migration."""

    def test_import_count(self, memory_db):
        """Should import all known PQR records."""
        migrate_import_known_pqrs(memory_db)

        count = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_pqr"
        ).fetchone()["n"]
        assert count == len(_KNOWN_PQRS)

    def test_idempotent(self, memory_db):
        """Running import twice should not duplicate records."""
        migrate_import_known_pqrs(memory_db)
        migrate_import_known_pqrs(memory_db)

        count = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_pqr"
        ).fetchone()["n"]
        assert count == len(_KNOWN_PQRS)

    def test_legacy_generic_pqr(self, memory_db):
        """Legacy generic PQR numbers should be importable."""
        migrate_import_known_pqrs(memory_db)

        row = memory_db.execute(
            "SELECT * FROM weld_pqr WHERE pqr_number = '1-6G-12'"
        ).fetchone()
        assert row is not None
        assert row["wps_number"] == "DM-01-P8_P1-GTAW"
        assert row["status"] == "active"

    def test_legacy_descriptive_pqr(self, memory_db):
        """Legacy descriptive PQR numbers should be importable."""
        migrate_import_known_pqrs(memory_db)

        row = memory_db.execute(
            "SELECT * FROM weld_pqr WHERE pqr_number = 'A106-NPS2-6G-ER70S-7018'"
        ).fetchone()
        assert row is not None
        assert row["wps_number"] == "CS-02-P1-GTAW/SMAW"

    def test_new_format_pqr(self, memory_db):
        """New-format PQRs should be importable."""
        migrate_import_known_pqrs(memory_db)

        row = memory_db.execute(
            "SELECT * FROM weld_pqr WHERE pqr_number = 'CS-03-P1-GTAW'"
        ).fetchone()
        assert row is not None

    def test_skips_existing(self, memory_db):
        """Should not overwrite a PQR that already exists."""
        memory_db.execute(
            "INSERT INTO weld_pqr (pqr_number, status, notes) "
            "VALUES ('1-6G-12', 'active', 'Pre-existing record')"
        )
        memory_db.commit()

        migrate_import_known_pqrs(memory_db)

        row = memory_db.execute(
            "SELECT notes FROM weld_pqr WHERE pqr_number = '1-6G-12'"
        ).fetchone()
        assert row["notes"] == "Pre-existing record"


class TestWPSPQRLinks:
    """Test WPS-PQR cross-reference link population."""

    def _seed_wps_and_pqrs(self, conn):
        """Seed all WPS and PQR records needed for linking."""
        # Seed WPS records (corrected names)
        for wps_number in _WPS_PQR_MAP:
            conn.execute(
                "INSERT OR IGNORE INTO weld_wps (wps_number, revision, status) "
                "VALUES (?, '0', 'active')",
                (wps_number,),
            )
        # Seed PQR records
        migrate_import_known_pqrs(conn)
        conn.commit()

    def test_links_created(self, memory_db):
        """Should create all expected links."""
        self._seed_wps_and_pqrs(memory_db)
        migrate_populate_wps_pqr_links(memory_db)

        total_expected = sum(len(pqrs) for pqrs in _WPS_PQR_MAP.values())
        count = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_wps_pqr_links"
        ).fetchone()["n"]
        assert count == total_expected

    def test_idempotent(self, memory_db):
        """Running link population twice should not duplicate."""
        self._seed_wps_and_pqrs(memory_db)
        migrate_populate_wps_pqr_links(memory_db)
        migrate_populate_wps_pqr_links(memory_db)

        total_expected = sum(len(pqrs) for pqrs in _WPS_PQR_MAP.values())
        count = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_wps_pqr_links"
        ).fetchone()["n"]
        assert count == total_expected

    def test_link_resolves_ids(self, memory_db):
        """Links should have both wps_id and pqr_id when both records exist."""
        self._seed_wps_and_pqrs(memory_db)
        migrate_populate_wps_pqr_links(memory_db)

        # Check a specific link: CS-03-P1-GTAW → CS-03-P1-GTAW
        link = memory_db.execute("""
            SELECT l.wps_id, l.pqr_id, l.pqr_number
            FROM weld_wps_pqr_links l
            JOIN weld_wps w ON w.id = l.wps_id
            WHERE w.wps_number = 'CS-03-P1-GTAW'
        """).fetchone()
        assert link is not None
        assert link["pqr_number"] == "CS-03-P1-GTAW"
        assert link["pqr_id"] is not None

    def test_link_without_pqr_record(self, memory_db):
        """Should create link with NULL pqr_id when PQR not in database."""
        # Seed only WPS, no PQRs
        for wps_number in _WPS_PQR_MAP:
            memory_db.execute(
                "INSERT OR IGNORE INTO weld_wps (wps_number, revision, status) "
                "VALUES (?, '0', 'active')",
                (wps_number,),
            )
        memory_db.commit()

        migrate_populate_wps_pqr_links(memory_db)

        link = memory_db.execute("""
            SELECT pqr_id, pqr_number FROM weld_wps_pqr_links LIMIT 1
        """).fetchone()
        assert link is not None
        assert link["pqr_id"] is None  # PQR not in DB yet
        assert link["pqr_number"] is not None  # But text reference preserved

    def test_skips_missing_wps(self, memory_db):
        """Should skip links when WPS record doesn't exist."""
        # Don't seed any WPS records
        migrate_import_known_pqrs(memory_db)
        migrate_populate_wps_pqr_links(memory_db)

        count = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_wps_pqr_links"
        ).fetchone()["n"]
        assert count == 0


class TestRunWeldingMigrations:
    """Test the migration runner."""

    def test_runner_calls_all(self, memory_db):
        """run_welding_migrations should complete without error."""
        # Seed a correctable WPS to verify it runs
        memory_db.execute(
            "INSERT INTO weld_wps (wps_number, revision, status) "
            "VALUES ('CS-05', '0', 'active')"
        )
        memory_db.commit()

        run_welding_migrations(memory_db)

        row = memory_db.execute(
            "SELECT wps_number FROM weld_wps WHERE wps_number = ?",
            ("CS-05-P1-GTAW/SMAW-Low Temp",),
        ).fetchone()
        assert row is not None

    def test_runner_imports_pqrs(self, memory_db):
        """Runner should import PQR records."""
        run_welding_migrations(memory_db)

        count = memory_db.execute(
            "SELECT COUNT(*) AS n FROM weld_pqr"
        ).fetchone()["n"]
        assert count == len(_KNOWN_PQRS)
