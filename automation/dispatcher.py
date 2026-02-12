"""
Automation Dispatcher

Scans incoming directory for JSON files, routes by "type" field to registered
handler functions, logs results, and moves processed files.

Handlers register themselves at import time via register_handler().
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from qms.core import get_db, get_logger
from qms.core.config import QMS_PATHS, get_config_value

logger = get_logger("qms.automation.dispatcher")

# Handler registry: type_name -> (handler_fn, module_name)
_HANDLERS: Dict[str, Tuple[Callable, str]] = {}


def register_handler(type_name: str, handler_fn: Callable, module: str) -> None:
    """Register a handler function for a given request type."""
    _HANDLERS[type_name] = (handler_fn, module)
    logger.debug("Registered handler for type '%s' from module '%s'", type_name, module)


def _get_automation_paths() -> Tuple[Path, Path, Path]:
    """Read automation directory paths from config.yaml."""
    incoming = get_config_value("automation", "incoming", default="data/automation/incoming")
    processed = get_config_value("automation", "processed", default="data/automation/processed")
    failed = get_config_value("automation", "failed", default="data/automation/failed")
    return (
        QMS_PATHS._resolve(incoming),
        QMS_PATHS._resolve(processed),
        QMS_PATHS._resolve(failed),
    )


def _move_file(source: Path, dest_dir: Path) -> Path:
    """Move a file to dest_dir with a timestamp prefix to avoid collisions."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    dest_name = f"{timestamp}_{source.name}"
    dest = dest_dir / dest_name
    shutil.move(str(source), str(dest))
    return dest


def process_file(json_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """
    Process a single JSON request file.

    Parses the JSON, extracts the "type" field, looks up the registered handler,
    calls it, logs the result, and moves the file to processed/ or failed/.

    Returns:
        Dict with keys: file, type, status, result_summary, error
    """
    result: Dict[str, Any] = {
        "file": json_path.name,
        "type": None,
        "status": "pending",
        "result_summary": None,
        "error": None,
    }

    # Parse JSON
    try:
        raw_text = json_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        result["status"] = "failed"
        result["error"] = f"Invalid JSON: {exc}"
        _log_processing(json_path.name, "unknown", "failed", None, str(exc), raw_text if 'raw_text' in dir() else None)
        if not dry_run:
            _, _, failed_dir = _get_automation_paths()
            _move_file(json_path, failed_dir)
        return result

    # Extract type
    request_type = data.get("type")
    if not request_type:
        result["status"] = "failed"
        result["error"] = "Missing 'type' field in JSON"
        _log_processing(json_path.name, "unknown", "failed", None, result["error"], raw_text)
        if not dry_run:
            _, _, failed_dir = _get_automation_paths()
            _move_file(json_path, failed_dir)
        return result

    result["type"] = request_type

    # Look up handler
    if request_type not in _HANDLERS:
        result["status"] = "failed"
        result["error"] = f"No handler registered for type '{request_type}'"
        _log_processing(json_path.name, request_type, "failed", None, result["error"], raw_text)
        if not dry_run:
            _, _, failed_dir = _get_automation_paths()
            _move_file(json_path, failed_dir)
        return result

    handler_fn, module_name = _HANDLERS[request_type]

    if dry_run:
        result["status"] = "dry_run"
        result["result_summary"] = f"Would process with handler from {module_name}"
        return result

    # Call handler
    _log_processing(json_path.name, request_type, "processing", module_name, None, raw_text)
    try:
        handler_result = handler_fn(json_path)
        summary = handler_result.get("summary", str(handler_result)) if isinstance(handler_result, dict) else str(handler_result)
        result["status"] = "success"
        result["result_summary"] = summary
        _log_processing(json_path.name, request_type, "success", module_name, None, raw_text, summary)

        _, processed_dir, _ = _get_automation_paths()
        _move_file(json_path, processed_dir)
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        _log_processing(json_path.name, request_type, "failed", module_name, str(exc), raw_text)
        logger.error("Handler failed for %s: %s", json_path.name, exc)

        _, _, failed_dir = _get_automation_paths()
        _move_file(json_path, failed_dir)

    return result


def process_all(dry_run: bool = False) -> List[Dict[str, Any]]:
    """
    Scan incoming directory for *.json files and process each one.

    Returns:
        List of result dicts from process_file()
    """
    incoming_dir, _, _ = _get_automation_paths()
    results: List[Dict[str, Any]] = []

    if not incoming_dir.exists():
        logger.info("Incoming directory does not exist: %s", incoming_dir)
        return results

    json_files = sorted(incoming_dir.glob("*.json"))
    if not json_files:
        logger.info("No JSON files found in %s", incoming_dir)
        return results

    logger.info("Found %d JSON file(s) to process", len(json_files))
    for json_path in json_files:
        result = process_file(json_path, dry_run=dry_run)
        results.append(result)
        logger.info("  %s: %s", json_path.name, result["status"])

    return results


def _log_processing(
    file_name: str,
    request_type: str,
    status: str,
    handler_module: Optional[str],
    error_message: Optional[str],
    source_json: Optional[str],
    result_summary: Optional[str] = None,
) -> None:
    """Write a row to the automation_processing_log table."""
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO automation_processing_log
                   (file_name, request_type, status, handler_module,
                    result_summary, error_message, source_json, processed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    file_name,
                    request_type,
                    status,
                    handler_module,
                    result_summary,
                    error_message,
                    source_json,
                    datetime.now().isoformat() if status in ("success", "failed") else None,
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to log processing result: %s", exc)


def get_processing_log(
    limit: int = 20,
    status: Optional[str] = None,
    request_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query the automation processing log."""
    query = "SELECT * FROM automation_processing_log WHERE 1=1"
    params: List[Any] = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if request_type:
        query += " AND request_type = ?"
        params.append(request_type)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_db(readonly=True) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
