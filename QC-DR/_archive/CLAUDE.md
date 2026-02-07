# SIS Quality Workspace

Autonomous drawing review system. Adapts to your existing folder structure.

## Your Folder Structure (Preserved)

```
D:\Projects\
├── 07600-Rosina\
│   ├── MANIFEST.json              ← Added by system
│   ├── Architectural\
│   │   ├── MANIFEST.json          ← Added by system
│   │   └── *.pdf
│   ├── Civil\
│   ├── Electrical\
│   ├── General\
│   ├── Mechanical\
│   ├── Plumbing\
│   ├── Refrigeration\
│   ├── Refrigeration-Controls\
│   ├── Structural\
│   └── Utilities\
│
├── 07609-Freshpet\
│   ├── Architectural\
│   ├── Civil\
│   ├── Electrical\
│   ├── Fire-Protection\
│   ├── General\
│   ├── Mechanical\
│   ├── Plumbing\
│   ├── Refrigeration\
│   ├── Structural\
│   └── Utility\
│
└── ... (future projects)

D:\
├── quality.db                     ← Shared database
├── QC-DR\
│   └── config.yaml                ← Settings
└── CLAUDE.md                      ← This file

D:\Projects\
├── _Inbox\                        ← Drop new drawings here
│   ├── NEEDS-REVIEW\
│   └── CONFLICTS\
├── _Specifications\               ← Spec PDFs by CSI division
├── _Calibration\                  ← Gold standard calibration data
└── {project folders}
```

**System adapts to your folder names. No reorganization.**

## Quick Start

```bash
# 1. Scan existing projects (first time only)
/sis-scan

# 2. Process a project
/sis-go 07600-Rosina

# 3. Or process one discipline
/sis-go 07600-Rosina/Mechanical

# 4. Check status
/sis-status
```

## Commands

| Command | What It Does |
|---------|--------------|
| `/sis-scan` | Discover folders, index drawings, create manifests |
| `/sis-intake` | Route drawings from Inbox to correct project/discipline |
| `/sis-go <path>` | Full autonomous pipeline |
| `/sis-status` | Show all projects, disciplines, progress |
| `/sis-report <path>` | Generate review report |
| `/sis-calibrate` | Build gold standard, set model thresholds |
| `/sis-validate` | Check extraction accuracy |

## Main Workflows

### Workflow 1: Process Existing Projects

```bash
# First time: scan to index everything
/sis-scan

# Process entire project
/sis-go 07600-Rosina

# Or process by discipline
/sis-go 07600-Rosina/Mechanical
/sis-go 07600-Rosina/Structural
```

### Workflow 2: New Drawings Arrive

```bash
# Drop files in inbox
Copy-Item *.pdf D:\Projects\_Inbox\

# Route to correct project/discipline folders
/sis-intake

# Process new files
/sis-go
```

### Workflow 3: Revision Updates

```bash
# New revision arrives in inbox
# System detects it's a revision, archives old, routes new
/sis-intake

# Process shows revision diff
/sis-go 07600-Rosina/Mechanical
```

## How Intake Routes Drawings

```
Incoming: P-101-Rev4.pdf

1. Read title block → "07600 Rosina", Drawing P-101, Rev 4
2. Match project → 07600-Rosina
3. Match discipline → "P-" prefix → Mechanical
4. Check existing → P-101-Rev3.pdf exists
5. Archive old → P-101-Rev3-SUPERSEDED.pdf
6. Move new → 07600-Rosina/Mechanical/P-101-Rev4.pdf
7. Queue for extraction + revision diff
```

## Discipline Detection

System learns from your folders:

| Your Folder | Detected Prefixes |
|-------------|-------------------|
| Mechanical | P-, ISO-, M-, PFD- |
| Structural | S-, SF-, ST- |
| Electrical | E-, EL- |
| Refrigeration | R-, RF- |
| Refrigeration-Controls | RC-, IC- |
| Plumbing | PL- |
| Fire-Protection | FP- |
| General | G-, GA-, D- |

Patterns are learned per-project and stored in database.

## Processing Pipeline

```
/sis-go 07600-Rosina

For each discipline:
  1. Load MANIFEST.json
  2. Find unprocessed sheets
  3. Spawn parallel extractors (3 at a time)
  4. Each sheet → fresh subagent context
  5. Results → database + update MANIFEST
  
After all disciplines:
  6. Cross-check within disciplines
  7. Cross-check across disciplines (P&ID vs Isometric, etc.)
  8. Generate reports
  9. Update project MANIFEST
```

## Cross-Discipline Checking

**Within Discipline:** Same line number, different values
- P-101 says 6"-CS-1001 is Carbon Steel
- P-102 says 6"-CS-1001 is Stainless Steel

**Across Disciplines:** P&ID vs Isometric consistency
- Mechanical/P&ID: Line 6"-CS-1001 is Carbon Steel
- Mechanical/Isometrics: ISO-1001 shows Stainless Steel

**Cross-project patterns:** (Optional)
- Have we seen this line number conflict before?
- Common issues across projects

## Status Output

```
/sis-status 07600-Rosina

Project: 07600-Rosina

Discipline              Sheets  Processed  Conflicts
───────────────────────────────────────────────────────
Architectural              18         18          0
Civil                      12         12          0
Electrical                 45         32          1
General                     8          8          0
Mechanical                156        120          5
Plumbing                   22         22          0
Refrigeration              35         28          2
Refrigeration-Controls     18         10          0
Structural                 48         48          1
Utilities                  15         15          0
───────────────────────────────────────────────────────
TOTAL                     377        313          9

Cross-Discipline Conflicts: 3
  • Line 6"-CS-1001: Mechanical vs Refrigeration (material)
  • Equipment V-101: Mechanical vs Electrical (location)
  • ...

Alerts:
  ⚠ Electrical: 13 sheets unprocessed
  ⚠ Refrigeration-Controls: 8 sheets unprocessed
```

## Model Routing

| Task | Model | Why |
|------|-------|-----|
| Scan/Index | Haiku | Read title blocks |
| Intake routing | Sonnet | Match project/discipline |
| Simple extraction | Haiku | Standard drawings |
| Complex extraction | Sonnet | Dense P&IDs, large ISOs |
| First sheet | Opus | Sets project context |
| Shadow review | Opus | Catches misses |
| Cross-check | Sonnet | Compare across sheets |
| Revision diff | Sonnet | Compare versions |
| Report | Haiku | Template filling |

## Files Added to Your Structure

System only adds MANIFEST.json files:

```
07600-Rosina/
├── MANIFEST.json          ← Project summary
├── report.md              ← Generated report
├── Mechanical/
│   ├── MANIFEST.json      ← Discipline summary
│   └── (your PDFs unchanged)
└── Structural/
    ├── MANIFEST.json
    └── (your PDFs unchanged)
```

Your drawings stay exactly where they are.
