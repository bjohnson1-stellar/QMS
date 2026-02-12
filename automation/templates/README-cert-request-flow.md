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

| Action Name       | Excel Table | Choice Format                       | Card Placeholder     |
|-------------------|-------------|-------------------------------------|----------------------|
| List Welders      | `Welders`   | `{Welder Stamp} - {Display Name}`   | `${welder_choices}`  |
| List WPS          | `WPS`       | `{WPS Number} - {Title}`            | `${wps_choices}`     |
| List Projects     | `Projects`  | `{Project Number} - {Project Name}` | `${project_choices}` |

For each, use a **Select** action to transform rows into `{"title": "...", "value": "..."}` objects:

```
// Welders example
Title:  concat(items('Apply_to_each')?['Welder Stamp'], ' - ', items('Apply_to_each')?['Display Name'])
Value:  items('Apply_to_each')?['Welder Stamp']
```

Replace the `${...}` placeholders in the card JSON with the resulting arrays
before posting.

### 3. Card-to-JSON Field Mapping

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

### 4. Build Coupons Array

For each coupon slot (1–4), check if `cN_process` is non-empty. If so,
append to the coupons array:

```json
{
  "process":       "@{body('Post_adaptive_card')?['data']?['c1_process']}",
  "position":      "@{body('Post_adaptive_card')?['data']?['c1_position']}",
  "wps_number":    "@{body('Post_adaptive_card')?['data']?['c1_wps']}",
  "base_material": "@{body('Post_adaptive_card')?['data']?['c1_base_material']}",
  "filler_metal":  "@{body('Post_adaptive_card')?['data']?['c1_filler_metal']}",
  "thickness":     "@{body('Post_adaptive_card')?['data']?['c1_thickness']}",
  "diameter":      "@{body('Post_adaptive_card')?['data']?['c1_diameter']}"
}
```

Repeat for `c2_*`, `c3_*`, `c4_*` — only include coupons where process is
not empty.

### 5. Write JSON File

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
