"""
Output Formatters

Format calculation and validation results for different output modes:
- Human-readable (default)
- JSON (for programmatic use)
- Markdown (for reports)
"""

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class OutputFormat(str, Enum):
    """Output format options."""
    HUMAN = "human"
    JSON = "json"
    MARKDOWN = "markdown"


def format_result(
    result: Any,
    format: OutputFormat = OutputFormat.HUMAN,
    title: Optional[str] = None,
) -> str:
    """
    Format a calculation or validation result.

    Args:
        result: Result object (dataclass or dict)
        format: Output format
        title: Optional title for the output

    Returns:
        Formatted string
    """
    if format == OutputFormat.JSON:
        return format_json(result)
    elif format == OutputFormat.MARKDOWN:
        return format_markdown(result, title)
    else:
        return format_human(result, title)


def format_json(result: Any) -> str:
    """Format result as JSON."""
    if is_dataclass(result):
        data = asdict(result)
    elif hasattr(result, '__dict__'):
        data = result.__dict__
    else:
        data = result

    return json.dumps(data, indent=2, default=str)


def format_human(result: Any, title: Optional[str] = None) -> str:
    """Format result for human reading."""
    lines = []

    if title:
        lines.append(title)
        lines.append("=" * len(title))
        lines.append("")

    if is_dataclass(result):
        data = asdict(result)
    elif hasattr(result, '__dict__'):
        data = result.__dict__
    elif isinstance(result, dict):
        data = result
    else:
        return str(result)

    # Format each field
    max_key_len = max(len(str(k)) for k in data.keys()) if data else 0

    for key, value in data.items():
        label = key.replace('_', ' ').title()

        if isinstance(value, float):
            formatted = f"{value:.3f}" if abs(value) < 100 else f"{value:,.1f}"
        elif isinstance(value, list):
            if value:
                formatted = "\n" + "\n".join(f"  - {v}" for v in value)
            else:
                formatted = "(none)"
        elif isinstance(value, dict):
            formatted = json.dumps(value, indent=2)
        else:
            formatted = str(value)

        lines.append(f"{label:<{max_key_len + 2}}: {formatted}")

    return "\n".join(lines)


def format_markdown(result: Any, title: Optional[str] = None) -> str:
    """Format result as markdown."""
    lines = []

    if title:
        lines.append(f"# {title}")
        lines.append("")

    if is_dataclass(result):
        data = asdict(result)
    elif hasattr(result, '__dict__'):
        data = result.__dict__
    elif isinstance(result, dict):
        data = result
    else:
        return str(result)

    # Create table
    lines.append("| Parameter | Value |")
    lines.append("|-----------|-------|")

    for key, value in data.items():
        label = key.replace('_', ' ').title()

        if isinstance(value, float):
            formatted = f"{value:.3f}" if abs(value) < 100 else f"{value:,.1f}"
        elif isinstance(value, list):
            formatted = ", ".join(str(v) for v in value) if value else "-"
        elif isinstance(value, dict):
            formatted = str(value)
        else:
            formatted = str(value)

        lines.append(f"| {label} | {formatted} |")

    return "\n".join(lines)


def format_validation_report(
    validations: List[Dict],
    format: OutputFormat = OutputFormat.HUMAN,
    project: Optional[str] = None,
) -> str:
    """
    Format validation results as a report.

    Args:
        validations: List of validation results
        format: Output format
        project: Project identifier

    Returns:
        Formatted report
    """
    if format == OutputFormat.JSON:
        return json.dumps(validations, indent=2, default=str)

    # Group by status
    failures = [v for v in validations if v.get('status') == 'FAIL']
    warnings = [v for v in validations if v.get('status') == 'WARNING']
    passed = [v for v in validations if v.get('status') == 'PASS']
    reviews = [v for v in validations if v.get('status') == 'REVIEW']

    lines = []

    if format == OutputFormat.MARKDOWN:
        title = f"Validation Report: Project {project}" if project else "Validation Report"
        lines.append(f"# {title}")
        lines.append("")

        if failures:
            lines.append("## Failures")
            for v in failures:
                lines.append(f"- **{v.get('item_tag', 'Unknown')}**: {v.get('notes', '')}")
            lines.append("")

        if warnings:
            lines.append("## Warnings")
            for v in warnings:
                lines.append(f"- **{v.get('item_tag', 'Unknown')}**: {v.get('notes', '')}")
            lines.append("")

        if reviews:
            lines.append("## Needs Review")
            for v in reviews:
                lines.append(f"- **{v.get('item_tag', 'Unknown')}**: {v.get('notes', '')}")
            lines.append("")

        lines.append("## Summary")
        lines.append(f"- **Passed**: {len(passed)}")
        lines.append(f"- **Warnings**: {len(warnings)}")
        lines.append(f"- **Failures**: {len(failures)}")
        lines.append(f"- **Review**: {len(reviews)}")
    else:
        # Human format
        title = f"VALIDATION REPORT: Project {project}" if project else "VALIDATION REPORT"
        lines.append(title)
        lines.append("=" * len(title))
        lines.append("")

        if failures:
            lines.append(f"FAILURES ({len(failures)}):")
            for v in failures:
                tag = v.get('item_tag', 'Unknown')
                extracted = v.get('extracted_value', '?')
                calculated = v.get('calculated_value', '?')
                notes = v.get('notes', '')
                lines.append(f"  {tag}: Drawing={extracted} | Required={calculated} | {notes}")
            lines.append("")

        if warnings:
            lines.append(f"WARNINGS ({len(warnings)}):")
            for v in warnings:
                tag = v.get('item_tag', 'Unknown')
                extracted = v.get('extracted_value', '?')
                calculated = v.get('calculated_value', '?')
                notes = v.get('notes', '')
                lines.append(f"  {tag}: Drawing={extracted} | Required={calculated} | {notes}")
            lines.append("")

        if reviews:
            lines.append(f"NEEDS REVIEW ({len(reviews)}):")
            for v in reviews:
                tag = v.get('item_tag', 'Unknown')
                notes = v.get('notes', '')
                lines.append(f"  {tag}: {notes}")
            lines.append("")

        lines.append(f"PASSED ({len(passed)}):")
        if len(passed) <= 5:
            for v in passed:
                lines.append(f"  {v.get('item_tag', 'Unknown')}")
        else:
            lines.append("  All other items within tolerance")
        lines.append("")

        lines.append(f"Summary: {len(passed)} PASS | {len(warnings)} WARNING | {len(failures)} FAIL")

    return "\n".join(lines)
