# Milestones

Completed milestone log for this project.

| Milestone | Completed | Duration | Stats |
|-----------|-----------|----------|-------|
| v0.2 License Compliance Platform | 2026-03-09 | 5 days | 8 phases, 18 plans |

---

## v0.2 License Compliance Platform

**Completed:** 2026-03-09
**Duration:** 5 days (2026-03-05 to 2026-03-09)

### Stats

| Metric | Value |
|--------|-------|
| Phases | 8 |
| Plans | 18 |
| Files changed | ~30 |
| New DB tables | ~13 |
| New API endpoints | ~65 |
| Key decisions | 54 |

### Key Accomplishments

- **Foundation hardened**: N+1 fixes, audit trail, pagination, validation, rate limiting, CSRF coverage
- **Renewal workflow**: Event-driven license lifecycle with 7 event types, fee tracking, auto-expire CLI
- **Notification engine**: Rule-driven alerts (expiration, CE deadline, renewal), Teams webhook, task queue UI
- **Document management**: File upload/download, notes, unified activity feed (UNION ALL timeline)
- **Entity registration**: Business entities with hierarchy (recursive CTE), SoS/DBE/MBE tracking, auto-linking
- **Regulatory intelligence**: State requirements database, compliance scoring (0-100), gap analysis
- **CE catalog**: Provider/course catalog, cross-state applicability, credit-course linking, auto-fill
- **Credential portfolio**: Master-detail employee view with license + welding qualification bridge
- **Dashboard & calendar**: Home widgets (expiring licenses, alerts), iCal feed for Outlook/GCal
- **External API**: Token-authenticated read-only API (SHA-256 hashed), verification tracking

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| Foundation hardening first | Security + perf before new features |
| Events in dedicated table | Flexible history, no SQLite schema rebuild |
| Clone welding notification pattern | Proven pattern, reduced risk |
| UNION ALL activity feed | Single query merging events + notes + docs |
| Entity hierarchy via recursive CTE | WITH RECURSIVE for tree traversal |
| CSS conic-gradient gauge | Lightweight compliance display, no Chart.js |
| Soft-delete for CE catalog | Preserves referential integrity |
| Master-detail credential layout | Compact UX, AJAX detail loading |
| SHA-256 hashed API tokens | Plaintext shown once, never stored |
| Read-only external API v1 | Safety first for LAN deployment |

---

*Milestones log created: 2026-03-09*
