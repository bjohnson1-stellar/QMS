# SIS Quality System

Autonomous drawing review. Works with your existing folder structure.

## Quick Start

```powershell
# 1. Extract system files to D:\
Expand-Archive QC-DR.zip D:\

# 2. Initialize database
cd D:\
sqlite3 quality.db ".read QC-DR\schema.sql"

# 3. Create inbox
mkdir D:\Projects\_Inbox
mkdir D:\Projects\_Inbox\NEEDS-REVIEW

# 4. Scan your existing projects
claude
/sis-scan

# 5. Process
/sis-go 07600-Rosina
```

## Your Existing Structure (Unchanged)

```
D:\Projects\
├── 07600-Rosina\
│   ├── Architectural\
│   ├── Civil\
│   ├── Electrical\
│   ├── Mechanical\
│   ├── ...
│   └── Utilities\
└── 07609-Freshpet\
    ├── Architectural\
    ├── Fire-Protection\
    └── ...
```

System adds only `MANIFEST.json` files for tracking. Your drawings stay in place.

## Commands

| Command | What It Does |
|---------|--------------|
| `/sis-scan` | Index existing projects (run first) |
| `/sis-intake` | Route new drawings from Inbox |
| `/sis-go 07600-Rosina` | Process entire project |
| `/sis-go 07600-Rosina/Mechanical` | Process one discipline |
| `/sis-status` | Show progress and alerts |
| `/sis-report 07600-Rosina` | Generate review report |

## Workflow

### First Time: Index Existing Projects

```bash
/sis-scan                    # Discovers all projects and disciplines
```

### Process Projects

```bash
/sis-go 07600-Rosina         # Full project
/sis-go 07600-Rosina/Mechanical    # Just Mechanical
```

### New Drawings Arrive

```bash
# Drop in inbox
Copy-Item *.pdf D:\Projects\_Inbox\

# Route to correct folders
/sis-intake

# Process
/sis-go
```

## What `/sis-scan` Discovers

```
07600-Rosina:
  Disciplines: 10
  ├── Architectural     18 drawings
  ├── Civil             12 drawings
  ├── Electrical        45 drawings
  ├── Mechanical       156 drawings
  ├── Plumbing          22 drawings
  ├── Refrigeration     35 drawings
  └── ...
  Total: 377 drawings
```

## What `/sis-go` Does

```
For each discipline:
  1. Find unprocessed sheets
  2. Extract data (parallel, 3 at a time)
  3. Validate quality
  4. Shadow review 10% with Opus
  
Then:
  5. Cross-check within discipline
  6. Cross-check across disciplines
  7. Generate reports
```

## Cross-Discipline Conflicts

Most valuable conflicts are across disciplines:
- P&ID shows Carbon Steel, Isometric shows Stainless
- Equipment on P&ID not shown on Electrical
- Pipe support conflicts with steel framing

## Status Output

```
/sis-status 07600-Rosina

Discipline              Sheets  Done  Conflicts
─────────────────────────────────────────────────
Mechanical                156   120       5
Structural                 48    48       1
Electrical                 45    32       1
Refrigeration              35    28       2
...
─────────────────────────────────────────────────
TOTAL                     377   313       9

Cross-Discipline: 3
```

## Model Usage

| Task | Model |
|------|-------|
| Scan, classify | Haiku |
| Simple extraction | Haiku |
| Complex extraction | Sonnet |
| Cross-check | Sonnet |
| First sheet | Opus |
| Shadow review | Opus |
