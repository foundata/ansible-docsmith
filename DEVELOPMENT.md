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

Markdown follows
[`guidelines/markdown-style-guide.md`](https://github.com/foundata/guidelines)
and is checked with the invocation it prescribes, which
[`tests/check_markdown.py`](./tests/check_markdown.py) carries so no local
configuration can alter the result:

```sh
# Check every Markdown file outside tests/fixtures
uv run python tests/check_markdown.py

# Apply what has a safe automatic fix
uv run python tests/check_markdown.py --format
```

The fixtures are excluded on purpose: they are the recorded input and expected
output of the generator under test, and formatting them would rewrite the
oracle the tests compare against.

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

The release tooling is the `release` command from foundata's
[releasing](https://github.com/foundata/releasing) package, a development
dependency of this project. It reads the `[tool.releasing]` table in
[`pyproject.toml`](./pyproject.toml).

1. Run the release checks and only continue if everything passes:

   ```sh
   ./scripts/release-check.sh
   ```

   This runs formatting, linting, type checks, the shell-script checks
   (`shfmt` and `shellcheck` over every shipped script, plus a dialect parse)
   and the test suite on every supported Python version, then builds the wheel
   and source distribution from a clean checkout of `HEAD` and smoke-tests the
   installed artifact (import and CLI). See also [Testing](#testing).
2. Determine the next version number. This project adheres to
   [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
3. Move the version and the changelog to the new release:

   ```sh
   version="<FIXME version>" # major.minor.patch

   uv run release version bump "${version}"
   uv run release changelog release "${version}"
   ```

   `version bump` rewrites the `version` in
   [`pyproject.toml`](./pyproject.toml) and runs `uv lock`, so the lockfile
   records the new version. The package reads its own version from the
   installed distribution metadata, so there is no second place to edit.
   `changelog release` turns the entries under `Unreleased` in
   [`CHANGELOG.md`](./CHANGELOG.md) into a dated section and updates the
   comparison links at the end of the file.
4. Review the changes and commit them. The tag will name this commit:

   ```sh
   git diff
   git add --all
   git commit -m "release: prepare ${version}"
   git status --short
   ```

   The last command must print nothing.
5. Build the distributions from the committed revision:

   ```sh
   uv run release build --out "../dist-${version}" --expect "${version}"
   ```

   The build exports the commit with `git archive` and prepares the
   `README.md` that ships in the artifacts inside that export: its
   repository-relative links become absolute GitHub URLs, so they resolve on
   pypi.org. The committed README keeps its relative links and the working
   tree is never modified. The source distribution is built from the export
   and the wheel from that source distribution; both are checked and their
   SHA-256 recorded in `artifacts.json`.
6. Tag the revision that was built, then publish the branch and the tag:

   ```sh
   uv run release tag create "${version}" \
     --manifest "../dist-${version}/artifacts.json"
   uv run release push "${version}"
   ```

   `tag create` refuses a dirty working tree, a version the sources and the
   changelog disagree on and, with `--manifest`, a revision other than the one
   those artifacts were built from. It also refuses a commit that credits a
   tool as its author; the `Assisted-by:` disclosure this project uses is
   allowed by `allowed-attribution` in [`pyproject.toml`](./pyproject.toml).
   `push` sends the branch before the tag and refuses when the branch does not
   contain the tagged commit. If something minor went wrong, delete the tag and
   start over:

   ```sh
   uv run release tag delete "${version}"
   ```

   This is refused once a
   [GitHub release](https://github.com/foundata/ansible-docsmith/releases/)
   exists for the tag. Use a new patch version then.
7. Publish exactly the files that were validated to
   [PyPI](https://pypi.org/project/ansible-docsmith/):

   ```sh
   printf 'PyPI API token: '
   read -rs UV_PUBLISH_TOKEN
   printf '\n'
   export UV_PUBLISH_TOKEN

   uv run release publish "../dist-${version}/artifacts.json"
   unset UV_PUBLISH_TOKEN
   ```

   `publish` re-checks every digest against the bytes on disk and uploads
   exactly the files the manifest names, so a file beside them that nothing
   validated is a refusal rather than an extra upload. Uploading needs a PyPI
   API token with upload rights for the project; the index tool reads it from
   `UV_PUBLISH_TOKEN`, which keeps the value out of the shell history and out
   of command lines visible in the process list.

   A version number can be uploaded only once. A broken release cannot be
   replaced, only [yanked](https://pypi.org/help/#yanked), and the fix needs a
   new patch version.
8. Create the GitHub release from the changelog section and the manifest:

   ```sh
   uv run release forge release-create "${version}" \
     --manifest "../dist-${version}/artifacts.json"
   ```

   The notes are the changelog section for the version and the attached files
   are the ones just published, so neither can drift from what was validated.
   The write itself goes through `gh`, which owns the authenticated session.
9. Verify what PyPI and GitHub now serve:

   ```sh
   uv run release verify "../dist-${version}/artifacts.json"
   ```

   This checks that PyPI serves the exact files whose digests the build
   recorded, that an isolated install reports the new version, and that the
   GitHub API reports the new tag as the latest release.

   ```sh
   uv run release status "${version}" \
     --manifest "../dist-${version}/artifacts.json"
   ```

   `status` reports the same release as separate steps and exits non-zero
   while any of them is unfinished, which is also how to resume after an
   interruption anywhere above.


## Troubleshooting<a id="troubleshooting"></a>

### Common issues<a id="common-issues"></a>

- **Import errors**: Ensure you've installed the package in development mode
  with `uv sync`.
- **Test failures**: Check if you have the latest dependencies with
  `uv sync --all-groups`.
- **CLI not found**: Make sure you're using `uv run ansible-docsmith` or have
  activated the virtual environment.
