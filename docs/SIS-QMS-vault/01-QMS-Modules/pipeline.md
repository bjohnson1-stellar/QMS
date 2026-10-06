---
module: pipeline
cli_name: pipeline
status: Complete
commands: [status, queue, import-drawing, import-batch, process]
depends_on: [core, projects, workforce, welding]
depended_by: [engineering, vectordb]
tables: [sheets, disciplines, discipline_defaults, lines, equipment, instruments, welds, conflicts, equipment_master, equipment_appearances, specifications, spec_sections, spec_items, master_spec_items, spec_variations, spec_intake_log, extraction_flags, model_runs, processing_queue, intake_log]
shared_tables: [business_units]
api_blueprint: "-"
source_dir: pipeline/
schema_file: pipeline/schema.sql
tags: [qms-module, extraction, sis, drawings]
created: 2026-02-10
updated: 2026-02-10
---

# Pipeline

The **SIS drawing extraction pipeline** — imports construction drawings (Excel workbooks from SIS field locations), extracts structured data (lines, equipment, instruments, welds), and stores it across **152+ discipline-specific tables**. The largest module by table count.

## Architecture

- Import → Queue → Process pipeline with status tracking
- Multi-discipline extraction: Plumbing, Mechanical, Refrigeration, Electrical, Civil, Fire Protection, etc.
- AI model routing with shadow reviews and accuracy tracking
- Revision management with delta tracking between versions
- Specification extraction and cross-project consistency analysis

### SIS Extraction Priority
> Plumbing > Mechanical > Refrigeration > Refrigeration-Controls > Electrical > Utility
> Then: Architectural, Civil, Fire-Protection, General, Structural

## CLI Commands

| Command | Description |
|---------|-------------|
| `qms pipeline status [project]` | Show extraction pipeline status |
| `qms pipeline queue [--status] [--limit]` | List and manage extraction queue |
| `qms pipeline import-drawing <file>` | Import single SIS drawing/field location file |
| `qms pipeline import-batch [--directory \| files...]` | Batch import SIS files |
| `qms pipeline process [project] [--limit]` | Run extraction processing on queued items |

## Database Tables (152+ total)

### Core Extraction (13 tables)
| Table | Purpose |
|-------|---------|
| `sheets` | Drawing master records (project, discipline, revision, extraction metadata) |
| `disciplines` | Project disciplines with processing counts |
| `lines` | Pipe/line records (line_number, size, material, spec_class) |
| `equipment` | Equipment tags extracted from drawings |
| `instruments` | Instrument tags (ISA standard) |
| `welds` | Weld records from drawings |
| `conflicts` | Extraction conflicts (cross-discipline, revision) |
| `equipment_master` | Consolidated equipment list per project |
| `processing_queue` | Extraction task queue |

### Specifications (7 tables)
| Table | Purpose |
|-------|---------|
| `specifications` | Specification master per project |
| `spec_items` | Individual spec items (pipes, fittings, valves) |
| `master_spec_items` | Cross-project master spec list |
| `spec_variations` | Deviations from master specs |

### Discipline-Specific Tables
| Discipline | Table Count | Key Tables |
|-----------|------------|------------|
| Electrical | 19 | transformers, switchgear, motors, panels, circuits, breakers, conduit |
| Civil & Survey | 26 | demolition, grading, drainage, contours, utilities, boundaries |
| Fire Protection | 13 | zones, systems, piping, valves, egress, occupancy |
| Plumbing | 5 | fixtures, risers, locations, pipes, cleanouts |
| Mechanical/HVAC | 3 | equipment, ventilation, air_flow_paths |
| Refrigeration | 2 | pipe_stands, duct_stands |
| Supports | 3 | support_details, supports, support_tags |
| Utility | 1 | utility_equipment |
| Environmental | 2 | zones, notes |

### QA & Accuracy (11 tables)
| Table | Purpose |
|-------|---------|
| `extraction_flags` | QA flags on extractions |
| `model_runs` | AI model run audit log |
| `shadow_reviews` | Opus shadow review results |
| `gold_standard` | Gold standard test set |
| `accuracy_log` | Model accuracy tracking over time |

## Key Functions

| Function | Location | Description |
|----------|----------|-------------|
| `import_single()` | `pipeline/importer.py` | Import single SIS file |
| `import_batch()` | `pipeline/importer.py` | Batch import from file list |
| `add_to_queue()` | `pipeline/importer.py` | Add item to processing queue |
| `process_and_import()` | `pipeline/processor.py` | Process and import SIS file |
| `parse_sis_sheet()` | `pipeline/processor.py` | Parse SIS Excel workbook |
| `get_pipeline_status()` | `pipeline/processor.py` | Pipeline status for project |

## Dependencies

### Depends On
- [[core]] — Database, logging, config
- [[projects]] — Project lookups, create projects, shared `business_units`
- [[workforce]] — Employee import, create employees
- [[welding]] — Continuity tracking for welders found in drawings

### Depended By
- [[engineering]] — Uses extracted data for validation
- [[vectordb]] — Indexes drawings and specifications for semantic search

## Related Notes
- [[engineering]] — Validates extraction against calculations
- [[Database Overview]] — All 152 pipeline tables
- [[Architecture Overview]] — Extraction flow diagram
