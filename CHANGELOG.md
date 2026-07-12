# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Fixed

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
