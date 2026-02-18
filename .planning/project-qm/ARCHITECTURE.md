# Project-Specific Quality Manual Generator

> **NOTE (2026-02-18):** This feature has NOT been implemented yet. Path references
> below use old conventions — update before implementing:
> - `D:\Quality Documents\References\` → `D:\qms\data\quality-documents\References\`
> - `D:\Projects\{project}\` → `D:\qms\data\projects\{project}\`
> - `D:\VectorDB` → `D:\qms\data\vectordb\`
> - `/cq <command>` → `qms cq <command>` (Typer CLI)
> - `/sis-refs extract` → `qms refs extract`
> - "150+ table database" → 256 tables

## Feature Overview

A compliance engine that intakes customer quality documents, compares them against
Stellar's Quality Manual (with code standard validation when needed), and generates a
project-specific Quality Manual (PDF) highlighting deviations from standard requirements.

**2-Step Check Model:**
```
Step 1 (Primary):    Customer Requirements  vs.  Stellar QM
                     "What's different from our standard approach?"
                     ├── Same/equivalent → GREEN (done, no further check)
                     ├── Different → proceed to Step 2
                     └── New topic not in QM → YELLOW (human decides)

Step 2 (Validation): Only for differences found in Step 1 →
                     Check against discipline-scoped applicable codes
                     (from cover sheet of that discipline's drawing set)
                     ├── Code requires it → GREEN (auto-accept, code-driven)
                     ├── Code says something different → RED (conflict)
                     └── Code is silent → YELLOW (human decides)
```

**Why 2-step instead of 3-way merge:** Stellar's QM is already written to comply with
codes - it's the "code-compliant baseline." The QM rarely contradicts codes. So codes
only need to be consulted as a referee when customer requirements differ from the QM.

---

## Requirements Summary

| Aspect | Decision |
|---|---|
| **Input formats** | PDF, Word, any format - QA plans, ITPs, specs, contract clauses |
| **Extraction** | Clause-level requirements, grouped by QM topic (AI-classified) |
| **Comparison** | 2-step: Customer vs Stellar QM (primary), code check (validation only) |
| **Auto-resolve** | QM equivalent → green; Code requires it → green; Code conflict → red |
| **Human review** | Traffic light: Green (auto-resolved) / Yellow (needs review) / Red (conflict) |
| **Applicable codes** | Extracted from cover sheet of each discipline's drawing set |
| **Contract** | Optional upload of quality-related sections or prepared summary |
| **Without contract** | Simple accept/reject per requirement |
| **Output** | PDF following Stellar QM Module 2 structure, highlighting differences |
| **Project location** | `D:\Projects\{project}\Quality\` with `Customer-Docs\` subfolder |
| **Intake path** | Drop directly into project Quality folder (not unified Inbox) |
| **Doc identification** | Subfolder convention - files in `Customer-Docs\` are customer quality docs |
| **Phases** | Pre-Construction → Construction → Closeout → Warranty |
| **Revisions** | Re-run comparison, track history, flag contractual vs change-order |
| **Scope** | Every project (with skip option) |
| **UI** | CLI for now, data model supports future webapp |
| **Priority** | Quality over speed |

---

## Stellar QM Structure (Target Output Format)

The project-specific QM mirrors Module 2's structure:

| Section | Title | Subsections | Content Blocks |
|---------|-------|-------------|----------------|
| 2.1 | Document Control | A-E (5) | ~45 |
| 2.2 | Procurement | A-F (6) | ~60 |
| 2.3 | Execution | A-J (10) | ~120 |
| 2.4 | Inspections and Testing | A-J (10) | ~110 |
| 2.5 | Closeout | A-J (10) | ~100 |
| 2.6 | Continuous Improvement | A-D (4) | ~25 |

Each section follows a consistent pattern:
- A: Purpose and Scope
- B-N: Procedures/Requirements/General content
- Last: Verification and Compliance

Module 1 (Core Quality Standards) sections 1.1-1.7 are referenced but rarely
project-modified. The system must be **dynamic** - new modules/sections added to the
QM should automatically appear in the comparison scope.

---

## Milestones

### Milestone 0: Cover Sheet Code Extraction + project_codes Enhancement + Code Linkage
### Milestone 1: Database Schema + Customer Doc Intake + Requirement Extraction
### Milestone 2: 2-Step Comparison Engine + Traffic Light Review
### Milestone 3: Project-Specific QM PDF Generation + Revision Tracking
### Milestone 4: Contract Analysis + Change Order Detection

See detailed milestone plans below.

---

## Milestone 0: Cover Sheet Code Extraction + Infrastructure

**Goal:** Extract applicable codes/standards from each discipline's cover sheet and
general notes, enhance `project_codes` with discipline scoping, and link project codes
to the reference standards already extracted in `ref_clauses`.

**Why this is Milestone 0:** The comparison engine (Milestone 2) needs discipline-scoped
codes to perform Step 2 validation. Currently cover sheets are cataloged but unextracted,
and `project_codes` has only 13 manually-entered entries for one project. This milestone
also benefits the entire SIS system independently.

### 0.1 Enhance `project_codes` Table

```sql
-- Add discipline scoping and source traceability
ALTER TABLE project_codes ADD COLUMN discipline TEXT;
ALTER TABLE project_codes ADD COLUMN source_sheet_id INTEGER REFERENCES sheets(id);
ALTER TABLE project_codes ADD COLUMN code_edition TEXT;        -- e.g., "2013 Edition"
ALTER TABLE project_codes ADD COLUMN code_section TEXT;        -- specific section if cited
ALTER TABLE project_codes ADD COLUMN code_type TEXT DEFAULT 'design'
    CHECK(code_type IN (
        'design',          -- Design/construction code (ASME B31.5, IBC)
        'material',        -- Material standard (ASTM B280, ASTM D1785)
        'testing',         -- Testing/inspection standard (ASME Section IX)
        'safety',          -- Safety code (NFPA, OSHA)
        'reference',       -- Reference standard (ASHRAE, SMACNA)
        'local'            -- Local jurisdiction code (Indiana Building Code)
    ));
ALTER TABLE project_codes ADD COLUMN is_primary INTEGER DEFAULT 0;  -- 1=main governing code
ALTER TABLE project_codes ADD COLUMN extracted_at TEXT;
ALTER TABLE project_codes ADD COLUMN extraction_confidence REAL;

-- New: link project codes to extracted reference standards
CREATE TABLE project_code_ref_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_code_id INTEGER NOT NULL REFERENCES project_codes(id) ON DELETE CASCADE,
    ref_clause_id   INTEGER REFERENCES ref_clauses(id),
    ref_section_id  INTEGER REFERENCES ref_sections(id),
    standard_id     TEXT,                    -- reference_id from ref_clauses (e.g., "ASME-BPVC-2013")
    link_type       TEXT DEFAULT 'matched'
        CHECK(link_type IN ('matched','partial','unmatched')),
    match_confidence REAL,
    notes           TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_code_id, standard_id)
);

-- Drop the old unique constraint and add new one with discipline
-- (SQLite doesn't support DROP CONSTRAINT, so we handle this in migration)
-- New unique: (project_id, code_name, discipline) instead of (project_id, code_name)
```

### 0.2 Cover Sheet Extraction Enhancement

**Current state:** Cover sheets exist in `sheets` table but are marked "extracted"
without actually extracting any structured data. No lines, equipment, instruments,
or notes are captured.

**Sheets to process (per project):**

| Sheet Pattern | Discipline | Content Expected |
|---|---|---|
| G0001 (Cover Sheet) | General | Project info, applicable building codes |
| G0004/G0005 (Building Code Analysis) | General | Jurisdictional codes, occupancy, construction type |
| P0001 (Plumbing General Notes) | Plumbing | Plumbing codes, material standards, test requirements |
| M0001 (Mechanical General Notes) | Mechanical | Mechanical codes, ASHRAE standards |
| E0001 (Electrical General Notes) | Electrical | NEC, local electrical codes |
| R0001 (Refrigeration General Notes) | Refrigeration | ASME B31.5, ASHRAE 15, material standards |
| R00001 (Refrigeration Cover Sheet) | Refrigeration | Applicable codes list, project scope |
| RC00001 (Refrig Controls Cover) | Refrigeration-Controls | Controls codes, communication standards |
| S0001 (Structural General Notes) | Structural | AISC, ACI, IBC structural provisions |
| U0001 (Utilities General Notes) | Utility | Utility codes, connection standards |
| C100/C102 (Civil Cover/Notes) | Civil | Civil codes, grading standards |

**Extraction targets from cover sheets:**

1. **Applicable Codes & Standards** → `project_codes` table
   - Code name, year/edition, specific sections cited
   - Discipline assignment based on which cover sheet it came from
   - Primary vs reference distinction

2. **Design Criteria** → `design_criteria` table (already exists)
   - Temperatures, pressures, flow rates
   - Seismic category, wind speed, snow load
   - Occupancy classification

3. **General Notes** → `drawing_notes` table (already exists)
   - Abbreviated notes that contain requirements
   - Material specifications, inspection requirements
   - Testing requirements (pressure tests, leak tests)

### 0.3 Cover Sheet Extraction Flow

```
/cq extract-codes <project-number> [--discipline <disc>]
    │
    ▼
Find cover sheets & general notes sheets for project
    │  Query: SELECT * FROM sheets
    │         WHERE project_id = ? AND (
    │           drawing_type IN ('cover','cover_sheet','general','notes','legend')
    │           OR drawing_number LIKE '%0001%'
    │           OR title LIKE '%cover%' OR title LIKE '%general note%'
    │           OR title LIKE '%code%'
    │         )
    │
    ▼
For each cover sheet / general notes sheet:
    │
    ├── cover-sheet-extractor agent (Sonnet)
    │   ├── Read the PDF (file_path from sheets table)
    │   ├── Extract applicable codes & standards
    │   │   ├── Parse code citations (ASME B31.5-2019, AWS D1.1, etc.)
    │   │   ├── Identify code type (design, material, testing, safety, etc.)
    │   │   ├── Determine if primary governing code vs reference
    │   │   ├── Capture year/edition
    │   │   └── INSERT INTO project_codes (with discipline, source_sheet_id)
    │   │
    │   ├── Extract design criteria
    │   │   ├── Parse design parameters (temps, pressures, loads)
    │   │   └── INSERT INTO design_criteria
    │   │
    │   ├── Extract general notes
    │   │   ├── Parse numbered/bulleted notes
    │   │   ├── Identify notes that contain requirements
    │   │   └── INSERT INTO drawing_notes
    │   │
    │   └── Attempt code-to-reference linking
    │       ├── For each extracted code:
    │       │   ├── Search ref_clauses for matching standard
    │       │   │   (fuzzy match on standard_id, code_name)
    │       │   ├── If found → INSERT INTO project_code_ref_links
    │       │   │   (link_type = 'matched')
    │       │   ├── If partial match → link_type = 'partial'
    │       │   └── If not found → link_type = 'unmatched'
    │       │       (standard not yet extracted into ref_clauses)
    │       └── Report: X matched, Y partial, Z unmatched
    │
    └── Display summary per project

SUMMARY: 07645-Vital Cover Sheet Extraction
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sheets processed: 11
Codes extracted:  47
  By discipline:
    General:              12 (building codes, fire codes)
    Plumbing:              6 (plumbing code, material stds)
    Mechanical:            5 (mechanical code, ASHRAE)
    Electrical:            4 (NEC, local electrical)
    Refrigeration:         8 (ASME B31.5, ASHRAE 15, material)
    Refrigeration-Controls: 3 (controls standards)
    Structural:            5 (AISC, ACI, IBC)
    Utility:               2 (utility standards)
    Civil:                 2 (civil standards)

Code-to-Reference linking:
    Matched (in ref_clauses):   5 (ASME-BPVC, AWS-D18.1, etc.)
    Partial match:              3
    Unmatched (not extracted):  39 ← these need /sis-refs extract

Design criteria extracted: 15
General notes extracted: 82
```

### 0.4 Code-to-Reference Linkage Strategy

The `project_code_ref_links` table bridges `project_codes` → `ref_clauses`.

**Matching logic:**
1. **Exact match** - `project_codes.code_name` matches `ref_clauses.standard_id`
   - e.g., "ASME-BPVC-2013" in ref_clauses matches "ASME BPVC" in project_codes
2. **Fuzzy match** - Normalize code names and match
   - Strip punctuation, standardize org prefixes (ASME, AWS, ASTM, etc.)
   - Match by org + document number (ignore year for matching, capture year separately)
3. **Unmatched** - Code is in project but not yet extracted into ref_clauses
   - These become candidates for `/sis-refs extract` queue

**When the comparison engine (Milestone 2 Step 2) needs code text:**
```sql
-- Find applicable code clauses for a customer requirement's discipline
SELECT rc.clause_number, rc.content, rc.title
FROM project_codes pc
JOIN project_code_ref_links pcrl ON pcrl.project_code_id = pc.id
JOIN ref_clauses rc ON rc.id = pcrl.ref_clause_id
WHERE pc.project_id = ?
  AND pc.discipline = ?           -- Scoped to the requirement's discipline
  AND pcrl.link_type IN ('matched','partial')
  AND rc.content LIKE '%' || ? || '%'   -- keyword search
-- Plus FTS search:
UNION
SELECT rc.clause_number, rc.content, rc.title
FROM ref_clauses_fts fts
JOIN ref_clauses rc ON rc.rowid = fts.rowid
JOIN project_code_ref_links pcrl ON pcrl.ref_clause_id = rc.id
JOIN project_codes pc ON pc.id = pcrl.project_code_id
WHERE pc.project_id = ? AND pc.discipline = ?
  AND ref_clauses_fts MATCH ?
```

### 0.5 Handling Unmatched Codes

When a project code is NOT in `ref_clauses` (most will be initially):

```
After cover sheet extraction, display:

UNMATCHED CODES (not yet in reference database):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. ASME B31.5-2019      (Refrigeration - primary design code)
  2. ASHRAE 15-2019        (Refrigeration - safety code)
  3. Indiana Plumbing Code (Plumbing - local code)
  ...

These codes cannot be used for Step 2 validation until extracted.
Options:
  a) /sis-refs extract <standard>  - Extract a standard now
  b) Continue without Step 2 for these codes (all diffs → YELLOW)
  c) Skip for now, extract later
```

The system works WITHOUT all codes extracted - it just means more items land as YELLOW
(needs human review) instead of being auto-resolved by code validation. As you extract
more reference standards over time, re-running comparison auto-resolves more items.

### 0.6 Migration Plan for Existing project_codes Data

The 13 existing entries in `project_codes` (all for project 07645-Vital) need:
1. `discipline` populated based on code type:
   - "ASME B31.5" → Refrigeration
   - "ASME Section IX" → General (welding, applies across disciplines)
   - "Indiana Building Code" → General
   - "Indiana Plumbing Code" → Plumbing
   - etc.
2. `source_sheet_id` set to NULL (manually entered, no source sheet)
3. `code_type` classified
4. Attempt `project_code_ref_links` matching against existing ref_clauses

### 0.7 Config Addition

```yaml
# In config.yaml - new section
cover_sheet_extraction:
  # Model for cover sheet extraction
  model: sonnet

  # Sheet identification patterns (in addition to drawing_type)
  cover_sheet_patterns:
    - drawing_number: "G0001"       # General cover sheet
    - drawing_number: "*0001"       # Discipline cover sheets
    - title_contains: "cover sheet"
    - title_contains: "general note"
    - title_contains: "code analysis"
    - drawing_type:
        - "cover"
        - "cover_sheet"
        - "general"
        - "notes"

  # Code name normalization
  code_normalization:
    # Map common variations to canonical names
    "ASME BPVC": "ASME-BPVC"
    "ASME Boiler and Pressure Vessel Code": "ASME-BPVC"
    "National Electrical Code": "NFPA-70"
    "NEC": "NFPA-70"
    "International Building Code": "IBC"
    # Add more as encountered

  # Auto-link to ref_clauses
  auto_link:
    enabled: true
    min_confidence: 0.7
```

### 0.8 CLI Commands (Milestone 0)

```bash
# Extract codes from cover sheets
/cq extract-codes <project-number>            # All disciplines
/cq extract-codes <project-number> --discipline Refrigeration

# Show extracted codes for a project
/cq codes <project-number>                    # List all with discipline grouping
/cq codes <project-number> --unmatched        # Show codes not in ref_clauses

# Link codes to reference standards
/cq link-codes <project-number>               # Re-run auto-linking

# Show code coverage (how many project codes have ref_clauses data)
/cq code-coverage <project-number>
```

### 0.9 Agents (Milestone 0)

| Agent | Model | Purpose |
|-------|-------|---------|
| `cover-sheet-extractor` | Sonnet | Extract codes, design criteria, general notes from cover sheets |

### 0.10 Integration with Existing SIS Pipeline

This milestone also enhances the existing extraction pipeline:
- When `/sis-go` runs extraction on a cover sheet, it can now trigger code extraction
- When `/scan` indexes a new project, it can flag cover sheets for code extraction
- When `/sis-refs extract` completes a new standard, it can auto-link to project codes

---

## Milestone 1: Foundation

**Goal:** Intake customer quality documents, extract structured requirements, store them
in the database linked to a project and mapped to QM topics.

### 1.1 Database Schema Additions

#### New Tables

```sql
-- ─── Project Phase Tracking ───────────────────────────────────────────
-- Adds phase awareness to existing projects table
ALTER TABLE projects ADD COLUMN phase TEXT DEFAULT 'pre-construction'
    CHECK(phase IN ('pre-construction','construction','closeout','warranty','complete'));
ALTER TABLE projects ADD COLUMN phase_updated_at TEXT;
ALTER TABLE projects ADD COLUMN qm_status TEXT DEFAULT 'not-started'
    CHECK(qm_status IN ('not-started','in-progress','review','approved','revision'));

-- ─── Customer Quality Documents ───────────────────────────────────────
-- Registry of customer quality documents per project
CREATE TABLE cust_quality_docs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    file_name       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_hash       TEXT,                   -- SHA-256 for dedup/change detection
    file_type       TEXT,                   -- pdf, docx, xlsx, etc.
    doc_type        TEXT,                   -- QA_PLAN, ITP, SPEC, CONTRACT, SUBMITTAL, OTHER
    title           TEXT,                   -- Extracted or user-provided title
    source          TEXT,                   -- Customer name or "contract"
    revision        TEXT DEFAULT '0',
    revision_date   TEXT,
    page_count      INTEGER,
    extraction_status TEXT DEFAULT 'pending'
        CHECK(extraction_status IN ('pending','extracting','extracted','failed','re-extract')),
    extraction_model TEXT,                  -- Model used for extraction
    quality_score   REAL,                   -- Extraction confidence 0.0-1.0
    supersedes_id   INTEGER REFERENCES cust_quality_docs(id),
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, file_name, revision)
);

-- ─── Extracted Customer Requirements ──────────────────────────────────
-- Individual requirements extracted from customer docs
CREATE TABLE cust_requirements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id          INTEGER NOT NULL REFERENCES cust_quality_docs(id) ON DELETE CASCADE,
    project_id      INTEGER NOT NULL REFERENCES projects(id),

    -- Source location in customer document
    source_section  TEXT,                   -- Section/clause in customer doc (e.g., "8.4.1")
    source_text     TEXT NOT NULL,          -- Original verbatim text from customer doc
    source_page     INTEGER,                -- Page number in source PDF

    -- Classified/mapped fields
    requirement_text TEXT NOT NULL,          -- Normalized requirement statement
    topic           TEXT NOT NULL,           -- AI-classified topic (maps to QM sections)
    subtopic        TEXT,                    -- Finer classification
    category        TEXT DEFAULT 'general'   -- inspection, testing, nde, welding, procurement,
        CHECK(category IN (                  -- documentation, training, calibration, material,
            'general','inspection','testing','nde','welding','procurement',
            'documentation','training','calibration','material','safety',
            'environmental','commissioning','closeout','other'
        )),

    -- Discipline scoping (determines which cover sheet codes apply)
    discipline      TEXT,                    -- Which discipline this requirement applies to
                                             -- NULL = applies to all disciplines

    -- Strength/bindingness
    requirement_level TEXT DEFAULT 'shall'
        CHECK(requirement_level IN ('shall','should','may','information')),
    is_contractual  INTEGER DEFAULT NULL,   -- NULL=unknown, 1=yes, 0=no

    -- Code references found in the requirement
    code_references TEXT,                   -- JSON array of cited standards ["ASME B31.3", "AWS D1.1"]

    -- QM mapping (populated during comparison phase, but stored here)
    mapped_module   INTEGER,                -- QM module number (1 or 2)
    mapped_section  TEXT,                   -- QM section number (e.g., "2.4")
    mapped_subsection TEXT,                 -- QM subsection letter (e.g., "D")
    mapping_confidence REAL,                -- How confident the AI mapping is (0.0-1.0)

    -- Status
    status          TEXT DEFAULT 'extracted'
        CHECK(status IN ('extracted','mapped','reviewed','accepted','rejected','deferred')),

    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- FTS index for requirement search
CREATE VIRTUAL TABLE cust_requirements_fts USING fts5(
    requirement_text, source_text, topic, subtopic,
    content='cust_requirements',
    content_rowid='id'
);

-- ─── QM Topic Taxonomy ───────────────────────────────────────────────
-- Dynamic topic registry - maps customer requirement topics to QM sections
-- Auto-populated from QM structure, extensible for new topics
CREATE TABLE qm_topic_map (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic           TEXT NOT NULL UNIQUE,    -- Canonical topic name
    display_name    TEXT,                    -- Human-friendly name
    module_id       INTEGER REFERENCES qm_modules(id),
    section_id      INTEGER REFERENCES qm_sections(id),
    subsection_id   INTEGER REFERENCES qm_subsections(id),
    category        TEXT,                    -- Same categories as cust_requirements
    keywords        TEXT,                    -- JSON array of matching keywords
    is_auto         INTEGER DEFAULT 1,       -- 1=auto-generated from QM, 0=manually added
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### Why This Schema

- **`cust_quality_docs`** mirrors the pattern of `specifications` table - registry of
  source documents with extraction tracking
- **`cust_requirements`** is the core extraction output - each row is one requirement
  clause, with both the original customer text and a normalized version
- **`cust_requirements.discipline`** is NEW vs original plan - scopes which cover sheet
  codes apply during Step 2 validation
- **`qm_topic_map`** provides the bridge between customer terminology and Stellar's QM
  structure - auto-populated from `qm_sections`/`qm_subsections` but extensible
- **`requirement_level`** captures shall/should/may language which determines bindingness
- **`is_contractual`** is NULL by default (unknown) - populated when contract is loaded
- **`code_references`** stored as JSON array to capture multiple code citations per requirement

### 1.2 Folder Structure

```
D:\Projects\{project}\
├── Quality\
│   ├── Customer-Docs\          ← Drop customer quality docs here
│   │   ├── raw\                ← Original files preserved
│   │   └── processed\          ← After extraction
│   ├── Contract\               ← Quality-related contract sections (Milestone 4)
│   ├── Reviews\                ← Comparison review snapshots
│   └── Output\                 ← Generated project-specific QM PDFs
├── Mechanical\
├── Plumbing\
└── ...
```

### 1.3 Customer Doc Intake Flow

```
User drops files into D:\Projects\{project}\Quality\Customer-Docs\
    │
    ▼
cust-doc-intake agent (Haiku)
    ├── Detect file type (PDF, DOCX, XLSX)
    ├── Generate file hash (dedup check)
    ├── Read title/metadata
    ├── Register in cust_quality_docs table
    ├── Classify doc_type (QA_PLAN, ITP, SPEC, etc.)
    └── Queue for extraction
    │
    ▼
cust-req-extractor agent (Sonnet)
    ├── Convert to text (pdftotext, python-docx, etc.)
    ├── Extract individual requirements (clause-level)
    ├── For each requirement:
    │   ├── Capture source section/page reference
    │   ├── Normalize requirement text
    │   ├── Classify topic + subtopic (against qm_topic_map)
    │   ├── Assign discipline (based on context/topic)
    │   ├── Detect requirement_level (shall/should/may)
    │   ├── Extract code_references (ASME, AWS, etc.)
    │   └── Insert into cust_requirements
    ├── Update FTS index
    ├── Calculate quality_score
    └── Move file to processed\
```

### 1.4 Topic Classification Strategy

The AI classifier maps customer requirements to QM topics using:

1. **Keyword matching** against `qm_topic_map.keywords` (fast, first pass)
2. **Semantic similarity** against QM content blocks via VectorDB embeddings (second pass)
3. **LLM classification** for ambiguous cases (Sonnet, with QM section summaries in context)

The system is **dynamic**: when new QM modules/sections are added, the `qm_topic_map`
is regenerated automatically, and new keywords/embeddings are created.

### 1.5 Config Addition

```yaml
# In config.yaml - new section
customer_quality:
  # Subfolder convention for intake
  intake_subfolder: "Quality/Customer-Docs"

  # Supported file types
  file_types:
    - ".pdf"
    - ".docx"
    - ".doc"
    - ".xlsx"
    - ".xls"

  # Extraction settings
  extraction:
    model: sonnet                    # Quality over speed
    min_confidence: 0.7              # Below this, flag for review
    batch_size: 5                    # Docs per extraction batch

  # Topic classification
  classification:
    primary_method: "semantic"       # keyword, semantic, or llm
    fallback_method: "llm"           # When primary confidence is low
    min_confidence: 0.6              # Below this, flag as "unmapped"
```

### 1.6 CLI Commands

```bash
# Intake customer docs for a project
/cq intake <project-number>        # Process all files in Customer-Docs/

# Show extraction status
/cq status <project-number>        # Show doc count, extraction progress

# List extracted requirements
/cq requirements <project-number>  # List all requirements with topic mapping

# Re-extract a specific document
/cq re-extract <doc-id>            # Re-run extraction on a document
```

### 1.7 Agents (Milestone 1)

| Agent | Model | Purpose |
|-------|-------|---------|
| `cust-doc-intake` | Haiku | File detection, registration, classification |
| `cust-req-extractor` | Sonnet | Requirement extraction and topic classification |

---

## Milestone 2: 2-Step Comparison Engine + Traffic Light Review

**Goal:** Compare extracted customer requirements against Stellar QM (Step 1), validate
differences against discipline-scoped applicable codes (Step 2), auto-resolve where
possible, present traffic light dashboard for human review.

### 2.1 Database Schema Additions

```sql
-- ─── Comparison Sessions ──────────────────────────────────────────────
-- Each comparison run is a session (supports re-running after changes)
CREATE TABLE cq_comparison_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    session_type    TEXT DEFAULT 'full'
        CHECK(session_type IN ('full','incremental','revision')),
    status          TEXT DEFAULT 'running'
        CHECK(status IN ('running','completed','failed')),
    total_requirements INTEGER,
    auto_resolved   INTEGER DEFAULT 0,      -- Green count
    needs_review    INTEGER DEFAULT 0,       -- Yellow count
    conflicts       INTEGER DEFAULT 0,       -- Red count
    step1_resolved  INTEGER DEFAULT 0,       -- Resolved at Step 1 (QM match)
    step2_resolved  INTEGER DEFAULT 0,       -- Resolved at Step 2 (code check)
    step2_skipped   INTEGER DEFAULT 0,       -- Skipped Step 2 (code not in ref_clauses)
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at    TEXT
);

-- ─── Comparison Results ───────────────────────────────────────────────
-- One row per customer requirement, showing comparison outcome
CREATE TABLE cq_comparisons (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES cq_comparison_sessions(id) ON DELETE CASCADE,
    requirement_id  INTEGER NOT NULL REFERENCES cust_requirements(id),
    project_id      INTEGER NOT NULL REFERENCES projects(id),

    -- Step 1: QM comparison
    qm_subsection_id    INTEGER REFERENCES qm_subsections(id),
    qm_content_block_id INTEGER REFERENCES qm_content_blocks(id),
    qm_text         TEXT,                    -- Relevant QM content
    step1_result    TEXT
        CHECK(step1_result IN (
            'equivalent',                -- Customer matches QM → GREEN (done)
            'qm_exceeds',               -- QM already stricter → GREEN (done)
            'different',                 -- Different from QM → proceed to Step 2
            'new_topic',                 -- Not in QM at all → YELLOW
            'informational'              -- Customer doc is informational only → GREEN
        )),

    -- Step 2: Code validation (only populated when step1_result = 'different')
    ref_clause_id   INTEGER REFERENCES ref_clauses(id),
    code_text       TEXT,                    -- Relevant code standard clause
    code_standard   TEXT,                    -- Which standard (e.g., "ASME B31.5")
    step2_result    TEXT
        CHECK(step2_result IN (
            'code_requires',             -- Code backs customer → GREEN (auto-accept)
            'code_conflict',             -- Code contradicts customer → RED
            'code_silent',               -- Code doesn't address this → YELLOW
            'code_unavailable',          -- Standard not in ref_clauses → YELLOW
            NULL                         -- Step 2 not needed (resolved at Step 1)
        )),

    -- Final outcome
    traffic_light   TEXT NOT NULL DEFAULT 'yellow'
        CHECK(traffic_light IN ('green','yellow','red')),
    comparison_type TEXT
        CHECK(comparison_type IN (
            'equivalent',                -- Same requirement, different wording
            'qm_exceeds',               -- QM already exceeds customer
            'code_driven',              -- Customer req backed by code
            'more_stringent_customer',   -- Customer wants more than QM, code silent
            'conflict',                  -- Customer contradicts code
            'gap_customer',              -- Customer requires something QM doesn't address
            'new_topic',                 -- Entirely new topic not in QM
            'informational'              -- Customer doc is informational only
        )),

    -- Auto-resolution
    auto_resolved   INTEGER DEFAULT 0,       -- 1=auto-resolved by rules
    auto_rule       TEXT,                    -- Which rule resolved it
    resolution_text TEXT,                    -- Explanation of auto-resolution

    -- Human review
    disposition     TEXT DEFAULT 'pending'
        CHECK(disposition IN (
            'pending','accepted','rejected','modified','deferred'
        )),
    disposition_text TEXT,                   -- What was decided
    disposition_by  TEXT,                    -- Who reviewed
    disposition_date TEXT,

    -- For the project-specific QM
    include_in_qm   INTEGER DEFAULT NULL,    -- NULL=undecided, 1=include, 0=exclude
    qm_override_text TEXT,                   -- Custom text if modified

    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ─── Auto-Resolution Rules ───────────────────────────────────────────
-- Configurable rules for automatic traffic light assignment
CREATE TABLE cq_auto_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name       TEXT NOT NULL UNIQUE,
    description     TEXT,
    priority        INTEGER DEFAULT 100,     -- Lower = higher priority
    condition_type  TEXT NOT NULL
        CHECK(condition_type IN (
            'qm_equivalent',             -- QM matches customer → green
            'qm_exceeds',               -- QM already stricter → green
            'code_requires',             -- Code backs customer → green (auto-accept)
            'informational_only',        -- Customer doc is informational → green
            'code_conflict',             -- Code contradicts → red
            'new_topic',                 -- New topic, no QM match → yellow
            'code_unavailable',          -- Can't check code → yellow
            'custom'                     -- Custom SQL/logic condition
        )),
    auto_disposition TEXT,                   -- What disposition to set
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Pre-populate default rules
INSERT INTO cq_auto_rules (rule_name, description, priority, condition_type, auto_disposition) VALUES
    ('qm_equivalent', 'Customer requirement matches QM - no action needed', 10, 'qm_equivalent', 'accepted'),
    ('qm_exceeds', 'QM already exceeds customer requirement', 20, 'qm_exceeds', 'accepted'),
    ('code_requires', 'Applicable code requires this - auto-accept', 30, 'code_requires', 'accepted'),
    ('informational', 'Customer doc is informational only', 40, 'informational_only', 'accepted'),
    ('code_conflict', 'Customer requirement conflicts with code', 50, 'code_conflict', NULL);
```

### 2.2 Comparison Engine Flow (2-Step)

```
/cq compare <project-number>
    │
    ▼
cq-comparator agent (Sonnet)
    │
    ├── 1. Load all cust_requirements for project (status='mapped')
    ├── 2. Load project_codes for this project (with discipline scoping)
    ├── 3. For each requirement:
    │   │
    │   │  ════ STEP 1: Customer vs QM ════
    │   │
    │   ├── a. Find matching QM content
    │   │      Query qm_content_blocks via mapped_section/subsection
    │   │      + semantic search via VectorDB for fuzzy matches
    │   │
    │   ├── b. Compare customer requirement against QM text
    │   │      ├── Equivalent → step1_result='equivalent' → GREEN (done)
    │   │      ├── QM exceeds → step1_result='qm_exceeds' → GREEN (done)
    │   │      ├── Informational → step1_result='informational' → GREEN (done)
    │   │      ├── New topic → step1_result='new_topic' → YELLOW (done)
    │   │      └── Different → step1_result='different' → proceed to Step 2
    │   │
    │   │  ════ STEP 2: Code Validation (only if different) ════
    │   │
    │   ├── c. Find applicable codes for this requirement's discipline
    │   │      Query project_codes WHERE discipline = requirement.discipline
    │   │      Look up linked ref_clauses via project_code_ref_links
    │   │
    │   ├── d. If no linked ref_clauses found:
    │   │      → step2_result='code_unavailable' → YELLOW
    │   │
    │   ├── e. If ref_clauses found, compare:
    │   │      ├── Code backs customer → step2_result='code_requires' → GREEN
    │   │      ├── Code contradicts → step2_result='code_conflict' → RED
    │   │      └── Code silent → step2_result='code_silent' → YELLOW
    │   │
    │   └── f. Insert into cq_comparisons
    │
    ├── 4. Apply auto-resolution rules to all GREEN items
    ├── 5. Update session statistics
    └── 6. Display summary with step breakdown

COMPARISON COMPLETE: 07645-Vital
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total requirements: 60

Step 1 (Customer vs QM):
  Equivalent/QM exceeds:  38 → GREEN (63%)
  Different from QM:      18 → proceeded to Step 2
  New topics:              3 → YELLOW
  Informational:           1 → GREEN

Step 2 (Code Validation - 18 items):
  Code requires it:        5 → GREEN (auto-accepted)
  Code conflict:           2 → RED
  Code silent:             6 → YELLOW
  Code unavailable:        5 → YELLOW (standards not yet extracted)

FINAL: 🟢 44 Green  🟡 14 Yellow  🔴 2 Red
```

### 2.3 Traffic Light Dashboard (CLI)

```
╔══════════════════════════════════════════════════════════════════╗
║  PROJECT QM REVIEW: 07645 - Vital                               ║
║  Session: #3 (2026-02-05)  Phase: Pre-Construction              ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  SUMMARY        🟢 Green: 44   🟡 Yellow: 14   🔴 Red: 2        ║
║  Progress       ████████████████████░░░░ 73% resolved            ║
║                                                                  ║
║  STEP 1 resolved: 39/60    STEP 2 resolved: 5/18                ║
║  Step 2 skipped (no ref data): 5                                ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  BY QM SECTION:                                                  ║
║  2.1 Document Control      🟢 8   🟡 2   🔴 0   [100% reviewed] ║
║  2.2 Procurement           🟢 5   🟡 3   🔴 0   [ 67% reviewed] ║
║  2.3 Execution             🟢 13  🟡 3   🔴 1   [ 65% reviewed] ║
║  2.4 Inspections/Testing   🟢 11  🟡 4   🔴 1   [ 53% reviewed] ║
║  2.5 Closeout              🟢 4   🟡 1   🔴 0   [ 80% reviewed] ║
║  2.6 Continuous Improvement 🟢 3   🟡 1   🔴 0   [ 75% reviewed] ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  COMMANDS:                                                       ║
║  /cq review <project> [section]  - Review yellow/red items       ║
║  /cq accept <id>                 - Accept a requirement          ║
║  /cq reject <id>                 - Reject a requirement          ║
║  /cq modify <id>                 - Accept with modifications     ║
║  /cq defer <id>                  - Defer decision                ║
║  /cq dashboard <project>         - Refresh this view             ║
╚══════════════════════════════════════════════════════════════════╝
```

### 2.4 Review Workflow

When reviewing a yellow/red item, the CLI presents:

```
─── REQUIREMENT #47 ─── 🟡 YELLOW ── Section 2.4 Inspections ──────
SOURCE: Customer QA Plan v2, Section 8.4.1, Page 12
DISCIPLINE: Refrigeration
STEP 1: Different from QM
STEP 2: Code silent (ASME B31.5 doesn't specify % for this joint type)

CUSTOMER SAYS:
  "All butt welds on refrigerant piping shall receive 100% radiographic
   testing per ASME B31.5 Section 8.4."

STELLAR QM SAYS (Section 2.4-D):
  "NDE requirements per applicable code. RT sampling per project
   specification or code minimum."

APPLICABLE CODE (ASME B31.5 §8.4):
  "Radiographic examination per Table 8.4.1. Category D joints:
   random examination per owner requirements."

ANALYSIS:
  Customer requires 100% RT on all butt welds. Code allows random
  examination at owner discretion. Customer requirement is MORE
  STRINGENT than code minimum but not contradictory (owner may
  require more). Stellar QM defers to code/spec.

ACTION: [A]ccept  [R]eject  [M]odify  [D]efer  [S]kip  ?
```

### 2.5 Agents (Milestone 2)

| Agent | Model | Purpose |
|-------|-------|---------|
| `cq-comparator` | Sonnet | 2-step comparison, traffic light assignment |

Note: `cq-auto-resolver` agent removed - auto-resolution is now handled by SQL rules
within the comparator agent (simpler, fewer moving parts).

---

## Milestone 3: Project-Specific QM PDF Generation + Revision Tracking

**Goal:** Generate a PDF document following Stellar QM structure that highlights
project-specific deviations, and track revisions over time.

### 3.1 Database Schema Additions

```sql
-- ─── Project QM Versions ──────────────────────────────────────────────
-- Each generated QM is a versioned snapshot
CREATE TABLE project_qm_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    version         TEXT NOT NULL,            -- "A", "B", "C" or "1", "2", "3"
    phase           TEXT,                     -- Project phase when generated
    session_id      INTEGER REFERENCES cq_comparison_sessions(id),
    status          TEXT DEFAULT 'draft'
        CHECK(status IN ('draft','review','approved','superseded')),

    -- Statistics at time of generation
    total_deviations    INTEGER,
    accepted_additions  INTEGER,              -- Customer requirements added
    accepted_modifications INTEGER,           -- QM sections modified
    rejected_items      INTEGER,
    deferred_items      INTEGER,

    -- Applicable codes snapshot
    applicable_codes TEXT,                    -- JSON snapshot of project_codes at generation time

    -- Output file
    file_path       TEXT,                     -- Path to generated PDF
    file_hash       TEXT,

    generated_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    approved_by     TEXT,
    approved_at     TEXT,

    UNIQUE(project_id, version)
);

-- ─── Project QM Sections ──────────────────────────────────────────────
-- Per-section content for the project QM (deviations from standard)
CREATE TABLE project_qm_sections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id      INTEGER NOT NULL REFERENCES project_qm_versions(id) ON DELETE CASCADE,

    -- Maps to QM structure
    module_number   INTEGER,
    section_number  TEXT,
    subsection_letter TEXT,

    -- Content
    has_deviation   INTEGER DEFAULT 0,        -- 1 if this section differs from standard
    deviation_type  TEXT
        CHECK(deviation_type IN (
            'addition',                       -- New requirement not in standard QM
            'modification',                   -- Standard QM text modified
            'stricter',                       -- More stringent than standard
            'exception',                      -- Exception to standard requirement
            NULL                              -- No deviation
        )),
    standard_text   TEXT,                     -- Original QM text
    project_text    TEXT,                     -- Project-specific text (if modified)
    deviation_summary TEXT,                   -- Brief description of what changed
    source_requirement_id INTEGER REFERENCES cust_requirements(id),
    source_comparison_id  INTEGER REFERENCES cq_comparisons(id),

    display_order   INTEGER,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ─── Revision History ─────────────────────────────────────────────────
-- Track what changed between QM versions
CREATE TABLE project_qm_changelog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    from_version_id INTEGER REFERENCES project_qm_versions(id),
    to_version_id   INTEGER NOT NULL REFERENCES project_qm_versions(id),

    section_number  TEXT,
    change_type     TEXT
        CHECK(change_type IN ('added','modified','removed','reverted')),
    change_summary  TEXT,
    trigger         TEXT,                     -- What caused the change
        -- 'customer_doc_revision', 'code_update', 'manual_edit',
        -- 'phase_change', 'change_order'
    is_contractual  INTEGER,                  -- Does this change affect contract scope?
    needs_change_order INTEGER DEFAULT 0,     -- Flag: requires change order

    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 PDF Generation Strategy

The PDF follows Stellar QM Module 2 structure with deviation highlighting:

```
┌─────────────────────────────────────────────────────┐
│  STELLAR QUALITY SYSTEMS                            │
│  PROJECT-SPECIFIC QUALITY MANUAL                    │
│                                                     │
│  Project: 07645 - Vital Farms                       │
│  Client:  Vital Farms, Inc.                         │
│  Phase:   Pre-Construction                          │
│  Version: A                                         │
│  Date:    2026-02-05                                │
│  Status:  DRAFT                                     │
│                                                     │
│  APPLICABLE CODES:                                  │
│  Refrigeration: ASME B31.5-2019, ASHRAE 15-2019    │
│  Plumbing: Indiana Plumbing Code 2012              │
│  General: 2014 Indiana Building Code, IBC 2012     │
│  Electrical: NEC 2008                              │
├─────────────────────────────────────────────────────┤
│                                                     │
│  This document identifies project-specific quality  │
│  requirements that differ from, supplement, or      │
│  modify the Stellar Quality Manual (Modules 1 & 2). │
│  All standard QM requirements apply unless          │
│  specifically noted in this document.               │
│                                                     │
│  DEVIATION LEGEND:                                  │
│  [+] ADDITION  - New requirement for this project   │
│  [M] MODIFIED  - Standard requirement modified      │
│  [S] STRICTER  - More stringent than standard       │
│  [E] EXCEPTION - Exception to standard requirement  │
│  [C] CODE-DRIVEN - Required by applicable code      │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  2.4 INSPECTIONS AND TESTING                        │
│  ─────────────────────────────────────              │
│                                                     │
│  2.4-D NDE Requirements                             │
│                                                     │
│  STANDARD QM:                                       │
│  "NDE requirements per applicable code. RT sampling │
│   per project specification or code minimum."       │
│                                                     │
│  [S] PROJECT-SPECIFIC (MORE STRINGENT):             │
│  "All butt welds on refrigerant piping shall        │
│   receive 100% radiographic testing per ASME B31.5  │
│   Section 8.4."                                     │
│                                                     │
│  Source: Customer QA Plan v2, Section 8.4.1         │
│  Disposition: Accepted (2026-02-03, B. Johnson)     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 3.3 PDF Generation Approach

Use **Python + ReportLab** or **WeasyPrint** (HTML→PDF) for generation:

1. Query `project_qm_sections` for the version
2. For sections WITH deviations: render deviation block with highlighting
3. For sections WITHOUT deviations: note "Standard QM requirements apply"
4. Include cover page with applicable codes, TOC, revision history, approval block
5. Save to `D:\Projects\{project}\Quality\Output\{project}-QM-Rev{version}.pdf`

### 3.4 CLI Commands (Milestone 3)

```bash
# Generate project QM PDF
/cq generate <project-number>            # Generate new version

# List versions
/cq versions <project-number>            # Show all versions

# Show changes between versions
/cq changelog <project-number> [version] # Show what changed

# Approve a version
/cq approve <project-number> <version>   # Mark version as approved
```

### 3.5 Agents (Milestone 3)

| Agent | Model | Purpose |
|-------|-------|---------|
| `cq-qm-generator` | Sonnet | Assemble project QM content, generate PDF |
| `cq-revision-differ` | Sonnet | Compare QM versions, generate changelog |

---

## Milestone 4: Contract Analysis + Change Order Detection

**Goal:** Load contract quality requirements, determine which customer requirements are
contractual, and detect when mid-project changes require change orders.

### 4.1 Database Schema Additions

```sql
-- ─── Contract Documents ───────────────────────────────────────────────
CREATE TABLE cq_contracts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    file_name       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_hash       TEXT,
    title           TEXT,
    contract_type   TEXT,                     -- 'quality_section', 'exhibit', 'summary'
    revision        TEXT DEFAULT '0',
    extraction_status TEXT DEFAULT 'pending'
        CHECK(extraction_status IN ('pending','extracting','extracted','failed')),
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, file_name, revision)
);

-- ─── Contract Requirements ────────────────────────────────────────────
-- Requirements extracted specifically from contract documents
CREATE TABLE cq_contract_requirements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id     INTEGER NOT NULL REFERENCES cq_contracts(id) ON DELETE CASCADE,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    requirement_text TEXT NOT NULL,
    source_section  TEXT,
    source_page     INTEGER,
    topic           TEXT,
    is_mandatory    INTEGER DEFAULT 1,        -- 1=shall, 0=should/may
    linked_cust_req_id INTEGER REFERENCES cust_requirements(id),
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ─── Change Order Tracking ────────────────────────────────────────────
CREATE TABLE cq_change_orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    changelog_id    INTEGER REFERENCES project_qm_changelog(id),

    change_description TEXT NOT NULL,
    reason          TEXT,                      -- Why the change is needed
    contractual_basis TEXT,                    -- Which contract clause is affected

    status          TEXT DEFAULT 'identified'
        CHECK(status IN ('identified','submitted','approved','rejected','void')),

    cost_impact     TEXT,                      -- 'none', 'increase', 'decrease', 'tbd'
    schedule_impact TEXT,                      -- 'none', 'delay', 'acceleration', 'tbd'

    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 Contract Analysis Flow

```
User drops contract quality sections into D:\Projects\{project}\Quality\Contract\
    │
    ▼
/cq load-contract <project-number>
    │
    ├── Extract requirements from contract docs
    ├── Match against existing cust_requirements
    │   ├── Matched → set is_contractual = 1
    │   └── Unmatched → flag as contract-only requirement
    ├── Re-run comparison for newly-flagged contractual items
    └── Update dashboard
```

### 4.3 Change Order Detection

When customer docs are revised mid-project:

```
/cq revision-check <project-number>
    │
    ├── Detect new/changed files in Customer-Docs/
    ├── Extract requirements from new revision
    ├── Diff against previous extraction
    │   ├── New requirements → flag as additions
    │   ├── Changed requirements → flag as modifications
    │   └── Removed requirements → flag as deletions
    ├── For each change:
    │   ├── Is requirement contractual? (check cq_contract_requirements)
    │   │   ├── Yes, and change ADDS scope → needs change order
    │   │   ├── Yes, and change REDUCES scope → may need change order
    │   │   └── No → informational change, update QM
    │   └── Insert into project_qm_changelog with trigger='customer_doc_revision'
    ├── Auto-create change order records where needed
    └── Display summary of changes requiring action
```

### 4.4 CLI Commands (Milestone 4)

```bash
# Load contract quality sections
/cq load-contract <project-number>

# Check for revisions / changes
/cq revision-check <project-number>

# List pending change orders
/cq change-orders <project-number>

# Update change order status
/cq change-order <id> --status approved
```

### 4.5 Agents (Milestone 4)

| Agent | Model | Purpose |
|-------|-------|---------|
| `cq-contract-analyzer` | Sonnet | Extract contract requirements, match to customer reqs |
| `cq-change-detector` | Sonnet | Diff revisions, identify contractual changes |

---

## Cross-Cutting Concerns

### Model Routing

| Task | Model | Rationale |
|------|-------|-----------|
| File detection, classification | Haiku | Simple pattern matching |
| Cover sheet code extraction | Sonnet | Structured extraction from drawings |
| Requirement extraction | Sonnet | Quality extraction, nuanced text |
| Topic classification | Sonnet | Semantic understanding needed |
| Step 1: Customer vs QM comparison | Sonnet | Primary quality comparison |
| Step 2: Code validation | Sonnet | Needs accuracy for code interpretation |
| PDF content assembly | Sonnet | Needs good writing |
| Conflict resolution suggestions | Opus | Critical decisions, high quality |
| Contract analysis | Sonnet | Legal-ish text, accuracy matters |

### Dynamic QM Adaptation

When new QM modules/sections are added:
1. Trigger `qm_topic_map` regeneration
2. Re-embed new content blocks to VectorDB
3. Existing project QMs are NOT auto-updated (would require new comparison session)
4. New projects automatically pick up the expanded QM structure

### Integration with Existing Systems

- **VectorDB** (`D:\VectorDB`) - Used for semantic search during topic classification
  and QM content matching
- **ref_clauses** / **ref_content_blocks** - Used for Step 2 code validation
- **project_codes** (enhanced) - Discipline-scoped applicable codes from cover sheets
- **project_code_ref_links** (new) - Bridges project codes to extracted ref_clauses
- **specifications** table - Cross-reference customer quality specs with project specs
- **qm_content_fts** / **ref_clauses_fts** - Full-text search for keyword matching
- **sheets** table - Source for cover sheet identification and code extraction
- **Existing intake** - Does NOT use unified Inbox; uses project-level folder convention
- **Existing /sis-refs** - Used to extract standards that are referenced but not yet
  in ref_clauses (feeds code coverage)

### Data Flow Diagram

```
                                ┌──────────────┐
          ┌─────────────────────│  Cover Sheet  │
          │                     │  Extraction   │
          │                     │  (Milestone 0)│
          │                     └──────┬───────┘
          │                            │
          │              project_codes + project_code_ref_links
          │                            │
          │                            ▼
          │                     ┌──────────────┐
          │                     │  ref_clauses  │
          │                     │  (existing +  │
          │                     │   /sis-refs)  │
          │                     └──────┬───────┘
          │                            │
          │     ┌──────────────┐       │
          │     │  Customer    │       │
          │     │  Quality     │       │
          │     │  Documents   │       │
          │     └──────┬───────┘       │
          │            │ Drop in Quality/Customer-Docs/
          │            ▼               │
          │     ┌──────────────┐       │
          │     │  Intake &    │  cust_quality_docs
          │     │  Register    │       │
          │     └──────┬───────┘       │
          │            │               │
          │            ▼               │
          │     ┌──────────────┐       │
          │     │  Extract     │  cust_requirements
          │     │  Requirements│  cust_requirements_fts
          │     └──────┬───────┘       │
          │            │               │
          │   ═════════╪═══════════════╪════════════
          │   STEP 1   │               │
          │            ▼               │
          │     ┌──────────────┐       │
          ├────►│  Customer    │       │
          │     │  vs QM       │  qm_content_blocks
          │     │  Comparison  │  qm_content_fts
          │     └──────┬───────┘
          │            │
          │     ┌──────┴──────┐
          │     │             │
          │  Equivalent    Different
          │  → GREEN       → Step 2
          │                   │
          │   ═══════════════╪════════════
          │   STEP 2         │
          │                  ▼
          │           ┌──────────────┐
          └──────────►│  Code        │  project_codes
                      │  Validation  │  project_code_ref_links
                      │  (discipline │  ref_clauses
                      │   scoped)    │
                      └──────┬───────┘
                             │
                      ┌──────┴──────┐
                      │             │
                   Code backs    Code silent/
                   customer      conflict
                   → GREEN       → YELLOW/RED
                             │
                             ▼
                      ┌──────────────┐
                      │  Traffic     │  disposition workflow
                      │  Light       │  accept/reject/modify
                      │  Review      │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │  Generate    │  project_qm_versions
                      │  Project QM  │  project_qm_sections
                      │  PDF         │  project_qm_changelog
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                  D:\Projects\{proj}\Quality\Output\
                  {project}-QM-Rev{version}.pdf
```

---

## New Tables Summary

| Milestone | Table | Purpose |
|-----------|-------|---------|
| 0 | `project_code_ref_links` | Links project codes to extracted ref_clauses |
| 1 | `cust_quality_docs` | Customer document registry |
| 1 | `cust_requirements` | Extracted requirements |
| 1 | `cust_requirements_fts` | Full-text search index |
| 1 | `qm_topic_map` | Topic → QM section mapping |
| 2 | `cq_comparison_sessions` | Comparison run tracking |
| 2 | `cq_comparisons` | Per-requirement comparison results |
| 2 | `cq_auto_rules` | Auto-resolution rule config |
| 3 | `project_qm_versions` | Generated QM version registry |
| 3 | `project_qm_sections` | Per-section QM content |
| 3 | `project_qm_changelog` | Version-to-version changes |
| 4 | `cq_contracts` | Contract document registry |
| 4 | `cq_contract_requirements` | Contract requirement extraction |
| 4 | `cq_change_orders` | Change order tracking |

**Total: 14 new tables** (+ FTS virtual table) added to existing 150+ table database.

---

## Altered Existing Tables

| Table | Change | Purpose |
|-------|--------|---------|
| `projects` | Add `phase`, `phase_updated_at`, `qm_status` columns | Project phase tracking |
| `project_codes` | Add `discipline`, `source_sheet_id`, `code_edition`, `code_section`, `code_type`, `is_primary`, `extracted_at`, `extraction_confidence` columns | Discipline scoping + code classification |

---

## New Agents Summary

| Agent | Model | Milestone | Purpose |
|-------|-------|-----------|---------|
| `cover-sheet-extractor` | Sonnet | 0 | Extract codes, criteria, notes from cover sheets |
| `cust-doc-intake` | Haiku | 1 | File detection, registration |
| `cust-req-extractor` | Sonnet | 1 | Requirement extraction + topic classification |
| `cq-comparator` | Sonnet | 2 | 2-step comparison, traffic light assignment |
| `cq-qm-generator` | Sonnet | 3 | PDF generation |
| `cq-revision-differ` | Sonnet | 3 | Version comparison |
| `cq-contract-analyzer` | Sonnet | 4 | Contract extraction |
| `cq-change-detector` | Sonnet | 4 | Change order detection |

**Total: 8 new agents**

---

## CLI Command Summary

All commands use the `/cq` prefix (Customer Quality):

| Command | Milestone | Purpose |
|---------|-----------|---------|
| `/cq extract-codes <project>` | 0 | Extract codes from cover sheets |
| `/cq codes <project>` | 0 | List project codes by discipline |
| `/cq link-codes <project>` | 0 | Re-run code-to-ref_clauses linking |
| `/cq code-coverage <project>` | 0 | Show ref_clauses coverage for project codes |
| `/cq intake <project>` | 1 | Process customer docs |
| `/cq status <project>` | 1 | Show extraction status |
| `/cq requirements <project>` | 1 | List extracted requirements |
| `/cq re-extract <doc-id>` | 1 | Re-extract a document |
| `/cq compare <project>` | 2 | Run 2-step comparison |
| `/cq dashboard <project>` | 2 | Traffic light overview |
| `/cq review <project> [section]` | 2 | Review yellow/red items |
| `/cq accept/reject/modify/defer <id>` | 2 | Disposition actions |
| `/cq generate <project>` | 3 | Generate QM PDF |
| `/cq versions <project>` | 3 | List QM versions |
| `/cq changelog <project>` | 3 | Show version changes |
| `/cq approve <project> <version>` | 3 | Approve a QM version |
| `/cq load-contract <project>` | 4 | Load contract docs |
| `/cq revision-check <project>` | 4 | Check for doc changes |
| `/cq change-orders <project>` | 4 | List pending change orders |

---

## Implementation Dependencies

```
Milestone 0 ──► Milestone 1 ──► Milestone 2 ──► Milestone 3
                                     │                │
                                     └────────────────┴──► Milestone 4

Milestone 0 can also run independently (benefits existing SIS pipeline)
Milestone 1 can start in parallel with Milestone 0 (schema + intake don't need codes)
Milestone 2 REQUIRES both Milestone 0 (codes) and Milestone 1 (requirements)
Milestone 3 REQUIRES Milestone 2 (comparison results)
Milestone 4 REQUIRES Milestone 3 (QM versions for change tracking)
```

### External Dependencies

- `/sis-refs extract` - To populate ref_clauses for project codes (existing command)
- VectorDB embeddings - For semantic search (existing infrastructure)
- pdftotext / python-docx - For document text extraction (may need pip install)
- ReportLab or WeasyPrint - For PDF generation (needs pip install)
