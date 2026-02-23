# Procore Integration

> Procore integration planning and reference. Updated 2026-02-23.

## What Exists

### CSV Import (`projects/procore_io.py`)
- `import_from_procore(conn, csv_path)` — upserts projects + jobs from "Company Home" CSV export
- Parses project numbers (`XXXXX-XXX-XX`), stages, addresses, departments
- Auto-creates customers, facilities, jobs, and project allocations
- CLI: `qms projects import-procore "path/to/Company Home.csv"`
- Pipeline: `config.yaml` → `document_types.procore_export` auto-detects CSV drops in inbox

### Drawing Zip Import (roadmap — not yet built)
- Extract PDFs from Procore drawing zip exports
- Route to `data/projects/{project}/{discipline}/`
- Handle revision superseding

## Planned: Quality Observation Export

### Goal
Export site visit observations from QMS → push into Procore project observation pages.

### Config Structure
Each active project with Procore observations gets a URL mapping in `config.yaml`:

```yaml
procore:
  base_url: "https://app.procore.com"
  projects:
    "07645":
      company_id: "XXXXX"
      project_id: "XXXXXX"
      observations_url: "https://app.procore.com/.../observations"
    "07587":
      company_id: "XXXXX"
      project_id: "XXXXXX"
      observations_url: "https://app.procore.com/.../observations"
```

### Data Flow
```
QMS Site Visit Form
    → observation records in quality.db
    → export as structured data (JSON or CSV)
    → browser automation (Chrome MCP) to fill Procore observation form
       OR
    → Procore REST API (if API access is available)
```

### Open Questions
- [ ] Do we have Procore API access, or is this browser automation only?
- [ ] What fields does a Procore observation require? (type, trade, location, description, photo, status)
- [ ] What does the QMS site visit form look like? (existing schema or new?)
- [ ] One observation per deficiency, or batch upload?

### Implementation Phases
1. **Config** — Add `procore:` section to `config.yaml` with project URL mappings
2. **Schema** — Define `site_visit_observations` table (or extend existing)
3. **Web UI** — Observation entry form (or extend existing site visit flow)
4. **Export** — Format observations for Procore consumption
5. **Push** — Browser automation or API to create observations in Procore

## Reference

### Procore Observation Fields (typical)
- Name/Title
- Type (Safety, Quality, Commissioning, etc.)
- Trade (Mechanical, Electrical, Plumbing, etc.)
- Location (building/area)
- Description
- Status (Open, Ready for Review, Closed)
- Priority (Low, Medium, High)
- Assignee
- Due date
- Photos/attachments

### Existing QMS Tables That May Relate
- `projects` — project number → Procore project mapping
- `business_units` — trade/department mapping
- `employees` — assignee mapping
