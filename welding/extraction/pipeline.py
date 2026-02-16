"""
Multi-agent extraction pipeline for welding forms.

Orchestration flow:
1. Extract text from PDF
2. Run primary extraction (Sonnet)
3. Run secondary extraction (Sonnet) in parallel
4. Cross-check results
5. If disagreement, run shadow review (Opus)
6. Validate combined result
7. Load to database (if not dry-run)
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from qms.core import get_config_value, get_db, get_logger

logger = get_logger("qms.welding.extraction.pipeline")


@dataclass
class PipelineResult:
    """Result of processing a single PDF."""
    source_file: str
    form_type: str
    identifier: Optional[str] = None
    status: str = "pending"  # pending, success, partial, failed, skipped
    confidence: float = 0.0
    data: Optional[Dict[str, Any]] = None
    validation_issues: List[Dict] = field(default_factory=list)
    disagreements: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    parent_record_id: Optional[int] = None
    child_record_counts: Dict[str, int] = field(default_factory=dict)
    processing_time_ms: int = 0


def _get_model_config() -> Dict[str, str]:
    """Get model names for pipeline stages from config."""
    return {
        "primary": get_config_value("welding", "forms", "extraction", "models", "primary",
                                    default="sonnet"),
        "secondary": get_config_value("welding", "forms", "extraction", "models", "secondary",
                                      default="sonnet"),
        "shadow": get_config_value("welding", "forms", "extraction", "models", "shadow",
                                   default="opus"),
    }


def _get_confidence_config() -> Dict[str, float]:
    """Get confidence thresholds from config."""
    return {
        "minimum": float(get_config_value("welding", "forms", "extraction", "confidence",
                                          "minimum", default=0.6)),
        "high": float(get_config_value("welding", "forms", "extraction", "confidence",
                                       "high", default=0.9)),
        "shadow_review_rate": float(get_config_value(
            "welding", "forms", "extraction", "confidence",
            "shadow_review_rate", default=0.10)),
    }


def _call_model(prompt: str, model: str = "sonnet") -> str:
    """
    Call an AI model with the given prompt.

    Uses the Anthropic SDK if available, otherwise raises ImportError.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "anthropic SDK is required for extraction. "
            "Install with: pip install anthropic>=0.25.0"
        )

    model_map = {
        "haiku": "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-6",
    }
    model_id = model_map.get(model, model)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model_id,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def _cross_check(primary: Dict[str, Any], secondary: Dict[str, Any],
                 numeric_tolerance: float = 0.05) -> tuple[Dict[str, Any], List[Dict], float]:
    """
    Compare two extraction results and merge.

    Returns:
        Tuple of (merged_data, disagreements, confidence_score).
    """
    disagreements: List[Dict] = []
    merged = {}

    # Compare parent fields
    p1 = primary.get("parent", {})
    p2 = secondary.get("parent", {})
    merged_parent = {}

    all_keys = set(list(p1.keys()) + list(p2.keys()))
    agree_count = 0
    total_count = 0

    for key in all_keys:
        v1 = p1.get(key)
        v2 = p2.get(key)

        if v1 is None and v2 is None:
            continue

        total_count += 1

        if v1 == v2:
            merged_parent[key] = v1
            agree_count += 1
        elif v1 is None:
            merged_parent[key] = v2
            agree_count += 0.5
        elif v2 is None:
            merged_parent[key] = v1
            agree_count += 0.5
        else:
            # Check numeric tolerance
            try:
                n1, n2 = float(v1), float(v2)
                if abs(n1 - n2) <= abs(n1) * numeric_tolerance:
                    merged_parent[key] = v1  # Use primary
                    agree_count += 0.9
                else:
                    disagreements.append({
                        "field": key,
                        "table": "parent",
                        "primary": v1,
                        "secondary": v2,
                    })
                    merged_parent[key] = v1  # Default to primary
            except (ValueError, TypeError):
                # String mismatch
                disagreements.append({
                    "field": key,
                    "table": "parent",
                    "primary": v1,
                    "secondary": v2,
                })
                merged_parent[key] = v1  # Default to primary

    merged["parent"] = merged_parent

    # Compare child arrays (use primary if same count, flag if different)
    child_keys = set(list(primary.keys()) + list(secondary.keys())) - {"parent"}
    for key in child_keys:
        c1 = primary.get(key, [])
        c2 = secondary.get(key, [])

        if not isinstance(c1, list):
            c1 = []
        if not isinstance(c2, list):
            c2 = []

        if len(c1) == len(c2):
            merged[key] = c1  # Use primary
            agree_count += 1
            total_count += 1
        elif len(c1) > 0 and len(c2) == 0:
            merged[key] = c1
            total_count += 1
            agree_count += 0.5
        elif len(c2) > 0 and len(c1) == 0:
            merged[key] = c2
            total_count += 1
            agree_count += 0.5
        else:
            # Different counts — flag disagreement, use longer list
            disagreements.append({
                "field": key,
                "table": "children",
                "primary": f"{len(c1)} entries",
                "secondary": f"{len(c2)} entries",
            })
            merged[key] = c1 if len(c1) >= len(c2) else c2
            total_count += 1

    confidence = agree_count / total_count if total_count > 0 else 0.0
    return merged, disagreements, confidence


def _log_extraction(conn, result: PipelineResult):
    """Write extraction result to weld_extraction_log."""
    conn.execute(
        """INSERT INTO weld_extraction_log (
               form_type, source_file, identifier, status, confidence,
               primary_model, secondary_model, shadow_model,
               disagreements_json, extracted_data_json, validation_issues_json,
               parent_record_id, child_records_json, processing_time_ms
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            result.form_type,
            result.source_file,
            result.identifier,
            result.status,
            result.confidence,
            "sonnet", "sonnet",
            "opus" if result.disagreements else None,
            json.dumps(result.disagreements) if result.disagreements else None,
            json.dumps(result.data) if result.data else None,
            json.dumps(result.validation_issues) if result.validation_issues else None,
            result.parent_record_id,
            json.dumps(result.child_record_counts) if result.child_record_counts else None,
            result.processing_time_ms,
        ),
    )


def run_pipeline(pdf_path: str | Path, form_type: Optional[str] = None,
                 dry_run: bool = False) -> PipelineResult:
    """
    Run the full extraction pipeline on a single PDF.

    Args:
        pdf_path: Path to PDF file.
        form_type: Form type override (auto-detected if None).
        dry_run: If True, validate but don't write to database.

    Returns:
        PipelineResult with extraction outcome.
    """
    from qms.welding.extraction.extractor import (
        extract_pdf_text, build_extraction_prompt,
        parse_extraction_response, detect_form_type,
    )
    from qms.welding.extraction.loader import load_to_database
    from qms.welding.validation import validate_form_data
    from qms.welding.seed_lookups import get_valid_values

    pdf_path = Path(pdf_path)
    start_time = time.time()

    result = PipelineResult(
        source_file=pdf_path.name,
        form_type=form_type or "unknown",
    )

    try:
        # Step 1: Extract text
        raw_text = extract_pdf_text(pdf_path)
        if not raw_text.strip():
            result.status = "failed"
            result.errors.append("No text extracted from PDF")
            return result

        # Step 2: Detect form type if not provided
        if not form_type:
            form_type = detect_form_type(pdf_path, raw_text)
            if not form_type:
                result.status = "failed"
                result.errors.append("Could not determine form type")
                return result
            result.form_type = form_type

        # Step 3: Get valid values for prompt
        with get_db(readonly=True) as conn:
            valid_values = get_valid_values(conn)

        # Step 4: Build prompt and run dual extraction
        prompt = build_extraction_prompt(raw_text, form_type, valid_values)
        models = _get_model_config()
        conf_config = _get_confidence_config()

        logger.info("Running primary extraction (%s)...", models["primary"])
        primary_response = _call_model(prompt, models["primary"])
        primary_data = parse_extraction_response(primary_response)

        logger.info("Running secondary extraction (%s)...", models["secondary"])
        secondary_response = _call_model(prompt, models["secondary"])
        secondary_data = parse_extraction_response(secondary_response)

        # Step 5: Cross-check
        merged_data, disagreements, confidence = _cross_check(
            primary_data, secondary_data,
            numeric_tolerance=float(get_config_value(
                "welding", "forms", "extraction", "numeric_tolerance", default=0.05)),
        )
        result.data = merged_data
        result.disagreements = disagreements
        result.confidence = confidence

        # Step 6: Shadow review if disagreements exist
        if disagreements and confidence < conf_config["high"]:
            logger.info("Disagreements found (%d), running shadow review (%s)...",
                        len(disagreements), models["shadow"])
            shadow_response = _call_model(prompt, models["shadow"])
            shadow_data = parse_extraction_response(shadow_response)
            # Shadow review resolves disagreements — use shadow for disputed fields
            parent = merged_data.get("parent", {})
            shadow_parent = shadow_data.get("parent", {})
            for d in disagreements:
                field_name = d["field"]
                if field_name in shadow_parent:
                    parent[field_name] = shadow_parent[field_name]
                    d["resolution"] = "shadow"
                    d["shadow_value"] = shadow_parent[field_name]
            merged_data["parent"] = parent

        # Extract identifier
        from qms.welding.forms import get_form_definition
        form_def = get_form_definition(form_type)
        id_col = form_def.identifier_column
        result.identifier = merged_data.get("parent", {}).get(id_col)

        # Step 7: Validate
        with get_db(readonly=True) as conn:
            validation = validate_form_data(merged_data, form_type, conn)

        result.validation_issues = [
            {"code": i.rule_code, "severity": i.severity,
             "message": i.message, "field": i.field}
            for i in validation.issues
        ]

        if not validation.is_valid:
            if confidence < conf_config["minimum"]:
                result.status = "failed"
                result.errors.append(
                    f"Validation failed with {validation.error_count} errors "
                    f"and confidence {confidence:.2f} below minimum {conf_config['minimum']}"
                )
                return result
            else:
                result.status = "partial"
        else:
            result.status = "success"

        # Step 8: Load to database
        if not dry_run:
            with get_db() as conn:
                load_result = load_to_database(merged_data, conn, form_def)
                result.parent_record_id = load_result.get("parent_id")
                result.child_record_counts = load_result.get("child_counts", {})
                _log_extraction(conn, result)
                conn.commit()
        else:
            logger.info("[DRY RUN] Would load: %s = %s",
                        id_col, result.identifier)

    except Exception as e:
        result.status = "failed"
        result.errors.append(str(e))
        logger.error("Pipeline error for %s: %s", pdf_path.name, e)

    result.processing_time_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Pipeline %s: %s (%s) confidence=%.2f time=%dms",
        result.status, result.source_file, result.identifier or "?",
        result.confidence, result.processing_time_ms,
    )
    return result


def run_batch(pdf_dir: str | Path, form_type: Optional[str] = None,
              pattern: str = "*.pdf", dry_run: bool = False) -> List[PipelineResult]:
    """
    Run extraction pipeline on all PDFs in a directory.

    Args:
        pdf_dir: Directory containing PDF files.
        form_type: Form type override (auto-detected per file if None).
        pattern: Glob pattern for PDF files.
        dry_run: If True, validate but don't write to database.

    Returns:
        List of PipelineResult for each file processed.
    """
    pdf_dir = Path(pdf_dir)
    if not pdf_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {pdf_dir}")

    pdfs = sorted(pdf_dir.glob(pattern))
    if not pdfs:
        logger.warning("No files matching '%s' in %s", pattern, pdf_dir)
        return []

    logger.info("Processing %d files from %s", len(pdfs), pdf_dir)
    results: List[PipelineResult] = []

    for i, pdf_path in enumerate(pdfs, 1):
        logger.info("[%d/%d] Processing %s...", i, len(pdfs), pdf_path.name)
        result = run_pipeline(pdf_path, form_type=form_type, dry_run=dry_run)
        results.append(result)

    # Summary
    success = sum(1 for r in results if r.status == "success")
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "failed")
    logger.info(
        "Batch complete: %d success, %d partial, %d failed (of %d total)",
        success, partial, failed, len(results),
    )
    return results
