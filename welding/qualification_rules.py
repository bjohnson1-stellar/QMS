"""
Multi-Code Qualification Derivation Engine.

Derives "Range Qualified" from "Actual Values" on WPQ and BPQR forms
using ASME BPVC Section IX and AWS D1.1 rules.

Plugin architecture: each welding code is a QualificationCode subclass
registered via register_code(). Adding a new code (API 1104, EN ISO 9606)
requires only one new class.

Usage:
    from qms.welding.qualification_rules import derive_qualified_ranges
    result = derive_qualified_ranges(data, "wpq", conn)
    print(result.per_code)       # per-code ranges
    print(result.governing)      # most restrictive intersection
"""

from __future__ import annotations

import re
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UNLIMITED = 999.0  # Sentinel for unlimited thickness/diameter


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DerivationResult:
    """Result of running all applicable codes against a single record."""
    per_code: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    governing: Dict[str, Any] = field(default_factory=dict)
    governing_code: Dict[str, str] = field(default_factory=dict)
    rules_fired: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    skipped_fields: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ABC + Registry
# ---------------------------------------------------------------------------

class QualificationCode(ABC):
    """Base class for a welding/brazing qualification code."""

    @property
    @abstractmethod
    def code_id(self) -> str:
        """Short identifier, e.g. 'asme_ix'."""
        ...

    @property
    @abstractmethod
    def code_name(self) -> str:
        """Display name, e.g. 'ASME BPVC Section IX'."""
        ...

    @property
    @abstractmethod
    def applicable_form_types(self) -> List[str]:
        """Form types this code can derive ranges for, e.g. ['wpq', 'bpqr']."""
        ...

    @abstractmethod
    def derive_thickness(
        self, parent: Dict[str, Any], form_type: str,
    ) -> Optional[Tuple[float, float, str]]:
        """Return (min, max, reference) or None if not derivable."""
        ...

    @abstractmethod
    def derive_diameter(
        self, parent: Dict[str, Any], form_type: str,
    ) -> Optional[Tuple[float, float, str]]:
        """Return (min, max, reference) or None."""
        ...

    @abstractmethod
    def derive_positions(
        self, parent: Dict[str, Any], form_type: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Optional[Tuple[str, Optional[str], str]]:
        """Return (groove_positions, fillet_positions_or_None, reference) or None."""
        ...

    @abstractmethod
    def derive_backing(
        self, parent: Dict[str, Any], form_type: str,
    ) -> Optional[Tuple[str, str]]:
        """Return (backing_type, reference) or None."""
        ...

    def derive_supplemental(
        self, parent: Dict[str, Any], form_type: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Tuple[Any, str]]:
        """Code-specific extra fields. Returns {field_name: (value, reference)}."""
        return {}


_CODE_REGISTRY: Dict[str, QualificationCode] = {}


def register_code(code: QualificationCode) -> None:
    """Register a QualificationCode implementation."""
    _CODE_REGISTRY[code.code_id] = code


def get_code(code_id: str) -> QualificationCode:
    """Get a registered code by ID."""
    if code_id not in _CODE_REGISTRY:
        valid = ", ".join(sorted(_CODE_REGISTRY.keys()))
        raise ValueError(f"Unknown code '{code_id}'. Registered: {valid}")
    return _CODE_REGISTRY[code_id]


def list_codes() -> List[str]:
    """Return sorted list of registered code IDs."""
    return sorted(_CODE_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_od(diameter_str: Optional[str]) -> Optional[float]:
    """
    Parse a diameter string like '2" N.P.S (2.375" OD)' or '2-7/8' or '24'
    into a float in inches.
    """
    if not diameter_str:
        return None
    s = str(diameter_str).strip()

    # Try to find explicit OD value like '2.375" OD'
    m = re.search(r'([\d.]+)\s*["\u201d]?\s*OD', s, re.IGNORECASE)
    if m:
        return float(m.group(1))

    # Try fraction like '2-7/8' or '2-1/8'
    m = re.match(r'^(\d+)-(\d+)/(\d+)$', s)
    if m:
        return int(m.group(1)) + int(m.group(2)) / int(m.group(3))

    # Try simple fraction like '7/8'
    m = re.match(r'^(\d+)/(\d+)$', s)
    if m:
        return int(m.group(1)) / int(m.group(2))

    # Try plain number
    m = re.match(r'^[\d.]+$', s)
    if m:
        return float(s)

    return None


def _parse_position(pos_str: Optional[str]) -> Optional[str]:
    """Normalize position string: '6G' -> '6G', '2g' -> '2G'."""
    if not pos_str:
        return None
    return str(pos_str).strip().upper()


def _has_backing(parent: Dict[str, Any]) -> bool:
    """Determine if the test was WITH backing."""
    backing = str(parent.get("backing_actual", "") or "").lower()
    if not backing:
        return True  # Default assumption
    no_backing_indicators = [
        "open root", "without", "n/a", "none", "no backing",
        "single sided", "consumable insert",
    ]
    for indicator in no_backing_indicators:
        if indicator in backing:
            return False
    return True


# ---------------------------------------------------------------------------
# ASME BPVC Section IX Implementation
# ---------------------------------------------------------------------------

class ASMEIXCode(QualificationCode):
    """ASME Boiler & Pressure Vessel Code, Section IX qualification rules."""

    @property
    def code_id(self) -> str:
        return "asme_ix"

    @property
    def code_name(self) -> str:
        return "ASME BPVC Section IX"

    @property
    def applicable_form_types(self) -> List[str]:
        return ["wpq", "bpqr"]

    # -- Thickness ----------------------------------------------------------

    def derive_thickness(
        self, parent: Dict[str, Any], form_type: str,
    ) -> Optional[Tuple[float, float, str]]:
        t = parent.get("coupon_thickness")
        if t is None:
            return None
        t = float(t)

        if form_type == "bpqr":
            return self._derive_thickness_brazing(t)
        return self._derive_thickness_welding(t)

    def _derive_thickness_welding(self, t: float) -> Tuple[float, float, str]:
        """QW-452.1 thickness ranges for welding."""
        if t < 1 / 16:
            return (t, t, "QW-452.1(a)")
        elif t < 3 / 8:
            return (1 / 16, 2 * t, "QW-452.1(b)")
        else:
            return (1 / 16, UNLIMITED, "QW-452.1(c)")

    def _derive_thickness_brazing(self, t: float) -> Tuple[float, float, str]:
        """QB-452.1 thickness ranges for brazing."""
        if t < 1 / 16:
            return (t, t, "QB-452.1(a)")
        elif t < 3 / 16:
            return (1 / 16, 2 * t, "QB-452.1(b)")
        else:
            return (1 / 16, UNLIMITED, "QB-452.1(c)")

    # -- Diameter -----------------------------------------------------------

    def derive_diameter(
        self, parent: Dict[str, Any], form_type: str,
    ) -> Optional[Tuple[float, float, str]]:
        od = _parse_od(parent.get("coupon_diameter"))
        if od is None:
            return None

        if form_type == "bpqr":
            return self._derive_diameter_brazing(od)
        return self._derive_diameter_welding(od)

    def _derive_diameter_welding(self, od: float) -> Tuple[float, float, str]:
        """QW-452.3 pipe diameter qualification ranges."""
        if od < 1.0:
            return (od, 1.0, "QW-452.3(a)")
        elif od < 2.875:
            return (1.0, UNLIMITED, "QW-452.3(b)")
        else:
            return (2.875, UNLIMITED, "QW-452.3(c)")

    def _derive_diameter_brazing(self, od: float) -> Tuple[float, float, str]:
        """QB-452.3 pipe diameter qualification ranges for brazing."""
        if od < 1.0:
            return (od, 1.0, "QB-452.3(a)")
        elif od < 2.875:
            return (1.0, UNLIMITED, "QB-452.3(b)")
        else:
            return (2.875, UNLIMITED, "QB-452.3(c)")

    # -- Positions ----------------------------------------------------------

    # QW-461.9 position qualification matrix
    _GROOVE_POSITION_MAP = {
        "1G": ["1G"],
        "2G": ["1G", "2G"],
        "3G": ["1G", "3G"],
        "4G": ["1G", "4G"],
        "5G": ["1G", "2G", "3G", "4G", "5G"],
        "6G": ["1G", "2G", "3G", "4G", "5G", "6G"],
        "6GR": ["1G", "2G", "3G", "4G", "5G", "6G", "6GR"],
    }

    _FILLET_FROM_GROOVE = {
        "1G": ["1F"],
        "2G": ["1F", "2F"],
        "3G": ["1F", "2F", "3F"],
        "4G": ["1F", "4F"],
        "5G": ["1F", "2F", "3F", "4F", "5F"],
        "6G": ["1F", "2F", "3F", "4F", "5F"],
        "6GR": ["1F", "2F", "3F", "4F", "5F"],
    }

    _FILLET_POSITION_MAP = {
        "1F": ["1F"],
        "2F": ["1F", "2F"],
        "3F": ["1F", "3F"],
        "4F": ["1F", "4F"],
        "5F": ["1F", "2F", "3F", "4F", "5F"],
    }

    def derive_positions(
        self, parent: Dict[str, Any], form_type: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Optional[Tuple[str, Optional[str], str]]:
        pos = _parse_position(parent.get("test_position"))
        if not pos:
            return None

        if form_type == "bpqr":
            # Brazing positions are simpler
            return self._derive_positions_brazing(pos)

        groove_quals = self._GROOVE_POSITION_MAP.get(pos)
        fillet_quals = self._FILLET_FROM_GROOVE.get(pos)

        if groove_quals is None:
            # Check if it's a fillet-only position
            fillet_only = self._FILLET_POSITION_MAP.get(pos)
            if fillet_only:
                return (
                    "N/A",
                    ", ".join(fillet_only),
                    "QW-461.9",
                )
            return None

        groove_str = "All" if len(groove_quals) >= 6 else ", ".join(groove_quals)
        fillet_str = "All" if fillet_quals and len(fillet_quals) >= 5 else (
            ", ".join(fillet_quals) if fillet_quals else None
        )

        return (groove_str, fillet_str, "QW-461.9")

    def _derive_positions_brazing(
        self, pos: str,
    ) -> Tuple[str, Optional[str], str]:
        """QB-461 brazing position rules — simpler than welding."""
        # In brazing, flat qualifies flat; any elevated position qualifies all
        flat_positions = {"1", "FLAT", "1F", "1G"}
        if pos in flat_positions:
            return ("Flat", None, "QB-461")
        return ("All", None, "QB-461")

    # -- Backing ------------------------------------------------------------

    def derive_backing(
        self, parent: Dict[str, Any], form_type: str,
    ) -> Optional[Tuple[str, str]]:
        if form_type == "bpqr":
            return None  # Not applicable to brazing

        has_bk = _has_backing(parent)
        if not has_bk:
            return ("With or Without", "QW-402.4")
        else:
            return ("With Only", "QW-402.4")

    # -- Supplemental (P/F numbers, deposit thickness, expiration) ----------

    def derive_supplemental(
        self, parent: Dict[str, Any], form_type: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Tuple[Any, str]]:
        result: Dict[str, Tuple[Any, str]] = {}

        if form_type == "wpq":
            result.update(self._derive_pf_numbers_wpq(parent))
            result.update(self._derive_deposit_thickness(parent))
            result.update(self._derive_filler_type(parent))

        if form_type == "bpqr":
            result.update(self._derive_pf_numbers_bpqr(parent))
            result.update(self._derive_joint_overlap(parent))

        return result

    def _derive_pf_numbers_wpq(
        self, parent: Dict[str, Any],
    ) -> Dict[str, Tuple[Any, str]]:
        """QW-423 P-number and QW-433 F-number cascade rules."""
        result: Dict[str, Tuple[Any, str]] = {}

        # P-number cascade: QW-423
        p_actual = parent.get("p_number_actual", "")
        if p_actual:
            p_qualified = self._expand_p_number(p_actual)
            if p_qualified:
                result["p_number_qualified"] = (p_qualified, "QW-423")

        # F-number cascade: QW-433
        f_actual = parent.get("f_number_actual", "")
        if f_actual:
            f_qualified = self._expand_f_number(f_actual)
            if f_qualified:
                result["f_number_qualified"] = (f_qualified, "QW-433")

        return result

    def _expand_p_number(self, p_str: str) -> Optional[str]:
        """
        QW-423: P-number cascade.
        P-1 qualifies P-1 through P-11 and P-4X group.
        Higher P-numbers qualify only themselves.
        """
        # Extract numeric P-numbers
        nums = re.findall(r'P-?(\d+)', p_str, re.IGNORECASE)
        if not nums:
            return None

        base_p = min(int(n) for n in nums)

        # QW-423.1: P-1 through P-11 and P-4X
        if base_p <= 11:
            return "P-1 thru P-11 & P-4X"

        # QW-423.2: Higher P-numbers qualify only themselves
        return f"P-{base_p}"

    def _expand_f_number(self, f_str: str) -> Optional[str]:
        """
        QW-433: F-number cascade.
        Higher F-numbers qualify lower F-numbers within the same group.
        F4 -> F4, F3, F2, F1
        """
        nums = re.findall(r'F-?(\d+)', f_str, re.IGNORECASE)
        if not nums:
            return None

        max_f = max(int(n) for n in nums)

        # F-number cascade: higher qualifies all lower
        qualified = [f"F{i}" for i in range(max_f, 0, -1)]
        return ", ".join(qualified)

    def _derive_pf_numbers_bpqr(
        self, parent: Dict[str, Any],
    ) -> Dict[str, Tuple[Any, str]]:
        """QB-423/QB-432 P/F-number rules for brazing."""
        result: Dict[str, Tuple[Any, str]] = {}

        p_actual = parent.get("p_number_actual", "")
        if p_actual:
            # Brazing P-number qualification is same-group only
            result["p_number_qualified"] = (p_actual, "QB-423")

        f_num = parent.get("f_number")
        if f_num is not None:
            result["f_number_qualified"] = (str(f_num), "QB-432")

        return result

    def _derive_deposit_thickness(
        self, parent: Dict[str, Any],
    ) -> Dict[str, Tuple[Any, str]]:
        """QW-452.5: Deposit thickness qualification."""
        deposit = parent.get("deposit_thickness_actual")
        if deposit is None:
            return {}

        deposit = float(deposit)
        # QW-452.5: Qualified to 2× actual deposit thickness
        max_deposit = 2 * deposit
        return {"deposit_thickness_max": (max_deposit, "QW-452.5")}

    def _derive_filler_type(
        self, parent: Dict[str, Any],
    ) -> Dict[str, Tuple[Any, str]]:
        """Filler type qualification passthrough."""
        filler = parent.get("filler_type")
        if filler:
            return {"filler_type_qualified": (filler, "QW-404")}
        return {}

    def _derive_joint_overlap(
        self, parent: Dict[str, Any],
    ) -> Dict[str, Tuple[Any, str]]:
        """QB-452: Joint type and overlap qualification for brazing."""
        result: Dict[str, Tuple[Any, str]] = {}

        joint = parent.get("joint_type")
        if joint:
            # Socket/lap qualifies same; butt qualifies butt
            result["joint_type_qualified"] = (joint, "QB-402.1")

        overlap = parent.get("overlap_length")
        if overlap is not None:
            result["overlap_qualified"] = (
                f"{float(overlap):.3f}\" and greater",
                "QB-452.2",
            )

        return result


register_code(ASMEIXCode())


# ---------------------------------------------------------------------------
# AWS D1.1 Implementation
# ---------------------------------------------------------------------------

class AWSD11Code(QualificationCode):
    """AWS D1.1 Structural Welding Code — Steel, welder qualification rules."""

    @property
    def code_id(self) -> str:
        return "aws_d1_1"

    @property
    def code_name(self) -> str:
        return "AWS D1.1"

    @property
    def applicable_form_types(self) -> List[str]:
        return ["wpq"]  # AWS D1.1 doesn't cover brazing

    # -- Thickness ----------------------------------------------------------

    def derive_thickness(
        self, parent: Dict[str, Any], form_type: str,
    ) -> Optional[Tuple[float, float, str]]:
        t = parent.get("coupon_thickness")
        if t is None:
            return None
        t = float(t)

        # AWS D1.1 Table 6.11 thickness qualification
        if t < 3 / 8:
            return (1 / 8, 2 * t, "Table 6.11")
        elif t < 1.0:
            return (1 / 8, 2 * t, "Table 6.11")
        else:
            return (1 / 8, UNLIMITED, "Table 6.11")

    # -- Diameter -----------------------------------------------------------

    def derive_diameter(
        self, parent: Dict[str, Any], form_type: str,
    ) -> Optional[Tuple[float, float, str]]:
        od = _parse_od(parent.get("coupon_diameter"))
        if od is None:
            return None

        # AWS D1.1 Table 6.11 diameter qualification
        if od < 4.0:
            return (od, 2 * od, "Table 6.11")
        elif od < 24.0:
            return (4.0, UNLIMITED, "Table 6.11")
        else:
            return (4.0, UNLIMITED, "Table 6.11")

    # -- Positions ----------------------------------------------------------

    # AWS D1.1 Table 6.10 position qualification
    _GROOVE_MAP = {
        "1G": ["1G"],
        "2G": ["1G", "2G"],
        "3G": ["1G", "3G"],
        "4G": ["1G", "4G"],
        "5G": ["1G", "2G", "3G", "4G", "5G"],
        "6G": ["1G", "2G", "3G", "4G", "5G", "6G"],
        "6GR": ["1G", "2G", "3G", "4G", "5G", "6G", "6GR"],
    }

    _FILLET_FROM_GROOVE = {
        "1G": ["1F"],
        "2G": ["1F", "2F"],
        "3G": ["1F", "2F", "3F"],
        "4G": ["1F", "4F"],
        "5G": ["1F", "2F", "3F", "4F", "5F"],
        "6G": ["1F", "2F", "3F", "4F", "5F"],
        "6GR": ["1F", "2F", "3F", "4F", "5F"],
    }

    _FILLET_MAP = {
        "1F": ["1F"],
        "2F": ["1F", "2F"],
        "3F": ["1F", "3F"],
        "4F": ["1F", "4F"],
        "5F": ["1F", "2F", "3F", "4F", "5F"],
    }

    def derive_positions(
        self, parent: Dict[str, Any], form_type: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Optional[Tuple[str, Optional[str], str]]:
        pos = _parse_position(parent.get("test_position"))
        if not pos:
            return None

        groove_quals = self._GROOVE_MAP.get(pos)
        fillet_quals = self._FILLET_FROM_GROOVE.get(pos)

        if groove_quals is None:
            fillet_only = self._FILLET_MAP.get(pos)
            if fillet_only:
                return ("N/A", ", ".join(fillet_only), "Table 6.10")
            return None

        groove_str = "All" if len(groove_quals) >= 6 else ", ".join(groove_quals)
        fillet_str = "All" if fillet_quals and len(fillet_quals) >= 5 else (
            ", ".join(fillet_quals) if fillet_quals else None
        )

        return (groove_str, fillet_str, "Table 6.10")

    # -- Backing ------------------------------------------------------------

    def derive_backing(
        self, parent: Dict[str, Any], form_type: str,
    ) -> Optional[Tuple[str, str]]:
        has_bk = _has_backing(parent)
        if not has_bk:
            return ("With or Without", "Clause 6.16")
        else:
            return ("With Only", "Clause 6.16")

    # -- Supplemental (AWS D1.1 doesn't use P/F numbers for WPQ) -----------

    def derive_supplemental(
        self, parent: Dict[str, Any], form_type: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Tuple[Any, str]]:
        return {}


register_code(AWSD11Code())


# ---------------------------------------------------------------------------
# Orchestrator — runs all applicable codes, computes governing values
# ---------------------------------------------------------------------------

def derive_qualified_ranges(
    data: Dict[str, Any],
    form_type: str,
    conn: Optional[sqlite3.Connection] = None,
    force: bool = False,
    codes: Optional[Tuple[str, ...]] = None,
) -> DerivationResult:
    """
    Derive qualification ranges from actual test values.

    Args:
        data: Extraction data dict with 'parent' key containing actual values.
        form_type: 'wpq' or 'bpqr'.
        conn: Optional DB connection for position lookups.
        force: If True, overwrite existing qualified values.
        codes: Tuple of code_ids to apply. None = all applicable.

    Returns:
        DerivationResult with per-code ranges, governing values, and audit trail.
    """
    result = DerivationResult()
    parent = data.get("parent", {})

    if not parent:
        result.warnings.append("No parent data for derivation")
        return result

    # Determine which codes to run
    if codes is None:
        applicable_codes = [
            c for c in _CODE_REGISTRY.values()
            if form_type in c.applicable_form_types
        ]
    else:
        applicable_codes = []
        for cid in codes:
            try:
                code = get_code(cid)
                if form_type in code.applicable_form_types:
                    applicable_codes.append(code)
                else:
                    result.warnings.append(
                        f"Code '{cid}' not applicable to form type '{form_type}'"
                    )
            except ValueError as e:
                result.warnings.append(str(e))

    if not applicable_codes:
        result.warnings.append(f"No applicable codes for form type '{form_type}'")
        return result

    # Run each code
    for code in applicable_codes:
        code_result = _run_single_code(code, parent, form_type, conn, result)
        result.per_code[code.code_id] = code_result

    # Compute governing (most restrictive) values
    _compute_governing(result, form_type)

    return result


def _run_single_code(
    code: QualificationCode,
    parent: Dict[str, Any],
    form_type: str,
    conn: Optional[sqlite3.Connection],
    result: DerivationResult,
) -> Dict[str, Any]:
    """Run one code's derivation methods and collect results."""
    code_data: Dict[str, Any] = {
        "code_id": code.code_id,
        "code_name": code.code_name,
    }

    # Thickness
    try:
        thickness = code.derive_thickness(parent, form_type)
        if thickness:
            t_min, t_max, t_ref = thickness
            code_data["thickness_qualified_min"] = t_min
            code_data["thickness_qualified_max"] = t_max
            code_data["thickness_reference"] = t_ref
            result.rules_fired.append({
                "code": code.code_id, "field": "thickness",
                "reference": t_ref, "min": t_min, "max": t_max,
            })
        else:
            result.skipped_fields.append(f"{code.code_id}:thickness")
    except Exception as e:
        result.warnings.append(f"{code.code_id} thickness error: {e}")

    # Diameter
    try:
        diameter = code.derive_diameter(parent, form_type)
        if diameter:
            d_min, d_max, d_ref = diameter
            code_data["diameter_qualified_min"] = d_min
            code_data["diameter_qualified_max"] = d_max
            code_data["diameter_reference"] = d_ref
            result.rules_fired.append({
                "code": code.code_id, "field": "diameter",
                "reference": d_ref, "min": d_min, "max": d_max,
            })
        else:
            result.skipped_fields.append(f"{code.code_id}:diameter")
    except Exception as e:
        result.warnings.append(f"{code.code_id} diameter error: {e}")

    # Positions
    try:
        positions = code.derive_positions(parent, form_type, conn)
        if positions:
            groove, fillet, p_ref = positions
            code_data["groove_positions_qualified"] = groove
            if fillet is not None:
                code_data["fillet_positions_qualified"] = fillet
            code_data["positions_reference"] = p_ref
            result.rules_fired.append({
                "code": code.code_id, "field": "positions",
                "reference": p_ref, "groove": groove, "fillet": fillet,
            })
        else:
            result.skipped_fields.append(f"{code.code_id}:positions")
    except Exception as e:
        result.warnings.append(f"{code.code_id} positions error: {e}")

    # Backing
    try:
        backing = code.derive_backing(parent, form_type)
        if backing:
            b_type, b_ref = backing
            code_data["backing_type"] = b_type
            result.rules_fired.append({
                "code": code.code_id, "field": "backing",
                "reference": b_ref, "type": b_type,
            })
    except Exception as e:
        result.warnings.append(f"{code.code_id} backing error: {e}")

    # Supplemental
    try:
        supplemental = code.derive_supplemental(parent, form_type, conn)
        for field_name, (value, ref) in supplemental.items():
            code_data[field_name] = value
            result.rules_fired.append({
                "code": code.code_id, "field": field_name,
                "reference": ref, "value": value,
            })
    except Exception as e:
        result.warnings.append(f"{code.code_id} supplemental error: {e}")

    return code_data


def _compute_governing(result: DerivationResult, form_type: str) -> None:
    """
    Compute governing (most restrictive) values across all codes.

    For numeric ranges: governing min = max(all mins), governing max = min(all maxes).
    For position sets: intersection of all qualified sets.
    For text fields: take from first code that provides a value.
    """
    if not result.per_code:
        return

    # Numeric range fields
    range_fields = [
        ("thickness_qualified_min", "thickness_qualified_max"),
        ("diameter_qualified_min", "diameter_qualified_max"),
    ]

    for min_field, max_field in range_fields:
        mins = []
        maxes = []
        governing_min_code = None
        governing_max_code = None

        for code_id, data in result.per_code.items():
            if min_field in data and max_field in data:
                min_val = data[min_field]
                max_val = data[max_field]
                if not mins or min_val > max(mins):
                    governing_min_code = code_id
                if not maxes or max_val < min(maxes):
                    governing_max_code = code_id
                mins.append(min_val)
                maxes.append(max_val)

        if mins and maxes:
            result.governing[min_field] = max(mins)
            result.governing[max_field] = min(maxes)
            result.governing_code[min_field] = governing_min_code
            result.governing_code[max_field] = governing_max_code

    # Single-value numeric fields (deposit thickness max)
    for field_name in ("deposit_thickness_max",):
        values = []
        for code_id, data in result.per_code.items():
            if field_name in data:
                values.append((data[field_name], code_id))
        if values:
            # Most restrictive = smallest max
            val, cid = min(values, key=lambda x: x[0])
            result.governing[field_name] = val
            result.governing_code[field_name] = cid

    # Position fields — intersection
    for field_name in ("groove_positions_qualified", "fillet_positions_qualified"):
        position_sets = []
        for code_id, data in result.per_code.items():
            val = data.get(field_name)
            if val is not None:
                if val == "All":
                    position_sets.append(("All", code_id))
                elif val == "N/A":
                    position_sets.append(("N/A", code_id))
                else:
                    position_sets.append((val, code_id))

        if position_sets:
            # If all say "All", governing is "All"
            if all(v == "All" for v, _ in position_sets):
                result.governing[field_name] = "All"
                result.governing_code[field_name] = position_sets[0][1]
            elif any(v == "N/A" for v, _ in position_sets):
                # If any is N/A (fillet from groove only), skip
                non_na = [(v, c) for v, c in position_sets if v != "N/A"]
                if non_na:
                    result.governing[field_name] = non_na[0][0]
                    result.governing_code[field_name] = non_na[0][1]
            else:
                # Intersection of position sets
                sets = []
                codes_contributing = []
                for v, c in position_sets:
                    if v != "All":
                        positions = {p.strip() for p in v.split(",")}
                        sets.append(positions)
                        codes_contributing.append(c)
                    else:
                        codes_contributing.append(c)

                if sets:
                    intersection = sets[0]
                    for s in sets[1:]:
                        intersection = intersection & s
                    result.governing[field_name] = ", ".join(sorted(intersection))
                    result.governing_code[field_name] = codes_contributing[0]

    # Text fields — first code wins
    text_fields = [
        "backing_type", "p_number_qualified", "f_number_qualified",
        "filler_type_qualified", "joint_type_qualified", "overlap_qualified",
    ]
    for field_name in text_fields:
        for code_id, data in result.per_code.items():
            if field_name in data and field_name not in result.governing:
                result.governing[field_name] = data[field_name]
                result.governing_code[field_name] = code_id

    # Backing special case: "With Only" is more restrictive than "With or Without"
    backing_values = []
    for code_id, data in result.per_code.items():
        bt = data.get("backing_type")
        if bt:
            backing_values.append((bt, code_id))

    if backing_values:
        # "With Only" is more restrictive
        with_only = [(v, c) for v, c in backing_values if "Only" in v]
        if with_only:
            result.governing["backing_type"] = with_only[0][0]
            result.governing_code["backing_type"] = with_only[0][1]
        else:
            result.governing["backing_type"] = backing_values[0][0]
            result.governing_code["backing_type"] = backing_values[0][1]
