"""
SOP Classifier — AI-powered PDF classification using Claude API.

Analyzes uploaded SOP PDFs and suggests:
- Category (one of 15 M4 categories)
- Scope tags (relevant keywords)
- Program linkages (M3 programs)
- Code references (industry codes/standards)
- Summary and document ID
"""

import base64
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from qms.core import QMS_PATHS
from qms.qualitydocs.db import (
    get_intake,
    list_categories,
    list_programs,
    next_document_id,
    update_intake,
)

logger = logging.getLogger(__name__)

_MODEL_MAP = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-5-20250929",
    "opus": "claude-opus-4-6",
}


def _build_classification_prompt(categories, programs):
    """Build the system prompt with category and program definitions."""
    cat_lines = []
    for c in categories:
        cat_lines.append(f"  - {c['category_code']} {c['name']}: {c.get('description', '')}")

    prog_lines = []
    for p in programs:
        codes = ""
        if p.get("primary_codes"):
            try:
                codes = ", ".join(json.loads(p["primary_codes"]))
            except (json.JSONDecodeError, TypeError):
                codes = str(p["primary_codes"])
        prog_lines.append(f"  - {p['program_id']} {p['title']} (codes: {codes})")

    return f"""You are a construction quality management expert classifying Standard Operating Procedures (SOPs) for an MEP (Mechanical, Electrical, Plumbing) contractor.

Analyze this PDF document and classify it into the SOP management system.

## Available M4 Categories (pick exactly one):
{chr(10).join(cat_lines)}

## Available M3 Quality Programs (pick zero or more):
{chr(10).join(prog_lines)}

## Instructions
1. Read the document thoroughly
2. Determine the best-fit M4 category based on subject matter
3. Identify which M3 programs this SOP relates to
4. Extract any industry code references (ASME, AWS, OSHA, NEC, NFPA, etc.)
5. Generate a concise 2-3 sentence summary
6. Suggest relevant scope tags (keywords for filtering)

## Response Format
Return ONLY valid JSON (no markdown fences, no explanation):
{{
  "suggested_category": {{
    "code": "4.XX",
    "name": "Category Name",
    "confidence": 0.95
  }},
  "suggested_scope_tags": ["tag1", "tag2", "tag3"],
  "suggested_programs": [
    {{
      "program_id": "SIS-3.XX",
      "name": "Program Name",
      "confidence": 0.85
    }}
  ],
  "code_references": [
    {{
      "code": "ASME B31.1",
      "organization": "ASME",
      "section": "Section reference if found",
      "original_text": "Brief quote where code is referenced"
    }}
  ],
  "summary": "2-3 sentence description of what this SOP covers.",
  "title": "Suggested title for the SOP based on document content"
}}"""


def _parse_json_response(text):
    """Parse JSON from Claude's response, handling markdown fences."""
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    cleaned = cleaned.strip()

    # Find the JSON object
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("No valid JSON found in response")


def classify_sop(intake_id, model="sonnet"):
    """Classify an SOP PDF using Claude API.

    Reads the PDF file, sends it to Claude for analysis, and updates
    the intake record with classification results.

    Args:
        intake_id: ID of the qm_sop_intake record.
        model: Model shorthand — 'haiku', 'sonnet', or 'opus'.
    """
    intake = get_intake(intake_id)
    if not intake:
        raise ValueError(f"Intake {intake_id} not found")

    # Mark as analyzing
    update_intake(intake_id, status="analyzing")

    try:
        # Read the PDF file
        file_path = intake.get("file_path")
        if not file_path:
            raise ValueError("No file_path on intake record")

        full_path = QMS_PATHS.package_root / "data" / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"PDF not found: {full_path}")

        pdf_bytes = full_path.read_bytes()
        pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

        # Load category and program definitions for the prompt
        categories = list_categories(module_number=4)
        programs = list_programs()

        prompt_text = _build_classification_prompt(categories, programs)

        # Call Claude API
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic SDK is required for SOP classification. "
                "Install with: pip install anthropic>=0.25.0"
            )

        model_id = _MODEL_MAP.get(model, model)
        client = anthropic.Anthropic()

        response = client.messages.create(
            model=model_id,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt_text,
                        },
                    ],
                }
            ],
        )

        response_text = response.content[0].text
        classification = _parse_json_response(response_text)

        # Resolve category code → category_id
        suggested_cat = classification.get("suggested_category", {})
        cat_code = suggested_cat.get("code", "")
        category_id = None
        for c in categories:
            if c["category_code"] == cat_code:
                category_id = c["id"]
                break

        # Resolve program IDs
        suggested_progs = classification.get("suggested_programs", [])
        program_ids = []
        for sp in suggested_progs:
            for p in programs:
                if p["program_id"] == sp.get("program_id"):
                    program_ids.append(p["id"])
                    break

        # Generate next document_id
        doc_id = None
        if cat_code:
            doc_id = next_document_id(cat_code)

        # Update intake with classification results
        update_intake(
            intake_id,
            status="classified",
            ai_classification=classification,
            suggested_category_id=category_id,
            suggested_scope_tags=classification.get("suggested_scope_tags", []),
            suggested_program_ids=program_ids,
            suggested_document_id=doc_id,
            processed_at=datetime.utcnow().isoformat(),
        )

        logger.info("SOP classified: intake=%d category=%s doc_id=%s", intake_id, cat_code, doc_id)

    except Exception as e:
        logger.error("SOP classification failed for intake %d: %s", intake_id, e)
        update_intake(
            intake_id,
            status="error",
            error_message=str(e),
        )
        raise
