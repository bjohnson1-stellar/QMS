"""
Mobile Capture Processing Engine.

Scans a configured OneDrive folder for photos, analyzes each with Claude
vision API to extract structured quality observation data, and creates
quality_issues records with attached images.

Usage (CLI):
    qms quality capture                          # Process from configured folder
    qms quality capture --dry-run                # Analyze without creating issues
    qms quality capture --folder /path/to/photos # Override source folder
    qms quality capture --project 07645          # Assign to specific project
"""

import base64
import hashlib
import json
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_config_value, get_db, get_logger
from qms.quality.db import normalize_trade, normalize_type

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

logger = get_logger("qms.quality.mobile_capture")

# Supported image extensions
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic"}

# Extension → MIME type mapping
_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/webp",  # Claude accepts HEIC as webp
}

# Model name → API model ID
_MODEL_MAP = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-5-20250929",
    "opus": "claude-opus-4-6",
}

# Structured prompt for photo analysis
_ANALYSIS_PROMPT = """Analyze this construction site photo and extract a quality observation.

Return a JSON object with exactly these fields:
{
    "title": "Short descriptive title for the observation (max 100 chars)",
    "type": "observation",
    "trade": "The responsible trade (e.g. Mechanical, Electrical, Plumbing, Refrigeration, HVAC, Fire Protection, General)",
    "severity": "low | medium | high | critical",
    "location": "Describe the location visible in the photo (area, floor, room, etc.)",
    "description": "Detailed description of what is observed — include specific details about materials, conditions, or work quality visible in the photo",
    "recommended_action": "What should be done to address this observation"
}

Guidelines:
- If you cannot determine a field, use a reasonable default
- For trade: identify from visible work, equipment, or materials
- For severity: low=minor cosmetic, medium=needs attention, high=code/safety concern, critical=immediate hazard
- For type: default to "observation" unless clearly a deficiency or punch item
- Be specific and factual in the description — describe what you see, not what you assume

Return ONLY the JSON object, no other text."""

# Valid values for CHECK-constrained fields
_VALID_SEVERITIES = {"low", "medium", "high", "critical"}
_VALID_TYPES = {"observation", "ncr", "car", "deficiency", "punch", "other"}


def _file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file for dedup tracking."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_capture_folder(
    folder: Path, conn: sqlite3.Connection
) -> List[Path]:
    """Discover new image files in the capture folder.

    Filters out files already tracked in capture_log (by filepath).
    Returns list of new files to process.
    """
    if not folder.exists():
        logger.warning("Capture folder does not exist: %s", folder)
        return []

    # Get already-processed filepaths
    rows = conn.execute("SELECT filepath FROM capture_log").fetchall()
    processed = {r["filepath"] for r in rows}

    new_files = []
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in _IMAGE_EXTENSIONS:
            continue
        if str(f) in processed:
            continue
        new_files.append(f)

    logger.info("Scan found %d new images in %s", len(new_files), folder)
    return new_files


def analyze_photo(image_path: Path, model: str = "sonnet") -> Dict[str, Any]:
    """Analyze a photo with Claude vision API.

    Sends the image to Claude with a structured extraction prompt,
    parses the JSON response, and normalizes fields to match
    quality_issues schema.

    Returns dict with quality_issues-compatible fields, or a dict
    with 'error' key on failure.
    """
    if anthropic is None:
        return {"error": "anthropic SDK not installed. pip install anthropic>=0.25.0"}

    # Read and encode image
    image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
    media_type = _MEDIA_TYPES.get(image_path.suffix.lower(), "image/jpeg")
    model_id = _MODEL_MAP.get(model, model)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model_id,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": _ANALYSIS_PROMPT,
                        },
                    ],
                }
            ],
        )
        raw_text = response.content[0].text
    except Exception as e:
        logger.error("Claude API error for %s: %s", image_path.name, e)
        return {"error": str(e)}

    # Parse JSON from response
    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not json_match:
        logger.warning("No JSON in Claude response for %s", image_path.name)
        return {"error": f"No JSON in response: {raw_text[:200]}"}

    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error for %s: %s", image_path.name, e)
        return {"error": f"JSON parse error: {e}"}

    # Normalize fields
    result = {
        "title": data.get("title", image_path.stem)[:200],
        "type": data.get("type", "observation"),
        "trade": normalize_trade(data.get("trade", "")),
        "severity": data.get("severity", "medium"),
        "location": data.get("location", ""),
        "description": data.get("description", ""),
        "recommended_action": data.get("recommended_action", ""),
    }

    # Validate constrained fields — only normalize if not already valid
    if result["type"] not in _VALID_TYPES:
        result["type"] = normalize_type(result["type"])
    if result["type"] not in _VALID_TYPES:
        result["type"] = "observation"
    if result["severity"] not in _VALID_SEVERITIES:
        result["severity"] = "medium"

    return result


def create_issue_from_capture(
    conn: sqlite3.Connection,
    analysis: Dict[str, Any],
    image_path: Path,
    project_id: Optional[int],
    attachment_dir: Path,
) -> int:
    """Create a quality issue from analyzed photo data.

    Inserts into quality_issues with source='mobile', copies the image
    to the attachment directory, creates an attachment record, and logs
    to capture_log.

    Returns the new issue ID.
    """
    # Build metadata JSON with recommended_action
    metadata = {}
    if analysis.get("recommended_action"):
        metadata["recommended_action"] = analysis["recommended_action"]

    # Insert quality issue
    cursor = conn.execute(
        """INSERT INTO quality_issues
           (type, title, description, project_id, location, trade,
            severity, status, source, reported_by, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'open', 'mobile', 'mobile-capture', ?)""",
        (
            analysis.get("type", "observation"),
            analysis["title"],
            analysis.get("description", ""),
            project_id,
            analysis.get("location", ""),
            analysis.get("trade", ""),
            analysis.get("severity", "medium"),
            json.dumps(metadata) if metadata else None,
        ),
    )
    issue_id = cursor.lastrowid

    # Copy image to attachment directory
    issue_dir = attachment_dir / str(issue_id)
    issue_dir.mkdir(parents=True, exist_ok=True)
    dest_path = issue_dir / image_path.name
    shutil.copy2(image_path, dest_path)

    # Create attachment record
    file_size = dest_path.stat().st_size
    conn.execute(
        """INSERT INTO quality_issue_attachments
           (issue_id, filename, filepath, file_type, file_size, description)
           VALUES (?, ?, ?, 'image', ?, 'Mobile capture photo')""",
        (issue_id, image_path.name, str(dest_path), file_size),
    )

    # Log to capture_log
    conn.execute(
        """INSERT INTO capture_log (filename, filepath, file_hash, status, issue_id)
           VALUES (?, ?, ?, 'processed', ?)""",
        (image_path.name, str(image_path), _file_hash(image_path), issue_id),
    )

    logger.info(
        "Created issue #%d from %s: %s", issue_id, image_path.name, analysis["title"]
    )
    return issue_id


def process_captures(
    folder: Optional[Path] = None,
    project_id: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Main orchestrator: scan → analyze → create issues.

    Reads configuration for source folder, model, and attachment directory.
    Processes all new images found in the capture folder.

    Returns summary dict with counts and created issue IDs.
    """
    # Read config
    if folder is None:
        source = get_config_value(
            "mobile_capture", "source_folder",
            default="C:/Users/bjohnson1/OneDrive - Stellar Group Incorporated/QMS-Capture",
        )
        folder = Path(source)

    model = get_config_value("mobile_capture", "model", default="sonnet")

    attachment_base = get_config_value(
        "mobile_capture", "attachment_dir",
        default="data/quality-issues/captures",
    ) or "data/quality-issues/captures"
    # Resolve relative paths against package dir
    attachment_dir = Path(attachment_base)
    if not attachment_dir.is_absolute():
        from qms.core.config import _PACKAGE_DIR
        attachment_dir = _PACKAGE_DIR / attachment_dir

    summary = {
        "folder": str(folder),
        "processed": 0,
        "failed": 0,
        "skipped": 0,
        "issues_created": [],
        "errors": [],
        "dry_run": dry_run,
    }

    with get_db() as conn:
        new_files = scan_capture_folder(folder, conn)

        if not new_files:
            logger.info("No new images to process")
            return summary

        for image_path in new_files:
            logger.info("Analyzing: %s", image_path.name)

            analysis = analyze_photo(image_path, model=model)

            if "error" in analysis:
                summary["failed"] += 1
                summary["errors"].append(
                    {"file": image_path.name, "error": analysis["error"]}
                )
                # Log failure to capture_log (skip on dry run)
                if not dry_run:
                    conn.execute(
                        """INSERT OR IGNORE INTO capture_log
                           (filename, filepath, file_hash, status, error_message)
                           VALUES (?, ?, ?, 'failed', ?)""",
                        (
                            image_path.name,
                            str(image_path),
                            _file_hash(image_path),
                            analysis["error"],
                        ),
                    )
                continue

            if dry_run:
                summary["processed"] += 1
                summary["issues_created"].append(
                    {"file": image_path.name, "analysis": analysis}
                )
                logger.info(
                    "[DRY RUN] Would create: %s (%s, %s)",
                    analysis["title"],
                    analysis.get("trade", "?"),
                    analysis.get("severity", "?"),
                )
                continue

            try:
                issue_id = create_issue_from_capture(
                    conn, analysis, image_path, project_id, attachment_dir
                )
                summary["processed"] += 1
                summary["issues_created"].append(
                    {"file": image_path.name, "issue_id": issue_id, "title": analysis["title"]}
                )
            except Exception as e:
                logger.error("Failed to create issue from %s: %s", image_path.name, e)
                summary["failed"] += 1
                summary["errors"].append({"file": image_path.name, "error": str(e)})
                conn.execute(
                    """INSERT OR IGNORE INTO capture_log
                       (filename, filepath, file_hash, status, error_message)
                       VALUES (?, ?, ?, 'failed', ?)""",
                    (
                        image_path.name,
                        str(image_path),
                        _file_hash(image_path),
                        str(e),
                    ),
                )

    return summary
