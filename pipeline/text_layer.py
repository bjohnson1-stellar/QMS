"""Text layer preprocessor — extract embedded text + coordinates from CAD PDFs.

Uses PyMuPDF (fitz) to extract every text string with bounding box coordinates
from CAD-generated PDFs. This data supplements the vision prompt so the AI model
can identify equipment tags regardless of image resolution. Also provides
cross-validation of Docling schedule extractions.

Part of v0.4 Equipment-Centric Platform (Phases 27-02a, 27-03).
"""

import re
from typing import Dict, List

from qms.core import get_db, get_logger

logger = get_logger("qms.pipeline.text_layer")

# Equipment tag patterns
# Standard: 2-5 letters + dash + 1-4 digits (RAHU-1, RCU-4, AHU-12)
_TAG_WITH_DASH = re.compile(r"^[A-Z]{2,5}-\d{1,4}$")
# Short: 2-3 letters + 1-3 digits, no dash (PT3, FI5, CV2) — min 3 chars
_TAG_NO_DASH = re.compile(r"^[A-Z]{2,3}\d{1,3}$")


def _is_equipment_tag(text: str) -> bool:
    """Check if text looks like an equipment tag."""
    upper = text.strip().upper()
    if not upper or len(upper) < 3:
        return False
    if _TAG_WITH_DASH.match(upper):
        return True
    if _TAG_NO_DASH.match(upper):
        return True
    return False


def extract_text_layer(file_path: str, page_num: int = 0) -> dict:
    """Extract all text with bounding boxes from a PDF page.

    Uses PyMuPDF (fitz) to get embedded text from CAD-generated PDFs.

    Args:
        file_path: Path to the PDF file.
        page_num: Page number (0-indexed). Defaults to first page.

    Returns:
        {
            "page_count": int,
            "page_width": float,
            "page_height": float,
            "text_blocks": [
                {"text": str, "x0": float, "y0": float, "x1": float, "y1": float},
                ...
            ],
            "equipment_tags": ["RAHU-1", "RCU-4", ...],
        }
    """
    import fitz

    doc = fitz.open(file_path)
    page_count = doc.page_count

    if page_num >= page_count:
        doc.close()
        return {
            "page_count": page_count,
            "page_width": 0,
            "page_height": 0,
            "text_blocks": [],
            "equipment_tags": [],
        }

    page = doc[page_num]
    page_width = round(page.rect.width, 1)
    page_height = round(page.rect.height, 1)
    data = page.get_text("dict")

    text_blocks = []
    equipment_tags = set()

    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue
                bbox = span.get("bbox", (0, 0, 0, 0))
                text_blocks.append({
                    "text": text,
                    "x0": round(bbox[0], 1),
                    "y0": round(bbox[1], 1),
                    "x1": round(bbox[2], 1),
                    "y1": round(bbox[3], 1),
                })

                if _is_equipment_tag(text):
                    equipment_tags.add(text.strip().upper())

    doc.close()

    return {
        "page_count": page_count,
        "page_width": page_width,
        "page_height": page_height,
        "text_blocks": text_blocks,
        "equipment_tags": sorted(equipment_tags),
    }


def format_text_layer_for_prompt(text_data: dict, max_lines: int = 200) -> str:
    """Format extracted text layer as a prompt section.

    Prioritizes equipment-tag-containing blocks, then positional order.

    Args:
        text_data: Output from extract_text_layer().
        max_lines: Maximum text entries to include.

    Returns:
        Formatted string for injection into extraction prompts.
    """
    blocks = text_data.get("text_blocks", [])
    if not blocks:
        return ""

    tags_set = set(text_data.get("equipment_tags", []))

    # Partition: tag-bearing blocks first, then rest by position
    tag_blocks = []
    other_blocks = []
    for b in blocks:
        if b["text"].strip().upper() in tags_set:
            tag_blocks.append(b)
        else:
            other_blocks.append(b)

    # Sort each group by position (top-to-bottom bands, then left-to-right)
    def sort_key(b):
        return (round(b["y0"] / 50) * 50, b["x0"])

    tag_blocks.sort(key=sort_key)
    other_blocks.sort(key=sort_key)

    # Combine: tags first, then others, capped at max_lines
    selected = (tag_blocks + other_blocks)[:max_lines]

    page_w = text_data.get("page_width", 1) or 1
    page_h = text_data.get("page_height", 1) or 1

    lines = []
    for b in selected:
        x_pct = round(b["x0"] / page_w * 100)
        y_pct = round(b["y0"] / page_h * 100)
        lines.append(f'  ({x_pct}%, {y_pct}%) "{b["text"]}"')

    tag_list = text_data.get("equipment_tags", [])

    header = (
        "TEXT LAYER DATA (extracted from PDF embedded text):\n"
        f"Page size: {text_data.get('page_width', 0):.0f} x "
        f"{text_data.get('page_height', 0):.0f} points\n"
        f"Equipment tags detected: {', '.join(tag_list) if tag_list else 'none'}\n"
        f"Text entries ({len(selected)} of {len(blocks)}):\n"
    )

    instruction = (
        "\n\nUse BOTH the visual image AND the text layer above to identify "
        "equipment. The text layer contains every text string embedded in the "
        "PDF with approximate coordinates (as % of page width/height). Use it "
        "to find tags that may be too small to read in the image."
    )

    return header + "\n".join(lines) + instruction


def extract_all_pages_tags(file_path: str) -> set:
    """Extract equipment tags from ALL pages of a PDF."""
    import fitz

    tags = set()
    try:
        doc = fitz.open(file_path)
        for page_num in range(doc.page_count):
            page = doc[page_num]
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text and _is_equipment_tag(text):
                            tags.add(text.upper())
        doc.close()
    except Exception as e:
        logger.warning("Failed to extract tags from %s: %s", file_path, e)
    return tags


def _extract_all_text_strings(file_path: str) -> set:
    """Extract ALL non-empty text strings from all pages of a PDF (uppercase)."""
    import fitz

    texts = set()
    try:
        doc = fitz.open(file_path)
        for page_num in range(doc.page_count):
            page = doc[page_num]
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            texts.add(text.upper())
        doc.close()
    except Exception as e:
        logger.warning("Failed to extract text from %s: %s", file_path, e)
    return texts


def _find_near_matches(tag: str, candidates: set, max_dist: int = 1) -> List[str]:
    """Find tags in candidates within edit distance max_dist of tag."""
    matches = []
    for c in candidates:
        if c == tag:
            continue
        if abs(len(c) - len(tag)) > max_dist:
            continue
        # Simple single-char difference check
        if len(c) == len(tag):
            diffs = sum(1 for a, b in zip(c, tag) if a != b)
            if diffs <= max_dist:
                matches.append(c)
        elif abs(len(c) - len(tag)) == 1:
            # Insertion/deletion — check if removing one char makes them equal
            longer, shorter = (c, tag) if len(c) > len(tag) else (tag, c)
            for i in range(len(longer)):
                if longer[:i] + longer[i + 1:] == shorter:
                    matches.append(c)
                    break
    return matches


def validate_schedule_against_text_layer(project_id: int) -> dict:
    """Cross-reference Docling schedule extractions against PDF text layer.

    For each schedule sheet:
    1. Extract ALL text strings from the PDF (not just regex-matched tags)
    2. Query schedule_extractions for Docling-extracted tags
    3. Check if each Docling tag appears anywhere in the PDF text
    4. Also detect equipment tags in PDF text that Docling didn't extract

    Returns:
        {
            "sheets_checked": int,
            "total_docling_tags": int,
            "confirmed": int,
            "docling_only": [{"sheet_id": int, "tag": str, "drawing": str}, ...],
            "text_only": [{"sheet_id": int, "tag": str, "drawing": str}, ...],
            "misread_candidates": [{"sheet_id": int, "docling": str, "text": str, "drawing": str}, ...],
            "per_sheet": [...],
            "no_text_sheets": [str],  # Scanned PDFs with no embedded text
        }
    """
    with get_db(readonly=True) as conn:
        sheets = conn.execute(
            """SELECT DISTINCT se.sheet_id, s.drawing_number, s.file_path
               FROM schedule_extractions se
               JOIN sheets s ON s.id = se.sheet_id
               WHERE se.project_id = ?
               ORDER BY s.drawing_number""",
            (project_id,),
        ).fetchall()

        results = {
            "sheets_checked": 0,
            "total_docling_tags": 0,
            "confirmed": 0,
            "docling_only": [],
            "text_only": [],
            "misread_candidates": [],
            "per_sheet": [],
            "no_text_sheets": [],
        }

        for sheet in sheets:
            sheet_id = sheet["sheet_id"]
            drawing = sheet["drawing_number"]
            file_path = sheet["file_path"]

            # Get Docling tags
            docling_rows = conn.execute(
                "SELECT tag FROM schedule_extractions WHERE sheet_id = ? AND project_id = ?",
                (sheet_id, project_id),
            ).fetchall()
            docling_tags = {row["tag"].upper() for row in docling_rows}

            # Get ALL text strings from the PDF (not just regex-matched tags)
            all_text = _extract_all_text_strings(file_path)

            if not all_text:
                results["no_text_sheets"].append(drawing)
                results["sheets_checked"] += 1
                results["total_docling_tags"] += len(docling_tags)
                results["per_sheet"].append({
                    "sheet_id": sheet_id,
                    "drawing": drawing,
                    "docling": len(docling_tags),
                    "text": 0,
                    "confirmed": 0,
                    "note": "scanned PDF — no embedded text",
                })
                continue

            # Check each Docling tag against raw PDF text
            confirmed = set()
            d_only = set()
            for tag in docling_tags:
                if tag in all_text:
                    confirmed.add(tag)
                else:
                    d_only.add(tag)

            # Also find equipment tags in text that Docling missed
            equip_tags = extract_all_pages_tags(file_path)
            t_only = equip_tags - docling_tags

            results["sheets_checked"] += 1
            results["total_docling_tags"] += len(docling_tags)
            results["confirmed"] += len(confirmed)

            for tag in sorted(d_only):
                near = _find_near_matches(tag, all_text)
                if near:
                    results["misread_candidates"].append({
                        "sheet_id": sheet_id,
                        "docling": tag,
                        "text": near[0],
                        "drawing": drawing,
                    })
                else:
                    results["docling_only"].append({
                        "sheet_id": sheet_id,
                        "tag": tag,
                        "drawing": drawing,
                    })

            for tag in sorted(t_only):
                results["text_only"].append({
                    "sheet_id": sheet_id,
                    "tag": tag,
                    "drawing": drawing,
                })

            results["per_sheet"].append({
                "sheet_id": sheet_id,
                "drawing": drawing,
                "docling": len(docling_tags),
                "text": len(equip_tags),
                "confirmed": len(confirmed),
            })

    logger.info(
        "Schedule validation: %d sheets, %d confirmed, %d docling-only, %d text-only, %d misread candidates",
        results["sheets_checked"], results["confirmed"],
        len(results["docling_only"]), len(results["text_only"]),
        len(results["misread_candidates"]),
    )
    return results
