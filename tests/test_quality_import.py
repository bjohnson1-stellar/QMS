"""
Tests for the quality issue import engine.

Covers: CSV parsing, field normalization, deduplication, dry-run mode,
header auto-mapping, date parsing, error handling, batch import,
and project resolution from filenames.
"""

import sqlite3
import pytest
from pathlib import Path

from qms.quality.import_engine import (
    import_quality_csv,
    import_batch,
    resolve_project_from_filename,
    _auto_map_headers,
    _filename_from_url,
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


# ---------------------------------------------------------------------------
# Fixtures: Batch import
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_two_projects(memory_db):
    """Insert two projects for batch import testing. Returns (id1, id2)."""
    memory_db.execute(
        "INSERT INTO projects (id, number, name, status) VALUES (10, '07645', 'Cold Storage Alpha', 'active')"
    )
    memory_db.execute(
        "INSERT INTO projects (id, number, name, status) VALUES (11, '07587', 'Cold Storage Beta', 'active')"
    )
    memory_db.commit()
    return (10, 11)


@pytest.fixture
def batch_csv_dir(tmp_path):
    """Create a directory with 2 CSVs named with project numbers."""
    csv1 = tmp_path / "07645 - Observations.csv"
    csv1.write_text(
        "Title,Type,Status,ID\n"
        "Cracked weld on beam,Safety,Open,OBS-101\n"
        "Missing insulation,Quality,Open,OBS-102\n",
        encoding="utf-8",
    )

    csv2 = tmp_path / "07587 - Observations.csv"
    csv2.write_text(
        "Title,Type,Status,ID\n"
        "Pipe support missing,Quality,Open,OBS-201\n",
        encoding="utf-8",
    )
    return str(tmp_path)


# ---------------------------------------------------------------------------
# Test: Project resolution from filename
# ---------------------------------------------------------------------------


class TestResolveProjectFromFilename:
    def test_standard_pattern(self, memory_db, seed_two_projects):
        result = resolve_project_from_filename(memory_db, "07645 - Observations.csv")
        assert result == (10, "07645")

    def test_underscore_pattern(self, memory_db, seed_two_projects):
        result = resolve_project_from_filename(memory_db, "Observations_07587.csv")
        assert result == (11, "07587")

    def test_bare_number(self, memory_db, seed_two_projects):
        result = resolve_project_from_filename(memory_db, "07645.csv")
        assert result == (10, "07645")

    def test_no_match(self, memory_db, seed_two_projects):
        result = resolve_project_from_filename(memory_db, "random.csv")
        assert result is None

    def test_number_not_in_db(self, memory_db, seed_two_projects):
        result = resolve_project_from_filename(memory_db, "99999 - Observations.csv")
        assert result is None


# ---------------------------------------------------------------------------
# Test: Batch import
# ---------------------------------------------------------------------------


class TestImportBatch:
    def test_batch_multiple_files(self, memory_db, seed_two_projects, batch_csv_dir):
        result = import_batch(memory_db, batch_csv_dir)
        assert result["files_processed"] == 2
        assert result["files_skipped"] == 0
        assert result["total_created"] == 3  # 2 + 1
        assert len(result["per_file"]) == 2

    def test_batch_with_explicit_project(self, memory_db, seed_two_projects, batch_csv_dir):
        result = import_batch(memory_db, batch_csv_dir, project_number="07645")
        assert result["files_processed"] == 2
        # All 3 rows go to project 07645
        assert result["total_created"] == 3
        for pf in result["per_file"]:
            assert pf["project"] == "07645"

    def test_batch_unresolved_skipped(self, memory_db, seed_two_projects, tmp_path):
        csv_file = tmp_path / "unknown_file.csv"
        csv_file.write_text(
            "Title,Type,Status\nSome issue,Safety,Open\n",
            encoding="utf-8",
        )
        result = import_batch(memory_db, str(tmp_path))
        assert result["files_processed"] == 0
        assert result["files_skipped"] == 1
        assert len(result["unresolved"]) == 1
        assert result["unresolved"][0]["file"] == "unknown_file.csv"

    def test_batch_dry_run(self, memory_db, seed_two_projects, batch_csv_dir):
        result = import_batch(memory_db, batch_csv_dir, dry_run=True)
        assert result["total_created"] == 3
        # Verify nothing actually in DB
        count = memory_db.execute(
            "SELECT COUNT(*) as cnt FROM quality_issues"
        ).fetchone()["cnt"]
        assert count == 0

    def test_batch_empty_directory(self, memory_db, seed_two_projects, tmp_path):
        result = import_batch(memory_db, str(tmp_path))
        assert result["files_processed"] == 0

    def test_batch_not_a_directory(self, memory_db, seed_two_projects, tmp_path):
        fake = tmp_path / "not_a_dir.txt"
        fake.write_text("hi")
        with pytest.raises(NotADirectoryError):
            import_batch(memory_db, str(fake))


# ---------------------------------------------------------------------------
# Fixtures: Attachment import
# ---------------------------------------------------------------------------


@pytest.fixture
def csv_with_attachments(tmp_path):
    """CSV with an Attachments column containing URLs."""
    csv_file = tmp_path / "with_photos.csv"
    csv_file.write_text(
        "Title,Type,Status,ID,Attachments\n"
        "Cracked pipe,Safety,Open,ATT-001,https://example.com/photos/IMG_001.jpg\n"
        'Missing label,Quality,Open,ATT-002,https://example.com/photos/IMG_002.jpg;https://example.com/photos/IMG_003.png\n'
        "No photo issue,Quality,Open,ATT-003,\n",
        encoding="utf-8",
    )
    return str(csv_file)


# ---------------------------------------------------------------------------
# Test: Attachment import
# ---------------------------------------------------------------------------


class TestAttachmentImport:
    def test_single_attachment_url(self, memory_db, seed_project, csv_with_attachments):
        result = import_quality_csv(
            memory_db, csv_with_attachments, project_id=seed_project
        )
        assert result["issues_created"] == 3
        assert result["attachments_recorded"] >= 1

        # Check ATT-001 has exactly 1 attachment
        issue = memory_db.execute(
            "SELECT id FROM quality_issues WHERE source_id = 'ATT-001'"
        ).fetchone()
        attachments = memory_db.execute(
            "SELECT * FROM quality_issue_attachments WHERE issue_id = ?",
            (issue["id"],),
        ).fetchall()
        assert len(attachments) == 1
        assert attachments[0]["source_url"] == "https://example.com/photos/IMG_001.jpg"
        assert attachments[0]["filename"] == "IMG_001.jpg"
        assert attachments[0]["file_type"] == "image"

    def test_multiple_attachment_urls(self, memory_db, seed_project, csv_with_attachments):
        import_quality_csv(
            memory_db, csv_with_attachments, project_id=seed_project
        )
        issue = memory_db.execute(
            "SELECT id FROM quality_issues WHERE source_id = 'ATT-002'"
        ).fetchone()
        attachments = memory_db.execute(
            "SELECT * FROM quality_issue_attachments WHERE issue_id = ? ORDER BY id",
            (issue["id"],),
        ).fetchall()
        assert len(attachments) == 2
        assert attachments[0]["source_url"] == "https://example.com/photos/IMG_002.jpg"
        assert attachments[1]["source_url"] == "https://example.com/photos/IMG_003.png"

    def test_no_attachment_column(self, memory_db, seed_project, sample_csv):
        """Existing CSV without attachment column works fine."""
        result = import_quality_csv(
            memory_db, sample_csv, project_id=seed_project
        )
        assert result["issues_created"] == 3
        assert result["attachments_recorded"] == 0

        count = memory_db.execute(
            "SELECT COUNT(*) as cnt FROM quality_issue_attachments"
        ).fetchone()["cnt"]
        assert count == 0

    def test_empty_attachment_field(self, memory_db, seed_project, csv_with_attachments):
        import_quality_csv(
            memory_db, csv_with_attachments, project_id=seed_project
        )
        # ATT-003 has empty attachment field
        issue = memory_db.execute(
            "SELECT id FROM quality_issues WHERE source_id = 'ATT-003'"
        ).fetchone()
        attachments = memory_db.execute(
            "SELECT * FROM quality_issue_attachments WHERE issue_id = ?",
            (issue["id"],),
        ).fetchall()
        assert len(attachments) == 0

    def test_attachment_filename_from_url(self):
        assert _filename_from_url("https://example.com/photos/IMG_001.jpg", 1) == "IMG_001.jpg"
        assert _filename_from_url("https://cdn.procore.com/uploads/photo.png", 1) == "photo.png"
        assert _filename_from_url("https://example.com/", 3) == "attachment_3.jpg"
        assert _filename_from_url("not-a-url", 2) == "attachment_2.jpg"


# ---------------------------------------------------------------------------
# Test: Quality issues vector indexer
# ---------------------------------------------------------------------------


class TestIndexQualityIssues:
    def test_index_function_importable(self):
        from qms.vectordb.indexer import index_quality_issues
        assert callable(index_quality_issues)

    def test_index_in_module_exports(self):
        from qms.vectordb import index_quality_issues
        assert callable(index_quality_issues)
