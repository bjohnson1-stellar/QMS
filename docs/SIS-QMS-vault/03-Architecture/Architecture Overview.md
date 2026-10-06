---
tags: [architecture, overview]
created: 2026-02-10
---

# Architecture Overview

## Design Philosophy

QMS follows a **monolithic modular** architecture:
- **Single SQLite database** (`quality.db`) — 220+ tables, single source of truth
- **Modular Python packages** — each module owns its schema, business logic, and CLI
- **Clean layer separation** — CLI (Typer) → Business Logic → Database (SQLite)
- **Optional web layer** — Flask app factory with thin API routes

## System Architecture

```mermaid
graph TB
    subgraph "User Interfaces"
        CLI[Typer CLI]
        WEB[Flask Web UI]
    end

    subgraph "Business Logic"
        CORE[core]
        ENG[engineering]
        WELD[welding]
        QDOC[qualitydocs]
        REFS[references]
        PROJ[projects]
        PIPE[pipeline]
        WORK[workforce]
        VDB[vectordb]
        RPT[reporting]
    end

    subgraph "Data Layer"
        DB[(quality.db<br>220+ tables)]
        CHROMA[(ChromaDB<br>Vector Store)]
        FS[File System<br>PDFs, Excel, XML]
    end

    CLI --> CORE
    CLI --> ENG & WELD & QDOC & REFS & PROJ & PIPE & WORK & VDB & RPT
    WEB --> PROJ

    CORE --> DB
    ENG & WELD & QDOC & REFS & PROJ & PIPE & WORK --> DB
    VDB --> DB & CHROMA
    PIPE --> FS
    REFS --> FS
    QDOC --> FS
```

## Module Dependency Graph

```mermaid
graph LR
    CORE((core)) --> WORK((workforce))
    CORE --> QDOC((qualitydocs))
    WORK --> PROJ((projects))
    WORK --> WELD((welding))
    WORK --> PIPE((pipeline))
    PROJ --> PIPE
    PROJ --> ENG((engineering))
    PROJ --> WEB((web))
    QDOC --> REFS((references))
    QDOC --> VDB((vectordb))
    REFS --> VDB
    PIPE --> VDB
    PIPE --> ENG
    WELD --> PIPE

    CORE --> RPT((reporting))
    PROJ --> RPT
    WORK --> RPT
    WELD --> RPT
    PIPE --> RPT

    style CORE fill:#4CAF50,color:#fff
    style RPT fill:#FF9800,color:#fff
    style WEB fill:#2196F3,color:#fff
    style VDB fill:#9C27B0,color:#fff
```

## Schema Dependency Order (FK Chain)

Migrations must run in this order to satisfy foreign key constraints:

```
1. core          → audit_log, attachments, notes
2. workforce     → departments, roles, employees, ...
3. projects      → business_units, projects, jobs, budgets, ...
4. qualitydocs   → qm_modules, qm_sections, qm_procedures, ...
5. references    → qm_references, ref_clauses, ref_procedure_links, ...
6. welding       → weld_welder_registry, weld_wps, weld_wpq, ...
7. pipeline      → sheets, lines, equipment, electrical_*, plumbing_*, ...
8. engineering   → eng_calculations, eng_validations
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Single SQLite DB | Simplicity, zero-config, portable, ACID transactions |
| Polymorphic audit/notes | Any entity can be audited or annotated without schema changes |
| Business logic isolation | No Flask imports in module code — testable without web dependencies |
| Shared `business_units` | Replaced per-module department tables; single source for org structure |
| FTS5 virtual tables | Full-text search without external search engine |
| ChromaDB for vectors | Separate store optimized for similarity search |
| SCHEMA_ORDER list | Explicit FK dependency chain prevents migration errors |

## Data Flow Patterns

### SIS Extraction Flow
```mermaid
sequenceDiagram
    participant U as User
    participant CLI as qms pipeline
    participant IMP as Importer
    participant Q as Processing Queue
    participant PROC as Processor
    participant DB as quality.db

    U->>CLI: import-batch --directory ./drawings/
    CLI->>IMP: import_from_directory()
    IMP->>DB: Create sheet records
    IMP->>Q: Add to processing queue
    U->>CLI: process
    CLI->>PROC: process_and_import()
    PROC->>DB: Extract lines, equipment, instruments
    PROC->>DB: Flag conflicts
```

### Web Request Flow
```mermaid
sequenceDiagram
    participant B as Browser
    participant F as Flask Route
    participant BL as Business Logic
    participant DB as quality.db

    B->>F: GET /projects/api/projects
    F->>BL: list_projects_with_budgets()
    BL->>DB: SELECT with JOINs
    DB-->>BL: Results
    BL-->>F: Python dicts
    F-->>B: JSON response
```

## File Organization

```
D:\qms\
├── core/           # Foundation (db, config, logging)
├── api/            # Flask blueprints (thin delivery layer)
├── frontend/       # Templates + static assets
├── engineering/    # Calculations + vendored refrig_calc
├── welding/        # Welding program management
├── qualitydocs/    # Quality manual content
├── references/     # External standards
├── projects/       # Project + budget management
├── pipeline/       # SIS extraction pipeline
├── workforce/      # Employee registry
├── vectordb/       # Semantic search
├── reporting/      # Cross-module reports (stub)
├── cli/            # Typer CLI entry point
├── tests/          # 142 tests
└── data/           # Runtime data (git-ignored)
```

## Related Notes
- [[Home]] — Dashboard
- [[Database Overview]] — Full schema documentation
- [[API Overview]] — REST endpoint reference
