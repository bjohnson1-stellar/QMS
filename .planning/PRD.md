# QMS — Product Requirements Document

> **Version:** 1.0
> **Date:** 2026-02-27
> **Author:** Brandon Johnson (bjohnson1@sissllc.com)
> **Organization:** Stellar Industrial & Systems Services (SIS)
> **Repository:** https://github.com/bjohnson1-stellar/QMS.git

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Vision & Goals](#2-product-vision--goals)
3. [Users & Access Control](#3-users--access-control)
4. [Technology Stack](#4-technology-stack)
5. [System Architecture](#5-system-architecture)
6. [Configuration System](#6-configuration-system)
7. [Database Design](#7-database-design)
8. [Module Specifications](#8-module-specifications)
   - 8.1 [Authentication](#81-authentication)
   - 8.2 [Projects & Budgets](#82-projects--budgets)
   - 8.3 [Time Tracker & Projections](#83-time-tracker--projections)
   - 8.4 [Welding Program (ASME IX)](#84-welding-program-asme-ix)
   - 8.5 [Workforce Management](#85-workforce-management)
   - 8.6 [Quality Intelligence](#86-quality-intelligence)
   - 8.7 [Document Pipeline & Intake](#87-document-pipeline--intake)
   - 8.8 [Engineering Calculations](#88-engineering-calculations)
   - 8.9 [Quality Documents (QM CMS)](#89-quality-documents-qm-cms)
   - 8.10 [Reference Standards Library](#810-reference-standards-library)
   - 8.11 [Vector Search](#811-vector-search)
   - 8.12 [Automation](#812-automation)
   - 8.13 [The Observatory (Blog)](#813-the-observatory-blog)
   - 8.14 [Reporting](#814-reporting)
   - 8.15 [Settings & Administration](#815-settings--administration)
9. [Frontend & Theming](#9-frontend--theming)
10. [CLI System](#10-cli-system)
11. [Import Infrastructure](#11-import-infrastructure)
12. [AI Model Integration](#12-ai-model-integration)
13. [External Integrations](#13-external-integrations)
14. [Testing Requirements](#14-testing-requirements)
15. [Deployment & Operations](#15-deployment--operations)
16. [Appendix A: Complete API Reference](#appendix-a-complete-api-reference)
17. [Appendix B: Complete Database Schema](#appendix-b-complete-database-schema)
18. [Appendix C: Config.yaml Reference](#appendix-c-configyaml-reference)

---

## 1. Executive Summary

**QMS (Quality Management System)** is a modular, config-driven Python/Flask application built for Stellar Industrial & Systems Services' MEP (Mechanical, Electrical, Plumbing) division. It consolidates construction quality management, welding certification tracking, project budgeting, employee management, engineering drawing intelligence, and document control into a single LAN-accessible web application backed by SQLite.

### What QMS Does

| Domain | Capability |
|--------|-----------|
| **Welding** | Full ASME IX / AWS D1.1 compliance: WPS, PQR, WPQ, BPS, BPQ, BPQR tracking with AI-powered PDF extraction, qualification derivation, continuity tracking, and certification request workflows |
| **Projects** | Project hierarchy with customer/facility/job relationships, 3-tier budget model (project → allocation → snapshot), Procore CSV import |
| **Time & Budget** | Transaction ledger, monthly hour projections with snapshot versioning, UKG timecard export, GMP budget tracking |
| **Workforce** | Employee/subcontractor registry, 4-level duplicate detection, certification tracking, permission management, CSV/Excel import with approval workflow |
| **Quality** | Unified issue tracker (observations, NCRs, CARs, deficiencies, punch items) with root cause analysis, corrective actions, audit trail, and Procore sync |
| **Pipeline** | Config-driven document classification and routing from unified inbox, engineering drawing extraction across 11 disciplines, revision tracking, conflict detection |
| **Engineering** | Refrigeration calculations (line sizing, relief valves, pumps, ventilation, charge), drawing-vs-calculation validation |
| **Documents** | Quality manual CMS (XML → structured content), procedures, forms, templates with FTS5 search and PDF export |
| **References** | Engineering standard extraction (ASME, AWS, ISO) with clause-level granularity and FTS5 search |
| **Search** | ChromaDB vector embeddings for semantic search across all content types |
| **Blog** | "The Observatory" — internal knowledge-sharing platform with scheduled publishing |

### Key Metrics

- **263 database tables** across 14 schema files
- **65+ CLI commands** across 13 module groups
- **11 Flask blueprints** serving web APIs and HTML pages
- **35 Jinja2 templates** with full dark mode support
- **534+ automated tests**
- **3,586 lines of CSS** with config-driven theming

---

## 2. Product Vision & Goals

### Vision

A single, self-hosted quality management platform that MEP construction teams use daily — replacing scattered spreadsheets, paper forms, and siloed databases with an integrated system that connects welding certifications to project budgets to quality observations to engineering calculations.

### Design Principles

1. **Config-driven modularity** — Adding a module requires YAML config, not code changes. Navigation, access control, and routing all derive from `config.yaml`.
2. **Single database** — One SQLite file (`quality.db`) holds all data. No microservices, no message queues. WAL mode enables concurrent reads.
3. **Layer separation** — Business logic lives in pure Python modules (no Flask imports). API layer wraps results. Templates consume context. This allows CLI, background tasks, and web to share logic.
4. **AI-augmented, not AI-dependent** — Claude models extract data from PDFs and drawings, but all data entry and management works without AI. Extraction enhances, doesn't gate.
5. **LAN-first** — Deployed on a single Windows workstation, accessible to the office network. No cloud dependencies for core operation.
6. **Incremental adoption** — Each module works independently. Teams can start with projects + welding and add quality tracking, pipeline extraction, etc. over time.

### Non-Goals

- Multi-tenant SaaS deployment
- Mobile-native applications (web responsive is sufficient)
- Real-time collaboration (eventual consistency via page refresh)
- Cloud-hosted database (SQLite is the design choice)

---

## 3. Users & Access Control

### User Model

Users authenticate with email + password (local provider, no external IdP). Each user has:

| Field | Type | Description |
|-------|------|-------------|
| `email` | TEXT UNIQUE | Login identifier |
| `display_name` | TEXT | Shown in UI |
| `password_hash` | TEXT | Werkzeug PBKDF2 hash |
| `role` | TEXT | Global role: `admin`, `user`, `viewer` |
| `is_active` | BOOLEAN | Account enabled/disabled |
| `must_change_password` | BOOLEAN | Force password change on next login |
| `employee_id` | FK | Optional link to workforce employee record |

### Three-Layer Access Control

**Layer 1: Global Role** (`users.role`)

| Role | Access |
|------|--------|
| `admin` | Full system access, bypasses all module/BU checks, sees admin-only modules |
| `user` | Access to assigned modules only |
| `viewer` | Read-only access to assigned modules |

**Layer 2: Module Access** (`user_module_access`)

Each non-admin user has per-module roles:

| Module Role | Capabilities |
|------------|-------------|
| `admin` | Full CRUD within module |
| `editor` | Create/update within module |
| `viewer` | Read-only within module |

Modules are defined in `config.yaml` `web_modules:` section. Some modules can be marked `admin_only: true` (returns 404 to non-admins, not 403 — hides from navigation).

**Layer 3: Business Unit Filtering** (`user_business_units`)

Non-admin users can be restricted to specific business units:
- Empty `user_business_units` = unrestricted (sees all BUs)
- Specific BU IDs = user sees only projects/data in those BUs
- Admins always bypass BU filtering

BU filtering applies to: dashboard stats, project lists, budget allocations, transaction views, quality issues, hierarchical views.

### Session Management

| Setting | Value |
|---------|-------|
| Cookie name | `qms_session` |
| Lifetime | 480 minutes (8 hours), configurable |
| HttpOnly | Yes (no JS access) |
| SameSite | Lax (CSRF protection for cross-origin) |
| Secret key | Persistent file (`data/.secret_key`), survives restarts |

### Dev Bypass Mode

Setting `auth.dev_bypass: true` in config.yaml auto-creates an admin session without requiring login. For development only.

### CSRF Protection

- HMAC-SHA256 tokens tied to session nonce
- Validated on all POST form submissions
- JSON requests exempt (SameSite=Lax provides protection)
- Tokens injected via `{{ csrf_token() }}` template function

---

## 4. Technology Stack

### Runtime

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Language | Python | ≥3.11 | Core runtime |
| Web Framework | Flask | ≥2.0 | API + HTML serving |
| WSGI Server | Waitress | ≥2.1.2 | Production server (Windows-native) |
| Database | SQLite | 3.x (bundled) | Single-file database with WAL |
| CLI Framework | Typer | ≥0.9.0 | Command-line interface |
| Template Engine | Jinja2 | (bundled with Flask) | HTML rendering |
| CSS | Vanilla CSS | — | No preprocessor, CSS custom properties |

### Core Dependencies

| Package | Purpose |
|---------|---------|
| `pyyaml` | Configuration parsing |
| `openpyxl` | Excel I/O (import/export) |
| `rich` | CLI terminal output formatting |
| `qrcode[pil]` | QR code generation for welding forms |
| `markdown` | Blog post rendering |
| `werkzeug` | Password hashing, HTTP utilities |

### Optional Dependencies

| Group | Packages | Purpose |
|-------|----------|---------|
| `pipeline` | chromadb, sentence-transformers, PyMuPDF, anthropic | Drawing extraction + vector search |
| `welding` | PyMuPDF, anthropic | Welding form PDF extraction |
| `export` | weasyprint | PDF report generation |
| `dev` | pytest, pytest-cov, ruff, mypy | Testing + linting |

### AI Models

| Tier | Model | Use Cases |
|------|-------|-----------|
| Simple | Claude Haiku | Title block reading, file routing, pattern matching |
| Complex | Claude Sonnet | Full extraction, conflict detection, revision comparison |
| Critical | Claude Opus | Shadow review, calibration, quality validation |

---

## 5. System Architecture

### Directory Structure

```
D:\qms/                              # Repo root = Package root
├── pyproject.toml                    # Package metadata + dependencies
├── config.yaml                       # Unified settings (relative paths)
├── CLAUDE.md                         # Development instructions
├── .planning/                        # Architecture docs, roadmap
│
├── data/                             # Runtime (git-ignored)
│   ├── quality.db                    # SQLite database (263 tables)
│   ├── .secret_key                   # Session secret (persistent)
│   ├── inbox/                        # Document intake hub
│   │   ├── NEEDS-REVIEW/
│   │   ├── CONFLICTS/
│   │   └── DUPLICATES/
│   ├── projects/                     # Engineering drawings by project
│   ├── quality-documents/            # QM procedures, forms, references
│   └── vectordb/                     # ChromaDB embeddings
│
├── core/                             # Shared services
│   ├── config.py                     # Config loading + QMS_PATHS singleton
│   ├── db.py                         # Database access + migration orchestration
│   └── logging.py                    # Structured logging
│
├── auth/                             # Authentication module
├── api/                              # Flask blueprints (11)
│   └── __init__.py                   # App factory
├── frontend/
│   ├── templates/                    # Jinja2 templates (35)
│   └── static/                       # CSS, fonts, images
│
├── projects/                         # Project + budget logic
├── timetracker/                      # Projections + transactions
├── welding/                          # ASME IX program (50+ tables)
├── workforce/                        # Employee management
├── quality/                          # Issue tracking
├── pipeline/                         # Document intake + extraction
├── engineering/                      # Calculation library
├── qualitydocs/                      # Quality manual CMS
├── references/                       # Standards library
├── vectordb/                         # Semantic search
├── imports/                          # Shared import engine
├── automation/                       # Power Automate integration
├── blog/                             # The Observatory
├── reporting/                        # Analytics
├── cli/main.py                       # Typer entrypoint
└── tests/                            # Test suite (534+ tests)
```

### Request Flow

```
Browser → Waitress (port 5000) → Flask App Factory
  → Security headers (X-Content-Type-Options, X-Frame-Options)
  → CSRF check (POST forms only)
  → Auth gate (session check)
  → Module access check (blueprint → module mapping)
  → BU filter injection (for non-admins)
  → Blueprint route handler
  → Module business logic (pure Python)
  → Database query (SQLite with WAL)
  → Template rendering (with theme + user context)
  → Response
```

### Blueprint Registration

| Blueprint | URL Prefix | Module | Admin Only |
|-----------|-----------|--------|------------|
| `auth` | `/auth` | — | No |
| `projects` | `/projects` | projects | No |
| `timetracker` | `/timetracker` | timetracker | Yes |
| `welding` | `/welding` | welding | No |
| `workforce` | `/workforce` | workforce | No |
| `quality` | `/quality` | quality | No |
| `pipeline` | `/pipeline` | pipeline | No |
| `automation` | `/automation` | automation | No |
| `qualitydocs` | `/qualitydocs` | qualitydocs | No |
| `blog` | `/blog` | — | No |
| `settings` | `/settings` | — | No |

### Context Processors (Global Template Variables)

Every template receives:
- `theme` — Branding dict (colors, fonts, app_name, tagline)
- `current_user` — Authenticated user object
- `accessible_modules` — Set of module keys the user can access
- `web_modules` — Full module registry from config
- `csrf_token` — CSRF token generator function

---

## 6. Configuration System

### Overview

`config.yaml` at the package root is the single source of truth for all runtime configuration. Paths are relative and resolved at runtime via `QMS_PATHS._resolve()` against the package directory.

### Key Functions

```python
get_config(reload=False) → dict          # Load/cache config.yaml
get_config_value(*keys, default=None)    # Nested key access
get_branding() → dict                    # Branding section with defaults
get_web_modules() → dict                 # Module registry with defaults
update_config_section(path, data)        # Persist changes to disk
```

### Config Sections

| Section | Purpose |
|---------|---------|
| `auth` | Provider, dev_bypass, session lifetime, secret key |
| `branding` | App name, colors (9), fonts (4), preset, default mode |
| `web_modules` | Module registry with labels, endpoints, admin_only flags |
| `inbox` | Unified inbox path + subdirectory names |
| `destinations` | File paths for projects, quality docs, database, vectordb |
| `document_types` | 15+ document classification patterns with regex, destination templates, handlers |
| `models` | AI model routing (simple/complex/critical → haiku/sonnet/opus) |
| `extraction` | Confidence thresholds, material codes, shadow review rate |
| `conflicts` | Conflict detection check toggles |
| `processing` | Batch size, auto-supersede, auto-archive settings |
| `intake` | Auto-extract, auto-embed, ambiguous handling |
| `departments` | MEP trade departments (600-665) |
| `discipline_prefixes` | Drawing prefix → discipline mapping |
| `csi_mapping` | CSI division → discipline mapping |
| `welding` | Cert request config, extraction model config, generation settings |
| `quality` | Attachment directory, trade/status/type normalization maps |
| `reference_extraction` | Parallel extraction thresholds, model assignments, validation settings |
| `procore` | Base URL + per-project Procore ID mappings |
| `onedrive_sync` | Source root, delete-after-sync flag |
| `embeddings` | Provider, model, dimensions, batch size |
| `automation` | Incoming/processed/failed directory paths |
| `qm_prefixes` | Document type prefix mappings (SP, WI, TP, FM, PL, RC) |

See [Appendix C](#appendix-c-configyaml-reference) for the complete reference.

---

## 7. Database Design

### Architecture

| Aspect | Details |
|--------|---------|
| Engine | SQLite 3.x (Python bundled) |
| Location | `data/quality.db` (resolved via QMS_PATHS) |
| Tables | 263 (including FTS5 virtual tables) |
| Schema files | 14 (one per module) |
| Pragmas | `foreign_keys = ON`, `journal_mode = WAL` |
| Row factory | `sqlite3.Row` (dict-like access) |
| Migrations | Idempotent `schema.sql` + incremental `migrations.py` per module |

### Schema Execution Order (FK Dependency Chain)

```python
SCHEMA_ORDER = [
    "auth",          # 1  — users, roles, permissions (no deps)
    "core",          # 2  — audit_log, notes, attachments
    "imports",       # 3  — import_sessions, import_actions
    "workforce",     # 4  — employees, certifications, history
    "projects",      # 5  — customers, projects, budgets, jobs
    "quality",       # 6  — issues, CAs (FK: projects)
    "timetracker",   # 7  — transactions, projections (FK: projects)
    "qualitydocs",   # 8  — QM modules, procedures, forms
    "references",    # 9  — standards, clauses, procedure links
    "welding",       # 10 — WPS/PQR/WPQ/BPS/BPQ (FK: workforce)
    "pipeline",      # 11 — sheets, specs, disciplines (FK: projects)
    "engineering",   # 12 — calculations, validations
    "automation",    # 13 — processing log
    "blog",          # 14 — posts (FK: auth.users)
]
```

### Table Counts by Module

| Module | Tables | Key Entities |
|--------|--------|-------------|
| auth | 3 | users, user_module_access, user_business_units |
| core | 3 | audit_log, notes, attachments |
| imports | 2 | import_sessions, import_actions |
| workforce | 9 | employees, departments, roles, permissions, certifications, history |
| projects | 11 | customers, facilities, contacts, business_units, projects, jobs, budgets, allocations, codes, patterns, flags |
| quality | 8 | root_causes, tags, quality_issues, attachments, history, links, tags_junction, corrective_actions |
| timetracker | 7 | transactions, budget_settings, periods, snapshots, entries, period_jobs, entry_details |
| qualitydocs | 15 | modules, sections, subsections, content_blocks, cross_refs, code_refs, responsibilities, FTS, procedures, forms, records, templates, history, intake_log |
| references | 8 | standards, clauses, content_blocks, sections, procedure_links, extraction_log, FTS (×2) |
| welding | 54 | welder_registry, WPS (11), PQR (14), WPQ (3), BPS (8), BPQ (1), BPQR (3), continuity (4), production (1), NDT (1), notifications (2), cert_requests (2), preapproved (1), lookups (8+), extraction (2) |
| pipeline | 130+ | sheets, disciplines, lines, equipment, instruments, welds, conflicts, specs (6), extraction QA (10+), electrical (18), plumbing (5), mechanical (3), refrigeration (2), supports (3), fire protection (6), life safety (4), environmental (2), civil (22), general (7), intake_log (2) |
| engineering | 2 | eng_calculations, eng_validations |
| automation | 1 | automation_processing_log |
| blog | 1 | blog_posts |

See [Appendix B](#appendix-b-complete-database-schema) for complete schema definitions.

---

## 8. Module Specifications

### 8.1 Authentication

**Purpose:** Local email + password authentication with session management.

**Schema:** 3 tables (`users`, `user_module_access`, `user_business_units`)

**Key Features:**
- Password hashing via Werkzeug PBKDF2
- Rate limiting per IP + email on login attempts
- Force password change on first login (`must_change_password`)
- Employee linking (optional FK to workforce)
- Session persists across server restarts (file-backed secret key)

**Web Routes:**

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| GET/POST | `/auth/login` | Public | Login form + handler |
| GET | `/auth/logout` | Authenticated | Clear session |
| GET | `/auth/me` | Authenticated | Current user JSON |
| GET/POST | `/auth/change-password` | Authenticated | Password change form |
| GET | `/auth/users` | Admin | List all users with modules |
| POST | `/auth/users/create` | Admin | Create user |
| POST | `/auth/users/<id>/role` | Admin | Change global role |
| POST | `/auth/users/<id>/active` | Admin | Toggle active status |
| POST | `/auth/users/<id>/reset-password` | Admin | Reset password (forces change) |
| GET/POST | `/auth/users/<id>/modules` | Admin | Get/grant module access |
| DELETE | `/auth/users/<id>/modules/<mod>` | Admin | Revoke module access |
| GET/POST | `/auth/users/<id>/business-units` | Admin | Get/set BU access |
| GET | `/auth/api/employees` | Admin | Employee list for linking |
| POST | `/auth/users/<id>/employee` | Admin | Link/unlink employee |

**CLI Commands:**

```
qms auth create-user          # Interactive user creation
qms auth reset-password       # Reset user password
qms auth grant-access         # Grant module access
qms auth revoke-access        # Revoke module access
qms auth list-users           # List all accounts
```

---

### 8.2 Projects & Budgets

**Purpose:** Project hierarchy, customer/facility relationships, 3-tier budget model, job tracking, and Procore integration.

**Schema:** 11 tables

**Data Model:**

```
customers (1) → facilities (many) → projects (many)
                                        ↓
                                   project_budgets (1:1)
                                        ↓
                                   project_allocations (many)
                                     ↓ (per BU + subjob)
                                   jobs (many)
```

**Business Rules:**
- Project numbers are unique identifiers (e.g., "07645")
- Projects have stages: Archive, Bidding, Construction and Bidding, Course of Construction, Lost Proposal, Post-Construction, Pre-Construction, Proposal, Warranty
- `business_units` table is shared across modules (projects, welding, pipeline)
- BU codes are 3-digit strings (e.g., "600" = Refrigeration)
- Allocations track per-BU budget within a project
- GMP (Guaranteed Maximum Price) flag affects weight multiplier in projections
- Procore CSV import auto-groups subjobs by 5-digit base project number

**Web Routes:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects/` | Dashboard with stats |
| GET | `/projects/manage` | Projects table/form |
| GET | `/projects/<number>` | Single project hub |
| GET/POST | `/projects/api/projects` | List/create projects |
| PUT/DELETE | `/projects/api/projects/<id>` | Update/delete project |
| GET/POST | `/projects/api/projects/<id>/allocations` | Allocation CRUD |
| GET | `/projects/api/projects/hierarchical` | Tree view (project → allocations) |
| PATCH | `/projects/api/allocations/<id>/weight` | Set allocation weight (0-2) |
| PATCH | `/projects/api/allocations/<id>/projection` | Toggle projection enabled |
| PATCH | `/projects/api/allocations/<id>/gmp` | Toggle GMP flag |
| PATCH | `/projects/api/allocations/bulk` | Bulk operations |
| GET/POST | `/projects/api/business-units` | BU CRUD |
| GET | `/projects/api/projects/template` | XLSX template download |
| POST | `/projects/api/projects/import` | XLSX import |
| POST | `/projects/api/projects/import-procore` | Procore CSV import |

**CLI:**

```
qms projects list [--stage "Course of Construction"]
qms projects summary <project_number>
qms projects scan [project_number]
qms projects import-procore "export.csv"
```

---

### 8.3 Time Tracker & Projections

**Purpose:** Project spending ledger with monthly hour forecasting, snapshot versioning, and UKG payroll export.

**Schema:** 7 tables

**Concepts:**

| Concept | Description |
|---------|-------------|
| **Transaction** | Cost entry: Time, Travel, Materials, or Other. Has amount, hours, rate. |
| **Projection Period** | A month (year + month). Can be locked to prevent edits. |
| **Snapshot** | A versioned forecast within a period. Status: Draft → Committed → Superseded. |
| **Entry** | Per-project allocation within a snapshot (hours, cost). |
| **Period Jobs** | Controls which allocations are included in a period's calculations. |
| **Budget Settings** | Singleton config: hourly rate ($150 default), working hours/month (176), fiscal year start, GMP multiplier (1.5×). |

**Snapshot Lifecycle:**
1. Create period (year/month)
2. Toggle jobs included/excluded
3. Calculate projections (distributes hours by weight)
4. Create snapshot (version 1)
5. Optionally commit snapshot
6. Create new snapshot (version 2) if adjustments needed
7. Finalize when period closes

**Web Routes:** Admin-only module (404 for non-admins)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/timetracker/transactions` | Transaction ledger page |
| GET | `/timetracker/projections` | Projections management page |
| GET/POST | `/timetracker/api/transactions` | Transaction CRUD |
| GET/POST | `/timetracker/api/projection-periods` | Period management |
| PUT | `/timetracker/api/projection-periods/<id>/lock` | Toggle lock |
| POST | `/timetracker/api/projections/calculate` | Run calculation |
| GET/POST | `/timetracker/api/projections/<id>` | Snapshot CRUD |
| PUT | `/timetracker/api/projections/snapshot/<id>/activate` | Activate snapshot |
| PUT | `/timetracker/api/projections/snapshot/<id>/commit` | Commit snapshot |
| PUT | `/timetracker/api/projections/snapshot/<id>/finalize` | Finalize snapshot |
| GET | `/timetracker/api/timecard/<period_id>` | UKG timecard export |
| GET | `/timetracker/api/timecard?start_date=...&end_date=...` | Date range export |

---

### 8.4 Welding Program (ASME IX)

**Purpose:** Complete ASME Section IX / AWS D1.1 welding program management — document tracking, welder certification, qualification derivation, continuity monitoring, and production weld recording.

**Schema:** 54 tables

This is the largest and most complex module. It manages the full lifecycle of welding qualifications.

#### Document Types

| Document | Full Name | Purpose | Tables |
|----------|-----------|---------|--------|
| **WPS** | Welding Procedure Specification | Defines how to weld a joint | 11 (main + processes, joints, base metals, filler metals, positions, preheat, PWHT, gas, electrical, technique, PQR links) |
| **PQR** | Procedure Qualification Record | Proves a WPS works (test results) | 14 (main + joints, base metals, filler metals, positions, preheat, PWHT, gas, electrical, personnel, tensile tests, bend tests, toughness tests, other tests) |
| **WPQ** | Welder Performance Qualification | Proves a welder can follow a WPS | 3 (main + tests + per-code qualifications) |
| **BPS** | Brazing Procedure Specification | Defines brazing procedure | 8 (main + joints, base metals, filler metals, flux/atmosphere, positions, PBHT, technique) |
| **BPQ** | Brazing Performance Qualification | Proves brazing performance | 1 |
| **BPQR** | Brazer Performance Qualification Record | Records brazer test results | 3 (main + tests + per-code qualifications) |

#### Welder Registry

Central `weld_welder_registry` table with:
- Unique `welder_stamp` (assigned at registration)
- Employee linkage (FK to employees table)
- Running totals: welds performed, tested, passed, failed
- Status tracking: active, inactive, terminated, archived
- BU assignment for department tracking

#### Qualification Derivation Engine

The qualification engine derives what a welder is allowed to weld based on their test coupon:

```
Test Coupon (single test) → Derived Qualified Ranges (per code)
  - P-numbers qualified (e.g., "P1 thru P11 & P4X")
  - F-numbers qualified (e.g., "F4, F3, F2 & F1")
  - Thickness range (min/max)
  - Diameter range (min/max)
  - Positions qualified (groove + fillet)
  - Deposit thickness max
```

This derivation follows ASME IX rules and is stored per-code in `weld_wpq_qualifications` and `weld_bpqr_qualifications`.

#### Continuity Tracking

ASME IX requires welders to use each process within defined intervals or lose qualification:

| Table | Purpose |
|-------|---------|
| `weld_continuity_events` | Weekly activity log per welder/process |
| `weld_continuity_event_processes` | Process types per event with WPQ linkage |
| `weld_continuity_log` | Detailed continuity history |
| `weld_production_welds` | Production weld records that count for continuity |

Status levels: OK → AT_RISK → LAPSED

#### Certification Request Workflow (WCR)

```
WCR Created (status: pending_approval)
  → Coupons specified (process, position, WPS, materials)
  → Admin approves (status: approved)
  → Welder tests coupons
  → Results recorded (visual, bend, RT)
  → Pass → WPQ created, ranges derived
  → Fail → Retest WCR created
```

#### Notification System

| Table | Purpose |
|-------|---------|
| `weld_notification_rules` | Configurable triggers (e.g., "30 days before expiration") |
| `weld_notifications` | Generated alerts with acknowledgement tracking |

#### Lookup Tables (ASME IX Reference Data)

8+ tables of standardized codes:
- `weld_valid_processes` — GTAW, GMAW, SMAW, SAW, FCAW, etc.
- `weld_valid_p_numbers` — P-number groups with material types
- `weld_valid_f_numbers` — Filler metal groups
- `weld_valid_a_numbers` — Alloy groups
- `weld_valid_positions` — 1G, 2G, 3G, 4G, 1F, 2F, etc.
- `weld_valid_sfa_specs` — SFA welding standards
- `weld_valid_aws_classes` — Electrode classifications
- `weld_valid_current_types` — AC, DCEP, DCEN

#### PDF Extraction

Dual-model extraction pipeline:
1. **Primary extraction** (Sonnet) — Parse PDF form fields
2. **Secondary extraction** (Sonnet) — Independent verification
3. **Shadow review** (Opus) — 10% sample QA
4. Confidence scoring (0-1) on all fields
5. Disagreements logged in `weld_extraction_log`

#### Web Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/welding/` | Dashboard with stats, expirations |
| GET | `/welding/forms` | All forms list (tabbed by type) |
| GET | `/welding/welders` | Welder table |
| GET | `/welding/welder/<stamp>` | Welder profile with history |
| GET | `/welding/wps/<id>`, `/pqr/<id>`, `/wpq/<id>`, `/bpqr/<id>` | Form detail pages |
| GET | `/welding/cert-requests` | WCR list |
| GET | `/welding/cert-request/new` | New WCR form |
| GET | `/welding/api/lookup/materials` | Material lookup |
| GET | `/welding/api/lookup/processes` | Process lookup (filtered) |
| GET | `/welding/api/lookup/wps` | WPS lookup (filtered) |
| GET | `/welding/api/lookup/positions` | Position codes |
| GET | `/welding/api/lookup/preapproved-coupons` | Pre-approved configs |
| GET | `/welding/api/welders/search?q=...` | Welder search (≥2 chars) |
| POST | `/welding/api/cert-requests` | Create WCR |
| GET/POST/PUT | `/welding/api/forms/<type>[/<id>]` | Form CRUD |
| POST | `/welding/api/derive` | Live derivation (no save) |
| POST | `/welding/api/derive/<type>/<id>` | Derive + save |
| PATCH | `/welding/api/welders/<stamp>/status` | Update welder status |

**CLI:** 18 commands including `extract`, `generate`, `derive-ranges`, `cert-requests`, `continuity`, `seed-lookups`

---

### 8.5 Workforce Management

**Purpose:** Employee/subcontractor registry with organizational hierarchy, certifications, and import infrastructure.

**Schema:** 9 tables

**Key Design Decisions:**
- UUID primary keys on employees (not autoincrement)
- Auto-incrementing employee numbers ("1", "2", "3"...)
- Auto-incrementing subcontractor numbers ("SUB-0001", "SUB-0002"...)
- Self-referential supervisor FK (`supervisor_id → employees.id`)
- `is_employee` and `is_subcontractor` flags (CHECK: at least one true)

**4-Level Duplicate Detection:**

When importing employees (CSV, Excel, or SIS data), matching cascades through:
1. **Employee number** — exact match
2. **Phone** — digit-normalized (strips formatting)
3. **Name** — case-insensitive exact match (single match = flag for review, multiple = flag)
4. **Email** — case-insensitive match

**Action Types:** insert, update, skip, flag (needs review), separate (not in roster), reactivate (previously terminated)

**Web Routes:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/workforce/` | Employee table with stats |
| GET | `/workforce/import` | 4-step import wizard (editor+ required) |
| POST | `/workforce/api/import/upload` | File upload + auto-mapping |
| POST | `/workforce/api/import/<sid>/plan` | Generate action plan |
| POST | `/workforce/api/import/<sid>/execute` | Execute approved actions |
| GET | `/workforce/api/employees` | List with filters |
| POST | `/workforce/api/employees` | Create employee |
| PUT | `/workforce/api/employees/<id>` | Update employee |
| PATCH | `/workforce/api/employees/<id>/supervisor` | Set supervisor |
| PATCH | `/workforce/api/employees/<id>/status` | Set status |
| PATCH | `/workforce/api/employees/bulk` | Bulk operations |

---

### 8.6 Quality Intelligence

**Purpose:** Unified quality issue tracking across all issue types (observations, NCRs, CARs, deficiencies, punch items) with root cause analysis, corrective actions, and audit trails.

**Schema:** 8 tables

**Issue Types:** `observation`, `ncr`, `car`, `deficiency`, `punch`, `other`

**Issue Lifecycle:**

```
open → in_review → in_progress → resolved → closed
                                     ↓
                                  deferred
```

**Corrective Actions (CAPA):** Each issue can have multiple actions:
- Types: `corrective`, `preventive`, `containment`
- Lifecycle: `open → in_progress → completed → verified → ineffective`
- Verification tracking with `verified_by`, `verified_at`, `effectiveness_notes`

**Root Cause Taxonomy:** Seeded categories: Workmanship, Materials, Design/Engineering, Environmental, Procedural, Subcontractor, Equipment/Tools, Other

**External Sources:**
- `source` field tracks origin: `manual`, `procore`, `mobile`, `import`
- `source_id` + `source_project_id` enable deduplication on re-import
- `source_url` links back to external system
- Procore CSV batch import with normalization (trade names, statuses, types)

**Search:**
- Primary: Vector search via ChromaDB (if available)
- Fallback: SQL LIKE on title/description
- All results filtered by user BU access

**Web Routes:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/quality/` | Dashboard with stats, charts, recent issues |
| GET | `/quality/browse` | Issue browser with filters |
| GET | `/quality/api/stats` | Summary counts (BU-filtered) |
| GET | `/quality/api/issues?type=&status=&severity=` | Filtered issue list |
| GET | `/quality/api/by-type` | Aggregation by type |
| GET | `/quality/api/by-status` | Aggregation by status |
| GET | `/quality/api/by-trade` | Aggregation by trade |
| GET | `/quality/api/search?q=...` | Vector + SQL search |

---

### 8.7 Document Pipeline & Intake

**Purpose:** Automatic document classification, routing from unified inbox, engineering drawing extraction across 11 disciplines, revision tracking, and cross-discipline conflict detection.

**Schema:** 130+ tables (largest module)

#### Unified Inbox

All documents enter through `data/inbox/`. The classifier reads `config.yaml` `document_types:` section and:
1. Matches filename against regex patterns (first match wins)
2. Resolves destination template variables ({project}, {discipline}, {set})
3. Routes to project/module-specific locations
4. Unresolvable files go to `NEEDS-REVIEW/`

**15+ Document Types:**
- Drawings (P-101, M-201, E-301...) → project discipline folders
- Specifications (242300-Refrigeration...) → project spec folders
- QM Documents (SP-, WI-, FM-, TP-, PL-, RC-) → quality-documents
- Welding forms (WPS-, PQR-, WPQ-, BPS-, BPQ-) → welding subfolders
- Procore exports, observation CSVs, production weld logs

#### Drawing Extraction

11 supported disciplines with discipline-specific extractors:

| Discipline | Extracted Entities |
|------------|-------------------|
| Electrical | Transformers, switchgear, motors, panels, circuits, breakers, fixtures, receptacles, conduit, disconnects |
| Plumbing | Fixtures, risers, locations, pipes, cleanouts |
| Mechanical | Equipment, ventilation systems, air flow paths |
| Refrigeration | Pipe stands, duct stands, piping lines |
| Fire Protection | Zones, equipment, systems, piping, valves |
| Life Safety | Exits, egress paths, occupancy, fire barriers |
| Civil | Demolition, erosion control, grading, drainage, utilities, survey data |
| General | Details, notes, abbreviations, design criteria |
| Structural | Support details, tags |
| Utility | Equipment (pumps, compressors, generators) |
| Environmental | Zones, finish notes |

Each extraction produces:
- **Lines** — pipe/duct runs with size, material, spec class
- **Equipment** — tagged items with type and description
- **Instruments** — control devices with loop numbers
- **Welds** — weld callouts with type, size, NDE requirements
- Confidence scores (0-1) on all items

#### Specification Extraction

Specifications (CSI format) are parsed into:
- `specifications` — document metadata
- `spec_sections` — section breakdown
- `spec_items` — individual line items (material, grade, schedule, rating)
- `master_spec_items` — cross-project standardized catalog
- `spec_variations` — deviations from standard

#### Quality Assurance

| Mechanism | Description |
|-----------|-------------|
| **Shadow review** | 10% of extractions reviewed by Opus model |
| **Gold standard** | Human-verified ground truth for accuracy benchmarking |
| **Accuracy log** | Model performance tracked per drawing type + period |
| **Extraction flags** | Issues flagged during extraction with severity |
| **Revision deltas** | Change tracking between drawing revisions |

#### Web Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pipeline/` | Intake dashboard |
| GET | `/pipeline/api/inbox` | Classified inbox contents |
| POST | `/pipeline/api/intake` | Process inbox (with dry_run option) |
| POST | `/pipeline/api/classify` | Classify single file (preview) |
| GET | `/pipeline/api/intake-log` | Recent intake history |

**CLI:** `status`, `queue`, `import-drawing`, `import-batch`, `process`, `intake`

---

### 8.8 Engineering Calculations

**Purpose:** Refrigeration engineering calculations with audit trail and drawing validation.

**Schema:** 2 tables (`eng_calculations`, `eng_validations`)

**Calculation Types:**

| Type | Purpose | Key Inputs |
|------|---------|-----------|
| `line-sizing` | Pipe size selection | Capacity (tons), temperatures, length, line type, refrigerant |
| `relief-valve` | Safety valve sizing | Volume, set pressure, refrigerant |
| `pump` | Pump capacity | Capacity, recirculation rate |
| `ventilation` | Room ventilation | Room dimensions |
| `charge` | Refrigerant charge | Volume, temperature |

**Validation:** Compares extracted drawing values against calculated values with configurable tolerance. Status: PASS, FAIL, WARNING, REVIEW.

**CLI:** 8 commands (`history`, `line-sizing`, `relief-valve`, `pump`, `ventilation`, `charge`, `validate-pipes`, `validate-relief`)

---

### 8.9 Quality Documents (QM CMS)

**Purpose:** Quality manual content management with XML ingestion, structured storage, full-text search, cross-reference tracking, and PDF export.

**Schema:** 15 tables

**Content Hierarchy:**

```
QM Module (e.g., "Module 2: Quality Program")
  → Sections (numbered, ordered)
    → Subsections (lettered: A, B, C...)
      → Content Blocks (paragraphs, lists, tables, notes)
```

**Subsection Types:** PurposeAndScope, Requirements, Procedures, Responsibilities, Documentation, VerificationAndCompliance, General

**Block Types:** HeadingParagraph, Paragraph, SubHeading, BulletList, NumberedList, Table, Note, ResponsibilityBlock

**Cross-Reference Tracking:**
- Internal refs (Module → Module)
- External refs (to standards like ASME B16.5)
- Code references with organization tracking
- Detection methods: explicit markup, prose detection

**FTS5 Search:** Virtual table `qm_content_fts` with porter unicode61 tokenizer, searching across module number, section, subsection, content.

**Document Management:**
- Procedures (SP-), Work Instructions (WI-), Policies (PL-), Forms (FM-), Templates (TP-), Records (RC-)
- Revision tracking with history
- File hash verification
- Retention management (default 7 years)

**CLI:** `load-module`, `summary`, `search`, `detail`

---

### 8.10 Reference Standards Library

**Purpose:** Extract, store, and search engineering standards (ASME, AWS, ISO, etc.) at clause-level granularity.

**Schema:** 8 tables

**Parallel Extraction Pipeline:**
For large standards (>50 pages):
1. **Split** (Haiku) — Parse TOC, split PDF into sections with `qpdf`
2. **Extract** (Sonnet) — Process each section in parallel (4 concurrent)
3. **Merge** (Sonnet) — Resolve overlapping boundary clauses
4. **Validate** (Opus) — Verify completeness (95% threshold) and accuracy (90% threshold, 10% sample)

**Content Structure:**
- `ref_clauses` — Hierarchical clause tree with parent_clause_id
- `ref_content_blocks` — 14 block types (Heading, Paragraph, Note, Warning, Caution, Table, Figure, Equation, Requirement, etc.)
- `ref_procedure_links` — Maps clauses to internal QM procedures (IMPLEMENTS, REFERENCES, PARTIAL, EXCLUDES)

**FTS5 Search:** Two virtual tables — one for clause metadata, one for content blocks.

**CLI:** `extract`, `list`, `search`, `clauses`

---

### 8.11 Vector Search

**Purpose:** Semantic search across all QMS content types using ChromaDB embeddings.

**Collections:**
- QM content (modules, sections, subsections)
- Reference clauses
- Specifications
- Drawing metadata and extracted items
- Quality issues

**Configuration:**
- Provider: auto-detect (OpenAI-compatible API or local HuggingFace)
- Model: nomic-embed-text-v1.5 (768 dimensions)
- Batch size: 32

**CLI:** `index [all|qm|refs|specs|drawings] [--rebuild]`, `search`, `status`, `queue`

---

### 8.12 Automation

**Purpose:** Power Automate webhook integration for processing incoming requests.

**Schema:** 1 table (`automation_processing_log`)

**Web Routes:**
- `/automation/preview` — Adaptive Card preview with template selector
- `/automation/api/jobs` — Jobs lookup for card population
- `/automation/api/employees` — Employee lookup
- `/automation/api/wps` — WPS lookup
- `/automation/api/card/<name>` — Card template retrieval

**CLI:** `process`, `status`

---

### 8.13 The Observatory (Blog)

**Purpose:** Internal knowledge-sharing platform with scheduled publishing.

**Schema:** 1 table (`blog_posts`)

**Three States:**
1. **Draft** — `published=0`, `publish_at=NULL` (manual publish only)
2. **Scheduled** — `published=0`, `publish_at='2026-03-15T14:30:00'` (auto-publishes)
3. **Published** — `published=1` (live)

**Auto-Publish Mechanism:** Lazy evaluation — `_auto_publish_scheduled()` runs inside `list_posts()`, checking for scheduled posts whose `publish_at` has passed and setting `published=1`.

**Content Format:** Markdown stored in `content_md`, rendered to `content_html` on save.

**Web Routes:**
- `/blog/` — Public post list (triggers auto-publish)
- `/blog/<slug>` — Post detail (404 for unpublished unless admin)
- `/blog/api/posts` — Admin CRUD API
- Settings UI → Observatory tab with datetime-local picker

**No CLI** — web-only module.

---

### 8.14 Reporting

**Purpose:** System-wide analytics.

**CLI:** `qms report system`

---

### 8.15 Settings & Administration

**Purpose:** Centralized configuration UI with 9+ tabs.

**Settings Tabs:**
1. **General** — Company name, app name, tagline
2. **Projects** — Project-specific config
3. **Welding** — WPS/WPQ settings
4. **Pipeline** — Document classifier config
5. **Extraction** — Form extraction thresholds
6. **Branding** — 9 color pickers, font selection, logos
7. **Integrations** — Procore, OneDrive, external APIs
8. **Business Units** — BU CRUD with department/job hierarchy
9. **Users & Access** — Full user management (create, role, active toggle, reset password, module access, BU access)
10. **The Observatory** — Blog post editor

**Admin System Map** (`/admin/system-map`):
- Hidden route (404 for non-admins)
- Access via "sys v0.1.0" link at settings page bottom (opacity: 0.4)
- Shows: roadmap from `.planning/roadmap.json`, DB stats, activity feed, extraction coverage, user list, disk health

**Config API:**
- `GET/PUT /settings/api/config/<section>` — Read/write config sections
- Only whitelisted sections editable: branding, intake, processing, onedrive_sync, welding.cert_requests, extraction.thresholds, conflicts.checks, embeddings

---

## 9. Frontend & Theming

### Template Architecture

All 35 templates extend `base.html`, which provides:
- **Top bar** (52px, fixed) — Brand + module tabs + settings + dark toggle + user menu
- **Sub-navigation** (42px, fixed) — Module-specific links
- **Main content area** — 94px top margin, max-width 1400px container

**Template Blocks:**
```jinja2
{% extends "base.html" %}
{% block title %}Page Title{% endblock %}
{% block content %}...{% endblock %}
```

### Navigation

Module tabs auto-generated from `web_modules` config:
- Each module gets a tab with SVG icon
- Active tab has bottom border (primary color) + background highlight
- `admin_only` modules hidden from non-admin navigation
- Sub-nav links vary per module (configured in base.html)

### Theming System

**CSS Architecture (3,586 lines, no preprocessor):**
- `style.css` (3,296 lines) — Design tokens, components, layouts
- `dark.css` (246 lines) — Dark mode overrides via `[data-theme="dark"]`
- `brand-fonts.css` (44 lines) — @font-face declarations with local font detection

**Design Tokens:**
```css
:root {
    --font-heading: 'Outfit', -apple-system, sans-serif;
    --font-body: 'DM Sans', -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
    --color-bg: #f1f3f8;
    --color-surface: #ffffff;
    --color-text: #1a1f2e;
    --color-primary: #2563eb;        /* Overridden by branding config */
    --color-success: #0d9668;
    --color-warning: #d97706;
    --color-danger: #dc2626;
    --shadow-sm/md/lg/xl: ...;
    --radius-sm/md/lg: 6/8/12px;
    --ease: cubic-bezier(0.4, 0, 0.2, 1);
}
```

**Brand Override Cascade (order critical):**
```html
<link rel="stylesheet" href="style.css">           <!-- 1. Base styles -->
<style>:root { --color-primary: {{ theme... }}; }</style>  <!-- 2. Brand overrides -->
<link rel="stylesheet" href="dark.css">            <!-- 3. Dark mode (uses vars) -->
```

**Dark Mode Persistence:**
- Toggle writes to `localStorage('qms-theme-mode')`
- Anti-FOUC script in `<head>` reads storage before DOM paint
- Sets `data-theme="dark"` on `<html>` element

**Config-Driven Branding:**
```yaml
branding:
  app_name: "SIS QMS"
  preset: "stellar"
  colors:
    primary: "#A41F35"         # Stellar red
    nav_bg: "#064975"          # Navy blue
    warning: "#FFA400"         # Orange
  fonts:
    heading: "Alternate Gothic ATF"
    heading_fallback: "Barlow Condensed"  # Google Fonts
    body: "Franklin Gothic URW"
    body_fallback: "Source Sans 3"        # Google Fonts
```

### Static Assets

| File | Description |
|------|-------------|
| `favicon.ico` | Multi-size ICO from SIS-QMS.png |
| `mascot.svg` | Navigator Penguin (home page hero) |
| `branding/SIS-QMS.png` | QMS logo (131K) |
| `branding/Stellar.png` | Company logo (17K) |
| `branding/Inspector Orion.png` | Mascot character (2.0M) |
| `branding/Stellar_40th_*.png` | Anniversary logos (2 variants) |
| `branding/*.pdf` | Brand Standards Guide |

---

## 10. CLI System

### Architecture

Entry point: `qms` command via Typer framework.

**Dynamic Module Registration:**
```python
module_registry = [
    ("qms.welding.cli",     "welding",     "Welding program management"),
    ("qms.workforce.cli",   "workforce",   "Employee & workforce management"),
    ("qms.projects.cli",    "projects",    "Projects, customers & jobs"),
    # ... 13 modules total
]

for module_path, name, help_text in module_registry:
    try:
        mod = importlib.import_module(module_path)
        app.add_typer(mod.app, name=name, help=help_text)
    except (ImportError, AttributeError):
        pass  # Silently skip missing modules
```

### Core Commands

| Command | Description |
|---------|-------------|
| `qms version` | Show version and module status |
| `qms migrate` | Run all database migrations (14 schemas) |
| `qms serve [--port 5000] [--host 0.0.0.0] [--debug] [--threads 8]` | Launch web server |

### Module Commands (65+ total)

| Group | Commands |
|-------|---------|
| `qms eng` | history, line-sizing, relief-valve, pump, ventilation, charge, validate-pipes, validate-relief |
| `qms welding` | dashboard, continuity, import-wps, import-weekly, check-notifications, register, export-lookups, cert-requests, cert-results, approve-wcr, assign-wpq, schedule-retest, process-requests, seed-lookups, extract, generate, register-template, derive-ranges |
| `qms projects` | scan, list, summary, import-procore |
| `qms timetracker` | export-timecard, migrate-timetracker |
| `qms pipeline` | status, queue, import-drawing, import-batch, process, intake |
| `qms workforce` | list, import-csv, import-from-sis, bulk-update |
| `qms docs` | load-module, summary, search, detail |
| `qms refs` | extract, list, search, clauses |
| `qms vectordb` | index, search, status, queue |
| `qms auth` | create-user, reset-password, grant-access, revoke-access, list-users |
| `qms automation` | process, status |
| `qms report` | system |
| `qms quality` | (varies) |

---

## 11. Import Infrastructure

### Shared Engine (`imports/` package)

All CSV/Excel imports share a common engine with module-specific callbacks.

**Data Models:**

| Model | Purpose |
|-------|---------|
| `ColumnDef` | Column definition with name, label, type, required flag, aliases, FK config |
| `ActionItem` | Per-row action: type, data, existing match, changes, approval status |
| `ActionPlan` | Collection of items with summary and categorization |
| `ImportSpec` | Module-provided spec with callbacks (match_fn, categorize_fn, detect_missing_fn, execute_fn) |

**Column Types:** text, int, float, date, bool, fk_lookup (auto-resolves FK display value to ID)

**4-Step Wizard Flow:**

1. **Upload** — Parse CSV/XLSX, create session, auto-map columns by header matching
2. **Map** — User adjusts column mapping, validates required fields
3. **Review** — Engine generates action plan (insert/update/skip/flag/separate/reactivate)
4. **Execute** — User approves/rejects categories, engine executes via spec callbacks

**Session Tracking:** `import_sessions` table tracks status (mapping → review → executing → completed/cancelled/error). `import_actions` table stores per-row plan with JSON data.

**File Cache:** In-memory dict keyed by session_id, cleared on execute/cancel (prevents re-parsing).

---

## 12. AI Model Integration

### Model Routing

Three tiers defined in config.yaml:

| Tier | Model | Tasks |
|------|-------|-------|
| **Simple** | Haiku | Title block reading, file routing, pattern matching, simple table extraction |
| **Complex** | Sonnet | Full extraction, conflict detection, cross-discipline checks, revision comparison, report generation |
| **Critical** | Opus | Shadow review, calibration, critical conflict resolution, quality validation, ambiguous routing |

### Extraction QA Pipeline

```
PDF → Primary Extraction (Sonnet) → Items + Confidence Scores
                                        ↓
                              [10% sample] → Shadow Review (Opus)
                                        ↓
                              Accuracy Log → Model Performance Metrics
                                        ↓
                              Gold Standard comparison (if available)
```

**Quality Gates:**
- `minimum_confidence: 0.6` — Reject items below this
- `high_confidence: 0.9` — Flag as high-quality
- `shadow_review_rate: 0.10` — 10% of extractions reviewed by Opus
- `numeric_tolerance: 0.05` — 5% tolerance on numeric field comparison

---

## 13. External Integrations

### Procore

**Current:** CSV import from "Company Home" export → creates projects + jobs
**Planned:** Quality observation export (QMS site visits → Procore observation pages)
**Config:** `procore:` section with base_url + per-project ID mappings

### UKG Payroll

Timecard export from projection periods, respecting UKG pay period boundaries.

### OneDrive

Optional sync from OneDrive folder to `data/inbox/` with configurable source root and delete-after-sync.

### Power Automate

Adaptive Card webhook integration for request processing. Card templates served via API.

---

## 14. Testing Requirements

### Test Infrastructure

- **Framework:** pytest with pytest-cov
- **Tests:** 534+ across 29 test modules
- **Exclusion:** vectordb tests excluded (torchvision crash on Windows)

### Fixture Pattern

```python
memory_db          # Fresh in-memory SQLite with all 14 schemas loaded
mock_db            # Patches all get_db() calls to use memory_db (14 patch locations)
cli_runner         # Typer CLI test runner
seed_project       # Minimal project for FK references
seed_sheet         # Drawing sheet linked to project
```

**Key property:** Each test gets an isolated database. No test pollution. All 14 schemas loaded in dependency order.

### Test Categories

| Category | Modules | Tests |
|----------|---------|-------|
| Core infrastructure | config, db, logging, output, paths | ~30 |
| Engineering | base, cli, db, output, properties, refrigeration, validators | ~60 |
| Welding | forms, extraction, derivation, continuity, cert requests | ~80 |
| Projects | budget, allocations, projections, timecard | ~60 |
| Workforce | employees, API, import | ~40 |
| Quality | issues, import, API | ~30 |
| Pipeline | classification, routing | ~20 |
| Integration | imports engine, automation, QR codes, CLI routing | ~40 |
| Other modules | qualitydocs, references, blog, auth | ~50+ |

### Coverage Target

`pytest --cov=qms --cov-report=term-missing` — all critical paths covered.

---

## 15. Deployment & Operations

### Server Modes

| Mode | Command | Host | Server | Use |
|------|---------|------|--------|-----|
| Production | `qms serve` | `0.0.0.0:5000` | Waitress (8 threads) | LAN access |
| Development | `qms serve --debug` | `127.0.0.1:5000` | Flask dev server | Auto-reload |

### LAN Configuration

- **Hostname:** `L004470-CAD` (Windows machine name)
- **URL:** `http://L004470-CAD:5000` (LAN-accessible)
- **Desktop shortcut:** `SIS QMS.url` (uses hostname, custom favicon)

### Installation

```bash
# Core (CLI + all modules)
pip install -e D:\qms

# With web UI
pip install -e "D:\qms[web]"

# With AI extraction
pip install -e "D:\qms[pipeline,welding]"

# Everything
pip install -e "D:\qms[web,pipeline,welding,export,dev]"
```

### Database Management

```bash
# Run all migrations (idempotent)
qms migrate

# Database is auto-created on first run
# WAL mode enabled automatically
# FK constraints enforced via PRAGMA
```

### File Structure (Runtime)

```
data/
├── quality.db          # Main database (263 tables)
├── .secret_key         # Session secret (auto-generated)
├── inbox/              # Document intake
│   ├── NEEDS-REVIEW/   # Unresolvable documents
│   ├── CONFLICTS/      # Detected conflicts
│   └── DUPLICATES/     # Duplicate documents
├── projects/           # Per-project drawing files
├── quality-documents/  # QM procedures, forms, references, welding
└── vectordb/           # ChromaDB embeddings
```

### Security Headers

Applied to all responses:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`

---

## Appendix A: Complete API Reference

### Auth (`/auth`)
| Method | Path | Access | Description |
|--------|------|--------|-------------|
| GET/POST | `/auth/login` | Public | Login |
| GET | `/auth/logout` | Auth | Logout |
| GET | `/auth/me` | Auth | Current user JSON |
| GET/POST | `/auth/change-password` | Auth | Password change |
| GET | `/auth/users` | Admin | List users |
| POST | `/auth/users/create` | Admin | Create user |
| POST | `/auth/users/<id>/role` | Admin | Set role |
| POST | `/auth/users/<id>/active` | Admin | Toggle active |
| POST | `/auth/users/<id>/reset-password` | Admin | Reset password |
| GET/POST | `/auth/users/<id>/modules` | Admin | Module access |
| DELETE | `/auth/users/<id>/modules/<mod>` | Admin | Revoke module |
| GET/POST | `/auth/users/<id>/business-units` | Admin | BU access |
| GET | `/auth/api/employees` | Admin | Employee list |
| POST | `/auth/users/<id>/employee` | Admin | Link employee |

### Projects (`/projects`)
| Method | Path | Access | Description |
|--------|------|--------|-------------|
| GET | `/projects/` | Module | Dashboard |
| GET | `/projects/manage` | Module | Projects page |
| GET | `/projects/<number>` | Module | Project detail |
| GET/POST | `/projects/api/projects` | Module | List/create |
| PUT/DELETE | `/projects/api/projects/<id>` | Module | Update/delete |
| GET/POST | `/projects/api/projects/<id>/allocations` | Module | Allocations |
| DELETE | `/projects/api/projects/<id>/allocations/<aid>` | Module | Delete allocation |
| GET | `/projects/api/projects/hierarchical` | Module | Tree view |
| PATCH | `/projects/api/allocations/<id>/weight` | Module | Set weight |
| PATCH | `/projects/api/allocations/<id>/projection` | Module | Toggle projection |
| PATCH | `/projects/api/allocations/<id>/gmp` | Module | Toggle GMP |
| PATCH | `/projects/api/allocations/<id>/budget` | Module | Set budget |
| PATCH | `/projects/api/allocations/<id>/stage` | Module | Set stage |
| PATCH | `/projects/api/allocations/bulk` | Module | Bulk operations |
| GET/POST | `/projects/api/business-units` | Module | BU CRUD |
| PUT/DELETE | `/projects/api/business-units/<id>` | Module | BU update/delete |
| GET | `/projects/api/projects/template` | Module | XLSX template |
| POST | `/projects/api/projects/import` | Module | XLSX import |
| POST | `/projects/api/projects/import-procore` | Module | Procore CSV |

### Time Tracker (`/timetracker`) — Admin Only
| Method | Path | Description |
|--------|------|-------------|
| GET | `/timetracker/transactions` | Transactions page |
| GET | `/timetracker/projections` | Projections page |
| GET/POST/PUT/DELETE | `/timetracker/api/transactions[/<id>]` | Transaction CRUD |
| GET/POST | `/timetracker/api/projection-periods` | Period management |
| GET | `/timetracker/api/projection-periods/<id>` | Get period |
| PUT | `/timetracker/api/projection-periods/<id>/lock` | Toggle lock |
| GET/PATCH | `/timetracker/api/projection-periods/<id>/jobs` | Period jobs |
| PATCH | `/timetracker/api/projection-periods/<id>/jobs/<aid>/toggle` | Toggle job |
| PATCH | `/timetracker/api/projection-periods/<id>/jobs/bulk-toggle` | Bulk toggle |
| POST | `/timetracker/api/projections/calculate` | Run calculation |
| GET/POST | `/timetracker/api/projections/<id>` | Snapshot CRUD |
| GET | `/timetracker/api/projections/period/<id>/snapshots` | List snapshots |
| GET | `/timetracker/api/projections/snapshot/<id>` | Get snapshot |
| PUT | `/timetracker/api/projections/snapshot/<id>/activate` | Activate |
| PUT | `/timetracker/api/projections/snapshot/<id>/commit` | Commit |
| PUT | `/timetracker/api/projections/snapshot/<id>/uncommit` | Uncommit |
| PUT | `/timetracker/api/projections/snapshot/<id>/finalize` | Finalize |
| GET | `/timetracker/api/projections/snapshot/<id>/distribute` | Distribute |
| GET | `/timetracker/api/projects/budget-summary` | Budget summary |
| GET | `/timetracker/api/timecard[/<period_id>]` | Timecard export |

### Welding (`/welding`)
| Method | Path | Access | Description |
|--------|------|--------|-------------|
| GET | `/welding/` | Module | Dashboard |
| GET | `/welding/forms` | Module | All forms |
| GET | `/welding/welders` | Module | Welder list |
| GET | `/welding/welder/<stamp>` | Module | Welder profile |
| GET | `/welding/wps/<id>` | Module | WPS detail |
| GET | `/welding/pqr/<id>` | Module | PQR detail |
| GET | `/welding/wpq/new`, `/welding/wpq/<id>` | Module | WPQ form |
| GET | `/welding/bpqr/new`, `/welding/bpqr/<id>` | Module | BPQR form |
| GET | `/welding/cert-requests` | Module | WCR list |
| GET | `/welding/cert-request/new` | Editor+ | New WCR form |
| GET | `/welding/api/lookup/materials` | Module | Material lookup |
| GET | `/welding/api/lookup/processes` | Module | Process lookup |
| GET | `/welding/api/lookup/wps` | Module | WPS lookup |
| GET | `/welding/api/lookup/positions` | Module | Position codes |
| GET | `/welding/api/lookup/preapproved-coupons` | Module | Preapproved configs |
| GET | `/welding/api/welders/search` | Module | Welder search |
| GET | `/welding/api/projects/search` | Module | Project search |
| GET | `/welding/api/welders/check-duplicate` | Module | Duplicate check |
| POST | `/welding/api/cert-requests` | Editor+ | Create WCR |
| GET/POST | `/welding/api/forms/<type>` | Module | Form list/create |
| GET/PUT | `/welding/api/forms/<type>/<id>` | Module | Form get/update |
| POST | `/welding/api/derive` | Module | Live derivation |
| POST | `/welding/api/derive/<type>/<id>` | Module | Derive + save |
| GET | `/welding/api/welders` | Module | Welder list API |
| GET | `/welding/api/welders/<stamp>` | Module | Welder detail API |
| PATCH | `/welding/api/welders/<stamp>/status` | Admin | Update status |

### Quality (`/quality`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/quality/` | Dashboard |
| GET | `/quality/browse` | Issue browser |
| GET | `/quality/api/stats` | Summary stats |
| GET | `/quality/api/issues` | Filtered issue list |
| GET | `/quality/api/by-type` | Aggregation by type |
| GET | `/quality/api/by-status` | Aggregation by status |
| GET | `/quality/api/by-trade` | Aggregation by trade |
| GET | `/quality/api/search` | Vector + SQL search |

### Workforce (`/workforce`)
| Method | Path | Access | Description |
|--------|------|--------|-------------|
| GET | `/workforce/` | Module | Employee page |
| GET | `/workforce/import` | Editor+ | Import wizard |
| POST | `/workforce/api/import/upload` | Editor+ | Upload file |
| POST | `/workforce/api/import/<sid>/plan` | Editor+ | Generate plan |
| POST | `/workforce/api/import/<sid>/execute` | Editor+ | Execute plan |
| GET | `/workforce/api/import/history` | Editor+ | Import history |
| POST | `/workforce/api/import/<sid>/cancel` | Editor+ | Cancel import |
| GET | `/workforce/api/employees` | Module | List employees |
| GET | `/workforce/api/employees/stats` | Module | Employee stats |
| GET | `/workforce/api/employees/managers` | Module | Potential managers |
| POST | `/workforce/api/employees` | Module | Create employee |
| PUT | `/workforce/api/employees/<id>` | Module | Update employee |
| PATCH | `/workforce/api/employees/<id>/supervisor` | Module | Set supervisor |
| PATCH | `/workforce/api/employees/<id>/status` | Module | Set status |
| PATCH | `/workforce/api/employees/<id>/role` | Module | Set role |
| PATCH | `/workforce/api/employees/bulk` | Module | Bulk operations |
| GET | `/workforce/api/roles` | Module | List roles |
| GET | `/workforce/api/departments` | Module | List departments |
| GET | `/workforce/api/jobs` | Module | List jobs |

### Pipeline (`/pipeline`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/pipeline/` | Intake dashboard |
| GET | `/pipeline/api/inbox` | Classified files |
| POST | `/pipeline/api/intake` | Process inbox |
| POST | `/pipeline/api/classify` | Classify single file |
| GET | `/pipeline/api/intake-log` | Intake history |

### Other Blueprints
| Blueprint | Key Routes |
|-----------|-----------|
| Blog (`/blog`) | `/blog/` (list), `/blog/<slug>` (detail), `/blog/api/posts` (CRUD) |
| Automation (`/automation`) | `/automation/preview`, `/automation/api/jobs`, `/automation/api/employees`, `/automation/api/wps`, `/automation/api/card/<name>` |
| QualityDocs (`/qualitydocs`) | `/qualitydocs/` (browser), `/qualitydocs/api/summary`, `/qualitydocs/api/module/<num>`, `/qualitydocs/api/section/<num>`, `/qualitydocs/api/export/<num>`, `/qualitydocs/api/search` |
| Settings (`/settings`) | `/settings/`, `/settings/api/budget` (GET/PUT), `/settings/api/config/<section>` (GET/PUT) |
| Root | `/` (dashboard), `/admin/system-map` (admin-only) |

### Error Response Format

```json
{
  "error": "Error message",
  "details": ["optional", "list", "of", "details"]
}
```

Status codes: 400 (validation), 403 (permission), 404 (not found), 409 (conflict), 500 (server error), 501 (not implemented)

---

## Appendix B: Complete Database Schema

### auth/schema.sql
```sql
-- users: Local authentication accounts
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT,
    role TEXT NOT NULL DEFAULT 'user',  -- admin | user | viewer
    is_active INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 1,
    employee_id INTEGER REFERENCES employees(id),
    first_login DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- user_module_access: Per-module role assignments
CREATE TABLE IF NOT EXISTS user_module_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    module TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',  -- admin | editor | viewer
    UNIQUE(user_id, module)
);

-- user_business_units: BU access restrictions (empty = unrestricted)
CREATE TABLE IF NOT EXISTS user_business_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    business_unit_id INTEGER NOT NULL REFERENCES business_units(id) ON DELETE CASCADE,
    UNIQUE(user_id, business_unit_id)
);
```

### Key Tables (Summary — Full schemas in module schema.sql files)

**projects:** `id, number(UNIQUE), name, client, status, stage, start_date, end_date, customer_id(FK), facility_id(FK), pm_employee_id(FK), is_gmp`

**employees:** `id(UUID), employee_number(UNIQUE), subcontractor_number(UNIQUE), last_name, first_name, is_employee, is_subcontractor, is_active, status, department_id(FK), job_id, supervisor_id(FK:self), role_id(FK), email, phone`

**quality_issues:** `id, type, title, description, project_id(FK), business_unit_id(FK), severity, priority, status, root_cause_id(FK), assigned_to(FK), source, source_id, metadata(JSON)`

**blog_posts:** `id, title, slug(UNIQUE), content_md, content_html, excerpt, author_id(FK), published, pinned, publish_at, created_at, updated_at`

**weld_welder_registry:** `id, welder_stamp(UNIQUE), employee_number, first_name, last_name, status, business_unit_id(FK), running_total_welds, welds_passed, welds_failed`

**weld_wpq:** `id, wpq_number(UNIQUE), revision, welder_id(FK), wps_id(FK), process_type, test_date, status, coupon_thickness, coupon_diameter, test_position, [qualified ranges], current_expiration_date`

**sheets:** `id, project_id(FK), drawing_number, revision, discipline, file_path, quality_score, is_current, supersedes(FK), superseded_by(FK)`

(Complete SQL definitions live in each module's `schema.sql` file)

---

## Appendix C: Config.yaml Reference

### Complete Section Inventory

```yaml
# ── Authentication ──────────────────────────────
auth:
  provider: "local"
  dev_bypass: false
  secret_key: null                    # Or QMS_SECRET_KEY env var
  session_lifetime_minutes: 480
  default_role: "admin"

# ── Branding & Theming ──────────────────────────
branding:
  app_name: "SIS QMS"
  app_tagline: "Quality Management System"
  preset: "stellar"                   # stellar | default | custom
  default_mode: "light"              # light | dark
  colors:
    primary: "#A41F35"
    primary_hover: "#8a1a2c"
    primary_subtle: "#f9eaec"
    nav_bg: "#064975"
    nav_hover: "#053d62"
    nav_active: "#A41F35"
    warning: "#FFA400"
    dark_surface: "#0C2340"
    light_surface: "#DBE2E9"
    neutral: "#77777A"
  fonts:
    heading: "Alternate Gothic ATF"
    heading_fallback: "Barlow Condensed"
    body: "Franklin Gothic URW"
    body_fallback: "Source Sans 3"
    google_fonts_url: "https://fonts.googleapis.com/css2?..."

# ── Module Registry ─────────────────────────────
web_modules:
  quality:
    label: "Quality"
    default_endpoint: "quality.dashboard"
  projects:
    label: "Projects"
    default_endpoint: "projects.dashboard"
  welding:
    label: "Welding"
    default_endpoint: "welding.dashboard"
  pipeline:
    label: "Pipeline"
    default_endpoint: "pipeline.intake_dashboard"
  automation:
    label: "Automation"
    default_endpoint: "automation.preview"
  workforce:
    label: "Workforce"
    default_endpoint: "workforce.employees_page"
  qualitydocs:
    label: "Quality Manual"
    default_endpoint: "qualitydocs.manual"
  timetracker:
    label: "Time Tracker"
    default_endpoint: "timetracker.projections_page"
    admin_only: true

# ── Paths ───────────────────────────────────────
inbox:
  path: "data/inbox"
  subdirs:
    needs_review: "NEEDS-REVIEW"
    conflicts: "CONFLICTS"
    duplicates: "DUPLICATES"

destinations:
  projects: "data/projects"
  quality_documents: "data/quality-documents"
  database: "data/quality.db"
  vector_database: "data/vectordb"

# ── Document Classification ─────────────────────
document_types:
  drawings:
    patterns: [...]
    destination: "{projects}/{project}/{discipline}"
    handler: "sis-intake"
  specifications:
    patterns: [...]
    destination: "{projects}/{project}/{drawing_set}/Specs"
    handler: "sis-spec-intake"
  # ... 13 more types (qm_modules, procedures, work_instructions,
  #     templates, forms, policies, records, wps, pqr, wpq, bps, bpq,
  #     procore_export, observation_csv, production_weld_log, field_locations)

# ── AI Model Routing ────────────────────────────
models:
  simple:
    model: haiku
    tasks: [title_block_read, file_routing, pattern_matching, simple_table_extraction]
  complex:
    model: sonnet
    tasks: [full_extraction, conflict_detection, cross_discipline_check, revision_comparison, report_generation]
  critical:
    model: opus
    tasks: [shadow_review, calibration, critical_conflict_resolution, quality_validation, ambiguous_routing]

# ── Extraction ──────────────────────────────────
extraction:
  thresholds:
    minimum_confidence: 0.6
    high_confidence: 0.9
    shadow_review_rate: 0.10
  materials:
    CS: "Carbon Steel"
    SS: "Stainless Steel"
    # ... 10+ material codes

# ── Conflict Detection ──────────────────────────
conflicts:
  checks:
    material_mismatch: true
    size_mismatch: true
    tag_duplicate: true
    missing_instrument: true
    weld_inconsistency: true
    cross_discipline: true

# ── Processing ──────────────────────────────────
processing:
  batch_size: 10
  auto:
    supersede_old_revisions: true
    archive_superseded: false
    queue_related_recheck: true

# ── Intake ──────────────────────────────────────
intake:
  auto_extract: false
  auto_embed: true
  read_title_block_always: true
  on_ambiguous: move_to_needs_review
  on_no_match: move_to_needs_review

# ── Departments ─────────────────────────────────
departments:
  - {number: "600", name: "Refrigeration"}
  - {number: "645", name: "Electrical"}
  - {number: "650", name: "Mechanical"}
  - {number: "655", name: "Plumbing"}
  - {number: "660", name: "HVAC"}
  - {number: "665", name: "Utility"}

# ── Discipline Mapping ──────────────────────────
discipline_prefixes:
  P/M/ISO: "Mechanical"
  E/EL/EP: "Electrical"
  S: "Structural"
  # ... 12+ prefixes

csi_mapping:
  "22": "Plumbing"
  "23": "HVAC"
  "24": "Refrigeration"
  "26": "Electrical"
  # ... 9+ CSI divisions

# ── Welding ─────────────────────────────────────
welding:
  cert_requests:
    wcr_prefix: "WCR"
    max_coupons_per_request: 4
    default_wpq_expiration_months: 6
  forms:
    extraction:
      models: {primary: sonnet, secondary: sonnet, shadow: opus}
      confidence: {minimum: 0.6, high: 0.9, shadow_review_rate: 0.10}
      numeric_tolerance: 0.05
    generation:
      output_dir: "data/quality-documents/Welding"
      default_format: "excel"

# ── Quality ─────────────────────────────────────
quality:
  attachment_dir: "data/quality-issues"
  normalize:
    trades: {"Mech": "Mechanical", "HVAC": "Mechanical", ...}
    statuses: {"Ready for Review": "in_review", ...}
    types: {"Safety": "observation", ...}

# ── Reference Extraction ────────────────────────
reference_extraction:
  parallel_threshold_pages: 50
  max_concurrent_extractors: 4
  section_overlap_pages: 2
  target_section_pages: 50
  models: {splitting: haiku, extraction: sonnet, merging: sonnet, validation: opus}
  confidence: {high: 0.9, medium: 0.7, low: 0.7}
  validation: {completeness_pass: 0.95, accuracy_pass: 0.90, sample_rate: 0.10}

# ── Embeddings ──────────────────────────────────
embeddings:
  provider: "auto"
  base_url: "http://127.0.0.1:1234/v1"
  model: "text-embedding-nomic-embed-text-v1.5@q8_0"
  local_model: "nomic-ai/nomic-embed-text-v1.5"
  dimensions: 768
  batch_size: 32

# ── Procore Integration ─────────────────────────
procore:
  base_url: "https://app.procore.com"
  projects: {}

# ── OneDrive Sync ───────────────────────────────
onedrive_sync:
  enabled: true
  source_root: "C:/Users/bjohnson1/OneDrive - Stellar Group Incorporated/QMS-Intake"
  delete_after_sync: true

# ── Automation ──────────────────────────────────
automation:
  incoming: "data/automation/incoming"
  processed: "data/automation/processed"
  failed: "data/automation/failed"

# ── QM Document Prefixes ────────────────────────
qm_prefixes:
  SP: "Standard Operating Procedure"
  WI: "Work Instruction"
  TP: "Template"
  FM: "Form"
  PL: "Policy"
  RC: "Record"
```

---

*This PRD was generated from the live QMS codebase at commit `d8d6d5c` on branch `main`.*

*Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>*
