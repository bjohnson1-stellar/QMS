"""
Transaction & Budget Settings Business Logic

Pure business logic for project transaction CRUD and singleton budget settings.
No Flask imports — used by both CLI and API layers.
"""

import sqlite3
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger

logger = get_logger("qms.timetracker.transactions")


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


def list_transactions(
    conn: Optional[sqlite3.Connection] = None,
    *,
    project_id: Optional[int] = None,
    transaction_type: Optional[str] = None,
    bu_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """List transactions with optional filters.

    When bu_ids is provided, only returns transactions for projects that
    have allocations in the given business units.
    """
    sql = """
        SELECT t.*, p.name AS project_name, p.number AS project_code
        FROM project_transactions t
        JOIN projects p ON t.project_id = p.id
    """
    conditions = []
    params: list = []
    if project_id:
        conditions.append("t.project_id = ?")
        params.append(project_id)
    if transaction_type:
        conditions.append("t.transaction_type = ?")
        params.append(transaction_type)
    if bu_ids:
        placeholders = ",".join("?" for _ in bu_ids)
        conditions.append(
            f"p.id IN (SELECT project_id FROM project_allocations WHERE business_unit_id IN ({placeholders}))"
        )
        params.extend(bu_ids)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY t.transaction_date DESC, t.created_at DESC"

    def _run(c: sqlite3.Connection):
        return [dict(r) for r in c.execute(sql, params).fetchall()]

    if conn:
        return _run(conn)
    with get_db(readonly=True) as c:
        return _run(c)


def get_transaction(conn: sqlite3.Connection, txn_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT t.*, p.name AS project_name, p.number AS project_code
        FROM project_transactions t
        JOIN projects p ON t.project_id = p.id
        WHERE t.id = ?
        """,
        (txn_id,),
    ).fetchone()
    return dict(row) if row else None


def create_transaction(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    transaction_date: str,
    transaction_type: str,
    description: str,
    amount: float,
    hours: Optional[float] = None,
    rate: Optional[float] = None,
    notes: Optional[str] = None,
) -> int:
    """Create a transaction. For Time type, amount = hours * rate."""
    if transaction_type == "Time" and hours and rate:
        amount = hours * rate

    cursor = conn.execute(
        """
        INSERT INTO project_transactions
            (project_id, transaction_date, transaction_type, description,
             amount, hours, rate, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, transaction_date, transaction_type, description,
         amount, hours, rate, notes),
    )
    conn.commit()
    return cursor.lastrowid


def update_transaction(
    conn: sqlite3.Connection,
    txn_id: int,
    *,
    project_id: int,
    transaction_date: str,
    transaction_type: str,
    description: str,
    amount: float,
    hours: Optional[float] = None,
    rate: Optional[float] = None,
    notes: Optional[str] = None,
) -> None:
    if transaction_type == "Time" and hours and rate:
        amount = hours * rate

    conn.execute(
        """
        UPDATE project_transactions
        SET project_id=?, transaction_date=?, transaction_type=?, description=?,
            amount=?, hours=?, rate=?, notes=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (project_id, transaction_date, transaction_type, description,
         amount, hours, rate, notes, txn_id),
    )
    conn.commit()


def delete_transaction(conn: sqlite3.Connection, txn_id: int) -> None:
    conn.execute("DELETE FROM project_transactions WHERE id=?", (txn_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Settings (singleton)
# ---------------------------------------------------------------------------


def get_settings(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Get budget settings, creating defaults if missing."""
    def _run(c: sqlite3.Connection) -> Dict[str, Any]:
        row = c.execute("SELECT * FROM budget_settings WHERE id = 1").fetchone()
        if not row:
            c.execute(
                "INSERT INTO budget_settings (id, company_name, default_hourly_rate, "
                "working_hours_per_month, fiscal_year_start_month, gmp_weight_multiplier, "
                "max_hours_per_week) "
                "VALUES (1, 'My Company', 150.0, 176, 1, 1.5, 40.0)"
            )
            c.commit()
            row = c.execute("SELECT * FROM budget_settings WHERE id = 1").fetchone()
        return dict(row)

    if conn:
        return _run(conn)
    with get_db() as c:
        return _run(c)


def update_settings(
    conn: sqlite3.Connection,
    *,
    company_name: str = "My Company",
    default_hourly_rate: float = 150.0,
    working_hours_per_month: int = 176,
    fiscal_year_start_month: int = 1,
    gmp_weight_multiplier: float = 1.5,
    max_hours_per_week: float = 40.0,
) -> None:
    conn.execute(
        """
        UPDATE budget_settings
        SET company_name=?, default_hourly_rate=?, working_hours_per_month=?,
            fiscal_year_start_month=?, gmp_weight_multiplier=?,
            max_hours_per_week=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=1
        """,
        (company_name, default_hourly_rate, working_hours_per_month,
         fiscal_year_start_month, gmp_weight_multiplier, max_hours_per_week),
    )
    conn.commit()
