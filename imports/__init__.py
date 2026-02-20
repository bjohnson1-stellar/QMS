"""
QMS Import Infrastructure — shared file parsing, column mapping, and action plan engine.

Usage:
    from qms.imports import ImportSpec, ColumnDef, ActionPlan
    from qms.imports.engine import parse_file, auto_map_columns, generate_action_plan
"""

from qms.imports.specs import ActionItem, ActionPlan, ColumnDef, ImportSpec
