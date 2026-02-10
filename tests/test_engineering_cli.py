"""Tests for engineering CLI commands via Typer CliRunner."""

from qms.engineering.cli import app as eng_app


def test_line_sizing_command(cli_runner, mock_db):
    result = cli_runner.invoke(eng_app, [
        "line-sizing", "--capacity-tons", "100", "--line-type", "dry",
    ])
    assert result.exit_code == 0, result.output


def test_relief_valve_command(cli_runner, mock_db):
    result = cli_runner.invoke(eng_app, [
        "relief-valve", "--volume-cuft", "100", "--set-pressure-psig", "250",
    ])
    assert result.exit_code == 0, result.output


def test_pump_command(cli_runner, mock_db):
    result = cli_runner.invoke(eng_app, ["pump"])
    assert result.exit_code == 0, result.output


def test_ventilation_command(cli_runner, mock_db):
    result = cli_runner.invoke(eng_app, [
        "ventilation", "--length-ft", "40", "--width-ft", "25", "--height-ft", "14",
    ])
    assert result.exit_code == 0, result.output


def test_charge_command(cli_runner, mock_db):
    result = cli_runner.invoke(eng_app, [
        "charge", "--volume-cuft", "20", "--temperature", "-20",
    ])
    assert result.exit_code == 0, result.output


def test_history_empty(cli_runner, mock_db):
    result = cli_runner.invoke(eng_app, ["history"])
    assert result.exit_code == 0
    assert "No calculations" in result.output
