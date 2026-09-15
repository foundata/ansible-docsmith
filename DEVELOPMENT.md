# Development

This file provides information for maintainers and contributors to
`ansible-docsmith`.


## Table of contents<a id="toc"></a>

- [Prerequisites](#prerequisites)
- [Getting started](#getting-started)
- [Project structure](#project-structure)
- [Development standards](#development-standards)
  - [Code formatting and linting](#code-linting)
  - [Commit messages and scopes](#commit-scopes)
- [Testing](#testing)
  - [Running tests](#running-tests)
  - [Manual testing examples](#manual-testing)
  - [Test structure](#test-structure)
  - [Writing tests](#writing-tests)
- [Recommended development workflow](#development-workflow)
  - [Before making changes](#before-making-changes)
  - [Making changes](#making-changes)
  - [Before committing](#before-committing)
- [Releases](#releases)
- [Troubleshooting](#troubleshooting)
  - [Common issues](#common-issues)


## Prerequisites<a id="prerequisites"></a>

- **Python 3.11 or later** - Required for running the application.
- **Git** - For version control
- **[`uv`](https://docs.astral.sh/uv/getting-started/installation/)** - Python
  package manager (recommended) or `pip` as fallback
- **[shfmt](https://github.com/mvdan/sh)** and
  **[shellcheck](https://www.shellcheck.net/)** for `scripts/release-check.sh`'s
  self-check. Fedora: `sudo dnf install shfmt ShellCheck`. Debian 13+ / Ubuntu
  24.04+: `sudo apt install shfmt shellcheck`. The release gate fails without
  them.


## Getting started<a id="getting-started"></a>

1. Clone the repository:

   ```sh
   git clone https://github.com/foundata/ansible-docsmith.git
   cd ansible-docsmith
   ```

2. Set up development environment:
   Install dependencies using `uv` (recommended):

   ```sh
   # Install all dependencies including development dependencies
   uv sync --all-groups

   # Alternative: Install only production dependencies
   uv sync
   ```

   Or using `pip` (fallback):

   ```sh
   # Create virtual environment
   python -m venv .venv
   source .venv/bin/activate

   # Install in development mode
   pip install -e .
   pip install pytest  # For testing
   ```

3. Test that the installation works:

   ```sh
   # Show help
   uv run ansible-docsmith --help

   # Show version
   uv run ansible-docsmith --version

   # Test with example role fixture (always use --dry-run to protect fixtures)
   uv run ansible-docsmith generate tests/fixtures/example-role-simple --dry-run
   ```


## Project structure<a id="project-structure"></a>

```text
ansible-docsmith/
├── CHANGELOG.md
├── CONTRIBUTING.md
├── DEVELOPMENT.md               # This file
├── README.md
├── REUSE.toml
├── LICENSES/                    # License texts (SPDX)
├── assets/                      # Logos and screenshots
├── .python-version
├── pyproject.toml               # Project configuration
├── uv.lock                      # Dependency lock file
├── scripts/
│   └── release-check.sh         # Local release gate (checks + build + smoke)
├── src/ansible_docsmith/        # Main package
│   ├── __init__.py
│   ├── cli.py                   # CLI interface
│   ├── constants.py             # Global constants
│   ├── core/                    # Core functionality
│   │   ├── __init__.py
│   │   ├── collection.py        # Collection detection and processing
│   │   ├── defaults_comments.py # Comment blocks for entry-point files
│   │   ├── doc_generators.py    # README documentation generators (MD, RST)
│   │   ├── exceptions.py        # Custom exceptions
│   │   ├── markdown_ast.py      # Shared Markdown parsing (markdown-it-py)
│   │   ├── markup.py            # Ansible markup conversion
│   │   ├── parser.py            # YAML parsing
│   │   ├── processor.py         # Main processing logic
│   │   ├── readme_updater.py    # Managed README sections
│   │   ├── text.py              # Shared text utilities
│   │   └── toc.py               # Table of Contents generators
│   ├── templates/               # Jinja2 templates & manager
│   │   ├── __init__.py          # Template manager
│   │   └── readme/
│   │       ├── __init__.py
│   │       ├── default.md.j2
│   │       └── default.rst.j2
│   └── utils/                   # Utility functions
│       ├── __init__.py
│       └── logging.py
└── tests/                       # Test suite
    ├── __init__.py
    ├── conftest.py              # Test configuration
    ├── fixtures/                # Test data (example roles)
    ├── integration/             # End-to-end tests
    └── unit/                    # Unit tests
```


## Development standards<a id="development-standards"></a>

This project follows these coding standards and rules:

- **Python Style**: [PEP 8](https://peps.python.org/pep-0008/) compliance.
- **Type Hints**: Use [type](https://docs.python.org/3/library/typing.html)
  annotations for all functions and methods.
- **Docstrings**: Use
  [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
  for all public functions, classes, and modules. Always use the
  three-double-quote `"""` format for docstrings (per
  [PEP 257](https://peps.python.org/pep-0257/))
- **Line Length**: Maximum 88 characters
  ([Black](https://black.readthedocs.io/en/stable/) default).
- **Import organization**: Follow [isort](https://pycqa.github.io/isort/)
  standards.
- **Error handling**: Use appropriate exception types and provide clear error
  messages.
- **Encoding, line ending:** Use UTF-8 encoding with `LF` (Line Feed `\n`) line
  endings *without* [BOM](https://en.wikipedia.org/wiki/Byte_order_mark) for all
  files.

The linting and formatting tool can take care of most of the rules (see next
section).


### Code formatting and linting<a id="code-linting"></a>

The project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and
formatting. Ruff is installed as a development dependency:

```sh
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

```sh
# Format and lint in one go
uv run ruff format . && uv run ruff check --fix .
```

The project has Ruff configured in [`pyproject.toml`](./pyproject.toml)

Shell scripts follow
[`guidelines/shell-scripting-style-guide.md`](https://github.com/foundata/guidelines)
and are checked with the tools and option sets it prescribes.
`scripts/release-check.sh` runs them over every shipped script, including
itself, so the quickest way to check a shell-script change is to run that step.


### Commit messages and scopes<a id="commit-scopes"></a>

Commit messages follow the foundata guideline (`guidelines/git-commits.md`):
`<scope>: <description>`, imperative, lowercase description, body only for
context the diff cannot preserve. Scopes in use:

|                    Scope                    | Area |
| ------------------------------------------- | ---- |
| `cli`                                       | `src/ansible_docsmith/cli.py` |
| `core`                                      | `src/ansible_docsmith/core/` (collection, parsing, processing, markup, README/entry-point generation) |
| `templates`                                 | `src/ansible_docsmith/templates/` |
| `utils`                                     | `src/ansible_docsmith/utils/` |
| `tests`                                     | the test suite |
| `build`, `dependencies`                     | packaging, lockfile |
| `licensing`, `release`, `repository`/`repo` | licensing files, release preparation, repository-wide concerns |

`docs` is not a scope: the foundata guideline lists it among the Conventional
Commits types a scope must not be written as. A commit that only changes
documentation still uses the scope of the subsystem it documents
(`core: record the marker contract`), or a cross-cutting scope such as
`repository` when the documentation is not about one subsystem.


## Testing<a id="testing"></a>

### Running tests<a id="running-tests"></a>

Execute the test suite to verify your changes:

```sh
# Run all tests
uv run pytest
uv run python -m pytest # alternative call

# Run all tests with verbose output
uv run pytest -v
uv run python -m pytest -v # alternative call
```

More examples:

```sh
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
4. **Test both `README.md` file and `defaults/main.yml` entry point comment
   generation**.
5. **Test validation functionality**.


#### Manual testing examples<a id="manual-testing"></a>

Always use `--dry-run` when testing with fixture files to prevent modifications!

```sh
# Test with example role fixture (read-only)
uv run ansible-docsmith generate tests/fixtures/example-role-simple --dry-run
uv run ansible-docsmith generate tests/fixtures/example-role-multiple-entry-points --dry-run
uv run ansible-docsmith generate tests/fixtures/example-role-simple-rst --dry-run

# Test validation (always a read-only operation): success
uv run ansible-docsmith validate tests/fixtures/example-role-multiple-entry-points

# Test validation (always a read-only operation): success with warning
uv run ansible-docsmith validate tests/fixtures/example-role-simple

# Test validation (always a read-only operation): failure
uv run ansible-docsmith validate tests/fixtures/example-role-mismatch-spec-defaults
uv run ansible-docsmith validate tests/fixtures/example-role-missing-readme-markers

# Test with different options (read-only)
uv run ansible-docsmith generate tests/fixtures/example-role-simple --no-defaults --dry-run
uv run ansible-docsmith generate tests/fixtures/example-role-simple --no-readme --dry-run
uv run ansible-docsmith generate tests/fixtures/example-role-multiple-entry-points --no-defaults --dry-run
uv run ansible-docsmith generate tests/fixtures/example-role-multiple-entry-points --no-readme --dry-run
```

If you need to test actual file creation/modification, create a temporary copy:

```sh
# Create temporary copies for testing
cp -r tests/fixtures/example-role-* /tmp

uv run ansible-docsmith generate /tmp/example-role-simple
uv run ansible-docsmith generate /tmp/example-role-simple-toc
uv run ansible-docsmith generate /tmp/example-role-simple-toc-rst
uv run ansible-docsmith generate /tmp/example-role-simple-toc-rst-fallback
uv run ansible-docsmith generate /tmp/example-role-multiple-entry-points
uv run ansible-docsmith generate /tmp/example-role-simple-rst
```


### Test structure<a id="test-structure"></a>

- **Unit Tests**: Located in `tests/unit/` - Test individual components in
  isolation.
- **Integration Tests**: Located in `tests/integration/` - Test end-to-end
  functionality.
- **Fixtures**: Located in `tests/fixtures/` - Sample data for testing. Files in
  `tests/fixtures/` should NEVER be modified by tests or manual testing!
- **Test Configuration**: `tests/conftest.py` - Shared fixtures and
  configuration.


### Writing tests<a id="writing-tests"></a>

When adding new features or fixing bugs:

1. **Write tests first**
   ([Test-driven development (TDD)](https://en.wikipedia.org/wiki/Test-driven_development)
   approach recommended).
2. **Cover edge cases** and error conditions.
3. **Use descriptive test names** explaining what is being tested.
4. **Follow the existing test patterns** in the codebase.
5. **Ensure tests are isolated** and don't depend on external resources.


## Recommended development workflow<a id="development-workflow"></a>

### Before making changes<a id="before-making-changes"></a>

1. **Create a feature branch**:

   ```sh
   git checkout -b feature/your-feature-name
   ```

2. **Ensure tests pass**:

   ```sh
   uv run pytest
   ```

### Making changes<a id="making-changes"></a>

1. **Follow the coding standards** mentioned above.
2. **Write or update tests** for your changes.
3. **Update documentation** if needed.
4. **[Tests](#running-tests) your changes** thoroughly.


### Before committing<a id="before-committing"></a>

Always run this checklist before committing:

```sh
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

1. Run the release checks and only continue if everything passes:

   ```sh
   ./scripts/release-check.sh
   ```

   This runs formatting, linting, type checks, the shell-script checks (`shfmt`
   and `shellcheck` over every shipped script, plus a dialect parse) and the
   test suite on every supported Python version, then builds the wheel and
   source distribution and smoke-tests the installed artifact (import and
   CLI). See also [Testing](#testing).
2. Determine the next version number. This project adheres to
   [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
3. Update several files to match the new release version:
   - [`CHANGELOG.md`](./CHANGELOG.md): Insert a section for the new release. Do
     not forget the comparison link at the end of the file.
   - [`uv.lock`](./uv.lock): updated by running `uv lock` after the
     `pyproject.toml` bump, never edited by hand. It records a version per
     package, so a hand-edited lockfile can claim a dependency version that was
     never resolved.
   - [`pyproject.toml`](./pyproject.toml): the `version` variable.
   - [`src/ansible_docsmith/__init__.py`](./src/ansible_docsmith/__init__.py):
     the `__version__` variable.
   - The following snippet can help with the Python files:

     ```sh
     old_version="<FIXME version>" # major.minor.patch
     new_version="<FIXME version>" # major.minor.patch

     files=(
      "./pyproject.toml"
      "./src/ansible_docsmith/__init__.py"
     )

     old_version_regex="${old_version//./\\.}"
     version_pattern="^([[:space:]]*(__version__|version)[[:space:]]*[:=][[:space:]]*)\"?${old_version_regex}\"?$"

     for file in "${files[@]}"; do
       echo "Before: $file"
       grep -B 1 -E "$version_pattern" "$file" || true
       sed -i -E "s@${version_pattern}@\1\"${new_version}\"@" "$file"
       echo "After: $file"
       grep -B 1 -E "^([[:space:]]*(__version__|version)[[:space:]]*[:=][[:space:]]*)\"?${new_version}\"?$" "$file" || true
       echo
     done

     uv lock # the lockfile records the project version
     ```

4. If everything is fine: commit the changes, tag the release and push:

   ```sh
   version="<FIXME version>" # major.minor.patch
   git add \
     "./CHANGELOG.md" \
     "./uv.lock" \
     "./pyproject.toml" \
     "./src/ansible_docsmith/__init__.py"
   git commit -m "release: prepare ${version}"

   git tag "v${version}" "$(git rev-parse --verify HEAD)" -m "version ${version}"
   git show "v${version}"

   git push origin main --follow-tags
   ```

   If something minor went wrong (like missing `CHANGELOG.md` update), delete
   the tag and start over:

   ```sh
   git tag -d "v${version}" # delete the old tag locally
   git push origin ":refs/tags/v${version}" # delete the old tag remotely
   ```

   This is *only* possible if there was no
   [GitHub release](https://github.com/foundata/ansible-docsmith/releases/). Use
   a new patch version number otherwise.
5. Prepare the `README.md` that ships with the artifacts by rewriting its
   relative links as absolute GitHub URLs (see Wiki "Process: Release Python
   artifacts"; an internal `foundata` helper script is available for this).
   These changes are made only in the working tree between the tag and the
   upload; nothing is ever committed. This is why the step belongs here rather
   than before step 4.
6. Build the package and publish it to
   [PyPI](https://pypi.org/project/ansible-docsmith/). The build in step 1 ran
   before the version bump, so `dist/` still holds artifacts of the old version
   and has to be rebuilt:

   ```sh
   rm -rf "./dist"
   uv build
   ls -1 "./dist" # a wheel and a source distribution, both carrying the new version
   ```

   Validate exactly these files before uploading; the release check in step 1
   ran before the version bump and the README preparation, so it never saw them.
   This verifies the version, the tag on `HEAD`, the prepared README and that
   the working tree carries no other changes:

   ```sh
   scripts/release-check.sh --artifacts
   ```

   Uploading needs a PyPI API token with upload rights for the project.
   `uv publish` reads it from `UV_PUBLISH_TOKEN`; keep the value out of the
   shell history and out of command lines visible in the process list:

   ```sh
   printf 'PyPI API token: '
   read -rs UV_PUBLISH_TOKEN
   printf '\n'
   export UV_PUBLISH_TOKEN

   uv publish
   unset UV_PUBLISH_TOKEN
   ```

   A version number can be uploaded only once. A broken release cannot be
   replaced, only [yanked](https://pypi.org/help/#yanked), and the fix needs a
   new patch version.

   Throw the prepared `README.md` away once the upload succeeded:

   ```sh
   git restore "./README.md"
   git status # expect a clean working tree
   ```

7. Verify that the published package installs and runs from PyPI:

   ```sh
   uv run --isolated --no-project --with "ansible-docsmith==${version}" -- ansible-docsmith --version
   ```

8. Use
   [GitHub's release feature](https://github.com/foundata/ansible-docsmith/releases/new),
   select the tag you pushed and create a new release:
   - Use `v<version>` as title
   - A description is optional. In doubt, use
     `See CHANGELOG.md for more information about this release.`
9. Check if the GitHub API delivers the correct version as `latest`:

   ```sh
   curl -s -L https://api.github.com/repos/foundata/ansible-docsmith/releases/latest | jq -r '.tag_name' | sed -e 's/^v//g'
   ```


## Troubleshooting<a id="troubleshooting"></a>

### Common issues<a id="common-issues"></a>

- **Import errors**: Ensure you've installed the package in development mode
  with `uv sync`.
- **Test failures**: Check if you have the latest dependencies with
  `uv sync --all-groups`.
- **CLI not found**: Make sure you're using `uv run ansible-docsmith` or have
  activated the virtual environment.
