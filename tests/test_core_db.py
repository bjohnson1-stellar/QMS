"""Tests for database connection management and query execution."""

from qms.core.db import SCHEMA_ORDER, execute_query


def test_get_db_sets_row_factory(mock_db):
    row = mock_db.execute("SELECT 1 AS val").fetchone()
    assert row["val"] == 1


def test_get_db_enables_foreign_keys(mock_db):
    fk = mock_db.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_execute_query_returns_rows(mock_db):
    rows = execute_query("SELECT 42 AS n")
    assert len(rows) == 1
    assert rows[0]["n"] == 42


def test_schema_order_length():
    assert len(SCHEMA_ORDER) == 11


def test_schema_order_starts_with_auth():
    assert SCHEMA_ORDER[0] == "auth"
    assert SCHEMA_ORDER[1] == "core"


def test_schema_order_blog_last():
    assert SCHEMA_ORDER[-1] == "blog"
