from click.testing import CliRunner

from cli.main import cli


class TestCLI:

    def setup_method(self):
        self.runner = CliRunner()

    def test_cli_base_help(self):
        """Test that the base CLI command shows help."""
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "HEDGE" in result.output
        assert "Commands:" in result.output

    def test_optimize_help(self):
        """Test that the optimize command shows help."""
        result = self.runner.invoke(cli, ["optimize", "--help"])
        assert result.exit_code == 0
        assert "Optimize Python code" in result.output

    def test_config_help(self):
        """Test that the config command shows help."""
        result = self.runner.invoke(cli, ["config", "--help"])
        assert result.exit_code == 0
        assert "Manage HEDGE configuration" in result.output

    def test_analyze_help(self):
        """Test that the analyze command shows help."""
        result = self.runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "Analyze Python code complexity" in result.output
