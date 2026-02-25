"""
Tests for the quality issue import engine.

Covers: CSV parsing, field normalization, deduplication, dry-run mode,
header auto-mapping, date parsing, and error handling.
"""

import sqlite3
import pytest
from pathlib import Path

from qms.quality.import_engine import (
    import_quality_csv,
    _auto_map_headers,
    _parse_date,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_csv(tmp_path):
    """Write a minimal 3-row CSV file with standard Procore-like headers."""
    csv_file = tmp_path / "observations.csv"
    csv_file.write_text(
        "Title,Type,Description,Trade,Status,Location,Priority,Severity,Reported By,Due Date,ID\n"
        "Damaged insulation on duct,Safety,Found torn insulation on supply duct in Room 201,HVAC,Open,Building A Room 201,medium,medium,Brandon Johnson,2026-03-15,OBS-001\n"
        "Missing firestop at penetration,Quality,Pipe penetration through rated wall missing firestop,Plbg,Ready for Review,Building B Floor 2,high,high,Mike Smith,2026-03-20,OBS-002\n"
        "Exposed wiring in ceiling,Safety,Uncovered junction box in drop ceiling,Elec,In Progress,Building A Room 105,urgent,critical,Brandon Johnson,2026-03-10,OBS-003\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_with_dupes(tmp_path):
    """CSV with duplicate source_ids for dedup testing."""
    csv_file = tmp_path / "dupes.csv"
    csv_file.write_text(
        "Title,Type,Description,Trade,Status,ID\n"
        "Original issue,Safety,First version,Mech,Open,DUP-001\n"
        "Another issue,Quality,Different issue,Elec,Closed,DUP-002\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_updated(tmp_path):
    """CSV with same source_ids but updated fields."""
    csv_file = tmp_path / "updated.csv"
    csv_file.write_text(
        "Title,Type,Description,Trade,Status,ID\n"
        "Original issue UPDATED,Safety,Updated description,Mech,Closed,DUP-001\n"
        "Another issue UPDATED,Quality,Updated description,Elec,Open,DUP-002\n",
        encoding="utf-8",
    )
    return str(csv_file)


@pytest.fixture
def sample_csv_missing_title(tmp_path):
    """CSV with a row missing the title field."""
    csv_file = tmp_path / "missing_title.csv"
    csv_file.write_text(
        "Title,Type,Description,Trade,Status\n"
        "Good row,Safety,Has a title,Mech,Open\n"
        ",Quality,Missing title,Elec,Closed\n"
        "Another good row,Safety,Also has a title,Plbg,Open\n",
        encoding="utf-8",
    )
    return str(csv_file)


# ---------------------------------------------------------------------------
# Test: Header auto-mapping
# ---------------------------------------------------------------------------


class TestHeaderAutoMapping:
    def test_standard_headers(self):
        headers = ["Title", "Type", "Description", "Trade", "Status", "Location"]
        mapping = _auto_map_headers(headers)
        assert mapping["Title"] == "title"
        assert mapping["Type"] == "type"
        assert mapping["Description"] == "description"
        assert mapping["Trade"] == "trade"
        assert mapping["Status"] == "status"
        assert mapping["Location"] == "location"

    def test_procore_style_headers(self):
        headers = ["Observation Name", "Observation Type", "Body", "Responsible Contractor"]
        mapping = _auto_map_headers(headers)
        assert mapping.get("Observation Name") == "title"
        assert mapping.get("Observation Type") == "type"
        assert mapping.get("Body") == "description"
        assert mapping.get("Responsible Contractor") == "trade"

    def test_case_insensitive(self):
        headers = ["TITLE", "type", "Trade", "STATUS"]
        mapping = _auto_map_headers(headers)
        assert len(mapping) == 4

    def test_unmapped_headers_excluded(self):
        headers = ["Title", "Random Column", "Foo Bar"]
        mapping = _auto_map_headers(headers)
        assert "Title" in mapping
        assert "Random Column" not in mapping
        assert "Foo Bar" not in mapping

    def test_no_duplicate_canonicals(self):
        """If multiple headers map to same canonical, only first wins."""
        headers = ["Title", "Name", "Subject"]  # all map to "title"
        mapping = _auto_map_headers(headers)
        title_mappings = [k for k, v in mapping.items() if v == "title"]
        assert len(title_mappings) == 1


# ---------------------------------------------------------------------------
# Test: Date parsing
# ---------------------------------------------------------------------------


class TestDateParsing:
    def test_iso_date(self):
        assert _parse_date("2026-03-15") == "2026-03-15"

    def test_iso_datetime(self):
        assert _parse_date("2026-03-15T14:30:00Z") == "2026-03-15"

    def test_us_date(self):
        assert _parse_date("3/15/2026") == "2026-03-15"

    def test_us_date_padded(self):
        assert _parse_date("03/15/2026") == "2026-03-15"

    def test_us_date_short_year(self):
        assert _parse_date("3/15/26") == "2026-03-15"

    def test_empty_returns_none(self):
        assert _parse_date("") is None
        assert _parse_date("  ") is None

    def test_invalid_returns_none(self):
        assert _parse_date("not a date") is None

    def test_whitespace_stripped(self):
        assert _parse_date("  2026-03-15  ") == "2026-03-15"


# ---------------------------------------------------------------------------
# Test: Basic CSV import
# ---------------------------------------------------------------------------


class TestImportCSVBasic:
    def test_import_creates_rows(self, memory_db, seed_project, sample_csv):
        result = import_quality_csv(
            memory_db, sample_csv, project_id=seed_project, source="procore"
        )
        assert result["issues_created"] == 3
        assert result["issues_updated"] == 0
        assert result["issues_skipped"] == 0
        assert result["rows_total"] == 3

        count = memory_db.execute(
            "SELECT COUNT(*) as cnt FROM quality_issues"
        ).fetchone()["cnt"]
        assert count == 3

    def test_fields_mapped_correctly(self, memory_db, seed_project, sample_csv):
        import_quality_csv(
            memory_db, sample_csv, project_id=seed_project, source="procore"
        )
        row = memory_db.execute(
            "SELECT * FROM quality_issues WHERE source_id = 'OBS-001'"
        ).fetchone()

        assert row["title"] == "Damaged insulation on duct"
        assert row["description"] == "Found torn insulation on supply duct in Room 201"
        assert row["location"] == "Building A Room 201"
        assert row["priority"] == "medium"
        assert row["severity"] == "medium"
        assert row["reported_by"] == "Brandon Johnson"
        assert row["due_date"] == "2026-03-15"
        assert row["project_id"] == seed_project
        assert row["source"] == "procore"
        assert row["source_id"] == "OBS-001"

    def test_project_id_set(self, memory_db, seed_project, sample_csv):
        import_quality_csv(
            memory_db, sample_csv, project_id=seed_project
        )
        rows = memory_db.execute(
            "SELECT project_id FROM quality_issues"
        ).fetchall()
        assert all(r["project_id"] == seed_project for r in rows)


# ---------------------------------------------------------------------------
# Test: Normalization
# ---------------------------------------------------------------------------


class TestImportNormalization:
    def test_trade_normalized(self, memory_db, seed_project, sample_csv):
        import_quality_csv(memory_db, sample_csv, project_id=seed_project)

        row1 = memory_db.execute(
            "SELECT trade FROM quality_issues WHERE source_id = 'OBS-001'"
        ).fetchone()
        assert row1["trade"] == "Mechanical"  # HVAC → Mechanical

        row2 = memory_db.execute(
            "SELECT trade FROM quality_issues WHERE source_id = 'OBS-002'"
        ).fetchone()
        assert row2["trade"] == "Plumbing"  # Plbg → Plumbing

        row3 = memory_db.execute(
            "SELECT trade FROM quality_issues WHERE source_id = 'OBS-003'"
        ).fetchone()
        assert row3["trade"] == "Electrical"  # Elec → Electrical

    def test_status_normalized(self, memory_db, seed_project, sample_csv):
        import_quality_csv(memory_db, sample_csv, project_id=seed_project)

        row1 = memory_db.execute(
            "SELECT status FROM quality_issues WHERE source_id = 'OBS-001'"
        ).fetchone()
        assert row1["status"] == "open"  # Open → open

        row2 = memory_db.execute(
            "SELECT status FROM quality_issues WHERE source_id = 'OBS-002'"
        ).fetchone()
        assert row2["status"] == "in_review"  # Ready for Review → in_review

        row3 = memory_db.execute(
            "SELECT status FROM quality_issues WHERE source_id = 'OBS-003'"
        ).fetchone()
        assert row3["status"] == "in_progress"  # In Progress → in_progress

    def test_type_normalized(self, memory_db, seed_project, sample_csv):
        import_quality_csv(memory_db, sample_csv, project_id=seed_project)

        rows = memory_db.execute(
            "SELECT type FROM quality_issues ORDER BY source_id"
        ).fetchall()
        # Safety → observation, Quality → observation
        assert all(r["type"] == "observation" for r in rows)


# ---------------------------------------------------------------------------
# Test: Deduplication
# ---------------------------------------------------------------------------


class TestImportDedup:
    def test_second_import_updates_not_duplicates(
        self, memory_db, seed_project, sample_csv_with_dupes, sample_csv_updated
    ):
        # First import
        r1 = import_quality_csv(
            memory_db, sample_csv_with_dupes, project_id=seed_project
        )
        assert r1["issues_created"] == 2
        assert r1["issues_updated"] == 0

        # Second import with same source_ids
        r2 = import_quality_csv(
            memory_db, sample_csv_updated, project_id=seed_project
        )
        assert r2["issues_created"] == 0
        assert r2["issues_updated"] == 2

        # Still only 2 rows
        count = memory_db.execute(
            "SELECT COUNT(*) as cnt FROM quality_issues"
        ).fetchone()["cnt"]
        assert count == 2

    def test_updated_fields_reflect_new_values(
        self, memory_db, seed_project, sample_csv_with_dupes, sample_csv_updated
    ):
        import_quality_csv(memory_db, sample_csv_with_dupes, project_id=seed_project)
        import_quality_csv(memory_db, sample_csv_updated, project_id=seed_project)

        row = memory_db.execute(
            "SELECT title, status FROM quality_issues WHERE source_id = 'DUP-001'"
        ).fetchone()
        assert row["title"] == "Original issue UPDATED"
        assert row["status"] == "closed"


# ---------------------------------------------------------------------------
# Test: Dry-run mode
# ---------------------------------------------------------------------------


class TestImportDryRun:
    def test_dry_run_no_rows_written(self, memory_db, seed_project, sample_csv):
        result = import_quality_csv(
            memory_db, sample_csv, project_id=seed_project, dry_run=True
        )
        assert result["issues_created"] == 3
        assert result["rows_total"] == 3

        count = memory_db.execute(
            "SELECT COUNT(*) as cnt FROM quality_issues"
        ).fetchone()["cnt"]
        assert count == 0

    def test_dry_run_detects_updates(
        self, memory_db, seed_project, sample_csv_with_dupes, sample_csv_updated
    ):
        # Real import first
        import_quality_csv(memory_db, sample_csv_with_dupes, project_id=seed_project)

        # Dry run of updated CSV
        result = import_quality_csv(
            memory_db, sample_csv_updated, project_id=seed_project, dry_run=True
        )
        assert result["issues_updated"] == 2
        assert result["issues_created"] == 0


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------


class TestImportErrorHandling:
    def test_missing_title_skipped(self, memory_db, seed_project, sample_csv_missing_title):
        result = import_quality_csv(
            memory_db, sample_csv_missing_title, project_id=seed_project
        )
        assert result["issues_created"] == 2
        assert result["issues_skipped"] == 1
        assert len(result["skipped_details"]) == 1
        assert result["skipped_details"][0]["reason"] == "Missing title"

    def test_file_not_found(self, memory_db, seed_project):
        with pytest.raises(FileNotFoundError):
            import_quality_csv(
                memory_db, "/nonexistent/file.csv", project_id=seed_project
            )

    def test_no_title_column(self, memory_db, seed_project, tmp_path):
        csv_file = tmp_path / "no_title.csv"
        csv_file.write_text("Foo,Bar\nval1,val2\n")
        result = import_quality_csv(
            memory_db, str(csv_file), project_id=seed_project
        )
        assert len(result["errors"]) == 1
        assert "title" in result["errors"][0].lower()
