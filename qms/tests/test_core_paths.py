"""Tests for path utilities."""

from qms.core.paths import ensure_directory


def test_ensure_directory_creates(tmp_path):
    new_dir = tmp_path / "sub" / "dir"
    ensure_directory(new_dir)
    assert new_dir.exists()


def test_ensure_directory_returns_path(tmp_path):
    result = ensure_directory(tmp_path / "test")
    assert result == tmp_path / "test"


def test_ensure_directory_idempotent(tmp_path):
    d = tmp_path / "existing"
    d.mkdir()
    ensure_directory(d)  # should not raise
    assert d.exists()
