---
tags: [dashboard, index]
---

# Module Index

## All QMS Modules

```dataview
TABLE
  cli_name AS "CLI Name",
  status AS "Status",
  commands AS "Commands",
  source_dir AS "Source",
  length(depends_on) AS "Dependencies",
  length(depended_by) AS "Used By"
FROM "01-QMS-Modules"
WHERE contains(tags, "qms-module")
SORT module ASC
```

## By Status

### Complete
```dataview
LIST
FROM "01-QMS-Modules"
WHERE status = "Complete"
SORT module ASC
```

### Pending
```dataview
LIST
FROM "01-QMS-Modules"
WHERE status = "Pending"
SORT module ASC
```

## By Layer

### Foundation
- [[core]] — Database, config, logging

### Data Sources (People & Projects)
- [[workforce]] — Employee registry
- [[projects]] — Project management, budgets, business units

### Domain Knowledge
- [[qualitydocs]] — Quality manual
- [[references]] — External standards (ASME, IIAR, etc.)

### Operational
- [[welding]] — Welding quality program (56 tables)
- [[pipeline]] — SIS drawing extraction (152+ tables)
- [[engineering]] — Refrigeration calculations & validation

### Integration
- [[automation]] — JSON request dispatcher (Power Automate intake)

### Intelligence
- [[vectordb]] — Semantic search across all content
- [[reporting]] — Cross-module analytics (stub)

### Delivery
- [[web]] — Flask web UI with REST API

## Shared Resources

### Shared Tables
| Table | Owner | Used By |
|-------|-------|---------|
| `business_units` | [[projects]] | [[welding]], [[pipeline]] |
| `employees` | [[workforce]] | [[projects]], [[welding]], [[pipeline]] |
| `qm_procedures` | [[qualitydocs]] | [[references]] |
| `sheets` | [[pipeline]] | [[engineering]] |
