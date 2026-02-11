# SharePoint + Power App Integration for Welding Certification Forms

## Architecture

```
QMS (SQLite)                    SharePoint Online                Power App (Teams)
┌──────────────┐   Graph API   ┌─────────────────────┐         ┌──────────────────┐
│ welding DB   │──── sync ────>│ SharePoint Lists    │<───────>│ Certification    │
│ tables       │               │ (lookup data)       │  native │ Form             │
└──────────────┘               ├─────────────────────┤         │                  │
                               │ Submissions List    │<────────│ Supervisor fills │
                               └──────────┬──────────┘         │ & submits        │
                                          │                    └──────────────────┘
                               ┌──────────▼──────────┐
                               │ Power Automate       │  (optional)
                               │ - Email on submit    │
                               │ - Status updates     │
                               └──────────────────────┘
                                          │
QMS (SQLite)                              │
┌──────────────┐   Graph API              │
│ import       │<──── pull ───────────────┘
│ submissions  │
└──────────────┘
```

## SharePoint Lists Schema

### 1. WeldActiveWelders
Source: `weld_welder_registry WHERE status = 'active'`

| Column | SP Type | Source Column | Notes |
|--------|---------|---------------|-------|
| Title | Single line | `welder_stamp` | SP requires Title; use stamp as primary key |
| EmployeeNumber | Single line | `employee_number` | |
| DisplayName | Single line | `display_name` | "LastName, FirstName" |
| FirstName | Single line | `first_name` | |
| LastName | Single line | `last_name` | |
| Department | Single line | `department` | |
| Supervisor | Single line | `supervisor` | |
| BusinessUnit | Single line | `business_unit` | |
| Status | Choice | `status` | active/inactive |

### 2. WeldProcesses
Source: Hardcoded from `VALID_PROCESSES`

| Column | SP Type | Source | Notes |
|--------|---------|--------|-------|
| Title | Single line | process code | SMAW, GTAW, etc. |
| FullName | Single line | — | "Shielded Metal Arc Welding", etc. |

### 3. WeldActiveWPS
Source: `weld_wps WHERE status IN ('active', 'draft')`

| Column | SP Type | Source Column | Notes |
|--------|---------|---------------|-------|
| Title | Single line | `wps_number` | |
| Revision | Single line | `revision` | |
| WPSTitle | Single line | `title` | |
| Status | Choice | `status` | draft/active |
| ApplicableCodes | Multi-line | `applicable_codes` | |
| IsSWPS | Yes/No | `is_swps` | |

### 4. WeldPositions
Source: Hardcoded from `POSITION_QUALIFIES`

| Column | SP Type | Source | Notes |
|--------|---------|--------|-------|
| Title | Single line | position code | 1G, 2G, ... 6GR, 1F ... 5F |
| PositionType | Choice | — | Groove / Fillet |
| QualifiesFor | Multi-line | — | JSON array of positions this qualifies for |

### 5. WeldBaseMaterials
Source: `MATERIAL_P_NUMBERS` + `weld_wps_base_metals`

| Column | SP Type | Source | Notes |
|--------|---------|--------|-------|
| Title | Single line | material spec | A53, A106, SS304, etc. |
| PNumber | Number | p_number | 1, 8, etc. |
| MaterialType | Single line | — | "Carbon Steel", "Stainless Steel" |

### 6. WeldFillerMetals
Source: `FILLER_METAL_INFO`

| Column | SP Type | Source | Notes |
|--------|---------|--------|-------|
| Title | Single line | filler code | 6010, 7018, ER70S, etc. |
| FNumber | Number | f_number | 3, 4, 6 |
| Process | Single line | process | SMAW, GTAW |
| AWSClass | Single line | description | E6010, E7018, ER308L, etc. |

### 7. WeldWPQStatus
Source: `weld_wpq JOIN weld_welder_registry`

| Column | SP Type | Source | Notes |
|--------|---------|--------|-------|
| Title | Single line | `wpq_number` | e.g. "Z-01-SMAW" |
| WelderStamp | Single line | via JOIN | |
| WelderName | Single line | via JOIN | |
| ProcessType | Single line | `process_type` | |
| PNumber | Number | `p_number` | |
| FNumber | Number | `f_number` | |
| PositionsQualified | Multi-line | `positions_qualified` | |
| TestDate | Date | `test_date` | |
| ExpirationDate | Date | `current_expiration_date` | |
| Status | Choice | `status` | active/expired/lapsed |
| ContinuityStatus | Choice | computed | OK/AT_RISK/LAPSED |
| DaysRemaining | Number | computed | |

### 8. WeldCertFormSubmissions (Write-back from Power App)
This is where supervisors submit completed certification forms.

| Column | SP Type | Filled By | Notes |
|--------|---------|-----------|-------|
| Title | Single line | Auto | "WPQ-{stamp}-{date}" |
| WelderStamp | Single line | Dropdown | From WeldActiveWelders |
| WelderName | Single line | Auto-fill | Populated on welder select |
| ProcessType | Single line | Dropdown | From WeldProcesses |
| WPSNumber | Single line | Dropdown | From WeldActiveWPS |
| TestPosition | Single line | Dropdown | From WeldPositions |
| BaseMaterial | Single line | Dropdown | From WeldBaseMaterials |
| FillerMetal | Single line | Dropdown | From WeldFillerMetals |
| TestDate | Date | Supervisor | Date of test |
| TestResult | Choice | Supervisor | Pass/Fail |
| BendTestResult | Choice | Supervisor | Pass/Fail/N-A |
| VisualTestResult | Choice | Supervisor | Pass/Fail/N-A |
| RTResult | Choice | Supervisor | Pass/Fail/N-A |
| Examiner | Single line | Supervisor | QC examiner name |
| Witness | Single line | Supervisor | Witness name |
| ProjectNumber | Single line | Supervisor | Project context |
| Notes | Multi-line | Supervisor | |
| SubmittedBy | Person | Auto | Current user |
| SubmittedDate | Date | Auto | |
| ImportedToQMS | Yes/No | Sync | Set true after import |

## Cascading Dropdown Logic (Power App Formulas)

```
// 1. Welder dropdown
ddWelder.Items = Filter(WeldActiveWelders, Status.Value = "active")

// 2. Process dropdown — show processes this welder is qualified for
ddProcess.Items = Distinct(
    Filter(WeldWPQStatus,
        WelderStamp = ddWelder.Selected.Title
        And Status.Value = "active"
    ),
    ProcessType
)

// 3. WPS dropdown — filter to WPS that support selected process
// (or show all active WPS if no process-WPS link exists yet)
ddWPS.Items = Filter(WeldActiveWPS, Status.Value = "active")

// 4. Position dropdown — show positions for selected position type
ddPosition.Items = Filter(WeldPositions,
    PositionType.Value = "Groove"  // or based on context
)

// 5. Base material — show all
ddBaseMaterial.Items = WeldBaseMaterials

// 6. Filler metal — filter by process
ddFillerMetal.Items = Filter(WeldFillerMetals,
    Process = ddProcess.Selected.Title
)

// Auto-fill welder name when welder is selected
lblWelderName.Text = ddWelder.Selected.DisplayName
```

## Sync Commands

```bash
# Push all lookup data to SharePoint
qms welding sync-sharepoint --push

# Push specific list only
qms welding sync-sharepoint --push --list welders
qms welding sync-sharepoint --push --list wpq-status

# Pull form submissions back into QMS
qms welding sync-sharepoint --pull

# Preview what would sync (dry run)
qms welding sync-sharepoint --push --dry-run

# Check sync status
qms welding sync-sharepoint --status
```

## Configuration (config.yaml addition)

```yaml
sharepoint:
  tenant_id: ""          # Azure AD tenant ID
  client_id: ""          # App registration client ID
  client_secret: ""      # App registration client secret (or use env var)
  site_name: ""          # SharePoint site name (e.g., "QualityManagement")
  site_id: ""            # SharePoint site ID (auto-discovered from site_name)
  list_prefix: "Weld"    # Prefix for all synced lists
```

## Azure AD App Registration Setup

1. Go to Azure Portal > Azure Active Directory > App registrations
2. New registration: "QMS SharePoint Sync"
3. API permissions:
   - Microsoft Graph > Application permissions:
     - `Sites.ReadWrite.All` (create/update lists)
     - `Sites.Read.All` (read site info)
   - Grant admin consent
4. Certificates & secrets > New client secret
5. Copy: Tenant ID, Client ID, Client Secret into config.yaml

## Dataverse for Teams — Verdict

**NOT VIABLE** for direct Python sync. Key limitations:
- No direct API access from external applications
- Only apps/flows/bots running inside Teams can access the runtime
- No custom connectors in Teams-only Power Apps
- Microsoft's official Dataverse SDK for Python does NOT work with Dataverse for Teams

**Possible future path:** If the org upgrades to full Dataverse ($20/user/mo),
the new [Dataverse SDK for Python](https://learn.microsoft.com/en-us/python/api/dataverse-sdk-docs-python/dataverse-overview) (released Dec 2025)
provides direct DML/DDL operations from Python.

## Implementation Phases

### Phase 1 (Current): SharePoint Lists Sync
- [x] Research Dataverse for Teams viability
- [ ] Build `sharepoint.py` sync module
- [ ] Add CLI commands
- [ ] Add config.yaml section
- [ ] Test with real SharePoint site

### Phase 2: Power App Build
- [ ] Create canvas app in Teams
- [ ] Build certification form with cascading dropdowns
- [ ] Add form validation rules
- [ ] Publish to Teams channel

### Phase 3: Submission Import
- [ ] Build pull mechanism for form submissions
- [ ] Map submissions to WPQ/production weld records
- [ ] Add notification on new submissions

### Phase 4 (Future): Power Automate Enhancements
- [ ] Email notification to QC manager on form submit
- [ ] Auto-generate PDF certificate from submission data
- [ ] Scheduled sync (every 15 min or on-demand)
