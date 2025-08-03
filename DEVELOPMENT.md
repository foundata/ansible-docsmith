# Development

This file provides information for maintainers and contributors to `ansible-docsmith`.


## Table of contents<a id="toc"></a>

- [Prerequisites](#prerequisites)
- [Getting started](#getting-started)
- [Project structure](#project-structure)
- [Development standards](#development-standards)
  - [Code formatting and linting](#code-linting)
- [Testing](#testing)
  - [Running tests](#running-tests)
   - [Manual testing examples](#manual-testing)
  - [Test structure](#test-structure)
  - [Writing tests](#writing-tests)
- [Recommended development Workflow](#development-workflow)
  - [Before making changes](#before-making-changes)
  - [Making changes](#making-changes)
  - [Before committing](#before-committing)
- [Release process](#release-process)
- [Troubleshooting](#troubleshooting)
  - [Common issues](#common-issues)


## Prerequisites<a id="prerequisites"></a>

- **Python 3.11 or later** - Required for running the application.
- **Git** - For version control
- **[`uv`](https://docs.astral.sh/uv/getting-started/installation/)** - Python package manager (recommended) or `pip` as fallback


## Getting started<a id="getting-started"></a>

1. Clone the repository:
   ```bash
   git clone https://github.com/foundata/ansible-docsmith.git
   cd ansible-docsmith/ansibledocsmith
   ```
2. Set up development environment:
   Install dependencies using `uv` (recommended):
   ```bash
   # Install all dependencies including development dependencies
   uv sync --all-groups

   # Alternative: Install only production dependencies
   uv sync
   ```
   Or using `pip` (fallback):
   ```bash
   # Create virtual environment
   python -m venv .venv
   source .venv/bin/activate

   # Install in development mode
   pip install -e .
   pip install pytest  # For testing
   ```
3. Test that the installation works:
   ```bash
   # Show help
   uv run ansible-docsmith --help

   # Show version
   uv run ansible-docsmith --version

   # Test with example role fixture (always use --dry-run to protect fixtures)
   uv run ansible-docsmith generate tests/fixtures/example-role-simple --dry-run
   ```


## Project structure<a id="project-structure"></a>

```
ansible-docsmith/
├── [...]
├── DEVELOPMENT.md              # This file
├── [...]
└── ansibledocsmith/            # Python package directory
    ├── pyproject.toml          # Project configuration
    ├── uv.lock                 # Dependency lock file
    ├── src/ansible_docsmith/   # Main package
    │   ├── __init__.py
    │   ├── cli.py              # CLI interface
    │   ├── core/               # Core functionality
    │   │   ├── __init__.py
    │   │   ├── exceptions.py   # Custom exceptions
    │   │   ├── generator.py    # Documentation generators
    │   │   ├── parser.py       # YAML parsing
    │   │   └── processor.py    # Main processing logic
    │   ├── templates/          # Jinja2 templates & manager
    │   │   ├── __init__.py     # Template manager
    │   │   └── readme/
    │   │       ├── __init__.py
    │   │       └── default.md.j2
    │   └── utils/              # Utility functions
    │       ├── __init__.py
    │       └── logging.py
    └── tests/                  # Test suite
        ├── __init__.py
        ├── conftest.py         # Test configuration
        ├── fixtures/           # Test data (example roles)
        ├── integration/        # End-to-end tests
        └── unit/               # Unit tests
```


## Development Standards<a id="development-standard"></a>

This project follows these coding standards and rules:

- **Python Style**: [PEP 8](https://peps.python.org/pep-0008/) compliance.
- **Type Hints**: Use [type](https://docs.python.org/3/library/typing.html) annotations for all functions and methods.
- **Docstrings**: Use [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for all public functions, classes, and modules. Always use the three-double-quote `"""` format for docstrings (per [PEP 257](https://peps.python.org/pep-0257/))
- **Line Length**: Maximum 88 characters ([Black](https://black.readthedocs.io/en/stable/) default).
- **Import organization**: Follow [isort](https://pycqa.github.io/isort/) standards.
- **Error handling**: Use appropriate exception types and provide clear error messages.
- **Encoding, line ending:** Use UTF-8 encoding with `LF` (Line Feed `\n`) line endings *without* [BOM](https://en.wikipedia.org/wiki/Byte_order_mark) for all files.

The linting and formatting tool can take care of most of the rules (see next section).


### Code formatting and linting<a id="code-linting"></a>

The project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting. Ruff is installed as a development dependency:

```bash
# Format code (equivalent to Black)
uv run ruff format .

# Lint code (equivalent to flake8, isort, etc.)
uv run ruff check .

# Fix auto-fixable linting issues
uv run ruff check --fix .

# Check for specific rule violations
uv run ruff check --select E,W,F .
```

**Important**: Always run formatting and linting before committing:

```bash
# Format and lint in one go
uv run ruff format . && uv run ruff check --fix .
```

The project has Ruff configured in [`ansibledocsmith/pyproject.toml`](./ansibledocsmith/pyproject.toml)


## Testing<a id="testing"></a>

### Running tests<a id="running-tests"></a>

Execute the test suite to verify your changes:

```bash
# Run all tests
uv run pytest

# Run all tests with verbose output
uv run pytest -v
```

More examples:

```bash
# Run a specific test file
uv run pytest tests/unit/test_generator.py

# Run a specific test method
uv run pytest tests/unit/test_generator.py::TestDocumentationGenerator::test_generate_role_documentation

# Run tests with coverage
uv run pytest --cov=ansible_docsmith

# Run integration tests only
uv run pytest tests/integration/

# Run unit tests only
uv run pytest tests/unit/
```

Test your changes with real-world scenarios:

1. **Create test roles** with various `argument_specs.yml` configurations.
2. **Test edge cases** like missing files, invalid YAML, and so on.
3. **Verify generated output** matches expected format.
4. **Test both `README.md` file and `defaults/main.yml` entry point comment generation**.
5. **Test validation functionality**.


#### Manual testing examples<a id="manual-testing"></a>

Always use `--dry-run` when testing with fixture files to prevent modifications!

```bash
# Test with example role fixture (read-only)
uv run ansible-docsmith generate tests/fixtures/example-role-simple --dry-run
uv run ansible-docsmith generate tests/fixtures/example-role-multiple-entry-points --dry-run

# Test validation (read-only)
uv run ansible-docsmith validate tests/fixtures/example-role-simple
uv run ansible-docsmith validate tests/fixtures/example-role-multiple-entry-points

# Test with different options (read-only)
uv run ansible-docsmith generate tests/fixtures/example-role-simple --no-defaults --dry-run
uv run ansible-docsmith generate tests/fixtures/example-role-simple --no-readme --dry-run
uv run ansible-docsmith generate tests/fixtures/example-role-multiple-entry-points --no-defaults --dry-run
uv run ansible-docsmith generate tests/fixtures/example-role-multiple-entry-points --no-readme --dry-run
```

If you need to test actual file creation/modification, create a temporary copy:

```bash
# Create temporary copies for testing
cp -r tests/fixtures/example-role-* /tmp

uv run ansible-docsmith generate /tmp/example-role-simple
uv run ansible-docsmith generate /tmp/example-role-multiple-entry-points
```


### Test structure<a id="test-structure"></a>

- **Unit Tests**: Located in `tests/unit/` - Test individual components in isolation.
- **Integration Tests**: Located in `tests/integration/` - Test end-to-end functionality.
- **Fixtures**: Located in `tests/fixtures/` - Sample data for testing. Files in `tests/fixtures/` should NEVER be modified by tests or manual testing!
- **Test Configuration**: `tests/conftest.py` - Shared fixtures and configuration.


### Writing tests<a id="writing-tests"></a>

When adding new features or fixing bugs:

1. **Write tests first** ([Test-driven development (TDD)](https://en.wikipedia.org/wiki/Test-driven_development) approach recommended).
2. **Cover edge cases** and error conditions.
3. **Use descriptive test names** explaining what is being tested.
4. **Follow the existing test patterns** in the codebase.
5. **Ensure tests are isolated** and don't depend on external resources.


## Recommended development workflow<a id="development-workflow"></a>

### Before making changes<a id="before-making-changes"></a>

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Ensure tests pass**:
   ```bash
   uv run pytest
   ```

### Making changes<a id="making-changes"></a>

1. **Follow the coding standards** mentioned above.
2. **Write or update tests** for your changes.
3. **Update documentation** if needed.
4. **[Tests](#running-tests) your changes** thoroughly.


### Before committing<a id="before-committing"></a>

Always run this checklist before committing:

```bash
# 1. Format code
uv run ruff format .

# 2. Fix linting issues (if any)
uv run ruff check --fix .

# 3. Run all tests
uv run pytest

# 4. Test CLI functionality (always use --dry-run with fixtures!)
uv run ansible-docsmith --help
uv run ansible-docsmith generate tests/fixtures/example-role-simple --dry-run
```


## Releases<a id="releases"></a>

1. Do proper [Testing](#testing). Continue only if everything is fine.
2. Determine the next version number. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
3. Update several files to match the new release version:
   - [`CHANGELOG.md`](./CHANGELOG.md): Insert a section for the new release. Do not forget the comparison link at the end of the file.
   - [`ansibledocsmith/pyproject.toml`](./ansibledocsmith/pyproject.toml): the `version` variable.
   - [`ansibledocsmith/src/ansible_docsmith/__init__.py`](./ansibledocsmith/src/ansible_docsmith/__init__.py): the `__version__` variable.
4. If everything is fine: commit the changes, tag the release and push:
   ```bash
   version="<FIXME version>"
   git add \
     "./CHANGELOG.md" \
     "./ansibledocsmith/pyproject.toml" \
     "./ansibledocsmith/src/ansible_docsmith/__init__.py"
   git commit -m "Release preparations: v${version}"

   git tag "v${version}" "$(git rev-parse --verify HEAD)" -m "version ${version}"
   git show "v${version}"

   git push origin main --follow-tags
   ```
   If something minor went wrong (like missing `CHANGELOG.md` update), delete the tag and start over:
   ```bash
   git tag -d "v${version}" # delete the old tag locally
   git push origin ":refs/tags/v${version}" # delete the old tag remotely
   ```
   This is *only* possible if there was no [GitHub release](https://github.com/foundata/ansible-docsmith/releases/). Use a new patch version number otherwise.
5. Use [GitHub's release feature](https://github.com/foundata/ansible-docsmith/releases/new), select the tag you pushed and create a new release:
   * Use `v<version>` as title
   * A description is optional. In doubt, use `See CHANGELOG.md for more information about this release.`
6. Check if the GitHub API delivers the correct version as `latest`:
   ```bash
   curl -s -L https://api.github.com/repos/foundata/ansible-docsmith/releases/latest | jq -r '.tag_name' | sed -e 's/^v//g'
   ```


## Troubleshooting<a id="troubleshooting"></a>

### Common issues<a id="common-issues"></a>

- **Import errors**: Ensure you've installed the package in development mode with `uv sync`.
- **Test failures**: Check if you have the latest dependencies with `uv sync --all-groups`.
- **CLI not found**: Make sure you're using `uv run ansible-docsmith` or have activated the virtual environment.
