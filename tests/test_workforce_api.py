"""Tests for workforce listing/stats functions used by the web UI."""

from qms.workforce.employees import (
    create_employee,
    get_employee_stats,
    list_employees,
    list_potential_managers,
    update_employee,
)


def _seed_roles(conn):
    conn.execute(
        "INSERT INTO roles (id, role_name, role_code) VALUES (1, 'Pipefitter', 'PF')"
    )
    conn.execute(
        "INSERT INTO roles (id, role_name, role_code) VALUES (2, 'Welder', 'WD')"
    )


def _seed_dept(conn):
    conn.execute(
        "INSERT INTO departments (id, department_number, name) "
        "VALUES (1, 'D001', 'Mechanical')"
    )


class TestListEmployees:
    def test_default_returns_active(self, memory_db):
        create_employee(memory_db, "Smith", "Jane", is_employee=True, status="active")
        create_employee(memory_db, "Gone", "Tom", is_employee=True, status="terminated")
        rows = list_employees(memory_db)
        assert len(rows) == 1
        assert rows[0]["last_name"] == "Smith"

    def test_include_inactive(self, memory_db):
        create_employee(memory_db, "Smith", "Jane", is_employee=True, status="active")
        create_employee(memory_db, "Gone", "Tom", is_employee=True, status="terminated")
        rows = list_employees(memory_db, include_inactive=True)
        assert len(rows) == 2

    def test_filter_by_role(self, memory_db):
        _seed_roles(memory_db)
        create_employee(memory_db, "Smith", "Jane", is_employee=True, role_id=1)
        create_employee(memory_db, "Doe", "John", is_employee=True, role_id=2)
        rows = list_employees(memory_db, role_id=1)
        assert len(rows) == 1
        assert rows[0]["role_name"] == "Pipefitter"

    def test_filter_by_department(self, memory_db):
        _seed_dept(memory_db)
        create_employee(memory_db, "Smith", "Jane", is_employee=True, department_id=1)
        create_employee(memory_db, "Doe", "John", is_employee=True)
        rows = list_employees(memory_db, department_id=1)
        assert len(rows) == 1
        assert rows[0]["department_name"] == "Mechanical"

    def test_search_by_name(self, memory_db):
        create_employee(memory_db, "Smith", "Jane", is_employee=True)
        create_employee(memory_db, "Doe", "John", is_employee=True)
        rows = list_employees(memory_db, search="smith")
        assert len(rows) == 1
        assert rows[0]["last_name"] == "Smith"

    def test_search_by_number(self, memory_db):
        create_employee(memory_db, "Smith", "Jane", is_employee=True)
        create_employee(memory_db, "Doe", "John", is_employee=True)
        rows = list_employees(memory_db, search="EMP-0002")
        assert len(rows) == 1
        assert rows[0]["last_name"] == "Doe"

    def test_includes_supervisor_name(self, memory_db):
        sup_id = create_employee(memory_db, "Boss", "The", is_employee=True)
        emp_id = create_employee(
            memory_db, "Worker", "Bee", is_employee=True, supervisor_id=sup_id
        )
        rows = list_employees(memory_db)
        worker = next(r for r in rows if r["id"] == emp_id)
        assert worker["supervisor_name"] == "The Boss"

    def test_ordered_by_last_name(self, memory_db):
        create_employee(memory_db, "Zeta", "Al", is_employee=True)
        create_employee(memory_db, "Alpha", "Bob", is_employee=True)
        rows = list_employees(memory_db)
        assert rows[0]["last_name"] == "Alpha"
        assert rows[1]["last_name"] == "Zeta"


class TestGetEmployeeStats:
    def test_correct_counts(self, memory_db):
        create_employee(memory_db, "Smith", "Jane", is_employee=True, status="active")
        create_employee(memory_db, "Doe", "John", is_employee=True, status="active")
        create_employee(memory_db, "Gone", "Tom", is_employee=True, status="terminated")
        stats = get_employee_stats(memory_db)
        assert stats["total_active"] == 2
        assert stats["total_inactive"] == 1

    def test_unassigned_manager(self, memory_db):
        sup_id = create_employee(memory_db, "Boss", "The", is_employee=True)
        create_employee(memory_db, "Worker", "A", is_employee=True, supervisor_id=sup_id)
        create_employee(memory_db, "Loner", "B", is_employee=True)
        stats = get_employee_stats(memory_db)
        # Boss + Loner have no supervisor
        assert stats["unassigned_manager"] == 2

    def test_by_role_breakdown(self, memory_db):
        _seed_roles(memory_db)
        create_employee(memory_db, "A", "A", is_employee=True, role_id=1)
        create_employee(memory_db, "B", "B", is_employee=True, role_id=1)
        create_employee(memory_db, "C", "C", is_employee=True, role_id=2)
        stats = get_employee_stats(memory_db)
        assert stats["by_role"]["Pipefitter"] == 2
        assert stats["by_role"]["Welder"] == 1


class TestListPotentialManagers:
    def test_returns_active_sorted(self, memory_db):
        create_employee(memory_db, "Zeta", "Al", is_employee=True, status="active")
        create_employee(memory_db, "Alpha", "Bob", is_employee=True, status="active")
        create_employee(memory_db, "Gone", "Tom", is_employee=True, status="terminated")
        mgrs = list_potential_managers(memory_db)
        assert len(mgrs) == 2
        assert mgrs[0]["last_name"] == "Alpha"
        assert mgrs[1]["last_name"] == "Zeta"

    def test_includes_role_name(self, memory_db):
        _seed_roles(memory_db)
        create_employee(memory_db, "Smith", "Jane", is_employee=True, role_id=1)
        mgrs = list_potential_managers(memory_db)
        assert mgrs[0]["role_name"] == "Pipefitter"
