# Quality Management System - Modular Restructure Planning Prompt

## Implementation Progress (updated 2026-02-09)

### Phase 0: Foundation — COMPLETE
- Package: `D:\qms\` installed editable (`pip install -e .`)
- CLI: `qms version`, `qms migrate`, 8 module sub-commands registered
- 224 tables (including FTS virtual tables) across 8 schema files
- Core services: db.py, config.py, logging.py, paths.py, output.py
- Git: `https://github.com/bjohnson1-stellar/QMS.git` branch `main`

### Phase 1: Port Business Logic — COMPLETE
**Batch 1** (4 modules, ported from QC-DR/ scripts):
| Module | Source → Target | Lines | CLI Commands |
|--------|----------------|-------|-------------|
| welding | 4 files → intake.py, importer.py, weekly.py, notifications.py | 2,404 | dashboard, continuity, import-wps, import-weekly, check-notifications |
| qualitydocs | load_quality_manual.py → loader.py | 878 | load-module, summary, search, detail |
| references | extract_reference.py → extractor.py | 541 | extract, list, search, clauses |
| projects | scan_projects.py → scanner.py | 674 | scan, list, summary |

**Batch 2** (3 modules):
| Module | Source → Target | Lines | CLI Commands |
|--------|----------------|-------|-------------|
| pipeline | 4 SIS files → common.py, importer.py, processor.py | 2,399 | status, queue, import-drawing, import-batch, process |
| workforce | employee_management.py + sis_employee_import.py → merged employees.py + sis_import.py | 797 | list, import-csv, import-from-sis, bulk-update |
| vectordb | 3 vector/embed files → embedder.py, indexer.py, search.py | 1,619 | index, search, status, rebuild |

**Package totals**: 56 files, 15,167 lines

### Phase 2: Remaining Work
| Module | Work Type | Source | Status |
|--------|-----------|--------|--------|
| engineering | **Integration** — move `D:\Eng\` (11,777 lines, 30 files) into `qms/engineering/` | `D:\Eng\` refrig_calc library | Not started |
| reporting | **New code** — cross-module dashboards and reports | No source exists | Not started |
| repo cleanup | Move pyproject.toml to repo root, delete QC-DR/, Eng/ | - | Not started |

### Source Script Mapping (QC-DR/ → qms/)
| Source (D:\QC-DR\) | Target (D:\qms\) | Status |
|---------------------|-------------------|--------|
| weld_intake.py | welding/intake.py | Ported |
| weld_excel_import.py | welding/importer.py | Ported |
| weld_weekly_import.py | welding/weekly.py | Ported |
| weld_notifications.py | welding/notifications.py | Ported |
| scripts/load_quality_manual.py | qualitydocs/loader.py | Ported |
| extract_reference.py | references/extractor.py | Ported |
| scripts/scan_projects.py | projects/scanner.py | Ported |
| sis_common.py | pipeline/common.py | Ported |
| sis_import.py | pipeline/importer.py | Ported |
| sis_bulk_import.py | pipeline/importer.py | Ported |
| sis_process_and_import.py | pipeline/processor.py | Ported |
| employee_management.py | workforce/employees.py | Ported |
| sis_employee_import.py | workforce/sis_import.py | Ported |
| embed_queue.py | vectordb/embedder.py | Ported |
| index_vectordb.py | vectordb/indexer.py | Ported |
| vector_db.py | vectordb/search.py | Ported |
| D:\Eng\* (30 files) | engineering/* | **Not started** |

---

## Original Planning Document (below)

## Executive Summary

I need to restructure a comprehensive quality management system from an ad-hoc collection of scripts in `D:\` into a professional, modular architecture that can scale from single-user local deployment to division-wide multi-user deployment without hindering initial development.

## Current State Assessment

### Directory Structure (Current)
```
D:\
├── QC-DR/                    # All quality/SIS code (Python scripts, schemas)
├── Eng/                      # Engineering calculations library
├── Projects/                 # Project-specific data (by project number/discipline)
├── Quality Documents/        # QM document storage
├── Inbox/                    # Unified document intake
├── VectorDB/                 # ChromaDB vector database
├── quality.db               # Main SQLite database (16MB)
└── tmp/                     # Temporary files
```

### Technology Stack
- **Language:** Python
- **Database:** SQLite (`quality.db`, 16MB)
- **Vector DB:** ChromaDB
- **Deployment:** Local, single-user (MVP)
- **Interface:** CLI-based (future GUI planned)

### Current Modules/Features (From Database Analysis)

**Drawing Review System (SIS)**
- Multi-discipline drawing extraction and conflict detection
- Disciplines: Plumbing, Mechanical, Refrigeration, Refrigeration-Controls, Electrical, Utility, Civil, Architectural, Fire-Protection, Structural, General
- 170+ database tables covering all disciplines
- Automated intake, classification, and routing

**Welding Program (ASME IX Compliance)**
- WPS/PQR/WPQ/BPS/BPQR/BPQ management (60+ weld_* tables)
- Welder qualification tracking and certification
- Continuity logging and expiration tracking
- Automated notifications and dashboard views
- Document generation and revision control

**Employee/Workforce Management**
- Employee registry with contact information
- Employment history tracking
- Certification management (all trades)
- Department and organizational hierarchy
- Skills matrix and permission management
- Integration with welding program (welder registry)

**Quality Manual (QM) Content Management**
- XML module-based QM structure
- Procedures, forms, templates, records
- Full-text search (FTS)
- Cross-references and code references
- Revision history and document chains
- Responsibility assignments

**Specification Management**
- Spec document intake and parsing
- Section extraction (CSI division-based routing)
- Master spec baseline tracking
- Variation detection across projects
- Integration with drawing review

**Reference Standards Extraction**
- Reference document parsing (ASME, ANSI, etc.)
- Clause extraction with FTS indexing
- Section-based parallel extraction
- Procedure linking

**Engineering Calculations**
- Refrigeration-focused library (Eng/)
- Line sizing, load calculations, equipment selection
- Pipe stress analysis and support design
- Safety relief valve sizing
- Modular calculation framework with CLI

**Project Management**
- Project tracking with codes and patterns
- Customer relationship tracking
- Job/project linking with PM details
- Multi-view dashboards

**Document Intake & Routing**
- Unified inbox for ALL document types
- Pattern-based classification (config.yaml)
- ZIP/folder extraction (Procore support)
- Conflict and duplicate detection
- Automated routing to correct locations

**Reporting & Analytics**
- Conflict reports, extraction accuracy
- Quality dashboards
- Compliance matrices
- Expiration tracking across all modules

### Current Problems

1. **Structure:**
   - All code in root or single `QC-DR/` directory
   - Multiple schema files (schema.sql, schema-welding.sql, schema-employees.sql, etc.) with no clear organization
   - Scripts mixed with documentation and configuration
   - No module boundaries or interfaces

2. **Naming:**
   - Inconsistent conventions (sis_, weld_, qm_, some without prefix)
   - Ad-hoc file naming
   - Database table naming varies by domain

3. **Scalability:**
   - Monolithic database (quality.db)
   - No separation of concerns
   - Difficult to develop features independently
   - No clear path to multi-user deployment

4. **Development:**
   - Hard to onboard new features
   - Changes risk breaking unrelated functionality
   - No clear ownership of code areas
   - Testing boundaries unclear

## Goals & Requirements

### Primary Goals
1. **Modular Architecture:** Clear module boundaries with defined interfaces
2. **Independent Development:** Develop each module as needed without blocking others
3. **Scalability:** Foundation that supports single-user → multi-user transition
4. **Simplicity:** Avoid over-engineering while enabling future growth
5. **Consistency:** Unified naming conventions and coding standards
6. **Maintainability:** Clear structure that's easy to understand and extend

### Technical Requirements
1. **Database Strategy:** Decide on single vs. multi-database approach
2. **Module Communication:** Define inter-module data sharing and APIs
3. **Shared Services:** Identify common utilities (logging, config, DB access)
4. **Configuration Management:** Centralized vs. distributed config
5. **Testing Strategy:** Module-level testing without dependencies
6. **Deployment:** Support local development and future production deployment

### Functional Requirements
1. **Preserve Existing Functionality:** All current features must continue working
2. **Data Migration:** Move existing data to new structure
3. **Backward Compatibility:** Gradual migration, not big-bang rewrite
4. **Documentation:** Clear module documentation and API contracts
5. **CLI Access:** Maintain command-line interface for all features
6. **Future GUI:** Architecture must support future web/desktop GUI

## Module Candidates

### User-Identified Modules
Based on your input, these modules are established as valuable:

1. **Workforce Management**
   - Employee registry, contacts, employment history
   - Department/organizational structure
   - Cross-module integration (links to certifications, projects, etc.)

2. **Qualifications Management** (General Trades)
   - Certification tracking for all trades (non-welding)
   - Expiration tracking and notifications
   - Skills matrix management

3. **Project Management**
   - Project registry and tracking
   - Customer relationships
   - Job/project hierarchy
   - Project team assignments

4. **Welding Program**
   - WPS/PQR/WPQ/BPS document management
   - Code compliance (ASME IX, etc.)
   - Welder registry and qualifications
   - Production weld tracking
   - Continuity logging
   - Document generation

5. **Welding Certification**
   - Welder qualification tracking
   - Certification expiration management
   - Automated document creation
   - Test result tracking

6. **Welder Continuity**
   - Continuity event logging
   - Automatic status tracking
   - Notification system
   - Compliance monitoring

7. **Quality Program**
   - Overall quality system coordination
   - Dashboard and reporting
   - Compliance management

8. **Quality Manual (CMS)**
   - Content management for QM and quality documents
   - Module/section/clause structure
   - Revision control
   - Cross-referencing
   - Full-text search

9. **Drawing Review (SIS)**
   - Multi-discipline drawing extraction
   - Conflict detection
   - Specification integration
   - Automated reporting

10. **Equipment Submittal Review**
    - Currently limited functionality
    - Needs expansion

11. **Engineering Module**
    - Calculation library
    - Workflows supporting other modules
    - Design verification
    - Code compliance calculations

12. **Customer Requirement Review**
    - Contract review
    - Requirement tracking
    - Compliance verification

13. **Field Operations**
    - Production tracking
    - Field quality control
    - Inspection management

14. **Continuous Improvement**
    - Metrics and analytics
    - Trend analysis
    - Corrective action tracking

15. **Warranty Management**
    - Warranty tracking
    - Issue management
    - Customer communication

### System-Identified Potential Modules
Based on database and code analysis:

16. **Document Management (Core)**
    - Unified intake and routing
    - Document classification
    - Storage management
    - Revision control (cross-module)

17. **Specification Management**
    - Spec document processing
    - CSI division routing
    - Master spec baseline
    - Variation tracking

18. **Reference Standards Library**
    - Reference document extraction
    - Clause management and search
    - Code reference linking

19. **Reporting & Analytics**
    - Cross-module reporting
    - Dashboard generation
    - Data visualization
    - Export capabilities

20. **Notification & Alert System**
    - Configurable notifications
    - Expiration alerts
    - Compliance reminders
    - Multi-channel delivery

21. **Compliance & Audit Management**
    - Audit scheduling and tracking
    - Finding management
    - Corrective action tracking
    - Compliance reporting

22. **Training Management**
    - Training requirements
    - Course tracking
    - Competency verification
    - Integration with certifications

23. **Configuration Management**
    - System-wide configuration
    - Module-specific settings
    - User preferences
    - Pattern/rule management

24. **Integration/API Layer**
    - Inter-module communication
    - External system integration
    - Future API for GUI/mobile

25. **User Management & Security**
    - User authentication (future multi-user)
    - Role-based permissions
    - Audit logging
    - Session management

## Architecture Questions to Address

### 1. Module Granularity
**Question:** How should modules be grouped/split?

**Considerations:**
- Some modules are tightly coupled (Welding Program ↔ Welding Certification ↔ Welder Continuity)
- Some are independent (Engineering calculations, Document Management)
- What's the right level of granularity to enable independent development without creating excessive integration complexity?

**Options:**
- A. Many small modules (20+ modules, each very focused)
- B. Moderate modules (8-12 modules, logical groupings)
- C. Domain-driven modules (4-6 large domains with sub-modules)

### 2. Database Architecture
**Question:** Single database or multiple databases?

**Current:** Monolithic `quality.db` (170+ tables)

**Options:**
- A. **Single Database:** All modules share quality.db
  - Pros: Simple, easy cross-module queries, transactions
  - Cons: Tight coupling, hard to separate modules

- B. **Database per Module:** Each module has its own database
  - Pros: True independence, clear boundaries
  - Cons: Complex cross-module queries, distributed transactions

- C. **Hybrid:** Shared core DB + module-specific DBs
  - Pros: Balance of independence and integration
  - Cons: Complexity in deciding what goes where

- D. **Schema-based Separation:** Single DB, logical schemas/prefixes
  - Pros: Logical separation, easy queries
  - Cons: Still coupled at DB level

### 3. Directory Structure
**Question:** How should code be organized on disk?

**Options:**
- A. Monorepo with module subdirectories
  ```
  D:\
  ├── modules/
  │   ├── welding/
  │   ├── drawings/
  │   ├── quality-manual/
  │   └── ...
  ├── shared/
  ├── config/
  └── data/
  ```

- B. Separate repositories per module (with shared libraries)
  ```
  D:\
  ├── module-welding/
  ├── module-drawings/
  ├── shared-core/
  └── ...
  ```

- C. Domain-based organization
  ```
  D:\
  ├── quality-system/
  ├── engineering/
  ├── operations/
  └── ...
  ```

### 4. Inter-Module Communication
**Question:** How do modules share data and functionality?

**Options:**
- A. Direct database access (shared tables/views)
- B. Service layer with defined APIs
- C. Event-driven messaging
- D. Shared library with data access objects

### 5. Shared Services
**Question:** What should be shared across all modules?

**Candidates:**
- Configuration management
- Database connection pooling
- Logging and monitoring
- Authentication/authorization (future)
- File storage management
- Notification delivery
- Reporting engine
- Document generation
- Search indexing (FTS, vector DB)

### 6. Development Strategy
**Question:** How to build the new system efficiently?

**Options:**
- A. **Clean Rebuild:** Start from architecture, build modules in priority order
- B. **Salvage & Refactor:** Keep working code, restructure around it
- C. **Hybrid:** New architecture with ported logic from existing code

**Note:** System is not live, so no migration/backward compatibility needed.

### 7. Configuration Management
**Question:** How should configuration be handled?

**Current:** Single `config.yaml` in QC-DR/

**Options:**
- A. Single monolithic config file
- B. Config per module with central registry
- C. Database-stored configuration
- D. Environment-based configuration (different files per environment)

### 8. Naming Conventions
**Question:** How to standardize naming across the system?

**Areas needing standards:**
- Python modules and packages
- Database tables and columns
- CLI commands
- Configuration keys
- File and directory names
- API endpoints (future)

### 9. Testing Strategy
**Question:** How to structure tests for independent modules?

**Considerations:**
- Unit tests per module
- Integration tests across modules
- End-to-end tests
- Test data management
- CI/CD pipeline (future)

### 10. GUI Preparation
**Question:** What architectural decisions support future GUI development?

**Considerations:**
- Separation of business logic from CLI
- API design (REST, GraphQL, etc.)
- Data validation and serialization
- Authentication/authorization hooks
- Real-time updates (WebSocket, polling, etc.)

## Design Philosophy & Constraints

### Your Stated Principles
1. **Modularity:** Framework allows developing most important features without restricting future features
2. **Simplicity Preference:** Value simple solutions, but recognize strategic complexity enables better outcomes
3. **Pragmatism:** You're the only quality manager for entire MEP division (6+ trade scopes)
4. **Automation Focus:** Manual = doesn't get done, so automation is critical
5. **Incremental Development:** Build what's needed when it's needed

### Key Constraints
- **Single Developer (Initially):** You're building this alone initially
- **Local Deployment (MVP):** No server infrastructure required for MVP
- **Division Rollout (Future):** Must support multi-user without major rework

### CRITICAL: Clean Slate Freedom
- **System is NOT live yet** - no production users depending on it
- **Can start from scratch** - no backward compatibility required
- **Data can be rebuilt** - can re-import/re-extract from source documents
- **No migration constraints** - free to design ideal architecture

This means: Design the RIGHT architecture, not a compromised one. Be bold with structural decisions.

## Deliverables Requested

### 1. Proposed Module Structure
- List of recommended modules with clear boundaries
- Rationale for grouping/splitting decisions
- Module dependency diagram
- Interface contracts between modules

### 2. Directory Structure
- Recommended file/folder organization
- Location of shared code vs. module-specific code
- Configuration file placement
- Data storage strategy (DB files, vector DB, documents)

### 3. Database Architecture
- Single vs. multi-database decision with justification
- Schema organization strategy
- Migration plan for existing 170+ tables
- Strategy for cross-module queries

### 4. Naming Conventions
- Python package/module naming standard
- Database object naming standard (tables, columns, views, indexes)
- CLI command naming standard
- Configuration key naming standard
- File/directory naming standard

### 5. Shared Services Architecture
- List of shared services/libraries
- Where they live in directory structure
- How modules access them
- Versioning and dependency management

### 6. Inter-Module Communication Strategy
- How modules share data
- How modules invoke each other's functionality
- Event/notification patterns
- API contracts (for future GUI)

### 7. Development Roadmap
- Phased approach to building modules
- Which modules to build first (priority order and dependencies)
- How to port/salvage existing code
- Testing strategy for new modules
- Timeline estimates for MVP vs. full system

### 8. Development Workflow
- How to add a new module
- How to add features to existing module
- Dependency management
- Testing approach
- Documentation requirements

### 9. Multi-User Preparation
- Authentication/authorization strategy
- Data isolation (if needed)
- Concurrent access handling
- User management module design

### 10. Future GUI Considerations
- Business logic separation from presentation
- API design principles
- Data serialization strategy
- Real-time update mechanisms

## Success Criteria

The proposed architecture should:

1. ✅ **Enable Independent Development:** New features can be added without touching unrelated code
2. ✅ **Maintain Simplicity:** Not over-engineered, understandable by a single developer
3. ✅ **Support Scaling:** Path from single-user local to multi-user division deployment exists
4. ✅ **Modern & Maintainable:** Clean structure, consistent naming, industry best practices
5. ✅ **Facilitate Testing:** Modules can be tested independently
6. ✅ **Multi-User Ready:** Authentication, permissions, concurrent access built-in (even if initially unused)
7. ✅ **GUI-Ready:** Business logic separated from CLI, proper API layer from day one
8. ✅ **Be Pragmatic:** Balances ideal architecture with practical constraints (single developer, incremental delivery)
9. ✅ **Production-Ready Foundation:** Even MVP should have proper logging, error handling, security basics

## Context for Planning

### User Role
- Solo quality manager for entire division
- Responsible for 6+ trade scopes (more coming)
- No formal software engineering team
- Self-performing MEP contractor

### Current System Usage
- Daily document intake (drawings, specs, QM docs)
- Welding program management (certifications, continuity)
- Employee/workforce tracking
- Project tracking across multiple disciplines
- Quality manual maintenance
- Engineering calculations for design support

### Pain Points Being Addressed
- Everything manual → doesn't get done
- No consistency in processes
- Difficult to find information
- Hard to track compliance and expirations
- Manual reporting is time-consuming
- Can't scale to handle all responsibilities

### Vision
A single integrated software system that handles all aspects of the quality manager role, enabling one person to effectively manage quality across an entire division through automation and intelligent workflows.

## Additional Information

### Technology Preferences
- Python (established, familiar)
- SQLite (proven for single-user, upgrade path to PostgreSQL for multi-user)
- ChromaDB (vector search established)
- CLI-first (GUI later)
- Minimal external dependencies

### Integration Points (Future)
- ERP system integration
- Document management systems (Procore, SharePoint)
- Email/notification systems
- Mobile access
- External reporting/dashboards

### Non-Functional Requirements
- **Performance:** Local operations should be fast (<1s for queries, <5s for reports)
- **Reliability:** Data integrity is critical (construction/safety domain)
- **Usability:** CLI should be intuitive, minimal learning curve
- **Documentation:** Self-documenting code + clear user guides
- **Backup/Recovery:** Simple backup strategy (file-based DB helps)

---

## Planning Instructions

Please analyze this system and provide:

1. A recommended modular architecture with specific module definitions
2. Concrete directory structure with example paths
3. Database architecture decision with migration strategy
4. Naming convention standards across all areas
5. Phased migration plan with specific steps
6. Development workflow documentation
7. Diagrams (ASCII art or mermaid) showing:
   - Module dependency graph
   - Directory structure tree
   - Database architecture
   - Data flow between modules

Focus on practical, implementable recommendations that balance ideal architecture with the reality of a single-developer, incrementally-developed system that needs to work today while preparing for tomorrow's scale.
