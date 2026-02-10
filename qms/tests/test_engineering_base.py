"""Tests for engineering base classes and data classes."""

import pytest

from qms.engineering.base import (
    ValidationStatus, CalculationResult, ValidationResult, DisciplineCalculator,
)


def test_validation_status_values():
    assert ValidationStatus.PASS.value == "PASS"
    assert ValidationStatus.FAIL.value == "FAIL"
    assert ValidationStatus.WARNING.value == "WARNING"
    assert ValidationStatus.REVIEW.value == "REVIEW"


def test_calculation_result_to_dict():
    r = CalculationResult(calculation_type="test", warnings=["w1"], notes=[])
    d = r.to_dict()
    assert d["calculation_type"] == "test"
    assert d["warnings"] == ["w1"]
    assert d["notes"] == []


def test_validation_result_to_dict():
    v = ValidationResult(
        item_type="pipe", item_tag="L-001", sheet_id=1,
        drawing_number="P-101", extracted_value="4",
        calculated_value="3.5", tolerance_pct=10.0,
        deviation_pct=14.3, status=ValidationStatus.WARNING,
    )
    d = v.to_dict()
    assert d["status"] == "WARNING"  # serialized as string, not enum
    assert d["item_tag"] == "L-001"


def test_discipline_calculator_is_abstract():
    with pytest.raises(TypeError):
        DisciplineCalculator()
