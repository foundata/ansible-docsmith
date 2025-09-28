# DocSmith for Ansible

**Automating role documentation (using `argument_specs.yml`)**

DocSmith is a documentation generator. It reads a role's [`meta/argument_specs.yml`](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#specification-format) and produces up‑to‑date variable descriptions for the `README.md` as well as inline comment blocks for `defaults/main.yml` (or other role entry-point files). It works with roles in both [stand‑alone form](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html) and within [collections](https://docs.ansible.com/ansible/latest/collections_guide/index.html).


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
  - [Validate `argument_specs.yml` and `/defaults`](#usage-validate)
  - [Custom templates](#usage-custom-templates)
- [Licensing, copyright](#licensing-copyright)
  - [Trademarks](#trademarks)
- [Author information](#author-information)


## Demo<a id="demo"></a>

### Roles using DocSmith<a id="demo-roles"></a>

* Ansible role: `foundata.acmesh.run`:
  1. [`README.md` with generated variable documentation](https://github.com/foundata/ansible-collection-acmesh/blob/main/roles/run/README.md#role-variables)
  2. [`defaults/main.yml` entry point with generated YAML comments](https://github.com/foundata/ansible-collection-acmesh/blob/main/roles/run/defaults/main.yml)
  3. [`argument_specs.yaml`](https://github.com/foundata/ansible-collection-acmesh/blob/main/roles/run/meta/argument_specs.yml) (source of truth)
* Ansible role: `foundata.sshd.run`:
  1. [`README.md` with generated variable documentation](https://github.com/foundata/ansible-collection-sshd/blob/main/roles/run/README.md#role-variables)
  2. [`defaults/main.yml` entry point with generated YAML comments](https://github.com/foundata/ansible-collection-sshd/blob/main/roles/run/defaults/main.yml)
  3. [`argument_specs.yaml`](https://github.com/foundata/ansible-collection-sshd/blob/main/roles/run/meta/argument_specs.yml) (source of truth)


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

- **Efficient and simple:** Uses the `argument_specs.yml` from [Ansible's built‑in role argument validation](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#role-argument-validation) as the single source of truth, generating human‑readable documentation in multiple places while maintaining just one file.
- **Built-in validation:** Verifies that argument specs are complete, correct, and in sync with entry-point `defaults/`.
- **Automation‑friendly:** Works seamlessly in CI/CD pipelines and pre‑commit hooks.
- **Supports Markdown and reStructuredText**.


## Installation<a id="installation"></a>

[![PyPI package version](https://img.shields.io/pypi/v/ansible-docsmith.svg?logo=pypi)](https://pypi.org/project/ansible-docsmith)

DocSmith needs Python ≥ v3.11. It is available on [PyPI](https://pypi.org/project/ansible-docsmith/) and can be installed with the package manager of your choice.

**Using [`uv`](https://docs.astral.sh/uv/getting-started/installation/) (recommended):**

```bash
uv tool install ansible-docsmith
```

**Using `pip` or `pipx`:**

```bash
pip install ansible-docsmith
pipx install ansible-docsmith
```


## Usage<a id="usage"></a>

### Preparations<a id="usage-preparations"></a>

1. If not already existing, simply **create an `argument_specs.yml`** for [Ansible’s role argument validation](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#role-argument-validation). Try to add `description:` to your variables. The more complete your specification, the better the argument validation and documentation.
2. **Add simple markers in your role's `README.md`** where DocSmith shall maintain the human-readable documentation. All content between these markers will be removed and updated on each `ansible-docsmith generate` run:
   ```markdown
   <!-- ANSIBLE DOCSMITH MAIN START -->
   <!-- ANSIBLE DOCSMITH MAIN END -->
   ```
   where the variable descriptions shall be placed (mandatory) and
   ```markdown
   <!-- ANSIBLE DOCSMITH TOC START -->
   <!-- ANSIBLE DOCSMITH TOC END -->
   ```
   for putting list entries for a table of contents (ToC) (optional).

That's it. The entry-point variable files below the `/defaults` directory of your role do *not* need additional preparations. The tool will automatically (re)place formatted inline comment blocks above variables defined there.

Example files:

* Markdown: [`README.md`](./ansibledocsmith/tests/fixtures/example-role-simple-toc/README.md?plain=1)
* reStructuredText: [`README.rst`](./ansibledocsmith/tests/fixtures/example-role-simple-toc-rst/README.rst?plain=1) (difference to Markdown: `.. ` comments, `.. contents:: **Table of Contents**` directive)


### Generate or update documentation<a id="usage-generate"></a>

Basic usage:

```bash
# Safely preview changes without writing to files. No modifications are made.
ansible-docsmith generate /path/to/role --dry-run

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

# Verbose output for debugging
ansible-docsmith generate /path/to/role --verbose
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
# - NOTICE:  Potential mismatches, where variables are listed in "argument_specs.yml"
#            but not in "defaults/", for user awareness.
ansible-docsmith validate /path/to/role

# Show help
ansible-docsmith --help
ansible-docsmith validate --help

# Verbose output for debugging
ansible-docsmith validate /path/to/role --verbose
```


### Custom templates<a id="usage-custom-templates"></a>

You can customize the generated Markdown output by providing your own [Jinja2 template](https://jinja.palletsprojects.com/en/stable/templates/). The rendered content will be inserted between the `<!-- ANSIBLE DOCSMITH MAIN START -->` and `<!-- ANSIBLE DOCSMITH MAIN END -->` markers in the role's `README.md` file.

```bash
# Use a custom template for README generation
ansible-docsmith generate /path/to/role --template-readme /path/to/custom-template.md.j2

# Combined with other options
ansible-docsmith generate /path/to/role --template-readme ./templates/my-readme.md.j2 --dry-run
```

Template files must use the `.j2` extension (for example, `simple-readme.md.j2`) and follow Jinja2 syntax. Below is a basic example:

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

**Check out the [`readme/default.md.j2`](./ansibledocsmith/src/ansible_docsmith/templates/readme/default.md.j2)** template that DocSmith uses as an advanced example with conditional sections. Copying this file is often the easiest way to get started.

**Most important available template variables:**
- `role_name`: Name of the Ansible role.
- `has_options`: Boolean indicating if variables are defined.
- `options`: Dictionary of all role variables with their specifications.
- `entry_points`: List of all Ansible role entry-point names.

**Most important available Jinja2 filters:**
- `ansible_escape`: Escapes characters for Ansible/YAML contexts.
- `code_escape`: Escapes content for code blocks.
- `format_default`: Formats default values appropriately.
- `format_description`: Formats multi-line descriptions.
- `format_table_description`: Formats descriptions for table cells.

If you are creative, you may even maintain non-obvious parts of your `README.md` between the markers:

~~~jinja
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
~~~


## Licensing, copyright<a id="licensing-copyright"></a>

<!--REUSE-IgnoreStart-->
Copyright (c) 2025 foundata GmbH (https://foundata.com)

This project is licensed under the GNU General Public License v3.0 or later (SPDX-License-Identifier: `GPL-3.0-or-later`), see [`LICENSES/GPL-3.0-or-later.txt`](./LICENSES/GPL-3.0-or-later.txt) for the full text.

The [`REUSE.toml`](./REUSE.toml) file provides detailed licensing and copyright information in a human- and machine-readable format. This includes parts that may be subject to different licensing or usage terms, such as third-party components. The repository conforms to the [REUSE specification](https://reuse.software/spec/). You can use [`reuse spdx`](https://reuse.readthedocs.io/en/latest/readme.html#cli) to create a [SPDX software bill of materials (SBOM)](https://en.wikipedia.org/wiki/Software_Package_Data_Exchange).
<!--REUSE-IgnoreEnd-->

[![REUSE status](https://api.reuse.software/badge/github.com/foundata/ansible-docsmith)](https://api.reuse.software/info/github.com/foundata/ansible-docsmith)


### Trademarks<a id="trademarks"></a>

* Red Hat® is a trademark of Red Hat, Inc., registered in the US and other countries.
* Ansible® is a trademark of Red Hat, Inc., registered in the US and other countries.


## Author information<a id="author-information"></a>

This project was created and is maintained by [foundata](https://foundata.com/). If you like it, you might [buy us a coffee](https://buy-me-a.coffee/ansible-docsmith/).

The Ansible DocSmith project is *not* associated with [Red Hat](https://www.redhat.com/) nor the [Ansible project](https://ansible.com/).
