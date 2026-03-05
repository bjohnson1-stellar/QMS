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

### Documentation Maintenance
**ALWAYS update the relevant `.planning/` reference doc when changing system structure.**
- New/removed API blueprint, template dir, or static asset → update `architecture.md`
- New/removed CLI command or module → update `cli-reference.md`
- New dev pattern, convention, or dependency → update `development-guide.md`
- Changed table count or schema files → update `architecture.md`

## Tool Usage Rules
- **NEVER use `dir`, `type`, or other cmd.exe commands** — the shell is Git Bash, not cmd.exe
- **NEVER use Bash for file discovery** — use Glob (not `find`, `ls`, `dir`) and Grep (not `grep`, `rg`)
- **NEVER use Bash to read files** — use the Read tool (not `cat`, `head`, `tail`)
- Reserve Bash for: `git`, `pip`, `pytest`, `python`, `qms` CLI, and system commands only

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
| [`.planning/procore-integration.md`](.planning/procore-integration.md) | Procore integration planning, observation export, config reference |
| [`.planning/roadmap.json`](.planning/roadmap.json) | Feature roadmap (feeds `/admin/system-map`) |
