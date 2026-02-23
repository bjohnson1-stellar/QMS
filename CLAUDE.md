# QMS — Quality Management System

Modular Python package at `D:\qms\` for construction quality management, drawing review, and engineering calculations.

## Git Workflow (MANDATORY)

**Repository:** `https://github.com/bjohnson1-stellar/QMS.git` — Branch: `main`

### Auto-Commit Rule
**ALWAYS commit and push after completing a batch of work.** Do not wait to be asked.

```bash
cd D:\qms
git add -A -- ':!data'
git commit -m "description of changes

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
git push origin main
```

### What to commit
- All package code (including `.planning/`)
- `.gitignore`, `CLAUDE.md`, `pyproject.toml`, `config.yaml`

### What to NEVER commit
- `data/` — runtime data (database, projects, documents, vectordb)
- `*.db`, `*.db-shm`, `*.db-wal` — database files
- `.mcp.json` — local MCP config
- `*.egg-info/` — build artifacts

### Roadmap Maintenance
**ALWAYS update `.planning/roadmap.json` when completing or adding features.**
- Completed feature → move to "Recently Completed" with `"completed": "YYYY-MM-DD"`
- New feature → add to "In Progress" or "Planned" with module, priority, tags
- Feeds the admin system map at `/admin/system-map`

## Key Paths

| Resource | Path |
|----------|------|
| Package root | `D:\qms\` |
| Config | `config.yaml` (relative paths, resolved by `QMS_PATHS`) |
| Database | `data/quality.db` (263 tables, 13 schema files) |
| Unified Inbox | `data/inbox/` |
| Projects | `data/projects/` |
| Quality Docs | `data/quality-documents/` |
| Vector DB | `data/vectordb/` |
| Planning | `.planning/` |

## Reference Docs

Detailed documentation lives in `.planning/` — read on demand:

| Doc | Contents |
|-----|----------|
| [`.planning/architecture.md`](.planning/architecture.md) | Directory tree, module map, DB schema, API blueprints, auth, theming |
| [`.planning/cli-reference.md`](.planning/cli-reference.md) | All 65 CLI commands, examples, unified inbox routing |
| [`.planning/development-guide.md`](.planning/development-guide.md) | Import patterns, DB conventions, web architecture, model routing, testing |
| [`.planning/roadmap.json`](.planning/roadmap.json) | Feature roadmap (feeds `/admin/system-map`) |
