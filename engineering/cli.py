"""Engineering CLI sub-commands."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def history(limit: int = typer.Option(20, help="Number of records")):
    """Show recent calculation history."""
    from qms.core import get_db

    with get_db(readonly=True) as conn:
        rows = conn.execute(
            "SELECT timestamp, discipline, calculation_type, equipment_tag, line_number "
            "FROM eng_calculations ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()

    if not rows:
        typer.echo("No calculations recorded.")
        return

    for r in rows:
        tag = r['equipment_tag'] or r['line_number'] or ''
        typer.echo(f"  {r['timestamp'][:16]}  {r['discipline']:<12} {r['calculation_type']:<20} {tag}")


# ---------------------------------------------------------------------------
# Calculation commands
# ---------------------------------------------------------------------------

@app.command("line-sizing")
def line_sizing(
    capacity_tons: float = typer.Option(100, help="Refrigeration capacity (tons)"),
    suction_temp: float = typer.Option(28, help="Suction temperature (F)"),
    condensing_temp: float = typer.Option(95, help="Condensing temperature (F)"),
    length: float = typer.Option(100, help="Pipe length (ft)"),
    line_type: str = typer.Option("dry", help="Line type: dry, wet, liquid, discharge"),
    refrigerant: str = typer.Option("NH3", help="Refrigerant name"),
):
    """Size refrigerant suction/discharge/liquid lines."""
    from qms.engineering.refrigeration import run_line_sizing
    from qms.engineering import db, output

    params = {
        'capacity_tons': capacity_tons,
        'suction_temp': suction_temp,
        'condensing_temp': condensing_temp,
        'length': length,
        'line_type': line_type,
        'refrigerant': refrigerant,
    }

    result = run_line_sizing(params)

    db.save_calculation(
        discipline="refrigeration",
        calculation_type="line-sizing",
        inputs=params,
        outputs=result,
        line_number=f"{line_type}-{refrigerant}",
    )

    typer.echo(output.format_result(result, title="Line Sizing Results"))


@app.command("relief-valve")
def relief_valve(
    volume_cuft: float = typer.Option(100, help="Vessel volume (ft3)"),
    set_pressure_psig: float = typer.Option(250, help="Set pressure (psig)"),
    refrigerant: str = typer.Option("NH3", help="Refrigerant name"),
):
    """Size pressure relief valves per IIAR/ASME."""
    from qms.engineering.refrigeration import run_relief_valve
    from qms.engineering import db, output

    params = {
        'volume_cuft': volume_cuft,
        'set_pressure_psig': set_pressure_psig,
        'refrigerant': refrigerant,
    }

    result = run_relief_valve(params)

    db.save_calculation(
        discipline="refrigeration",
        calculation_type="relief-valve",
        inputs=params,
        outputs=result,
        equipment_tag=f"RV-{refrigerant}",
    )

    typer.echo(output.format_result(result, title="Relief Valve Sizing Results"))


@app.command("pump")
def pump(
    capacity_tons: float = typer.Option(100, help="Refrigeration capacity (tons)"),
    recirculation_rate: float = typer.Option(4.0, help="Recirculation rate"),
    suction_temp: float = typer.Option(28, help="Suction temperature (F)"),
    static_head_ft: float = typer.Option(10, help="Static head (ft)"),
    pipe_length_ft: float = typer.Option(100, help="Pipe length (ft)"),
):
    """Size refrigerant recirculation pumps."""
    from qms.engineering.refrigeration import run_pump
    from qms.engineering import db, output

    params = {
        'capacity_tons': capacity_tons,
        'recirculation_rate': recirculation_rate,
        'suction_temp': suction_temp,
        'static_head_ft': static_head_ft,
        'pipe_length_ft': pipe_length_ft,
    }

    result = run_pump(params)

    db.save_calculation(
        discipline="refrigeration",
        calculation_type="pump",
        inputs=params,
        outputs=result,
        equipment_tag="P-recirc",
    )

    typer.echo(output.format_result(result, title="Pump Sizing Results"))


@app.command("ventilation")
def ventilation(
    length_ft: float = typer.Option(30, help="Room length (ft)"),
    width_ft: float = typer.Option(20, help="Room width (ft)"),
    height_ft: float = typer.Option(12, help="Room height (ft)"),
    refrigerant_charge_lb: float = typer.Option(1000, help="Refrigerant charge (lb)"),
    standard: str = typer.Option("iiar", help="Standard: iiar or ashrae"),
):
    """Calculate machine room ventilation requirements."""
    from qms.engineering.refrigeration import run_ventilation
    from qms.engineering import db, output

    params = {
        'length_ft': length_ft,
        'width_ft': width_ft,
        'height_ft': height_ft,
        'refrigerant_charge_lb': refrigerant_charge_lb,
        'standard': standard,
    }

    result = run_ventilation(params)

    db.save_calculation(
        discipline="refrigeration",
        calculation_type="ventilation",
        inputs=params,
        outputs=result,
    )

    typer.echo(output.format_result(result, title="Ventilation Requirements"))


@app.command("charge")
def charge(
    volume_cuft: float = typer.Option(10, help="Component volume (ft3)"),
    component_type: str = typer.Option("vessel", help="Type: vessel, coil, piping"),
    refrigerant: str = typer.Option("NH3", help="Refrigerant name"),
    temperature: float = typer.Option(28, help="Operating temperature (F)"),
    liquid_percent: float = typer.Option(80, help="Liquid fill percentage"),
):
    """Calculate refrigerant charge for a component."""
    from qms.engineering.refrigeration import run_charge
    from qms.engineering import db, output

    params = {
        'volume_cuft': volume_cuft,
        'component_type': component_type,
        'refrigerant': refrigerant,
        'temperature': temperature,
        'liquid_percent': liquid_percent,
    }

    result = run_charge(params)

    db.save_calculation(
        discipline="refrigeration",
        calculation_type="charge",
        inputs=params,
        outputs=result,
        equipment_tag=f"{component_type}-{refrigerant}",
    )

    typer.echo(output.format_result(result, title="Charge Calculation Results"))


# ---------------------------------------------------------------------------
# Validation commands
# ---------------------------------------------------------------------------

@app.command("validate-pipes")
def validate_pipes(
    project: str = typer.Argument(..., help="Project number or name"),
    drawing: str = typer.Option(None, help="Specific drawing number"),
    tolerance: float = typer.Option(10.0, help="Tolerance percentage"),
):
    """Validate pipe sizing against calculations."""
    from qms.engineering import db, validators, output

    proj = db.get_project_by_number(project)
    if not proj:
        typer.echo(f"Project not found: {project}")
        raise typer.Exit(1)

    results = validators.validate_pipe_sizing(
        proj['id'],
        drawing_number=drawing,
        tolerance_pct=tolerance,
    )

    typer.echo(output.format_validation_report(
        results, project=proj.get('name', project)
    ))


@app.command("validate-relief")
def validate_relief(
    project: str = typer.Argument(..., help="Project number or name"),
    drawing: str = typer.Option(None, help="Specific drawing number"),
    tolerance: float = typer.Option(10.0, help="Tolerance percentage"),
):
    """Validate relief valve sizing against calculations."""
    from qms.engineering import db, validators, output

    proj = db.get_project_by_number(project)
    if not proj:
        typer.echo(f"Project not found: {project}")
        raise typer.Exit(1)

    results = validators.validate_relief_valves(
        proj['id'],
        drawing_number=drawing,
        tolerance_pct=tolerance,
    )

    typer.echo(output.format_validation_report(
        results, project=proj.get('name', project)
    ))
