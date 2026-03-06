"""
Tests for the license events system (Phase 7).

Covers: event creation, event listing, auto-expire logic, renewal workflow,
API endpoint validation, and CLI auto-expire command.
"""

import json
import sqlite3
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from contextlib import contextmanager

from qms.licenses.db import (
    create_event,
    create_license,
    get_event,
    get_license,
    get_license_events,
    auto_expire_licenses,
    renew_license,
    VALID_EVENT_TYPES,
    VALID_FEE_TYPES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def license_db(memory_db):
    """Memory DB with a test license inserted."""
    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    memory_db.execute(
        """INSERT INTO state_licenses
               (id, state_code, license_type, license_number, holder_name,
                issued_date, expiration_date, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        ("lic-001", "FL", "Mechanical Contractor", "MC-12345",
         "SIS Industrial Services", "2025-03-01", tomorrow, "active"),
    )
    memory_db.commit()
    return memory_db


@pytest.fixture
def expired_license_db(memory_db):
    """Memory DB with an expired license."""
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    memory_db.execute(
        """INSERT INTO state_licenses
               (id, state_code, license_type, license_number, holder_name,
                issued_date, expiration_date, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        ("lic-expired", "TX", "Master Plumber", "MP-99999",
         "SIS Industrial Services", "2024-03-01", yesterday, "active"),
    )
    memory_db.commit()
    return memory_db


@pytest.fixture
def already_expired_db(memory_db):
    """Memory DB with a license already in expired status."""
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    memory_db.execute(
        """INSERT INTO state_licenses
               (id, state_code, license_type, license_number, holder_name,
                expiration_date, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        ("lic-already-exp", "GA", "Conditioned Air", "CA-11111",
         "SIS Industrial Services", yesterday, "expired"),
    )
    memory_db.commit()
    return memory_db


@pytest.fixture
def flask_app(memory_db):
    """Flask test app with patched DB."""
    from qms.api import create_app

    @contextmanager
    def _get_db(readonly=False):
        yield memory_db

    app = create_app()
    app.config["TESTING"] = True

    with patch("qms.core.db.get_db", _get_db), \
         patch("qms.core.get_db", _get_db), \
         patch("qms.api.licenses.get_db", _get_db):
        yield app


@pytest.fixture
def client(flask_app):
    """Flask test client with auth bypass."""
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user"] = {"id": "test-user", "email": "test@test.com", "role": "admin"}
            sess["modules"] = {"licenses": "admin"}
            sess["_csrf_nonce"] = "test"
        yield c


# ---------------------------------------------------------------------------
# DB Function Tests
# ---------------------------------------------------------------------------

class TestCreateEvent:
    def test_create_event(self, license_db):
        """Create an event with all fields."""
        event = create_event(
            license_db, "lic-001", "renewed", "2026-03-06",
            notes="Annual renewal", fee_amount=150.00, fee_type="renewal",
            created_by="admin",
        )
        assert event is not None
        assert event["license_id"] == "lic-001"
        assert event["event_type"] == "renewed"
        assert event["event_date"] == "2026-03-06"
        assert event["notes"] == "Annual renewal"
        assert event["fee_amount"] == 150.00
        assert event["fee_type"] == "renewal"
        assert event["created_by"] == "admin"

    def test_create_event_with_fee(self, license_db):
        """Event with fee tracking."""
        event = create_event(
            license_db, "lic-001", "amended", "2026-03-06",
            fee_amount=75.50, fee_type="amendment",
        )
        assert event["fee_amount"] == 75.50
        assert event["fee_type"] == "amendment"

    def test_create_event_invalid_license(self, license_db):
        """Non-existent license returns None."""
        event = create_event(license_db, "nonexistent", "issued", "2026-01-01")
        assert event is None

    def test_create_event_audit_logged(self, license_db):
        """Event creation writes audit_log entry."""
        create_event(license_db, "lic-001", "suspended", "2026-03-06")
        rows = license_db.execute(
            "SELECT * FROM audit_log WHERE entity_type = 'license_event'"
        ).fetchall()
        assert len(rows) >= 1
        assert rows[-1]["action"] == "created"


class TestGetLicenseEvents:
    def test_get_events_ordered(self, license_db):
        """Events returned newest-first by event_date."""
        create_event(license_db, "lic-001", "issued", "2025-01-01")
        create_event(license_db, "lic-001", "amended", "2025-06-15")
        create_event(license_db, "lic-001", "renewed", "2026-01-01")

        events = get_license_events(license_db, "lic-001")
        assert len(events) == 3
        assert events[0]["event_date"] == "2026-01-01"
        assert events[1]["event_date"] == "2025-06-15"
        assert events[2]["event_date"] == "2025-01-01"

    def test_get_events_empty(self, license_db):
        """License with no events returns empty list."""
        events = get_license_events(license_db, "lic-001")
        assert events == []


class TestAutoExpire:
    def test_auto_expire_overdue(self, expired_license_db):
        """Active license past expiration → expired + event created."""
        result = auto_expire_licenses(expired_license_db)
        assert result["expired_count"] == 1
        assert result["licenses"][0]["id"] == "lic-expired"

        # Verify status changed
        lic = get_license(expired_license_db, "lic-expired")
        assert lic["status"] == "expired"

        # Verify event created
        events = get_license_events(expired_license_db, "lic-expired")
        assert len(events) == 1
        assert events[0]["event_type"] == "expired"

    def test_auto_expire_skips_future(self, license_db):
        """Active license with future expiration → unchanged."""
        result = auto_expire_licenses(license_db)
        assert result["expired_count"] == 0

        lic = get_license(license_db, "lic-001")
        assert lic["status"] == "active"

    def test_auto_expire_skips_already_expired(self, already_expired_db):
        """License already in 'expired' status → not double-expired."""
        result = auto_expire_licenses(already_expired_db)
        assert result["expired_count"] == 0

    def test_auto_expire_dry_run(self, expired_license_db):
        """dry_run returns what would expire without changing anything."""
        result = auto_expire_licenses(expired_license_db, dry_run=True)
        assert result["expired_count"] == 1

        # Verify nothing actually changed
        lic = get_license(expired_license_db, "lic-expired")
        assert lic["status"] == "active"

        events = get_license_events(expired_license_db, "lic-expired")
        assert events == []


class TestRenewLicense:
    def test_renew_active_license(self, license_db):
        """Renew an active license — updates expiration, creates event."""
        result = renew_license(
            license_db, "lic-001", "2027-03-01",
            fee_amount=200.00, fee_type="renewal", notes="Renewed for 2027",
        )
        assert result is not None
        assert result["expiration_date"] == "2027-03-01"
        assert result["status"] == "active"

        events = get_license_events(license_db, "lic-001")
        assert len(events) == 1
        assert events[0]["event_type"] == "renewed"
        assert events[0]["fee_amount"] == 200.00

    def test_renew_expired_license(self, already_expired_db):
        """Renewing an expired license → reinstated + renewed events, status='active'."""
        result = renew_license(
            already_expired_db, "lic-already-exp", "2027-06-01",
            notes="Reinstated and renewed",
        )
        assert result is not None
        assert result["status"] == "active"
        assert result["expiration_date"] == "2027-06-01"

        events = get_license_events(already_expired_db, "lic-already-exp")
        # Should have both 'reinstated' and 'renewed' events
        event_types = {e["event_type"] for e in events}
        assert "reinstated" in event_types
        assert "renewed" in event_types

    def test_renew_nonexistent_license(self, license_db):
        """Renewing non-existent license returns None."""
        result = renew_license(license_db, "nonexistent", "2027-01-01")
        assert result is None


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------

class TestEventAPI:
    def test_api_get_events(self, client, memory_db):
        """GET events returns JSON array."""
        # Create a license first
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        memory_db.execute(
            """INSERT INTO state_licenses
                   (id, state_code, license_type, license_number, holder_name,
                    expiration_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            ("api-lic-1", "FL", "Mechanical", "MC-API", "Test Co", tomorrow, "active"),
        )
        memory_db.commit()
        create_event(memory_db, "api-lic-1", "issued", "2025-01-01")

        resp = client.get("/licenses/api/licenses/api-lic-1/events")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["event_type"] == "issued"

    def test_api_get_events_not_found(self, client):
        """GET events for non-existent license → 404."""
        resp = client.get("/licenses/api/licenses/nonexistent/events")
        assert resp.status_code == 404

    def test_api_create_event(self, client, memory_db):
        """POST creates event, returns 201."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        memory_db.execute(
            """INSERT INTO state_licenses
                   (id, state_code, license_type, license_number, holder_name,
                    expiration_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            ("api-lic-2", "TX", "Plumber", "PL-API", "Test Co", tomorrow, "active"),
        )
        memory_db.commit()

        resp = client.post(
            "/licenses/api/licenses/api-lic-2/events",
            json={"event_type": "amended", "event_date": "2026-03-06", "notes": "Scope change"},
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["event_type"] == "amended"
        assert data["notes"] == "Scope change"

    def test_api_create_event_invalid_type(self, client, memory_db):
        """Invalid event_type returns 400."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        memory_db.execute(
            """INSERT INTO state_licenses
                   (id, state_code, license_type, license_number, holder_name,
                    expiration_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            ("api-lic-3", "GA", "HVAC", "HV-API", "Test Co", tomorrow, "active"),
        )
        memory_db.commit()

        resp = client.post(
            "/licenses/api/licenses/api-lic-3/events",
            json={"event_type": "bogus", "event_date": "2026-03-06"},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "event_type" in resp.get_json()["errors"][0]

    def test_api_create_event_missing_date(self, client, memory_db):
        """Missing event_date returns 400."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        memory_db.execute(
            """INSERT INTO state_licenses
                   (id, state_code, license_type, license_number, holder_name,
                    expiration_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            ("api-lic-4", "AL", "Plumber", "PL-API2", "Test Co", tomorrow, "active"),
        )
        memory_db.commit()

        resp = client.post(
            "/licenses/api/licenses/api-lic-4/events",
            json={"event_type": "renewed"},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "event_date" in resp.get_json()["errors"][0]

    def test_api_renew_license(self, client, memory_db):
        """POST /renew updates expiration + creates event."""
        memory_db.execute(
            """INSERT INTO state_licenses
                   (id, state_code, license_type, license_number, holder_name,
                    expiration_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            ("api-lic-5", "FL", "Mechanical", "MC-RNW", "Test Co", "2026-06-01", "active"),
        )
        memory_db.commit()

        resp = client.post(
            "/licenses/api/licenses/api-lic-5/renew",
            json={"new_expiration_date": "2027-06-01", "fee_amount": 200, "fee_type": "renewal"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["expiration_date"] == "2027-06-01"

    def test_api_renew_past_date(self, client, memory_db):
        """new_expiration_date in past returns 400."""
        memory_db.execute(
            """INSERT INTO state_licenses
                   (id, state_code, license_type, license_number, holder_name,
                    expiration_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            ("api-lic-6", "TX", "Plumber", "PL-RNW", "Test Co", "2026-06-01", "active"),
        )
        memory_db.commit()

        resp = client.post(
            "/licenses/api/licenses/api-lic-6/renew",
            json={"new_expiration_date": "2020-01-01"},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "future" in resp.get_json()["errors"][0]


# ---------------------------------------------------------------------------
# CLI Tests
# ---------------------------------------------------------------------------

class TestCLI:
    def test_auto_expire_cli(self, cli_runner, memory_db):
        """CLI auto-expire command runs successfully."""
        from qms.licenses.cli import app as licenses_app
        from contextlib import contextmanager

        @contextmanager
        def _get_db(readonly=False):
            yield memory_db

        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        memory_db.execute(
            """INSERT INTO state_licenses
                   (id, state_code, license_type, license_number, holder_name,
                    expiration_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            ("cli-lic-1", "FL", "Mechanical", "MC-CLI", "Test Co", yesterday, "active"),
        )
        memory_db.commit()

        with patch("qms.core.db.get_db", _get_db), \
             patch("qms.core.get_db", _get_db):
            result = cli_runner.invoke(licenses_app, [])
        assert result.exit_code == 0
        assert "Expired 1" in result.output

    def test_auto_expire_cli_dry_run(self, cli_runner, memory_db):
        """CLI auto-expire --dry-run shows what would expire."""
        from qms.licenses.cli import app as licenses_app
        from contextlib import contextmanager

        @contextmanager
        def _get_db(readonly=False):
            yield memory_db

        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        memory_db.execute(
            """INSERT INTO state_licenses
                   (id, state_code, license_type, license_number, holder_name,
                    expiration_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            ("cli-lic-2", "TX", "Plumber", "PL-CLI", "Test Co", yesterday, "active"),
        )
        memory_db.commit()

        with patch("qms.core.db.get_db", _get_db), \
             patch("qms.core.get_db", _get_db):
            result = cli_runner.invoke(licenses_app, ["--dry-run"])
        assert result.exit_code == 0
        assert "Would expire 1" in result.output

        # Verify nothing changed
        lic = memory_db.execute("SELECT status FROM state_licenses WHERE id = 'cli-lic-2'").fetchone()
        assert lic["status"] == "active"


# ---------------------------------------------------------------------------
# Route Context Tests (Plan 07-02)
# ---------------------------------------------------------------------------

class TestDetailPageEvents:
    @pytest.fixture(autouse=True)
    def _page_client(self, flask_app):
        """Client with display_name for base.html template."""
        with flask_app.test_client() as c:
            with c.session_transaction() as sess:
                sess["user"] = {
                    "id": "test-user", "email": "test@test.com",
                    "role": "admin", "display_name": "Test User",
                }
                sess["modules"] = {"licenses": "admin"}
                sess["_csrf_nonce"] = "test"
            self._client = c
            yield

    def test_detail_page_shows_events(self, memory_db):
        """Detail page includes event data in rendered HTML."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        memory_db.execute(
            """INSERT INTO state_licenses
                   (id, state_code, license_type, license_number, holder_name,
                    expiration_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            ("page-lic-1", "OH", "Electrical", "EL-PAGE", "Page Co", tomorrow, "active"),
        )
        memory_db.commit()
        create_event(memory_db, "page-lic-1", "issued", "2025-01-15", notes="Initial issue")

        resp = self._client.get("/licenses/page-lic-1")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Event History" in html
        assert "issued" in html
        assert "2025-01-15" in html
        assert "Initial issue" in html

    def test_detail_page_empty_events(self, memory_db):
        """Detail page shows empty state when no events exist."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        memory_db.execute(
            """INSERT INTO state_licenses
                   (id, state_code, license_type, license_number, holder_name,
                    expiration_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            ("page-lic-2", "CA", "General", "GN-PAGE", "Empty Co", tomorrow, "active"),
        )
        memory_db.commit()

        resp = self._client.get("/licenses/page-lic-2")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Event History" in html
        assert "No events recorded." in html

    def test_detail_page_shows_renew_button(self, memory_db):
        """Detail page shows Renew button for editor/admin users."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        memory_db.execute(
            """INSERT INTO state_licenses
                   (id, state_code, license_type, license_number, holder_name,
                    expiration_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            ("page-lic-3", "NY", "Plumbing", "PL-PAGE", "Renew Co", tomorrow, "active"),
        )
        memory_db.commit()

        resp = self._client.get("/licenses/page-lic-3")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "openRenewModal()" in html
        assert "openEventModal()" in html
