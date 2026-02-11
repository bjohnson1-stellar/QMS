"""
Tests for the projection overhaul features.

Covers: period jobs, toggles, calculate with toggles, snapshots with details,
list/activate/commit/uncommit snapshots, budget summary, negative budgets.
"""

import pytest

from qms.projects.budget import (
    activate_snapshot,
    bulk_toggle_period_jobs,
    calculate_projection,
    commit_snapshot,
    create_projection_period,
    create_projection_snapshot,
    get_budget_summary,
    get_settings,
    get_snapshot_with_details,
    has_committed_projections,
    list_snapshots,
    load_period_jobs,
    sync_budget_rollup,
    toggle_period_job,
    uncommit_snapshot,
)


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


def _seed_allocation(conn, project_id, bu_id, budget=50000, subjob="00", projection_enabled=1, is_gmp=0):
    """Insert a project allocation and return its id."""
    proj = conn.execute("SELECT number FROM projects WHERE id = ?", (project_id,)).fetchone()
    bu = conn.execute("SELECT code FROM business_units WHERE id = ?", (bu_id,)).fetchone()
    job_code = f"{proj['number']}-{bu['code']}-{subjob}"
    cursor = conn.execute(
        """INSERT INTO project_allocations
           (project_id, business_unit_id, subjob, job_code,
            allocated_budget, weight_adjustment, projection_enabled, is_gmp)
           VALUES (?, ?, ?, ?, ?, 1.0, ?, ?)""",
        (project_id, bu_id, subjob, job_code, budget, projection_enabled, is_gmp),
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

    def test_excludes_zero_budget(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db)
        _seed_allocation(memory_db, pid, bu_id, budget=0)
        period = _seed_period(memory_db)

        jobs = load_period_jobs(memory_db, period["id"])
        assert len(jobs) == 0

    def test_excludes_inactive_stage(self, memory_db):
        _seed_settings(memory_db)
        bu_id = _seed_bu(memory_db)
        pid = _seed_project(memory_db, stage="Archive")
        _seed_allocation(memory_db, pid, bu_id, budget=50000)
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
