"""Tests for core output formatters."""

import json

from qms.core.output import format_result, OutputFormat


def test_format_human_with_title():
    text = format_result({"key": "val"}, title="Test Title")
    assert "Test Title" in text
    assert "===" in text


def test_format_json():
    text = format_result({"temp": 28.5}, fmt=OutputFormat.JSON)
    data = json.loads(text)
    assert data["temp"] == 28.5


def test_format_markdown():
    text = format_result({"size": 4.0}, fmt=OutputFormat.MARKDOWN)
    assert "| Parameter | Value |" in text
    assert "Size" in text


def test_format_float_precision():
    text = format_result({"small": 0.12345, "large": 12345.6})
    assert "0.123" in text
    assert "12,345.6" in text


def test_format_list_values():
    text = format_result({"items": ["a", "b"]})
    assert "- a" in text
    assert "- b" in text


def test_format_empty_list():
    text = format_result({"items": []})
    assert "(none)" in text
