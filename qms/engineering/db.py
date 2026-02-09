"""
Database Operations

Audit trail operations for engineering calculations and validations.
Uses qms.core for database connections.
"""

import json
from typing import Any, Dict, List, Optional

from qms.core import get_db, get_logger


logger = get_logger('qms.engineering.db')


def save_calculation(
    discipline: str,
    calculation_type: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    project_id: Optional[int] = None,
    sheet_id: Optional[int] = None,
    equipment_tag: Optional[str] = None,
    line_number: Optional[str] = None,
    notes: Optional[str] = None,
) -> int:
    """
    Save a calculation to the audit trail.

    Args:
        discipline: Discipline name (e.g., 'refrigeration')
        calculation_type: Type of calculation (e.g., 'line-sizing')
        inputs: Input parameters as dict
        outputs: Output results as dict
        project_id: Optional project ID reference
        sheet_id: Optional sheet ID reference
        equipment_tag: Optional equipment tag
        line_number: Optional line number
        notes: Optional notes

    Returns:
        ID of inserted calculation record
    """
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO eng_calculations (
                discipline, calculation_type, input_json, output_json,
                project_id, sheet_id, equipment_tag, line_number, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            discipline,
            calculation_type,
            json.dumps(inputs, default=str),
            json.dumps(outputs, default=str),
            project_id,
            sheet_id,
            equipment_tag,
            line_number,
            notes,
        ))
        conn.commit()

        calc_id = cursor.lastrowid
        logger.info(f"Saved calculation {calc_id}: {discipline}/{calculation_type}")
        return calc_id


def save_validation(
    project_id: int,
    item_type: str,
    item_tag: str,
    extracted_value: str,
    calculated_value: str,
    status: str,
    calculation_id: Optional[int] = None,
    sheet_id: Optional[int] = None,
    tolerance_pct: Optional[float] = None,
    deviation_pct: Optional[float] = None,
    notes: Optional[str] = None,
) -> int:
    """
    Save a validation result.

    Args:
        project_id: Project ID
        item_type: Type of item (e.g., 'pipe', 'relief_valve')
        item_tag: Item identifier
        extracted_value: Value extracted from drawing
        calculated_value: Calculated required value
        status: Validation status (PASS, FAIL, WARNING, REVIEW)
        calculation_id: Optional linked calculation ID
        sheet_id: Optional sheet ID
        tolerance_pct: Tolerance percentage used
        deviation_pct: Actual deviation percentage
        notes: Notes about the validation

    Returns:
        ID of inserted validation record
    """
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO eng_validations (
                calculation_id, project_id, sheet_id, item_type, item_tag,
                extracted_value, calculated_value, tolerance_pct,
                deviation_pct, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            calculation_id,
            project_id,
            sheet_id,
            item_type,
            item_tag,
            extracted_value,
            calculated_value,
            tolerance_pct,
            deviation_pct,
            status,
            notes,
        ))
        conn.commit()

        return cursor.lastrowid


def get_project_by_number(project_number: str) -> Optional[Dict]:
    """Get project by number (partial match)."""
    with get_db(readonly=True) as conn:
        cursor = conn.execute("""
            SELECT id, number, name, path
            FROM projects
            WHERE number LIKE ? OR name LIKE ?
            LIMIT 1
        """, (f"%{project_number}%", f"%{project_number}%"))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_project_lines(
    project_id: int, drawing_number: Optional[str] = None
) -> List[Dict]:
    """
    Get lines for a project.

    Args:
        project_id: Project ID
        drawing_number: Optional specific drawing number

    Returns:
        List of line records
    """
    with get_db(readonly=True) as conn:
        if drawing_number:
            cursor = conn.execute("""
                SELECT l.*, s.drawing_number, s.discipline
                FROM lines l
                JOIN sheets s ON l.sheet_id = s.id
                WHERE s.project_id = ? AND s.drawing_number LIKE ?
                ORDER BY l.line_number
            """, (project_id, f"%{drawing_number}%"))
        else:
            cursor = conn.execute("""
                SELECT l.*, s.drawing_number, s.discipline
                FROM lines l
                JOIN sheets s ON l.sheet_id = s.id
                WHERE s.project_id = ?
                ORDER BY s.drawing_number, l.line_number
            """, (project_id,))

        return [dict(row) for row in cursor.fetchall()]


def get_project_equipment(
    project_id: int,
    equipment_type: Optional[str] = None,
    drawing_number: Optional[str] = None,
) -> List[Dict]:
    """
    Get equipment for a project.

    Args:
        project_id: Project ID
        equipment_type: Optional filter by type
        drawing_number: Optional specific drawing number

    Returns:
        List of equipment records
    """
    with get_db(readonly=True) as conn:
        query = """
            SELECT e.*, s.drawing_number, s.discipline
            FROM equipment e
            JOIN sheets s ON e.sheet_id = s.id
            WHERE s.project_id = ?
        """
        params: list = [project_id]

        if equipment_type:
            query += " AND e.equipment_type LIKE ?"
            params.append(f"%{equipment_type}%")

        if drawing_number:
            query += " AND s.drawing_number LIKE ?"
            params.append(f"%{drawing_number}%")

        query += " ORDER BY e.tag"

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_validation_history(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict]:
    """
    Get validation history.

    Args:
        project_id: Optional filter by project
        status: Optional filter by status
        limit: Max records to return

    Returns:
        List of validation records
    """
    with get_db(readonly=True) as conn:
        query = "SELECT * FROM eng_validations WHERE 1=1"
        params: list = []

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
