# QMS CLI Reference

> All 65 CLI commands. Updated 2026-02-23.

## Quick Start

```bash
pip install -e D:\qms            # Install editable (core)
pip install -e "D:\qms[web]"     # Install with web UI (Flask)
qms version                      # Show version
qms migrate                      # Run all schema migrations
qms serve                        # Launch web UI at localhost:5000
qms serve --debug                # Dev server with auto-reload
```

## Command Table

| Group | Command | Description |
|-------|---------|-------------|
| `qms` | `version` | Show version |
| | `migrate` | Run all schema migrations |
| | `serve` | Launch web UI |
| `qms eng` | `history` | Calculation history |
| | `line-sizing` | Pipe line sizing |
| | `relief-valve` | Safety relief valve sizing |
| | `pump` | Pump sizing |
| | `ventilation` | Ventilation calculations |
| | `charge` | Refrigerant charge calculation |
| | `validate-pipes` | Validate pipe drawings vs calcs |
| | `validate-relief` | Validate relief valve drawings vs calcs |
| `qms welding` | `dashboard` | Welding program status |
| | `continuity` | Continuity tracking |
| | `import-wps` | Import WPS documents |
| | `import-weekly` | Import weekly reports |
| | `check-notifications` | Check expiration notifications |
| | `register` | Register welders |
| | `export-lookups` | Export lookup tables |
| | `cert-requests` | Certification requests |
| | `cert-results` | Certification results |
| | `approve-wcr` | Approve welder cert requests |
| | `assign-wpq` | Assign WPQ to welder |
| | `schedule-retest` | Schedule retest |
| | `process-requests` | Process pending requests |
| | `seed-lookups` | Seed lookup data |
| | `extract` | Extract form data from PDF |
| | `generate` | Generate welding documents |
| | `register-template` | Register form template |
| | `derive-ranges` | Derive qualification ranges |
| `qms automation` | `process` | Process automation requests |
| | `status` | Show automation status |
| `qms docs` | `load-module` | Load QM module XML |
| | `summary` | Quality manual summary |
| | `search` | Search quality documents |
| | `detail` | Show document detail |
| `qms refs` | `extract` | Extract reference standard |
| | `list` | List extracted standards |
| | `search` | Search reference clauses |
| | `clauses` | Show clauses for a standard |
| `qms projects` | `scan` | Scan project folders |
| | `list` | List projects |
| | `summary` | Project summary |
| | `import-procore` | Import from Procore |
| `qms timetracker` | `export-timecard` | UKG timecard export |
| | `migrate-timetracker` | Migrate time tracking data |
| `qms pipeline` | `status` | Pipeline status |
| | `queue` | Show processing queue |
| | `import-drawing` | Import single drawing |
| | `import-batch` | Batch import drawings |
| | `process` | Process queued items |
| | `intake` | Run document intake |
| `qms workforce` | `list` | List employees |
| | `import-csv` | Import employees from CSV |
| | `import-from-sis` | Import from SIS data |
| | `bulk-update` | Bulk update employee records |
| `qms vectordb` | `index` | Build/rebuild search index |
| | `search` | Semantic search |
| | `status` | Index status |
| | `queue` | Show indexing queue |
| `qms auth` | `create-user` | Create new user |
| | `reset-password` | Reset user password |
| | `grant-access` | Grant module access |
| | `revoke-access` | Revoke module access |
| | `list-users` | List all users |
| `qms report` | `system` | System report |

## Engineering Calculation Examples

```bash
qms eng line-sizing --capacity-tons 200 --line-type wet
qms eng relief-valve --volume-cuft 150 --set-pressure-psig 300
qms eng pump --capacity-tons 100 --recirculation-rate 4
qms eng ventilation --length-ft 40 --width-ft 25 --height-ft 14
qms eng charge --volume-cuft 20 --temperature -20

# Validate drawings against calculations
qms eng validate-pipes 07645
qms eng validate-relief 07645
```

All calculations are saved to the `eng_calculations` audit trail.

## Unified Inbox

Drop ALL documents in `data/inbox/` — the system classifies and routes automatically:

| Document Type | Example | Routes To |
|---------------|---------|-----------|
| Drawings | `P-101_Rev_B.pdf` | `data/projects/{project}/{discipline}/` |
| Specifications | `242300-Refrigeration_Rev_01.pdf` | `data/projects/{project}/{set}/Specs/` |
| Procedures | `SP-001-Welding.pdf` | `data/quality-documents/Procedures/` |
| Forms | `FM-001-Inspection.pdf` | `data/quality-documents/Forms/` |
| QM Modules | `module1.xml` | `data/quality-documents/Modules/` |

Classification uses `pipeline/classifier.py` — config-driven regex patterns covering 15+ document types.
