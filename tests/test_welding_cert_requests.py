"""Tests for the weld certification request workflow."""

import json
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from qms.welding.cert_requests import (
    get_next_wcr_number,
    validate_cert_request_json,
    process_cert_request,
    list_cert_requests,
    get_cert_request_detail,
    enter_coupon_result,
    assign_wpq_from_coupon,
    schedule_retest,
    approve_cert_request,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_welder(memory_db):
    """Insert a test welder. Returns welder id."""
    memory_db.execute(
        """INSERT INTO weld_welder_registry
           (id, employee_number, first_name, last_name, welder_stamp, display_name, status)
           VALUES (100, '12345', 'John', 'Doe', 'Z-15', 'Doe, John', 'active')"""
    )
    memory_db.commit()
    return 100


@pytest.fixture
def sample_wcr_json(tmp_path):
    """Write a valid cert request JSON to a temp file. Returns the path."""
    data = {
        "type": "weld_cert_request",
        "welder": {
            "employee_number": "12345",
            "name": "John Doe",
            "stamp": "Z-15",
        },
        "project": {
            "number": "07645",
            "name": "Test Project",
        },
        "coupons": [
            {
                "process": "SMAW",
                "position": "6G",
                "wps_number": "WPS-001",
                "base_material": "A106",
                "filler_metal": "7018",
                "thickness": "3/4\"",
                "diameter": "6\"",
            },
            {
                "process": "GTAW",
                "position": "2G",
                "wps_number": "WPS-002",
                "base_material": "A312",
                "filler_metal": "ER308",
            },
        ],
        "submitted_by": "Jane Smith",
        "request_date": "2026-02-11",
        "notes": "Rush request",
    }
    path = tmp_path / "WCR-test.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def created_wcr(mock_db, seed_welder, sample_wcr_json):
    """Create a WCR and return its detail dict."""
    result = process_cert_request(sample_wcr_json)
    assert not result["errors"], f"WCR creation failed: {result['errors']}"
    return get_cert_request_detail(result["wcr_number"])


# ---------------------------------------------------------------------------
# WCR Number Generation
# ---------------------------------------------------------------------------

class TestWCRNumberGeneration:
    def test_first_number(self, memory_db):
        num = get_next_wcr_number(memory_db)
        year = date.today().year
        assert num == f"WCR-{year}-0001"

    def test_sequential(self, memory_db):
        year = date.today().year
        # Insert some existing WCRs
        memory_db.execute(
            "INSERT INTO weld_cert_requests (wcr_number, status) VALUES (?, 'completed')",
            (f"WCR-{year}-0003",),
        )
        memory_db.commit()

        num = get_next_wcr_number(memory_db)
        assert num == f"WCR-{year}-0004"

    def test_year_prefix(self, memory_db):
        # Old year WCRs shouldn't affect current year numbering
        memory_db.execute(
            "INSERT INTO weld_cert_requests (wcr_number, status) VALUES ('WCR-2025-0050', 'completed')"
        )
        memory_db.commit()

        year = date.today().year
        num = get_next_wcr_number(memory_db)
        if year != 2025:
            assert num == f"WCR-{year}-0001"


# ---------------------------------------------------------------------------
# JSON Validation
# ---------------------------------------------------------------------------

class TestValidateJSON:
    def test_valid(self):
        data = {
            "welder": {"employee_number": "12345", "name": "John Doe"},
            "coupons": [{"process": "SMAW"}],
        }
        errors = validate_cert_request_json(data)
        assert errors == []

    def test_missing_welder(self):
        data = {"coupons": [{"process": "SMAW"}]}
        errors = validate_cert_request_json(data)
        assert any("welder" in e.lower() for e in errors)

    def test_missing_welder_id(self):
        data = {
            "welder": {"name": "John Doe"},
            "coupons": [{"process": "SMAW"}],
        }
        errors = validate_cert_request_json(data)
        assert any("employee_number" in e or "stamp" in e for e in errors)

    def test_empty_coupons(self):
        data = {
            "welder": {"employee_number": "12345", "name": "John"},
            "coupons": [],
        }
        errors = validate_cert_request_json(data)
        assert any("coupon" in e.lower() for e in errors)

    def test_too_many_coupons(self):
        data = {
            "welder": {"employee_number": "12345", "name": "John"},
            "coupons": [{"process": "SMAW"}] * 5,
        }
        errors = validate_cert_request_json(data)
        assert any("too many" in e.lower() for e in errors)

    def test_invalid_process(self):
        data = {
            "welder": {"employee_number": "12345", "name": "John"},
            "coupons": [{"process": "LAZER"}],
        }
        errors = validate_cert_request_json(data)
        assert any("invalid process" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Process Cert Request
# ---------------------------------------------------------------------------

class TestProcessCertRequest:
    def test_creates_db_rows(self, mock_db, seed_welder, sample_wcr_json):
        result = process_cert_request(sample_wcr_json)

        assert not result["errors"]
        assert result["wcr_number"].startswith("WCR-")
        assert result["welder_id"] == 100
        assert result["welder_stamp"] == "Z-15"
        assert result["coupon_count"] == 2
        assert not result["welder_created"]

        # Verify DB rows
        wcr = mock_db.execute(
            "SELECT * FROM weld_cert_requests WHERE wcr_number = ?",
            (result["wcr_number"],),
        ).fetchone()
        assert wcr is not None
        assert wcr["welder_name"] == "John Doe"
        assert wcr["project_number"] == "07645"

        coupons = mock_db.execute(
            "SELECT * FROM weld_cert_request_coupons WHERE wcr_id = ? ORDER BY coupon_number",
            (wcr["id"],),
        ).fetchall()
        assert len(coupons) == 2
        assert coupons[0]["process"] == "SMAW"
        assert coupons[1]["process"] == "GTAW"

    def test_new_welder_registration(self, mock_db, tmp_path):
        data = {
            "type": "weld_cert_request",
            "welder": {
                "employee_number": "99999",
                "name": "New Welder",
                "is_new": True,
            },
            "coupons": [{"process": "SMAW", "position": "3G"}],
            "submitted_by": "Test",
        }
        path = tmp_path / "new_welder.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        result = process_cert_request(path)
        assert not result["errors"]
        assert result["welder_created"] is True
        assert result["welder_stamp"] is not None

    def test_welder_not_found(self, mock_db, tmp_path):
        data = {
            "type": "weld_cert_request",
            "welder": {
                "employee_number": "00000",
                "name": "Ghost",
            },
            "coupons": [{"process": "SMAW"}],
        }
        path = tmp_path / "ghost.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        result = process_cert_request(path)
        assert result["errors"]
        assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# Results Entry
# ---------------------------------------------------------------------------

class TestEnterResults:
    def test_pass_result(self, created_wcr, mock_db):
        wcr_number = created_wcr["wcr_number"]
        # Must approve first
        approve_cert_request(wcr_number, "admin")

        output = enter_coupon_result(wcr_number, 1, "pass")
        assert not output["errors"]
        assert output["status"] == "passed"

    def test_fail_result(self, created_wcr, mock_db):
        wcr_number = created_wcr["wcr_number"]
        approve_cert_request(wcr_number, "admin")

        output = enter_coupon_result(wcr_number, 2, "fail", failure_reason="Bend test failed")
        assert not output["errors"]
        assert output["status"] == "failed"

    def test_invalid_result_value(self, created_wcr, mock_db):
        output = enter_coupon_result(created_wcr["wcr_number"], 1, "maybe")
        assert output["errors"]

    def test_requires_approved_status(self, created_wcr, mock_db):
        # WCR is pending_approval, should reject
        output = enter_coupon_result(created_wcr["wcr_number"], 1, "pass")
        assert output["errors"]
        assert "pending_approval" in output["errors"][0]

    def test_wcr_status_updates(self, created_wcr, mock_db):
        wcr_number = created_wcr["wcr_number"]
        approve_cert_request(wcr_number, "admin")

        # Pass all coupons -> WCR should become completed
        enter_coupon_result(wcr_number, 1, "pass")
        output = enter_coupon_result(wcr_number, 2, "pass")
        assert output["wcr_status"] == "completed"

    def test_mixed_results_status(self, created_wcr, mock_db):
        wcr_number = created_wcr["wcr_number"]
        approve_cert_request(wcr_number, "admin")

        enter_coupon_result(wcr_number, 1, "pass")
        output = enter_coupon_result(wcr_number, 2, "fail")
        assert output["wcr_status"] == "results_received"


# ---------------------------------------------------------------------------
# WPQ Assignment
# ---------------------------------------------------------------------------

class TestAssignWPQ:
    def test_creates_wpq(self, created_wcr, mock_db):
        wcr_number = created_wcr["wcr_number"]
        approve_cert_request(wcr_number, "admin")
        enter_coupon_result(wcr_number, 1, "pass")

        output = assign_wpq_from_coupon(wcr_number, 1)
        assert not output["errors"]
        assert output["wpq_id"] is not None
        assert output["wpq_number"] is not None
        assert output["expiration_date"] is not None

        # Verify WPQ row
        wpq = mock_db.execute(
            "SELECT * FROM weld_wpq WHERE id = ?", (output["wpq_id"],)
        ).fetchone()
        assert wpq is not None
        assert wpq["process_type"] == "SMAW"
        assert wpq["welder_id"] == 100

    def test_rejects_non_passed_coupon(self, created_wcr, mock_db):
        # Coupon is still 'pending' — can't assign WPQ
        output = assign_wpq_from_coupon(created_wcr["wcr_number"], 1)
        assert output["errors"]
        assert "passed" in output["errors"][0]

    def test_coupon_status_updated(self, created_wcr, mock_db):
        wcr_number = created_wcr["wcr_number"]
        approve_cert_request(wcr_number, "admin")
        enter_coupon_result(wcr_number, 1, "pass")
        assign_wpq_from_coupon(wcr_number, 1)

        detail = get_cert_request_detail(wcr_number)
        coupon = detail["coupons"][0]
        assert coupon["status"] == "wpq_assigned"
        assert coupon["wpq_id"] is not None


# ---------------------------------------------------------------------------
# Retest Scheduling
# ---------------------------------------------------------------------------

class TestScheduleRetest:
    def test_creates_new_wcr(self, created_wcr, mock_db):
        wcr_number = created_wcr["wcr_number"]
        approve_cert_request(wcr_number, "admin")
        enter_coupon_result(wcr_number, 2, "fail")

        output = schedule_retest(wcr_number, 2, notes="Retest needed")
        assert not output["errors"]
        assert output["new_wcr_number"] is not None
        assert output["new_wcr_number"] != wcr_number

        # Verify new WCR has 1 coupon with same process/position
        new_detail = get_cert_request_detail(output["new_wcr_number"])
        assert new_detail is not None
        assert len(new_detail["coupons"]) == 1
        new_coupon = new_detail["coupons"][0]
        original_coupon = created_wcr["coupons"][1]  # coupon 2
        assert new_coupon["process"] == original_coupon["process"]
        assert new_coupon["position"] == original_coupon["position"]

    def test_rejects_non_failed_coupon(self, created_wcr, mock_db):
        # Coupon 1 is 'pending', not 'failed'
        output = schedule_retest(created_wcr["wcr_number"], 1)
        assert output["errors"]
        assert "failed" in output["errors"][0]

    def test_original_coupon_updated(self, created_wcr, mock_db):
        wcr_number = created_wcr["wcr_number"]
        approve_cert_request(wcr_number, "admin")
        enter_coupon_result(wcr_number, 2, "fail")
        schedule_retest(wcr_number, 2)

        detail = get_cert_request_detail(wcr_number)
        coupon_2 = detail["coupons"][1]
        assert coupon_2["status"] == "retest_scheduled"
        assert coupon_2["retest_wcr_id"] is not None


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------

class TestApproval:
    def test_approve(self, created_wcr, mock_db):
        output = approve_cert_request(created_wcr["wcr_number"], "admin")
        assert not output["errors"]
        assert output["status"] == "approved"

    def test_reject_non_pending(self, created_wcr, mock_db):
        approve_cert_request(created_wcr["wcr_number"], "admin")
        output = approve_cert_request(created_wcr["wcr_number"], "admin2")
        assert output["errors"]


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

class TestQueries:
    def test_list_cert_requests(self, created_wcr, mock_db):
        results = list_cert_requests()
        assert len(results) >= 1
        assert results[0]["wcr_number"] == created_wcr["wcr_number"]

    def test_filter_by_status(self, created_wcr, mock_db):
        results = list_cert_requests(status="pending_approval")
        assert len(results) >= 1

        results = list_cert_requests(status="completed")
        wcrs_found = [r for r in results if r["wcr_number"] == created_wcr["wcr_number"]]
        assert len(wcrs_found) == 0

    def test_get_detail(self, created_wcr, mock_db):
        detail = get_cert_request_detail(created_wcr["wcr_number"])
        assert detail is not None
        assert detail["wcr_number"] == created_wcr["wcr_number"]
        assert len(detail["coupons"]) == 2

    def test_detail_not_found(self, mock_db):
        detail = get_cert_request_detail("WCR-9999-9999")
        assert detail is None
