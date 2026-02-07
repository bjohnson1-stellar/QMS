# Quick Reference

## First Time Setup

```bash
# Extract to D:\
Expand-Archive QC-DR.zip D:\

# Init database
sqlite3 D:\quality.db ".read D:\QC-DR\schema.sql"

# Create inbox
mkdir D:\Projects\_Inbox

# Scan existing projects
claude
/sis-scan
```

## Daily Commands

```bash
/sis-status                        # Overview
/sis-go 07600-Rosina               # Process project
/sis-go 07600-Rosina/Mechanical    # Process discipline
/sis-intake                        # Route new files
/sis-report 07600-Rosina           # Generate report
```

## Full Command List

| Command | Usage |
|---------|-------|
| `/sis-scan` | Index all projects |
| `/sis-scan 07600-Rosina` | Index one project |
| `/sis-intake` | Route inbox to projects |
| `/sis-go` | Process all pending |
| `/sis-go <project>` | Process project |
| `/sis-go <project>/<discipline>` | Process discipline |
| `/sis-status` | All projects status |
| `/sis-status <project>` | Project detail |
| `/sis-report <project>` | Generate report |
| `/sis-validate` | Check accuracy |
| `/sis-calibrate` | Update gold standard |

## Workflow: New Drawings

```bash
# 1. Drop files
Copy-Item *.pdf D:\Projects\_Inbox\

# 2. Route
/sis-intake

# 3. Process
/sis-go
```

## Workflow: Revisions

System handles automatically:
1. Detects revision from title block
2. Archives old (adds -SUPERSEDED)
3. Routes new to correct folder
4. Extracts + diffs against previous

## Common Queries

```sql
-- Project summary
SELECT * FROM v_project_summary;

-- Discipline breakdown
SELECT * FROM v_discipline_summary WHERE project = '07600';

-- Cross-discipline conflicts
SELECT * FROM v_cross_discipline_conflicts;

-- Unprocessed sheets
SELECT * FROM v_unprocessed;

-- Find line number
SELECT * FROM lines WHERE line_number LIKE '%CS-1001%';

-- Revision history
SELECT * FROM v_revision_history WHERE drawing_number = 'P-101';
```

## Folder Structure

```
D:\
├── Projects\              # Your existing structure
│   ├── _Inbox\            # New drawings drop here
│   ├── _Specifications\   # Spec PDFs by CSI division
│   ├── _Calibration\      # Gold standard data
│   └── 07600-Rosina\
│       ├── MANIFEST.json  # Added: tracking
│       ├── Mechanical\
│       │   ├── MANIFEST.json
│       │   └── *.pdf
│       └── ...
├── QC-DR\                 # System config
│   └── config.yaml        # Settings
└── quality.db             # Database
```

## Model Routing

| Task | Model |
|------|-------|
| Scan | Haiku |
| Intake | Sonnet |
| Extract (simple) | Haiku |
| Extract (complex) | Sonnet |
| First sheet | Opus |
| Shadow review | Opus |
| Cross-check | Sonnet |
| Report | Haiku |
