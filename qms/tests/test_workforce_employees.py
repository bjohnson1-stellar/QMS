"""Tests for employee CRUD, auto-numbering, and duplicate detection."""

from qms.workforce.employees import (
    create_employee,
    find_employee_by_number,
    find_employee_by_email,
    find_employee_by_phone,
    find_employee_by_name,
    update_employee,
    terminate_employee,
    import_weekly_personnel,
)


class TestCreateEmployee:
    def test_returns_uuid(self, memory_db):
        emp_id = create_employee(memory_db, "Doe", "John", is_employee=True)
        assert len(emp_id) == 36  # UUID v4

    def test_auto_number(self, memory_db):
        create_employee(memory_db, "Smith", "Jane", is_employee=True)
        row = memory_db.execute("SELECT employee_number FROM employees").fetchone()
        assert row["employee_number"] == "EMP-0001"

    def test_second_employee_increments(self, memory_db):
        create_employee(memory_db, "Smith", "Jane", is_employee=True)
        create_employee(memory_db, "Doe", "John", is_employee=True)
        rows = memory_db.execute(
            "SELECT employee_number FROM employees ORDER BY employee_number"
        ).fetchall()
        assert rows[0]["employee_number"] == "EMP-0001"
        assert rows[1]["employee_number"] == "EMP-0002"

    def test_subcontractor_number(self, memory_db):
        create_employee(memory_db, "Contractor", "Bob",
                        is_employee=False, is_subcontractor=True)
        row = memory_db.execute("SELECT subcontractor_number FROM employees").fetchone()
        assert row["subcontractor_number"] == "SUB-0001"


class TestFindEmployee:
    def test_by_number(self, memory_db):
        create_employee(memory_db, "Smith", "Jane", is_employee=True)
        found = find_employee_by_number(memory_db, employee_number="EMP-0001")
        assert found["last_name"] == "Smith"

    def test_by_email(self, memory_db):
        create_employee(memory_db, "Smith", "Jane", email="jane@test.com")
        found = find_employee_by_email(memory_db, "JANE@TEST.COM")
        assert found is not None

    def test_by_phone(self, memory_db):
        # SQL REPLACE strips - ( ) but not spaces, so use a no-space format
        create_employee(memory_db, "Smith", "Jane", phone="555-123-4567")
        found = find_employee_by_phone(memory_db, "5551234567")
        assert found is not None

    def test_by_name(self, memory_db):
        create_employee(memory_db, "Smith", "Jane")
        results = find_employee_by_name(memory_db, "smith", "jane")
        assert len(results) == 1


class TestUpdateEmployee:
    def test_update_position(self, memory_db):
        emp_id = create_employee(memory_db, "Smith", "Jane")
        update_employee(memory_db, emp_id, position="Senior Welder")
        row = memory_db.execute(
            "SELECT position FROM employees WHERE id=?", (emp_id,)
        ).fetchone()
        assert row["position"] == "Senior Welder"

    def test_rejects_unknown_fields(self, memory_db):
        emp_id = create_employee(memory_db, "Smith", "Jane")
        result = update_employee(memory_db, emp_id, hacker_field="bad")
        assert result is False


class TestTerminateEmployee:
    def test_terminates(self, memory_db):
        emp_id = create_employee(memory_db, "Smith", "Jane")
        terminate_employee(memory_db, emp_id, status_reason="Resigned")
        row = memory_db.execute(
            "SELECT status, is_active FROM employees WHERE id=?", (emp_id,)
        ).fetchone()
        assert row["status"] == "terminated"
        assert row["is_active"] == 0


class TestImportWeeklyPersonnel:
    def test_insert_new(self, memory_db):
        records = [{"last_name": "New", "first_name": "Person", "is_employee": True}]
        result = import_weekly_personnel(memory_db, records)
        assert result["inserted"] == 1
        assert result["updated"] == 0

    def test_update_existing(self, memory_db):
        create_employee(memory_db, "Existing", "Employee", email="e@test.com")
        records = [{"last_name": "Existing", "first_name": "Employee",
                     "email": "e@test.com", "position": "Updated"}]
        result = import_weekly_personnel(memory_db, records)
        assert result["updated"] == 1
        assert result["inserted"] == 0

    def test_flags_multiple_name_matches(self, memory_db):
        create_employee(memory_db, "Common", "Name")
        create_employee(memory_db, "Common", "Name", email="c2@test.com")
        records = [{"last_name": "Common", "first_name": "Name"}]
        result = import_weekly_personnel(memory_db, records)
        assert result["flagged_for_review"] == 1
