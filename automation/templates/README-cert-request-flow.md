# Weld Certification Request — Power Automate Flow Guide

How to wire `cert-request-card.json` into a Power Automate flow that delivers
JSON files to `data/automation/incoming/` for processing by `qms automation process`.

## Prerequisites

- `welding-lookups.xlsx` synced to OneDrive (run `qms welding export-lookups`)
- Power Automate with standard connectors (no premium required)
- Teams channel or group chat where superintendents submit requests

## Flow Overview

```
Trigger: Teams adaptive card submission
   |
   v
1. Read lookup tables from welding-lookups.xlsx (OneDrive)
2. Build dynamic choice arrays for Welders, WPS, Projects
3. Post adaptive card to Teams (with populated dropdowns)
4. On submit → map card fields to JSON schema
5. Write JSON file to data/automation/incoming/
```

## Step-by-Step

### 1. Trigger

Use **"When someone responds to an adaptive card"** or post the card via
**"Post adaptive card and wait for a response"** in a Teams channel.

### 2. Populate Dynamic Choices

Add three **"List rows present in a table"** actions (Excel Online connector)
pointing at `welding-lookups.xlsx` on OneDrive:

| Action Name       | Excel Table  | Choice Format                       | Card Placeholder     |
|-------------------|--------------|-------------------------------------|----------------------|
| List Projects     | `Projects`   | `{Project Number} - {Project Name}` | `${project_choices}` |
| List Welders      | `Employees`  | `{Welder Stamp} - {Display Name}`   | `${welder_choices}`  |
| List WPS          | `WPS`        | `{WPS Number} - {Title}`            | `${wps_choices}`     |

**Filtering welders by project:** The `Employees` table includes a `Project Number`
column. After the user selects a project, use a **Filter array** action on the
Employees rows where `Project Number` equals the submitted `project_number` value.
This reduces the welder dropdown from ~100 entries to only those assigned to the
selected jobsite (~5-15).

For a single-card flow (no refresh), pre-populate `${welder_choices}` with all
welders — the `style: "filtered"` typeahead still makes it easy to find someone.
For a two-step flow, post a project-picker card first, then post the full form
with a filtered welder list.

For each choice list, use a **Select** action to transform rows into
`{"title": "...", "value": "..."}` objects:

```
// Projects example
Title:  concat(items('Apply_to_each')?['Project Number'], ' - ', items('Apply_to_each')?['Project Name'])
Value:  items('Apply_to_each')?['Project Number']

// Welders example (filtered by project)
Title:  concat(items('Apply_to_each')?['Welder Stamp'], ' - ', items('Apply_to_each')?['Display Name'])
Value:  items('Apply_to_each')?['Welder Stamp']
```

Replace the `${...}` placeholders in the card JSON with the resulting arrays
before posting.

### 3. WPS Lookup

The card captures a single `wps_number` at the card level. After submission,
look up the selected WPS row from the `WPS` table in `welding-lookups.xlsx` to
extract `process`, `base_material`, and `filler_metal`. These values are
shared across all coupons in the request.

Use a **Filter array** action on the WPS table where `WPS Number` equals the
submitted `wps_number` value, then read the first matching row.

### 4. Card-to-JSON Field Mapping

The submit payload uses flat field IDs. Map them to the nested JSON structure
expected by `validate_cert_request_json()` in `welding/cert_requests.py`:

```json
{
  "type": "weld_cert_request",
  "submitted_by": "@{body('Post_adaptive_card')?['responder']['displayName']}",
  "request_date": "@{utcNow('yyyy-MM-dd')}",
  "welder": {
    // EXISTING welder (welder_stamp has a value):
    "stamp": "@{body('Post_adaptive_card')?['data']?['welder_stamp']}",
    "employee_number": "<lookup from Welders table by stamp>",
    "name": "<lookup from Welders table by stamp>",
    "is_new": false,

    // NEW welder (new_welder_emp_number has a value):
    "employee_number": "@{body('Post_adaptive_card')?['data']?['new_welder_emp_number']}",
    "name": "@{concat(body('Post_adaptive_card')?['data']?['new_welder_first_name'], ' ', body('Post_adaptive_card')?['data']?['new_welder_last_name'])}",
    "is_new": true
  },
  "project": {
    "number": "@{body('Post_adaptive_card')?['data']?['project_number']}",
    "name": "<lookup from Projects table by number>"
  },
  "coupons": [],
  "notes": "@{body('Post_adaptive_card')?['data']?['notes']}"
}
```

**Welder mode detection:** Use a Condition action —
if `welder_stamp` is not empty, use existing-welder mapping; otherwise use
new-welder mapping.

### 5. Build Coupons Array

For each coupon slot (1–4), check if `cN_position` is non-empty. If so,
append to the coupons array. The `process`, `wps_number`, `base_material`,
and `filler_metal` come from the WPS lookup (step 3), not from the card:

```json
{
  "process":       "<from WPS lookup>",
  "position":      "@{body('Post_adaptive_card')?['data']?['c1_position']}",
  "wps_number":    "@{body('Post_adaptive_card')?['data']?['wps_number']}",
  "base_material": "<from WPS lookup>",
  "filler_metal":  "<from WPS lookup>",
  "thickness":     "@{body('Post_adaptive_card')?['data']?['c1_thickness']}",
  "diameter":      "@{body('Post_adaptive_card')?['data']?['c1_diameter']}"
}
```

Repeat for `c2_*`, `c3_*`, `c4_*` — only include coupons where `cN_position`
is not empty.

### 6. Write JSON File

Use **"Create file"** (OneDrive or file system connector) to write the
composed JSON to `data/automation/incoming/`:

- **Filename:** `wcr-@{utcNow('yyyyMMdd-HHmmss')}.json`
- **Content:** The composed JSON object from steps 3–4

The automation dispatcher picks up files from this directory when
`qms automation process` runs (manually or on a schedule).

## Keeping Lookups Fresh

Run `qms welding export-lookups` periodically (or on a schedule) to refresh
`welding-lookups.xlsx`. The Excel file syncs to OneDrive, so Power Automate
always reads current data.

## Testing

1. Paste the card JSON into https://adaptivecards.io/designer/ to preview
2. Replace `${...}` placeholders with sample choice arrays for testing
3. Submit a test card and verify the JSON file lands in `data/automation/incoming/`
4. Process with `qms automation process` and check `qms welding cert-requests`
