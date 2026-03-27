"""Extraction harness — session-aware orchestrator for schedule-first extraction.

Provides a sheet-at-a-time state machine that Claude Code sessions step through.
The harness handles bookkeeping (progress, checkpoints, error tracking) while the
Claude Code session does the actual AI work (reading PDFs, extracting data).

Design principle: The harness does NOT call the Anthropic API or spawn agents.
It records results and tracks state. The session orchestrates.

Usage from Claude Code session:
    from qms.pipeline.extraction_harness import ExtractionHarness
    h = ExtractionHarness(7, phase="schedules",
                          skip_disciplines=["Architectural", "Civil", "General"])
    while sheet := h.next_sheet():
        # Session reads PDF via Docling or Claude vision
        h.record_result(sheet["id"], entries, model_used="docling")
        if h.is_batch_complete():
            print(h.get_batch_summary())
            break
    h.save_checkpoint()

Part of v0.4 Equipment-Centric Platform (Phase 25).
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.extraction_harness")

# Default state directory
_STATE_DIR = Path(".paul")


class ExtractionHarness:
    """Session-aware extraction orchestrator.

    A synchronous state machine stepped by the Claude Code session.
    Each step = one sheet. The session reads the PDF, extracts data,
    and feeds results back to the harness.
    """

    def __init__(self, project_id: int, phase: str = "schedules",
                 batch_size: int = 5, skip_disciplines: List[str] = None,
                 state_file: Path = None):
        self.project_id = project_id
        self.phase = phase
        self.batch_size = batch_size
        self.skip_disciplines: Set[str] = set(skip_disciplines or [])
        self.state_file = state_file or (_STATE_DIR / f"extraction-state-{project_id}.json")

        # Runtime counters (within this session)
        self._batch_completed = 0
        self._session_start = datetime.now(timezone.utc).isoformat()
        self._errors: List[Dict] = []
        self._sheet_times: List[Dict] = []
        self._current_sheet_start: float = 0
        self._processed_sheet_ids: Set[int] = set()  # tracks ALL processed sheets (even empty)

        # Cached counts (avoid re-classifying all sheets every call)
        self._total_sheets: Optional[int] = None
        self._skipped_sheet_ids: Optional[Set[int]] = None

    def _get_all_phase_sheets(self) -> List[Dict]:
        """Get all sheets for the current phase (cached count on first call)."""
        if self.phase == "plans":
            from qms.pipeline.extraction_order import get_plan_sheets
            sheets = get_plan_sheets(self.project_id)
        else:
            from qms.pipeline.extraction_order import get_schedule_sheets
            sheets = get_schedule_sheets(self.project_id)
        if self._total_sheets is None:
            self._total_sheets = len(sheets)
            self._skipped_sheet_ids = {
                s["id"] for s in sheets
                if s.get("discipline") in self.skip_disciplines
            }
        return sheets

    # Backward compatibility alias
    _get_all_schedule_sheets = _get_all_phase_sheets

    def _get_completed_count(self) -> int:
        """Direct DB query for completed sheet count (fast)."""
        table = "floor_plan_extractions" if self.phase == "plans" else "schedule_extractions"
        with get_db(readonly=True) as conn:
            return conn.execute(
                f"SELECT COUNT(DISTINCT sheet_id) FROM {table} WHERE project_id = ?",
                (self.project_id,),
            ).fetchone()[0]

    def get_status(self) -> Dict[str, Any]:
        """Current extraction progress."""
        # Ensure cache is populated
        self._get_all_schedule_sheets()

        completed = self._get_completed_count()
        skipped = len(self._skipped_sheet_ids)
        pending = self._total_sheets - completed - skipped

        # Load state file for error history
        state = self._load_state()
        errors = state.get("errors", []) if state else []

        return {
            "project_id": self.project_id,
            "phase": self.phase,
            "total": self._total_sheets,
            "completed": completed,
            "pending": max(0, pending),
            "skipped": skipped,
            "batch_completed": self._batch_completed,
            "batch_size": self.batch_size,
            "skip_disciplines": sorted(self.skip_disciplines),
            "errors": errors,
            "session_start": self._session_start,
        }

    def next_sheet(self) -> Optional[Dict]:
        """Get the next sheet to process. Returns None if phase complete.

        Skips sheets whose discipline is in skip_disciplines and sheets
        already processed in this session (even if they had 0 entries).
        """
        if self.phase == "plans":
            from qms.pipeline.floor_plan_extractor import get_pending_floor_plans
            pending = get_pending_floor_plans(self.project_id)
        else:
            from qms.pipeline.schedule_extractor import get_pending_schedules
            pending = get_pending_schedules(self.project_id)

        # Filter out skipped disciplines and already-processed sheets
        pending = [
            s for s in pending
            if s.get("discipline") not in self.skip_disciplines
            and s["id"] not in self._processed_sheet_ids
        ]

        if not pending:
            logger.info("All eligible schedule sheets processed for project %d", self.project_id)
            return None

        sheet = pending[0]
        self._current_sheet_start = time.monotonic()
        logger.info(
            "Next sheet: %s (id=%d, discipline=%s)",
            sheet["drawing_number"], sheet["id"], sheet.get("discipline", "?"),
        )
        return sheet

    def record_result(self, sheet_id: int, entries: List[Dict],
                      model_used: str = "docling",
                      confidence: float = None) -> Dict[str, int]:
        """Record extraction result for a sheet.

        Args:
            sheet_id: Sheet ID
            entries: Equipment dicts (each should include page_number if available)
            model_used: "docling", "claude-sonnet-vision", or "claude-opus-shadow"
            confidence: Override confidence (None = derive from model_used)

        Returns:
            Stats dict: {"stored": N, "skipped": N, "errors": N}
        """
        if self.phase == "plans":
            from qms.pipeline.floor_plan_extractor import store_floor_plan_data
            stats = store_floor_plan_data(
                sheet_id, self.project_id, entries,
                model_used=model_used, confidence=confidence,
            )
        else:
            from qms.pipeline.schedule_extractor import store_schedule_data
            stats = store_schedule_data(
                sheet_id, self.project_id, entries,
                model_used=model_used, confidence=confidence,
            )
        self._batch_completed += 1
        self._processed_sheet_ids.add(sheet_id)

        # Track timing
        elapsed = time.monotonic() - self._current_sheet_start if self._current_sheet_start else 0
        self._sheet_times.append({
            "sheet_id": sheet_id,
            "elapsed_seconds": round(elapsed, 1),
            "entries_stored": stats["stored"],
            "model_used": model_used,
        })

        logger.info(
            "Recorded result for sheet %d: %d stored, %d skipped, %d errors (%.1fs)",
            sheet_id, stats["stored"], stats["skipped"], stats["errors"], elapsed,
        )

        self.save_checkpoint()
        return stats

    def record_error(self, sheet_id: int, error_msg: str):
        """Record a failed extraction.

        First failure: marks for retry. Second failure: skip and flag.
        """
        from qms.pipeline.schedule_extractor import get_schedule_sheet_info

        sheet_info = get_schedule_sheet_info(sheet_id)  # works for any sheet type
        drawing_number = sheet_info["drawing_number"] if sheet_info else f"sheet_{sheet_id}"

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
            self._processed_sheet_ids.add(sheet_id)
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
        # Use cached total + direct query (no full reclassification)
        if self._total_sheets is None:
            self._get_all_schedule_sheets()

        completed = self._get_completed_count()
        skipped = len(self._skipped_sheet_ids) if self._skipped_sheet_ids else 0

        state = {
            "project_id": self.project_id,
            "phase": self.phase,
            "batch_size": self.batch_size,
            "skip_disciplines": sorted(self.skip_disciplines),
            "started_at": self._session_start,
            "sheets_completed": completed,
            "sheets_total": self._total_sheets,
            "sheets_skipped": skipped,
            "sheets_pending": max(0, self._total_sheets - completed - skipped),
            "batch_completed": self._batch_completed,
            "processed_sheet_ids": sorted(self._processed_sheet_ids),
            "errors": self._errors,
            "sheet_times": self._sheet_times[-20:],  # last 20 for size control
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

        # Average time per sheet
        if self._sheet_times:
            avg_time = sum(t["elapsed_seconds"] for t in self._sheet_times) / len(self._sheet_times)
            est_remaining = avg_time * status["pending"] / 60
            time_line = f"Avg time/sheet: {avg_time:.1f}s, est remaining: {est_remaining:.0f}min"
        else:
            time_line = ""

        lines = [
            f"Batch complete: {self._batch_completed} sheets processed this session",
            f"Overall progress: {status['completed']}/{status['total']} schedule sheets",
            f"Skipped (non-MEP): {status['skipped']}",
            f"Remaining: {status['pending']} sheets",
        ]
        if time_line:
            lines.append(time_line)
        if self._errors:
            error_skipped = [e for e in self._errors if e.get("action") == "skipped"]
            retryable = [e for e in self._errors if e.get("action") == "retry"]
            if error_skipped:
                lines.append(f"Failed (2 attempts): {len(error_skipped)}")
            if retryable:
                lines.append(f"Will retry: {len(retryable)}")
        return "\n".join(lines)

    def should_skip(self, sheet_id: int) -> bool:
        """Check if a sheet should be skipped (failed twice)."""
        return any(
            e["sheet_id"] == sheet_id and e.get("action") == "skipped"
            for e in self._errors
        )

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
                     batch_size: int = 5,
                     skip_disciplines: List[str] = None) -> Dict[str, Any]:
    """Create a new extraction harness and return initial status."""
    harness = ExtractionHarness(
        project_id, phase=phase, batch_size=batch_size,
        skip_disciplines=skip_disciplines,
    )
    status = harness.get_status()
    harness.save_checkpoint()

    logger.info(
        "Started %s extraction for project %d: %d sheets (%d pending, %d skipped)",
        phase, project_id, status["total"], status["pending"], status["skipped"],
    )
    return {"harness": harness, "status": status}


def resume_extraction(project_id: int) -> Dict[str, Any]:
    """Resume extraction from saved checkpoint."""
    state_file = _STATE_DIR / f"extraction-state-{project_id}.json"
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
    skip_disciplines = state.get("skip_disciplines", [])

    harness = ExtractionHarness(
        project_id, phase=phase, batch_size=batch_size,
        skip_disciplines=skip_disciplines,
    )
    harness._errors = state.get("errors", [])
    harness._processed_sheet_ids = set(state.get("processed_sheet_ids", []))

    status = harness.get_status()

    logger.info(
        "Resumed %s extraction for project %d: %d/%d complete (%d pending, %d skipped)",
        phase, project_id, status["completed"], status["total"],
        status["pending"], status["skipped"],
    )

    return {
        "harness": harness,
        "status": status,
        "resumed_from": {
            "saved_at": state.get("saved_at"),
            "sheets_completed_at_save": state.get("sheets_completed"),
        },
    }
