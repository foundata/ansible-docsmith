"""End-to-end integration tests."""

import shutil
from pathlib import Path

from typer.testing import CliRunner

from ansible_docsmith.cli import app


class TestEndToEnd:
    """Test complete workflows."""

    def test_generate_converts_ansible_markup(self, temp_dir):
        """Ansible markup in descriptions is converted in README and defaults."""
        runner = CliRunner()

        fixture = (
            Path(__file__).parent.parent / "fixtures" / "example-role-ansible-markup"
        )
        role_path = temp_dir / "example-role-ansible-markup"
        shutil.copytree(fixture, role_path)

        result = runner.invoke(app, ["generate", str(role_path)])
        assert result.exit_code == 0

        readme = (role_path / "README.md").read_text(encoding="utf-8")
        # B(...) -> bold, O(known) -> anchor link, M(fqcn) -> docs link
        assert "**present**" in readme
        assert "[`markup_port`](#variable-markup_port)" in readme
        assert (
            "[`ansible.builtin.copy`](https://docs.ansible.com/ansible/latest/"
            "collections/ansible/builtin/copy_module.html)" in readme
        )
        # U(...) -> autolink, V/E -> code, unknown O() and invalid M() unlinked
        assert "<https://example.com/>" in readme
        assert "`8080`" in readme
        assert "`MARKUP_PORT`" in readme
        assert "`markup_unknown`" in readme
        assert "M(noFQCN)" in readme
        # No raw markup left over (outside the intentionally invalid M())
        assert "B(present)" not in readme
        assert "O(markup_port)" not in readme

        defaults = (role_path / "defaults" / "main.yml").read_text(encoding="utf-8")
        # Markup converted in YAML comments, but never as anchor links
        assert "`8080`" in defaults
        assert "O(markup_port)" not in defaults
        assert "](#variable-" not in defaults

        # Idempotence: a second run must not change anything
        readme_before, defaults_before = readme, defaults
        result = runner.invoke(app, ["generate", str(role_path)])
        assert result.exit_code == 0
        assert (role_path / "README.md").read_text(encoding="utf-8") == readme_before
        assert (role_path / "defaults" / "main.yml").read_text(
            encoding="utf-8"
        ) == defaults_before

    def test_generate_documents_nested_options(self, temp_dir):
        """Nested options are documented in defaults comments (issue #21)."""
        runner = CliRunner()

        fixture = (
            Path(__file__).parent.parent / "fixtures" / "example-role-nested-options"
        )
        role_path = temp_dir / "example-role-nested-options"
        shutil.copytree(fixture, role_path)

        result = runner.invoke(app, ["generate", str(role_path)])
        assert result.exit_code == 0

        defaults = (role_path / "defaults" / "main.yml").read_text(encoding="utf-8")
        assert "# - Dict attributes:" in defaults
        assert "#   - name: Name of the group." in defaults
        assert "#     - Required: Yes" in defaults
        assert "#     - Choices: present, absent" in defaults
        # Third nesting level is rendered, the fourth is omitted
        assert "- username: Login name of the member." in defaults
        assert "- permission: Permission entry (third nesting level)." in defaults
        assert "- too_deep:" not in defaults
        assert "omitted at this nesting depth" in defaults

        # Idempotence: a second run must not change anything
        result = runner.invoke(app, ["generate", str(role_path)])
        assert result.exit_code == 0
        assert (role_path / "defaults" / "main.yml").read_text(
            encoding="utf-8"
        ) == defaults

        # Opt-out flag removes the nested documentation
        result = runner.invoke(
            app, ["generate", str(role_path), "--no-defaults-comments-nested"]
        )
        assert result.exit_code == 0
        defaults = (role_path / "defaults" / "main.yml").read_text(encoding="utf-8")
        assert "Dict attributes" not in defaults

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

    def test_validate_command(self, sample_role_with_specs_and_defaults):
        """Test validate command."""
        runner = CliRunner()

        result = runner.invoke(
            app, ["validate", str(sample_role_with_specs_and_defaults), "--verbose"]
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

    def test_generate_readme_only(self, sample_role_with_specs_and_defaults):
        """Test generate command with README only."""
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "generate",
                str(sample_role_with_specs_and_defaults),
                "--no-defaults",
                "--dry-run",
            ],
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

    def test_validate_role_without_defaults_fails(self, sample_role_with_specs):
        """
        Test that validation fails when defaults are missing for variables with
        defaults in specs.
        """
        runner = CliRunner()

        result = runner.invoke(
            app, ["validate", str(sample_role_with_specs), "--verbose"]
        )

        assert result.exit_code == 1
        output = result.stdout + (result.stderr or "")
        assert (
            "Consistency validation failed" in output or "Validation failed" in output
        )

    def test_generate_with_custom_template(
        self, sample_role_with_specs_and_defaults, temp_dir
    ):
        """Test generate command with custom README template."""
        runner = CliRunner()

        # Create a custom template file
        custom_template = temp_dir / "custom_readme.md.j2"
        custom_template.write_text("""# Custom {{ role_name }} Role

This is a custom template for {{ role_name }}.

{% if has_options %}
## Variables
{% for var_name, var_spec in options.items() %}
- **{{ var_name }}**: {{ var_spec.description }}
{% endfor %}
{% endif %}
""")

        result = runner.invoke(
            app,
            [
                "generate",
                str(sample_role_with_specs_and_defaults),
                f"--template-readme={custom_template}",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "Using custom template" in result.stdout
        assert "Documentation generation complete!" in result.stdout

    def test_generate_with_invalid_template_extension(
        self, sample_role_with_specs_and_defaults, temp_dir
    ):
        """Test generate command with invalid template file extension."""
        runner = CliRunner()

        # Create a file with wrong extension
        invalid_template = temp_dir / "template.txt"
        invalid_template.write_text("Some content")

        result = runner.invoke(
            app,
            [
                "generate",
                str(sample_role_with_specs_and_defaults),
                f"--template-readme={invalid_template}",
                "--dry-run",
            ],
        )

        assert result.exit_code == 1
        assert "must have .j2 extension" in result.stdout

    def test_generate_with_invalid_template_syntax(
        self, sample_role_with_specs_and_defaults, temp_dir
    ):
        """Test generate command with template file containing invalid Jinja2 syntax."""
        runner = CliRunner()

        # Create a template with invalid syntax
        invalid_template = temp_dir / "invalid.md.j2"
        invalid_template.write_text("# {{ role_name \n\nMissing closing brace")

        result = runner.invoke(
            app,
            [
                "generate",
                str(sample_role_with_specs_and_defaults),
                f"--template-readme={invalid_template}",
                "--dry-run",
            ],
        )

        assert result.exit_code == 1
        output = result.stdout + (result.stderr or "")
        assert "Template error" in output

    def test_validate_role_with_readme_missing_markers(self, temp_dir):
        """Test validation fails when README exists but lacks required markers."""
        runner = CliRunner()

        # Create a minimal valid role structure
        role_path = temp_dir / "test-role"
        role_path.mkdir()

        # Create meta directory and argument_specs.yml
        meta_dir = role_path / "meta"
        meta_dir.mkdir()
        specs_file = meta_dir / "argument_specs.yml"
        specs_file.write_text("""---
argument_specs:
  main:
    short_description: Test role
    options:
      test_var:
        type: str
        description: A test variable
        default: test_value
""")

        # Create defaults directory and main.yml
        defaults_dir = role_path / "defaults"
        defaults_dir.mkdir()
        defaults_file = defaults_dir / "main.yml"
        defaults_file.write_text("test_var: test_value\n")

        # Create README without markers
        readme_file = role_path / "README.md"
        readme_file.write_text("""# Test Role

This is a test role without the required markers.

## Variables

Some variables here.
""")

        result = runner.invoke(app, ["validate", str(role_path)])

        assert result.exit_code == 1
        output = result.stdout + (result.stderr or "")
        assert "missing required markers" in output
        assert "ANSIBLE DOCSMITH" in output
        assert "Validation failed" in output
