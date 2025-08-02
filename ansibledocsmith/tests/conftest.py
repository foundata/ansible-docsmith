"""Pytest configuration for ansible-docsmith tests."""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_role_path(temp_dir):
    """Create a sample role structure for testing."""
    role_path = temp_dir / "test-role"
    role_path.mkdir()

    # Create required directories
    (role_path / "meta").mkdir()
    (role_path / "defaults").mkdir()
    (role_path / "tasks").mkdir()

    return role_path


@pytest.fixture
def sample_role_fixture_path():
    """Get path to the simple example role fixture."""
    return Path(__file__).parent / "fixtures" / "example-role-simple"


@pytest.fixture
def sample_role_with_specs(sample_role_path, sample_role_fixture_path):
    """Create a sample role with argument_specs.yml from fixtures."""
    # Copy the comprehensive argument_specs.yml from fixtures
    fixture_spec = sample_role_fixture_path / "meta" / "argument_specs.yml"
    spec_file = sample_role_path / "meta" / "argument_specs.yml"
    spec_file.write_text(fixture_spec.read_text(encoding="utf-8"))
    return sample_role_path


@pytest.fixture
def sample_role_with_specs_and_defaults(
    sample_role_with_specs, sample_role_fixture_path
):
    """Create a sample role with both argument specs and defaults from fixtures."""
    # Copy the comprehensive defaults file from fixtures
    fixture_defaults = sample_role_fixture_path / "defaults" / "main.yml"
    defaults_file = sample_role_with_specs / "defaults" / "main.yml"
    defaults_file.write_text(fixture_defaults.read_text(encoding="utf-8"))
    return sample_role_with_specs
