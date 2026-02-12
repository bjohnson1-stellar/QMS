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
2. Build dynamic choice arrays for Employees, WPS, Projects
3. Post adaptive card to Teams (with populated dropdowns)
4. On submit → look up employee in Welders table for stamp
5. Map card fields to JSON schema (enrich from WPS + Welders)
6. Write JSON file to data/automation/incoming/
```

## Step-by-Step

### 1. Trigger

Use **"When someone responds to an adaptive card"** or post the card via
**"Post adaptive card and wait for a response"** in a Teams channel.

### 2. Populate Dynamic Choices

Add three **"List rows present in a table"** actions (Excel Online connector)
pointing at `welding-lookups.xlsx` on OneDrive:

| Action Name       | Excel Table  | Choice Format                            | Card Placeholder       |
|-------------------|--------------|------------------------------------------|------------------------|
| List Projects     | `Projects`   | `{Project Number} - {Project Name}`      | `${project_choices}`   |
| List Employees    | `Employees`  | `{Employee #} - {Display Name}`          | `${employee_choices}`  |
| List WPS          | `WPS`        | `{WPS Number} - {Title}`                 | `${wps_choices}`       |

**Filtering employees by project:** The `Employees` table includes a
`Project Number` column. After the user selects a project, use a **Filter array**
action on the Employees rows where `Project Number` equals the submitted
`project_number` value. This reduces the employee dropdown from ~100 entries to
only those assigned to the selected jobsite (~5-15).

For a single-card flow (no refresh), pre-populate `${employee_choices}` with all
employees — the `style: "filtered"` typeahead still makes it easy to find someone.
For a two-step flow, post a project-picker card first, then post the full form
with a filtered employee list.

For each choice list, use a **Select** action to transform rows into
`{"title": "...", "value": "..."}` objects:

```
// Projects example
Title:  concat(items('Apply_to_each')?['Project Number'], ' - ', items('Apply_to_each')?['Project Name'])
Value:  items('Apply_to_each')?['Project Number']

// Employees example (filtered by project)
Title:  concat(items('Apply_to_each')?['Employee #'], ' - ', items('Apply_to_each')?['Display Name'])
Value:  items('Apply_to_each')?['Employee #']
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

### 4. Welder Stamp Check (optional enrichment)

The employee dropdown pulls from the **Employees** table — not the Welders
table. Most cert test candidates are not yet registered welders (pipefitters,
apprentices, etc.), so this is expected.

After submission, optionally check the `Welders` table to see if the
selected employee already has a welder stamp:

1. **Filter** the `Welders` table where `Employee #` equals the submitted
   `employee_number`.
2. **If found:** include the `Welder Stamp` in the JSON and set `is_new`
   to `false`.
3. **If not found (common case):** set `is_new` to `true`. The backend
   auto-registers the employee as a new welder via
   `_lookup_or_register_welder()` when the request is processed.

For the "New Employee" path (manual entry of someone not yet in the employee
system), use the typed fields directly.

### 5. Card-to-JSON Field Mapping

The submit payload uses flat field IDs. Map them to the nested JSON structure
expected by `validate_cert_request_json()` in `welding/cert_requests.py`:

```json
{
  "type": "weld_cert_request",
  "submitted_by": "@{body('Post_adaptive_card')?['responder']['displayName']}",
  "request_date": "@{utcNow('yyyy-MM-dd')}",
  "welder": {
    // EXISTING employee (employee_number has a value):
    "employee_number": "@{body('Post_adaptive_card')?['data']?['employee_number']}",
    "stamp": "<from Welders table lookup, or empty if not a welder>",
    "name": "<from Employees table lookup by employee_number>",
    "is_new": "<true if not found in Welders table>"

    // NEW employee (new_welder_emp_number has a value):
    // "employee_number": "@{body('Post_adaptive_card')?['data']?['new_welder_emp_number']}",
    // "name": "@{concat(first_name, ' ', last_name)}",
    // "is_new": true
  },
  "project": {
    "number": "@{body('Post_adaptive_card')?['data']?['project_number']}",
    "name": "<lookup from Projects table by number>"
  },
  "coupons": [],
  "notes": "@{body('Post_adaptive_card')?['data']?['notes']}"
}
```

**Employee mode detection:** Use a Condition action —
if `employee_number` is not empty, use existing-employee mapping; otherwise use
new-employee mapping (from the manual entry fields).

### 6. Build Coupons Array

For each coupon slot (1–4), check if `cN_thickness` is non-empty. If so,
append to the coupons array. The `process`, `wps_number`, `base_material`,
and `filler_metal` come from the WPS lookup (step 3). Position is hardcoded
to `6G` (all processes on this card are non-brazing):

```json
{
  "process":       "<from WPS lookup>",
  "position":      "6G",
  "wps_number":    "@{body('Post_adaptive_card')?['data']?['wps_number']}",
  "base_material": "<from WPS lookup>",
  "filler_metal":  "<from WPS lookup>",
  "thickness":     "@{body('Post_adaptive_card')?['data']?['c1_thickness']}",
  "diameter":      "@{body('Post_adaptive_card')?['data']?['c1_diameter']}"
}
```

Repeat for `c2_*`, `c3_*`, `c4_*` — only include coupons where `cN_thickness`
is not empty.

### 7. Write JSON File

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
