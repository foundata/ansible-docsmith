"""Tests for RoleProcessor."""

import pytest

from ansible_docsmith.core.exceptions import ValidationError
from ansible_docsmith.core.processor import RoleProcessor


class TestRoleProcessor:
    """Test the RoleProcessor class."""

    def test_validate_role_success(self, sample_role_with_specs_and_defaults):
        """Test successful role validation."""
        processor = RoleProcessor()

        result = processor.validate_role(sample_role_with_specs_and_defaults)

        assert "specs" in result
        assert "spec_file" in result
        assert "role_name" in result
        assert result["role_name"] == sample_role_with_specs_and_defaults.name

    def test_validate_role_failure(self, sample_role_path):
        """Test role validation failure."""
        processor = RoleProcessor()

        with pytest.raises(ValidationError):
            processor.validate_role(sample_role_path)

    def test_process_role_readme_only(self, sample_role_with_specs_and_defaults):
        """Test processing role with README generation only."""
        processor = RoleProcessor(dry_run=True)

        result = processor.process_role(
            sample_role_with_specs_and_defaults,
            generate_readme=True,
            update_defaults=False,
        )

        assert len(result.operations) >= 1
        assert len(result.errors) == 0
        # Check that README operation exists
        readme_ops = [op for op in result.operations if "README" in str(op[0])]
        assert len(readme_ops) == 1

    def test_process_role_defaults_only(self, sample_role_with_specs_and_defaults):
        """Test processing role with defaults update only."""
        processor = RoleProcessor(dry_run=True)

        result = processor.process_role(
            sample_role_with_specs_and_defaults,
            generate_readme=False,
            update_defaults=True,
        )

        assert len(result.operations) >= 1
        assert len(result.errors) == 0
        # Check that defaults operation exists
        defaults_ops = [op for op in result.operations if "main.yml" in str(op[0])]
        assert len(defaults_ops) == 1

    def test_process_role_both_operations(self, sample_role_with_specs_and_defaults):
        """Test processing role with both README and defaults."""
        processor = RoleProcessor(dry_run=True)

        result = processor.process_role(
            sample_role_with_specs_and_defaults,
            generate_readme=True,
            update_defaults=True,
        )

        assert len(result.operations) >= 2
        assert len(result.errors) == 0

    def test_process_role_no_defaults_file(self, sample_role_with_specs):
        """Test processing role without defaults file."""
        processor = RoleProcessor(dry_run=True)

        result = processor.process_role(
            sample_role_with_specs, generate_readme=True, update_defaults=True
        )

        # Should have an error about validation failing (because of consistency)
        assert len(result.errors) >= 1
        assert any("validation failed" in error.lower() for error in result.errors)

    def test_find_defaults_files_main_yml(self, sample_role_path):
        """Test finding defaults files for main entry point."""
        processor = RoleProcessor()

        defaults_file = sample_role_path / "defaults" / "main.yml"
        defaults_file.write_text("---\ntest_var: test_value")

        specs = {"main": {"options": {}}}
        result = processor._find_defaults_files(sample_role_path, specs)

        assert result == {"main": defaults_file}

    def test_find_defaults_files_multiple_entry_points(self, sample_role_path):
        """Test finding defaults files for multiple entry points."""
        processor = RoleProcessor()

        main_file = sample_role_path / "defaults" / "main.yml"
        main_file.write_text("---\ntest_var: test_value")

        other_file = sample_role_path / "defaults" / "other.yaml"
        other_file.write_text("---\nother_var: other_value")

        specs = {"main": {"options": {}}, "other": {"options": {}}}
        result = processor._find_defaults_files(sample_role_path, specs)

        assert result == {"main": main_file, "other": other_file}

    def test_find_defaults_files_none(self, sample_role_path):
        """Test when no defaults files exist."""
        processor = RoleProcessor()

        specs = {"main": {"options": {}}}
        result = processor._find_defaults_files(sample_role_path, specs)

        assert result == {}

    def test_validate_defaults_consistency_success(self):
        """Test successful consistency validation with matching defaults and specs."""
        processor = RoleProcessor()

        # Use the working multi-entry-point fixture
        from pathlib import Path

        fixture_path = Path("tests/fixtures/example-role-multiple-entry-points")

        # Get the specs
        role_data = processor.parser.validate_structure(fixture_path)

        # Test the consistency validation
        errors, warnings, notices = processor._validate_defaults_consistency(
            fixture_path, role_data["specs"], role_data["spec_file"]
        )

        # Should have no errors for this fixture
        consistency_errors = [
            e
            for e in errors
            if not e.startswith("Entry point") or "Unknown keys" not in e
        ]
        assert len(consistency_errors) == 0

        # Should have no errors for this fixture (no unknown keys warnings expected)
        assert len(errors) == 0

    def test_validate_defaults_consistency_errors(self):
        """
        Test consistency validation with mismatch fixture that should produce errors.
        """
        processor = RoleProcessor()

        from pathlib import Path

        fixture_path = Path("tests/fixtures/example-role-mismatch-spec-defaults")

        # Get the specs
        role_data = processor.parser.validate_structure(fixture_path)

        # Test the consistency validation
        errors, warnings, notices = processor._validate_defaults_consistency(
            fixture_path, role_data["specs"], role_data["spec_file"]
        )

        # Should have specific errors
        error_messages = "\n".join(errors)
        assert "main_missing_in_spec" in error_messages
        assert "main_state" in error_messages
        assert "defaults/main.yml but not in argument_specs.yml" in error_messages
        assert (
            "have defaults in argument_specs.yml but are missing from" in error_messages
        )

    def test_validate_unknown_keys(self, temp_dir):
        """Test validation of unknown keys in argument_specs."""
        processor = RoleProcessor()

        # Create a test spec file with unknown keys
        spec_file = temp_dir / "argument_specs.yml"
        spec_file.write_text("""---
argument_specs:
  main:
    description: "Valid description"
    unknown_key: "invalid"  # This should trigger a warning
    options:
      test_var:
        type: "str"
        description: "Valid description"
        invalid_option_key: "bad"  # This should also trigger a warning
""")

        warnings = processor._validate_unknown_keys(spec_file)

        assert len(warnings) == 2
        assert any("unknown_key" in w for w in warnings)
        assert any("invalid_option_key" in w for w in warnings)
        assert any("This might be an error in your role" in w for w in warnings)

    def test_extract_variables_from_defaults(self, temp_dir):
        """Test extracting variable names from defaults files."""
        processor = RoleProcessor()

        # Create test defaults file
        defaults_file = temp_dir / "main.yml"
        defaults_file.write_text("""---
var1: "value1"
var2: 123
var3:
  nested: true
""")

        result = processor._extract_variables_from_defaults(defaults_file)

        assert result == {"var1", "var2", "var3"}

    def test_extract_variables_from_defaults_empty_file(self, temp_dir):
        """Test extracting variables from empty defaults file."""
        processor = RoleProcessor()

        # Create empty defaults file
        defaults_file = temp_dir / "empty.yml"
        defaults_file.write_text("---\n")

        result = processor._extract_variables_from_defaults(defaults_file)

        assert result == set()

    def test_extract_variables_from_defaults_invalid_file(self, temp_dir):
        """Test extracting variables from invalid YAML file."""
        processor = RoleProcessor()

        # Create invalid YAML file
        defaults_file = temp_dir / "invalid.yml"
        defaults_file.write_text("invalid: yaml: content: [")

        result = processor._extract_variables_from_defaults(defaults_file)

        assert result == set()

    def test_validate_role_with_consistency_errors(self):
        """Test that validate_role fails when there are consistency errors."""
        processor = RoleProcessor()

        from pathlib import Path

        fixture_path = Path("tests/fixtures/example-role-mismatch-spec-defaults")

        # Should raise ValidationError due to consistency errors
        with pytest.raises(ValidationError) as exc_info:
            processor.validate_role(fixture_path)

        error_message = str(exc_info.value)
        assert "validation failed" in error_message.lower()
        assert "main_missing_in_spec" in error_message.lower()
        assert "main_state" in error_message.lower()

    def test_validate_role_with_warnings_only(self):
        """Test that validate_role passes when there are only warnings."""
        processor = RoleProcessor()

        from pathlib import Path

        fixture_path = Path("tests/fixtures/example-role-simple")

        # Should pass validation despite warnings
        result = processor.validate_role(fixture_path)

        assert "warnings" in result
        assert "errors" in result
        assert "notices" in result
        assert len(result["errors"]) == 0
        assert len(result["notices"]) > 0

    def test_validate_role_with_notices(self):
        """Test that validate_role includes notices for potential mismatches."""
        processor = RoleProcessor()

        from pathlib import Path

        fixture_path = Path("tests/fixtures/example-role-simple")

        # Should pass validation with notices about variables in specs but not defaults
        result = processor.validate_role(fixture_path)

        assert "notices" in result
        assert len(result["notices"]) > 0
        # Should have notice about acmesh_dns_provider being in specs but not defaults
        notice_messages = "\n".join(result["notices"])
        assert "acmesh_dns_provider" in notice_messages
        assert "may be intentional" in notice_messages

    def test_validate_role_with_unknown_key_warnings(self):
        """
        Test that validate_role includes warnings for unknown keys in mismatch
        fixture.
        """
        processor = RoleProcessor()

        from pathlib import Path

        fixture_path = Path("tests/fixtures/example-role-mismatch-spec-defaults")

        # This fixture has validation errors, so we expect an exception
        # But we can check that the unknown key warning would be included
        warnings = processor._validate_unknown_keys(
            fixture_path / "meta" / "argument_specs.yml",
        )

        assert len(warnings) == 1
        warning_messages = "\n".join(warnings)
        assert "unknown_key" in warning_messages.lower()
        assert "might be an error in your role" in warning_messages.lower()

    def test_validate_readme_markers_no_readme(self, temp_dir):
        """Test validation when no README.md exists (should pass)."""
        processor = RoleProcessor()

        # Create a basic role structure without README
        role_path = temp_dir / "test-role"
        role_path.mkdir()

        errors = processor._validate_readme_markers(role_path)
        assert errors == []

    def test_validate_readme_markers_missing_both(self, temp_dir):
        """Test validation when README exists but has no markers."""
        processor = RoleProcessor()

        # Create role with README missing markers
        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.md"
        readme_path.write_text("# My Role\n\nSome content without markers.")

        errors = processor._validate_readme_markers(role_path)
        assert len(errors) == 1
        assert "missing required markers" in errors[0]
        assert "BEGIN ANSIBLE DOCSMITH" in errors[0]
        assert "END ANSIBLE DOCSMITH" in errors[0]

    def test_validate_readme_markers_missing_start(self, temp_dir):
        """Test validation when README has end marker but no start marker."""
        processor = RoleProcessor()

        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.md"
        readme_path.write_text("""# My Role

Some content.

<!-- END ANSIBLE DOCSMITH -->
""")

        errors = processor._validate_readme_markers(role_path)
        assert len(errors) == 1
        assert "missing start marker" in errors[0]
        assert "BEGIN ANSIBLE DOCSMITH" in errors[0]

    def test_validate_readme_markers_missing_end(self, temp_dir):
        """Test validation when README has start marker but no end marker."""
        processor = RoleProcessor()

        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.md"
        readme_path.write_text("""# My Role

<!-- BEGIN ANSIBLE DOCSMITH -->
Some content.
""")

        errors = processor._validate_readme_markers(role_path)
        assert len(errors) == 1
        assert "missing end marker" in errors[0]
        assert "END ANSIBLE DOCSMITH" in errors[0]

    def test_validate_readme_markers_both_present(self, temp_dir):
        """Test validation when README has both markers (should pass)."""
        processor = RoleProcessor()

        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.md"
        readme_path.write_text("""# My Role

Some content.

<!-- BEGIN ANSIBLE DOCSMITH -->
Generated content here.
<!-- END ANSIBLE DOCSMITH -->

More content.
""")

        errors = processor._validate_readme_markers(role_path)
        assert errors == []
