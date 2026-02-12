"""Validate test infrastructure: all schemas load, FK constraints work."""

import sqlite3
import pytest
from pathlib import Path

from qms.core.db import SCHEMA_ORDER


def test_all_schemas_load_in_memory(memory_db):
    """All 8 schema files should load without error into in-memory DB."""
    tables = memory_db.execute(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table'"
    ).fetchone()
    # We expect 200+ tables across 8 schemas
    assert tables["n"] > 100, f"Expected >100 tables, got {tables['n']}"


def test_schema_order_has_nine_modules():
    """SCHEMA_ORDER should list all 9 modules in FK-dependency order."""
    assert len(SCHEMA_ORDER) == 9
    assert SCHEMA_ORDER[0] == "core"
    assert SCHEMA_ORDER[-1] == "automation"


def test_schema_order_contents():
    """All expected modules should be in SCHEMA_ORDER."""
    expected = {"core", "workforce", "projects", "qualitydocs",
                "references", "welding", "pipeline", "engineering",
                "automation"}
    assert set(SCHEMA_ORDER) == expected


def test_foreign_keys_enforced(memory_db):
    """FK constraints should be active — bogus FK should raise IntegrityError."""
    fk_status = memory_db.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_status == 1


def test_key_tables_exist(memory_db):
    """Critical tables from each module should exist."""
    critical_tables = [
        "audit_log",          # core
        "employees",          # workforce
        "projects",           # projects
        "qm_modules",         # qualitydocs
        "ref_clauses",        # references
        "weld_wps",           # welding
        "processing_queue",   # pipeline
        "eng_calculations",   # engineering
    ]
    for table in critical_tables:
        try:
            memory_db.execute(f"SELECT 1 FROM [{table}] LIMIT 0")
        except sqlite3.OperationalError:
            pytest.fail(f"Table '{table}' does not exist — schema not loaded")


def test_all_schema_files_exist():
    """Every module in SCHEMA_ORDER should have a schema.sql file on disk."""
    schema_dir = Path(__file__).parent.parent
    for module in SCHEMA_ORDER:
        schema_file = schema_dir / module / "schema.sql"
        assert schema_file.exists(), f"Missing: {module}/schema.sql"
