"""Docling-based table extraction for schedule drawings.

Uses IBM Docling (TableFormer model) for structured table extraction from
CAD-generated PDFs. Provides column mapping to schedule_extractions fields
and discipline-specific prompts for Claude vision fallback.

Docling is an optional dependency — import is lazy with a clear error message.

Part of v0.4 Equipment-Centric Platform (Phase 25).
"""

import re
from typing import Any, Dict, List, Optional

from qms.core import get_logger

logger = get_logger("qms.pipeline.docling_extractor")

# Lazy-initialized converter (reuse across calls)
_converter = None


def _get_converter():
    """Get or create the Docling DocumentConverter (lazy singleton)."""
    global _converter
    if _converter is None:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError:
            raise ImportError(
                "Docling is not installed. Install with: pip install docling"
            )
        _converter = DocumentConverter()
        logger.info("Docling DocumentConverter initialized")
    return _converter


# --- Column name matching patterns ---
# Maps regex patterns to schedule_extractions field names

_COLUMN_PATTERNS = {
    "tag": re.compile(
        r"^(mark|tag|unit|item|equip\w*\s*tag|designation)$", re.I
    ),
    "description": re.compile(
        r"^(area\s*served|description|service|location|room|serving)$", re.I
    ),
    "equipment_type": re.compile(
        r"^(type|equipment\s*type|style)$", re.I
    ),
    "hp": re.compile(
        r"^(hp|hp\s*each|motor\s*hp|horsepower|bhp)$", re.I
    ),
    "kva": re.compile(
        r"^(kva|kw|capacity\s*\(kw\)|heating\s*capacity|watts|input\s*kw)$", re.I
    ),
    "voltage": re.compile(
        r"^(v/ph/hz|voltage|electrical|volts|electrical\s*v/ph/hz)$", re.I
    ),
    "amperage": re.compile(
        r"^(mca|amperage|fla|amps|full\s*load\s*amps|rla)$", re.I
    ),
    "phase_count": re.compile(
        r"^(phase|ph|phases)$", re.I
    ),
    "circuit": re.compile(
        r"^(circuit|ckt|breaker|circuit\s*number)$", re.I
    ),
    "panel_source": re.compile(
        r"^(panel|fed\s*from|panel\s*source|source|supply\s*from)$", re.I
    ),
    "manufacturer": re.compile(
        r"^(manufacturer|mfr|mfg|basis\s*of\s*design[\.\s]*manufacturer)$", re.I
    ),
    "model_number": re.compile(
        r"^(model|model\s*number|model\s*no|basis\s*of\s*design[\.\s]*model)$", re.I
    ),
    "weight_lbs": re.compile(
        r"^(weight|weight\s*\(lbs?\)|operating\s*weight|wt)$", re.I
    ),
    "cfm": re.compile(
        r"^(cfm|air\s*flow|air\s*flow[\.\s]*cfm|airflow|volume)$", re.I
    ),
}


def _match_column(header: str) -> Optional[str]:
    """Match a column header to a schedule_extractions field name.

    Returns field name or None if no match.
    """
    # Clean up the header: strip whitespace, remove trailing dots/periods
    clean = header.strip().rstrip(".")

    # Try direct pattern match first
    for field, pattern in _COLUMN_PATTERNS.items():
        if pattern.search(clean):
            return field

    # Try matching last segment of dotted headers (e.g., "BASIS OF DESIGN.MODEL")
    if "." in clean:
        last_segment = clean.rsplit(".", 1)[-1].strip()
        for field, pattern in _COLUMN_PATTERNS.items():
            if pattern.search(last_segment):
                return field

    return None


def _parse_numeric(value: str) -> Optional[float]:
    """Extract numeric value from a string, handling commas and units."""
    if not value or not isinstance(value, str):
        return None
    # Remove commas, common suffixes
    cleaned = re.sub(r"[,\s]", "", value)
    cleaned = re.sub(r"(lbs?|hp|kw|kva|cfm|amps?|gpm|ft)\.?$", "", cleaned, flags=re.I)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def extract_tables_from_pdf(file_path: str) -> List[Dict[str, Any]]:
    """Extract all tables from a PDF using Docling.

    Returns list of dicts, each with:
      - table_index: int
      - page_number: int (1-based)
      - headers: list of column names
      - rows: list of dicts (column_name -> value)
      - row_count: int
      - col_count: int
    """
    converter = _get_converter()
    result = converter.convert(file_path)
    doc = result.document

    tables = []
    for i, table in enumerate(doc.tables):
        try:
            df = table.export_to_dataframe(doc)
        except TypeError:
            # Older docling versions don't accept doc param
            df = table.export_to_dataframe()

        if df.empty:
            continue

        headers = list(df.columns)
        rows = []
        for _, row in df.iterrows():
            row_dict = {}
            for col in headers:
                val = row[col]
                if val is not None and str(val).strip():
                    row_dict[col] = str(val).strip()
            if row_dict:
                rows.append(row_dict)

        # Determine page number from table's location in the document
        page_num = 1
        if hasattr(table, "prov") and table.prov:
            prov = table.prov[0] if isinstance(table.prov, list) else table.prov
            if hasattr(prov, "page_no"):
                page_num = prov.page_no

        tables.append({
            "table_index": i,
            "page_number": page_num,
            "headers": headers,
            "rows": rows,
            "row_count": len(rows),
            "col_count": len(headers),
        })

    logger.info(
        "Docling extracted %d tables from %s",
        len(tables), file_path,
    )
    return tables


def tables_to_equipment(tables: List[Dict], discipline: str) -> List[Dict]:
    """Convert Docling table output to harness-compatible equipment entries.

    Maps column headers to schedule_extractions fields using fuzzy matching.
    Skips rows without a tag/mark value.

    Returns list of equipment dicts ready for store_schedule_data().
    """
    entries = []

    for table in tables:
        headers = table.get("headers", [])
        page_number = table.get("page_number", 1)

        # Build column mapping for this table
        col_map = {}  # original_header -> field_name
        for header in headers:
            field = _match_column(header)
            if field:
                col_map[header] = field

        # Need at least a tag column
        tag_headers = [h for h, f in col_map.items() if f == "tag"]
        if not tag_headers:
            logger.debug(
                "Table %d has no tag/mark column (headers: %s) — skipping",
                table.get("table_index", 0), headers[:5],
            )
            continue

        tag_header = tag_headers[0]

        for row in table.get("rows", []):
            tag_val = row.get(tag_header, "").strip()
            if not tag_val:
                continue

            entry = {"tag": tag_val, "page_number": page_number}

            for header, field in col_map.items():
                if field == "tag":
                    continue
                val = row.get(header, "")
                if not val:
                    continue

                # Convert numeric fields
                if field in ("hp", "kva", "amperage", "weight_lbs", "cfm"):
                    numeric = _parse_numeric(val)
                    if numeric is not None:
                        entry[field] = numeric
                elif field == "phase_count":
                    numeric = _parse_numeric(val)
                    if numeric is not None:
                        entry[field] = int(numeric)
                else:
                    entry[field] = val

            entries.append(entry)

    logger.info(
        "Mapped %d equipment entries from %d tables (%s)",
        len(entries), len(tables), discipline,
    )
    return entries


def get_discipline_prompt(discipline: str) -> str:
    """Get discipline-specific extraction prompt for Claude vision agents.

    Returns a focused prompt tailored to the equipment types and attributes
    expected for this discipline's schedule drawings.
    """
    prompts = {
        "Electrical": """Extract all electrical panel schedules and load schedules from this drawing.

For each PANEL, extract:
- tag: Panel name (e.g., "1HMSB", "1HMCC041", "1HH041")
- equipment_type: "Switchboard", "Distribution Panel", "Lighting Panel", "Motor Control Center"
- voltage (e.g., "480/277V", "208/120V")
- phase_count: Number of phases (1 or 3)
- amperage: Main bus rating
- panel_source: What feeds this panel (fed from)

For each CIRCUIT LOAD in the panel, extract:
- tag: Equipment tag served (e.g., "EF-1", "P-H1")
- equipment_type: "Motor", "Equipment", "Transformer"
- hp: Horsepower (for motors)
- kva: KVA rating
- amperage: Breaker/trip amps
- circuit: Circuit number
- panel_source: Which panel it's in
- Additional: starter type (FVNR/VFD), frame amps

Return as JSON array. Include both panels AND their loads as separate entries.""",

        "Refrigeration": """Extract all refrigeration equipment schedules from this drawing.

For AIR HANDLING UNITS (RAHU), extract:
- tag: Unit tag (e.g., "RAHU-1"). If grouped (e.g., "RAHU-1 TO RAHU-3"), create SEPARATE entries for each unit.
- equipment_type: "Air Handling Unit"
- manufacturer, model_number
- hp: Fan motor HP (per fan)
- voltage (e.g., "460/3/60")
- weight_lbs
- Additional: capacity TR, fan count, coil temp, room temp, refrigerant

For CONDENSING UNITS (RCU), extract:
- tag: Unit tag (e.g., "RCU-1")
- equipment_type: "Condensing Unit"
- manufacturer, model_number
- hp: Compressor motor HP
- voltage
- weight_lbs
- Additional: capacity TR, compressor count, refrigerant type, suction temp

Return as JSON array. EXPAND grouped tags into individual entries.""",

        "Mechanical": """Extract all HVAC and mechanical equipment schedules from this drawing.

Equipment types to look for:
- HVLS fans, exhaust fans, supply fans → tag, CFM, HP, voltage, weight, manufacturer, model
- Unit heaters, cabinet heaters, trench heaters → tag, KW, voltage, manufacturer, model
- RTUs (rooftop units) → tag, CFM, tonnage, voltage, weight, manufacturer, model
- ERVs (energy recovery ventilators) → tag, CFM, voltage
- CRAC units → tag, CFM, capacity MBH, voltage, weight, manufacturer, model
- Air curtains → tag, CFM, HP, voltage, manufacturer, model
- Louvers → tag, size, service, manufacturer, model
- Gravity ventilators → tag, CFM, type (exhaust/intake)

Skip air distribution schedules (diffuser/grille type marks like A1, B1, D1) — those are product types, not installed equipment.

Return as JSON array.""",

        "Utility": """Extract all utility equipment schedules from this drawing.

Equipment types to look for:
- Pumps → tag, HP, flow GPM, head ft, RPM, voltage, manufacturer, model, service (CHW/HHW/DHW)
- Chillers → tag, capacity tons, voltage, refrigerant, weight, manufacturer, model
- Boilers/water heaters → tag, input BTU/hr, capacity gallons, voltage, manufacturer, model
- Air compressors → tag, HP, SCFM, pressure PSIG, voltage, manufacturer, model
- Air dryers → tag, SCFM, voltage, manufacturer, model
- Tanks (expansion, storage, receiver) → tag, capacity gallons, material, manufacturer, model
- Water softeners → tag, GPM, manufacturer, model
- Air separators → tag, GPM, manufacturer, model
- Safety fixtures (eyewash/shower) → tag, manufacturer, model
- Backflow preventers, hose bibbs → tag, manufacturer, model

Return as JSON array.""",

        "Plumbing": """Extract all plumbing fixture and equipment schedules from this drawing.

Equipment types to look for:
- Fixtures: water closets, urinals, lavatories, sinks, wash stations, showers, mop basins
- Floor drains, floor sinks, hub drains, cleanouts
- Pumps (sump, sewage, etc.)
- Water heaters (if not on utility drawings)

For each, extract:
- tag: Fixture/equipment tag (e.g., "WC-1", "FD-1", "S-3")
- description: Full description
- equipment_type: Type classification
- manufacturer, model_number
- Connection sizes if shown (waste, vent, DCW, DHW)
- HP (for pumps only)
- voltage (for pumps/electric fixtures only)

Return as JSON array.""",

        "Structural": """Extract any structural equipment schedules from this drawing.

Look for:
- Jib cranes, hoists, monorails → tag, capacity, manufacturer, model
- Equipment pads/supports → tag, dimensions, load capacity
- Structural steel schedules are NOT equipment — skip member schedules

If the drawing has no equipment schedules (only structural member schedules), return an empty array [].

Return as JSON array.""",
    }

    prompt = prompts.get(discipline)
    if prompt:
        return prompt

    # Default generic prompt
    return """Extract all equipment from the schedule tables on this drawing.

For each row in each schedule table, extract:
- tag: Equipment tag/identifier (REQUIRED — skip rows without tags)
- description: Equipment description or name
- equipment_type: Type of equipment
- hp, kva, voltage, amperage, phase_count, cfm, weight_lbs
- manufacturer, model_number
- circuit, panel_source

Return as JSON array. Only extract what is ACTUALLY shown. Do NOT fabricate."""
