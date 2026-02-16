"""
Welding Form Type Registry.

Provides get_form_definition() to retrieve the correct form handler
for any ASME Section IX / QB form type.
"""

from typing import Dict, Optional

from qms.welding.forms.base import BaseFormDefinition, FieldMapping, ValidationRule

_REGISTRY: Dict[str, BaseFormDefinition] = {}


def _ensure_loaded():
    """Lazy-load all form definitions on first access."""
    if _REGISTRY:
        return

    from qms.welding.forms.wps import WPSFormDefinition
    from qms.welding.forms.pqr import PQRFormDefinition
    from qms.welding.forms.wpq import WPQFormDefinition
    from qms.welding.forms.bps import BPSFormDefinition
    from qms.welding.forms.bpq import BPQFormDefinition

    for cls in [WPSFormDefinition, PQRFormDefinition, WPQFormDefinition,
                BPSFormDefinition, BPQFormDefinition]:
        instance = cls()
        _REGISTRY[instance.form_type] = instance


def get_form_definition(form_type: str) -> BaseFormDefinition:
    """
    Get the form definition for a given type.

    Args:
        form_type: One of 'wps', 'pqr', 'wpq', 'bps', 'bpq'.

    Returns:
        BaseFormDefinition subclass instance.

    Raises:
        ValueError: If form_type is not recognized.
    """
    _ensure_loaded()
    key = form_type.lower().strip()
    if key not in _REGISTRY:
        valid = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(f"Unknown form type '{form_type}'. Valid types: {valid}")
    return _REGISTRY[key]


def list_form_types() -> list[str]:
    """Return list of registered form type names."""
    _ensure_loaded()
    return sorted(_REGISTRY.keys())


__all__ = [
    "BaseFormDefinition",
    "FieldMapping",
    "ValidationRule",
    "get_form_definition",
    "list_form_types",
]
