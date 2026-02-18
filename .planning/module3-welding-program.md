# Module 3 — Welding Quality Program

> **Purpose:** Collect policies, definitions, operational decisions, and
> requirements for the SIS Welding Quality Program. This document feeds
> into Quality Manual Module 3 when it is formally authored.
>
> **How to use:** Add notes under the relevant section as decisions are made.
> Each entry should include the date and brief rationale. When Module 3 is
> written, these notes become the source material.

---

## 1. Welder Status Lifecycle

Defines the status values for welder registry records and when each applies.

| Status | Meaning | Criteria | Can Return to Active? |
|--------|---------|----------|----------------------|
| **Active** | Currently working on SIS projects | Onsite or available for assignment | -- |
| **Inactive** | Not currently assigned but may return | Between projects, on leave, seasonal layoff. WPQ continuity still tracked per ASME IX 6-month rule | Yes -- set back to Active when reassigned |
| **Terminated** | No longer employed by SIS | Left the company, fired, resigned. Continuity clock stops but records preserved for audit | Rare -- would need re-qualification |
| **Archived** | Administrative cleanup | Test/duplicate entries, stamps never assigned to a real welder, data migration artifacts. Not a real welder record | Admin restore if archived by mistake |

**Key distinctions:**
- Inactive vs Terminated: Inactive welders are expected to return; their 6-month continuity window (ASME Section IX) still applies. Terminated welders have permanently left -- their records are retained for audit but qualifications are no longer maintained.
- Inactive vs Archived: Inactive is a real person with real qualifications. Archived means the record itself is noise (test data, duplicates, import artifacts).
- Only admins can archive/restore welders (enforced in API and UI).

*Added 2026-02-18. Rationale: 337 inactive welders in registry, 75 with zero WPQs -- needed clear criteria to distinguish real-but-idle welders from data cleanup candidates.*

---

## 2. Stamp Assignment Rules

| Rule | Detail |
|------|--------|
| **Format** | `{LastInitial}{NN}` -- single uppercase letter + zero-padded 2-digit number (e.g., B01, D08, T17) |
| **No dashes** | Legacy format `B-15` has been migrated to `B15`. Dashes are not part of the stamp. |
| **Never recycled** | Archived/terminated stamps are still reserved. `get_next_stamp()` scans ALL registry rows regardless of status. |
| **Uniqueness** | Enforced at database level (UNIQUE constraint on `welder_stamp`) and validated in `register_new_welder()`. |
| **Legacy stamps** | Non-standard stamps (e.g., `BW`, `JS01`) exist from pre-system data. These are grandfathered but new stamps must follow the standard format. |

*Added 2026-02-18. Rationale: Migrated 360 stamps from dash format, zero-padded 174 single-digit stamps, cleaned up 1 malformed entry (F1-).*

---

## 3. Qualification Continuity (ASME Section IX)

> QM Reference: Section 1.4-B, Section 2.4-D

- Welders must maintain 6-month continuity logs per ASME Section IX
- Continuity logs must be updated daily when welding
- If a welder has not welded with a specific process for 6 months, the WPQ for that process expires
- Requalification requires new test pieces and documentation
- The Quality Manager audits welder qualification records during periodic site visits

**Open questions:**
- [ ] Define the exact workflow for continuity log submission (daily upload? weekly batch?)
- [ ] Define threshold for "rejection rate exceeding project thresholds" (QM 2.4-D) -- what percentage triggers retesting?
- [ ] Define NDT cross-reference requirements for weld maps

---

## 4. Welder Registration Process

> QM Reference: Section 1.4-A, Section 1.4-D

- Personnel must possess certifications aligned with industry standards and applicable codes
- Site Superintendent must verify qualifications before assigning tasks
- Examples of critical tasks requiring validated competency: pipefitting, pressure testing, welding, brazing, system commissioning

**Current system workflow:**
1. `qms welding register` -- interactive or batch CSV import
2. Auto-assigns stamp based on last name initial + next available number
3. Optional initial WPQ creation with process type
4. Welder appears in `/welding/welders` dashboard

**Open questions:**
- [ ] Should registration require supervisor approval?
- [ ] Should welders be linked to specific business units/projects?
- [ ] Define onboarding documentation checklist (certifications to collect)

---

## 5. WPQ / BPQR Management

> QM Reference: Section 2.4-D

- All welders must be qualified per ASME BPV Section IX for specific processes and materials
- New welders must demonstrate competency through initial test pieces before production welding
- Weld Quality Reports must be completed after each NDT session and uploaded to Procore within 24 hours
- Welders with rejection rates exceeding project thresholds shall be retrained or retested
- NDT results must be cross-referenced to weld maps

**Qualification derivation:**
- System derives qualified ranges from actual test values using ASME IX and AWS D1.1 rules
- Ranges include: thickness, diameter, P-number, F-number, positions, backing, deposit thickness
- Live derivation available via `/welding/api/derive`

**Open questions:**
- [ ] Define standard WPS templates for common SIS processes
- [ ] Define rejection rate threshold per project type
- [ ] Define Procore integration workflow for NDT uploads

---

## 6. Roles and Responsibilities

> QM Reference: Section 1.3-B, Section 2.3-I, Section 2.4-G

| Role | Welding-Specific Responsibilities |
|------|----------------------------------|
| **Site Superintendent** | Verify welder qualifications before task assignment. Maintain continuity logs. Conduct in-process inspections. Coordinate NDT. Submit test documentation within 24 hours. |
| **Project Manager** | Integrate testing schedule into project schedule. Identify required third-party inspections. Review test documentation for completeness. |
| **Quality Manager** | Audit welder qualification records during site visits. Coordinate additional testing as required. Verify testing procedures are being followed. |

---

## 7. Document Control for Welding

> QM Reference: Section 1.6-A, Section 2.1-E

- Welding documentation maintained in Procore
- Weld maps, torque logs, and photos uploaded per project requirements
- Test records stored and available for review
- Six-month continuity logs maintained for each welder

**Open questions:**
- [ ] Define standard folder structure in Procore for welding docs
- [ ] Define retention period for welding records post-project
- [ ] Define backup/export procedure for welding data from QMS database

---

## 8. Future Considerations

- [ ] Batch extraction of ~500 WPS/PQR/WPQ PDFs from `D:\RAW_DATA\`
- [ ] Procore API integration for automatic NDT result uploads
- [ ] Welder mobile app for daily continuity log entry
- [ ] Automated expiration notifications (email/Teams)
- [ ] Dashboard integration with QM content (contextual policy display)
- [ ] Welder certification card generation (PDF export)

---

*This document is version-controlled in `.planning/` and committed to the QMS repository.*
