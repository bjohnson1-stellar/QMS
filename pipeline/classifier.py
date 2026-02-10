"""
Document Intake Classifier & Router.

Reads document_types from config.yaml, classifies inbox files by regex
pattern matching, resolves destination paths, and moves files.

Public API:
    load_document_types()  — config dict
    compile_patterns()     — pre-compiled regexes
    classify_file()        — single file classification
    resolve_destination()  — template variable substitution
    scan_inbox()           — classify all inbox files
    process_files()        — move files to destinations
    get_intake_stats()     — aggregate log stats
"""

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from qms.core import get_db, get_config, get_logger
from qms.core.config import QMS_PATHS

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    """Result of classifying a single inbox file."""

    filename: str
    source_path: Path
    doc_type: Optional[str] = None
    handler: Optional[str] = None
    destination: Optional[str] = None
    destination_template: Optional[str] = None
    matched_pattern: Optional[str] = None
    status: str = "unrecognized"  # matched | incomplete | unrecognized
    unresolved_vars: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    file_size: int = 0
    file_modified: Optional[str] = None


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def load_document_types() -> Dict:
    """Load the document_types section from config.yaml."""
    cfg = get_config()
    return cfg.get("document_types", {})


def _load_discipline_prefixes() -> Dict[str, str]:
    """Load discipline_prefixes mapping from config.yaml."""
    cfg = get_config()
    return cfg.get("discipline_prefixes", {})


CompiledPattern = Tuple[str, str, re.Pattern, str, str]
# (doc_type, pattern_str, compiled, destination_template, handler)


def compile_patterns(
    doc_types: Optional[Dict] = None,
) -> List[CompiledPattern]:
    """
    Pre-compile all regex patterns from document_types config.

    Returns list of (doc_type, pattern_str, compiled_re, destination_template, handler)
    in config insertion order (first match wins).
    """
    if doc_types is None:
        doc_types = load_document_types()

    compiled: List[CompiledPattern] = []
    for doc_type, spec in doc_types.items():
        patterns = spec.get("patterns", [])
        dest = spec.get("destination", "")
        handler = spec.get("handler", "")
        for pat_str in patterns:
            try:
                compiled.append(
                    (doc_type, pat_str, re.compile(pat_str, re.IGNORECASE), dest, handler)
                )
            except re.error as exc:
                logger.warning("Bad regex in document_types.%s: %s (%s)", doc_type, pat_str, exc)
    return compiled


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_file(
    filename: str,
    source_path: Path,
    compiled: Optional[List[CompiledPattern]] = None,
) -> ClassificationResult:
    """
    Classify a single file against document_type patterns.

    First match wins (config insertion order).
    """
    if compiled is None:
        compiled = compile_patterns()

    result = ClassificationResult(
        filename=filename,
        source_path=source_path,
    )

    # File metadata
    if source_path.exists():
        stat = source_path.stat()
        result.file_size = stat.st_size
        result.file_modified = datetime.fromtimestamp(stat.st_mtime).isoformat(
            timespec="seconds"
        )

    for doc_type, pat_str, regex, dest_tmpl, handler in compiled:
        if regex.search(filename):
            result.doc_type = doc_type
            result.handler = handler
            result.matched_pattern = pat_str
            result.destination_template = dest_tmpl

            # Try to resolve destination
            resolved, unresolved = resolve_destination(dest_tmpl, filename)
            if unresolved:
                result.status = "incomplete"
                result.unresolved_vars = unresolved
                result.notes = f"Unresolved: {', '.join(unresolved)}"
            else:
                result.status = "matched"
                result.destination = resolved

            return result

    result.status = "unrecognized"
    result.notes = "No pattern matched"
    return result


# ---------------------------------------------------------------------------
# Destination resolution
# ---------------------------------------------------------------------------

# Pattern to extract 5-digit project number from filename
_PROJECT_RE = re.compile(r"^(\d{5})[-_]")
# Pattern to extract 6-digit drawing set / spec number
_DRAWING_SET_RE = re.compile(r"^(\d{6})")
# Pattern to extract discipline prefix (letter(s) before dash+digits)
_DISCIPLINE_PREFIX_RE = re.compile(r"^([A-Z]{1,3})-\d", re.IGNORECASE)


def resolve_destination(
    template: str,
    filename: str,
) -> Tuple[str, List[str]]:
    """
    Replace template variables in a destination string.

    Returns (resolved_path_str, list_of_unresolved_variable_names).
    """
    unresolved: List[str] = []
    result = template

    variables = {
        "{projects}": str(QMS_PATHS.projects),
        "{quality_documents}": str(QMS_PATHS.quality_documents),
        "{year}": str(datetime.now().year),
    }

    # Extract {project} from filename
    m = _PROJECT_RE.match(filename)
    if m:
        variables["{project}"] = m.group(1)

    # Extract {drawing_set} from filename
    m = _DRAWING_SET_RE.match(filename)
    if m:
        variables["{drawing_set}"] = m.group(1)

    # Extract {discipline} from filename using discipline_prefixes mapping
    m = _DISCIPLINE_PREFIX_RE.match(filename)
    if m:
        prefix = m.group(1).upper()
        prefixes = _load_discipline_prefixes()
        if prefix in prefixes:
            variables["{discipline}"] = prefixes[prefix]

    # Substitute all known variables
    for var, val in variables.items():
        if var in result:
            result = result.replace(var, val)

    # Check for any remaining unresolved variables
    remaining = re.findall(r"\{(\w+)\}", result)
    for var_name in remaining:
        unresolved.append(var_name)

    return result, unresolved


# ---------------------------------------------------------------------------
# Inbox scanning
# ---------------------------------------------------------------------------

# Subdirectories to skip when scanning inbox root
_SKIP_DIRS = {"NEEDS-REVIEW", "CONFLICTS", "DUPLICATES", "_EXTRACTING", "_PROCESSED"}


def scan_inbox(inbox_path: Optional[Path] = None) -> List[ClassificationResult]:
    """
    Classify all files at the inbox root (skip subdirectories).

    Returns list of ClassificationResult in alphabetical order.
    """
    if inbox_path is None:
        inbox_path = QMS_PATHS.inbox

    if not inbox_path.exists():
        logger.warning("Inbox path does not exist: %s", inbox_path)
        return []

    compiled = compile_patterns()
    results: List[ClassificationResult] = []

    for item in sorted(inbox_path.iterdir()):
        if item.is_dir():
            continue  # skip all subdirectories
        results.append(classify_file(item.name, item, compiled))

    return results


# ---------------------------------------------------------------------------
# Processing (move files)
# ---------------------------------------------------------------------------


@dataclass
class ProcessAction:
    """Describes an action taken or planned for a file."""

    filename: str
    action: str  # routed | needs_review | duplicate | would_route | would_need_review
    source: str
    destination: str
    doc_type: Optional[str] = None
    handler: Optional[str] = None
    notes: Optional[str] = None


def process_files(
    results: List[ClassificationResult],
    dry_run: bool = False,
) -> List[ProcessAction]:
    """
    Move classified files to their destinations.

    - matched + destination resolved → move to destination
    - incomplete/unrecognized → move to NEEDS-REVIEW
    - If destination file already exists → mark as duplicate, skip
    - dry_run=True → return planned actions without moving
    """
    actions: List[ProcessAction] = []
    needs_review = QMS_PATHS.needs_review

    for r in results:
        if r.status == "matched" and r.destination:
            dest = Path(r.destination) / r.filename
            action_name = "would_route" if dry_run else "routed"

            if not dry_run and dest.exists():
                actions.append(
                    ProcessAction(
                        filename=r.filename,
                        action="duplicate",
                        source=str(r.source_path),
                        destination=str(dest),
                        doc_type=r.doc_type,
                        handler=r.handler,
                        notes=f"File already exists at destination",
                    )
                )
                continue

            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(r.source_path), str(dest))

            actions.append(
                ProcessAction(
                    filename=r.filename,
                    action=action_name,
                    source=str(r.source_path),
                    destination=str(dest),
                    doc_type=r.doc_type,
                    handler=r.handler,
                )
            )
        else:
            dest = needs_review / r.filename
            action_name = "would_need_review" if dry_run else "needs_review"

            if not dry_run:
                needs_review.mkdir(parents=True, exist_ok=True)
                if r.source_path.exists():
                    shutil.move(str(r.source_path), str(dest))

            actions.append(
                ProcessAction(
                    filename=r.filename,
                    action=action_name,
                    source=str(r.source_path),
                    destination=str(dest),
                    doc_type=r.doc_type,
                    handler=r.handler,
                    notes=r.notes,
                )
            )

    # Log to database (skip in dry-run mode)
    if not dry_run and actions:
        _log_actions(actions)

    return actions


def _log_actions(actions: List[ProcessAction]) -> None:
    """Write process actions to document_intake_log table."""
    try:
        with get_db() as conn:
            conn.executemany(
                """
                INSERT INTO document_intake_log
                    (file_name, source_path, destination_path, document_type, handler, action, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        a.filename,
                        a.source,
                        a.destination,
                        a.doc_type,
                        a.handler,
                        a.action,
                        a.notes,
                    )
                    for a in actions
                ],
            )
            conn.commit()
    except Exception as exc:
        logger.error("Failed to log intake actions: %s", exc)


# ---------------------------------------------------------------------------
# Stats / log queries
# ---------------------------------------------------------------------------


def get_intake_stats() -> Dict:
    """Aggregate statistics from document_intake_log."""
    try:
        with get_db(readonly=True) as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN action = 'routed' THEN 1 ELSE 0 END) AS routed,
                    SUM(CASE WHEN action = 'needs_review' THEN 1 ELSE 0 END) AS needs_review,
                    SUM(CASE WHEN action = 'duplicate' THEN 1 ELSE 0 END) AS duplicate
                FROM document_intake_log
                """
            ).fetchone()

            recent = conn.execute(
                """
                SELECT file_name, document_type, handler, action, notes, created_at
                FROM document_intake_log
                ORDER BY created_at DESC
                LIMIT 50
                """
            ).fetchall()

        return {
            "total": row[0] or 0,
            "routed": row[1] or 0,
            "needs_review": row[2] or 0,
            "duplicate": row[3] or 0,
            "recent": [dict(r) for r in recent],
        }
    except Exception as exc:
        logger.error("Failed to read intake stats: %s", exc)
        return {"total": 0, "routed": 0, "needs_review": 0, "duplicate": 0, "recent": []}


def get_intake_log(limit: int = 50) -> List[Dict]:
    """Return recent intake log entries."""
    try:
        with get_db(readonly=True) as conn:
            rows = conn.execute(
                """
                SELECT id, file_name, source_path, destination_path,
                       document_type, handler, action, notes, created_at
                FROM document_intake_log
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
