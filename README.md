# DocSmith for Ansible: role documentation automation (helper using `argument_specs.yml` as single source of truth)

**⚠⚠⚠ WARNING: NOT FOR PRODUCTION USE YET, HIGHLY EXPERIMENTAL ⚠⚠⚠**

**This project is *not* associated with Red Hat nor the [Ansible project](https://ansible.com/).** Please [report any bugs or suggestions to us](./CONTRIBUTING.md), do NOT use the official Red Hat or Ansible support channels.

---

DocSmith helps to maintain Ansible role variable documentation by automatically generating the needed parts of a role's `README.md` and `defaults/main.yml` inline comments. It uses your [`meta/argument_specs.yml`](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#specification-format) definitions as single source of truth. No more documentation drift, no more manual updates. Just write your variable specs once and let DocSmith handle the rest.

The `argument_specs.yml` is used by [Ansible's built-in role argument validation](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#role-argument-validation). By using it in combination with DocSmith, you get effortless validation of passed role variables and nice documentation for free.

DocSmith is compatible with roles in Ansible collections as well as stand-alone ones.


**Features:**

- **Single Source of Truth**: Uses `argument_specs.yml` as the canonical source for all documentation.
- **Rich Documentation**:
  - Generates beautiful tables and descriptions for your role's `README.md` (as new file or ad an partial update between markers).
  - Adds the descriptions as comment blocks above the variable default in `defaults/main.yml`.
- **Zero Configuration**: Works out-of-the-box with sensible defaults.
- **Validation**: Ensures your argument specs are valid and complete.
- **CI/CD Ready**: Perfect for automation pipelines and pre-commit hooks.





## Installation

FIXME will be added after packaging tests are done / pypi release is prepared.



## Usage

**How DocSmith works:**

1. **Reads** your role's `meta/argument_specs.yml` file.
2. **Parses** role structure and variable definitions.
3. **Adds or updates variable documentation**
   * Generate a new readme `README.md` (if not existing) or update the variable description between special markers (preserves custom content)
   * Add or update inline comments in `defaults/main.yml`
4. **Validates** everything is correct and complete

### Quick Start

#### Generate Documentation

```bash
# Generate README.md and update defaults/main.yml comments
ansible-docsmith generate /path/to/your/ansible/role

# Preview changes without writing files
ansible-docsmith generate /path/to/role --dry-run

# Generate only README, skip commenting variables in defaults/main.yml
ansible-docsmith generate /path/to/role --no-defaults

# Verbose output for debugging
ansible-docsmith generate /path/to/role --verbose
```

#### Validate `argument_specs.yml`

```bash
# Validate argument_specs.yml structure
ansible-docsmith validate /path/to/your/ansible/role
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
