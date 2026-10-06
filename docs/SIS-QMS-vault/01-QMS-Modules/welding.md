---
module: welding
cli_name: welding
status: Complete
commands: [dashboard, continuity, import-wps, import-weekly, check-notifications, register, export-lookups, cert-requests, cert-results, approve-wcr, assign-wpq, schedule-retest, process-requests, seed-lookups, extract, generate, register-template, derive-ranges, fix-wps, list-pqrs]
depends_on: [core, workforce, automation]
depended_by: [pipeline]
tables: [weld_welder_registry, weld_wps, weld_pqr, weld_wpq, weld_bps, weld_bpq, weld_bpqr, weld_continuity_log, weld_production_welds, weld_ndt_results, weld_notification_rules, weld_notifications, weld_intake_log, weld_document_revisions, weld_cert_requests, weld_cert_request_coupons]
shared_tables: [business_units]
api_blueprint: "-"
source_dir: welding/
schema_file: welding/schema.sql
tags: [qms-module, welding-program]
created: 2026-02-10
updated: 2026-02-18
---

# Welding

Manages the **complete welding quality program**: WPS/PQR/WPQ document control, welder qualifications, brazing procedures, continuity tracking, production weld logging, NDT results, automated notifications for expiring qualifications, and **weld certification request processing** (WCR workflow from Power Automate intake through testing and WPQ assignment).

## Architecture

- **56 database tables** — the largest schema in QMS
- Three-tier document hierarchy: WPS (procedure) → PQR (qualification record) → WPQ (welder performance)
- Parallel brazing hierarchy: BPS → BPQ → BPQR
- Notification engine with configurable rules for expiration alerts
- **Weld Cert Request (WCR) workflow** with JSON intake from Power Automate, status tracking, coupon-level results, WPQ creation, and retest scheduling
- Registers `weld_cert_request` handler with the [[automation]] dispatcher
- Uses shared [[projects#business_units]] table for BU assignment
- Links to [[workforce]] employees via `employee_id` FK

## CLI Commands

### Core Commands
| Command | Description |
|---------|-------------|
| `qms welding dashboard` | Welding program dashboard summary |
| `qms welding continuity` | Show welder continuity status (6-month qualification windows) |
| `qms welding import-wps <file>` | Import WPS/welder data from Excel spreadsheet |
| `qms welding import-weekly <file>` | Process weekly weld production import from Excel/CSV |
| `qms welding check-notifications` | Check and manage welding qualification notifications |

### Registration Commands
| Command | Description |
|---------|-------------|
| `qms welding register` | Register a new welder (interactive, CLI args, or batch CSV via `--batch`). Supports `--dry-run`. |
| `qms welding export-lookups` | Export welding lookup data (welders, WPS, processes) to Excel for Power Automate dropdowns. Supports `--output`, `--dry-run`. |

### Cert Request Workflow Commands
| Command | Description |
|---------|-------------|
| `qms welding cert-requests` | List WCRs with filters (`--status`, `--project`, `--welder`). Use `--detail <WCR#>` for full detail with coupons. |
| `qms welding cert-results <WCR#>` | Enter test results for coupons. Single coupon via `--coupon`/`--result`, or interactive mode for all pending coupons. |
| `qms welding approve-wcr <WCR#>` | Approve a pending cert request. Requires `--by <approver>`. |
| `qms welding assign-wpq <WCR#>` | Create a WPQ record from a passed coupon. Requires `--coupon`. Optional `--months` for expiration. |
| `qms welding schedule-retest <WCR#>` | Schedule retest for a failed coupon (creates new WCR). Requires `--coupon`. |
| `qms welding process-requests [file]` | Process cert request JSON files (delegates to [[automation]] dispatcher). Supports `--dry-run`. |

## Database Tables (56 total)

### Core Registry
| Table | Purpose |
|-------|---------|
| `weld_welder_registry` | Welder master records (stamp, BU, status, weld counts) |

### WPS Family (12 tables)
| Table | Purpose |
|-------|---------|
| `weld_wps` | Welding Procedure Specifications |
| `weld_wps_processes` | WPS welding processes (SMAW, GMAW, etc.) |
| `weld_wps_joints` | Joint types and groove details |
| `weld_wps_base_metals` | Base metal P-numbers and specs |
| `weld_wps_filler_metals` | Filler metal F-numbers and AWS class |
| `weld_wps_positions` | Qualified welding positions |
| `weld_wps_preheat` | Preheat requirements |
| `weld_wps_pwht` | Post-weld heat treatment |
| `weld_wps_gas` | Shielding/backing gas |
| `weld_wps_electrical_params` | Amperage, voltage, travel speed |
| `weld_wps_technique` | Bead type, weave, electrode details |
| `weld_wps_pqr_links` | WPS ↔ PQR linkages |

### PQR Family (13 tables)
| Table | Purpose |
|-------|---------|
| `weld_pqr` | Procedure Qualification Records |
| `weld_pqr_joints` through `weld_pqr_personnel` | PQR detail and test result tables |

### WPQ (2 tables)
| Table | Purpose |
|-------|---------|
| `weld_wpq` | Welder Performance Qualifications |
| `weld_wpq_tests` | WPQ test specimens and results |

### Brazing (10 tables)
| Table | Purpose |
|-------|---------|
| `weld_bps`, `weld_bpq`, `weld_bpqr` | Brazing procedure/qualification equivalents |
| + detail tables | Base metals, filler metals, tests |

### Production & QA
| Table | Purpose |
|-------|---------|
| `weld_continuity_log` | 6-month continuity tracking events |
| `weld_production_welds` | Production weld records (per welder/project/week) |
| `weld_ndt_results` | NDT test results (RT, UT, MT, PT, VT) |

### Notifications
| Table | Purpose |
|-------|---------|
| `weld_notification_rules` | Configurable notification rules |
| `weld_notifications` | Active notification instances |

### Weld Cert Requests (2 tables)

| Table | Purpose |
|-------|---------|
| `weld_cert_requests` | Certification test requests (WCR-YYYY-NNNN). Tracks welder, project, approval, status lifecycle. |
| `weld_cert_request_coupons` | Individual test coupons within a WCR. Tracks process, position, WPS, test results, WPQ assignment, retest linkage. |

#### `weld_cert_requests` Schema

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| wcr_number | TEXT UNIQUE | Format: `WCR-YYYY-NNNN` |
| welder_id | INTEGER FK | References `weld_welder_registry(id)` |
| employee_number | TEXT | Welder employee number |
| welder_name | TEXT | Welder full name |
| welder_stamp | TEXT | Welder stamp (e.g., Z-15) |
| project_number | TEXT | Project number |
| project_name | TEXT | Project name |
| request_date | TEXT | Date of request |
| submitted_by | TEXT | Who submitted the request |
| submitted_at | TEXT | Submission timestamp |
| status | TEXT | `pending_approval`, `approved`, `testing`, `results_received`, `completed`, `cancelled` |
| is_new_welder | INTEGER | 1 if welder was auto-registered during intake |
| notes | TEXT | Free-form notes |
| approved_by | TEXT | Approver name |
| approved_at | TEXT | Approval timestamp |
| source_file | TEXT | Original JSON filename |

#### `weld_cert_request_coupons` Schema

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| wcr_id | INTEGER FK | References `weld_cert_requests(id)` ON DELETE CASCADE |
| coupon_number | INTEGER | Coupon sequence (1-4) within the WCR |
| process | TEXT | Welding process (SMAW, GTAW, GMAW, FCAW, SAW, GTAW/SMAW) |
| position | TEXT | Test position (e.g., 6G) |
| wps_number | TEXT | WPS being qualified against |
| base_material | TEXT | Base metal spec |
| filler_metal | TEXT | Filler metal spec |
| thickness | TEXT | Material thickness |
| diameter | TEXT | Pipe diameter |
| status | TEXT | `pending`, `testing`, `passed`, `failed`, `wpq_assigned`, `retest_scheduled` |
| test_result | TEXT | `pass` or `fail` |
| visual_result | TEXT | Visual test result |
| bend_result | TEXT | Bend test result |
| rt_result | TEXT | Radiographic test result |
| failure_reason | TEXT | Reason for failure |
| tested_by | TEXT | Tester name |
| tested_at | TEXT | Test date |
| wpq_id | INTEGER FK | References `weld_wpq(id)` when WPQ is assigned |
| retest_wcr_id | INTEGER FK | References `weld_cert_requests(id)` for retest linkage |

#### WCR Status Lifecycle

```
pending_approval  ──[approve-wcr]──>  approved
                                         │
                                    [enter results]
                                         │
                                      testing  ──[all results in]──>  results_received
                                                                          │
                                                               [all passed + WPQ assigned]
                                                                          │
                                                                      completed
```

- **Status auto-calculated** from coupon statuses by `_update_wcr_status()`
- All coupons `passed`/`wpq_assigned` => WCR `completed`
- Mix of results with some pending => `testing`
- All results entered but not all WPQs assigned => `results_received`
- Failed coupons can be retested via `schedule-retest` (creates a new WCR)

#### JSON Intake Format

Requests arrive as JSON files (typically from Power Automate) with `"type": "weld_cert_request"`:

```json
{
  "type": "weld_cert_request",
  "welder": {
    "employee_number": "12345",
    "name": "John Doe",
    "stamp": "Z-15",
    "is_new": false
  },
  "project": { "number": "07645", "name": "Project Name" },
  "coupons": [
    {
      "process": "SMAW",
      "position": "6G",
      "wps_number": "WPS-001",
      "base_material": "A106",
      "filler_metal": "7018",
      "thickness": "3/4\"",
      "diameter": "6\""
    }
  ],
  "submitted_by": "Jane Smith",
  "request_date": "2026-02-11"
}
```

Max coupons per request: 4 (configurable in `config.yaml`).

## Key Functions

| Function | Location | Description |
|----------|----------|-------------|
| `process_cert_request(json_path)` | `welding/cert_requests.py` | Full intake pipeline: parse, validate, register welder, create WCR + coupons |
| `validate_cert_request_json(data)` | `welding/cert_requests.py` | Validate JSON structure and fields |
| `get_next_wcr_number(conn)` | `welding/cert_requests.py` | Generate next WCR-YYYY-NNNN sequence |
| `list_cert_requests(status, project, welder)` | `welding/cert_requests.py` | Query WCRs with optional filters |
| `get_cert_request_detail(wcr_number)` | `welding/cert_requests.py` | Full WCR detail with nested coupons |
| `enter_coupon_result(wcr, coupon, result)` | `welding/cert_requests.py` | Enter pass/fail result for a coupon |
| `approve_cert_request(wcr, approved_by)` | `welding/cert_requests.py` | Approve a pending WCR |
| `assign_wpq_from_coupon(wcr, coupon)` | `welding/cert_requests.py` | Create WPQ record from a passed coupon |
| `schedule_retest(wcr, coupon)` | `welding/cert_requests.py` | Create new WCR for failed coupon retest |
| `register_new_welder(conn, ...)` | `welding/registration.py` | Register a new welder in the registry |
| `register_batch(csv_path, dry_run)` | `welding/registration.py` | Batch register welders from CSV |
| `export_lookups(output_path, dry_run)` | `welding/export_lookups.py` | Export lookup data to Excel for Power Automate |

## Dependencies

### Depends On
- [[core]] — Database, logging, config
- [[workforce]] — Employee linkages via `employee_id`
- [[automation]] — Dispatcher for JSON request intake (registers `weld_cert_request` handler)
- `business_units` table (defined in [[projects]] schema)

### Depended By
- [[pipeline]] — Continuity tracking for welders found in drawings

## Naming Conventions

See [[welding-naming-conventions]] for the full reference document (WP-003).

**Quick reference:**
- **WPS:** `{Material}-{Seq}-P{num}-{Process}[-Modifier]` (e.g., `CS-01-P1-SMAW`)
- **PQR:** Mirrors WPS or legacy format retained
- **WPQ:** `{Stamp}-{WPS_Number}` (e.g., `B15-CS-01-P1-SMAW`)
- **Stamp:** `{LastInitial}{NN}` (e.g., `B15`) — no dash, zero-padded

### Migrations (welding/migrations.py)
| Migration | Purpose |
|-----------|---------|
| `migrate_fix_wps_numbers` | Correct 5 truncated WPS numbers + cascade |
| `migrate_normalize_wpq_numbers` | Normalize separators, case, process slashes |
| `migrate_import_known_pqrs` | Import 15 PDF-verified PQR records |
| `migrate_populate_wps_pqr_links` | Cross-reference 7 WPS to their supporting PQRs |

### New CLI Commands
| Command | Description |
|---------|-------------|
| `qms welding fix-wps <wps> --name <new>` | Fix an ambiguous WPS number with cascade |
| `qms welding list-pqrs` | Show PQR records with linked WPS count |

## Related Notes
- [[welding-naming-conventions]] — Formal naming convention reference (WP-003)
- [[automation]] — JSON request dispatcher (intake gateway)
- [[workforce]] — Employee master records
- [[projects]] — Shared `business_units` table
- [[Database Overview]] — Cross-module FK map
