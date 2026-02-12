"""Tests for the automation dispatcher module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from qms.automation.dispatcher import (
    register_handler,
    process_file,
    process_all,
    get_processing_log,
    _HANDLERS,
)


@pytest.fixture(autouse=True)
def clean_handlers():
    """Clear handler registry between tests."""
    saved = dict(_HANDLERS)
    _HANDLERS.clear()
    yield
    _HANDLERS.clear()
    _HANDLERS.update(saved)


@pytest.fixture
def incoming_dir(tmp_path):
    """Create incoming/processed/failed directories."""
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    failed = tmp_path / "failed"
    incoming.mkdir()
    processed.mkdir()
    failed.mkdir()
    return incoming, processed, failed


@pytest.fixture
def mock_automation_paths(incoming_dir):
    """Patch _get_automation_paths to use temp directories."""
    incoming, processed, failed = incoming_dir
    with patch(
        "qms.automation.dispatcher._get_automation_paths",
        return_value=(incoming, processed, failed),
    ):
        yield incoming, processed, failed


class TestRegisterHandler:
    def test_register_handler(self):
        def my_handler(path):
            return {"status": "ok"}

        register_handler("test_type", my_handler, "test_module")
        assert "test_type" in _HANDLERS
        assert _HANDLERS["test_type"] == (my_handler, "test_module")


class TestProcessFile:
    def test_invalid_json(self, mock_automation_paths, mock_db):
        incoming, _, failed = mock_automation_paths
        bad_file = incoming / "bad.json"
        bad_file.write_text("not json at all", encoding="utf-8")

        result = process_file(bad_file)
        assert result["status"] == "failed"
        assert "Invalid JSON" in result["error"]
        # File should be moved to failed/
        assert not bad_file.exists()
        assert any(f.name.endswith("bad.json") for f in failed.iterdir())

    def test_missing_type_field(self, mock_automation_paths, mock_db):
        incoming, _, failed = mock_automation_paths
        no_type = incoming / "no_type.json"
        no_type.write_text(json.dumps({"data": "stuff"}), encoding="utf-8")

        result = process_file(no_type)
        assert result["status"] == "failed"
        assert "Missing 'type'" in result["error"]

    def test_unknown_type(self, mock_automation_paths, mock_db):
        incoming, _, failed = mock_automation_paths
        unknown = incoming / "unknown.json"
        unknown.write_text(json.dumps({"type": "alien_signal"}), encoding="utf-8")

        result = process_file(unknown)
        assert result["status"] == "failed"
        assert "No handler registered" in result["error"]

    def test_successful_processing(self, mock_automation_paths, mock_db):
        incoming, processed, _ = mock_automation_paths

        def ok_handler(path):
            return {"summary": "All good"}

        register_handler("test_ok", ok_handler, "test")

        test_file = incoming / "good.json"
        test_file.write_text(json.dumps({"type": "test_ok", "data": 1}), encoding="utf-8")

        result = process_file(test_file)
        assert result["status"] == "success"
        assert result["result_summary"] == "All good"
        # File should be moved to processed/
        assert not test_file.exists()
        assert any(f.name.endswith("good.json") for f in processed.iterdir())

    def test_handler_exception(self, mock_automation_paths, mock_db):
        incoming, _, failed = mock_automation_paths

        def bad_handler(path):
            raise ValueError("something broke")

        register_handler("test_fail", bad_handler, "test")

        test_file = incoming / "fail.json"
        test_file.write_text(json.dumps({"type": "test_fail"}), encoding="utf-8")

        result = process_file(test_file)
        assert result["status"] == "failed"
        assert "something broke" in result["error"]

    def test_dry_run_no_move(self, mock_automation_paths, mock_db):
        incoming, processed, _ = mock_automation_paths

        def ok_handler(path):
            return {"summary": "ok"}

        register_handler("test_dry", ok_handler, "test")

        test_file = incoming / "dry.json"
        test_file.write_text(json.dumps({"type": "test_dry"}), encoding="utf-8")

        result = process_file(test_file, dry_run=True)
        assert result["status"] == "dry_run"
        # File should NOT be moved
        assert test_file.exists()


class TestProcessAll:
    def test_empty_directory(self, mock_automation_paths, mock_db):
        results = process_all()
        assert results == []

    def test_processes_all_files(self, mock_automation_paths, mock_db):
        incoming, processed, _ = mock_automation_paths
        call_count = {"n": 0}

        def counter_handler(path):
            call_count["n"] += 1
            return {"summary": f"processed #{call_count['n']}"}

        register_handler("batch_test", counter_handler, "test")

        for i in range(3):
            f = incoming / f"file{i}.json"
            f.write_text(json.dumps({"type": "batch_test", "i": i}), encoding="utf-8")

        results = process_all()
        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)
        assert call_count["n"] == 3


class TestProcessingLog:
    def test_log_written_on_success(self, mock_automation_paths, mock_db):
        incoming, processed, _ = mock_automation_paths

        def ok_handler(path):
            return {"summary": "logged"}

        register_handler("log_test", ok_handler, "test")

        test_file = incoming / "log.json"
        test_file.write_text(json.dumps({"type": "log_test"}), encoding="utf-8")

        process_file(test_file)

        entries = get_processing_log(limit=10)
        assert len(entries) >= 1
        # Find the success entry
        success_entries = [e for e in entries if e["status"] == "success"]
        assert len(success_entries) >= 1
        assert success_entries[0]["request_type"] == "log_test"
