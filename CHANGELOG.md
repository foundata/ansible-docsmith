# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Added

- Nested options ("dict attributes") are now documented in the comments of entry-point files like `defaults/main.yml` (#21, thanks to @Adam-SCP for the suggestion and issue). Each attribute is rendered as a compact, indented bullet with its description, type, required flag, default and choices, up to three nesting levels (matching the README templates). Use `--no-defaults-comments-nested` to restore the old behavior.
- Support for [Ansible markup](https://docs.ansible.com/projects/ansible/latest/dev_guide/ansible_markup.html) in `argument_specs.yml` descriptions (#22, thanks to @spike77453 for the suggestion and issue). Constructs like `C(...)`, `B(...)`, `I(...)`, `V(...)`, `E(...)`, `U(...)`, `L(...)`, `R(...)` and `HORIZONTALLINE` are converted to the target format (Markdown, reStructuredText, or YAML comments) instead of being rendered verbatim:
  - `O(variable)` references to variables of the same role become links to the matching README section.
  - `M(ns.col.module)` and `P(ns.col.plugin#type)` become links to the official documentation on docs.ansible.com.
  - Invalid markup (e.g. `M()` without a FQCN) is left verbatim; existing Markdown in descriptions is never touched. Descriptions without Ansible markup remain byte-identical.
- The `validate` command accepts `--no-readme` and `--no-argument-specs` to validate only parts of a role (#19, #20, thanks to @Adam-SCP for the issue and pull request).
- The `validate` command accepts `--strict` to treat warnings as errors (exit code 1), for use in CI/CD pipelines and pre-commit hooks.
- The `validate` command now lints [Ansible markup](https://docs.ansible.com/projects/ansible/latest/dev_guide/ansible_markup.html) in all descriptions and warns about invalid constructs (like `M()` without a FQCN or an unclosed `C(`), which the generators leave verbatim.

### Changed

- Replaced the `commonmark` library (archived upstream, CommonMark spec 0.29) with `markdown-it-py` (maintained, spec 0.30) for all internal Markdown parsing. No output changes intended.
- Removed the unused `pydantic` dependency.

### Fixed

- Failing `generate` and `validate` runs no longer log a spurious "Unexpected error: 1" line after the actual error summary.
- `generate --no-readme` no longer fails when the role's README is invalid (e.g. missing markers); README validation is skipped when the README is not being generated (#20, thanks to @Adam-SCP).
- Validation no longer emits false "Unknown keys" warnings for valid argument-spec keys such as `no_log`, `aliases`, `seealso`, `notes`, `apply_defaults` or `mutually_exclusive`. Unknown-key checking also covers nested options now.
- Table-cell truncation in the README variable overview no longer cuts through Markdown links or inline code (whole tokens are dropped instead).
- Autolinks (`<https://...>`) in variable descriptions are rendered as bare URLs in `defaults/` YAML comments instead of a redundant `[url](url)` construct.

- Pipe characters (`|`) in default values and descriptions no longer break the Markdown variable table; they are escaped only there (previously, pipes in choices were escaped globally, rendering a stray backslash outside of tables).
- Inline code containing backticks now renders correctly in Markdown (longer delimiter runs instead of backslash escapes, which are not processed inside code spans).
- Default values in reStructuredText output now use valid inline literals (double backticks); single backticks are interpreted text in RST and rendered incorrectly.

- Comment blocks in `defaults/` files are no longer injected above indented (nested) keys that share a top-level variable's name, and hand-written comments above such nested keys are no longer deleted during comment cleanup.
- `README.*` and `defaults/` files are now always written with LF line endings on all platforms.
- The processing results now report "Created" for a newly generated README (previously always "Updated") and "Skipped (no variables found)" instead of "Comments added" for defaults files without variables.


## [2.0.2] - 2026-05-31

This release contains no functional changes from 2.0.1. It only improves the README rendering for PyPI and the documentation.

### Fixed

- SVG logo contained text instead of paths (#14, 04d0347)



## [2.0.1] - 2026-05-31

### Fixed

- Keep slash-separated code spans intact (df742bd)
- Keep punctuation attached to inline code (#16, 267f89e)
- Render empty string defaults explicitly (#18, b22e3d5)
- Wrap compound defaults in YAML comments (#17, e486a60)
- Preserve Markdown links in defaults comments (#16, 917e575)
- Preserve backslashes when updating README markers (#15, d47193b)



## [2.0.0] - 2025-09-27

This is a very big update, providing new features and improvements. Please note the **small but breaking change in the marker syntax.**

### Added

- **Support for reStructuredText (reST, `.rst`).**
  - DocSmith is now able to detect and use a `README.rst`.
  - The `generate` action was extended by a `--format` option you can use if automatic detection fails.
- **Support for generating Table of Contents (ToC).**
  * Markdown:
    ```markdown
    ## Table of contents

    - My 1st non DocSmith entry<!-- ANSIBLE DOCSMITH TOC START --><!-- ANSIBLE DOCSMITH TOC END -->
    - My 2nd non DocSmith entry
    - [...]
    ```
  * reST: Using the [contents directive](https://docutils.sourceforge.io/docs/ref/rst/directives.html#document-parts) is highly recommended:
    ```reStructuredText
    .. contents:: Table of Contents
     :depth: 6
    ```
    If this directive is not available in your environment, you can use
    ```reStructuredText
    .. ANSIBLE DOCSMITH TOC START

    .. ANSIBLE DOCSMITH TOC END
    ```
    as fallback.
- **Additional validations for `arguments_spec`.** The `validate` command now warns about additional issues (like mutally exclusive options).
- **Far better Support for nested options**.


### Changed

- **⚠ Breaking: `Rename "BEGIN|END ANSIBLE DOCSMITH"` to `"ANSIBLE DOCSMITH MAIN START|END"`** (4864fea, 2cb6f58):<br><br>As there may be more and more additional content sections in the future, it would be good to make a small change now - while the tool is still new and has few users - to avoid bigger breaking changes later. This is basically a switch to a format like:
  ```markdown
  <!-- ANSIBLE DOCSMITH [Type of content] START -->
  <!-- ANSIBLE DOCSMITH [Type of content] END -->
  ```
  What to do?<br><br>Replace
  ```markdown
  <!-- BEGIN ANSIBLE DOCSMITH -->
  ...
  <!-- END ANSIBLE DOCSMITH -->
  ```
  with
  ```markdown
   <!-- ANSIBLE DOCSMITH MAIN START -->
   ...
   <!-- ANSIBLE DOCSMITH MAIN END -->
  ```
  in your documents. That's it. See #8 for more reasoning.
- **Formatting of YAML comments was improved.**


## [1.0.0] - 2025-08-04

### Added

- All functionality and files. I dedicate this tool and its release to the memory of my beloved father, who recently passed away. May he rest in peace.


[unreleased]: https://github.com/foundata/ansible-docsmith/compare/v2.0.2...HEAD
[2.0.2]: https://github.com/foundata/ansible-docsmith/releases/tag/v2.0.1
[2.0.1]: https://github.com/foundata/ansible-docsmith/releases/tag/v2.0.1
[2.0.0]: https://github.com/foundata/ansible-docsmith/releases/tag/v2.0.0
[1.0.0]: https://github.com/foundata/ansible-docsmith/releases/tag/v1.0.0
