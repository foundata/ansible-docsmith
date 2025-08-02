"""Tests for ArgumentSpecParser."""

import pytest
from pathlib import Path
from ansible_docsmith.core.parser import ArgumentSpecParser
from ansible_docsmith.core.exceptions import ParseError, ValidationError


class TestArgumentSpecParser:
    """Test the ArgumentSpecParser class."""

    def test_parse_valid_file(self, sample_role_path):
        """Test parsing a valid argument_specs.yml file."""
        parser = ArgumentSpecParser()
        
        # Create argument_specs.yml
        spec_file = sample_role_path / "meta" / "argument_specs.yml"
        spec_content = """---
argument_specs:
  main:
    short_description: Test role
    description: A test role for testing
    options:
      test_var:
        type: str
        required: true
        description: A test variable
"""
        spec_file.write_text(spec_content)
        
        result = parser.parse_file(spec_file)
        
        assert "main" in result
        assert result["main"]["short_description"] == "Test role"
        assert "test_var" in result["main"]["options"]
        assert result["main"]["options"]["test_var"]["type"] == "str"
        assert result["main"]["options"]["test_var"]["required"] is True

    def test_parse_missing_file(self, sample_role_path):
        """Test parsing a non-existent file."""
        parser = ArgumentSpecParser()
        spec_file = sample_role_path / "meta" / "missing.yml"
        
        with pytest.raises(ParseError, match="File not found"):
            parser.parse_file(spec_file)

    def test_parse_empty_file(self, sample_role_path):
        """Test parsing an empty file."""
        parser = ArgumentSpecParser()
        spec_file = sample_role_path / "meta" / "argument_specs.yml"
        spec_file.write_text("")
        
        with pytest.raises(ParseError, match="Empty or invalid YAML"):
            parser.parse_file(spec_file)

    def test_parse_missing_argument_specs_key(self, sample_role_path):
        """Test parsing file without argument_specs key."""
        parser = ArgumentSpecParser()
        spec_file = sample_role_path / "meta" / "argument_specs.yml"
        spec_file.write_text("---\nother_key: value")
        
        with pytest.raises(ParseError, match="Missing 'argument_specs' key"):
            parser.parse_file(spec_file)

    def test_validate_structure_success(self, sample_role_path):
        """Test successful role structure validation."""
        parser = ArgumentSpecParser()
        
        # Create valid argument_specs.yml
        spec_file = sample_role_path / "meta" / "argument_specs.yml"
        spec_content = """---
argument_specs:
  main:
    short_description: Test role
    options:
      test_var:
        type: str
        description: Test variable
"""
        spec_file.write_text(spec_content)
        
        result = parser.validate_structure(sample_role_path)
        
        assert result["role_name"] == "test-role"
        assert result["spec_file"] == spec_file
        assert "main" in result["specs"]

    def test_validate_structure_missing_meta(self, temp_dir):
        """Test validation with missing meta directory."""
        parser = ArgumentSpecParser()
        role_path = temp_dir / "invalid-role"
        role_path.mkdir()
        
        with pytest.raises(ValidationError, match="Required directory missing.*meta"):
            parser.validate_structure(role_path)

    def test_validate_structure_missing_specs_file(self, sample_role_path):
        """Test validation with missing argument_specs file."""
        parser = ArgumentSpecParser()
        
        with pytest.raises(ValidationError, match="No argument_specs.yml found"):
            parser.validate_structure(sample_role_path)

    def test_validate_structure_missing_main_entry(self, sample_role_path):
        """Test validation with missing main entry point."""
        parser = ArgumentSpecParser()
        
        spec_file = sample_role_path / "meta" / "argument_specs.yml"
        spec_content = """---
argument_specs:
  other:
    short_description: Other entry point
"""
        spec_file.write_text(spec_content)
        
        with pytest.raises(ValidationError, match="Missing 'main' entry point"):
            parser.validate_structure(sample_role_path)

    def test_normalize_description_list(self):
        """Test description normalization from list."""
        parser = ArgumentSpecParser()
        
        description = ["Line 1", "Line 2", "Line 3"]
        result = parser._normalize_description(description)
        
        assert result == "Line 1\nLine 2\nLine 3"

    def test_normalize_description_string(self):
        """Test description normalization from string."""
        parser = ArgumentSpecParser()
        
        description = "Single line description"
        result = parser._normalize_description(description)
        
        assert result == "Single line description"

    def test_normalize_author_string(self):
        """Test author normalization from string."""
        parser = ArgumentSpecParser()
        
        author = "John Doe"
        result = parser._normalize_author(author)
        
        assert result == ["John Doe"]

    def test_normalize_author_list(self):
        """Test author normalization from list."""
        parser = ArgumentSpecParser()
        
        author = ["John Doe", "Jane Smith"]
        result = parser._normalize_author(author)
        
        assert result == ["John Doe", "Jane Smith"]

    def test_normalize_options_with_suboptions(self, sample_role_path):
        """Test options normalization with suboptions."""
        parser = ArgumentSpecParser()
        
        spec_file = sample_role_path / "meta" / "argument_specs.yml"
        spec_content = """---
argument_specs:
  main:
    options:
      complex_var:
        type: dict
        suboptions:
          sub_var:
            type: str
            default: "test"
"""
        spec_file.write_text(spec_content)
        
        result = parser.parse_file(spec_file)
        
        options = result["main"]["options"]
        assert "complex_var" in options
        assert "suboptions" in options["complex_var"]
        assert "sub_var" in options["complex_var"]["suboptions"]
        assert options["complex_var"]["suboptions"]["sub_var"]["default"] == "test"