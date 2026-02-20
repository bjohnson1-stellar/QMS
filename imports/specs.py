"""
Import infrastructure data models.

Shared dataclasses used by the import engine and module-specific import specs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ColumnDef:
    """Definition for a single importable column/field."""

    name: str                          # Internal field name (e.g. "last_name")
    label: str                         # Human-readable label
    type: str = "text"                 # text | int | float | date | bool | fk_lookup
    required: bool = False
    aliases: List[str] = field(default_factory=list)  # Alternative header names

    # FK resolution: table + display column → looked up to get the FK id
    fk_table: Optional[str] = None     # e.g. "departments"
    fk_display: Optional[str] = None   # e.g. "name" — matched against import value
    fk_id: Optional[str] = None        # e.g. "id" — the FK value to store

    def all_names(self) -> List[str]:
        """Return all possible names for header matching (lowercase)."""
        names = [self.name.lower(), self.label.lower()]
        names.extend(a.lower() for a in self.aliases)
        return list(dict.fromkeys(names))  # dedupe, preserve order


@dataclass
class ActionItem:
    """A single planned import action (one per source row)."""

    row_index: int
    action_type: str   # insert | update | skip | flag | separate | reactivate
    record_data: Dict[str, Any]
    existing_data: Optional[Dict[str, Any]] = None
    match_method: Optional[str] = None
    changes: Optional[Dict[str, list]] = None  # {field: [old, new]}
    reason: Optional[str] = None
    approved: Optional[bool] = None   # None=pending, True/False
    executed: bool = False
    execution_error: Optional[str] = None

    def to_db_row(self, session_id: str) -> dict:
        """Serialize for import_actions table."""
        return {
            "session_id": session_id,
            "row_index": self.row_index,
            "action_type": self.action_type,
            "record_data": json.dumps(self.record_data),
            "existing_data": json.dumps(self.existing_data) if self.existing_data else None,
            "match_method": self.match_method,
            "changes": json.dumps(self.changes) if self.changes else None,
            "reason": self.reason,
            "approved": 1 if self.approved else (0 if self.approved is False else None),
            "executed": 1 if self.executed else 0,
            "execution_error": self.execution_error,
        }


@dataclass
class ActionPlan:
    """Collection of planned actions for an import session."""

    session_id: str
    items: List[ActionItem] = field(default_factory=list)
    parse_errors: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def by_category(self) -> Dict[str, List[ActionItem]]:
        """Group items by action_type for the review UI."""
        groups: Dict[str, List[ActionItem]] = {}
        for item in self.items:
            groups.setdefault(item.action_type, []).append(item)
        return groups

    @property
    def summary(self) -> Dict[str, int]:
        """Count items by action_type."""
        counts: Dict[str, int] = {}
        for item in self.items:
            counts[item.action_type] = counts.get(item.action_type, 0) + 1
        return counts


@dataclass
class ImportSpec:
    """Module-specific import specification.

    Each module (workforce, welding, etc.) defines one or more ImportSpecs
    that describe how to import data from spreadsheets into that module's tables.
    """

    name: str              # e.g. "employees"
    label: str             # e.g. "Employee Import"
    module: str            # e.g. "workforce"
    target_table: str      # e.g. "employees"
    columns: List[ColumnDef] = field(default_factory=list)

    # Module provides these callbacks:
    match_fn: Optional[Callable] = None       # (conn, record) -> (existing_dict, match_method) | (None, None)
    categorize_fn: Optional[Callable] = None  # (record, existing, match_method) -> ActionItem
    detect_missing_fn: Optional[Callable] = None  # (conn, import_ids) -> list of ActionItems
    execute_fn: Optional[Callable] = None     # (conn, action_item) -> None  (applies one action)

    @property
    def required_columns(self) -> List[ColumnDef]:
        return [c for c in self.columns if c.required]

    @property
    def column_map(self) -> Dict[str, ColumnDef]:
        return {c.name: c for c in self.columns}
