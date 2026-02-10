"""Smoke-test that all public APIs can be imported without error.

Catches stale imports, circular dependencies, and missing deps.
No DB or fixtures needed — pure import checks.
"""


def test_import_qms():
    import qms
    assert qms.__version__ == "0.1.0"


def test_import_core():
    from qms.core import get_db, get_config, get_logger, QMS_PATHS, migrate_all, execute_query  # noqa: F401


def test_import_engineering():
    from qms.engineering import (  # noqa: F401
        DisciplineCalculator, CalculationResult, ValidationResult, ValidationStatus,
    )


def test_import_engineering_refrigeration():
    from qms.engineering.refrigeration import (  # noqa: F401
        RefrigerationCalculator, run_line_sizing, run_relief_valve,
        run_pump, run_ventilation, run_charge,
    )


def test_import_refrig_calc():
    from qms.engineering.refrig_calc import (  # noqa: F401
        NH3Properties, LineSizing, ReliefValveSizer, PumpCalculator,
        MachineRoomVentilation, ChargeCalculator, get_refrigerant,
    )


def test_import_engineering_validators():
    from qms.engineering.validators import (  # noqa: F401
        parse_pipe_size, compare_sizes, parse_line_number,
    )


def test_import_engineering_db():
    from qms.engineering.db import (  # noqa: F401
        save_calculation, save_validation, get_project_by_number,
        get_project_lines, get_project_equipment,
    )


def test_import_workforce():
    from qms.workforce.employees import (  # noqa: F401
        create_employee, find_employee_by_number, find_employee_by_email,
        update_employee, terminate_employee, import_weekly_personnel,
    )


def test_import_workforce_sis():
    from qms.workforce.sis_import import (  # noqa: F401
        import_employees_from_sis, find_existing_employee,
    )


def test_import_cli_main():
    from qms.cli.main import app, main  # noqa: F401


def test_import_core_output():
    from qms.core.output import format_result, OutputFormat  # noqa: F401


def test_import_engineering_output():
    from qms.engineering.output import format_result, OutputFormat, format_validation_report  # noqa: F401


def test_import_core_paths():
    from qms.core.paths import ensure_directory  # noqa: F401
