---
phase: 13-integrations-automation
plan: 01
subsystem: ui, api
tags: [ical, calendar, dashboard, widgets, flask]

requires:
  - phase: 12-advanced-ce-multi-credential
    provides: CE requirements, license data, notification tables
provides:
  - Home dashboard license stats (expiring licenses + alerts)
  - iCal calendar feed endpoint (/licenses/calendar.ics)
  - Calendar subscribe UI on licenses page
affects: [13-02, 13-03]

tech-stack:
  added: []
  patterns: [iCal string-building without external library]

key-files:
  created: []
  modified:
    - api/__init__.py
    - api/licenses.py
    - licenses/db.py
    - frontend/templates/home.html
    - frontend/templates/licenses/licenses.html

key-decisions:
  - "No icalendar library — RFC 5545 output built with string formatting"
  - "License stats use v_expiring_licenses view + license_notifications table"

patterns-established:
  - "iCal DATE-only events (DTSTART;VALUE=DATE) for expiration dates"
  - "Module-gated dashboard stat cards with conditional warning styling"

duration: ~10min
completed: 2026-03-06
---

# Phase 13 Plan 01: Dashboard Widgets + iCal Calendar Feed Summary

**Home dashboard now shows expiring license count and active alerts; iCal feed at /licenses/calendar.ics enables Outlook/Google Calendar subscription for renewal deadlines.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~10min |
| Completed | 2026-03-06 |
| Tasks | 3 completed |
| Files modified | 5 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Home Dashboard License Stats | Pass | Expiring licenses (1) and alerts (6) display correctly; hidden without module access |
| AC-2: iCal Calendar Feed | Pass | Returns valid VCALENDAR with DATE-only VEVENTs; 1 license expiration event verified |
| AC-3: Calendar Subscribe Link | Pass | Export dropdown has "Subscribe to Calendar" option; popover with URL copy + webcal link |

## Accomplishments

- License expiring count and active alerts now visible on home dashboard, gated by module access
- `GET /licenses/calendar.ics` returns valid iCalendar feed with license expirations and CE deadlines
- Calendar subscribe popover on licenses page with copy-to-clipboard URL and "Open in Calendar App" webcal link

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `api/__init__.py` | Modified | Added license stats queries to home dashboard index route |
| `api/licenses.py` | Modified | Added `get_calendar_events` import, `calendar_ics` route, `_ical_escape` helper |
| `licenses/db.py` | Modified | Added `get_calendar_events()` — queries expirations + CE deadlines |
| `frontend/templates/home.html` | Modified | Added expiring licenses + license alerts stat cards (module-gated) |
| `frontend/templates/licenses/licenses.html` | Modified | Added "Subscribe to Calendar" in export menu + popover with URL copy |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| No icalendar library | RFC 5545 format is simple enough for string building; avoids new dependency | Zero new deps |
| CE deadlines use license expiration as period end proxy | ce_requirements has period_months but no explicit end date; expiration is the natural deadline | Accurate for renewal-aligned CE cycles |
| Warning color on expiring count > 0 | Visual urgency for licenses needing attention | Immediate attention signal |

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

**Ready:**
- Dashboard integration pattern established (query + module-gated card)
- iCal feed infrastructure ready for future event types
- Plan 13-02 (cross-module links + bulk operations) can proceed

**Concerns:**
- Only 1 license has a future expiration date in current data — calendar feed will be richer with more data

**Blockers:**
- None

---
*Phase: 13-integrations-automation, Plan: 01*
*Completed: 2026-03-06*
