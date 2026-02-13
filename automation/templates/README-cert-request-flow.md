# Weld Certification Request — Power Automate Flow Guide

Two-step Adaptive Card flow that posts to a Teams channel. Superintendents
pick a project first, then fill out the full cert request form with employees
filtered to that jobsite. The flow writes a JSON file for backend processing
by `qms automation process`.

## Prerequisites

- `welding-lookups.xlsx` on SharePoint (run `qms welding export-lookups`)
- Power Automate with standard connectors (no premium required)
- Teams channel or group chat where superintendents submit requests

## Card Templates

| File | Purpose | Placeholders |
|------|---------|-------------|
| `cert-request-card-step1.json` | Project picker (Step 1) | `${project_choices}` |
| `cert-request-card.json` | Full form (Step 2) | `${project_display}`, `${employee_choices}`, `${wps_choices}` |

## Flow Overview

```
Trigger (manual or scheduled)
   |
   v
1. Read lookup tables from welding-lookups.xlsx (SharePoint)
2. Build project choice array
3. Post Step 1 card (project picker) --> wait for response
   |
   v
4. Filter Employees by selected project
5. Build employee + WPS choice arrays
6. Build Step 2 card with project display + filtered employees
7. Post Step 2 card (full form) --> wait for response
   |
   v
8. Look up employee in Welders table for stamp
9. Look up WPS for process/material details
10. Build coupons array from card fields
11. Compose JSON payload
12. Write JSON file to SharePoint
```

## Step-by-Step

### 1. Trigger

Use **"Manually trigger a flow"** for testing, or schedule it. The trigger
kicks off the lookup reads.

### 2. Read Lookup Tables

Add **"List rows present in a table"** actions (Excel Online connector)
pointing at `welding-lookups.xlsx` on SharePoint:

| Action Name       | Excel Table  | When Read |
|-------------------|--------------|-----------|
| List Projects     | `Projects`   | Before Step 1 card |
| List Employees    | `Employees`  | Before Step 1 card (filtered after project selection) |
| List WPS          | `WPS`        | Before Step 2 card |

### 3. Build Project Choices & Post Step 1 Card

Use a **Select** action to transform project rows into choice objects:

```
Title:  concat(item()?['Project Number'], ' - ', item()?['Project Name'])
Value:  item()?['Project Number']
```

Build the Step 1 card JSON from `cert-request-card-step1.json`, replacing
`${project_choices}` with the Select output. Post with **"Post adaptive card
and wait for a response"** to the Teams channel.

### 4. Filter Employees by Project

After the superintendent selects a project in Step 1, use a **Filter array**
action on the Employees table where `Project Number` equals the submitted
`project_number` from Step 1's response:

```
body('Post_Step_1_Card')?['data']?['project_number']
```

This reduces the employee dropdown from ~80 entries to only those assigned
to the selected jobsite (~5-15 people).

### 5. Build Step 2 Choices

Two **Select** actions:

**Employees** (from filtered array):
```
Title:  concat(item()?['Employee #'], ' - ', item()?['Display Name'])
Value:  item()?['Employee #']
```

**WPS**:
```
Title:  concat(item()?['WPS Number'], ' - ', item()?['Title'])
Value:  item()?['WPS Number']
```

### 6. Build & Post Step 2 Card

Build the Step 2 card JSON from `cert-request-card.json`. Replace:

| Placeholder | Value |
|-------------|-------|
| `${project_display}` | `concat(project_number, ' - ', project_name)` from Step 1 response + Projects lookup |
| `${employee_choices}` | Filtered employee Select output |
| `${wps_choices}` | WPS Select output |

Post with a second **"Post adaptive card and wait for a response"** action.

### 7. WPS Lookup

After Step 2 submission, filter the WPS table where `WPS Number` equals the
submitted `wps_number` to extract `process`, `base_material`, and
`filler_metal`. These values are shared across all coupons.

### 8. Welder Stamp Check

The employee dropdown pulls from the **Employees** table — not the Welders
table. Most cert test candidates are not yet registered welders (pipefitters,
apprentices, etc.), so this is expected.

After Step 2 submission, check the `Welders` table:

1. **Filter** where `Employee #` equals the submitted `employee_number`.
2. **If found:** include `Welder Stamp` and set `is_new = false`.
3. **If not found (common):** set `is_new = true`. The backend auto-registers
   via `_lookup_or_register_welder()`.

### 9. Card-to-JSON Field Mapping

Map flat card field IDs to the nested JSON structure expected by
`validate_cert_request_json()` in `welding/cert_requests.py`:

```json
{
  "type": "weld_cert_request",
  "submitted_by": "<Step 2 responder displayName>",
  "request_date": "<utcNow yyyy-MM-dd>",
  "welder": {
    "employee_number": "<from Step 2 card: employee_number or new_welder_emp_number>",
    "name": "<from Employees lookup or manual entry>",
    "stamp": "<from Welders lookup, or empty>",
    "is_new": "<true if not in Welders table>"
  },
  "project": {
    "number": "<from Step 1 card: project_number>",
    "name": "<from Projects lookup>"
  },
  "coupons": [],
  "notes": "<from Step 2 card: notes>"
}
```

**Employee mode detection:** If `employee_number` is not empty, use
existing-employee path; otherwise use new-employee manual entry fields.

**Project number source:** Comes from the Step 1 card response, NOT Step 2.

### 10. Build Coupons Array

For each coupon slot (1-4), check if `cN_thickness` is non-empty. If so,
append a coupon object:

```json
{
  "process":       "<from WPS lookup>",
  "position":      "6G",
  "wps_number":    "<from Step 2 card>",
  "base_material": "<from WPS lookup>",
  "filler_metal":  "<from WPS lookup>",
  "thickness":     "<from Step 2 card: cN_thickness>",
  "diameter":      "<from Step 2 card: cN_diameter>"
}
```

### 11. Write JSON File

Use **"Create file"** (SharePoint connector) to write the composed JSON:

- **Site:** SIS Quality Management
- **Folder:** `/Shared Documents/General/Welding Program/automation/incoming`
- **Filename:** `wcr-<utcNow('yyyyMMdd-HHmmss')>.json`
- **Content:** `string(outputs('Compose_2'))`

The automation dispatcher picks up files from this directory when
`qms automation process` runs.

## Data Filtering

The `Employees` sheet in `welding-lookups.xlsx` includes `Project Number`
and `Project Name` columns. Only employees with active job assignments
appear (generated by `_get_field_employees()` in `export_lookups.py`).

The `Projects` sheet only includes projects that have active field
personnel (generated by `_get_active_projects()` via JOIN through
jobs/employees tables).

## Keeping Lookups Fresh

Run `qms welding export-lookups` periodically to refresh
`welding-lookups.xlsx`. The Excel file syncs to SharePoint, so Power
Automate always reads current data.

## Testing

1. Paste card JSON into https://adaptivecards.io/designer/ to preview
2. Replace `${...}` placeholders with sample choice arrays
3. Run the flow manually (Test > Manually > Run flow)
4. Verify Step 1 card posts to Teams with project dropdown
5. Select a project, verify Step 2 card shows filtered employees
6. Submit Step 2, verify JSON file lands on SharePoint
7. Process with `qms automation process` and check `qms welding cert-requests`
