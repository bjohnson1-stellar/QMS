"""
Tests for the mobile capture processing engine.

Covers: folder scanning, Claude vision analysis (mocked), quality issue
creation, attachment handling, capture_log tracking, dry-run mode,
duplicate skipping, voice note transcription, transcript analysis,
and mixed file processing.
"""

import json
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from qms.quality.mobile_capture import (
    scan_capture_folder,
    analyze_photo,
    analyze_transcript,
    create_issue_from_capture,
    process_captures,
    transcribe_audio,
    _AUDIO_EXTENSIONS,
    _ALL_EXTENSIONS,
    _file_hash,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def capture_folder(tmp_path):
    """Create a temp folder with test image files, audio files, and non-media files."""
    (tmp_path / "photo1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    (tmp_path / "photo2.png").write_bytes(b"\x89PNG" + b"\x00" * 100)
    (tmp_path / "photo3.jpeg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)
    (tmp_path / "voice1.m4a").write_bytes(b"\x00" * 200)
    (tmp_path / "voice2.mp3").write_bytes(b"\xff\xfb\x90" + b"\x00" * 150)
    (tmp_path / "notes.txt").write_text("not an image")
    (tmp_path / "data.csv").write_text("col1,col2\na,b")
    return tmp_path


@pytest.fixture
def mock_analysis():
    """Standard successful analysis result from Claude."""
    return {
        "title": "Damaged pipe insulation in mechanical room",
        "type": "observation",
        "trade": "Mechanical",
        "severity": "medium",
        "location": "Mechanical Room B, 2nd Floor",
        "description": "Fiberglass pipe insulation is torn and hanging from a 4-inch chilled water supply line.",
        "recommended_action": "Replace damaged insulation section and secure with new vapor barrier jacket.",
    }


@pytest.fixture
def mock_claude_response(mock_analysis):
    """Mock anthropic API response object."""
    response = MagicMock()
    response.content = [MagicMock()]
    response.content[0].text = json.dumps(mock_analysis)
    return response


# ---------------------------------------------------------------------------
# Test: Folder scanning
# ---------------------------------------------------------------------------


class TestScanCaptureFolder:
    def test_scan_finds_images(self, capture_folder, memory_db):
        """Scan discovers .jpg, .png, .jpeg files and ignores .txt, .csv."""
        files = scan_capture_folder(capture_folder, memory_db)
        names = {f.name for f in files}
        assert "photo1.jpg" in names
        assert "photo2.png" in names
        assert "photo3.jpeg" in names
        assert "notes.txt" not in names
        assert "data.csv" not in names

    def test_scan_finds_audio_files(self, capture_folder, memory_db):
        """Scan discovers .m4a and .mp3 audio files alongside images."""
        files = scan_capture_folder(capture_folder, memory_db)
        names = {f.name for f in files}
        assert "voice1.m4a" in names
        assert "voice2.mp3" in names
        # Total: 3 images + 2 audio = 5
        assert len(files) == 5

    def test_scan_skips_processed(self, capture_folder, memory_db):
        """Files already in capture_log are not returned."""
        # Mark photo1.jpg as already processed
        memory_db.execute(
            "INSERT INTO capture_log (filename, filepath, status) VALUES (?, ?, 'processed')",
            ("photo1.jpg", str(capture_folder / "photo1.jpg")),
        )
        memory_db.commit()

        files = scan_capture_folder(capture_folder, memory_db)
        names = {f.name for f in files}
        assert "photo1.jpg" not in names
        assert "photo2.png" in names
        assert "photo3.jpeg" in names
        assert "voice1.m4a" in names

    def test_scan_empty_folder(self, tmp_path, memory_db):
        """Empty folder returns empty list."""
        files = scan_capture_folder(tmp_path, memory_db)
        assert files == []

    def test_scan_nonexistent_folder(self, memory_db):
        """Non-existent folder returns empty list without error."""
        files = scan_capture_folder(Path("/nonexistent/folder"), memory_db)
        assert files == []


# ---------------------------------------------------------------------------
# Test: Photo analysis
# ---------------------------------------------------------------------------


class TestAnalyzePhoto:
    def test_parses_response(self, capture_folder, mock_claude_response):
        """Mocked Claude response is parsed into correct dict."""
        mock_client = MagicMock()
        mock_client.return_value.messages.create.return_value = mock_claude_response

        with patch("qms.quality.mobile_capture.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_claude_response
            result = analyze_photo(capture_folder / "photo1.jpg")

        assert result["title"] == "Damaged pipe insulation in mechanical room"
        assert result["type"] == "observation"
        assert result["trade"] == "Mechanical"
        assert result["severity"] == "medium"
        assert "error" not in result

    def test_normalizes_trade(self, capture_folder):
        """Trade names are normalized through normalize_trade()."""
        response = MagicMock()
        response.content = [MagicMock()]
        response.content[0].text = json.dumps({
            "title": "Test issue",
            "type": "observation",
            "trade": "Mech",  # Should normalize to "Mechanical"
            "severity": "low",
            "location": "Room 1",
            "description": "Test",
        })

        with patch("qms.quality.mobile_capture.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value.messages.create.return_value = response
            result = analyze_photo(capture_folder / "photo1.jpg")

        assert result["trade"] == "Mechanical"

    def test_handles_api_error(self, capture_folder):
        """API exceptions return error dict instead of raising."""
        with patch("qms.quality.mobile_capture.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value.messages.create.side_effect = Exception("API rate limit")
            result = analyze_photo(capture_folder / "photo1.jpg")

        assert "error" in result
        assert "API rate limit" in result["error"]

    def test_handles_invalid_json(self, capture_folder):
        """Non-JSON response returns error dict."""
        response = MagicMock()
        response.content = [MagicMock()]
        response.content[0].text = "I cannot analyze this image."

        with patch("qms.quality.mobile_capture.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value.messages.create.return_value = response
            result = analyze_photo(capture_folder / "photo1.jpg")

        assert "error" in result

    def test_validates_severity(self, capture_folder):
        """Invalid severity values are defaulted to 'medium'."""
        response = MagicMock()
        response.content = [MagicMock()]
        response.content[0].text = json.dumps({
            "title": "Test",
            "type": "observation",
            "trade": "General",
            "severity": "EXTREME",  # Invalid
            "location": "Outside",
            "description": "Test desc",
        })

        with patch("qms.quality.mobile_capture.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value.messages.create.return_value = response
            result = analyze_photo(capture_folder / "photo1.jpg")

        assert result["severity"] == "medium"


# ---------------------------------------------------------------------------
# Test: Issue creation
# ---------------------------------------------------------------------------


class TestCreateIssueFromCapture:
    def test_inserts_record(self, memory_db, capture_folder, mock_analysis, tmp_path):
        """Creates quality_issues + attachments + capture_log records."""
        attachment_dir = tmp_path / "attachments"
        image_path = capture_folder / "photo1.jpg"

        issue_id = create_issue_from_capture(
            memory_db, mock_analysis, image_path, project_id=None, attachment_dir=attachment_dir
        )
        memory_db.commit()

        # Check quality_issues
        issue = memory_db.execute(
            "SELECT * FROM quality_issues WHERE id = ?", (issue_id,)
        ).fetchone()
        assert issue is not None
        assert issue["source"] == "mobile"
        assert issue["title"] == "Damaged pipe insulation in mechanical room"
        assert issue["trade"] == "Mechanical"
        assert issue["severity"] == "medium"

        # Check attachment
        att = memory_db.execute(
            "SELECT * FROM quality_issue_attachments WHERE issue_id = ?", (issue_id,)
        ).fetchone()
        assert att is not None
        assert att["filename"] == "photo1.jpg"
        assert att["file_type"] == "image"

        # Check capture_log
        log = memory_db.execute(
            "SELECT * FROM capture_log WHERE issue_id = ?", (issue_id,)
        ).fetchone()
        assert log is not None
        assert log["status"] == "processed"
        assert log["filename"] == "photo1.jpg"

    def test_copies_file(self, memory_db, capture_folder, mock_analysis, tmp_path):
        """Image file is copied to attachment directory."""
        attachment_dir = tmp_path / "attachments"
        image_path = capture_folder / "photo1.jpg"

        issue_id = create_issue_from_capture(
            memory_db, mock_analysis, image_path, project_id=None, attachment_dir=attachment_dir
        )

        dest = attachment_dir / str(issue_id) / "photo1.jpg"
        assert dest.exists()
        assert dest.read_bytes() == image_path.read_bytes()

    def test_stores_metadata(self, memory_db, capture_folder, mock_analysis, tmp_path):
        """recommended_action is stored in metadata JSON."""
        attachment_dir = tmp_path / "attachments"
        image_path = capture_folder / "photo1.jpg"

        issue_id = create_issue_from_capture(
            memory_db, mock_analysis, image_path, project_id=None, attachment_dir=attachment_dir
        )

        issue = memory_db.execute(
            "SELECT metadata FROM quality_issues WHERE id = ?", (issue_id,)
        ).fetchone()
        metadata = json.loads(issue["metadata"])
        assert "recommended_action" in metadata


# ---------------------------------------------------------------------------
# Test: End-to-end processing
# ---------------------------------------------------------------------------


class TestProcessCaptures:
    def _patch_get_db(self, memory_db):
        """Create a context manager mock for get_db that yields memory_db."""
        from contextlib import contextmanager

        @contextmanager
        def _get_db(readonly=False):
            yield memory_db

        return patch("qms.quality.mobile_capture.get_db", _get_db)

    def _mock_whisper_response(self):
        """Create a mock Whisper API response."""
        transcript = MagicMock()
        transcript.text = "The insulation on the chilled water line in mechanical room B is damaged. Looks like it was torn during pipe hanger installation."
        return transcript

    def test_dry_run(self, capture_folder, mock_claude_response, memory_db):
        """Dry run analyzes but does not insert records."""
        with patch("qms.quality.mobile_capture.anthropic") as mock_anthropic, \
             patch("qms.quality.mobile_capture.openai_sdk") as mock_openai, \
             patch("qms.quality.mobile_capture.get_config_value", return_value=None), \
             self._patch_get_db(memory_db):
            mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_claude_response
            mock_openai.OpenAI.return_value.audio.transcriptions.create.return_value = self._mock_whisper_response()
            result = process_captures(
                folder=capture_folder, project_id=None, dry_run=True
            )

        # 3 images + 2 audio = 5 files
        assert result["processed"] == 5
        assert result["transcribed"] == 2
        assert result["failed"] == 0
        assert result["dry_run"] is True
        assert len(result["issues_created"]) == 5

    def test_full_run(self, capture_folder, mock_claude_response, memory_db, tmp_path):
        """Full run creates issues and attachment files."""
        attachment_dir = tmp_path / "att"

        def _config_side_effect(*keys, default=None):
            if keys == ("mobile_capture", "model"):
                return "sonnet"
            if keys == ("mobile_capture", "attachment_dir"):
                return str(attachment_dir)
            return default

        with patch("qms.quality.mobile_capture.anthropic") as mock_anthropic, \
             patch("qms.quality.mobile_capture.openai_sdk") as mock_openai, \
             patch("qms.quality.mobile_capture.get_config_value", side_effect=_config_side_effect), \
             self._patch_get_db(memory_db):
            mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_claude_response
            mock_openai.OpenAI.return_value.audio.transcriptions.create.return_value = self._mock_whisper_response()
            result = process_captures(
                folder=capture_folder, project_id=None, dry_run=False
            )

        assert result["processed"] == 5
        assert result["transcribed"] == 2
        assert result["failed"] == 0
        assert len(result["issues_created"]) == 5
        # All should have issue_ids
        for item in result["issues_created"]:
            assert "issue_id" in item

    def test_skips_duplicates(self, capture_folder, mock_claude_response, memory_db, tmp_path):
        """Re-running on same folder produces 0 new issues."""
        attachment_dir = tmp_path / "att"

        def _config_side_effect(*keys, default=None):
            if keys == ("mobile_capture", "model"):
                return "sonnet"
            if keys == ("mobile_capture", "attachment_dir"):
                return str(attachment_dir)
            return default

        with patch("qms.quality.mobile_capture.anthropic") as mock_anthropic, \
             patch("qms.quality.mobile_capture.openai_sdk") as mock_openai, \
             patch("qms.quality.mobile_capture.get_config_value", side_effect=_config_side_effect), \
             self._patch_get_db(memory_db):
            mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_claude_response
            mock_openai.OpenAI.return_value.audio.transcriptions.create.return_value = self._mock_whisper_response()
            # First run
            result1 = process_captures(folder=capture_folder, project_id=None, dry_run=False)
            # Second run — same folder
            result2 = process_captures(folder=capture_folder, project_id=None, dry_run=False)

        assert result1["processed"] == 5
        assert result2["processed"] == 0
        assert result2["failed"] == 0


# ---------------------------------------------------------------------------
# Test: Voice transcription
# ---------------------------------------------------------------------------


class TestTranscribeAudio:
    def test_transcribe_success(self, capture_folder):
        """Mocked Whisper response returns transcript text."""
        mock_transcript = MagicMock()
        mock_transcript.text = "The pipe insulation is damaged in room B."

        with patch("qms.quality.mobile_capture.openai_sdk") as mock_openai:
            mock_openai.OpenAI.return_value.audio.transcriptions.create.return_value = mock_transcript
            result = transcribe_audio(capture_folder / "voice1.m4a")

        assert "text" in result
        assert result["text"] == "The pipe insulation is damaged in room B."
        assert "error" not in result

    def test_transcribe_handles_error(self, capture_folder):
        """API errors return error dict instead of raising."""
        with patch("qms.quality.mobile_capture.openai_sdk") as mock_openai:
            mock_openai.OpenAI.return_value.audio.transcriptions.create.side_effect = Exception("Quota exceeded")
            result = transcribe_audio(capture_folder / "voice1.m4a")

        assert "error" in result
        assert "Quota exceeded" in result["error"]

    def test_transcribe_missing_sdk(self, capture_folder):
        """Returns error when openai SDK not installed."""
        with patch("qms.quality.mobile_capture.openai_sdk", None):
            result = transcribe_audio(capture_folder / "voice1.m4a")

        assert "error" in result
        assert "openai SDK not installed" in result["error"]


class TestAnalyzeTranscript:
    def test_parses_response(self):
        """Mocked Claude response from transcript is parsed into correct dict."""
        analysis_json = json.dumps({
            "title": "Damaged insulation on chilled water line",
            "type": "observation",
            "trade": "Mechanical",
            "severity": "medium",
            "location": "Mechanical Room B",
            "description": "Pipe insulation torn during hanger install",
            "recommended_action": "Replace insulation section",
        })
        response = MagicMock()
        response.content = [MagicMock()]
        response.content[0].text = analysis_json

        with patch("qms.quality.mobile_capture.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value.messages.create.return_value = response
            result = analyze_transcript("The insulation is damaged in room B.")

        assert result["title"] == "Damaged insulation on chilled water line"
        assert result["type"] == "observation"
        assert result["trade"] == "Mechanical"
        assert "error" not in result

    def test_preserves_transcript(self):
        """Original transcript text is preserved in result dict."""
        analysis_json = json.dumps({
            "title": "Test observation",
            "type": "observation",
            "trade": "General",
            "severity": "low",
            "location": "Site",
            "description": "Test",
            "recommended_action": "None needed",
        })
        response = MagicMock()
        response.content = [MagicMock()]
        response.content[0].text = analysis_json

        original_text = "Walking the third floor, I see some water damage near column C4."

        with patch("qms.quality.mobile_capture.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value.messages.create.return_value = response
            result = analyze_transcript(original_text)

        assert result["transcript"] == original_text

    def test_handles_api_error(self):
        """API error returns error dict."""
        with patch("qms.quality.mobile_capture.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value.messages.create.side_effect = Exception("API timeout")
            result = analyze_transcript("Some voice note text")

        assert "error" in result
        assert "API timeout" in result["error"]


class TestCreateIssueFromAudio:
    def test_audio_attachment_type(self, memory_db, capture_folder, tmp_path):
        """Audio captures get file_type='audio' in attachments."""
        analysis = {
            "title": "Voice note observation",
            "type": "observation",
            "trade": "Mechanical",
            "severity": "medium",
            "location": "Room B",
            "description": "Insulation damage",
            "recommended_action": "Replace insulation",
            "transcript": "The insulation is damaged.",
        }
        attachment_dir = tmp_path / "att"
        audio_path = capture_folder / "voice1.m4a"

        issue_id = create_issue_from_capture(
            memory_db, analysis, audio_path, project_id=None, attachment_dir=attachment_dir
        )
        memory_db.commit()

        att = memory_db.execute(
            "SELECT * FROM quality_issue_attachments WHERE issue_id = ?", (issue_id,)
        ).fetchone()
        assert att["file_type"] == "audio"
        assert att["filename"] == "voice1.m4a"

    def test_transcript_in_metadata(self, memory_db, capture_folder, tmp_path):
        """Transcript is stored in quality_issues metadata JSON."""
        analysis = {
            "title": "Voice note observation",
            "type": "observation",
            "trade": "General",
            "severity": "low",
            "location": "Hallway",
            "description": "Minor issue",
            "transcript": "Walking the hallway, I notice some paint peeling.",
        }
        attachment_dir = tmp_path / "att"
        audio_path = capture_folder / "voice1.m4a"

        issue_id = create_issue_from_capture(
            memory_db, analysis, audio_path, project_id=None, attachment_dir=attachment_dir
        )

        issue = memory_db.execute(
            "SELECT metadata FROM quality_issues WHERE id = ?", (issue_id,)
        ).fetchone()
        metadata = json.loads(issue["metadata"])
        assert metadata["transcript"] == "Walking the hallway, I notice some paint peeling."


# ---------------------------------------------------------------------------
# Test: Utility functions
# ---------------------------------------------------------------------------


class TestFileHash:
    def test_consistent_hash(self, capture_folder):
        """Same file produces same hash."""
        h1 = _file_hash(capture_folder / "photo1.jpg")
        h2 = _file_hash(capture_folder / "photo1.jpg")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_files_different_hash(self, capture_folder):
        """Different files produce different hashes."""
        h1 = _file_hash(capture_folder / "photo1.jpg")
        h2 = _file_hash(capture_folder / "photo2.png")
        assert h1 != h2
