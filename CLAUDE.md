# SIS Quality System

Automated construction drawing review and quality document management.

## Quick Start

```
/intake                # Route ALL documents from D:\Inbox (drawings, specs, QM docs)
/sis-scan              # Index existing projects in D:\Projects
/sis-go <project>      # Full extraction pipeline for a project
/sis-status            # Show all projects with processing status
/sis-report <project>  # Generate conflict report
```

## Unified Inbox

**Drop ALL documents in `D:\Inbox`** - the system automatically classifies and routes:

| Document Type | Example | Routes To |
|---------------|---------|-----------|
| Drawings | `P-101_Rev_B.pdf` | `D:\Projects\{project}\{discipline}\` |
| Specifications | `242300-Refrigeration_Rev_01.pdf` | `D:\Projects\{project}\{set}\Specs\` |
| Procedures | `SP-001-Welding.pdf` | `D:\Quality Documents\Procedures\` |
| Work Instructions | `WI-001-Pipe-Install.pdf` | `D:\Quality Documents\Procedures\` |
| Forms | `FM-001-Inspection.pdf` | `D:\Quality Documents\Forms\` |
| Templates | `TP-001-Report.docx` | `D:\Quality Documents\Templates\` |
| Records | `RC-2024-001-Audit.pdf` | `D:\Quality Documents\Records\2024\` |
| QM Modules | `module1.xml` | `D:\Quality Documents\Modules\` |

### ZIP Files & Folders (Procore Support)

**The intake system handles archives and folders automatically:**

| Input | What Happens |
|-------|--------------|
| `Procore-Export.zip` | Extracted, contents classified, ZIP deleted |
| `Submittal-Package/` (folder) | Contents moved to inbox, folder deleted |
| Nested ZIPs | Extracted up to 2 levels deep |

This supports typical Procore download workflows - just drop the ZIP or folder and run `/intake`.

## Directory Structure

```
D:\
├── Inbox/                       # UNIFIED - Drop ALL documents here
│   ├── NEEDS-REVIEW/            # Files needing manual classification
│   ├── CONFLICTS/               # Revision conflicts
│   └── DUPLICATES/              # Hash-matched duplicates
│
├── Projects/                    # Engineering drawings by project
│   ├── 07600-Rosina/
│   │   ├── MANIFEST.json
│   │   ├── Mechanical/
│   │   │   ├── P-101_Rev_B.pdf
│   │   │   └── Specs/           # Specs route here by CSI division
│   │   ├── Refrigeration/
│   │   └── ...
│   ├── 07645-Vital/
│   └── _Specifications/         # Spec workflow utilities
│
├── Quality Documents/           # Quality Management System documents
│   ├── Modules/                 # QM XML modules (loaded by load_quality_manual.py)
│   ├── Procedures/              # SOPs, Work Instructions, Policies
│   ├── Forms/                   # Form templates
│   ├── Templates/               # Document templates
│   ├── Policies/                # Policy documents
│   └── Records/                 # Completed forms, audit evidence
│       └── 2024/                # Organized by year
│
├── QC-DR/                       # Scripts and configuration
│   ├── config.yaml              # All intake patterns and settings
│   ├── sis_common.py            # Shared utilities (config, DB, logging)
│   ├── requirements.txt         # Python dependencies
│   ├── schema.sql               # Drawing/extraction tables
│   ├── schema-specs.sql         # Specification tables
│   ├── schema-qm-docs.sql       # Quality document tables
│   ├── schema-welding.sql       # Welding document tables
│   ├── extract_reference.py     # Reference standard extractor
│   ├── weld_intake.py           # Welding document intake
│   └── scripts/
│       └── load_quality_manual.py  # QM module XML loader
│
├── quality.db                   # SQLite database (source of truth)
├── VectorDB/                    # ChromaDB vector database for semantic search
│   └── chroma.sqlite3           # ChromaDB persistence
├── Eng/                         # Engineering calculations library
└── CLAUDE.md                    # This file
```

## Key Paths

| Resource | Path |
|----------|------|
| Database | `D:\quality.db` |
| Vector Database | `D:\VectorDB` |
| **Unified Inbox** | `D:\Inbox` |
| Projects | `D:\Projects\` |
| Quality Documents | `D:\Quality Documents\` |
| Engineering Lib | `D:\Eng\` |
| Config | `D:\QC-DR\config.yaml` |

## Document Classification

### Automatic Pattern Detection

The intake system reads patterns from `config.yaml` to classify documents:

```yaml
document_types:
  drawings:
    patterns: ["^[PMSEIC]-\\d+", "^ISO-\\d+", ...]
  specifications:
    patterns: ["^\\d{6}-.*_Rev[_.]"]
  procedures:
    prefix: "SP"
    patterns: ["^SP-\\d+"]
  # ... etc
```

### Drawing Prefixes

| Prefix | Discipline |
|--------|------------|
| P-, M- | Mechanical |
| ISO- | Isometrics |
| S- | Structural |
| E-, EL- | Electrical |
| I- | Instrumentation |
| R-, RF- | Refrigeration |
| U-, UT- | Utility |
| C- | Civil |
| A- | Architectural |
| FP- | Fire Protection |
| G-, GA- | General |

### Quality Document Prefixes

| Prefix | Document Type | Destination |
|--------|---------------|-------------|
| SP- | Standard Operating Procedure | Procedures/ |
| WI- | Work Instruction | Procedures/ |
| PL- | Policy | Policies/ |
| FM- | Form | Forms/ |
| TP- | Template | Templates/ |
| RC- | Record | Records/{year}/ |

## Workflow

### Daily Operations

```bash
# 1. Drop documents in unified inbox
#    (drawings, specs, QM docs - anything)

# 2. Run intake to classify and route
/intake

# 3. Process project extractions
/sis-go 07645-Vital

# 4. Check status
/sis-status 07645

# 5. Generate reports
/sis-report 07645
```

### Intake Options

```bash
/intake                # Process ALL document types
/intake --dry-run      # Preview without changes
/intake --drawings-only    # Only process drawings
/intake --specs-only       # Only process specifications
/intake --qm-only          # Only process quality documents
```

### Handling Special Cases

Files that can't be classified go to `D:\Inbox\NEEDS-REVIEW\`
- Check for naming issues
- Manually route or rename and re-run intake

## Database Tables

### Drawing Tables
- `projects` - Project info
- `sheets` - Drawing pages with revision tracking
- `lines` - Piping data
- `equipment` - Pumps, vessels, tanks
- `instruments` - Measurement devices
- `welds` - Weld specifications
- `conflicts` - Detected issues

### Specification Tables
- `specifications` - Spec documents
- `spec_sections` - Sections within specs
- `spec_items` - Individual requirements
- `master_spec_items` - Cross-project baseline

### Quality Document Tables
- `qm_modules` - Quality Manual XML modules
- `qm_procedures` - SOPs, WIs, Policies
- `qm_forms` - Form registry
- `qm_templates` - Document templates
- `qm_records` - Completed records
- `qm_document_history` - Revision tracking

## Development

### Shared Utilities (`sis_common.py`)

All scripts import from `D:\QC-DR\sis_common.py` for consistent behavior:

```python
from sis_common import get_config, get_db_path, get_logger, SIS_PATHS

# Get database path from config.yaml
db_path = get_db_path()

# Get a configured logger
logger = get_logger('my_script')

# Access common paths
projects = SIS_PATHS.projects
inbox = SIS_PATHS.inbox

# Database context manager
from sis_common import get_db_connection
with get_db_connection() as conn:
    cursor = conn.execute("SELECT * FROM projects")
```

### Adding New Scripts

1. Create script in `D:\QC-DR\` or `D:\QC-DR\scripts\`
2. Import from `sis_common` (add `sys.path` if in subfolder)
3. Use `get_db_path()` instead of hardcoding paths
4. Use `get_logger('script_name')` for consistent logging

### Dependencies

Install with: `pip install -r D:\QC-DR\requirements.txt`

## Model Routing

| Model | Tasks |
|-------|-------|
| Haiku | File routing, pattern matching, title block reading |
| Sonnet | Full extraction, conflict detection, report generation |
| Opus | Shadow review (10%), critical decisions, ambiguous routing |

## Commands Reference

| Command | Description |
|---------|-------------|
| `/intake` | Process ALL documents from D:\Inbox |
| `/sis-scan` | Index D:\Projects, update MANIFESTs |
| `/sis-go <project>` | Full pipeline for project |
| `/sis-status` | Show all projects status |
| `/sis-report <project>` | Generate conflict report |
| `/sis-calibrate` | Add calibration samples |
| `/sis-validate <project>` | Run quality validation |
| `/spec-intake` | Legacy - redirects to /intake --specs-only |

## Agents

| Agent | Purpose |
|-------|---------|
| intake-router | Classify documents by filename pattern |
| sis-intake | Route drawings to project folders |
| sis-spec-intake | Process specifications |
| qm-intake | Route quality documents |
| sis-extractor | Read drawings, extract data |
| sis-cross-checker | Find conflicts across drawings |
| sis-reporter | Generate markdown reports |

## Quality Assurance

### Confidence Scores
- `< 0.6` - Flagged for manual review
- `0.6 - 0.9` - Normal confidence
- `> 0.9` - High confidence

### Shadow Review
Opus reviews 10% of extractions to validate quality.

### Revision Tracking
All document types maintain revision chains:
- Drawings: `supersedes`/`superseded_by` in sheets table
- Specs: `revision` column in specifications table
- QM Docs: `supersedes_id` chain in qm_procedures, qm_forms, etc.

## Troubleshooting

### File won't classify
- Check filename matches expected patterns
- Review patterns in `D:\QC-DR\config.yaml`
- Check `D:\Inbox\NEEDS-REVIEW\` for unclassified files

### Duplicate detection
- Exact hash matches go to `D:\Inbox\DUPLICATES\`
- Same revision, different content goes to `D:\Inbox\CONFLICTS\`

### Database queries
```bash
# Check recent intake
sqlite3 D:\quality.db "SELECT * FROM intake_log ORDER BY created_at DESC LIMIT 10;"

# QM document summary
sqlite3 D:\quality.db "SELECT * FROM v_qm_summary;"

# Project status
sqlite3 D:\quality.db "SELECT * FROM v_project_summary;"
```
