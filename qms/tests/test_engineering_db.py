"""Tests for the engineering audit trail (save/retrieve)."""

import json

from qms.engineering.db import save_calculation, save_validation, get_project_by_number


def test_save_calculation(mock_db):
    calc_id = save_calculation(
        discipline="refrigeration",
        calculation_type="line-sizing",
        inputs={"capacity_tons": 100},
        outputs={"nominal_size": 6},
    )
    assert calc_id > 0
    row = mock_db.execute(
        "SELECT * FROM eng_calculations WHERE id=?", (calc_id,)
    ).fetchone()
    assert row["discipline"] == "refrigeration"
    assert "capacity_tons" in row["input_json"]


def test_save_calculation_with_tag(mock_db):
    calc_id = save_calculation(
        discipline="refrigeration",
        calculation_type="relief-valve",
        inputs={},
        outputs={},
        equipment_tag="RV-NH3-001",
    )
    row = mock_db.execute(
        "SELECT * FROM eng_calculations WHERE id=?", (calc_id,)
    ).fetchone()
    assert row["equipment_tag"] == "RV-NH3-001"


def test_save_validation(mock_db, seed_project):
    val_id = save_validation(
        project_id=seed_project,
        item_type="pipe",
        item_tag="L-001",
        extracted_value='4"',
        calculated_value='4"',
        status="PASS",
    )
    assert val_id > 0


def test_get_project_by_number(mock_db, seed_project):
    proj = get_project_by_number("07645")
    assert proj is not None
    assert proj["name"] == "Test Project"


def test_get_project_by_number_not_found(mock_db):
    proj = get_project_by_number("99999")
    assert proj is None
