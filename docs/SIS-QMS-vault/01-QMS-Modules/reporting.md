---
module: reporting
cli_name: report
status: Pending
commands: [system]
depends_on: [core, projects, workforce, welding, pipeline]
depended_by: []
tables: []
api_blueprint: "-"
source_dir: reporting/
schema_file: "-"
tags: [qms-module, reporting, stub]
created: 2026-02-10
updated: 2026-02-10
---

# Reporting

> **Status: STUB** — This module is not yet implemented. Only a skeleton `system` command exists.

Cross-module reporting and analytics. Will aggregate data from all other modules to produce quality dashboards, compliance reports, and trend analysis.

## Planned Architecture

- Read-only module — queries tables from other modules, creates no tables of its own
- Planned report types:
  - System-wide quality dashboard
  - Project status reports
  - Welding program compliance
  - Workforce certification status
  - Pipeline extraction accuracy trends

## CLI Commands

| Command | Description | Status |
|---------|-------------|--------|
| `qms report system` | System-wide quality dashboard | **Stub** |

## Database Tables
None — reads from other modules.

## Dependencies

### Depends On
- [[core]] — Database
- [[projects]] — Project data
- [[workforce]] — Employee/certification data
- [[welding]] — Welding program data
- [[pipeline]] — Extraction data

### Depended By
None.

## TODO
- [ ] Design report templates
- [ ] Implement system dashboard
- [ ] Add project-level reporting
- [ ] Add welding compliance reporting
- [ ] Add workforce certification reporting
- [ ] Add pipeline accuracy trending
