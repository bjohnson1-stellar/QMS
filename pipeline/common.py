"""
Pipeline Common Utilities

Shared utilities for the SIS extraction pipeline module.
Provides file path helpers, drawing number parsing, discipline detection,
job number normalization, date parsing, and configuration lookups.

Used by:
    - pipeline.importer (single + bulk import)
    - pipeline.processor (core extraction engine)
"""

import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from qms.core import get_config, get_config_value, get_logger, QMS_PATHS

logger = get_logger("qms.pipeline.common")


# ---------------------------------------------------------------------------
# Job number parsing / normalization
# ---------------------------------------------------------------------------

def normalize_job_numbers(job_num: str) -> List[str]:
    """
    Normalize job numbers, handling slash suffixes and -00 appending.

    Examples:
        07396-650    -> ['07396-650-00']
        07427-650-01/02 -> ['07427-650-01', '07427-650-02']
        07396-650-00 -> ['07396-650-00']

    Args:
        job_num: Raw job number string from SIS sheet.

    Returns:
        List of normalized job number strings.
    """
    job_num = job_num.strip()

    # Handle slash suffixes: 07427-650-01/02 -> [07427-650-01, 07427-650-02]
    slash_match = re.match(r'^(\d{4,5}-\d{3})-(\d{2}(?:/\d{2})+)$', job_num)
    if slash_match:
        base = slash_match.group(1)
        suffixes = slash_match.group(2).split('/')
        return [f"{base}-{s}" for s in suffixes]

    # Already has -NN suffix
    if re.match(r'^\d{4,5}-\d{3}-\d{2}$', job_num):
        return [job_num]

    # Missing -NN suffix, append -00
    if re.match(r'^\d{4,5}-\d{3}$', job_num):
        return [f"{job_num}-00"]

    # Doesn't match expected pattern, return as-is
    return [job_num]


def extract_project_number(job_number: str) -> str:
    """
    Extract 5-digit project prefix from full job number.

    Examples:
        07396-650-00 -> '07396'
        07650-BRV-PerroGrande -> '07650'

    Args:
        job_number: Full job number string.

    Returns:
        Project number prefix (4-5 digits).
    """
    match = re.match(r'^(\d{4,5})', job_number)
    return match.group(1) if match else job_number


def extract_department_number(job_number: str) -> str:
    """
    Extract 3-digit department number from job number.

    Examples:
        07308-650-01 -> '650'
        07396-600-00 -> '600'

    Args:
        job_number: Full job number string (NNNNN-DDD-SS format).

    Returns:
        Department number string, or empty string if not found.
    """
    match = re.match(r'^\d{4,5}-(\d{3})-\d{2}$', job_number)
    return match.group(1) if match else ''


def extract_suffix(job_number: str) -> str:
    """
    Extract 2-digit suffix from job number.

    Examples:
        07308-650-01 -> '01'
        07396-600-00 -> '00'

    Args:
        job_number: Full job number string (NNNNN-DDD-SS format).

    Returns:
        Suffix string, or '00' if not found.
    """
    match = re.match(r'^\d{4,5}-\d{3}-(\d{2})$', job_number)
    return match.group(1) if match else '00'


# ---------------------------------------------------------------------------
# Name / address parsing
# ---------------------------------------------------------------------------

def strip_city_state(project_name: str) -> str:
    """
    Strip '- CITY, ST' suffix from project names.

    Args:
        project_name: Raw project name string.

    Returns:
        Cleaned project name without city/state suffix.
    """
    match = re.match(r'^(.+?)\s*-\s*[A-Za-z\s.\'\-]+,\s*[A-Z]{2}$', project_name)
    return match.group(1).strip() if match else project_name


def parse_address(addr: str) -> Tuple[str, str, str, str]:
    """
    Parse address into components.

    Args:
        addr: Raw address string.

    Returns:
        Tuple of (street, city, state, zip).

    Examples:
        '123 Main St, Springfield, IL 62701' -> ('123 Main St', 'Springfield', 'IL', '62701')
        '456 Oak Ave, Portland, OR'          -> ('456 Oak Ave', 'Portland', 'OR', '')
    """
    addr = addr.strip()

    # Try: Street, City, ST ZIP
    match = re.match(r'^(.+),\s*(.+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$', addr)
    if match:
        return (match.group(1).strip(), match.group(2).strip(),
                match.group(3).strip(), match.group(4).strip())

    # Try: Street, City, ST (no zip)
    match = re.match(r'^(.+),\s*(.+),\s*([A-Z]{2})$', addr)
    if match:
        return (match.group(1).strip(), match.group(2).strip(),
                match.group(3).strip(), "")

    # Unable to parse, return street only
    return (addr, "", "", "")


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def parse_date(value: str) -> Optional[date]:
    """
    Parse various date formats.

    Supports: YYYY-MM-DD, MM/DD/YYYY, MM/DD/YY, DD-Mon-YYYY, Month DD, YYYY.

    Args:
        value: Date string in any supported format.

    Returns:
        date object if parseable, None otherwise.
    """
    if not value:
        return None
    value = str(value).strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%d-%b-%Y', '%B %d, %Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def extract_date_from_filename(filepath: Path) -> Optional[date]:
    """
    Extract date from filename.

    Supported patterns:
        - SIS_Locations_2026-02-07.xlsx  -> 2026-02-07
        - SIS_Report_2026-02-07.xlsx     -> 2026-02-07
        - SIS_20260207.xlsx              -> 2026-02-07
        - SIS_2026_02_07.xlsx            -> 2026-02-07
        - Weekly_SIS_02-07-2026.xlsx     -> 2026-02-07
        - WE 2.7.2026 (Week Ending)     -> 2026-02-07

    Args:
        filepath: Path to file (uses stem for matching).

    Returns:
        date object if found, None otherwise.
    """
    filename = filepath.stem

    # Pattern 1: YYYY-MM-DD
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    # Pattern 2: YYYYMMDD
    match = re.search(r'(\d{8})', filename)
    if match:
        try:
            date_str = match.group(1)
            return date(int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8]))
        except ValueError:
            pass

    # Pattern 3: YYYY_MM_DD
    match = re.search(r'(\d{4})_(\d{2})_(\d{2})', filename)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    # Pattern 4: MM-DD-YYYY
    match = re.search(r'(\d{2})-(\d{2})-(\d{4})', filename)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
        except ValueError:
            pass

    # Pattern 5: MM_DD_YYYY
    match = re.search(r'(\d{2})_(\d{2})_(\d{4})', filename)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
        except ValueError:
            pass

    # Pattern 6: M.D.YYYY or MM.DD.YYYY (with dots)
    match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', filename)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
        except ValueError:
            pass

    # Pattern 7: WE M.D.YYYY (Week Ending format)
    match = re.search(r'WE\s+(\d{1,2})\.(\d{1,2})\.(\d{4})', filename, re.IGNORECASE)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def load_departments_from_config() -> List[Dict[str, str]]:
    """
    Load departments list from config.yaml.

    Returns:
        List of department dicts with keys: number, name, full_name, manager.
    """
    config = get_config()
    return config.get('departments', [])


def get_projects_path() -> Path:
    """
    Get the projects root directory from config.

    Returns:
        Path to projects folder.
    """
    return QMS_PATHS.projects


def get_inbox_path() -> Path:
    """
    Get the inbox directory from config.

    Returns:
        Path to inbox folder.
    """
    return QMS_PATHS.inbox


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def ensure_directory(path: Path) -> Path:
    """
    Ensure a directory exists, creating if necessary.

    Args:
        path: Directory path.

    Returns:
        The path (for chaining).
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_project_path(project_id: str) -> Optional[Path]:
    """
    Find a project folder by ID (partial match supported).

    Args:
        project_id: Project ID or partial match (e.g., '07645' or 'Vital').

    Returns:
        Path to project folder, or None if not found.
    """
    projects_dir = QMS_PATHS.projects

    if not projects_dir.exists():
        return None

    for folder in projects_dir.iterdir():
        if folder.is_dir() and not folder.name.startswith('_'):
            if project_id in folder.name:
                return folder

    return None
