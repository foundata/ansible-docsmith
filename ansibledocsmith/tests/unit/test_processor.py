"""Tests for RoleProcessor."""

import pytest

from ansible_docsmith.core.exceptions import ValidationError
from ansible_docsmith.core.processor import RoleProcessor


class TestRoleProcessor:
    """Test the RoleProcessor class."""

    def test_validate_role_success(self, sample_role_with_specs):
        """Test successful role validation."""
        processor = RoleProcessor()

        result = processor.validate_role(sample_role_with_specs)

        assert "specs" in result
        assert "spec_file" in result
        assert "role_name" in result
        assert result["role_name"] == sample_role_with_specs.name

    def test_validate_role_failure(self, sample_role_path):
        """Test role validation failure."""
        processor = RoleProcessor()

        with pytest.raises(ValidationError):
            processor.validate_role(sample_role_path)

    def test_process_role_readme_only(self, sample_role_with_specs):
        """Test processing role with README generation only."""
        processor = RoleProcessor(dry_run=True)

        result = processor.process_role(
            sample_role_with_specs, generate_readme=True, update_defaults=False
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

        # Should have a warning about missing defaults
        assert len(result.warnings) >= 1
        assert any("defaults" in warning.lower() for warning in result.warnings)

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
