# DocSmith for Ansible: automating role documentation (using `argument_specs.yml`)

**This project is *not* associated with [Red Hat](https://www.redhat.com/) nor the [Ansible project](https://ansible.com/).** Please [report any bugs or suggestions to us](./CONTRIBUTING.md), do NOT use the official Red Hat or Ansible support channels.

---

DocSmith is a documentation generator for Ansible roles. It reads a role's [`meta/argument_specs.yml`](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#specification-format) and produces up‑to‑date variable descriptions for the `README.md` as well as inline comment blocks for `defaults/main.yml` (or other role entry-point files).

DocSmith works with roles in both [stand‑alone form](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html) and within [collections](https://docs.ansible.com/ansible/latest/collections_guide/index.html).


## Table of contents<a id="toc"></a>

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Preparations](#usage-preparations)
  - [Generate or update documentation](#usage-generate)
  - [Validate `argument_specs.yml`](#usage-validate)
- [Licensing, copyright](#licensing-copyright)
- [Author information](#author-information)


### Features<a id="features"></a>


- **Efficient and simple:** Uses the `argument_specs.yml` from [Ansible's built‑in role argument validation](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#role-argument-validation) as the single source of truth, generating human‑readable documentation in multiple places while maintaining just one file.
- **Built-in validation:** Verifies that argument specs are complete and correct.
- **Automation‑friendly:** Works seamlessly in CI/CD pipelines and pre‑commit hooks.


## Installation<a id="installation"></a>

DocSmith is available on [PyPI](https://pypi.org/project/ansible-docsmith/) and can be installed with the package manager of your choice.

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

1. If not already existing, simply create an `argument_specs.yml` for [Ansible’s role argument validation](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#role-argument-validation). The more complete your specification, the better the argument validation and documentation.
2. Add simple markers in your role's `README.md` where DocSmith shall maintain the human-readable documentation:
   ```
   <!-- BEGIN ANSIBLE DOCSMITH -->
   <!-- END ANSIBLE DOCSMITH -->
   ```
   All content between these markes will be removed and updated on each `ansible-docsmith generate` run.

That's it. The entry-point variable files below the `/defaults` directory of your role do *not* need additional preparations. The tool will automatically (re)place formatted inline comment blocks above variables defined there.


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
# entry-point files (like defaults/main.yml)
ansible-docsmith generate /path/to/role --no-defaults

# Generate / update only the comments in entry-point files (like defaults/main.yml),
# skip README.md
ansible-docsmith generate /path/to/role --no-readme

# Verbose output for debugging
ansible-docsmith generate /path/to/role --verbose
```

### Validate `argument_specs.yml`<a id="usage-validate"></a>

```bash
# Validate argument_specs.yml structure
ansible-docsmith validate /path/to/role

# Show help
ansible-docsmith --help
ansible-docsmith validate --help

# Verbose output for debugging
ansible-docsmith validate /path/to/role --verbose
```


## Licensing, copyright<a id="licensing-copyright"></a>

<!--REUSE-IgnoreStart-->
Copyright (c) 2025 foundata GmbH (https://foundata.com)

This project is licensed under the GNU General Public License v3.0 or later (SPDX-License-Identifier: `GPL-3.0-or-later`), see [`LICENSES/GPL-3.0-or-later.txt`](LICENSES/GPL-3.0-or-later.txt) for the full text.

The [`REUSE.toml`](REUSE.toml) file provides detailed licensing and copyright information in a human- and machine-readable format. This includes parts that may be subject to different licensing or usage terms, such as third-party components. The repository conforms to the [REUSE specification](https://reuse.software/spec/). You can use [`reuse spdx`](https://reuse.readthedocs.io/en/latest/readme.html#cli) to create a [SPDX software bill of materials (SBOM)](https://en.wikipedia.org/wiki/Software_Package_Data_Exchange).
<!--REUSE-IgnoreEnd-->

[![REUSE status](https://api.reuse.software/badge/github.com/foundata/ansible-docsmith)](https://api.reuse.software/info/github.com/foundata/ansible-docsmith)


## Author information<a id="author-information"></a>

This project was created and is maintained by [foundata](https://foundata.com/).
