"""Tests for engineering output formatters."""

import json

from qms.engineering.output import format_result, format_validation_report, OutputFormat


def test_format_human_with_title():
    text = format_result({"pressure": 250.0}, title="Relief Valve")
    assert "Relief Valve" in text
    assert "250" in text


def test_format_json_output():
    text = format_result({"orifice": "G"}, format=OutputFormat.JSON)
    data = json.loads(text)
    assert data["orifice"] == "G"


def test_format_markdown_output():
    text = format_result({"size": 4.0}, format=OutputFormat.MARKDOWN)
    assert "| Parameter | Value |" in text


def test_validation_report_with_results():
    validations = [
        {"status": "PASS", "item_tag": "L-001"},
        {"status": "FAIL", "item_tag": "L-002", "extracted_value": "3",
         "calculated_value": "4", "notes": "UNDERSIZED"},
        {"status": "WARNING", "item_tag": "L-003", "extracted_value": "6",
         "calculated_value": "4", "notes": "Oversized"},
    ]
    report = format_validation_report(validations, project="07645")
    assert "FAIL" in report
    assert "L-002" in report
    assert "1 PASS" in report or "Passed" in report


def test_validation_report_empty():
    report = format_validation_report([])
    assert "0 PASS" in report or "Summary" in report
