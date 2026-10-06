---
adr_number: 1
title: "Single SQLite Database"
status: "Accepted"
date: 2026-02-10
deciders: [bjohnson1]
tags: [adr, architecture, database]
---

# ADR-001: Single SQLite Database

## Status
Accepted

## Context
QMS manages 220+ tables across 8 modules. The system needs to support:
- Cross-module queries (e.g., project data + welding data + workforce data)
- Foreign key integrity between module tables
- Simple deployment (no database server)
- Portable data (single file backup)

## Decision
Use a **single SQLite database** (`quality.db`) for all modules. Each module defines its own schema file, but all tables live in one database. Migration order is controlled by `SCHEMA_ORDER` in `core/db.py`.

## Consequences

### Positive
- Zero-config deployment — no PostgreSQL/MySQL server needed
- Cross-module JOINs are trivial (same database)
- FK constraints enforced natively
- Single-file backup/restore
- WAL mode provides good concurrent read performance

### Negative
- No concurrent write scaling (SQLite limitation)
- Single point of failure for all data
- Large DB file size (mitigated by SQLite's efficiency)
- No built-in replication

### Neutral
- ChromaDB used separately for vector storage (not suitable for SQLite)
- FTS5 virtual tables used for full-text search instead of external search engine

## Alternatives Considered
1. **PostgreSQL** — Better scaling but requires server deployment
2. **Per-module databases** — Isolation but no cross-module JOINs
3. **SQLite per module + federation** — Complex, fragile FK enforcement

## Related
- [[core]] — Database connection management
- [[Database Overview]] — Full schema map
- [[Architecture Overview]] — System design
