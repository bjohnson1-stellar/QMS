# Module 3 — Quality Programs

> **Purpose:** Master planning document for Quality Manual Module 3. Defines the
> program registry architecture, individual program content, integration points
> with Modules 1, 2, and 4, and open questions to resolve before XML authoring.
>
> **How to use:** Each program section collects policies, decisions, and source
> material. Add notes with dates and rationale as decisions are made. When
> Module 3 XML is authored, these notes become the source material.
>
> **Supersedes:** `.planning/module3-welding-program.md` (welding content
> preserved in Section 3.2 below)

---

## Architecture

### Two-Layer Design

Module 3 uses a **registry architecture** with two layers:

1. **Program Framework (Section 3.1)** — A short front matter explaining how
   programs are organized, their lifecycle, and how they bridge Modules 2 and 4.
2. **Individual Programs (Sections 3.2–3.8)** — Each program is a self-contained
   section with its own internal structure tailored to its purpose. A reader
   should be able to read *just one program* and understand everything they need.

### Bridge Role (Module 2 → Module 3 → Module 4)

```
Module 2 (Project Procedures)       Module 3 (Quality Programs)        Module 4 (SOPs)
"We will do X on this project"  →   "Here's what X means company-wide" → "Step-by-step how to do X"

Example:
M2 §2.4-D: "Qualify per ASME IX"  → M3 §3.2: Welding Program          → M4: SOP for WPQ test coupon
M2 §2.4-C: "Calibrate instruments"→ M3 §3.4: Testing & Calibration    → M4: SOP for gauge calibration
M2 §2.6:   "Document NCRs"        → M3 §3.5: CI/CAPA Program          → M4: SOP for NCR in Procore
```

### PDCA Mapping

| Cycle | Module | Role |
|-------|--------|------|
| **Plan** | Module 1 | Establish policies, roles, expectations |
| **Do** | Module 2 | Execute project procedures |
| **Check** | Module 3 | Verify, qualify, audit, inspect |
| **Act** | Module 3 | Correct, improve, learn |
| **Execute** | Module 4 | Step-by-step task procedures |

### Section Registry

| Section | Program | Primary Audience | Grouping |
|---------|---------|-----------------|----------|
| 3.1 | Program Framework | All | How programs work |
| 3.2 | Welding Quality Program | Quality Manager, Welders | Personnel Qualification |
| 3.3 | Training & Workforce Qualification | All Trades, Superintendents | Personnel Qualification |
| 3.4 | Testing & Calibration Program | Superintendents, QM | Verification |
| 3.5 | Continuous Improvement & CAPA | All Staff, PMs | Improvement |
| 3.6 | Field Operations Manual | Site Superintendents | Field Reference |
| 3.7 | Vendor & Subcontractor Quality | PMs, Procurement | Supply Chain |
| 3.8 | Internal Audit Program | Quality Manager, Leadership | Self-Assessment |

---

## 3.1 — Program Framework

> The "manual" layer that explains how Module 3 is organized and used.

### Planned Subsections

- **3.1-A Purpose and Scope** — What Module 3 is, who it's for, how it relates
  to Modules 1, 2, and 4
- **3.1-B How Programs Are Organized** — Each program is self-contained with its
  own structure tailored to its purpose; common elements every program shares
  (overview, roles, verification)
- **3.1-C Program Lifecycle** — Draft → Active → Under Review → Superseded →
  Retired; version control and review cadence
- **3.1-D Integration with Modules 2 and 4** — How project procedures (M2)
  reference programs, how programs reference SOPs (M4), the bridge pattern

### Common Elements (every program includes)

1. Program Overview (scope, applicable standards, owner)
2. Requirements & Criteria (what the program mandates)
3. Process/Workflow (how the program operates)
4. Roles & Responsibilities (who does what)
5. Verification & Compliance (how the program checks itself)

*Added 2026-02-20. Rationale: Module 3 needs a registry layer because programs
have independent structures — the framework section provides the unifying
context.*

---

## 3.2 — Welding Quality Program

> Company-wide welding qualification, certification, and quality framework.
> Applicable standards: ASME BPV Section IX, AWS D1.1.
> QM References: §1.4-A, §1.4-B, §1.4-D, §1.5-B, §2.3-B, §2.3-I, §2.4-D

### Planned Subsections

- **3.2-A Program Overview & Applicable Standards**
- **3.2-B Welder Status Lifecycle**
- **3.2-C Stamp Assignment & Registry**
- **3.2-D Qualification Continuity (ASME Section IX)**
- **3.2-E Registration & Onboarding**
- **3.2-F WPQ/BPQR Management & Derivation**
- **3.2-G Roles & Responsibilities**
- **3.2-H Document Control for Welding**
- **3.2-I Verification & Compliance**

### Content Notes

#### Welder Status Lifecycle

| Status | Meaning | Criteria | Can Return to Active? |
|--------|---------|----------|----------------------|
| **Active** | Currently working on SIS projects | Onsite or available for assignment | -- |
| **Inactive** | Not currently assigned but may return | Between projects, on leave, seasonal layoff. WPQ continuity still tracked per ASME IX 6-month rule | Yes — set back to Active when reassigned |
| **Terminated** | No longer employed by SIS | Left the company, fired, resigned. Continuity clock stops but records preserved for audit | Rare — would need re-qualification |
| **Archived** | Administrative cleanup | Test/duplicate entries, stamps never assigned to a real welder, data migration artifacts | Admin restore if archived by mistake |

**Key distinctions:**
- Inactive vs Terminated: Inactive welders are expected to return; their 6-month
  continuity window still applies. Terminated welders have permanently left.
- Inactive vs Archived: Inactive is a real person. Archived means the record is
  noise (test data, duplicates, import artifacts).
- Only admins can archive/restore (enforced in API and UI).

*Added 2026-02-18. Rationale: 337 inactive welders in registry, 75 with zero
WPQs.*

#### Stamp Assignment Rules

| Rule | Detail |
|------|--------|
| **Format** | `{LastInitial}{NN}` — single uppercase letter + zero-padded 2-digit number (e.g., B01, D08, T17) |
| **No dashes** | Legacy format `B-15` migrated to `B15`. |
| **Never recycled** | Archived/terminated stamps still reserved. `get_next_stamp()` scans ALL rows. |
| **Uniqueness** | DB UNIQUE constraint + validation in `register_new_welder()`. |
| **Legacy stamps** | Non-standard stamps (e.g., `BW`, `JS01`) grandfathered. New stamps must follow standard format. |

*Added 2026-02-18. Rationale: Migrated 360 stamps, zero-padded 174, cleaned 1
malformed entry.*

#### Qualification Continuity (ASME Section IX)

- 6-month continuity logs per ASME Section IX
- Updated daily when welding
- WPQ expires after 6 months idle per process
- Requalification requires new test pieces and documentation
- Quality Manager audits during periodic site visits

#### Welder Registration Process

**Current system workflow:**
1. `qms welding register` — interactive or batch CSV import
2. Auto-assigns stamp based on last name initial + next available number
3. Optional initial WPQ creation with process type
4. Welder appears in `/welding/welders` dashboard

#### WPQ / BPQR Management

- Qualified per ASME BPV Section IX for specific processes and materials
- Initial test pieces required before production welding
- Weld Quality Reports after each NDT session, uploaded to Procore within 24 hours
- Rejection rates exceeding thresholds trigger retraining or retesting
- NDT results cross-referenced to weld maps

**Qualification derivation:**
- System derives qualified ranges from actual test values (ASME IX + AWS D1.1)
- Ranges: thickness, diameter, P-number, F-number, positions, backing, deposit
  thickness
- Live derivation: `/welding/api/derive`

#### Roles & Responsibilities

| Role | Welding-Specific Responsibilities |
|------|----------------------------------|
| **Site Superintendent** | Verify qualifications before assignment. Maintain continuity logs. In-process inspections. Coordinate NDT. Submit test docs within 24 hours. |
| **Project Manager** | Integrate testing into schedule. Identify third-party inspections. Review test documentation. |
| **Quality Manager** | Audit qualification records. Coordinate additional testing. Verify procedures followed. |

#### Document Control for Welding

- Documentation maintained in Procore
- Weld maps, torque logs, photos per project requirements
- Test records stored and available for review
- Six-month continuity logs per welder

### Open Questions (Welding)

- [ ] Continuity log submission workflow (daily upload? weekly batch?)
- [ ] Rejection rate threshold that triggers retesting (what percentage?)
- [ ] NDT cross-reference requirements for weld maps
- [ ] Supervisor approval required for registration?
- [ ] Link welders to specific business units/projects?
- [ ] Onboarding documentation checklist
- [ ] Standard WPS templates for common SIS processes
- [ ] Procore integration workflow for NDT uploads
- [ ] Standard Procore folder structure for welding docs
- [ ] Retention period for welding records post-project
- [ ] Backup/export procedure for QMS welding data

### Future (Welding)

- [ ] Batch extraction of ~500 WPS/PQR/WPQ PDFs from `D:\RAW_DATA\`
- [ ] Procore API integration for automatic NDT result uploads
- [ ] Welder mobile app for daily continuity log entry
- [ ] Automated expiration notifications (email/Teams)
- [ ] Dashboard integration with QM content (contextual policy display)
- [ ] Welder certification card generation (PDF export)

---

## 3.3 — Training & Workforce Qualification Program

> Company-wide personnel qualification framework for all trades beyond welding.
> Extends the welding program's qualification model to pipefitters, electricians,
> brazing personnel, commissioning technicians, and other skilled trades.
> QM References: §1.4-A, §1.4-B, §1.4-C, §1.4-D, §1.5-B, §2.3-G, §2.3-J,
> §2.5-E

### Planned Subsections

- **3.3-A Program Overview & Scope**
- **3.3-B Required Certifications Matrix** (by trade/role)
- **3.3-C Competency Assessment Framework** (hands-on, written, prior performance)
- **3.3-D New Hire Onboarding & Orientation**
- **3.3-E Certification Tracking & Renewal**
- **3.3-F Roles & Responsibilities**
- **3.3-G Verification & Compliance**

### Content Notes

#### Gap This Program Fills

Module 1 Section 1.4-A lists 7 critical competencies requiring validated
certification: pipefitting, pressure testing, equipment calibration, welding,
brazing, system commissioning, and electrical testing. Only welding has a formal
qualification program (Section 3.2). This program covers the other six plus any
additional trade-specific requirements.

#### Required Certifications Matrix (draft)

| Trade/Role | Required Certifications | Renewal Cycle | Governing Standard |
|-----------|------------------------|---------------|-------------------|
| **Welder** | See Section 3.2 (Welding Program) | 6-month continuity (ASME IX) | ASME Section IX, AWS D1.1 |
| **Pipefitter** | Journeyman license (state-specific), medical gas brazer cert where applicable | Per state requirements | State licensing boards |
| **Electrician** | Journeyman/Master license, NFPA 70E | Per state requirements | NEC, NFPA 70E |
| **Brazer** | ASME Section IX brazing qualification | 6-month continuity | ASME Section IX |
| **Commissioning Tech** | Factory-trained on specific equipment, manufacturer certifications | Per manufacturer | OEM requirements |
| **Refrigeration Tech** | EPA 608 certification, state refrigeration license | Per EPA/state | EPA 40 CFR Part 82 |
| **Calibration Tech** | Instrument calibration training | Annual | NIST traceability standards |
| **Superintendent** | OSHA 30, first aid/CPR, site-specific orientation | OSHA 30 per card expiry | OSHA 1926 |

*Draft 2026-02-20. Requires validation against actual SIS workforce roles.*

#### Competency Validation Process (from Module 1 §1.4-B)

**Initial Qualification:**
- Hands-on demonstrations
- Written exams
- Review of prior project performance
- Third-party certifications where code-required (EPA, state licenses, NFPA 70E)

**Ongoing Validation:**
- Annual recertification as applicable
- Trade-specific continuity requirements (welders: 6-month per ASME IX)
- Certification renewal tracking via Procore Workforce Management

#### Integration with Workforce Module

The QMS `workforce/` module already tracks:
- Employee records with certifications
- Import from SIS field location data
- Certification expiration dates

This program formalizes the *policies* that the workforce module *implements*.

### Open Questions (Training)

- [ ] Which certifications are actually required vs. preferred for each trade?
- [ ] Who is responsible for verifying certifications at hire vs. at assignment?
- [ ] Does SIS have a formal new-hire orientation process to document?
- [ ] What is the process when a certification expires mid-project?
- [ ] Should the system send automated expiration warnings? (email/Teams)
- [ ] How are subcontractor workforce qualifications verified?
- [ ] Define competency assessment templates for non-certification trades
- [ ] Procore Workforce Management integration details

*Added 2026-02-20. Rationale: Module 1 references 7 trade competencies but only
welding has a formal program. This gap was identified during Module 3 structure
review.*

---

## 3.4 — Testing & Calibration Program

> Company-wide standards for instrument calibration, test methods, acceptance
> criteria, and test documentation. Includes commissioning quality standards.
> QM References: §1.4-A, §1.5-C, §2.3-G, §2.4-C, §2.4-E, §2.4-F, §2.4-G,
> §2.4-H, §2.4-I, §2.5-D, §2.5-E, §2.5-F

### Planned Subsections

- **3.4-A Program Overview & Applicable Standards**
- **3.4-B Calibration Management** (instrument registry, intervals, NIST
  traceability, out-of-tolerance response)
- **3.4-C Test Method Standards** (hydrostatic, pneumatic, electrical, functional)
- **3.4-D Acceptance Criteria Framework** (code-based minimums, project-specific
  overrides)
- **3.4-E Test Documentation Standards** (minimum content, storage, cross-
  references)
- **3.4-F Hold Points & Witness Points** (third-party/AHJ coordination)
- **3.4-G Commissioning Quality Standards** (pre-startup checklists, TAB,
  startup technician qualifications)
- **3.4-H Roles & Responsibilities**
- **3.4-I Verification & Compliance**

### Content Notes

#### Calibration Management (from Module 2 §2.4-C)

Module 2 Section 2.4-C already contains significant calibration program content:
- NIST-traceable calibration required for all measurement instruments
- Calibration certificates uploaded to Procore on receipt
- Each instrument tagged with next due date
- Project calibration log maintained
- Instruments approaching due dates flagged in weekly meetings
- Out-of-tolerance instruments removed immediately ("OUT OF SERVICE")
- Superintendent evaluates all previous readings from affected instrument
- Replacement or recalibration before resuming activities

This program **elevates these project-level requirements** to a company-wide
framework: instrument registry, standard calibration intervals by instrument
type, approved calibration vendors, out-of-tolerance investigation procedure.

#### Test Types Covered

| Test Type | Source Section | Key Standards |
|-----------|--------------|---------------|
| Hydrostatic | §2.4-E | ASME B31.1/B31.5, project specs |
| Pneumatic | §2.4-F | ASME B31.1/B31.5, safety zones |
| Electrical | §2.4-G | NEC, NFPA 70E, project specs |
| Insulation Resistance | §2.4-G | IEEE, manufacturer specs |
| Functional/Controls | §2.4-G | Design documents, BAS specs |
| TAB (Test & Balance) | §2.5-F | AABC, NEBB, TABB standards |

#### Documentation Standards (from Module 2 §2.4-H)

Minimum test documentation content (already defined in M2):
- System identification and boundaries
- Test media, pressures/voltages (specified vs actual)
- Duration and environmental conditions
- Calibrated instrument IDs and certificates
- Detailed results with acceptance criteria compliance
- Required signatures (SIS, client, AHJ)
- Photographic documentation

### Open Questions (Testing & Calibration)

- [ ] Standard calibration intervals by instrument type (gauges, meggers, torque wrenches)
- [ ] Approved calibration vendors/labs
- [ ] Instrument registry template and tracking system
- [ ] Out-of-tolerance investigation form/procedure
- [ ] How do commissioning quality standards differ from testing standards?
- [ ] Define minimum TAB company qualifications beyond AABC/NEBB/TABB
- [ ] Pre-startup checklist template for common equipment types

*Added 2026-02-20. Rationale: Section 2.4-C defines calibration requirements at
project level; this program elevates them to company-wide standards. Sections
2.4-E through 2.4-I define test procedures that need a unifying framework.*

---

## 3.5 — Continuous Improvement & Corrective Action Program

> Company-wide NCR workflow, CAPA process, root cause analysis, lessons learned,
> vendor performance tracking, and trend analysis.
> QM References: §1.2-E, §1.3-A, §1.5-C, §1.7, §2.1-E, §2.2-F, §2.3-D,
> §2.3-J, §2.4-E, §2.4-J, §2.5-B, §2.6

### Planned Subsections

- **3.5-A Program Overview & Philosophy**
- **3.5-B Non-Conformance Report (NCR) Workflow** (trigger, classification,
  disposition, closure)
- **3.5-C Root Cause Analysis Methods** (5-Why, Fishbone, Pareto)
- **3.5-D Corrective & Preventive Actions (CAPA)** (action development,
  implementation, effectiveness verification)
- **3.5-E Lessons Learned Database** (capture, categorization, dissemination)
- **3.5-F Project Debrief Process** (client + internal debriefs, action tracking)
- **3.5-G Vendor Performance & Rating** (1-5 scale, assessment criteria,
  trend tracking)
- **3.5-H Trend Analysis & KPI Metrics** (quarterly QM review, common NCR
  types, patterns)
- **3.5-I Roles & Responsibilities**
- **3.5-J Verification & Compliance**

### Content Notes

#### NCR: The Most Cross-Cutting Quality Tool

The phrase "nonconformances shall be documented" appears in **8 separate sections**
across Modules 1 and 2:

| Section | Context |
|---------|---------|
| §1.5-C | In-progress inspection nonconformances |
| §2.1-E | Document control nonconformances |
| §2.2-F | Procurement nonconformances |
| §2.3-D | Receiving inspection — "Tag with HOLD/NCR" |
| §2.3-J | Execution nonconformances |
| §2.4-E | Hydrostatic test failures |
| §2.4-J | Testing nonconformances |
| §2.5-J | Closeout nonconformances |

Yet neither module defines the NCR workflow itself. This program fills that gap.

#### NCR Workflow (draft)

1. **Identification** — Issue discovered and documented in Procore
2. **Classification** — Severity: Critical / Major / Minor (aligns with punch
   list categories in §2.5-B)
3. **Containment** — Immediate actions to prevent further impact
4. **Root Cause Analysis** — Method selected based on complexity
5. **Corrective Action** — Address root cause
6. **Preventive Action** — Prevent recurrence
7. **Effectiveness Verification** — Confirm actions worked
8. **Closure** — Formal sign-off and lessons learned capture

#### Vendor Rating System (from Module 2 §2.6-C)

| Rating | Meaning |
|--------|---------|
| 5 | Exceptional — exceeded expectations |
| 4 | Good — met expectations |
| 3 | Acceptable — met minimum expectations |
| 2 | Below expectations — issues noted |
| 1 | Unacceptable — do not use again |

**Assessment criteria:** Quality of work, schedule performance, safety record,
financial/administrative performance, communication, problem-solving, overall
value. Ratings visible to other PMs during future bidding.

#### Quarterly Analysis (from Module 2 §2.6-D)

Quality Manager reviews across projects:
- Common NCR types
- Recurring issues
- Patterns warranting corrective action
- Recommendations to division leadership
- QMS updates based on findings

### Open Questions (CI/CAPA)

- [ ] NCR severity classification criteria (what makes Critical vs Major vs Minor?)
- [ ] Required response times by severity level
- [ ] Who has NCR disposition authority? (PM only, or QM for Critical?)
- [ ] Root cause analysis method selection guide (when to use which method)
- [ ] Lessons learned database structure and dissemination process
- [ ] KPI definitions and targets (NCR closure rate, recurrence rate, time-to-close)
- [ ] How do audit findings (from §3.8) feed into CAPA?
- [ ] Vendor rating threshold for "do not use" (rating of 1 → automatic removal from AVL?)

*Added 2026-02-20. Rationale: NCR is referenced in 8 sections but never formally
defined. This is the most cross-cutting gap in the current manual.*

---

## 3.6 — Field Operations Manual

> Consolidated quick-reference for Site Superintendents. Reorganizes Module 2
> execution content by workflow rather than by project phase. Designed for
> tablet/mobile access in the field.
> QM References: §1.2-C, §1.3-B, §1.5-B, §2.1-C/E, §2.3-C through §2.3-I,
> §2.5-B

### Planned Subsections

- **3.6-A Program Overview & Quick-Start Guide**
- **3.6-B Daily Superintendent Checklist**
- **3.6-C Receiving & Material Control** (delivery verification, NCR tagging,
  storage standards, segregation rules)
- **3.6-D Site Setup & Logistics** (laydown areas, security, utilities, weather
  protection)
- **3.6-E Installation Verification** (pre-set checks, post-set QC walkdown,
  documentation)
- **3.6-F Trade-Specific Requirements** (special jointing, electrical raceways,
  equipment installation, bolted flanges)
- **3.6-G Hot Work & Special Operations** (hot tapping, pipe flushing, permits)
- **3.6-H Document Control Quick Reference** (current revisions, superseded docs,
  as-builts)
- **3.6-I Housekeeping & Roof Protection**
- **3.6-J Decision Trees & Troubleshooting** (damaged delivery, out-of-tolerance
  instrument, failed test, NCR initiation)

### Content Notes

#### Design Philosophy

This is NOT a narrative document. It's organized by **workflow** (what the
superintendent is doing right now) rather than by project phase. Format emphasis:

- **Checklists** for daily/weekly activities
- **Decision trees** for troubleshooting
- **Tables** for quick-reference standards
- **Minimal narrative** — only enough context to understand the requirement

The field manual **consolidates and reorganizes** content from 7+ Module 2
subsections (2.3-C through 2.3-I) that a superintendent currently has to search
through individually.

#### Daily Superintendent Checklist (draft)

- [ ] Verify field personnel using current document revisions
- [ ] Confirm craftsperson qualifications for assigned tasks
- [ ] Check calibration status of test instruments in use
- [ ] Walk work areas for quality and housekeeping
- [ ] Review material storage and protection
- [ ] Confirm safety measures (hot work permits, lockout/tagout)
- [ ] Upload documentation to Procore (test records, photos, as-builts)
- [ ] Update continuity logs for active welders
- [ ] Report nonconformances immediately

#### Decision Trees (planned)

| Scenario | Starts at | Key decisions |
|----------|-----------|---------------|
| Damaged delivery | Receiving | Accept/reject → NCR → disposition |
| Out-of-tolerance instrument | Testing | Remove → evaluate prior readings → re-test? |
| Failed pressure test | Testing | NCR → root cause → repair → re-test |
| Unqualified worker discovered | Execution | Stop work → verify certs → reassign or qualify |
| Superseded drawing in field | Doc Control | Remove → replace → verify as-builts transferred |

### Open Questions (Field Manual)

- [ ] What format works best for field use? (web-responsive, PDF, or both?)
- [ ] Should decision trees be flowcharts or text-based?
- [ ] What are the most common superintendent pain points? (interview field staff)
- [ ] Should this include safety checklists or defer to separate safety manual?
- [ ] Mobile-friendly layout requirements (tablet portrait orientation?)

*Added 2026-02-20. Rationale: Module 2 execution content is scattered across 7+
subsections. Superintendents need a consolidated, workflow-organized reference.*

---

## 3.7 — Vendor & Subcontractor Quality Program

> Company-wide vendor qualification criteria, approved vendor list management,
> shop inspection standards, and vendor performance tracking.
> QM References: §1.3-A, §1.3-B, §1.5-A, §2.2-B, §2.2-C, §2.2-D, §2.2-E,
> §2.3-B, §2.6-C

### Planned Subsections

- **3.7-A Program Overview & Scope**
- **3.7-B Vendor Qualification Criteria** (Tradetapp framework, financial
  stability, safety record, insurance, technical capability, past performance)
- **3.7-C Approved Vendor List (AVL) Management** (qualification, maintenance,
  removal triggers)
- **3.7-D Contract Classification** (SC, ESS, PSA, PO, SO — when to use each)
- **3.7-E Submittal Quality Standards** (review actions, acceptance criteria,
  resubmittal requirements)
- **3.7-F Shop Inspection Program** (scope, frequency, documentation, deficiency
  resolution)
- **3.7-G Vendor Performance Tracking** (rating system, trend analysis, feedback
  loop to AVL)
- **3.7-H Roles & Responsibilities**
- **3.7-I Verification & Compliance**

### Content Notes

#### Tradetapp Prequalification (from Module 2 §2.2-B)

Evaluation criteria:
- Financial stability
- Safety record
- Insurance capacity
- Technical capability
- Past performance

All vendors must be approved in Tradetapp per Risk Department policy before
contract award.

#### Shop Inspection Standards (from Module 2 §2.3-B)

Shop visits confirm:
- Dimensional and identification verification (random pieces per shop drawings)
- Piece marks correct and legible
- Welding quality acceptable, welds stamped with welder ID
- Valves installed and welded properly
- No splices in straight piping runs under 21 feet
- Materials match specifications
- Material certifications available
- Test records and welding documentation complete
- Delivery schedule on track

Reports uploaded to Procore within 48 hours with photographs.
Deficiencies resolved before shipment.

#### Vendor Rating (from Module 2 §2.6-C)

1-5 scale across 8 criteria. Ratings visible to future PMs during bidding.
Include project name/number in comments. Attach supporting docs (punch list
logs, NCRs, change orders).

### Open Questions (Vendor Quality)

- [ ] What rating triggers removal from AVL? (e.g., two consecutive 1-ratings?)
- [ ] How often is the AVL reviewed and refreshed?
- [ ] Are there different qualification tiers (e.g., critical vs. non-critical vendors)?
- [ ] Should vendor ratings aggregate across projects for trend view?
- [ ] Who approves adding a new vendor to the AVL?
- [ ] Define shop inspection frequency criteria (every visit? milestone-based?)

*Added 2026-02-20. Rationale: Vendor qualification and rating are company-wide
functions referenced across procurement, execution, and closeout phases.*

---

## 3.8 — Internal Audit Program

> Company-wide framework for Quality Manager site visits, project audits,
> management review, and performance reporting.
> QM References: §1.3-A, §1.3-B, §2.1-E, §2.2-F, §2.3-J, §2.4-J, §2.5-J,
> §2.6-D

### Planned Subsections

- **3.8-A Program Overview & Scope**
- **3.8-B Audit Schedule & Frequency** (per project phase, per BU, annual plan)
- **3.8-C Audit Scope & Criteria** (what the QM checks during site visits)
- **3.8-D Audit Methodology** (checklists, sampling, observation, interview)
- **3.8-E Finding Classification** (Major NC, Minor NC, Observation, Opportunity
  for Improvement)
- **3.8-F Corrective Action from Audits** (findings → CAPA program §3.5)
- **3.8-G Management Review** (monthly reporting per §1.3-A, quarterly trend
  analysis per §2.6-D)
- **3.8-H Roles & Responsibilities**
- **3.8-I Verification & Compliance**

### Content Notes

#### The "Periodically Verify" Gap

The phrase "Quality Manager shall periodically verify during site visits"
appears in **6 separate V&C sections** of Module 2:

| Section | What QM verifies |
|---------|-----------------|
| §2.1-E | Current document revisions in use, superseded docs removed, as-builts maintained |
| §2.2-F | Vendor qualifications, submittal completeness, material conformance |
| §2.3-J | Materials stored/protected, qualified personnel performing work, in-process inspections conducted |
| §2.4-J | Testing procedures followed, instruments calibrated, documentation complete, approvals obtained |
| §2.5-J | Closeout procedures followed, punch list progress, training completed, O&M manuals complete |
| §2.6-D | Quarterly analysis of NCR types, recurring issues, patterns warranting corrective action |

This program defines "periodically" — the audit schedule, scope for each visit,
and how findings feed into the CI/CAPA program (§3.5).

#### Audit-to-CAPA Integration

```
Audit finding (§3.8) → classified → if NC: enters CAPA workflow (§3.5)
                                   → if Observation: tracked for trend analysis
                                   → Management review: quarterly summary
```

#### Monthly Performance Reporting (from Module 1 §1.3-A)

"Monthly performance reporting that tracks conformance and continuous improvement
initiatives" — this program defines:
- What metrics are reported
- Report format and distribution
- Who reviews and takes action
- How trends are tracked over time

### Open Questions (Audit)

- [ ] Define audit frequency (monthly? per project milestone? per project phase?)
- [ ] Standard audit checklist template for site visits
- [ ] Finding classification criteria (what's Major NC vs Minor NC vs Observation?)
- [ ] Management review meeting format and frequency
- [ ] Monthly report template and KPIs
- [ ] How are audit results communicated to project teams?
- [ ] Should audits be announced or unannounced?
- [ ] Integration with any external audit requirements (client audits, insurance)

*Added 2026-02-20. Rationale: "Periodically verify" appears in 6 Module 2
sections with no defined schedule or methodology. §1.3-A references "independent
audits" and "monthly performance reporting" without a governing program.*

---

## Integration: Module 1 & 2 Updates Required

Once Module 3 is authored, these sections need cross-reference updates.

### Module 1 Updates

| Section | Current | Needed Update |
|---------|---------|---------------|
| **1.1-D** | "welding quality, testing and calibration, corrective action, and other quality functions" | List all 7 programs by name and section number |
| 1.4-A | Lists 7 competencies generically | Add: "See §3.2 (Welding) and §3.3 (Training & Workforce) for qualification programs" |
| 1.4-B | "6-month continuity logs per ASME Section IX" | Add: "per §3.2 Welding Quality Program" |
| 1.4-C | "Procore Workforce Management" tracking | Add: "per §3.3 Training & Workforce Qualification Program" |
| 1.5-C | "gauges and instruments properly calibrated" | Add: "per §3.4 Testing & Calibration Program" |
| 1.5-C | "Nonconformances documented in Procore" | Add: "per §3.5 CI/CAPA Program" |
| 1.3-A | "independent audits, monthly performance reporting" | Add: "per §3.8 Internal Audit Program" |
| 1.7 | Continuous improvement philosophy | Add: "§3.5 provides the formal CI/CAPA Program" |

### Module 2 Updates

| Section | Current | Needed Update |
|---------|---------|---------------|
| 2.2-B | Tradetapp prequalification | Add: "per §3.7 Vendor & Subcontractor Quality Program" |
| 2.3-B | Shop inspection requirements | Add: "per §3.7 §3.7-F Shop Inspection Program" |
| 2.3-G | "Assign only trained and certified personnel" | Add: "per §3.3 Training & Workforce Qualification Program" |
| **2.4-C** | Full calibration section | Add: "implements §3.4 Testing & Calibration Program at the project level" |
| **2.4-D** | Full welding section | Add: "implements §3.2 Welding Quality Program at the project level" |
| All V&C | "Quality Manager shall periodically verify" | Add: "per the schedule in §3.8 Internal Audit Program" |
| **2.6** | CI process management | Add: "implements §3.5 CI/CAPA Program at the project level" |
| 2.6-C | Vendor rating | Add: "per §3.7 Vendor & Subcontractor Quality Program" |

---

## XML Authoring Plan

### Technical Constraints

- **Namespace:** `http://stellarindustrial.com/quality-manual`
- **Section numbering:** 3.1, 3.2, ... 3.8
- **Subsection letters:** A, B, C, ... (per section)
- **Subsection types:** PurposeAndScope, Requirements, Procedures,
  Responsibilities, Documentation, VerificationAndCompliance, General
- **Content blocks:** HeadingParagraph, Paragraph, SubHeading, BulletList,
  NumberedList, Table, Note, ResponsibilityBlock
- **Cross-references:** Prose-embedded ("per Section 2.4-D") auto-detected by
  loader
- **Code references:** Prose-embedded ("ASME Section IX") auto-detected by loader
- **Load command:** `qms docs load-module data/quality-documents/module3_output.xml`

### Authoring Order

1. **3.1 Program Framework** — write first (establishes context)
2. **3.2 Welding Quality Program** — most complete content, ready to author
3. **3.3 Training & Workforce** — close companion to 3.2
4. **3.5 CI/CAPA** — cross-cutting, needed by other programs
5. **3.8 Internal Audit** — integrates with 3.5
6. **3.4 Testing & Calibration** — significant M2 content to elevate
7. **3.7 Vendor Quality** — significant M2 content to elevate
8. **3.6 Field Operations Manual** — unique format, may need special approach

### Estimated Scale

| Metric | Estimate |
|--------|----------|
| Sections | 8 (3.1 through 3.8) |
| Subsections | ~60-70 |
| Content blocks | ~400-500 |
| Cross-references (prose) | ~80-100 |
| Code references (auto-detected) | ~30-40 |

---

## Appendix: Adjacent Quality Functions (Not Module 3)

The following quality functions were identified during Module 3 planning but
belong elsewhere in the QMS. They are tracked here to ensure nothing falls
through the cracks.

### Safety & HSE Program

**Why excluded from Module 3:** Safety is typically a parallel management system
(ISO 45001), not a subsection of the quality manual. Most construction companies
maintain a separate Safety Manual alongside their Quality Manual.

**Where it belongs:** Standalone Safety Manual (or future Module 5 if SIS
integrates safety into the QMS under an IMS approach).

**Current references in QMS:**
- §2.3-C: Security measures, emergency egress
- §2.3-E: Hazardous materials storage, spill containment
- §2.3-F: Roof protection guidelines
- §2.3-H: Hot work safety, fire watch, isolation procedures
- §2.4-F: Pneumatic testing safety zones, exclusion zones
- §2.5-E: Life safety systems verification

**What it would cover:**
- Site-specific safety plans
- Hazard communication (HazCom)
- Lockout/tagout (LOTO) procedures
- Fall protection program
- Confined space entry
- Hot work permit program (currently in §2.3-H)
- Emergency action plans
- Incident investigation and reporting
- Safety orientation and training requirements
- PPE requirements by task/area
- OSHA compliance tracking

**Status:** Not started. Recommend as a separate planning initiative.

---

### Material Control & Traceability Program

**Why excluded from Module 3:** Material traceability is critical for pressure
work (ASME) but is primarily a project execution activity. The cross-project
elements are covered by existing programs.

**Where it belongs:** Split across existing programs:
- **Field Operations Manual (§3.6-C):** Receiving inspection, storage standards,
  segregation rules, NCR tagging for nonconforming materials
- **Testing & Calibration (§3.4):** MTR verification, material certification
  requirements
- **Vendor Quality (§3.7-F):** Shop inspection material verification

**What it would cover if standalone:**
- Material Test Reports (MTR) management and verification
- Heat number tracking and positive material identification (PMI)
- Material segregation requirements (stainless from carbon steel, etc.)
- Material substitution approval process
- Non-conforming material quarantine and disposition
- Traceability chain from mill cert to installed location

**Current references in QMS:**
- §2.3-B: "Materials match specifications", "material certifications available"
- §2.3-D: "Traceability documentation (tags, heat numbers, certificates)"
- §2.3-E: "Dissimilar metals stored separately to prevent cross-contamination"

**Decision:** Covered within existing Module 3 programs. Revisit if ASME
pressure work volume increases and warrants standalone treatment.

---

### Commissioning & Startup Quality Standards

**Why excluded from Module 3:** Startup procedures are project-specific (Module
2) and step-by-step checklists are SOPs (Module 4). The cross-project elements
fit within Testing & Calibration.

**Where it belongs:** Split across modules:
- **Testing & Calibration (§3.4-G):** Commissioning quality standards, pre-startup
  checklist framework, TAB company qualifications, startup technician requirements
- **Module 2 (§2.5-D/E/F):** Project-level commissioning procedures (already there)
- **Module 4 (future):** Specific SOPs for startup procedures by equipment type

**What it would cover if standalone:**
- Pre-startup verification requirements (by system type)
- Commissioning authority roles and qualifications
- Equipment startup sequence and documentation
- Testing and Balancing (TAB) program standards
- Client training and knowledge transfer framework
- System turnover process and acceptance criteria

**Decision:** Folded into §3.4-G. Revisit if SIS expands commissioning services.

---

### Client Satisfaction & Relations Program

**Why excluded from Module 3:** Client feedback is partially covered by the
CI/CAPA program's debrief process and vendor ratings framework. Not enough
cross-project infrastructure to justify standalone treatment currently.

**Where it belongs:**
- **CI/CAPA (§3.5-F):** Project debriefs (client + internal), which already
  capture client satisfaction feedback
- **Module 2 (§2.6-B):** Client debrief meeting procedures

**What it would cover if standalone:**
- Client satisfaction survey program
- Net Promoter Score (NPS) or equivalent tracking
- Client complaint escalation process
- Client retention and relationship management
- Warranty period quality monitoring
- Post-project follow-up procedures

**Decision:** Debrief process in §3.5 handles current needs. Revisit when SIS
formalizes client satisfaction measurement beyond project debriefs.

---

### Risk Management Program

**Why excluded from Module 3:** Risk management is a broad business function
that spans quality, safety, financial, and strategic domains. The quality-
specific risk elements are covered within existing programs.

**Where it belongs:**
- **Vendor Quality (§3.7-B):** Vendor risk assessment via Tradetapp
- **CI/CAPA (§3.5):** Risk-based NCR severity classification
- **Internal Audit (§3.8):** Risk-based audit scheduling (higher risk projects
  get more frequent audits)
- **Module 1 (§1.3-A):** Management-level risk oversight

**What it would cover if standalone:**
- Project quality risk assessment at award
- Risk register and mitigation tracking
- Risk-based inspection planning
- Insurance and liability risk management
- Change management risk evaluation
- Lessons learned feeding risk identification

**Decision:** Quality risk elements distributed across existing programs.
Enterprise risk management is a business function beyond the QMS scope.

---

### Design Control / Engineering Review

**Why excluded from Module 3:** SIS is primarily a contractor, not a design
firm. Design review is performed by the Engineer of Record. SIS's quality role
is to verify installation matches approved designs.

**Where it belongs:**
- **Module 2 (§2.2-E):** Submittal review and approval process
- **Module 2 (§2.3-I):** Pre/post-installation verification against IFC drawings
- **Vendor Quality (§3.7-E):** Submittal quality standards

**What it would cover if applicable:**
- Design review and verification process
- Design change management
- Engineering calculation verification
- Constructability review procedures
- Value engineering proposals

**Decision:** Not applicable to SIS's current scope as a contractor. Revisit if
SIS expands into design-build services.

---

### Document Control Program

**Why excluded from Module 3:** Document control is already well-defined as a
project procedure in Module 2 Section 2.1 (5 subsections). The company-wide
policies are in Module 1 Section 1.6.

**Where it belongs:**
- **Module 1 (§1.6):** Company-wide document control philosophy
- **Module 2 (§2.1):** Project-level document control procedures
- **Field Operations Manual (§3.6-H):** Document control quick reference for
  superintendents

**What it would cover if standalone:**
- Company-wide document numbering and classification
- Document retention policies and schedules
- Digital document management standards
- QMS document change control process

**Decision:** Adequately covered by M1 §1.6 + M2 §2.1 + Field Manual §3.6-H.
Not a gap.

---

*Note: These items should be revisited annually during management review (per
§3.8-G) to determine if any have grown in scope enough to warrant standalone
program treatment. Items may also be promoted to Module 3 programs if SIS
business model evolves (e.g., design-build expansion, commissioning services).*

---

*This document is version-controlled in `.planning/` and committed to the QMS
repository. Last updated: 2026-02-20.*
