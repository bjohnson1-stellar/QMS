# Reference Standard Extraction Redesign - Context Handoff

Created: 2026-02-04
Purpose: Preserve context for planning parallelized reference extraction system

---

## Goal

Design a **parallelized agent-based extraction system** for reference standards (ISO, ASME, AWS, etc.) that:
1. Splits documents into **logical sections** (not arbitrary page ranges)
2. Saves section files in `D:\Quality Documents\References\` as extraction records
3. Uses **smaller context windows** for improved accuracy
4. Mirrors the architecture of drawing extraction agents

---

## Current State

### Existing Infrastructure

| Component | Location | Status |
|-----------|----------|--------|
| Extraction script | `D:\QC-DR\extract_reference.py` | Single-threaded Python, uses pdftotext |
| Main table | `qm_references` | Stores PDF metadata, extraction status |
| Clauses table | `ref_clauses` | Clause numbers, titles, hierarchy |
| Content table | `ref_content_blocks` | Text blocks typed (Paragraph, Note, Warning, Table) |
| FTS index | `ref_content_fts` | SQLite FTS5 full-text search |
| Procedure links | `ref_procedure_links` | Links procedures to standard clauses |
| Command | `/sis-refs extract <standard-id>` | Orchestrates extraction |

### Current Extraction Flow (Single-Threaded)
```
PDF → pdftotext (whole document) → regex clause parsing → database insert
```

### Limitations
- No parallelization (large PDFs like ASME BPVC are slow)
- Whole-document context exceeds optimal window sizes
- No intermediate files for human review
- Regex-based parsing misses context-dependent boundaries

---

## Sample Document in System

- **File**: `D:\Quality Documents\References\ASME-BPVC-2013.pdf`
- **Standard ID**: `ASME-BPVC-2013`
- **Size**: 4.8 MB
- **Status**: `content_extracted = 0` (not yet extracted)
- **Hash**: `d11261aa972babbb72dfdae7e1ecffc0`

Also present: `ISO9001-2015.pdf` (already extracted for reference)

---

## User Requirements

1. **Logical section splitting** - Split by content structure (TOC, section headers) not page numbers
2. **Section files saved** - Each section becomes a file in References folder for:
   - Record of what was extracted
   - Human-searchable outside the database
3. **Parallelized agents** - Similar to drawing extraction pipeline
4. **Smaller context windows** - Each agent processes one section for accuracy

---

## Drawing Extraction Architecture (Model to Follow)

The SIS drawing extraction uses these agent types:
- `sis-extractor` - Extracts data from individual sheets
- `sis-validator` - Validates extraction quality
- `sis-shadow-reviewer` - Opus-based QA sampling (10%)
- `sis-cross-checker` - Detects conflicts across drawings

Orchestration via `/sis-go` with wave-based parallelization.

---

## Database Schema (Existing)

```sql
-- Main reference record
CREATE TABLE qm_references (
    id INTEGER PRIMARY KEY,
    standard_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    edition TEXT,
    publisher TEXT,
    category TEXT,
    file_path TEXT,
    file_hash TEXT,
    status TEXT DEFAULT 'CURRENT',
    content_extracted INTEGER DEFAULT 0,
    extraction_date TIMESTAMP,
    extraction_method TEXT
);

-- Clauses
CREATE TABLE ref_clauses (
    id INTEGER PRIMARY KEY,
    reference_id INTEGER NOT NULL REFERENCES qm_references(id),
    clause_number TEXT NOT NULL,
    clause_title TEXT,
    parent_clause_id INTEGER REFERENCES ref_clauses(id),
    requirement_summary TEXT,
    UNIQUE(reference_id, clause_number)
);

-- Content blocks
CREATE TABLE ref_content_blocks (
    id INTEGER PRIMARY KEY,
    clause_id INTEGER NOT NULL REFERENCES ref_clauses(id),
    block_type TEXT NOT NULL,  -- Paragraph, Note, Warning, Table, etc.
    content TEXT NOT NULL,
    page_number INTEGER,
    display_order INTEGER
);

-- FTS index
CREATE VIRTUAL TABLE ref_content_fts USING fts5(
    standard_id, clause_number, clause_title, block_type, content
);
```

---

## Proposed Architecture (To Be Designed)

### New Agents Needed
1. **ref-section-splitter** - Analyzes PDF structure, identifies logical sections, creates section files
2. **ref-section-extractor** - Extracts clauses/content from one section (parallel)
3. **ref-merger** - Combines extracted data, resolves cross-references
4. **ref-validator** - Quality checks on extraction

### New Database Tables (Likely)
- `ref_sections` - Track section files and extraction status
- `ref_extraction_log` - Audit trail of extraction runs

### File Organization
```
D:\Quality Documents\References\
├── ASME-BPVC-2013.pdf              # Original PDF
├── ASME-BPVC-2013\                  # Section folder
│   ├── _manifest.json              # Section inventory
│   ├── Section-I-Power-Boilers.pdf
│   ├── Section-VIII-Div1-Pressure-Vessels.pdf
│   ├── Section-IX-Welding.pdf
│   └── ...
```

---

## Key Files to Study

| File | Purpose |
|------|---------|
| `D:\QC-DR\extract_reference.py` | Current extraction logic, clause patterns |
| `D:\.claude\commands\sis-refs.md` | Current `/sis-refs` command definition |
| `D:\QC-DR\config.yaml` | System configuration, model routing |
| Drawing agent definitions | Model for new agent structure |

---

## Next Steps

1. Enter planning mode in fresh conversation
2. Read this handoff document
3. Study drawing extraction agents for architecture patterns
4. Design section-splitting strategy (TOC parsing, AI-detected boundaries)
5. Define new agents and database schema
6. Create implementation plan

---

## Command to Start Fresh Session

```
Tell Claude: "Read D:/.planning/ref-extraction-redesign-handoff.md and enter planning mode to design the parallelized reference extraction system"
```
