# SIS Quality System - Quick Reference

## Commands

| Command | Description |
|---------|-------------|
| `/intake` | Route documents from unified Inbox to correct locations |
| `/intake --full` | Route + Extract + Embed (complete pipeline) |
| `/go <project>` | Extract, validate, cross-check, embed |
| `/go <project>/<discipline>` | Process single discipline |
| `/status` | Show all projects status |
| `/status <project>` | Detailed project status |
| `/report <project>` | Generate conflict report |
| `/scan` | Index existing projects, create MANIFESTs |
| `/validate <project>` | Run quality validation |
| `/calibrate` | Add calibration samples |

## Typical Workflow

```
1. /scan                           # First time setup
2. Drop PDFs in D:\Inbox           # Unified inbox
3. /intake                         # Route to projects
4. /go 07600                       # Extract + embed
5. /status 07600                   # Check progress
6. /report 07600                   # Review conflicts
```

Or use the full pipeline:
```
1. Drop PDFs in D:\Inbox
2. /intake --full                  # Route → Extract → Embed
```

## Directory Structure

```
D:\
├── quality.db              # SQLite database
├── Inbox\                  # Unified inbox (ALL documents)
│   ├── NEEDS-REVIEW\       # Ambiguous files
│   ├── CONFLICTS\          # Revision conflicts
│   └── DUPLICATES\         # Duplicate files
├── Projects\               # Project drawings
│   └── 07600-Rosina\       # Project folder
│       ├── MANIFEST.json
│       ├── Mechanical\
│       └── REPORTS\
├── Quality Documents\      # QM documents
│   ├── Procedures\         # SP-, WI-, PL-
│   ├── Forms\              # FM-
│   ├── Templates\          # TP-
│   ├── Modules\            # QM XML modules
│   └── References\         # ASME, AWS, ISO standards
├── QC-DR\                  # Scripts, config, schemas
└── VectorDB\               # ChromaDB semantic search
```

## Drawing Prefixes

| Prefix | Discipline |
|--------|------------|
| P-, M- | Mechanical |
| ISO- | Mechanical (Isometrics) |
| S- | Structural |
| E- | Electrical |
| I- | Instrumentation |
| C- | Civil |
| A- | Architectural |

## Conflict Severities

| Icon | Level | Action |
|------|-------|--------|
| 🔴 | Critical | Immediate review required |
| 🟠 | High | Review before IFC |
| 🟡 | Medium | Review when possible |
| 🟢 | Low | Informational |

## Quality Scores

| Range | Status |
|-------|--------|
| 0.9+ | Excellent |
| 0.8-0.9 | Good |
| 0.6-0.8 | Acceptable |
| <0.6 | Needs review |

## Model Usage

| Model | Tasks |
|-------|-------|
| Haiku | Title blocks, simple parsing |
| Sonnet | Full extraction, conflict detection |
| Opus | Shadow review, critical decisions |

## Database Tables

| Table | Purpose |
|-------|---------|
| projects | Project registry |
| disciplines | Folders within projects |
| sheets | Drawing pages |
| lines | Piping data |
| equipment | Pumps, vessels, tanks |
| instruments | Measurement devices |
| welds | Weld specifications |
| conflicts | Detected issues |

## Key Views

| View | Shows |
|------|-------|
| v_project_summary | Projects with counts |
| v_discipline_summary | Disciplines with status |
| v_material_conflicts | Material mismatches |
| v_unprocessed | Sheets needing extraction |

## File Naming

Expected format:
```
ProjectNumber_DrawingNumber_Revision.pdf
07600_P-101_B.pdf
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| File won't route | Check title block, verify project exists |
| Low confidence | Add calibration samples |
| False conflict | Mark resolved with notes |
| Missing discipline | Create folder, run /scan |

## SQLite CLI

```bash
# Create database
sqlite3 D:\quality.db < D:\schema.sql

# Query projects
sqlite3 D:\quality.db "SELECT * FROM v_project_summary"

# Query conflicts
sqlite3 D:\quality.db "SELECT * FROM conflicts WHERE resolved=0"
```
