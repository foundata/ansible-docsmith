# DocSmith for Ansible

**Automating role documentation (using `argument_specs.yml`)**

DocSmith is a documentation generator. It reads a role's
[`meta/argument_specs.yml`](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#specification-format)
and produces up‑to‑date variable descriptions for the `README.md` as well as
inline comment blocks for `defaults/main.yml` (or other role entry-point files).
It works with roles in both
[stand‑alone form](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html)
and within
[collections](https://docs.ansible.com/ansible/latest/collections_guide/index.html).


<div align="center" id="project-readme-header">
<br>
<br>

<img src="./assets/images/logos/ansible-docsmith.svg" alt="Logo: DocSmith for Ansible" height="128" />

<br>
<br>

**⭐ Found this useful? Support open-source and star this project:**

[![GitHub repository](https://img.shields.io/github/stars/foundata/ansible-docsmith.svg)](https://github.com/foundata/ansible-docsmith)

<br>
</div>


## Table of contents<a id="toc"></a>

- [Demo](#demo)
  - [Roles using DocSmith](#demo-roles)
  - [Screenshots](#demo-screenshots)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Preparations](#usage-preparations)
  - [Generate or update documentation](#usage-generate)
  - [Collections](#usage-collections)
  - [Validate `argument_specs.yml` and `/defaults`](#usage-validate)
  - [Exit codes](#usage-exit-codes)
  - [Custom templates](#usage-custom-templates)
- [Licensing, copyright](#licensing-copyright)
  - [Trademarks](#trademarks)
- [Author information](#author-information)


## Demo<a id="demo"></a>

### Roles using DocSmith<a id="demo-roles"></a>

- Ansible role: `foundata.acmesh.run`:
  1. [`README.md` with generated variable documentation](https://github.com/foundata/ansible-collection-acmesh/blob/main/roles/run/README.md#role-variables)
  2. [`defaults/main.yml` entry point with generated YAML comments](https://github.com/foundata/ansible-collection-acmesh/blob/main/roles/run/defaults/main.yml)
  3. [`argument_specs.yaml`](https://github.com/foundata/ansible-collection-acmesh/blob/main/roles/run/meta/argument_specs.yml)
     (source of truth)
- Ansible role: `foundata.sshd.run`:
  1. [`README.md` with generated variable documentation](https://github.com/foundata/ansible-collection-sshd/blob/main/roles/run/README.md#role-variables)
  2. [`defaults/main.yml` entry point with generated YAML comments](https://github.com/foundata/ansible-collection-sshd/blob/main/roles/run/defaults/main.yml)
  3. [`argument_specs.yaml`](https://github.com/foundata/ansible-collection-sshd/blob/main/roles/run/meta/argument_specs.yml)
     (source of truth)


### Screenshots<a id="demo-screenshots"></a>

[<img src="./assets/images/screenshots/ansible-docsmith-cli-01-help.png" alt="Screenshot: DocSmith CLI, help" height="128" />](./assets/images/screenshots/ansible-docsmith-cli-01-help.png)
&#160;
[<img src="./assets/images/screenshots/ansible-docsmith-cli-sshd-01-validate.png" alt="Screenshot: DocSmith CLI, validate; Results for foundata.sshd.run" height="128" />](./assets/images/screenshots/ansible-docsmith-cli-sshd-01-validate.png)
&#160;
[<img src="./assets/images/screenshots/ansible-docsmith-cli-sshd-02-generate-dry-run.png" alt="Screenshot: DocSmith CLI, generate dry run; Results for foundata.sshd.run" height="128" />](./assets/images/screenshots/ansible-docsmith-cli-sshd-02-generate-dry-run.png)
&#160;
[<img src="./assets/images/screenshots/ansible-docsmith-cli-sshd-03-generate.png" alt="Screenshot: DocSmith CLI, generate; Results for foundata.sshd.run" height="128" />](./assets/images/screenshots/ansible-docsmith-cli-sshd-03-generate.png)
&#160;
[<img src="./assets/images/screenshots/ansible-docsmith-readme-sshd-01-toc.png" alt="Screenshot: Part of a README.md ToC, generated with DocSmith" height="128" />](./assets/images/screenshots/ansible-docsmith-readme-sshd-01-toc.png)
&#160;
[<img src="./assets/images/screenshots/ansible-docsmith-readme-sshd-02-main.png" alt="Screenshot: Part of a README.md's main content describing role variables, generated with DocSmith" height="128" />](./assets/images/screenshots/ansible-docsmith-readme-sshd-02-main.png)


## Features<a id="features"></a>

- **Efficient and simple:** Uses the `argument_specs.yml` from
  [Ansible's built‑in role argument validation](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#role-argument-validation)
  as the single source of truth, generating human‑readable documentation in
  multiple places while maintaining just one file.
- **Built-in validation:** Verifies that argument specs are complete, correct,
  and in sync with entry-point `defaults/`.
- **Automation‑friendly:** Works seamlessly in CI/CD pipelines and pre‑commit
  hooks.
- **Supports Markdown and reStructuredText**.
- **Understands
  [Ansible markup](https://docs.ansible.com/projects/ansible/latest/dev_guide/ansible_markup.html):**
  Constructs like `C(...)`, `O(...)`, `V(...)` or `M(...)` in descriptions are
  converted to the target format.


## Installation<a id="installation"></a>

[![PyPI package version](https://img.shields.io/pypi/v/ansible-docsmith.svg?logo=pypi)](https://pypi.org/project/ansible-docsmith)

DocSmith needs Python ≥ v3.11. It is available on
[PyPI](https://pypi.org/project/ansible-docsmith/) and can be installed with the
package manager of your choice.

**Using [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
(recommended):**

```bash
uv tool install ansible-docsmith
```

**Using `pip` or `pipx`:**

```bash
pip install ansible-docsmith
pipx install ansible-docsmith
```

The minimum Python version is 3.11 (rather than the newer 3.12 baseline used for
most of our projects) so DocSmith runs on
[Debian 12 "Bookworm"](https://packages.debian.org/bookworm/python3).


## Usage<a id="usage"></a>

### Preparations<a id="usage-preparations"></a>

1. If not already existing, simply **create an `argument_specs.yml`** for
   [Ansible’s role argument validation](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#role-argument-validation).
   Try to add `description:` to your variables. The more complete your
   specification, the better the argument validation and documentation.
2. **Add simple markers in your role's `README.md`** where DocSmith shall
   maintain the human-readable documentation. All content between these markers
   will be removed and updated on each `ansible-docsmith generate` run:

   ```markdown
   <!-- ANSIBLE DOCSMITH MAIN START -->
   <!-- ANSIBLE DOCSMITH MAIN END -->
   ```

   where the variable descriptions shall be placed (mandatory) and

   ```markdown
   <!-- ANSIBLE DOCSMITH TOC START -->
   <!-- ANSIBLE DOCSMITH TOC END -->
   ```

   for putting list entries for a table of contents (ToC) (optional). These list
   only the DocSmith-managed variable documentation and are designed to be
   placed inside a hand-written ToC list. Alternatively, use

   ```markdown
   <!-- ANSIBLE DOCSMITH TOC-FULL START -->
   <!-- ANSIBLE DOCSMITH TOC-FULL END -->
   ```

   to generate a complete ToC of *all* headings of the README, including
   hand-written ones (optional). Headings with an explicit anchor (like
   `## Usage<a id="usage"></a>`) are linked exactly; for other headings, the
   anchor is derived from the heading text and `validate` emits a notice, as the
   derivation cannot be guaranteed to match your rendering platform for exotic
   titles.

That's it. The entry-point variable files below the `/defaults` directory of
your role do *not* need additional preparations. The tool will automatically
(re)place formatted inline comment blocks above variables defined there.

**The marker contract** in short:

- **All content between a START and END marker pair is owned by DocSmith** and
  gets replaced on every `generate` run. Everything outside the markers is never
  touched.
- **A lone marker is always an error**, no matter the type: a `START` without
  its `END` (or vice versa) fails validation instead of guessing where the
  managed section ends. This applies to `MAIN`, `TOC`, `TOC-FULL` and the
  role-named markers in collection READMEs alike.
- **A missing README is fine**: `generate` creates one from a basic skeleton,
  markers included. However, an *existing* README **without** the mandatory
  `MAIN` markers is a hard validation error, so DocSmith cannot accidentally
  overwrite hand-written content in a README that was never prepared for it.

Example files:

- Markdown:
  [`README.md`](./tests/fixtures/example-role-simple-toc/README.md?plain=1)
- reStructuredText:
  [`README.rst`](./tests/fixtures/example-role-simple-toc-rst/README.rst?plain=1)
  (difference to Markdown: `..` comments, `.. contents:: **Table of Contents**`
  directive)


### Generate or update documentation<a id="usage-generate"></a>

Basic usage:

```bash
# Safely preview changes without writing to files. No modifications are made.
ansible-docsmith generate /path/to/role --dry-run

# Check whether the documentation is up to date without writing files:
# exit code 1 (and a diff) if a run would change anything, 0 otherwise.
# Useful for CI/CD pipelines and pre-commit hooks.
ansible-docsmith generate /path/to/role --check

# Generate / update README.md and comments in entry-point files (like defaults/main.yml)
ansible-docsmith generate /path/to/role

# Show help
ansible-docsmith --help
ansible-docsmith generate --help
```

Advanced parameters:

```bash
# Generate / update only the README.md, skip comments for variables in
# entry-point files (like defaults/main.yml).
ansible-docsmith generate /path/to/role --no-defaults

# Generate / update only the comments in entry-point files (like defaults/main.yml),
# skip README.md
ansible-docsmith generate /path/to/role --no-readme

# Do not document nested options ("dict attributes") in the comments of
# entry-point files (like defaults/main.yml)
ansible-docsmith generate /path/to/role --no-defaults-comments-nested

# Verbose output for debugging
ansible-docsmith generate /path/to/role --verbose
```


### Collections<a id="usage-collections"></a>

`generate` and `validate` also accept a **collection** path. All roles found via
`roles/*/meta/argument_specs.yml` are then processed like single roles.
Additionally, DocSmith maintains role-named marker sections in the collection's
`README.md` (or `README.rst`), so the collection README can reference the role
documentation without manual upkeep:

```markdown
### My role: foo

<!-- ANSIBLE DOCSMITH TOC foo START -->
<!-- ANSIBLE DOCSMITH TOC foo END -->

### My role: bar

<!-- ANSIBLE DOCSMITH TOC-FULL bar START -->
<!-- ANSIBLE DOCSMITH TOC-FULL bar END -->

<!-- ANSIBLE DOCSMITH MAIN bar START -->
<!-- ANSIBLE DOCSMITH MAIN bar END -->
```

- `TOC <role>` lists the role's variable documentation, `TOC-FULL <role>` lists
  *all* headings of the role's README. Both link into `roles/<role>/README.*`
  using relative paths.
- `MAIN <role>` embeds the role's complete variable documentation directly in
  the collection README. All anchors get a `<role>-` prefix so several embedded
  roles cannot collide on variable names. If a `TOC <role>` section exists in
  the same (Markdown) document, it links to the embedded documentation instead
  of the role's README.
- Role-named sections are opt-in per role: roles without markers are simply not
  referenced in the collection README (`validate` emits a notice listing them).
  Markers referencing an unknown role produce a warning.

```bash
ansible-docsmith generate /path/to/collection
ansible-docsmith validate /path/to/collection
ansible-docsmith generate /path/to/collection --check
```


### Validate `argument_specs.yml` and `/defaults`<a id="usage-validate"></a>

```bash
# Validate argument_specs.yml structure as well as role entry-point files in /defaults/.
# These validation checks include:
#
# - ERROR:   Variables present in "defaults/" but missing from "argument_specs.yml".
# - ERROR:   Variables with "default:" values defined in "argument_specs.yml" but
#            missing from the entry-point files in "defaults/".
# - WARNING: Unknown keys in "argument_specs.yml".
# - WARNING: Invalid Ansible markup in descriptions (like "M()" without a FQCN).
# - NOTICE:  Potential mismatches, where variables are listed in "argument_specs.yml"
#            but not in "defaults/", for user awareness.
# - NOTICE:  Variables whose name suggests a secret (like "*_password", "*_token")
#            but do not set "no_log: true".
ansible-docsmith validate /path/to/role

# Treat warnings as errors (exit code 1). Useful for CI/CD pipelines and
# pre-commit hooks. Notices do not fail validation.
ansible-docsmith validate /path/to/role --strict

# Validate only parts of a role:
#
# Skip the README checks (markers and ToC). Useful when only maintaining
# comments in entry-point files.
ansible-docsmith validate /path/to/role --no-readme
# Skip the argument_specs.yml checks (consistency, unknown keys, ...).
# The file must still be parseable YAML.
ansible-docsmith validate /path/to/role --no-argument-specs

# Show help
ansible-docsmith --help
ansible-docsmith validate --help

# Verbose output for debugging
ansible-docsmith validate /path/to/role --verbose
```


### Exit codes<a id="usage-exit-codes"></a>

All commands use conventional exit codes, so DocSmith can be wired into scripts,
CI/CD pipelines and pre-commit hooks without output parsing:

| Exit code | Meaning |
| --------- | ------- |
| `0`       | Success. Warnings and notices alone do *not* fail a run (unless `--strict` is used). `generate --check` returns `0` when the documentation is up to date. |
| `1`       | Validation or processing error (like missing `MAIN` markers, inconsistencies between `argument_specs.yml` and `defaults/`). Also: warnings when `validate --strict` is used, and pending changes when `generate --check` is used. |
| `2`       | Command line usage error (unknown option, non-existing path). |

Notices are informational and never affect the exit code. A typical gate:

```bash
ansible-docsmith validate /path/to/role --strict && \
    ansible-docsmith generate /path/to/role --check
```


### Custom templates<a id="usage-custom-templates"></a>

You can customize the generated output by providing your own
[Jinja2 template](https://jinja.palletsprojects.com/en/stable/templates/). The
rendered content will be inserted between the `ANSIBLE DOCSMITH MAIN START` and
`END` markers in the role's README. Name the file `*.md.j2` for Markdown or
`*.rst.j2` for reStructuredText, matching the README format of the role.

```bash
# Use a custom template for README generation
ansible-docsmith generate /path/to/role --template-readme /path/to/custom-template.md.j2

# Combined with other options
ansible-docsmith generate /path/to/role --template-readme ./templates/my-readme.md.j2 --dry-run
```

Template files must use the `.j2` extension (for example, `simple-readme.md.j2`)
and follow Jinja2 syntax. Below is a basic example:

```jinja
# {{ role_name | title }} Ansible Role

{% if has_options %}
## Role variables

{% for var_name, var_spec in options.items() %}
- **{{ var_name }}** ({{ var_spec.type }}): {{ var_spec.description }}
{% endfor %}
{% else %}
The role has no configurable variables.
{% endif %}
```

**Check out the
[`readme/default.md.j2`](./src/ansible_docsmith/templates/readme/default.md.j2)**
template that DocSmith uses as an advanced example with conditional sections.
Copying this file is often the easiest way to get started.

**Available template variables** (the context contract):

|       Variable        |    Type     | Description |
| --------------------- | ----------- | ----------- |
| `specs`               | `dict`      | All entry points in spec file order: entry point name → normalized spec. This is the recommended way to render complete documentation (the built-in templates iterate it). |
| `role_name`           | `str`       | Name of the Ansible role (directory name). |
| `role_path`           | `Path`      | Path to the role directory. |
| `entry_points`        | `list[str]` | All entry-point names, in spec file order. |
| `anchor_ns`           | `str`       | Anchor namespace to prepend to every anchor and internal link the template generates. Empty for role READMEs; `<role>-` when the content is embedded into a collection README via `MAIN <role>` markers. Use it like the built-in templates do, or embedded content of several roles may collide. |
| `primary_entry_point` | `str`       | *Backwards compatibility:* name of the first entry point. |
| `primary_spec`        | `dict`      | *Backwards compatibility:* spec of the first entry point (keys: `short_description`, `description`, `author`, `version_added`, `options`). |
| `options`             | `dict`      | *Backwards compatibility:* variables of the first entry point only. |
| `has_options`         | `bool`      | *Backwards compatibility:* whether the first entry point defines variables. |

Each entry in an `options` dictionary maps a variable name to its normalized
specification with the keys `type`, `required`, `default`, `description`,
`choices`, `elements`, `options` (nested sub-options, same structure),
`version_added`, `no_log` and `aliases`.

**Available Jinja2 filters** (signatures show the optional arguments):

|                                              Filter                                              | Description |
| ------------------------------------------------------------------------------------------------ | ----------- |
| `format_description(value)`                                                                      | Formats a description (string or list of paragraphs) for regular display, including [Ansible markup](https://docs.ansible.com/projects/ansible/latest/dev_guide/ansible_markup.html) conversion. |
| `format_table_description(value, variable_name=None, max_length=250, anchor_prefix="variable-")` | Formats a description for a table cell: markup conversion, HTML stripping, single-line folding and truncation with a `[…]` link to `#<anchor_prefix><variable_name>`. Set `max_length=0` to disable truncation. |
| `format_default(value, table=False)`                                                             | Formats a default value as inline code (`N/A` for `None`). Pass `true` inside Markdown table cells so pipes get escaped. |
| `code_escape(value, table=False)`                                                                | Renders a value as inline code, handling backticks correctly. Pass `true` inside Markdown table cells. |
| `ansible_escape(value)`                                                                          | Escapes Ansible Jinja2 syntax (`{{ }}`) so it renders literally (Markdown only). |
| `csv_escape(value)`                                                                              | Escapes double quotes for `csv-table` cells (reStructuredText templates only). |

**Stability:** the variables and filters documented above are the supported
contract and only change with a major release (deprecated values like `options`
may then disappear). Anything else you might discover by reading DocSmith's
internals — undocumented context values, filter internals, module layout — can
change in any release.

If you are creative, you may even maintain non-obvious parts of your `README.md`
between the markers:

````jinja
## Example Playbook

```yaml
[...]
- ansible.builtin.include_role:
    name: "{{ role_name }}"
  vars:
{% for var_name, var_spec in options.items() %}
{% if var_spec.default is not none %}
    {{ var_name }}: {{ var_spec.default }}
{% else %}
    # {{ var_name }}: # {{ var_spec.description }}
{% endif %}
{% endfor %}
```

## Author Information

{% if primary_spec.author %}
{% for author in primary_spec.author %}

- {{ author }}
{% endfor %}
{% endif %}
````


## Licensing, copyright<a id="licensing-copyright"></a>

<!--REUSE-IgnoreStart-->
Copyright (c) 2025, 2026 [foundata GmbH](https://foundata.com/)
(<https://foundata.com>)

This project is licensed under the GNU General Public License v3.0 or later
(SPDX-License-Identifier: `GPL-3.0-or-later`), see
[`LICENSES/GPL-3.0-or-later.txt`](./LICENSES/GPL-3.0-or-later.txt) for the full
text.

The [`REUSE.toml`](./REUSE.toml) file provides detailed licensing and copyright
information in a human- and machine-readable format. This includes parts that
may be subject to different licensing or usage terms, such as third-party
components. The repository conforms to the
[REUSE specification](https://reuse.software/spec/). You can use
[`reuse spdx`](https://reuse.readthedocs.io/en/latest/readme.html#cli) to create
a
[SPDX software bill of materials (SBOM)](https://en.wikipedia.org/wiki/Software_Package_Data_Exchange).
<!--REUSE-IgnoreEnd-->

[![REUSE status](https://api.reuse.software/badge/github.com/foundata/ansible-docsmith)](https://api.reuse.software/info/github.com/foundata/ansible-docsmith)


### Trademarks<a id="trademarks"></a>

- Red Hat® is a trademark of Red Hat, Inc., registered in the US and other
  countries.
- Ansible® is a trademark of Red Hat, Inc., registered in the US and other
  countries.

Their use here is purely descriptive and does not imply any affiliation with or
endorsement by the trademark holders.


## Author information<a id="author-information"></a>

This project was created and is maintained by [foundata](https://foundata.com/).
If you like it, you might
[buy us a coffee](https://buy-me-a.coffee/ansible-docsmith/).

The Ansible DocSmith project is *not* associated with
[Red Hat](https://www.redhat.com/) nor the
[Ansible project](https://ansible.com/).
