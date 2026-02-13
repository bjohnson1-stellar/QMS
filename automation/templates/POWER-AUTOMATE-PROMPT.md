# Power Automate Flow Build — Browser Automation Prompt

Paste everything below into a new Claude Code session.

---

## Prompt

I need you to help me restructure the existing Weld Certification Request Power Automate flow into a **two-step card flow** using browser automation (claude-in-chrome MCP). The flow already exists and needs to be modified.

**Flow URL:** https://make.powerautomate.com/environments/4e6a36d1-5c91-e916-9112-46afaad1e516/flows/55131374-1afb-46aa-8cac-2c6a78099cf7?v3=true

### What the flow does

Posts two Adaptive Cards to a Teams channel for weld certification requests:
1. **Step 1 card** — superintendent picks a project site
2. **Step 2 card** — full form with employees filtered to that project, WPS selection, and coupon details

The flow writes a JSON file to SharePoint for backend processing.

### Current flow actions (to be restructured)

```
Manually trigger a flow
  → List Projects → List Employees → List WPS
  → Select (projects) → Select 1 (employees) → Select WPS
  → Card Template → Build Card
  → Post adaptive card and wait for a response
  → List Welders → Filter Welders → Filter WPS Row
  → Initialize variable (coupons)
  → Condition (c1) → Condition 1 (c2) → Condition 2 (c3) → Condition 3 (c4)
  → Compose 2 → Create file
```

### Target two-step flow

```
Manually trigger a flow
  → List Projects → Select Projects
  → Step 1 Card Template → Build Step 1 Card
  → Post Step 1 card (project picker) → wait
  |
  → Filter Employees by project_number from Step 1
  → Select Filtered Employees → List WPS → Select WPS
  → Step 2 Card Template → Build Step 2 Card (with project_display)
  → Post Step 2 card (full form) → wait
  |
  → List Welders → Filter Welders → Filter WPS Row
  → Initialize variable (coupons)
  → Conditions (c1-c4)
  → Compose 2 (updated for two-step refs) → Create file
```

### Key changes needed

1. **Split card posting into two steps:**
   - Move project Select before a new "Post Step 1 card" action
   - Add Filter array on Employees where `Project Number` equals Step 1's `project_number`
   - Existing employee/WPS Select actions move after the filter
   - Second "Post adaptive card and wait" for the full form

2. **Card templates:**
   - Step 1: `D:\qms\automation\templates\cert-request-card-step1.json` (project picker only)
   - Step 2: `D:\qms\automation\templates\cert-request-card.json` (read-only project display + filtered employees + WPS + coupons)

3. **Step 2 card placeholders:**
   - `${project_display}` — read-only text like "07645 - Project Name"
   - `${employee_choices}` — filtered to selected project
   - `${wps_choices}` — all active WPS

4. **Compose 2 update:** `project_number` comes from Step 1 card response, not Step 2

### Card field IDs

**Step 1 card submission:**
```
project_number           - Selected project
action: "select_project" - Identifies this as Step 1
```

**Step 2 card submission:**
```
employee_number          - Selected employee (from filtered Employees)
new_welder_emp_number    - Manual entry: employee number
new_welder_first_name    - Manual entry: first name
new_welder_last_name     - Manual entry: last name
wps_number               - Selected WPS
c1_thickness, c1_diameter - Coupon 1
c2_thickness, c2_diameter - Coupon 2 (if expanded)
c3_thickness, c3_diameter - Coupon 3 (if expanded)
c4_thickness, c4_diameter - Coupon 4 (if expanded)
notes                    - Free text
action: "submit_cert_request" - Identifies this as Step 2
```

### Files to reference

- **Step 1 card:** `D:\qms\automation\templates\cert-request-card-step1.json`
- **Step 2 card:** `D:\qms\automation\templates\cert-request-card.json`
- **Flow guide:** `D:\qms\automation\templates\README-cert-request-flow.md`
- **Excel export code:** `D:\qms\welding\export_lookups.py` (shows table/column names)

### Important notes

- The Excel file `welding-lookups.xlsx` is on SharePoint (SIS Quality Management site)
- Use only standard (non-premium) connectors
- Cards use `style: "filtered"` for searchable dropdowns — works in Teams but not the web designer
- Employee mode detection: if `employee_number` is not empty → existing employee path; otherwise → new employee path
- SharePoint Create file action uses site "SIS Quality Management", folder `/Shared Documents/General/Welding Program/automation/incoming`
- Canvas buttons in Power Automate require JavaScript `.click()` — standard DOM clicks don't register
- Monaco expression editor needs clipboard paste (via `navigator.clipboard.writeText()` + Ctrl+V) to avoid smart quote autocorrection
