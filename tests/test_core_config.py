"""Tests for config loading and QMS_PATHS path resolution."""

from pathlib import Path

from qms.core.config import get_config, get_config_value, QMS_PATHS, _PACKAGE_DIR


def test_get_config_returns_dict():
    config = get_config(reload=True)
    assert isinstance(config, dict)
    assert "destinations" in config or "inbox" in config


def test_get_config_caching():
    c1 = get_config()
    c2 = get_config()
    assert c1 is c2


def test_get_config_reload_returns_fresh():
    c1 = get_config()
    c2 = get_config(reload=True)
    # After reload the cache is replaced, so a new call should return c2
    c3 = get_config()
    assert c3 is c2


def test_get_config_value_nested():
    db_path = get_config_value("destinations", "database")
    assert db_path is not None
    assert "quality.db" in db_path


def test_get_config_value_missing_returns_default():
    result = get_config_value("nonexistent", "deep", "path", default="fallback")
    assert result == "fallback"


def test_qms_paths_database_is_absolute():
    assert QMS_PATHS.database.is_absolute()
    assert str(QMS_PATHS.database).endswith("quality.db")


def test_qms_paths_inbox_is_absolute():
    assert QMS_PATHS.inbox.is_absolute()


def test_qms_paths_needs_review_child_of_inbox():
    assert QMS_PATHS.needs_review.parent == QMS_PATHS.inbox


def test_qms_paths_all_resolve_under_package_dir():
    for prop in ["database", "inbox", "projects", "quality_documents", "vector_database"]:
        path = getattr(QMS_PATHS, prop)
        assert path.is_absolute(), f"{prop} is not absolute"
        assert str(path).startswith(str(_PACKAGE_DIR)), (
            f"{prop} does not resolve under package dir: {path}"
        )


def test_database_path_is_relative_in_config():
    """The database path in config.yaml should be relative, not a Windows path."""
    raw = get_config_value("destinations", "database")
    assert raw is not None
    assert not raw.startswith("C:"), "Database path should be relative"
    assert not raw.startswith("D:"), "Database path should be relative"
