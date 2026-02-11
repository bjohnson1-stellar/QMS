# Weld Certification Workflow — Adaptive Cards + Power Automate + QMS

**Created:** 2026-02-11
**Status:** Design Complete — Ready to Implement
**Context:** Replaces the SharePoint Power App approach with Teams Adaptive Cards + Power Automate for simpler deployment and better mobile UX.

---

## Problem Statement

Superintendents need to request welder certification tests from the field. Currently this is done via phone calls, texts, or verbal requests — nothing is tracked until a paper WPQ shows up weeks later. We need a structured, mobile-friendly way for supers to:

1. Request a cert test for a welder
2. Register new welders who aren't in the system yet
3. Track test results and WPQ assignment

---

## Architecture Overview

```
┌─────────────────────┐        ┌──────────────────────────┐
│  Superintendent      │        │  Power Automate           │
│  (Teams mobile)      │        │  (orchestration)          │
│                      │        │                           │
│  Opens Adaptive Card │───────>│  1. Receives submission   │
│  Fills out request   │        │  2. Writes JSON to inbox  │
│  Taps Submit         │        │  3. Posts confirmation     │
└─────────────────────┘        │  4. Notifies QC manager   │
                                └────────────┬─────────────┘
                                             │
                                             ▼
┌─────────────────────┐        ┌──────────────────────────┐
│  QMS CLI             │        │  qms/data/inbox/          │
│                      │        │                           │
│  qms pipeline process│<───────│  WCR-2026-0023.json      │
│                      │        │  coupon1_WCR-2026-0023.jpg│
│  - Validates JSON    │        └──────────────────────────┘
│  - Creates DB records│
│  - Registers welder  │        ┌──────────────────────────┐
│    (if new)          │───────>│  quality.db               │
│  - Sends status back │        │  - weld_cert_requests     │
└─────────────────────┘        │  - weld_cert_request_     │
                                │    coupons                │
                                │  - weld_welder_registry   │
                                │    (if new welder)        │
                                └──────────────────────────┘
```

---

## 5-Step Workflow

### Step 1: Superintendent Submits Request (Adaptive Card in Teams)

**Trigger:** Super opens a pinned Adaptive Card in the project Teams channel (or a bot command like `@QMS new cert test`).

**Card Design — One card per welder, multiple coupons:**

```
┌──────────────────────────────────────────┐
│  Weld Certification Test Request         │
│                                          │
│  Project:  [ 07645 - Cold Storage   ▾ ] │
│  Employee: [ Bobby Torres           ▾ ] │
│  ☐ New welder (not in system yet)        │
│  Date:     [ 02/11/2026               ] │
│                                          │
│  ── Coupon 1 ─────────────────────────── │
│  Process:  [ SMAW    ▾ ]                │
│  Position: [ 3G      ▾ ]                │
│  WPS:      [ WPS-001 ▾ ]                │
│  Material: [ A53     ▾ ]                │
│                                          │
│  [+ Add Coupon 2]                        │
│                                          │
│  ── Coupon 2 (hidden until tapped) ───── │
│  Process:  [ GTAW    ▾ ]                │
│  Position: [ 6G      ▾ ]                │
│  WPS:      [ WPS-003 ▾ ]                │
│  Material: [ A53     ▾ ]                │
│                                          │
│  [+ Add Coupon 3]                        │
│  [- Remove Coupon 2]                     │
│                                          │
│  Notes: [ First time testing GTAW     ] │
│                                          │
│  [ Submit Request ]                      │
└──────────────────────────────────────────┘
```

**New Welder Toggle:** When checked, reveals additional fields:
```
│  ── New Welder Info ──────────────────── │
│  First Name:    [ Bobby              ]   │
│  Last Name:     [ Torres             ]   │
│  Employee #:    [ 40587              ]   │
│  Department:    [ Piping        ▾    ]   │
│  Supervisor:    [ Mike Johnson  ▾    ]   │
```

**Key Design Decision:** One card per welder with multiple coupons (not one card per coupon). Rationale:
- Matches real world — "Bobby is testing today, here's what he's doing"
- Less tedious for supers (one submission vs 3-4 nearly identical ones)
- Each coupon still tracked independently for pass/fail results
- Adaptive Cards support this via `Action.ToggleVisibility` for coupon 2-4 sections
- Rarely more than 4 coupons per test event

### Step 2: Power Automate Processes Submission

**Flow:** "WCR — Process Certification Request"

```
Trigger: Adaptive Card submitted in Teams
    │
    ├─ Generate WCR number (WCR-{YYYY}-{seq})
    │
    ├─ Write JSON file to QMS inbox
    │   Path: \\server\qms\data\inbox\WCR-2026-0023.json
    │   (or SharePoint sync folder → local inbox)
    │
    ├─ Post confirmation to Teams channel:
    │   "✓ WCR-2026-0023: Bobby Torres — 2 coupons
    │    SMAW/3G, GTAW/6G — submitted by Mike Johnson"
    │
    ├─ Notify QC Manager (Adaptive Card):
    │   "New cert test request. [Approve] [Review] [Reject]"
    │
    └─ If "New welder" checked:
        └─ Flag for QC review: "New welder registration pending"
```

### Step 3: QMS Ingests the Request

**Command:** `qms pipeline process` (or `qms welding process-requests`)

QMS picks up JSON files from inbox, validates, and creates database records:

```
WCR-2026-0023.json
  → weld_cert_requests (1 row, status: pending_approval)
  → weld_cert_request_coupons (2 rows, each status: pending)
  → weld_welder_registry (1 row IF new welder)
```

### Step 4: External Tester Reports Results

After the physical test, results come back per coupon. Options:
- **Adaptive Card** sent to QC manager with pass/fail per coupon
- **Manual entry** via `qms welding cert-results WCR-2026-0023`
- **Future:** External tester gets their own Adaptive Card

```
Results Card:
┌──────────────────────────────────────────┐
│  Test Results: WCR-2026-0023             │
│  Welder: Bobby Torres                    │
│                                          │
│  Coupon 1: SMAW / 3G                    │
│  Visual:  (●) Pass  ( ) Fail            │
│  Bend:    (●) Pass  ( ) Fail  ( ) N/A   │
│  RT:      ( ) Pass  ( ) Fail  (●) N/A   │
│  Result:  (●) Pass  ( ) Fail            │
│                                          │
│  Coupon 2: GTAW / 6G                    │
│  Visual:  ( ) Pass  (●) Fail            │
│  Bend:    ( ) Pass  ( ) Fail  (●) N/A   │
│  RT:      ( ) Pass  ( ) Fail  (●) N/A   │
│  Result:  ( ) Pass  (●) Fail            │
│  Failure Reason: [ incomplete fusion  ]  │
│                                          │
│  [ Submit Results ]                      │
└──────────────────────────────────────────┘
```

### Step 5: QC Manager Assigns WPQs

For each passing coupon, QC manager assigns a WPQ:

```
Approval Card:
┌──────────────────────────────────────────┐
│  WCR-2026-0023 — Ready for Assignment    │
│  Welder: Bobby Torres (Z-47)             │
│                                          │
│  Coupon 1: SMAW/3G — PASSED             │
│  Action: [Assign WPQ] [Review Details]   │
│                                          │
│  Coupon 2: GTAW/6G — FAILED             │
│  Action: [Schedule Retest] [Dismiss]     │
│                                          │
│  [ Complete All ]                        │
└──────────────────────────────────────────┘
```

On "Assign WPQ":
- Creates `weld_wpq` record with test date, process, positions, materials
- Sets expiration (6 months from test date)
- Updates welder's active WPQ count
- Posts confirmation to Teams

On "Schedule Retest":
- Creates new WCR for just the failed coupon
- Notifies superintendent

---

## JSON Schema — Inbox File

Power Automate writes this JSON to `qms/data/inbox/`:

```json
{
  "type": "weld_cert_request",
  "version": "1.0",
  "wcr_number": "WCR-2026-0023",
  "submitted_by": "mjohnson@company.com",
  "submitted_at": "2026-02-11T14:30:00Z",
  "project_number": "07645",
  "project_name": "Cold Storage Facility",
  "request_date": "2026-02-11",

  "welder": {
    "employee_number": "40587",
    "name": "Bobby Torres",
    "welder_stamp": "Z-47",
    "is_new": false
  },

  "new_welder_info": null,

  "coupons": [
    {
      "coupon_number": 1,
      "process": "SMAW",
      "position": "3G",
      "wps_number": "WPS-001",
      "base_material": "A53",
      "filler_metal": "7018",
      "thickness": null,
      "diameter": null,
      "notes": null
    },
    {
      "coupon_number": 2,
      "process": "GTAW",
      "position": "6G",
      "wps_number": "WPS-003",
      "base_material": "A53",
      "filler_metal": "ER70S-2",
      "thickness": null,
      "diameter": null,
      "notes": "First time testing GTAW"
    }
  ],

  "notes": "Bobby has been welding SMAW on site for 3 months, wants to add GTAW"
}
```

**When `is_new` is true**, `new_welder_info` is populated:

```json
{
  "new_welder_info": {
    "first_name": "Bobby",
    "last_name": "Torres",
    "employee_number": "40587",
    "department": "Piping",
    "supervisor": "Mike Johnson",
    "business_unit": "Field"
  }
}
```

---

## Database Schema

### Table: `weld_cert_requests`

```sql
CREATE TABLE IF NOT EXISTS weld_cert_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    wcr_number      TEXT NOT NULL UNIQUE,          -- WCR-2026-0001
    welder_id       INTEGER REFERENCES weld_welder_registry(id),
    employee_number TEXT,
    welder_name     TEXT NOT NULL,
    welder_stamp    TEXT,
    project_number  TEXT,
    project_name    TEXT,
    request_date    TEXT NOT NULL,                  -- YYYY-MM-DD
    submitted_by    TEXT NOT NULL,                  -- email of super
    submitted_at    TEXT NOT NULL,                  -- ISO 8601
    status          TEXT NOT NULL DEFAULT 'pending_approval',
        -- pending_approval → approved → testing → results_received
        -- → completed | cancelled
    is_new_welder   INTEGER NOT NULL DEFAULT 0,    -- 1 if welder wasn't in system
    notes           TEXT,
    approved_by     TEXT,                           -- QC manager email
    approved_at     TEXT,
    source_file     TEXT,                           -- inbox JSON filename
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_wcr_status ON weld_cert_requests(status);
CREATE INDEX idx_wcr_welder ON weld_cert_requests(welder_id);
CREATE INDEX idx_wcr_project ON weld_cert_requests(project_number);
```

### Table: `weld_cert_request_coupons`

```sql
CREATE TABLE IF NOT EXISTS weld_cert_request_coupons (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    wcr_id          INTEGER NOT NULL REFERENCES weld_cert_requests(id),
    coupon_number   INTEGER NOT NULL,              -- 1, 2, 3, 4
    process         TEXT NOT NULL,                  -- SMAW, GTAW, FCAW, etc.
    position        TEXT NOT NULL,                  -- 1G, 2G, 3G, 4G, 5G, 6G, 6GR
    wps_number      TEXT,                           -- WPS-001
    base_material   TEXT,                           -- A53, A106, SS304
    filler_metal    TEXT,                           -- 7018, ER70S-2, ER308L
    thickness       TEXT,                           -- coupon thickness if relevant
    diameter        TEXT,                           -- pipe diameter if relevant
    status          TEXT NOT NULL DEFAULT 'pending',
        -- pending → testing → passed | failed → wpq_assigned | retest_scheduled
    test_result     TEXT,                           -- pass / fail
    visual_result   TEXT,                           -- pass / fail / n-a
    bend_result     TEXT,                           -- pass / fail / n-a
    rt_result       TEXT,                           -- pass / fail / n-a
    failure_reason  TEXT,
    wpq_id          INTEGER REFERENCES weld_wpq(id),  -- set when WPQ assigned
    tested_by       TEXT,                           -- external tester name
    tested_at       TEXT,                           -- test completion date
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(wcr_id, coupon_number)
);

CREATE INDEX idx_wcrc_wcr ON weld_cert_request_coupons(wcr_id);
CREATE INDEX idx_wcrc_status ON weld_cert_request_coupons(status);
```

---

## QMS Processing Logic

### Inbox Handler: `weld_cert_request`

When `qms pipeline process` encounters a JSON with `"type": "weld_cert_request"`:

```python
def process_weld_cert_request(json_path: Path) -> None:
    """
    Process a weld certification request from the inbox.

    1. Parse and validate JSON against schema
    2. Look up or register welder
    3. Create weld_cert_requests row
    4. Create weld_cert_request_coupons rows (one per coupon)
    5. Move JSON to processed folder
    6. Log to audit trail
    """
```

**Welder lookup logic:**
```
if is_new == false:
    → Look up by employee_number or welder_stamp in weld_welder_registry
    → If not found: set status = 'pending_review', flag for QC
    → If found: link welder_id

if is_new == true:
    → Check employee_number doesn't already exist (prevent duplicates)
    → Create new weld_welder_registry row with status='pending_certification'
    → Assign next available stamp if not provided
    → Link welder_id to request
```

### CLI Commands to Add

```bash
# Process cert requests from inbox
qms welding process-requests          # Process all pending WCR JSONs

# List cert requests
qms welding cert-requests             # All active requests
qms welding cert-requests --status pending_approval
qms welding cert-requests --project 07645

# Enter test results
qms welding cert-results WCR-2026-0023
  # Interactive: prompts for each coupon's pass/fail + details

# Assign WPQ from passed coupon
qms welding assign-wpq WCR-2026-0023 --coupon 1
  # Creates WPQ, sets expiration, updates coupon status

# Schedule retest for failed coupon
qms welding schedule-retest WCR-2026-0023 --coupon 2
  # Creates new WCR with just the failed coupon
```

---

## Adaptive Card JSON (Teams)

### Request Card (Step 1)

The Adaptive Card uses `Action.ToggleVisibility` to show/hide coupon sections.
Dropdown choices are populated by Power Automate from the `export-lookups` command output.

Key Adaptive Card features used:
- `Input.ChoiceSet` for dropdowns (project, welder, process, position, WPS, material)
- `Input.Toggle` for "new welder" checkbox
- `Action.ToggleVisibility` to show/hide coupon 2-4 and new welder fields
- `Container` with `id` for toggle targets
- `Action.Submit` sends all field values to Power Automate

### Dropdown Data Source

The `qms welding export-lookups` command (already built) exports:
- Active welders → populates Employee dropdown
- Active WPS list → populates WPS dropdown
- Processes → SMAW, GTAW, FCAW, SAW
- Positions → 1G through 6GR
- Base materials → A53, A106, SS304, etc.
- Filler metals → 7018, ER70S-2, ER308L, etc.
- Active projects → populates Project dropdown

This data lives in a SharePoint list (or JSON file) that Power Automate reads
when constructing the Adaptive Card.

---

## Power Automate Flow Design

### Flow 1: "WCR — Send Request Card"

```
Trigger: Scheduled (weekly) or manual button in Teams
    │
    ├─ Fetch lookup data from SharePoint lists
    │   (or from export-lookups JSON)
    │
    ├─ Build Adaptive Card JSON with current dropdown values
    │
    └─ Post card to Teams channel (or send to specific super)
```

### Flow 2: "WCR — Process Submission"

```
Trigger: Adaptive Card submitted (Action.Submit)
    │
    ├─ Parse submitted fields
    │
    ├─ Generate WCR number
    │   → SharePoint counter list or sequential naming
    │
    ├─ Build JSON file content (see schema above)
    │
    ├─ Write JSON to inbox location
    │   Option A: SharePoint document library → synced to local inbox
    │   Option B: Direct file write via on-premises gateway
    │   Option C: HTTP webhook to QMS API (future)
    │
    ├─ Post confirmation message to channel
    │   "@{submitter} — WCR-2026-0023 submitted for Bobby Torres
    │    Coupons: SMAW/3G, GTAW/6G"
    │
    └─ Send approval card to QC Manager
        "New cert request needs your approval. [Approve] [Review] [Reject]"
```

### Flow 3: "WCR — Results Entry" (Future)

```
Trigger: QC Manager opens results card
    │
    ├─ Fetch WCR details from SharePoint (or QMS export)
    │
    ├─ Show results Adaptive Card with coupon list
    │
    ├─ On submit: write results JSON to inbox
    │
    └─ Notify QC Manager for WPQ assignment
```

---

## Config Changes (config.yaml)

```yaml
welding:
  cert_requests:
    enabled: true
    wcr_prefix: "WCR"
    max_coupons_per_request: 4
    auto_approve: false              # if true, skip QC approval step
    notify_on_new_welder: true       # flag new welder registrations
    default_wpq_expiration_months: 6
    inbox_type: "weld_cert_request"  # matches JSON "type" field
```

---

## Implementation Order

### Phase 1: Database + Inbox Processing
1. Add `weld_cert_requests` and `weld_cert_request_coupons` tables (schema migration)
2. Add inbox handler for `type: weld_cert_request` in pipeline module
3. Add `qms welding process-requests` CLI command
4. Add `qms welding cert-requests` list/status command
5. Test with sample JSON files

### Phase 2: Results + WPQ Assignment
6. Add `qms welding cert-results` CLI command (interactive results entry)
7. Add `qms welding assign-wpq` command (creates WPQ from passed coupon)
8. Add `qms welding schedule-retest` command (creates new WCR for failed coupon)
9. Wire up status transitions and notifications

### Phase 3: Adaptive Card + Power Automate
10. Build Adaptive Card JSON template for request card
11. Build Power Automate flow for card submission → JSON → inbox
12. Build confirmation/notification cards
13. Test end-to-end: Teams → Power Automate → Inbox → QMS → DB

### Phase 4: Results Card + Approval Card
14. Build Adaptive Card for test results entry
15. Build Adaptive Card for WPQ assignment/approval
16. Power Automate flows for results and approval workflows

---

## Data Flow Summary

```
FIELD                          ORCHESTRATION                    QMS
─────                          ─────────────                    ───

Super fills out          ──>   Power Automate            ──>   qms pipeline process
Adaptive Card in Teams         writes JSON to inbox             reads JSON, creates DB rows

                               Power Automate            <──   qms welding export-lookups
                               reads lookup data                exports dropdowns as JSON

QC Manager enters        ──>   Power Automate            ──>   qms welding cert-results
results in card                writes results JSON              updates coupon rows

QC Manager approves      ──>   Power Automate            ──>   qms welding assign-wpq
WPQ assignment                 writes approval JSON             creates WPQ record
```

---

## Related Files

- **Existing:** `qms/.planning/weldcertsprogress.md` — Phase 1-5 progress
- **Existing:** `qms/.planning/sharepoint-powerapp-integration.md` — SharePoint lists schema
- **Existing:** `qms/welding/` — Welding module code
- **Existing:** `qms/pipeline/` — Inbox processing pipeline
- **To build:** `qms/welding/cert_requests.py` — Cert request processing
- **To build:** Schema migration for new tables
- **To build:** CLI commands in `qms/welding/cli.py`
