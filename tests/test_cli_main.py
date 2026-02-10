"""Tests for the top-level CLI assembly."""

from qms.cli.main import app


def test_main_app_help(cli_runner):
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Quality Management System" in result.output


def test_version_output(cli_runner):
    result = cli_runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_unknown_command(cli_runner):
    result = cli_runner.invoke(app, ["nonexistent"])
    assert result.exit_code != 0
