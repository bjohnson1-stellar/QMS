"""Tests for projects.timecard — UKG timecard export logic."""

import pytest
from datetime import date

from qms.timetracker.timecard import (
    clean_job_number,
    distribute_hours,
    format_ukg_transfer,
    generate_timecard_entries,
    generate_timecard_for_pay_period,
    get_working_dates,
)


# ---------------------------------------------------------------------------
# TestCleanJobNumber
# ---------------------------------------------------------------------------


class TestCleanJobNumber:
    def test_strip_00_subjob(self):
        assert clean_job_number("07600-600-00") == "07600-600"

    def test_keep_nonzero_subjob(self):
        assert clean_job_number("06974-230-01") == "06974-230-01"

    def test_two_part_code(self):
        """Two-part codes are already clean (parse_job_code normalizes to -00)."""
        assert clean_job_number("07600-600") == "07600-600"

    def test_base_only(self):
        assert clean_job_number("07600") == "07600"

    def test_invalid_code_passthrough(self):
        assert clean_job_number("INVALID") == "INVALID"

    def test_subjob_02(self):
        assert clean_job_number("12345-100-02") == "12345-100-02"


# ---------------------------------------------------------------------------
# TestFormatUkgTransfer
# ---------------------------------------------------------------------------


class TestFormatUkgTransfer:
    def test_standard_format(self):
        assert format_ukg_transfer("07600-600") == ";;;,,07600-600,,,;"

    def test_with_subjob(self):
        assert format_ukg_transfer("06974-230-01") == ";;;,,06974-230-01,,,;"

    def test_base_only(self):
        assert format_ukg_transfer("07600") == ";;;,,07600,,,;"


# ---------------------------------------------------------------------------
# TestGetWorkingDates
# ---------------------------------------------------------------------------


class TestGetWorkingDates:
    def test_full_week(self):
        # Feb 2-6, 2026 is Mon-Fri
        dates = get_working_dates(date(2026, 2, 2), date(2026, 2, 6))
        # Default Mon-Thu, so Friday excluded
        assert len(dates) == 4
        assert dates[0] == date(2026, 2, 2)  # Monday
        assert dates[-1] == date(2026, 2, 5)  # Thursday

    def test_weekend_excluded(self):
        # Feb 7-8 is Sat-Sun
        dates = get_working_dates(date(2026, 2, 7), date(2026, 2, 8))
        assert len(dates) == 0

    def test_custom_weekdays(self):
        # Mon-Fri
        dates = get_working_dates(
            date(2026, 2, 2), date(2026, 2, 6), weekdays=(0, 1, 2, 3, 4)
        )
        assert len(dates) == 5

    def test_single_day(self):
        dates = get_working_dates(date(2026, 2, 3), date(2026, 2, 3))
        assert len(dates) == 1
        assert dates[0] == date(2026, 2, 3)

    def test_empty_range(self):
        dates = get_working_dates(date(2026, 2, 5), date(2026, 2, 3))
        assert len(dates) == 0

    def test_february_2026_working_days(self):
        """Feb 2026 has 16 Mon-Thu days, matching projection system."""
        dates = get_working_dates(date(2026, 2, 1), date(2026, 2, 28))
        assert len(dates) == 16


# ---------------------------------------------------------------------------
# TestDistributeHours
# ---------------------------------------------------------------------------


class TestDistributeHours:
    def test_even_split(self):
        result = distribute_hours(10.0, 5)
        assert result == [2.0, 2.0, 2.0, 2.0, 2.0]
        assert sum(result) == 10.0

    def test_uneven_split(self):
        result = distribute_hours(10.0, 3)
        assert len(result) == 3
        assert sum(result) == pytest.approx(10.0)

    def test_single_day(self):
        result = distribute_hours(8.5, 1)
        assert result == [8.5]

    def test_zero_hours(self):
        result = distribute_hours(0, 5)
        assert result == []

    def test_zero_days(self):
        result = distribute_hours(10.0, 0)
        assert result == []

    def test_sum_preserved(self):
        """Critical: sum must exactly equal input regardless of rounding."""
        for total in [10.0, 7.33, 15.5, 160.0, 3.33]:
            for days in [1, 3, 4, 7, 16, 22]:
                result = distribute_hours(total, days)
                if result:
                    assert sum(result) == pytest.approx(total, abs=0.01), \
                        f"distribute_hours({total}, {days}) sum={sum(result)}"

    def test_small_hours_many_days(self):
        result = distribute_hours(1.0, 16)
        assert len(result) == 16
        assert sum(result) == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# TestGenerateTimecardEntries (integration with in-memory DB)
# ---------------------------------------------------------------------------


class TestGenerateTimecardEntries:
    @pytest.fixture
    def seeded_db(self, memory_db):
        """Seed DB with a project, allocation, period, snapshot, and entries."""
        db = memory_db

        # Business unit
        db.execute(
            "INSERT INTO business_units (id, code, name) VALUES (1, '600', 'Mechanical')"
        )

        # Project
        db.execute(
            "INSERT INTO projects (id, number, name, status, stage) "
            "VALUES (1, '07600', 'Rosina', 'active', 'Course of Construction')"
        )

        # Budget
        db.execute(
            "INSERT INTO project_budgets (project_id, total_budget) VALUES (1, 50000)"
        )

        # Allocation
        db.execute(
            "INSERT INTO project_allocations "
            "(id, project_id, business_unit_id, subjob, job_code, allocated_budget) "
            "VALUES (1, 1, 1, '00', '07600-600-00', 50000)"
        )

        # Projection period (Feb 2026: 16 working days, 160 hours)
        db.execute(
            "INSERT INTO projection_periods (id, year, month, working_days, total_hours) "
            "VALUES (1, 2026, 2, 16, 160)"
        )

        # Snapshot
        db.execute(
            "INSERT INTO projection_snapshots "
            "(id, period_id, version, name, hourly_rate, total_hours, "
            "total_projected_cost, status, is_active) "
            "VALUES (1, 1, 1, 'v1', 150.0, 160, 24000.0, 'Draft', 1)"
        )

        # Entry: all 160 hours to project 1
        db.execute(
            "INSERT INTO projection_entries "
            "(snapshot_id, project_id, allocated_hours, projected_cost) "
            "VALUES (1, 1, 160.0, 24000.0)"
        )

        db.commit()
        return db

    def test_basic_generation(self, seeded_db):
        result = generate_timecard_entries(seeded_db, 1)
        assert "error" not in result
        assert result["year"] == 2026
        assert result["month"] == 2
        assert result["working_days"] == 16
        assert result["total_hours"] == pytest.approx(160.0, abs=0.1)
        assert len(result["entries"]) == 16  # one entry per day

    def test_entries_have_correct_fields(self, seeded_db):
        result = generate_timecard_entries(seeded_db, 1)
        entry = result["entries"][0]
        assert "date" in entry
        assert "day_name" in entry
        assert entry["project_name"] == "Rosina"
        assert entry["project_code"] == "07600"
        assert entry["job_code"] == "07600-600-00"
        assert entry["cleaned_job_number"] == "07600-600"
        assert entry["pay_code"] == "Hours Worked"
        assert entry["transfer"] == ";;;,,07600-600,,,;"
        assert entry["amount"] > 0

    def test_date_range_filter(self, seeded_db):
        result = generate_timecard_entries(
            seeded_db, 1,
            start_date=date(2026, 2, 9),
            end_date=date(2026, 2, 12),
        )
        assert "error" not in result
        # Feb 9=Mon, 10=Tue, 11=Wed, 12=Thu → 4 working days
        assert result["working_days"] == 4
        assert len(result["entries"]) == 4
        # Pro-rated: 4/16 of 160h = 40h
        assert result["total_hours"] == pytest.approx(40.0, abs=0.1)

    def test_prorate_partial_month(self, seeded_db):
        """Requesting half the month should yield half the hours."""
        result = generate_timecard_entries(
            seeded_db, 1,
            start_date=date(2026, 2, 9),
            end_date=date(2026, 2, 28),
        )
        assert "error" not in result
        # Feb 9-28: 12 Mon-Thu working days out of 16 total
        assert result["working_days"] == 12
        # 12/16 of 160 = 120
        assert result["total_hours"] == pytest.approx(120.0, abs=0.1)

    def test_dates_outside_month_are_clamped(self, seeded_db):
        """Dates beyond the period's month are clamped to month boundary."""
        result = generate_timecard_entries(
            seeded_db, 1,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 3, 15),  # extends into March
        )
        assert "error" not in result
        # Should be clamped to Feb, so full 16 days and 160 hours
        assert result["working_days"] == 16
        assert result["total_hours"] == pytest.approx(160.0, abs=0.1)

    def test_no_active_snapshot(self, memory_db):
        memory_db.execute(
            "INSERT INTO projection_periods (id, year, month, working_days, total_hours) "
            "VALUES (99, 2025, 1, 20, 200)"
        )
        memory_db.commit()
        result = generate_timecard_entries(memory_db, 99)
        assert result["error"] == "No active projection snapshot for this period"

    def test_period_not_found(self, memory_db):
        result = generate_timecard_entries(memory_db, 999)
        assert result["error"] == "Period not found"

    def test_no_allocations_fallback(self, memory_db):
        """Project with no allocations falls back to project number."""
        db = memory_db
        db.execute(
            "INSERT INTO projects (id, number, name, status, stage) "
            "VALUES (2, '99999', 'NoAlloc', 'active', 'Course of Construction')"
        )
        db.execute(
            "INSERT INTO projection_periods (id, year, month, working_days, total_hours) "
            "VALUES (2, 2026, 3, 4, 40)"
        )
        db.execute(
            "INSERT INTO projection_snapshots "
            "(id, period_id, version, name, hourly_rate, total_hours, "
            "total_projected_cost, status, is_active) "
            "VALUES (2, 2, 1, 'v1', 150.0, 40, 6000.0, 'Draft', 1)"
        )
        db.execute(
            "INSERT INTO projection_entries "
            "(snapshot_id, project_id, allocated_hours, projected_cost) "
            "VALUES (2, 2, 40.0, 6000.0)"
        )
        db.commit()

        result = generate_timecard_entries(
            db, 2,
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 5),
        )
        assert "error" not in result
        assert len(result["warnings"]) == 1
        assert "no allocations" in result["warnings"][0].lower()
        assert result["entries"][0]["cleaned_job_number"] == "99999"

    def test_multiple_allocations_split(self, memory_db):
        """Hours are split proportionally when project has multiple allocations."""
        db = memory_db

        db.execute(
            "INSERT INTO business_units (id, code, name) VALUES (10, '600', 'Mech')"
        )
        db.execute(
            "INSERT INTO business_units (id, code, name) VALUES (11, '230', 'Elec')"
        )
        db.execute(
            "INSERT INTO projects (id, number, name, status, stage) "
            "VALUES (3, '06974', 'MultiAlloc', 'active', 'Course of Construction')"
        )
        db.execute(
            "INSERT INTO project_allocations "
            "(project_id, business_unit_id, subjob, job_code, allocated_budget) "
            "VALUES (3, 10, '00', '06974-600-00', 30000)"
        )
        db.execute(
            "INSERT INTO project_allocations "
            "(project_id, business_unit_id, subjob, job_code, allocated_budget) "
            "VALUES (3, 11, '01', '06974-230-01', 10000)"
        )

        db.execute(
            "INSERT INTO projection_periods (id, year, month, working_days, total_hours) "
            "VALUES (3, 2026, 4, 4, 40)"
        )
        db.execute(
            "INSERT INTO projection_snapshots "
            "(id, period_id, version, name, hourly_rate, total_hours, "
            "total_projected_cost, status, is_active) "
            "VALUES (3, 3, 1, 'v1', 150.0, 40, 6000.0, 'Draft', 1)"
        )
        db.execute(
            "INSERT INTO projection_entries "
            "(snapshot_id, project_id, allocated_hours, projected_cost) "
            "VALUES (3, 3, 40.0, 6000.0)"
        )
        db.commit()

        result = generate_timecard_entries(
            db, 3,
            start_date=date(2026, 4, 6),
            end_date=date(2026, 4, 9),
        )
        assert "error" not in result

        # Should have entries for both job codes
        job_codes = set(e["cleaned_job_number"] for e in result["entries"])
        assert "06974-600" in job_codes   # -00 stripped
        assert "06974-230-01" in job_codes  # -01 kept

        # Total should still be 40 hours (pro-rated: 4/4 * 40 = 40)
        assert result["total_hours"] == pytest.approx(40.0, abs=0.1)


# ---------------------------------------------------------------------------
# TestGenerateTimecardForPayPeriod (cross-month)
# ---------------------------------------------------------------------------


class TestGenerateTimecardForPayPeriod:
    @pytest.fixture
    def two_month_db(self, memory_db):
        """Seed DB with two months of projection data."""
        db = memory_db

        # Business unit + project
        db.execute(
            "INSERT INTO business_units (id, code, name) VALUES (1, '600', 'Mechanical')"
        )
        db.execute(
            "INSERT INTO projects (id, number, name, status, stage) "
            "VALUES (1, '07600', 'Rosina', 'active', 'Course of Construction')"
        )
        db.execute(
            "INSERT INTO project_allocations "
            "(id, project_id, business_unit_id, subjob, job_code, allocated_budget) "
            "VALUES (1, 1, 1, '00', '07600-600-00', 50000)"
        )

        # Jan 2026: 17 Mon-Thu days, 170 hours
        db.execute(
            "INSERT INTO projection_periods (id, year, month, working_days, total_hours) "
            "VALUES (1, 2026, 1, 17, 170)"
        )
        db.execute(
            "INSERT INTO projection_snapshots "
            "(id, period_id, version, name, hourly_rate, total_hours, "
            "total_projected_cost, status, is_active) "
            "VALUES (1, 1, 1, 'v1', 150.0, 170, 25500.0, 'Draft', 1)"
        )
        db.execute(
            "INSERT INTO projection_entries "
            "(snapshot_id, project_id, allocated_hours, projected_cost) "
            "VALUES (1, 1, 170.0, 25500.0)"
        )

        # Feb 2026: 16 Mon-Thu days, 160 hours
        db.execute(
            "INSERT INTO projection_periods (id, year, month, working_days, total_hours) "
            "VALUES (2, 2026, 2, 16, 160)"
        )
        db.execute(
            "INSERT INTO projection_snapshots "
            "(id, period_id, version, name, hourly_rate, total_hours, "
            "total_projected_cost, status, is_active) "
            "VALUES (2, 2, 1, 'v1', 150.0, 160, 24000.0, 'Draft', 1)"
        )
        db.execute(
            "INSERT INTO projection_entries "
            "(snapshot_id, project_id, allocated_hours, projected_cost) "
            "VALUES (2, 1, 160.0, 24000.0)"
        )

        db.commit()
        return db

    def test_cross_month_pay_period(self, two_month_db):
        """Pay period spanning Jan 26 - Feb 8 pulls from both months."""
        result = generate_timecard_for_pay_period(
            two_month_db,
            date(2026, 1, 26),
            date(2026, 2, 8),
        )
        assert "error" not in result
        assert len(result["periods"]) == 2

        # Jan 26-31: Mon=26, Tue=27, Wed=28, Thu=29 → 4 working days
        # Feb 1-8: Mon=2, Tue=3, Wed=4, Thu=5 → 4 working days
        assert result["working_days"] == 8

        # Jan: 4/17 * 170 ≈ 40.0; Feb: 4/16 * 160 = 40.0 → ~80 total
        assert result["total_hours"] == pytest.approx(80.0, abs=1.0)

    def test_single_month_via_pay_period(self, two_month_db):
        """Pay period within one month works too."""
        result = generate_timecard_for_pay_period(
            two_month_db,
            date(2026, 2, 9),
            date(2026, 2, 22),
        )
        assert "error" not in result
        assert len(result["periods"]) == 1
        assert result["periods"][0]["year"] == 2026
        assert result["periods"][0]["month"] == 2

    def test_missing_month_warns(self, two_month_db):
        """If a month in the range has no projection, a warning is added."""
        result = generate_timecard_for_pay_period(
            two_month_db,
            date(2026, 2, 23),
            date(2026, 3, 8),
        )
        # Feb should work, March has no projection
        assert any("No projection period for 2026-03" in w for w in result["warnings"])
