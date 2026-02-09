"""
QMS - Quality Management System

Modular quality management for MEP division operations.

Modules:
    core        - Shared services (db, config, logging, paths)
    workforce   - Employees, departments, roles, permissions
    projects    - Projects, customers, jobs
    welding     - WPS/PQR/WPQ, welder registry, continuity, production welds
    qualitydocs - Quality manual CMS, procedures, forms, templates
    references  - Reference standards extraction and search
    pipeline    - Drawing extraction, conflict detection, specs
    engineering - Calculation library and design verification
    reporting   - Cross-module reporting and dashboards
"""

__version__ = "0.1.0"
