"""
Tests for the projection overhaul features.

Covers: period jobs, toggles, calculate with toggles, snapshots with details,
list/activate/commit/uncommit snapshots, budget summary, negative budgets.
"""

import pytest

from qms.projects.budget import sync_budget_rollup
from qms.timetracker.projections import (
    MAX_ENTRIES_PER_DAY,
    _assign_days_to_jobs,
    _distribute_single_job,
    _get_working_days_mf,
    _group_days_by_week,
    activate_snapshot,
    bulk_toggle_period_jobs,
    calculate_projection,
    commit_snapshot,
    create_projection_period,
    create_projection_snapshot,
    distribute_projection_hours,
    get_budget_summary,
    get_snapshot_with_details,
    has_committed_projections,
    list_snapshots,
    load_period_jobs,
    toggle_period_job,
    uncommit_snapshot,
)
from qms.timetracker.transactions import get_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_bu(conn, code="600", name="Plumbing"):
    """Insert a business unit and return its id."""
    cursor = conn.execute(
        "INSERT INTO business_units (code, name) VALUES (?, ?)", (code, name)
    )
    conn.commit()
    return cursor.lastrowid


def _seed_project(conn, number="07600", name="Test Project", stage="Course of Construction"):
    """Insert a project with budget and return project id."""
    cursor = conn.execute(
        "INSERT INTO projects (number, name, stage, status) VALUES (?, ?, ?, 'active')",
        (number, name, stage),
    )
    pid = cursor.lastrowid
    conn.execute(
        "INSERT INTO project_budgets (project_id, total_budget) VALUES (?, 100000)",
        (pid,),
    )
    conn.commit()
    return pid


def _seed_allocation(conn, project_id, bu_id, budget=50000, subjob="00",
                     projection_enabled=1, is_gmp=0, stage="Course of Construction"):
    """Insert a project allocation and return its id."""
    proj = conn.execute("SELECT number FROM projects WHERE id = ?", (project_id,)).fetchone()
    bu = conn.execute("SELECT code FROM business_units WHERE id = ?", (bu_id,)).fetchone()
    job_code = f"{proj['number']}-{bu['code']}-{subjob}"
    cursor = conn.execute(
        """INSERT INTO project_allocations
           (project_id, business_unit_id, subjob, job_code,
            allocated_budget, weight_adjustment, projection_enabled, is_gmp, stage)
           VALUES (?, ?, ?, ?, ?, 1.0, ?, ?, ?)""",
        (project_id, bu_id, subjob, job_code, budget, projection_enabled, is_gmp, stage),
    )
    conn.commit()
    sync_budget_rollup(conn, project_id)
    conn.commit()
    return cursor.lastrowid


def _seed_period(conn, year=2026, month=2):
    """Create a projection period and return its dict."""
    return create_projection_period(conn, year=year, month=month)


def _seed_settings(conn):
    """Ensure budget_settings row exists."""
    get_settings(conn)


# ---------------------------------------------------------------------------
# TestLoadPeriodJobs
# ---------------------------------------------------------------------------


class TestLoadPeriodJobs:
    def test_auto_populate_from_enabled_allocations(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        aid = _seed_allocation(memory_db, pid, bu_id, budget=50000)
        period = _seed_period(memory_db)

        jobs = load_period_jobs(memory_db, period["id"])
        assert len(jobs) == 1
        assert jobs[0]["allocation_id"] == aid
        assert jobs[0]["included"] == 1

    def test_respects_projection_enabled_flag(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        _seed_allocation(memory_db, pid, bu_id, budget=50000, projection_enabled=0)
        period = _seed_period(memory_db)

        jobs = load_period_jobs(memory_db, period["id"])
        assert len(jobs) == 0

    def test_empty_state_no_allocations(self, memory_db):
        _seed_settings(memory_db)
        period = _seed_period(memory_db)
        jobs = load_period_jobs(memory_db, period["id"])
        assert len(jobs) == 0

    def test_includes_zero_budget(self, memory_db):
        """Zero-budget jobs appear in selection list (but get 0 hours in calculation)."""
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        _seed_allocation(memory_db, pid, bu_id, budget=0)
        period = _seed_period(memory_db)

        jobs = load_period_jobs(memory_db, period["id"])
        assert len(jobs) == 1
        assert jobs[0]["allocated_budget"] == 0

    def test_excludes_inactive_stage(self, memory_db):
        """Allocations with inactive stage (Archive/Lost Proposal/Warranty) are excluded."""
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        _seed_allocation(memory_db, pid, bu_id, budget=50000, stage="Archive")
        period = _seed_period(memory_db)

        jobs = load_period_jobs(memory_db, period["id"])
        assert len(jobs) == 0

    def test_idempotent_on_second_call(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        _seed_allocation(memory_db, pid, bu_id, budget=50000)
        period = _seed_period(memory_db)

        jobs1 = load_period_jobs(memory_db, period["id"])
        jobs2 = load_period_jobs(memory_db, period["id"])
        assert len(jobs1) == len(jobs2) == 1


# ---------------------------------------------------------------------------
# TestTogglePeriodJob
# ---------------------------------------------------------------------------


class TestTogglePeriodJob:
    def test_toggle_off_and_on(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        aid = _seed_allocation(memory_db, pid, bu_id, budget=50000)
        period = _seed_period(memory_db)
        load_period_jobs(memory_db, period["id"])

        toggle_period_job(memory_db, period["id"], aid, False)
        jobs = load_period_jobs(memory_db, period["id"])
        assert jobs[0]["included"] == 0

        toggle_period_job(memory_db, period["id"], aid, True)
        jobs = load_period_jobs(memory_db, period["id"])
        assert jobs[0]["included"] == 1

    def test_toggle_idempotent(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        aid = _seed_allocation(memory_db, pid, bu_id, budget=50000)
        period = _seed_period(memory_db)
        load_period_jobs(memory_db, period["id"])

        toggle_period_job(memory_db, period["id"], aid, False)
        toggle_period_job(memory_db, period["id"], aid, False)
        jobs = load_period_jobs(memory_db, period["id"])
        assert jobs[0]["included"] == 0

    def test_bulk_toggle(self, memory_db):
        _seed_settings(memory_db)
        bu_id1 = _seed_bu(memory_db, "600", "Plumbing")
        bu_id2 = _seed_bu(memory_db, "601", "Mechanical")
        pid = _seed_project(memory_db)
        aid1 = _seed_allocation(memory_db, pid, bu_id1, budget=30000)
        aid2 = _seed_allocation(memory_db, pid, bu_id2, budget=20000, subjob="01")
        period = _seed_period(memory_db)
        load_period_jobs(memory_db, period["id"])

        count = bulk_toggle_period_jobs(memory_db, period["id"], [aid1, aid2], False)
        assert count == 2

        jobs = load_period_jobs(memory_db, period["id"])
        assert all(j["included"] == 0 for j in jobs)


# ---------------------------------------------------------------------------
# TestCalculateWithToggles
# ---------------------------------------------------------------------------


class TestCalculateWithToggles:
    def test_respects_period_toggles(self, memory_db):
        _seed_settings(memory_db)
        bu_id1 = _seed_bu(memory_db, "600", "Plumbing")
        bu_id2 = _seed_bu(memory_db, "601", "Mechanical")
        pid = _seed_project(memory_db)
        aid1 = _seed_allocation(memory_db, pid, bu_id1, budget=60000)
        aid2 = _seed_allocation(memory_db, pid, bu_id2, budget=40000, subjob="01")
        period = _seed_period(memory_db)

        # Calculate with both included
        result = calculate_projection(memory_db, period["id"])
        assert len(result["entries"]) == 2

        # Exclude one
        toggle_period_job(memory_db, period["id"], aid2, False)
        result = calculate_projection(memory_db, period["id"])
        assert len(result["entries"]) == 1
        assert result["entries"][0]["allocation_id"] == aid1

    def test_excluded_jobs_get_zero(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        aid = _seed_allocation(memory_db, pid, bu_id, budget=50000)
        period = _seed_period(memory_db)

        # Exclude the only job
        load_period_jobs(memory_db, period["id"])
        toggle_period_job(memory_db, period["id"], aid, False)
        result = calculate_projection(memory_db, period["id"])
        assert len(result["entries"]) == 0
        assert result["total_cost"] == 0

    def test_locked_period_returns_error(self, memory_db):
        _seed_settings(memory_db)
        period = _seed_period(memory_db)
        memory_db.execute(
            "UPDATE projection_periods SET is_locked = 1 WHERE id = ?",
            (period["id"],),
        )
        memory_db.commit()
        result = calculate_projection(memory_db, period["id"])
        assert "error" in result


# ---------------------------------------------------------------------------
# TestSnapshotWithDetails
# ---------------------------------------------------------------------------


class TestSnapshotWithDetails:
    def test_saves_both_levels(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        aid = _seed_allocation(memory_db, pid, bu_id, budget=50000)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        detail_entries = [{
            "project_id": pid,
            "allocation_id": aid,
            "job_code": "07600-600-00",
            "allocated_hours": 80,
            "projected_cost": 12000,
            "weight_used": 50000,
            "is_manual_override": 0,
        }]

        result = create_projection_snapshot(
            memory_db, period["id"],
            entries=entries,
            detail_entries=detail_entries,
            hourly_rate=150.0,
            total_hours=180,
        )
        assert "id" in result
        assert result["version"] == 1

        snap = get_snapshot_with_details(memory_db, result["id"])
        assert snap is not None
        assert len(snap["entries"]) == 1
        assert len(snap["entries"][0]["details"]) == 1
        assert snap["entries"][0]["details"][0]["job_code"] == "07600-600-00"

    def test_version_increment(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r1 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        r2 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        assert r1["version"] == 1
        assert r2["version"] == 2

    def test_new_snapshot_deactivates_others(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r1 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        r2 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )

        s1 = get_snapshot_with_details(memory_db, r1["id"])
        s2 = get_snapshot_with_details(memory_db, r2["id"])
        assert s1["is_active"] == 0
        assert s2["is_active"] == 1


# ---------------------------------------------------------------------------
# TestListSnapshots
# ---------------------------------------------------------------------------


class TestListSnapshots:
    def test_returns_all_versions_ordered(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )

        snaps = list_snapshots(memory_db, period["id"])
        assert len(snaps) == 2
        assert snaps[0]["version"] > snaps[1]["version"]  # DESC order

    def test_empty_period(self, memory_db):
        _seed_settings(memory_db)
        period = _seed_period(memory_db)
        snaps = list_snapshots(memory_db, period["id"])
        assert len(snaps) == 0


# ---------------------------------------------------------------------------
# TestActivateSnapshot
# ---------------------------------------------------------------------------


class TestActivateSnapshot:
    def test_activates_one_deactivates_others(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r1 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        r2 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )

        # r2 is active, reactivate r1
        ok = activate_snapshot(memory_db, r1["id"])
        assert ok is True

        s1 = get_snapshot_with_details(memory_db, r1["id"])
        s2 = get_snapshot_with_details(memory_db, r2["id"])
        assert s1["is_active"] == 1
        assert s2["is_active"] == 0

    def test_cannot_activate_committed(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        commit_snapshot(memory_db, r["id"])
        ok = activate_snapshot(memory_db, r["id"])
        assert ok is False  # already Committed, not Draft


# ---------------------------------------------------------------------------
# TestCommitSnapshot
# ---------------------------------------------------------------------------


class TestCommitSnapshot:
    def test_commits_and_locks_period(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )

        result = commit_snapshot(memory_db, r["id"])
        assert result["status"] == "Committed"
        assert result["total_hours"] == 80

        # Period should be locked
        row = memory_db.execute(
            "SELECT is_locked FROM projection_periods WHERE id = ?",
            (period["id"],),
        ).fetchone()
        assert row["is_locked"] == 1

    def test_rejects_double_commit(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r1 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        r2 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )

        commit_snapshot(memory_db, r1["id"])
        result = commit_snapshot(memory_db, r2["id"])
        assert "error" in result

    def test_supersedes_other_snapshots(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r1 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        r2 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )

        commit_snapshot(memory_db, r2["id"])
        s1 = get_snapshot_with_details(memory_db, r1["id"])
        assert s1["status"] == "Superseded"


# ---------------------------------------------------------------------------
# TestUncommitSnapshot
# ---------------------------------------------------------------------------


class TestUncommitSnapshot:
    def test_uncommit_reverts_to_draft(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        commit_snapshot(memory_db, r["id"])
        result = uncommit_snapshot(memory_db, r["id"])
        assert result["status"] == "Draft"

        # Period unlocked
        row = memory_db.execute(
            "SELECT is_locked FROM projection_periods WHERE id = ?",
            (period["id"],),
        ).fetchone()
        assert row["is_locked"] == 0

    def test_uncommit_unsupersedes_others(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r1 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        r2 = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )

        commit_snapshot(memory_db, r2["id"])
        uncommit_snapshot(memory_db, r2["id"])

        s1 = get_snapshot_with_details(memory_db, r1["id"])
        assert s1["status"] == "Draft"

    def test_cannot_uncommit_draft(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        result = uncommit_snapshot(memory_db, r["id"])
        assert "error" in result


# ---------------------------------------------------------------------------
# TestBudgetSummary
# ---------------------------------------------------------------------------


class TestBudgetSummary:
    def test_committed_and_projected_costs(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        commit_snapshot(memory_db, r["id"])

        summary = get_budget_summary(memory_db, project_id=pid)
        assert len(summary) == 1
        assert summary[0]["committed_cost"] == 12000
        assert summary[0]["budget_remaining"] == 100000 - 0 - 12000  # no spent

    def test_negative_remaining_allowed(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        # Set tiny budget
        memory_db.execute(
            "UPDATE project_budgets SET total_budget = 5000 WHERE project_id = ?", (pid,)
        )
        memory_db.commit()

        period = _seed_period(memory_db)
        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        commit_snapshot(memory_db, r["id"])

        summary = get_budget_summary(memory_db, project_id=pid)
        assert summary[0]["budget_remaining"] < 0  # Negative is allowed


# ---------------------------------------------------------------------------
# TestNegativeBudget
# ---------------------------------------------------------------------------


class TestNegativeBudget:
    def test_overspent_project_does_not_break_calculation(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        _seed_allocation(memory_db, pid, bu_id, budget=50000)

        # Overspend the budget
        memory_db.execute(
            "INSERT INTO project_transactions (project_id, transaction_date, "
            "transaction_type, description, amount) VALUES (?, '2026-01-01', 'Time', 'Work', 200000)",
            (pid,),
        )
        memory_db.commit()

        period = _seed_period(memory_db)
        result = calculate_projection(memory_db, period["id"])
        assert "error" not in result
        # With remaining_ratio clamped to 0, all weights become 0 → no entries
        # This is correct: overspent projects contribute 0 weight
        assert result["total_cost"] == 0

    def test_mixed_overspent_and_normal(self, memory_db):
        _seed_settings(memory_db)
        bu_id1 = _seed_bu(memory_db, "600", "Plumbing")
        bu_id2 = _seed_bu(memory_db, "601", "Mechanical")

        pid1 = _seed_project(memory_db, number="07600", name="Overspent")
        _seed_allocation(memory_db, pid1, bu_id1, budget=50000)
        memory_db.execute(
            "INSERT INTO project_transactions (project_id, transaction_date, "
            "transaction_type, description, amount) VALUES (?, '2026-01-01', 'Time', 'Work', 200000)",
            (pid1,),
        )

        pid2 = _seed_project(memory_db, number="07601", name="Normal")
        _seed_allocation(memory_db, pid2, bu_id2, budget=50000)

        memory_db.commit()

        period = _seed_period(memory_db)
        result = calculate_projection(memory_db, period["id"])
        assert "error" not in result
        # Both jobs appear, but overspent one gets 0 hours
        assert len(result["entries"]) == 2
        overspent = [e for e in result["entries"] if e["project_id"] == pid1]
        normal = [e for e in result["entries"] if e["project_id"] == pid2]
        assert overspent[0]["allocated_hours"] == 0
        assert normal[0]["allocated_hours"] > 0


# ---------------------------------------------------------------------------
# TestHasCommittedProjections
# ---------------------------------------------------------------------------


class TestHasCommittedProjections:
    def test_returns_true_when_committed(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        commit_snapshot(memory_db, r["id"])

        assert has_committed_projections(memory_db, pid) is True

    def test_returns_false_for_draft_only(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )

        assert has_committed_projections(memory_db, pid) is False

    def test_delete_project_blocked_by_committed(self, memory_db):
        from qms.projects.budget import delete_project

        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        period = _seed_period(memory_db)

        entries = [{"project_id": pid, "allocated_hours": 80, "projected_cost": 12000}]
        r = create_projection_snapshot(
            memory_db, period["id"], entries=entries, hourly_rate=150, total_hours=180,
        )
        commit_snapshot(memory_db, r["id"])

        with pytest.raises(ValueError, match="committed projections"):
            delete_project(memory_db, pid)


# ---------------------------------------------------------------------------
# TestDistributeProjectionHours
# ---------------------------------------------------------------------------


class TestDistributeSingleJob:
    """Unit tests for the pure distribution helper."""

    def test_even_division(self):
        """160 hours / 20 days = 8.0 each, no remainder."""
        result = _distribute_single_job(160, 20)
        assert len(result) == 20
        assert all(h == 8.0 for h in result)
        assert sum(result) == 160

    def test_remainder_spread_evenly(self):
        """47.5 hours / 20 days: base=2.0, 15 days get +0.5."""
        result = _distribute_single_job(47.5, 20)
        assert len(result) == 20
        assert sum(result) == pytest.approx(47.5)
        assert all(h in (2.0, 2.5) for h in result)
        assert result.count(2.5) == 15
        assert result.count(2.0) == 5

    def test_small_hours_across_many_days(self):
        """2.0 hours / 20 days: 4 days get 0.5, rest get 0."""
        result = _distribute_single_job(2.0, 20)
        assert sum(result) == pytest.approx(2.0)
        assert result.count(0.5) == 4
        assert result.count(0.0) == 16

    def test_zero_hours(self):
        result = _distribute_single_job(0, 20)
        assert all(h == 0.0 for h in result)

    def test_zero_days(self):
        result = _distribute_single_job(40, 0)
        assert result == []

    def test_single_day(self):
        result = _distribute_single_job(8.5, 1)
        assert result == [8.5]

    def test_sum_exact_with_odd_total(self):
        """Verify rounding dust is corrected."""
        result = _distribute_single_job(37.5, 22)
        assert sum(result) == pytest.approx(37.5)


class TestAssignDaysToJobs:
    """Unit tests for the day-assignment scheduling algorithm."""

    def test_few_jobs_get_all_days(self):
        """When jobs <= max_per_day, every job gets every day."""
        jobs = [
            {"hours": 80, "job_code": "A"},
            {"hours": 40, "job_code": "B"},
        ]
        _assign_days_to_jobs(jobs, num_days=20, max_per_day=3)
        assert all(j["assigned_days"] == list(range(20)) for j in jobs)

    def test_many_jobs_respects_cap(self):
        """With 6 jobs and max 3/day, no day should have more than 3 entries."""
        jobs = [
            {"hours": 40, "job_code": f"J{i}"}
            for i in range(6)
        ]
        _assign_days_to_jobs(jobs, num_days=20, max_per_day=3)

        day_counts = [0] * 20
        for j in jobs:
            for d in j["assigned_days"]:
                day_counts[d] += 1
        assert all(c <= 3 for c in day_counts), f"Day counts: {day_counts}"

    def test_big_job_gets_more_days(self):
        """A job with more hours should be assigned to more days."""
        jobs = [
            {"hours": 80, "job_code": "BIG"},
            {"hours": 10, "job_code": "SMALL1"},
            {"hours": 10, "job_code": "SMALL2"},
            {"hours": 10, "job_code": "SMALL3"},
        ]
        _assign_days_to_jobs(jobs, num_days=20, max_per_day=3)
        big = next(j for j in jobs if j["job_code"] == "BIG")
        smalls = [j for j in jobs if j["job_code"].startswith("SMALL")]
        assert len(big["assigned_days"]) > max(len(s["assigned_days"]) for s in smalls)

    def test_every_job_gets_at_least_one_day(self):
        """Even tiny jobs should get at least 1 day."""
        jobs = [{"hours": h, "job_code": f"J{i}"} for i, h in enumerate([80, 5, 3, 2, 1])]
        _assign_days_to_jobs(jobs, num_days=20, max_per_day=3)
        assert all(len(j["assigned_days"]) >= 1 for j in jobs)

    def test_total_hours_preserved_per_job(self):
        """After assignment + distribution, each job's total is exact."""
        jobs = [
            {"hours": 60, "job_code": "A"},
            {"hours": 30, "job_code": "B"},
            {"hours": 20, "job_code": "C"},
            {"hours": 10, "job_code": "D"},
        ]
        _assign_days_to_jobs(jobs, num_days=20, max_per_day=3)
        for job in jobs:
            daily = _distribute_single_job(job["hours"], len(job["assigned_days"]))
            assert sum(daily) == pytest.approx(job["hours"])


class TestGroupDaysByWeek:
    def test_february_2026_has_correct_weeks(self):
        days = _get_working_days_mf(2026, 2)
        weeks = _group_days_by_week(days)
        # Feb 2026: W06 (2-6), W07 (9-13), W08 (16-20), W09 (23-27) = 4 full weeks
        assert len(weeks) == 4
        assert all(len(w["days"]) == 5 for w in weeks)

    def test_month_with_partial_weeks(self):
        """January 2026 starts on Thursday → W01 has 2 days."""
        days = _get_working_days_mf(2026, 1)
        weeks = _group_days_by_week(days)
        assert len(weeks[0]["days"]) == 2  # Thu Jan 1, Fri Jan 2
        assert weeks[0]["week_key"] == "2026-W01"


class TestGetWorkingDaysMF:
    def test_february_2026(self):
        days = _get_working_days_mf(2026, 2)
        assert len(days) == 20  # Feb 2026: 20 weekdays
        assert all(d.weekday() < 5 for d in days)
        assert days[0].day == 2  # Feb 1 is Sunday, first weekday is Feb 2

    def test_march_2026(self):
        days = _get_working_days_mf(2026, 3)
        assert len(days) == 22  # March 2026: 22 weekdays
        assert days[0].day == 2  # March 1 is Sunday

    def test_no_weekends(self):
        days = _get_working_days_mf(2026, 1)
        for d in days:
            assert d.weekday() < 5, f"{d} is a weekend"


class TestDistributeProjectionHours:
    """Integration test using snapshot with job-level details."""

    def _make_snapshot_with_details(self, conn):
        """Create a period, project, allocations, calculate, and save snapshot."""
        _seed_settings(conn)
        bu_id = _seed_bu(conn)
        pid = _seed_project(conn)
        aid1 = _seed_allocation(conn, pid, bu_id, budget=50000, subjob="00")
        aid2 = _seed_allocation(conn, pid, bu_id, budget=30000, subjob="01")
        period = _seed_period(conn)

        calc = calculate_projection(conn, period["id"])
        assert "error" not in calc, calc.get("error", "")

        # Build project-level and detail-level entries
        from collections import defaultdict
        proj_map = defaultdict(lambda: {"allocated_hours": 0, "projected_cost": 0})
        detail_entries = []
        for e in calc["entries"]:
            proj_map[e["project_id"]]["allocated_hours"] += e["allocated_hours"]
            proj_map[e["project_id"]]["projected_cost"] += e["projected_cost"]
            detail_entries.append({
                "project_id": e["project_id"],
                "allocation_id": e["allocation_id"],
                "job_code": e["job_code"],
                "allocated_hours": e["allocated_hours"],
                "projected_cost": e["projected_cost"],
                "weight_used": e.get("effective_budget", 0),
            })

        entries = [
            {"project_id": k, "allocated_hours": v["allocated_hours"],
             "projected_cost": v["projected_cost"]}
            for k, v in proj_map.items()
        ]

        snap = create_projection_snapshot(
            conn, period["id"],
            entries=entries,
            detail_entries=detail_entries,
            hourly_rate=calc["hourly_rate"],
            total_hours=calc["total_hours"],
        )
        return snap, period, calc

    def test_returns_schedule(self, memory_db):
        snap, period, calc = self._make_snapshot_with_details(memory_db)
        result = distribute_projection_hours(memory_db, snap["id"])
        assert "error" not in result
        assert result["num_working_days"] == 20  # Feb 2026
        assert len(result["schedule"]) == 20

    def test_total_hours_match_snapshot(self, memory_db):
        snap, period, calc = self._make_snapshot_with_details(memory_db)
        result = distribute_projection_hours(memory_db, snap["id"])
        schedule_total = sum(d["day_total"] for d in result["schedule"])
        assert schedule_total == pytest.approx(result["total_hours"])

    def test_each_day_has_entries(self, memory_db):
        snap, period, calc = self._make_snapshot_with_details(memory_db)
        result = distribute_projection_hours(memory_db, snap["id"])
        for day in result["schedule"]:
            assert isinstance(day["entries"], list)
            assert isinstance(day["day_total"], float)
            assert day["date"]  # ISO date string

    def test_weekly_totals_computed(self, memory_db):
        snap, period, calc = self._make_snapshot_with_details(memory_db)
        result = distribute_projection_hours(memory_db, snap["id"])
        assert len(result["weekly_totals"]) > 0
        # Sum of weekly totals should equal total hours
        weekly_sum = sum(result["weekly_totals"].values())
        assert weekly_sum == pytest.approx(result["total_hours"])

    def test_job_hours_sum_to_allocated(self, memory_db):
        """Each job's distributed hours should sum to its snapshot allocation."""
        snap, period, calc = self._make_snapshot_with_details(memory_db)
        result = distribute_projection_hours(memory_db, snap["id"])

        # Aggregate hours per job code from the schedule
        from collections import defaultdict
        job_totals = defaultdict(float)
        for day in result["schedule"]:
            for entry in day["entries"]:
                job_totals[entry["job_code"]] += entry["hours"]

        # Compare against snapshot detail entries
        snapshot = get_snapshot_with_details(memory_db, snap["id"])
        for proj_entry in snapshot["entries"]:
            for detail in proj_entry.get("details", []):
                if detail["allocated_hours"] > 0:
                    assert job_totals[detail["job_code"]] == pytest.approx(
                        detail["allocated_hours"]
                    ), f"Mismatch for {detail['job_code']}"

    def test_snapshot_not_found(self, memory_db):
        result = distribute_projection_hours(memory_db, 9999)
        assert result["error"] == "Snapshot not found"

    def test_all_entries_half_hour_increments(self, memory_db):
        snap, period, calc = self._make_snapshot_with_details(memory_db)
        result = distribute_projection_hours(memory_db, snap["id"])
        for day in result["schedule"]:
            for entry in day["entries"]:
                assert entry["hours"] % 0.5 == pytest.approx(0), (
                    f"{entry['job_code']} on {day['date']}: {entry['hours']} "
                    f"is not a 0.5 increment"
                )

    def test_max_entries_per_day_enforced(self, memory_db):
        """With many jobs, no day should exceed MAX_ENTRIES_PER_DAY."""
        _seed_settings(memory_db)
        bu_plumb = _seed_bu(memory_db, code="600", name="Plumbing")
        bu_mech = _seed_bu(memory_db, code="650", name="Mechanical")
        bu_elec = _seed_bu(memory_db, code="700", name="Electrical")
        bu_refr = _seed_bu(memory_db, code="750", name="Refrigeration")

        # Create 3 projects × 2 BUs = 6 jobs (exceeds cap of 3/day)
        p1 = _seed_project(memory_db, number="07600", name="P1")
        p2 = _seed_project(memory_db, number="07601", name="P2")
        p3 = _seed_project(memory_db, number="07602", name="P3")

        _seed_allocation(memory_db, p1, bu_plumb, budget=40000, subjob="00")
        _seed_allocation(memory_db, p1, bu_mech, budget=30000, subjob="01")
        _seed_allocation(memory_db, p2, bu_plumb, budget=25000, subjob="00")
        _seed_allocation(memory_db, p2, bu_elec, budget=20000, subjob="01")
        _seed_allocation(memory_db, p3, bu_refr, budget=15000, subjob="00")
        _seed_allocation(memory_db, p3, bu_mech, budget=10000, subjob="01")

        period = _seed_period(memory_db)
        calc = calculate_projection(memory_db, period["id"])
        assert len(calc["entries"]) == 6, f"Expected 6 jobs, got {len(calc['entries'])}"

        # Build snapshot with details
        from collections import defaultdict
        proj_map = defaultdict(lambda: {"allocated_hours": 0, "projected_cost": 0})
        detail_entries = []
        for e in calc["entries"]:
            proj_map[e["project_id"]]["allocated_hours"] += e["allocated_hours"]
            proj_map[e["project_id"]]["projected_cost"] += e["projected_cost"]
            detail_entries.append({
                "project_id": e["project_id"],
                "allocation_id": e["allocation_id"],
                "job_code": e["job_code"],
                "allocated_hours": e["allocated_hours"],
                "projected_cost": e["projected_cost"],
            })

        entries = [
            {"project_id": k, "allocated_hours": v["allocated_hours"],
             "projected_cost": v["projected_cost"]}
            for k, v in proj_map.items()
        ]

        snap = create_projection_snapshot(
            memory_db, period["id"],
            entries=entries,
            detail_entries=detail_entries,
            hourly_rate=calc["hourly_rate"],
            total_hours=calc["total_hours"],
        )

        result = distribute_projection_hours(memory_db, snap["id"])
        assert "error" not in result

        # Verify the cap
        for day in result["schedule"]:
            assert len(day["entries"]) <= MAX_ENTRIES_PER_DAY, (
                f"{day['date']}: {len(day['entries'])} entries exceeds cap of {MAX_ENTRIES_PER_DAY}"
            )

        # Verify all job hours still sum correctly
        from collections import defaultdict as dd
        job_totals = dd(float)
        for day in result["schedule"]:
            for entry in day["entries"]:
                job_totals[entry["job_code"]] += entry["hours"]

        snapshot = get_snapshot_with_details(memory_db, snap["id"])
        for proj_entry in snapshot["entries"]:
            for detail in proj_entry.get("details", []):
                if detail["allocated_hours"] > 0:
                    assert job_totals[detail["job_code"]] == pytest.approx(
                        detail["allocated_hours"]
                    ), f"Hour mismatch for {detail['job_code']}"

    def test_weekly_hours_respect_cap(self, memory_db):
        """No week should exceed the configured max_hours_per_week."""
        snap, period, calc = self._make_snapshot_with_details(memory_db)
        result = distribute_projection_hours(memory_db, snap["id"])
        max_cap = result["max_hours_per_week"]
        for week_key, total in result["weekly_totals"].items():
            assert total <= max_cap + 0.01, (
                f"{week_key}: {total} hrs exceeds cap of {max_cap}"
            )

    def test_custom_max_hours_per_week(self, memory_db):
        """Changing max_hours_per_week in settings is respected."""
        from qms.timetracker.transactions import update_settings
        _seed_settings(memory_db)
        # Lower the weekly cap to 32 hours
        settings = get_settings(memory_db)
        update_settings(
            memory_db,
            company_name=settings["company_name"],
            default_hourly_rate=settings["default_hourly_rate"],
            working_hours_per_month=settings["working_hours_per_month"],
            fiscal_year_start_month=settings["fiscal_year_start_month"],
            gmp_weight_multiplier=settings["gmp_weight_multiplier"],
            max_hours_per_week=32.0,
        )
        snap, period, calc = self._make_snapshot_with_details(memory_db)
        result = distribute_projection_hours(memory_db, snap["id"])
        assert result["max_hours_per_week"] == 32.0
        for week_key, total in result["weekly_totals"].items():
            assert total <= 32.0 + 0.01, (
                f"{week_key}: {total} hrs exceeds custom cap of 32"
            )
