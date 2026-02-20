# Module 4 — Standard Operating Procedures

> **Purpose:** Architecture and planning document for Quality Manual Module 4.
> Defines the SOP library structure, numbering system, standard SOP template,
> lifecycle management, and the complete catalog of SOPs mapped to their parent
> programs (Module 3) and procedures (Module 2).
>
> **How to use:** This document defines the framework. Individual SOPs are
> authored in the Module 4 XML file following the template and numbering
> conventions defined here.

---

## Architecture

### What Module 4 Is

Module 4 is a **library of task-level procedures**. Unlike Modules 1-3 (which
are narrative documents read top-to-bottom), Module 4 is a **reference
collection** — users look up the specific SOP they need and follow it step by
step.

From Module 1 Section 1.1-E:
> "Module 4 contains the detailed, task-level standard operating procedures that
> define how specific work activities are performed. Each SOP is written so that
> a qualified person can follow it as a practical field reference without
> additional explanation."

### Design Principles

1. **Self-contained** — Each SOP can be read and followed independently
2. **Field-ready** — Written for the person doing the work, not a manager
3. **Consistent structure** — Every SOP follows the same template
4. **Traceable** — Every SOP links back to its parent Module 3 program and/or
   Module 2 procedure
5. **Maintainable** — SOPs can be added, revised, or retired without
   restructuring the module
6. **Searchable** — FTS index enables finding SOPs by keyword, trade, or
   activity

### Bridge Role (Module 3 → Module 4)

```
Module 3 (Quality Programs)              Module 4 (SOPs)
"Here's what the program requires"   →   "Here's exactly how to do it"

Example:
M3 §3.2: "Welders must maintain         M4 §4.26: "SOP: Welder Continuity
 6-month continuity logs"            →    Log Entry" (step-by-step procedure)

M3 §3.4: "Instruments must be           M4 §4.18: "SOP: Pressure Gauge
 calibrated to NIST standards"       →    Calibration" (step-by-step procedure)

M3 §3.5: "Nonconformances shall         M4 §4.30: "SOP: NCR Initiation
 follow the CAPA workflow"           →    and Classification" (step-by-step)
```

### Technical Implementation

- **Single XML file:** `data/quality-documents/module4_output.xml`
- **Module number:** 4
- **Each SOP = one Section** (4.1, 4.2, ..., 4.45+)
- **Subsections A-Z per SOP** for internal structure (Purpose, Procedure, etc.)
- **Loader:** Existing `qms docs load-module` — no changes needed
- **FTS:** Scales to 500+ content blocks with <50ms query time
- **Cross-references:** Prose-embedded ("per Section 4.1-A") auto-detected

---

## SOP Numbering System

### Section Range Reservations

SOPs are grouped by category with reserved section number ranges. This provides
visual organization while allowing each category to grow independently.

| Range | Category | Parent Program(s) | Est. SOPs |
|-------|----------|-------------------|-----------|
| 4.1 | SOP Framework | — | 1 |
| 4.2–4.5 | Document Control & Records | M2 §2.1, M3 §3.6 | 4 |
| 4.6–4.10 | Procurement & Vendor Management | M2 §2.2, M3 §3.7 | 5 |
| 4.11–4.16 | Site Logistics & Material Management | M2 §2.3, M3 §3.6 | 6 |
| 4.17–4.22 | Calibration & Instruments | M2 §2.4-C, M3 §3.4 | 5 |
| 4.23–4.29 | Testing (Hydro/Pneumatic/Electrical) | M2 §2.4, M3 §3.4 | 6 |
| 4.30–4.35 | Welding & Personnel Qualification | M2 §2.4-D, M3 §3.2, §3.3 | 6 |
| 4.36–4.40 | Continuous Improvement & NCR | M2 §2.6, M3 §3.5 | 5 |
| 4.41–4.47 | Closeout, Startup & Commissioning | M2 §2.5, M3 §3.4 | 7 |
| 4.48–4.50 | Internal Audit & Management Review | M3 §3.8 | 3 |

**Expansion room:** Each range has 1-2 spare slots for future SOPs. If a
category outgrows its range, new SOPs use the next available number above 4.50.

### SOP Identifier Convention

Each SOP also has a human-readable **SOP ID** for use in forms, training records,
and field reference. The ID appears in the SOP's Purpose subsection.

Format: `SOP-{CATEGORY}-{NNN}`

| Category Code | Meaning | Examples |
|---------------|---------|---------|
| DOC | Document Control | SOP-DOC-001, SOP-DOC-002 |
| PRO | Procurement | SOP-PRO-001, SOP-PRO-002 |
| VND | Vendor Management | SOP-VND-001, SOP-VND-002 |
| MAT | Material Management | SOP-MAT-001, SOP-MAT-002 |
| FLD | Field Operations | SOP-FLD-001, SOP-FLD-002 |
| CAL | Calibration | SOP-CAL-001, SOP-CAL-002 |
| TST | Testing | SOP-TST-001, SOP-TST-002 |
| WLD | Welding | SOP-WLD-001, SOP-WLD-002 |
| TRN | Training & Qualification | SOP-TRN-001, SOP-TRN-002 |
| NCR | Nonconformance / CAPA | SOP-NCR-001, SOP-NCR-002 |
| CLS | Closeout | SOP-CLS-001, SOP-CLS-002 |
| AUD | Audit | SOP-AUD-001, SOP-AUD-002 |

The SOP ID is cross-referenced to the XML section number in the master registry
(Section 4.1).

---

## Standard SOP Template

Every SOP follows this subsection structure:

| Subsection | Type | Content |
|------------|------|---------|
| **A** | PurposeAndScope | SOP ID, purpose (1-2 sentences), scope, applicability, exclusions |
| **B** | Requirements | Prerequisites, required certifications/training, tools/equipment needed, PPE, referenced standards |
| **C** | Procedures | Numbered step-by-step instructions with decision points, safety notes embedded at relevant steps, hold points clearly marked |
| **D** | Responsibilities | Who does what — uses ResponsibilityBlock for structured role assignments |
| **E** | Documentation | Records generated, forms to complete, where to upload (Procore folder), retention requirements |
| **F** | VerificationAndCompliance | How to verify the procedure was followed correctly, acceptance criteria, what triggers an NCR |

**Optional subsections** (appended as needed):

| Subsection | Type | When Used |
|------------|------|-----------|
| **G** | General | Decision trees, troubleshooting guides |
| **H** | General | Checklists (rendered as BulletList with checkboxes) |
| **I** | General | Reference tables, code extracts, specification data |

### XML Template

```xml
<Section id="sec-4.X" number="4.X">
    <Title>SOP: [Descriptive Title]</Title>
    <Subsections>
        <Subsection id="sec-4.X-A" letter="A" subsectionType="PurposeAndScope">
            <Title>Purpose and Scope</Title>
            <Content>
                <HeadingParagraph level="3">SOP ID: SOP-XXX-NNN</HeadingParagraph>
                <Paragraph>This procedure defines [what].</Paragraph>
                <HeadingParagraph level="3">Scope</HeadingParagraph>
                <Paragraph>Applies to [when/where/who].</Paragraph>
                <HeadingParagraph level="3">References</HeadingParagraph>
                <BulletList>
                    <Item>Module 3, Section 3.X — [Parent Program]</Item>
                    <Item>Module 2, Section 2.X — [Parent Procedure]</Item>
                    <Item>[Applicable code/standard]</Item>
                </BulletList>
            </Content>
        </Subsection>
        <Subsection id="sec-4.X-B" letter="B" subsectionType="Requirements">
            <Title>Prerequisites</Title>
            <Content>
                <HeadingParagraph level="3">Required Qualifications</HeadingParagraph>
                <BulletList>
                    <Item>[Certification or training required]</Item>
                </BulletList>
                <HeadingParagraph level="3">Tools and Equipment</HeadingParagraph>
                <BulletList>
                    <Item>[Required tools, calibrated instruments, PPE]</Item>
                </BulletList>
            </Content>
        </Subsection>
        <Subsection id="sec-4.X-C" letter="C" subsectionType="Procedures">
            <Title>Procedure</Title>
            <Content>
                <NumberedList>
                    <Item>Step 1: [Action with specific details]</Item>
                    <Item>Step 2: [Action with specific details]</Item>
                    <Item>HOLD POINT: [Do not proceed until verified by ___]</Item>
                    <Item>Step 3: [Action with specific details]</Item>
                </NumberedList>
                <Note>Safety: [Critical safety note embedded at relevant point]</Note>
            </Content>
        </Subsection>
        <Subsection id="sec-4.X-D" letter="D" subsectionType="Responsibilities">
            <Title>Responsibilities</Title>
            <Content>
                <ResponsibilityBlock>
                    <Role>Site Superintendent</Role>
                    <Responsibilities>
                        <Item>[Specific responsibility]</Item>
                    </Responsibilities>
                </ResponsibilityBlock>
            </Content>
        </Subsection>
        <Subsection id="sec-4.X-E" letter="E" subsectionType="Documentation">
            <Title>Records</Title>
            <Content>
                <BulletList>
                    <Item>[Form name] — upload to Procore [folder] within [timeframe]</Item>
                </BulletList>
            </Content>
        </Subsection>
        <Subsection id="sec-4.X-F" letter="F" subsectionType="VerificationAndCompliance">
            <Title>Verification</Title>
            <Content>
                <BulletList>
                    <Item>[How to verify procedure was followed correctly]</Item>
                    <Item>[Acceptance criteria]</Item>
                    <Item>[What triggers an NCR if not met]</Item>
                </BulletList>
            </Content>
        </Subsection>
    </Subsections>
    <SectionEnd>END OF SOP</SectionEnd>
</Section>
```

---

## SOP Lifecycle Management

### Status Values

| Status | Meaning | Who Can Set |
|--------|---------|------------|
| **Draft** | Under development, not approved for use | Author |
| **Under Review** | Technical review in progress | Author / QM |
| **Active** | Approved and in effect | Quality Manager |
| **Superseded** | Replaced by newer version | Quality Manager |
| **Retired** | No longer applicable | Quality Manager |

### Review Schedule

| SOP Risk Level | Review Frequency | Criteria |
|---------------|-----------------|----------|
| **High** (safety-critical, code-required) | Annual | Welding, pressure testing, hot work, calibration |
| **Standard** | Every 2 years | Most SOPs |
| **Low** (administrative) | Every 3 years | Document control, filing, reporting |

### Trigger-Based Review (immediate)

- Regulatory/code change affecting the procedure
- Incident or NCR traceable to the procedure
- Audit finding identifying a gap
- Equipment or technology change
- Process improvement identified
- Client requirement change

### Revision Tracking

Revisions tracked in the XML `<RevisionHistory>` element and in the SOP master
registry (Section 4.1). Major revisions increment the version (1.0 → 2.0);
minor revisions use decimals (1.0 → 1.1).

Training is required when an SOP undergoes a **major revision** that changes
procedural steps. Minor revisions (typos, clarifications) do not require
retraining.

---

## Complete SOP Catalog

### 4.1 — SOP Framework

> **SOP ID:** (none — this is the framework section, not a procedure)
>
> The master registry and guide for how SOPs are organized, written, reviewed,
> and maintained.

**Subsections:**
- 4.1-A Purpose and Scope — what Module 4 is, audience, how to use it
- 4.1-B SOP Numbering and Classification — numbering convention, category codes
- 4.1-C Standard SOP Template — required structure for all SOPs
- 4.1-D SOP Lifecycle — draft → review → active → superseded → retired
- 4.1-E Master SOP Registry — table of all SOPs with ID, title, category, owner,
  revision, status, review date
- 4.1-F Writing Guide — how to author a new SOP, style conventions, approval
  workflow

---

### Document Control & Records (4.2–4.5)

| Section | SOP ID | Title | Source | Audience | Priority |
|---------|--------|-------|--------|----------|----------|
| 4.2 | SOP-DOC-001 | Procore Document Distribution and Access Setup | M2 §2.1-B/E | PM | High |
| 4.3 | SOP-DOC-002 | Controlled Document Revision Management | M2 §2.1-C, M3 §3.6-H | PM, Supt | High |
| 4.4 | SOP-DOC-003 | As-Built Markup Maintenance and Final Submittal | M2 §2.1-C, §2.5-I | Supt, PM | High |
| 4.5 | SOP-DOC-004 | O&M Manual Collection, Assembly, and Delivery | M2 §2.5-H | PM | High |

**Consolidation notes:** The 123-item catalog identified 8 granular document
control procedures. These consolidate into 4 SOPs by grouping related steps:
- SOP-DOC-001 combines distribution setup + access control + alternative platforms
- SOP-DOC-002 combines revision tracking + obsolete doc removal + discrepancy reporting
- SOP-DOC-003 combines ongoing markups + final as-built submittal
- SOP-DOC-004 combines O&M collection scheduling + tracking + assembly + delivery

---

### Procurement & Vendor Management (4.6–4.10)

| Section | SOP ID | Title | Source | Audience | Priority |
|---------|--------|-------|--------|----------|----------|
| 4.6 | SOP-PRO-001 | Vendor Prequalification via Tradetapp | M2 §2.2-B, M3 §3.7-B | PM, Risk | High |
| 4.7 | SOP-PRO-002 | Bid Package Assembly and Competitive Sourcing | M2 §2.2-C | PM | High |
| 4.8 | SOP-PRO-003 | Bid Review, Evaluation, and Contract Award | M2 §2.2-C/D | PM | High |
| 4.9 | SOP-PRO-004 | Submittal Management and Approval Workflow | M2 §2.2-E, M3 §3.7-E | PM | High |
| 4.10 | SOP-VND-001 | Vendor Performance Assessment and Rating | M2 §2.6-C, M3 §3.7-G | PM | High |

---

### Site Logistics & Material Management (4.11–4.16)

| Section | SOP ID | Title | Source | Audience | Priority |
|---------|--------|-------|--------|----------|----------|
| 4.11 | SOP-FLD-001 | Site Office, Laydown, and Logistics Setup | M2 §2.3-C, M3 §3.6-D | Supt | High |
| 4.12 | SOP-MAT-001 | Delivery Verification and Receiving Inspection | M2 §2.3-D, M3 §3.6-C | Supt | High |
| 4.13 | SOP-MAT-002 | Material Storage, Segregation, and Protection | M2 §2.3-E, M3 §3.6-C | Supt | High |
| 4.14 | SOP-MAT-003 | Nonconforming Material Quarantine and Disposition | M2 §2.3-D, M3 §3.5-B | Supt, PM | High |
| 4.15 | SOP-FLD-002 | Daily Housekeeping and Waste Management | M2 §2.3-F | Supt | Medium |
| 4.16 | SOP-FLD-003 | Roof Protection Installation and Maintenance | M2 §2.3-F | Supt | High |

---

### Calibration & Instruments (4.17–4.22)

| Section | SOP ID | Title | Source | Audience | Priority |
|---------|--------|-------|--------|----------|----------|
| 4.17 | SOP-CAL-001 | Instrument Calibration Program Setup and Registry | M2 §2.4-C, M3 §3.4-B | Supt, QM | High |
| 4.18 | SOP-CAL-002 | Pressure Gauge and Test Instrument Calibration | M2 §2.4-C, M3 §3.4-B | Cal Tech | High |
| 4.19 | SOP-CAL-003 | Torque Wrench Calibration and Verification | M2 §2.3-G, M3 §3.4-B | Cal Tech | High |
| 4.20 | SOP-CAL-004 | Out-of-Tolerance Response and Impact Assessment | M2 §2.4-C, M3 §3.4-B | Supt, QM | High |
| 4.21 | SOP-CAL-005 | Calibration Certificate Receipt and Instrument Tagging | M2 §2.4-C | Supt | Medium |

**Note:** Section 4.22 reserved for future calibration SOPs.

---

### Testing — Hydrostatic, Pneumatic, Electrical (4.23–4.29)

| Section | SOP ID | Title | Source | Audience | Priority |
|---------|--------|-------|--------|----------|----------|
| 4.23 | SOP-TST-001 | Hydrostatic Test Planning, Execution, and Documentation | M2 §2.4-E, M3 §3.4-C | Supt, Tech | High |
| 4.24 | SOP-TST-002 | Pneumatic Test Safety Setup, Execution, and Documentation | M2 §2.4-F, M3 §3.4-C | Supt, Tech | High |
| 4.25 | SOP-TST-003 | Electrical Raceway Inspection and Megger Testing | M2 §2.4-G, M3 §3.4-C | Electrician | High |
| 4.26 | SOP-TST-004 | Electrical Functional Testing and Circuit Verification | M2 §2.4-G, M3 §3.4-C | Electrician | High |
| 4.27 | SOP-TST-005 | Test Documentation Organization and Storage | M2 §2.4-H, M3 §3.4-E | QM, PM | High |
| 4.28 | SOP-TST-006 | Third-Party and AHJ Inspection Coordination | M2 §2.4-I, M3 §3.4-F | PM | High |
| 4.29 | SOP-TST-007 | Hold Point and Witness Point Management | M2 §2.4-I, M3 §3.4-F | PM, Supt | High |

**Consolidation notes:** The 32 granular testing procedures identified in the
catalog consolidate into 7 SOPs. For example, hydrostatic test planning,
execution, depressurization, documentation, and failure response are all
subsection steps within SOP-TST-001 rather than separate SOPs.

---

### Welding & Personnel Qualification (4.30–4.35)

| Section | SOP ID | Title | Source | Audience | Priority |
|---------|--------|-------|--------|----------|----------|
| 4.30 | SOP-WLD-001 | Welder Qualification Verification and Assignment | M2 §2.4-D, M3 §3.2-D | Supt | High |
| 4.31 | SOP-WLD-002 | Welder Continuity Log Entry and Maintenance | M2 §2.4-D, M3 §3.2-D | Supt, Welder | High |
| 4.32 | SOP-WLD-003 | WPQ Test Piece Procedure and Documentation | M2 §2.4-D, M3 §3.2-F | QM, Inspector | High |
| 4.33 | SOP-WLD-004 | NDT Reporting and Weld Map Cross-Reference | M2 §2.4-D, M3 §3.2-H | Inspector, QM | High |
| 4.34 | SOP-TRN-001 | Craftsperson Certification Verification Before Assignment | M2 §2.3-J, M3 §3.3-B | Supt | High |
| 4.35 | SOP-TRN-002 | New Hire Orientation and Competency Assessment | M3 §3.3-D | Supt, HR | Medium |

---

### Continuous Improvement & NCR (4.36–4.40)

| Section | SOP ID | Title | Source | Audience | Priority |
|---------|--------|-------|--------|----------|----------|
| 4.36 | SOP-NCR-001 | NCR Initiation, Classification, and Containment | M2 (8 refs), M3 §3.5-B | All Field | High |
| 4.37 | SOP-NCR-002 | Root Cause Analysis (5-Why, Fishbone, Pareto) | M3 §3.5-C | QM, PM | High |
| 4.38 | SOP-NCR-003 | Corrective Action Development and Effectiveness Verification | M3 §3.5-D | QM, PM | High |
| 4.39 | SOP-NCR-004 | Project Debrief Planning and Facilitation | M2 §2.6-B, M3 §3.5-F | PM | High |
| 4.40 | SOP-NCR-005 | Lessons Learned Capture and Dissemination | M3 §3.5-E | PM, QM | Medium |

---

### Closeout, Startup & Commissioning (4.41–4.47)

| Section | SOP ID | Title | Source | Audience | Priority |
|---------|--------|-------|--------|----------|----------|
| 4.41 | SOP-CLS-001 | Internal Punch List Walk and Deficiency Documentation | M2 §2.5-B, M3 §3.6 | Supt, PM | High |
| 4.42 | SOP-CLS-002 | Client Punch List Coordination and Resolution | M2 §2.5-C | PM, Supt | High |
| 4.43 | SOP-CLS-003 | Pre-Startup Inspection and Regulatory Compliance | M2 §2.5-D, M3 §3.4-G | PM | High |
| 4.44 | SOP-CLS-004 | Equipment Startup and Commissioning Coordination | M2 §2.5-E, M3 §3.4-G | PM, Tech | High |
| 4.45 | SOP-CLS-005 | Testing and Balancing (TAB) Coordination | M2 §2.5-F, M3 §3.4-G | PM | High |
| 4.46 | SOP-CLS-006 | Client Training Scheduling and Documentation | M2 §2.5-G | PM | High |
| 4.47 | SOP-CLS-007 | Project Closeout Documentation Package | M2 §2.5-H/I/J | PM | High |

---

### Internal Audit & Management Review (4.48–4.50)

| Section | SOP ID | Title | Source | Audience | Priority |
|---------|--------|-------|--------|----------|----------|
| 4.48 | SOP-AUD-001 | Quality Manager Site Visit and Audit Execution | M3 §3.8-C/D | QM | High |
| 4.49 | SOP-AUD-002 | Audit Finding Classification and CAPA Routing | M3 §3.8-E/F | QM | High |
| 4.50 | SOP-AUD-003 | Monthly Performance Report and Quarterly Review | M3 §3.8-G | QM, Leadership | High |

---

## Quality Control & Execution SOPs (4.51–4.57)

> **Note:** These SOPs cover execution-phase quality activities that don't fit
> neatly into other categories. They're primarily superintendent-facing
> procedures for specialized work activities.

| Section | SOP ID | Title | Source | Audience | Priority |
|---------|--------|-------|--------|----------|----------|
| 4.51 | SOP-FLD-004 | Shop Inspection Planning, Execution, and Reporting | M2 §2.3-B, M3 §3.7-F | QM, PM | High |
| 4.52 | SOP-FLD-005 | Special Jointing Methods (Press Fit, Solder, Fusion, Grooved) | M2 §2.3-G | Foreman, Tech | High |
| 4.53 | SOP-FLD-006 | Equipment Installation Verification (Pre-Set and Post-Set) | M2 §2.3-I | Supt | High |
| 4.54 | SOP-FLD-007 | Bolted Flange Assembly and Torque Documentation | M2 §2.3-G | Mechanic, Supt | High |
| 4.55 | SOP-FLD-008 | Hot Tap Procedure Development and Execution | M2 §2.3-H | Supt, PM | High |
| 4.56 | SOP-FLD-009 | Pipe Flushing and Cleaning Procedures | M2 §2.3-H | Supt | High |
| 4.57 | SOP-FLD-010 | In-Process Quality Inspection and Documentation | M2 §2.3-J | Supt, QM | High |

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| **Total SOPs** | 50 (including framework section) |
| **Categories** | 11 |
| **Subsections per SOP** | 6-9 (A-F standard, G-I optional) |
| **Estimated subsections** | ~350-400 |
| **Estimated content blocks** | ~500-700 |
| **High priority** | 46 (92%) |
| **Medium priority** | 4 (8%) |

### SOPs by Parent Module 3 Program

| M3 Program | SOP Count | Section Range |
|-----------|-----------|---------------|
| §3.2 Welding Quality | 4 | 4.30-4.33 |
| §3.3 Training & Workforce | 2 | 4.34-4.35 |
| §3.4 Testing & Calibration | 12 | 4.17-4.29 |
| §3.5 CI/CAPA | 5 | 4.36-4.40 |
| §3.6 Field Operations Manual | 10 | 4.11-4.16, 4.51-4.57 |
| §3.7 Vendor Quality | 6 | 4.6-4.10, 4.51 |
| §3.8 Internal Audit | 3 | 4.48-4.50 |
| M2 only (no M3 parent) | 8 | 4.2-4.5, 4.41-4.47 (closeout) |

---

## Integration: Cross-Reference Map

### Module 2 → Module 4 (procedure → SOP)

| M2 Section | M4 SOP(s) |
|-----------|-----------|
| §2.1 Document Control | 4.2, 4.3, 4.4, 4.5 |
| §2.2 Procurement | 4.6, 4.7, 4.8, 4.9, 4.10 |
| §2.3 Execution | 4.11-4.16, 4.51-4.57 |
| §2.4 Inspections & Testing | 4.17-4.35 |
| §2.5 Closeout | 4.41-4.47 |
| §2.6 Continuous Improvement | 4.39, 4.40, 4.10 |

### Module 3 → Module 4 (program → SOPs)

| M3 Section | M4 SOP(s) |
|-----------|-----------|
| §3.2 Welding Quality | 4.30, 4.31, 4.32, 4.33 |
| §3.3 Training & Workforce | 4.34, 4.35 |
| §3.4 Testing & Calibration | 4.17-4.29, 4.43-4.45 |
| §3.5 CI/CAPA | 4.36, 4.37, 4.38, 4.39, 4.40 |
| §3.6 Field Operations | 4.11-4.16, 4.52-4.57 |
| §3.7 Vendor Quality | 4.6, 4.7, 4.8, 4.9, 4.10, 4.51 |
| §3.8 Internal Audit | 4.48, 4.49, 4.50 |

---

## Authoring Plan

### Phase 1 — Framework + High-Impact SOPs (priority)

Write these first — they fill the most critical gaps:

1. **4.1** SOP Framework (establishes template and registry)
2. **4.36** NCR Initiation (most cross-referenced gap in the QMS)
3. **4.30** Welder Qualification Verification (code-required)
4. **4.31** Welder Continuity Log (code-required)
5. **4.17** Calibration Program Setup (code-required)
6. **4.23** Hydrostatic Test (safety-critical)
7. **4.24** Pneumatic Test (safety-critical)

### Phase 2 — Execution & Field SOPs

8. **4.12** Receiving Inspection
9. **4.13** Material Storage & Segregation
10. **4.14** Nonconforming Material Quarantine
11. **4.51** Shop Inspection
12. **4.52** Special Jointing Methods
13. **4.53** Equipment Installation Verification
14. **4.54** Bolted Flange Assembly
15. **4.55** Hot Tap Procedures

### Phase 3 — Procurement, Closeout, Admin

16. **4.6-4.10** Procurement & Vendor SOPs
17. **4.41-4.47** Closeout SOPs
18. **4.2-4.5** Document Control SOPs
19. **4.48-4.50** Audit SOPs

### Phase 4 — Remaining SOPs

20. All remaining SOPs, additional SOPs identified during operations

---

## Module 1 & 2 Updates Required

Once Module 4 is authored:

### Module 1

| Section | Update |
|---------|--------|
| §1.1-E | Update description to list SOP categories and count |

### Module 2

| Section | Update |
|---------|--------|
| §2.1 V&C | Add: "For step-by-step procedures, see Module 4 Sections 4.2-4.5" |
| §2.2 V&C | Add: "For step-by-step procedures, see Module 4 Sections 4.6-4.10" |
| §2.3 V&C | Add: "For step-by-step procedures, see Module 4 Sections 4.11-4.16, 4.51-4.57" |
| §2.4 V&C | Add: "For step-by-step procedures, see Module 4 Sections 4.17-4.35" |
| §2.5 V&C | Add: "For step-by-step procedures, see Module 4 Sections 4.41-4.47" |
| §2.6 V&C | Add: "For step-by-step procedures, see Module 4 Sections 4.36-4.40" |

### Module 3

| Section | Update |
|---------|--------|
| §3.2 Welding Program | Add: "Implementing SOPs: Sections 4.30-4.33" |
| §3.3 Training Program | Add: "Implementing SOPs: Sections 4.34-4.35" |
| §3.4 Testing & Calibration | Add: "Implementing SOPs: Sections 4.17-4.29" |
| §3.5 CI/CAPA | Add: "Implementing SOPs: Sections 4.36-4.40" |
| §3.6 Field Operations | Add: "Implementing SOPs: Sections 4.11-4.16, 4.51-4.57" |
| §3.7 Vendor Quality | Add: "Implementing SOPs: Sections 4.6-4.10, 4.51" |
| §3.8 Internal Audit | Add: "Implementing SOPs: Sections 4.48-4.50" |

---

## Open Questions

- [ ] Should SOPs have a formal approval workflow (draft → review → approve) tracked in the database, or is XML version control sufficient?
- [ ] Do we need a `Checklist` subsectionType for field-ready SOPs, or can BulletList with "[ ]" markers suffice?
- [ ] Should the SOP master registry (Section 4.1-E) be a static XML table or a dynamic database query rendered in the web UI?
- [ ] What is the process for requesting a new SOP? (field identifies need → QM authors → review → publish)
- [ ] Should SOPs include estimated completion time for each procedure?
- [ ] Mobile/tablet rendering: do we need a separate "field view" for SOPs with larger fonts and simplified layout?
- [ ] Training integration: when an SOP is revised, how is retraining tracked? (link to workforce module?)
- [ ] Should SOPs be printable as standalone PDF documents for field binders?

---

*This document is version-controlled in `.planning/` and committed to the QMS
repository. Last updated: 2026-02-20.*
