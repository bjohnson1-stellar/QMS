"""
Output formatters for CLI display.

Supports human-readable, JSON, and markdown output modes.
"""

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class OutputFormat(str, Enum):
    HUMAN = "human"
    JSON = "json"
    MARKDOWN = "markdown"


def format_result(
    result: Any,
    fmt: OutputFormat = OutputFormat.HUMAN,
    title: Optional[str] = None,
) -> str:
    """Format a result object for display."""
    if fmt == OutputFormat.JSON:
        return _format_json(result)
    elif fmt == OutputFormat.MARKDOWN:
        return _format_markdown(result, title)
    else:
        return _format_human(result, title)


def _to_dict(result: Any) -> Dict:
    if is_dataclass(result):
        return asdict(result)
    elif hasattr(result, "__dict__"):
        return result.__dict__
    elif isinstance(result, dict):
        return result
    return {"value": str(result)}


def _format_json(result: Any) -> str:
    return json.dumps(_to_dict(result), indent=2, default=str)


def _format_human(result: Any, title: Optional[str] = None) -> str:
    lines = []
    if title:
        lines.extend([title, "=" * len(title), ""])

    data = _to_dict(result)
    max_key_len = max(len(str(k)) for k in data.keys()) if data else 0

    for key, value in data.items():
        label = key.replace("_", " ").title()
        if isinstance(value, float):
            formatted = f"{value:.3f}" if abs(value) < 100 else f"{value:,.1f}"
        elif isinstance(value, list):
            formatted = "\n".join(f"  - {v}" for v in value) if value else "(none)"
            if value:
                formatted = "\n" + formatted
        else:
            formatted = str(value)
        lines.append(f"{label:<{max_key_len + 2}}: {formatted}")

    return "\n".join(lines)


def _format_markdown(result: Any, title: Optional[str] = None) -> str:
    lines = []
    if title:
        lines.extend([f"# {title}", ""])

    data = _to_dict(result)
    lines.extend(["| Parameter | Value |", "|-----------|-------|"])

    for key, value in data.items():
        label = key.replace("_", " ").title()
        if isinstance(value, float):
            formatted = f"{value:.3f}" if abs(value) < 100 else f"{value:,.1f}"
        elif isinstance(value, list):
            formatted = ", ".join(str(v) for v in value) if value else "-"
        else:
            formatted = str(value)
        lines.append(f"| {label} | {formatted} |")

    return "\n".join(lines)
