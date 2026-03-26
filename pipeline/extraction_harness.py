"""Extraction harness — session-aware orchestrator for schedule-first extraction.

Provides a sheet-at-a-time state machine that Claude Code sessions step through.
The harness handles bookkeeping (progress, checkpoints, error tracking) while the
Claude Code session does the actual AI work (reading PDFs, extracting data).

Design principle: The harness does NOT call the Anthropic API or spawn agents.
It provides prompts and records results. The session orchestrates.

Usage from Claude Code session:
    from qms.pipeline.extraction_harness import ExtractionHarness
    h = ExtractionHarness(7, phase="schedules")
    while sheet := h.next_sheet():
        # Session reads PDF, extracts data
        h.record_result(sheet["id"], entries)
        if h.is_batch_complete():
            print(h.get_batch_summary())
            break  # or continue
    h.save_checkpoint()

Part of v0.4 Equipment-Centric Platform (Phase 25).
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_logger

logger = get_logger("qms.pipeline.extraction_harness")

# Default state file location
_STATE_DIR = Path(".paul")
_STATE_FILE = _STATE_DIR / "extraction-state.json"


class ExtractionHarness:
    """Session-aware extraction orchestrator.

    A synchronous state machine stepped by the Claude Code session.
    Each step = one sheet. The session reads the PDF, extracts data,
    and feeds results back to the harness.
    """

    def __init__(self, project_id: int, phase: str = "schedules",
                 batch_size: int = 5, state_file: Path = None):
        self.project_id = project_id
        self.phase = phase
        self.batch_size = batch_size
        self.state_file = state_file or _STATE_FILE

        # Runtime counters (within this session)
        self._batch_completed = 0
        self._session_start = datetime.now(timezone.utc).isoformat()
        self._errors: List[Dict] = []

    def get_status(self) -> Dict[str, Any]:
        """Current extraction progress from the database."""
        from qms.pipeline.extraction_order import get_schedule_sheets
        from qms.pipeline.schedule_extractor import get_pending_schedules

        all_sheets = get_schedule_sheets(self.project_id)
        pending = get_pending_schedules(self.project_id)

        total = len(all_sheets)
        completed = total - len(pending)

        # Load state file for error history
        state = self._load_state()
        errors = state.get("errors", []) if state else []

        return {
            "project_id": self.project_id,
            "phase": self.phase,
            "total": total,
            "completed": completed,
            "pending": len(pending),
            "batch_completed": self._batch_completed,
            "batch_size": self.batch_size,
            "errors": errors,
            "session_start": self._session_start,
        }

    def next_sheet(self) -> Optional[Dict]:
        """Get the next sheet to process. Returns None if phase complete."""
        from qms.pipeline.schedule_extractor import get_pending_schedules

        pending = get_pending_schedules(self.project_id)
        if not pending:
            logger.info("All schedule sheets processed for project %d", self.project_id)
            return None

        sheet = pending[0]
        logger.info(
            "Next sheet: %s (id=%d, discipline=%s)",
            sheet["drawing_number"], sheet["id"], sheet.get("discipline", "?"),
        )
        return sheet

    def record_result(self, sheet_id: int, entries: List[Dict],
                      status: str = "success") -> Dict[str, int]:
        """Record extraction result for a sheet.

        Calls store_schedule_data() and updates progress tracking.

        Returns:
            Stats dict from store_schedule_data: {"stored": N, "skipped": N, "errors": N}
        """
        from qms.pipeline.schedule_extractor import store_schedule_data

        stats = store_schedule_data(sheet_id, self.project_id, entries)
        self._batch_completed += 1

        logger.info(
            "Recorded result for sheet %d: %d stored, %d skipped, %d errors",
            sheet_id, stats["stored"], stats["skipped"], stats["errors"],
        )

        # Auto-save checkpoint after each sheet
        self.save_checkpoint()

        return stats

    def record_error(self, sheet_id: int, error_msg: str):
        """Record a failed extraction.

        First failure: marks for retry. Second failure: skip and flag.
        """
        from qms.pipeline.schedule_extractor import get_schedule_sheet_info

        sheet_info = get_schedule_sheet_info(sheet_id)
        drawing_number = sheet_info["drawing_number"] if sheet_info else f"sheet_{sheet_id}"

        # Check if this sheet already has an error (retry tracking)
        prior_errors = [e for e in self._errors if e["sheet_id"] == sheet_id]

        error_entry = {
            "sheet_id": sheet_id,
            "drawing_number": drawing_number,
            "error": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attempt": len(prior_errors) + 1,
        }

        if len(prior_errors) >= 1:
            error_entry["action"] = "skipped"
            logger.warning(
                "Sheet %s (id=%d) failed twice — skipping. Error: %s",
                drawing_number, sheet_id, error_msg,
            )
        else:
            error_entry["action"] = "retry"
            logger.warning(
                "Sheet %s (id=%d) failed — will retry. Error: %s",
                drawing_number, sheet_id, error_msg,
            )

        self._errors.append(error_entry)
        self.save_checkpoint()

    def save_checkpoint(self):
        """Save current state for session resumption."""
        status = self.get_status()

        state = {
            "project_id": self.project_id,
            "phase": self.phase,
            "batch_size": self.batch_size,
            "started_at": self._session_start,
            "sheets_completed": status["completed"],
            "sheets_total": status["total"],
            "sheets_pending": status["pending"],
            "batch_completed": self._batch_completed,
            "errors": self._errors,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2))
        logger.debug("Checkpoint saved: %s", self.state_file)

    def is_batch_complete(self) -> bool:
        """True if current batch of N sheets is done."""
        return self._batch_completed >= self.batch_size

    def get_batch_summary(self) -> str:
        """Human-readable summary of current batch progress."""
        status = self.get_status()
        lines = [
            f"Batch complete: {self._batch_completed} sheets processed this session",
            f"Overall progress: {status['completed']}/{status['total']} schedule sheets",
            f"Remaining: {status['pending']} sheets",
        ]
        if self._errors:
            skipped = [e for e in self._errors if e.get("action") == "skipped"]
            retryable = [e for e in self._errors if e.get("action") == "retry"]
            if skipped:
                lines.append(f"Skipped (2 failures): {len(skipped)}")
            if retryable:
                lines.append(f"Will retry: {len(retryable)}")
        return "\n".join(lines)

    def should_skip(self, sheet_id: int) -> bool:
        """Check if a sheet should be skipped (failed twice)."""
        prior_errors = [e for e in self._errors if e["sheet_id"] == sheet_id]
        return any(e.get("action") == "skipped" for e in prior_errors)

    def _load_state(self) -> Optional[Dict]:
        """Load state file if it exists."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load state file: %s", e)
        return None


# --- Module-level convenience functions ---


def start_extraction(project_id: int, phase: str = "schedules",
                     batch_size: int = 5) -> Dict[str, Any]:
    """Create a new extraction harness and return initial status.

    Returns: {"harness": ExtractionHarness, "status": dict}
    """
    harness = ExtractionHarness(project_id, phase=phase, batch_size=batch_size)
    status = harness.get_status()
    harness.save_checkpoint()

    logger.info(
        "Started %s extraction for project %d: %d sheets (%d pending)",
        phase, project_id, status["total"], status["pending"],
    )
    return {"harness": harness, "status": status}


def resume_extraction(project_id: int) -> Dict[str, Any]:
    """Resume extraction from saved checkpoint.

    Loads state file, creates harness at checkpoint position.
    Returns: {"harness": ExtractionHarness, "status": dict, "resumed_from": dict}
    """
    state_file = _STATE_FILE
    if not state_file.exists():
        logger.info("No checkpoint found, starting fresh")
        return start_extraction(project_id)

    try:
        state = json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt checkpoint, starting fresh")
        return start_extraction(project_id)

    phase = state.get("phase", "schedules")
    batch_size = state.get("batch_size", 5)

    harness = ExtractionHarness(project_id, phase=phase, batch_size=batch_size)

    # Restore error history from checkpoint
    harness._errors = state.get("errors", [])

    status = harness.get_status()

    logger.info(
        "Resumed %s extraction for project %d: %d/%d complete (%d pending)",
        phase, project_id, status["completed"], status["total"], status["pending"],
    )

    return {
        "harness": harness,
        "status": status,
        "resumed_from": {
            "saved_at": state.get("saved_at"),
            "sheets_completed_at_save": state.get("sheets_completed"),
        },
    }


def get_extraction_prompt(sheet: Dict) -> str:
    """Generate the extraction prompt for a schedule sheet.

    This is the bridge between the harness and the Claude Code session.
    The harness generates the prompt text; the session reads the PDF and applies it.

    Args:
        sheet: Sheet dict from next_sheet() with drawing_number, discipline, file_path

    Returns:
        Formatted prompt string for the session to use when reading the PDF.
    """
    drawing_number = sheet.get("drawing_number", "Unknown")
    discipline = sheet.get("discipline", "Unknown")

    return f"""Extract all equipment from this schedule drawing.

Drawing: {drawing_number} ({discipline})

Instructions:
1. Identify every equipment schedule table on this sheet
2. For each row in each schedule table, extract:
   - tag: Equipment tag/identifier (REQUIRED — skip rows without tags)
   - description: Equipment description or name
   - equipment_type: Type of equipment (e.g., "Panel", "Fan", "Pump", "Water Heater")
   - hp: Horsepower rating (numeric, e.g., 1.5)
   - kva: KVA rating (numeric)
   - voltage: Voltage (e.g., "480/277V", "208V")
   - amperage: Amperage rating (numeric)
   - phase_count: Number of phases (1 or 3)
   - circuit: Circuit identifier
   - panel_source: Source panel (e.g., "LP-1A")
   - manufacturer: Manufacturer name
   - model_number: Model number
   - weight_lbs: Weight in pounds (numeric)
   - cfm: Airflow in CFM (numeric)

3. Return a JSON array of equipment objects
4. Only extract what is ACTUALLY shown in the schedule tables
5. Do NOT fabricate or hallucinate equipment — if a cell is empty, omit that field
6. If the drawing has no schedule tables, return an empty array []

Return ONLY the JSON array, no other text."""
