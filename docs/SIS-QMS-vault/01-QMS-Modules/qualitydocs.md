---
module: qualitydocs
cli_name: docs
status: Complete
commands: [load-module, summary, search, detail]
depends_on: [core]
depended_by: [references, vectordb]
tables: [qm_modules, qm_sections, qm_subsections, qm_content_blocks, qm_cross_references, qm_code_references, qm_responsibility_assignments, qm_content_fts, qm_procedures, qm_forms, qm_records, qm_templates, qm_document_history, qm_intake_log]
api_blueprint: "-"
source_dir: qualitydocs/
schema_file: qualitydocs/schema.sql
tags: [qms-module, quality-manual]
created: 2026-02-10
updated: 2026-02-10
---

# Quality Documents

Manages the **Quality Manual** — the top-level document in any ISO 9001 / ASME quality program. Stores structured content from XML-parsed quality manual modules, with full-text search, cross-referencing, and procedure/form/record tracking.

## Architecture

- Quality Manual is structured: **Modules → Sections → Subsections → Content Blocks**
- Content loaded from XML files via `load_module_from_file()`
- FTS5 virtual table (`qm_content_fts`) enables full-text search with Porter stemming
- Cross-references detected automatically between modules and to external codes/standards
- Procedures (SOP, WI, Policy) tracked separately with revision control

## CLI Commands

| Command | Description |
|---------|-------------|
| `qms docs load-module [files...]` | Load quality manual module(s) from XML |
| `qms docs summary` | Show quality manual summary/status |
| `qms docs search <query>` | Full-text search across quality manual content |
| `qms docs detail <module_number>` | Show detailed info about a specific module |

## Database Tables (14 total)

### Quality Manual Structure
| Table | Purpose |
|-------|---------|
| `qm_modules` | Quality manual modules (top-level documents) |
| `qm_sections` | Sections within modules |
| `qm_subsections` | Subsections (7 types: policy, scope, responsibility, procedure, reference, definition, appendix) |
| `qm_content_blocks` | Content blocks (9 types: paragraph, list_item, table, figure, note, warning, example, requirement, definition) |

### Cross-References
| Table | Purpose |
|-------|---------|
| `qm_cross_references` | Cross-refs between modules and to external standards |
| `qm_code_references` | Code/standard references in content (ASME, IIAR, etc.) |
| `qm_responsibility_assignments` | Role-responsibility mappings |
| `qm_content_fts` | **FTS5 virtual table** for full-text search |

### Document Control
| Table | Purpose |
|-------|---------|
| `qm_procedures` | SOPs, Work Instructions, Policies (with revision tracking) |
| `qm_forms` | Forms registry (linked to procedures and modules) |
| `qm_records` | Quality records (linked to forms and projects) |
| `qm_templates` | Document templates |
| `qm_document_history` | Revision history for all document types |
| `qm_intake_log` | Document intake log |

## Key Functions

| Function | Location | Description |
|----------|----------|-------------|
| `load_module_from_file(path)` | `qualitydocs/` | Parse XML and load single module |
| `get_manual_summary()` | `qualitydocs/` | Summary statistics across all modules |
| `get_module_detail(number)` | `qualitydocs/` | Detailed module info with sections |
| `search_content(query, limit)` | `qualitydocs/` | FTS5 search with Porter stemming |

## Dependencies

### Depends On
- [[core]] — Database, logging

### Depended By
- [[references]] — `qm_procedures` table referenced by `ref_procedure_links`
- [[vectordb]] — Indexes QM content for semantic search

## Related Notes
- [[references]] — External standards that map to QM procedures
- [[vectordb]] — Semantic search across QM content
