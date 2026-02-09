"""
Refrigeration Validators

QC validation logic to compare extracted drawing data against calculations.
Validates pipe sizing and relief valve sizing on drawings.
"""

import re
from typing import Any, Dict, List, Optional

from qms.engineering.base import ValidationStatus, ValidationResult
from qms.engineering.refrigeration import run_line_sizing, run_relief_valve


# ---------------------------------------------------------------------------
# Utility: compare_sizes (inlined from disciplines.base)
# ---------------------------------------------------------------------------

def compare_sizes(
    extracted: str,
    calculated: float,
    tolerance_pct: float = 10.0,
) -> tuple:
    """
    Compare extracted size against calculated size.

    Args:
        extracted: Size string from drawing (e.g., '4"', '4', '4 in')
        calculated: Calculated required size (float)
        tolerance_pct: Tolerance percentage

    Returns:
        Tuple of (ValidationStatus, deviation_pct, notes)
    """
    match = re.search(r'(\d+\.?\d*)', str(extracted))
    if not match:
        return ValidationStatus.REVIEW, 0.0, f"Cannot parse size: {extracted}"

    extracted_value = float(match.group(1))

    if calculated == 0:
        return ValidationStatus.REVIEW, 0.0, "Calculated value is zero"

    deviation = ((extracted_value - calculated) / calculated) * 100

    if abs(deviation) <= tolerance_pct:
        return ValidationStatus.PASS, deviation, ""
    elif extracted_value > calculated:
        return ValidationStatus.WARNING, deviation, f"Oversized by {deviation:.0f}%"
    else:
        return ValidationStatus.FAIL, deviation, f"UNDERSIZED by {abs(deviation):.0f}%"


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_pipe_size(size_str: str) -> Optional[float]:
    """
    Parse a pipe size string to float.

    Examples:
        '4"'     -> 4.0
        '2-1/2"' -> 2.5
        '1 1/2'  -> 1.5
        '6'      -> 6.0
    """
    if not size_str:
        return None

    s = str(size_str).strip().replace('"', '').replace("'", '').strip()

    # Handle fractions like "2-1/2" or "1 1/2"
    if '-' in s or ' ' in s:
        parts = re.split(r'[-\s]+', s)
        if len(parts) == 2:
            whole = float(parts[0]) if parts[0] else 0
            if '/' in parts[1]:
                num, den = parts[1].split('/')
                frac = float(num) / float(den)
            else:
                frac = float(parts[1])
            return whole + frac

    # Handle simple fractions
    if '/' in s:
        num, den = s.split('/')
        return float(num) / float(den)

    # Simple number
    try:
        return float(s)
    except ValueError:
        return None


def parse_line_number(line_num: str) -> Dict[str, Any]:
    """
    Parse a line number to extract metadata.

    Format: SIZE-REFRIG-SEQ-AREA or similar
    Example: 2-NH3-101-3A -> size=2, refrigerant=NH3, sequence=101, area=3A

    Returns:
        Dict with parsed components.
    """
    parts = str(line_num).split('-')

    result: Dict[str, Any] = {
        'original': line_num,
        'size': None,
        'refrigerant': None,
        'service': None,
    }

    if len(parts) >= 1:
        size = parse_pipe_size(parts[0])
        if size and size <= 24:  # Reasonable pipe size
            result['size'] = size

    if len(parts) >= 2:
        if parts[1].upper() in ('NH3', 'R22', 'R404A', 'CO2', 'GLY', 'CW'):
            result['refrigerant'] = parts[1].upper()

    return result


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def validate_pipe_sizing(
    project_id: int,
    drawing_number: Optional[str] = None,
    tolerance_pct: float = 10.0,
    save_to_db: bool = True,
) -> List[Dict]:
    """
    Validate pipe sizing on drawings against calculations.

    Args:
        project_id: Project ID to validate
        drawing_number: Optional specific drawing
        tolerance_pct: Tolerance percentage for pass/fail
        save_to_db: Whether to save results to database

    Returns:
        List of validation result dicts
    """
    from qms.engineering import db

    lines = db.get_project_lines(project_id, drawing_number)

    if not lines:
        return [{
            'item_type': 'pipe',
            'item_tag': 'N/A',
            'status': 'REVIEW',
            'notes': 'No lines found in project',
        }]

    results = []

    for line in lines:
        line_num = line.get('line_number', '')
        extracted_size = line.get('size') or line.get('normalized_size')

        if not extracted_size:
            parsed = parse_line_number(line_num)
            extracted_size = parsed.get('size')

        if not extracted_size:
            results.append({
                'item_type': 'pipe',
                'item_tag': line_num,
                'sheet_id': line.get('sheet_id'),
                'drawing_number': line.get('drawing_number'),
                'extracted_value': 'N/A',
                'calculated_value': 'N/A',
                'tolerance_pct': tolerance_pct,
                'deviation_pct': 0,
                'status': 'REVIEW',
                'notes': 'Could not determine pipe size',
            })
            continue

        extracted_float = parse_pipe_size(str(extracted_size))
        if not extracted_float:
            results.append({
                'item_type': 'pipe',
                'item_tag': line_num,
                'sheet_id': line.get('sheet_id'),
                'drawing_number': line.get('drawing_number'),
                'extracted_value': str(extracted_size),
                'calculated_value': 'N/A',
                'tolerance_pct': tolerance_pct,
                'deviation_pct': 0,
                'status': 'REVIEW',
                'notes': f'Could not parse size: {extracted_size}',
            })
            continue

        # Determine line type from service/material
        service = (line.get('service') or '').lower()
        refrigerant = line.get('refrigerant') or 'NH3'

        if 'suction' in service or 'wet' in service:
            line_type = 'wet' if 'wet' in service else 'dry'
        elif 'discharge' in service or 'hot gas' in service:
            line_type = 'discharge'
        elif 'liquid' in service:
            line_type = 'liquid'
        else:
            line_type = 'dry'  # Default assumption

        default_capacity = 50  # tons - would come from linked equipment

        params = {
            'capacity_tons': default_capacity,
            'suction_temp': 28,
            'condensing_temp': 95,
            'length': 100,
            'line_type': line_type,
            'refrigerant': refrigerant,
        }

        try:
            calc_result = run_line_sizing(params)
            calculated_size = calc_result.get('nominal_size', 0)
        except Exception as e:
            results.append({
                'item_type': 'pipe',
                'item_tag': line_num,
                'sheet_id': line.get('sheet_id'),
                'drawing_number': line.get('drawing_number'),
                'extracted_value': str(extracted_size),
                'calculated_value': 'ERROR',
                'tolerance_pct': tolerance_pct,
                'deviation_pct': 0,
                'status': 'REVIEW',
                'notes': f'Calculation error: {e}',
            })
            continue

        status, deviation, notes = compare_sizes(
            str(extracted_float),
            calculated_size,
            tolerance_pct,
        )

        if not notes:
            notes = f'Based on {default_capacity}T @ {line_type}'
        else:
            notes = f'{notes} (based on {default_capacity}T @ {line_type})'

        validation = {
            'item_type': 'pipe',
            'item_tag': line_num,
            'sheet_id': line.get('sheet_id'),
            'drawing_number': line.get('drawing_number'),
            'extracted_value': f'{extracted_float}"',
            'calculated_value': f'{calculated_size}"',
            'tolerance_pct': tolerance_pct,
            'deviation_pct': deviation,
            'status': status.value,
            'notes': notes,
        }

        results.append(validation)

        if save_to_db:
            try:
                db.save_validation(
                    project_id=project_id,
                    item_type='pipe',
                    item_tag=line_num,
                    extracted_value=f'{extracted_float}"',
                    calculated_value=f'{calculated_size}"',
                    status=status.value,
                    sheet_id=line.get('sheet_id'),
                    tolerance_pct=tolerance_pct,
                    deviation_pct=deviation,
                    notes=notes,
                )
            except Exception:
                pass  # Don't fail on db error

    return results


def validate_relief_valves(
    project_id: int,
    drawing_number: Optional[str] = None,
    tolerance_pct: float = 10.0,
    save_to_db: bool = True,
) -> List[Dict]:
    """
    Validate relief valve sizing on drawings.

    Args:
        project_id: Project ID to validate
        drawing_number: Optional specific drawing
        tolerance_pct: Tolerance percentage
        save_to_db: Whether to save results

    Returns:
        List of validation result dicts
    """
    from qms.engineering import db

    # Get equipment with type containing 'relief', 'prv', or 'rv-'
    equipment = db.get_project_equipment(project_id, 'relief', drawing_number)
    prv_equipment = db.get_project_equipment(project_id, 'prv', drawing_number)
    equipment.extend(prv_equipment)
    rv_equipment = db.get_project_equipment(project_id, 'rv-', drawing_number)
    equipment.extend(rv_equipment)

    if not equipment:
        return [{
            'item_type': 'relief_valve',
            'item_tag': 'N/A',
            'status': 'REVIEW',
            'notes': 'No relief valves found in project',
        }]

    results = []
    seen_tags: set = set()

    for equip in equipment:
        tag = equip.get('tag', '')
        if tag in seen_tags:
            continue
        seen_tags.add(tag)

        description = equip.get('description', '')

        # Try to extract vessel size from description
        volume_match = re.search(
            r'(\d+\.?\d*)\s*(cf|cuft|cu\.?\s*ft)', description.lower()
        )
        if volume_match:
            vessel_volume = float(volume_match.group(1))
        else:
            vessel_volume = 100  # Default

        # Try to extract set pressure
        pressure_match = re.search(r'(\d+)\s*(psig|psi)', description.lower())
        if pressure_match:
            set_pressure = float(pressure_match.group(1))
        else:
            set_pressure = 250  # Default

        # Try to extract orifice size from description
        orifice_match = re.search(r'orifice\s*([A-T])', description, re.IGNORECASE)
        if orifice_match:
            extracted_orifice = orifice_match.group(1).upper()
        else:
            extracted_orifice = None
            for letter in 'DEFGHJKLMNPQRT':
                if f'-{letter}' in tag.upper() or f'{letter}-' in tag.upper():
                    extracted_orifice = letter
                    break

        if not extracted_orifice:
            results.append({
                'item_type': 'relief_valve',
                'item_tag': tag,
                'sheet_id': equip.get('sheet_id'),
                'drawing_number': equip.get('drawing_number'),
                'extracted_value': 'N/A',
                'calculated_value': 'N/A',
                'tolerance_pct': tolerance_pct,
                'deviation_pct': 0,
                'status': 'REVIEW',
                'notes': 'Could not determine orifice size',
            })
            continue

        # Run relief valve sizing
        params = {
            'volume_cuft': vessel_volume,
            'set_pressure_psig': set_pressure,
            'refrigerant': 'NH3',
        }

        try:
            calc_result = run_relief_valve(params)
            calculated_orifice = calc_result.get('selected_orifice', '')
        except Exception as e:
            results.append({
                'item_type': 'relief_valve',
                'item_tag': tag,
                'sheet_id': equip.get('sheet_id'),
                'drawing_number': equip.get('drawing_number'),
                'extracted_value': extracted_orifice,
                'calculated_value': 'ERROR',
                'tolerance_pct': tolerance_pct,
                'deviation_pct': 0,
                'status': 'REVIEW',
                'notes': f'Calculation error: {e}',
            })
            continue

        # Compare orifices
        orifice_order = 'DEFGHJKLMNPQRT'
        try:
            extracted_idx = orifice_order.index(extracted_orifice)
            calculated_idx = orifice_order.index(calculated_orifice)
            diff = extracted_idx - calculated_idx
        except ValueError:
            diff = 0

        if diff == 0:
            status = 'PASS'
            notes = 'Orifice size matches'
        elif diff > 0:
            status = 'WARNING'
            notes = f'Oversized by {diff} orifice sizes (acceptable)'
        else:
            status = 'FAIL'
            notes = f'UNDERSIZED by {abs(diff)} orifice sizes'

        validation = {
            'item_type': 'relief_valve',
            'item_tag': tag,
            'sheet_id': equip.get('sheet_id'),
            'drawing_number': equip.get('drawing_number'),
            'extracted_value': extracted_orifice,
            'calculated_value': calculated_orifice,
            'tolerance_pct': tolerance_pct,
            'deviation_pct': diff * 10,  # Approximate percentage
            'status': status,
            'notes': notes,
        }

        results.append(validation)

        if save_to_db:
            try:
                db.save_validation(
                    project_id=project_id,
                    item_type='relief_valve',
                    item_tag=tag,
                    extracted_value=extracted_orifice,
                    calculated_value=calculated_orifice,
                    status=status,
                    sheet_id=equip.get('sheet_id'),
                    tolerance_pct=tolerance_pct,
                    deviation_pct=diff * 10,
                    notes=notes,
                )
            except Exception:
                pass

    return results
