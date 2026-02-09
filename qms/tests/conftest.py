"""
Shared test fixtures for QMS.

Provides an in-memory database for isolated testing.
"""

import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def memory_db():
    """Provide an in-memory SQLite database with core schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    # Apply core schema
    schema_dir = Path(__file__).parent.parent
    for module in ["core", "workforce", "projects"]:
        schema_file = schema_dir / module / "schema.sql"
        if schema_file.exists():
            conn.executescript(schema_file.read_text(encoding="utf-8"))

    yield conn
    conn.close()


@pytest.fixture
def mock_db(memory_db):
    """Patch get_db to return the in-memory database."""
    from contextlib import contextmanager

    @contextmanager
    def _get_db(readonly=False):
        yield memory_db

    with patch("qms.core.db.get_db", _get_db):
        yield memory_db
