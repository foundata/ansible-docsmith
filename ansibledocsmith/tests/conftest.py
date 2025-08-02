"""Pytest configuration for ansible-docsmith tests."""

import pytest
from pathlib import Path
import tempfile
import shutil


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
def sample_role_with_specs(sample_role_path):
    """Create a sample role with argument_specs.yml."""
    spec_file = sample_role_path / "meta" / "argument_specs.yml"
    spec_content = """---
argument_specs:
  main:
    short_description: Test role for acme-shell
    description:
      - "This role manages SSL certificates using acme-shell tool"
      - "It can obtain, renew, and manage certificates from Let's Encrypt"
    author:
      - "foundata GmbH"
      - "Andreas Haerter <ah@foundata.com>"
    version_added: "1.0.0"
    options:
      acmesh_domain:
        type: str
        required: true
        description: "Primary domain name for the certificate"
      acmesh_email:
        type: str
        required: true
        description: "Email address for ACME account registration"
      acmesh_staging:
        type: bool
        required: false
        default: false
        description: "Use Let's Encrypt staging environment for testing"
      acmesh_config:
        type: dict
        required: false
        default: {}
        description: "Additional configuration options"
        suboptions:
          force_renewal:
            type: bool
            default: false
            description: "Force certificate renewal even if not expired"
          key_size:
            type: int
            default: 2048
            choices: [2048, 4096]
            description: "RSA key size in bits"
"""
    spec_file.write_text(spec_content)
    return sample_role_path


@pytest.fixture
def sample_role_with_specs_and_defaults(sample_role_with_specs):
    """Create a sample role with both argument specs and defaults."""
    defaults_file = sample_role_with_specs / "defaults" / "main.yml"
    defaults_content = """---
# Default configuration for test role

acmesh_domain: "example.com"
acmesh_email: "admin@example.com"
acmesh_staging: false

acmesh_config:
  force_renewal: false
  key_size: 2048
"""
    defaults_file.write_text(defaults_content)
    return sample_role_with_specs
