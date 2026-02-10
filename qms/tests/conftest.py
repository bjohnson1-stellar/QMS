"""
Shared test fixtures for QMS.

Provides an in-memory database with all schemas, mock config, CLI runner,
and seed data fixtures for isolated testing.
"""

import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager

from qms.core.db import SCHEMA_ORDER


@pytest.fixture
def memory_db():
    """Provide an in-memory SQLite database with ALL schemas applied in FK order."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    schema_dir = Path(__file__).parent.parent
    for module in SCHEMA_ORDER:
        schema_file = schema_dir / module / "schema.sql"
        if schema_file.exists():
            conn.executescript(schema_file.read_text(encoding="utf-8"))

    yield conn
    conn.close()


@pytest.fixture
def mock_db(memory_db):
    """Patch get_db everywhere to return the in-memory database."""

    @contextmanager
    def _get_db(readonly=False):
        yield memory_db

    with patch("qms.core.db.get_db", _get_db), \
         patch("qms.core.get_db", _get_db), \
         patch("qms.engineering.db.get_db", _get_db):
        yield memory_db


@pytest.fixture
def cli_runner():
    """Typer CLI test runner."""
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture
def seed_project(memory_db):
    """Insert a minimal project for FK references. Returns project id."""
    memory_db.execute(
        "INSERT INTO projects (id, number, name, status) VALUES (1, '07645', 'Test Project', 'active')"
    )
    memory_db.commit()
    return 1


@pytest.fixture
def seed_sheet(memory_db, seed_project):
    """Insert a test sheet. Returns sheet id."""
    memory_db.execute(
        "INSERT INTO sheets (id, project_id, drawing_number, discipline, revision) "
        "VALUES (1, ?, 'P-101', 'piping', 'A')",
        (seed_project,),
    )
    memory_db.commit()
    return 1
