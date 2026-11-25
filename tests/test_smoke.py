from typer.testing import CliRunner

from rav.cli import app


def test_cli_help():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.output
