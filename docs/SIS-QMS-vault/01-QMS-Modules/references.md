---
module: references
cli_name: refs
status: Complete
commands: [extract, list, search, clauses]
depends_on: [core, qualitydocs]
depended_by: [vectordb]
tables: [qm_references, ref_clauses, ref_content_blocks, ref_procedure_links, ref_sections, ref_extraction_log, ref_clauses_fts, ref_content_fts]
api_blueprint: "-"
source_dir: references/
schema_file: references/schema.sql
tags: [qms-module, standards]
created: 2026-02-10
updated: 2026-02-10
---

# References

Extracts, stores, and searches **external reference standards** (ASME, IIAR, OSHA, etc.) from PDF documents. Links extracted clauses back to internal QMS procedures, creating a compliance traceability matrix.

## Architecture

- PDF extraction pipeline: **detect publisher → split sections → extract text → parse clauses → load to DB**
- Parallel extraction via `ref_sections` (each section processed independently)
- AI-assisted extraction with confidence scoring and model tracking
- Dual FTS5 tables for searching both clause summaries and full content
- Links to [[qualitydocs]] procedures via `ref_procedure_links` table

## CLI Commands

| Command | Description |
|---------|-------------|
| `qms refs extract <pdf_path> --standard-id <id>` | Extract reference standard content from PDF |
| `qms refs list [--status] [--extracted]` | List reference standards |
| `qms refs search <query> [--content]` | Full-text search across reference standards |
| `qms refs clauses <standard_id>` | List extracted clauses for a standard |

## Database Tables (8 total)

| Table | Purpose |
|-------|---------|
| `qm_references` | Reference standards registry (standard_id, publisher, extraction status) |
| `ref_clauses` | Extracted clauses with hierarchy (self-referencing parent_clause_id) |
| `ref_content_blocks` | Content blocks within clauses (14 block types) |
| `ref_procedure_links` | **Cross-module:** Links clauses → `qm_procedures` (IMPLEMENTS/REFERENCES/PARTIAL/EXCLUDES) |
| `ref_sections` | PDF sections for parallel extraction with status tracking |
| `ref_extraction_log` | Extraction operation audit trail |
| `ref_clauses_fts` | FTS5 search on clause summaries |
| `ref_content_fts` | FTS5 search on content blocks |

## Key Functions

| Function | Location | Description |
|----------|----------|-------------|
| `extract_and_load()` | `references/` | Full extraction pipeline (PDF → DB) |
| `detect_publisher()` | `references/` | Auto-detect standard publisher from PDF |
| `parse_clauses()` | `references/` | Parse clause structure from extracted text |
| `search_clauses()` | `references/` | FTS search on clause summaries |
| `search_content()` | `references/` | FTS search on content blocks |
| `list_clauses()` | `references/` | List clauses for a standard |

## Dependencies

### Depends On
- [[core]] — Database, logging
- [[qualitydocs]] — `qm_procedures` table for procedure linking

### Depended By
- [[vectordb]] — Indexes reference clauses for semantic search

## Related Notes
- [[qualitydocs]] — Internal procedures that implement reference standards
- [[vectordb]] — Semantic search across reference content
