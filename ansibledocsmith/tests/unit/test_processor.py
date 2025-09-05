"""Tests for RoleProcessor."""

import pytest

from ansible_docsmith import (
    MARKER_COMMENT_MD_BEGIN,
    MARKER_COMMENT_MD_END,
    MARKER_COMMENT_RST_BEGIN,
    MARKER_COMMENT_RST_END,
    MARKER_README_MAIN_END,
    MARKER_README_MAIN_START,
    MARKER_README_TOC_END,
    MARKER_README_TOC_START,
)
from ansible_docsmith.core.exceptions import ValidationError
from ansible_docsmith.core.processor import RoleProcessor, detect_format_from_role


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

        # Should have no errors now (fixed the mismatch fixture)
        assert len(errors) == 0

        # Should have value mismatch warnings
        warning_messages = "\n".join(warnings)
        assert "Default value mismatch for variable 'main_state'" in warning_messages
        assert "argument_specs.yml defines 'present'" in warning_messages
        assert "defaults/main.yml defines 'absent'" in warning_messages
        assert (
            "Default value mismatch for variable 'install_version'" in warning_messages
        )
        assert "Default value mismatch for variable 'install_force'" in warning_messages

    def test_validate_defaults_value_mismatch_detection(self, temp_dir):
        """Test detection of default value mismatches between specs and defaults."""
        processor = RoleProcessor()

        # Create required directory structure
        meta_dir = temp_dir / "meta"
        meta_dir.mkdir()

        # Create argument_specs.yml with specific default values
        spec_file = meta_dir / "argument_specs.yml"
        spec_file.write_text("""---
argument_specs:
  main:
    options:
      test_string:
        type: str
        default: "expected_value"
      test_bool:
        type: bool
        default: true
      test_number:
        type: int
        default: 42
""")

        # Create defaults/main.yml with different values
        defaults_dir = temp_dir / "defaults"
        defaults_dir.mkdir()
        defaults_file = defaults_dir / "main.yml"
        defaults_file.write_text("""---
test_string: "different_value"
test_bool: false
test_number: 99
""")

        # Run validation
        role_data = processor.parser.validate_structure(temp_dir)
        errors, warnings, notices = processor._validate_defaults_consistency(
            temp_dir, role_data["specs"], role_data["spec_file"]
        )

        # Should have no errors but three mismatch warnings
        assert len(errors) == 0
        assert len(warnings) == 3

        warning_messages = "\n".join(warnings)
        assert "Default value mismatch for variable 'test_string'" in warning_messages
        assert "'expected_value'" in warning_messages
        assert "'different_value'" in warning_messages
        assert "Default value mismatch for variable 'test_bool'" in warning_messages
        assert "True" in warning_messages
        assert "False" in warning_messages
        assert "Default value mismatch for variable 'test_number'" in warning_messages
        assert "42" in warning_messages
        assert "99" in warning_messages

    def test_validate_mutually_exclusive_keys(self, temp_dir):
        """Test validation of mutually exclusive default and required: true."""
        processor = RoleProcessor()

        # Create required directory structure
        meta_dir = temp_dir / "meta"
        meta_dir.mkdir()

        # Create argument_specs.yml with mutually exclusive keys
        spec_file = meta_dir / "argument_specs.yml"
        spec_file.write_text("""---
argument_specs:
  main:
    options:
      # ERROR: both default and required: true
      conflict_var:
        type: str
        default: "present"
        required: true

      # VALID: default with required: false
      valid_default_false:
        type: str
        default: "stable"
        required: false

      # VALID: default without required key
      valid_default_implicit:
        type: bool
        default: true

      # VALID: required: true without default
      valid_required_only:
        type: str
        required: true

  install:
    options:
      # Another ERROR case
      another_conflict:
        type: int
        default: 42
        required: true
""")

        # Test the mutually exclusive validation directly
        errors = processor._validate_mutually_exclusive_keys(spec_file)

        # Should have exactly 2 errors (one for each conflicting variable)
        assert len(errors) == 2

        error_messages = "\n".join(errors)
        assert "conflict_var" in error_messages
        assert "another_conflict" in error_messages
        assert "mutually exclusive" in error_messages
        assert "required: true" in error_messages

    def test_validate_mutually_exclusive_keys_with_role_validation(self):
        """Test that mutually exclusive keys cause role validation to fail."""
        processor = RoleProcessor()

        from pathlib import Path
        fixture_path = Path("tests/fixtures/example-role-mutually-exclusive-keys")

        # Should raise ValidationError due to mutually exclusive keys
        with pytest.raises(ValidationError) as exc_info:
            processor.validate_role(fixture_path)

        error_message = str(exc_info.value)
        assert "mutually exclusive" in error_message.lower()
        assert "conflict_variable" in error_message.lower()
        assert "install_conflict" in error_message.lower()

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

    def test_validate_role_with_value_mismatch_warnings(self):
        """Test that validate_role succeeds but reports value mismatch warnings."""
        processor = RoleProcessor()

        from pathlib import Path

        fixture_path = Path("tests/fixtures/example-role-mismatch-spec-defaults")

        # Should succeed but return warnings about value mismatches
        role_data = processor.validate_role(fixture_path)

        # Check that warnings are present
        assert "warnings" in role_data
        assert len(role_data["warnings"]) > 0

        warning_messages = "\n".join(role_data["warnings"])
        assert "Default value mismatch" in warning_messages
        assert "main_state" in warning_messages
        assert "install_version" in warning_messages
        assert "install_force" in warning_messages

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
        expected_start = (
            f"{MARKER_COMMENT_MD_BEGIN}"
            f"{MARKER_README_MAIN_START}"
            f"{MARKER_COMMENT_MD_END}"
        )
        expected_end = (
            f"{MARKER_COMMENT_MD_BEGIN}{MARKER_README_MAIN_END}{MARKER_COMMENT_MD_END}"
        )
        assert expected_start in errors[0]
        assert expected_end in errors[0]

    def test_validate_readme_markers_missing_start(self, temp_dir):
        """Test validation when README has end marker but no start marker."""
        processor = RoleProcessor()

        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.md"
        readme_path.write_text(f"""# My Role

Some content.

{MARKER_COMMENT_MD_BEGIN}{MARKER_README_MAIN_END}{MARKER_COMMENT_MD_END}
""")

        errors = processor._validate_readme_markers(role_path)
        assert len(errors) == 1
        assert "missing start marker" in errors[0]
        expected_start = (
            f"{MARKER_COMMENT_MD_BEGIN}"
            f"{MARKER_README_MAIN_START}"
            f"{MARKER_COMMENT_MD_END}"
        )
        assert expected_start in errors[0]

    def test_validate_readme_markers_missing_end(self, temp_dir):
        """Test validation when README has start marker but no end marker."""
        processor = RoleProcessor()

        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.md"
        readme_path.write_text(f"""# My Role

{MARKER_COMMENT_MD_BEGIN}{MARKER_README_MAIN_START}{MARKER_COMMENT_MD_END}
Some content.
""")

        errors = processor._validate_readme_markers(role_path)
        assert len(errors) == 1
        assert "missing end marker" in errors[0]
        expected_end = (
            f"{MARKER_COMMENT_MD_BEGIN}{MARKER_README_MAIN_END}{MARKER_COMMENT_MD_END}"
        )
        assert expected_end in errors[0]

    def test_validate_readme_markers_both_present(self, temp_dir):
        """Test validation when README has both markers (should pass)."""
        processor = RoleProcessor()

        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.md"
        readme_path.write_text(f"""# My Role

Some content.

{MARKER_COMMENT_MD_BEGIN}{MARKER_README_MAIN_START}{MARKER_COMMENT_MD_END}
Generated content here.
{MARKER_COMMENT_MD_BEGIN}{MARKER_README_MAIN_END}{MARKER_COMMENT_MD_END}

More content.
""")

        errors = processor._validate_readme_markers(role_path)
        assert errors == []

    def test_validate_readme_toc_markers_both_missing(self, temp_dir):
        """Test TOC validation when README exists but has no TOC markers."""
        processor = RoleProcessor()

        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.md"
        readme_path.write_text("# My Role\n\nSome content without TOC markers.")

        errors, notices = processor._validate_readme_toc_markers(role_path)
        assert len(errors) == 0
        assert len(notices) == 1
        assert "does not contain TOC markers" in notices[0]
        expected_toc_start = (
            f"{MARKER_COMMENT_MD_BEGIN}{MARKER_README_TOC_START}{MARKER_COMMENT_MD_END}"
        )
        expected_toc_end = (
            f"{MARKER_COMMENT_MD_BEGIN}{MARKER_README_TOC_END}{MARKER_COMMENT_MD_END}"
        )
        assert expected_toc_start in notices[0]
        assert expected_toc_end in notices[0]

    def test_validate_readme_toc_markers_missing_start(self, temp_dir):
        """Test TOC validation when README has end marker but no start marker."""
        processor = RoleProcessor()

        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.md"
        readme_path.write_text(f"""# My Role

Some content.

{MARKER_COMMENT_MD_BEGIN}{MARKER_README_TOC_END}{MARKER_COMMENT_MD_END}
""")

        errors, notices = processor._validate_readme_toc_markers(role_path)
        assert len(errors) == 1
        assert len(notices) == 0
        assert "missing TOC start marker" in errors[0]
        expected_toc_start = (
            f"{MARKER_COMMENT_MD_BEGIN}{MARKER_README_TOC_START}{MARKER_COMMENT_MD_END}"
        )
        assert expected_toc_start in errors[0]

    def test_validate_readme_toc_markers_missing_end(self, temp_dir):
        """Test TOC validation when README has start marker but no end marker."""
        processor = RoleProcessor()

        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.md"
        readme_path.write_text(f"""# My Role

{MARKER_COMMENT_MD_BEGIN}{MARKER_README_TOC_START}{MARKER_COMMENT_MD_END}
Some content.
""")

        errors, notices = processor._validate_readme_toc_markers(role_path)
        assert len(errors) == 1
        assert len(notices) == 0
        assert "missing TOC end marker" in errors[0]
        expected_toc_end = (
            f"{MARKER_COMMENT_MD_BEGIN}{MARKER_README_TOC_END}{MARKER_COMMENT_MD_END}"
        )
        assert expected_toc_end in errors[0]

    def test_validate_readme_toc_markers_both_present(self, temp_dir):
        """Test TOC validation when README has both TOC markers (should pass)."""
        processor = RoleProcessor()

        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.md"
        readme_path.write_text(f"""# My Role

{MARKER_COMMENT_MD_BEGIN}{MARKER_README_TOC_START}{MARKER_COMMENT_MD_END}
Generated TOC here.
{MARKER_COMMENT_MD_BEGIN}{MARKER_README_TOC_END}{MARKER_COMMENT_MD_END}

## Section One

More content.
""")

        errors, notices = processor._validate_readme_toc_markers(role_path)
        assert errors == []
        assert notices == []

    def test_validate_readme_toc_markers_no_readme(self, temp_dir):
        """Test TOC validation when no README exists."""
        processor = RoleProcessor()

        role_path = temp_dir / "test-role"
        role_path.mkdir()

        errors, notices = processor._validate_readme_toc_markers(role_path)
        assert errors == []
        assert notices == []

    def test_validate_role_rst_success(self, temp_dir):
        """Test successful RST role validation."""
        processor = RoleProcessor(format_type="rst")

        # Create a role with RST README and proper markers
        role_path = temp_dir / "test-role"
        role_path.mkdir()

        # Create meta directory and argument_specs.yml
        meta_dir = role_path / "meta"
        meta_dir.mkdir()
        spec_file = meta_dir / "argument_specs.yml"
        spec_file.write_text("""---
argument_specs:
  main:
    short_description: "Test role"
    description: "A test role"
    options:
      test_var:
        type: str
        description: "A test variable"
""")

        # Create defaults directory and main.yml
        defaults_dir = role_path / "defaults"
        defaults_dir.mkdir()
        defaults_file = defaults_dir / "main.yml"
        defaults_file.write_text("---\ntest_var: test_value")

        # Create README.rst with proper markers
        readme_path = role_path / "README.rst"
        rst_start = (
            f"{MARKER_COMMENT_RST_BEGIN}"
            f"{MARKER_README_MAIN_START}"
            f"{MARKER_COMMENT_RST_END}"
        )
        rst_end = (
            f"{MARKER_COMMENT_RST_BEGIN}"
            f"{MARKER_README_MAIN_END}"
            f"{MARKER_COMMENT_RST_END}"
        )
        readme_path.write_text(f"""Test Role RST
==============

Some description.

{rst_start}
Role variables
==============

``test_var``
-------------

A test variable

:Type: ``str``
:Required: No
:Default: `"test_value"`

{rst_end}

License
-------

MIT
""")

        result = processor.validate_role(role_path)

        assert "specs" in result
        assert "spec_file" in result
        assert "role_name" in result
        assert result["role_name"] == role_path.name
        assert len(result["errors"]) == 0

    def test_validate_role_rst_missing_markers_forced(self, temp_dir):
        """Test RST validation fails when markers are missing and format is forced."""
        processor = RoleProcessor(format_type="rst")

        # Create a role with RST README but missing markers
        role_path = temp_dir / "test-role"
        role_path.mkdir()

        # Create meta directory and argument_specs.yml
        meta_dir = role_path / "meta"
        meta_dir.mkdir()
        spec_file = meta_dir / "argument_specs.yml"
        spec_file.write_text("""---
argument_specs:
  main:
    short_description: "Test role"
    description: "A test role"
    options:
      test_var:
        type: str
        description: "A test variable"
""")

        # Create defaults directory and main.yml
        defaults_dir = role_path / "defaults"
        defaults_dir.mkdir()
        defaults_file = defaults_dir / "main.yml"
        defaults_file.write_text("---\ntest_var: test_value")

        # Create README.rst WITHOUT proper markers
        readme_path = role_path / "README.rst"
        readme_path.write_text("""Test Role RST
==============

Some description without markers.

License
-------

MIT
""")

        with pytest.raises(ValidationError) as exc_info:
            processor.validate_role(role_path)

        error_message = str(exc_info.value)
        assert "validation failed" in error_message.lower()
        assert "missing required markers" in error_message.lower()
        rst_start = (
            f"{MARKER_COMMENT_RST_BEGIN}"
            f"{MARKER_README_MAIN_START}"
            f"{MARKER_COMMENT_RST_END}"
        )
        rst_end = (
            f"{MARKER_COMMENT_RST_BEGIN}"
            f"{MARKER_README_MAIN_END}"
            f"{MARKER_COMMENT_RST_END}"
        )
        assert rst_start in error_message
        assert rst_end in error_message

    def test_validate_readme_markers_rst_missing_both(self, temp_dir):
        """Test validation when RST README exists but has no markers."""
        processor = RoleProcessor(format_type="rst")

        # Create role with README.rst missing markers
        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.rst"
        readme_path.write_text("Test Role\n=========\n\nSome content without markers.")

        errors = processor._validate_readme_markers(role_path)
        assert len(errors) == 1
        assert "missing required markers" in errors[0]
        expected_start = (
            f"{MARKER_COMMENT_RST_BEGIN}"
            f"{MARKER_README_MAIN_START}"
            f"{MARKER_COMMENT_RST_END}"
        )
        expected_end = (
            f"{MARKER_COMMENT_RST_BEGIN}"
            f"{MARKER_README_MAIN_END}"
            f"{MARKER_COMMENT_RST_END}"
        )
        assert expected_start in errors[0]
        assert expected_end in errors[0]

    def test_validate_readme_markers_rst_both_present(self, temp_dir):
        """Test validation when RST README has both markers (should pass)."""
        processor = RoleProcessor(format_type="rst")

        role_path = temp_dir / "test-role"
        role_path.mkdir()
        readme_path = role_path / "README.rst"
        rst_start = (
            f"{MARKER_COMMENT_RST_BEGIN}"
            f"{MARKER_README_MAIN_START}"
            f"{MARKER_COMMENT_RST_END}"
        )
        rst_end = (
            f"{MARKER_COMMENT_RST_BEGIN}"
            f"{MARKER_README_MAIN_END}"
            f"{MARKER_COMMENT_RST_END}"
        )
        readme_path.write_text(f"""Test Role
=========

Some content.

{rst_start}
Generated content here.
{rst_end}

More content.
""")

        errors = processor._validate_readme_markers(role_path)
        assert errors == []

    def test_detect_format_from_role_rst_exists(self, temp_dir):
        """Test format detection when README.rst exists."""
        role_path = temp_dir / "test-role"
        role_path.mkdir()

        # Create README.rst
        readme_rst = role_path / "README.rst"
        readme_rst.write_text("Test Role\n=========\n\nDescription.")

        result = detect_format_from_role(role_path)
        assert result == "rst"

    def test_detect_format_from_role_md_exists(self, temp_dir):
        """Test format detection when README.md exists."""
        role_path = temp_dir / "test-role"
        role_path.mkdir()

        # Create README.md
        readme_md = role_path / "README.md"
        readme_md.write_text("# Test Role\n\nDescription.")

        result = detect_format_from_role(role_path)
        assert result == "markdown"

    def test_detect_format_from_role_both_exist_prefer_rst(self, temp_dir):
        """Test format detection when both README files exist (should prefer RST)."""
        role_path = temp_dir / "test-role"
        role_path.mkdir()

        # Create both README files
        readme_rst = role_path / "README.rst"
        readme_rst.write_text("Test Role\n=========\n\nDescription.")
        readme_md = role_path / "README.md"
        readme_md.write_text("# Test Role\n\nDescription.")

        result = detect_format_from_role(role_path)
        assert result == "rst"

    def test_detect_format_from_role_neither_exists(self, temp_dir):
        """Test format detection when no README exists (should default to markdown)."""
        role_path = temp_dir / "test-role"
        role_path.mkdir()

        result = detect_format_from_role(role_path)
        assert result == "markdown"

    def test_processor_auto_format_detection(self, temp_dir):
        """Test RoleProcessor with auto format detection."""
        role_path = temp_dir / "test-role"
        role_path.mkdir()

        # Create README.rst
        readme_rst = role_path / "README.rst"
        readme_rst.write_text("Test Role\n=========\n\nDescription.")

        # Create processor with auto format
        processor = RoleProcessor(format_type="auto")

        # Mock the validation to just check the format is detected correctly
        detected_format = (
            processor.format_type
            if processor.format_type != "auto"
            else detect_format_from_role(role_path)
        )
        assert detected_format == "rst"

    def test_processor_markdown_format_detection(self, temp_dir):
        """Test RoleProcessor with markdown format when README.md exists."""
        role_path = temp_dir / "test-role"
        role_path.mkdir()

        # Create README.md
        readme_md = role_path / "README.md"
        readme_md.write_text("# Test Role\n\nDescription.")

        # Create processor with auto format
        processor = RoleProcessor(format_type="auto")

        # Mock the validation to just check the format is detected correctly
        detected_format = (
            processor.format_type
            if processor.format_type != "auto"
            else detect_format_from_role(role_path)
        )
        assert detected_format == "markdown"
