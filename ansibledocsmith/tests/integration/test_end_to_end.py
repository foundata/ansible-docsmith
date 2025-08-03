"""End-to-end integration tests."""

from typer.testing import CliRunner

from ansible_docsmith.cli import app


class TestEndToEnd:
    """Test complete workflows."""

    def test_generate_command_dry_run(self, sample_role_with_specs_and_defaults):
        """Test generate command in dry run mode."""
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "generate",
                str(sample_role_with_specs_and_defaults),
                "--dry-run",
                "--verbose",
            ],
        )

        assert result.exit_code == 0
        assert "Processing role" in result.stdout
        assert "DRY RUN MODE" in result.stdout
        assert "✅ Documentation generation complete!" in result.stdout

    def test_validate_command(self, sample_role_with_specs):
        """Test validate command."""
        runner = CliRunner()

        result = runner.invoke(
            app, ["validate", str(sample_role_with_specs), "--verbose"]
        )

        assert result.exit_code == 0
        assert "✅ Validation passed!" in result.stdout
        assert "test-role" in result.stdout

    def test_generate_command_with_actual_files(
        self, sample_role_with_specs_and_defaults
    ):
        """Test generate command that actually creates files."""
        runner = CliRunner()

        # Ensure no README exists initially
        readme_path = sample_role_with_specs_and_defaults / "README.md"
        if readme_path.exists():
            readme_path.unlink()

        result = runner.invoke(
            app, ["generate", str(sample_role_with_specs_and_defaults), "--verbose"]
        )

        assert result.exit_code == 0
        assert "✅ Documentation generation complete!" in result.stdout

        # Check that README was created / updated
        assert readme_path.exists()
        readme_content = readme_path.read_text()
        assert "## Role variables" in readme_content
        assert "acmesh_domain" in readme_content
        assert "Primary domain name" in readme_content

        # Check that defaults file was updated with comments
        defaults_path = sample_role_with_specs_and_defaults / "defaults" / "main.yml"
        defaults_content = defaults_path.read_text()
        assert (
            "Primary domain name" in defaults_content
            or "Email address for ACME" in defaults_content
        )

    def test_validate_invalid_role(self, sample_role_path):
        """Test validate command on invalid role."""
        runner = CliRunner()

        result = runner.invoke(app, ["validate", str(sample_role_path)])

        assert result.exit_code == 1
        # Error message goes to stderr or could be in stdout
        output = result.stdout + (result.stderr or "")
        assert "argument_specs.yml" in output or "Validation failed" in output

    def test_generate_readme_only(self, sample_role_with_specs):
        """Test generate command with README only."""
        runner = CliRunner()

        result = runner.invoke(
            app, ["generate", str(sample_role_with_specs), "--no-defaults", "--dry-run"]
        )

        assert result.exit_code == 0
        assert "README=True, Defaults=False" in result.stdout

    def test_generate_defaults_only(self, sample_role_with_specs_and_defaults):
        """Test generate command with defaults only."""
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "generate",
                str(sample_role_with_specs_and_defaults),
                "--no-readme",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "README=False, Defaults=True" in result.stdout
