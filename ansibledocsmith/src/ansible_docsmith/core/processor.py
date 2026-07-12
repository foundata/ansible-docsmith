"""Main processor for ansible-docsmith operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..constants import SPEC_VALID_ENTRYPOINT_KEYS, SPEC_VALID_OPTION_KEYS
from .defaults_comments import DefaultsCommentGenerator
from .doc_generators import create_documentation_generator
from .exceptions import ProcessingError, ValidationError
from .markup import lint_ansible_markup
from .parser import ArgumentSpecParser
from .readme_updater import ReadmeUpdater


def detect_format_from_role(role_path: Path) -> str:
    """Auto-detect format based on existing README files in role directory.

    Args:
        role_path: Path to the role directory

    Returns:
        'rst' if README.rst exists, 'markdown' if README.md exists or neither exists
    """
    rst_readme = role_path / "README.rst"
    md_readme = role_path / "README.md"

    # If both exist, prefer RST (since it's more specific)
    if rst_readme.exists():
        return "rst"
    elif md_readme.exists():
        return "markdown"
    else:
        # Default to markdown if neither exists
        return "markdown"


@dataclass
class ProcessingResults:
    """Results from role processing operation."""

    operations: list[tuple[Path, str, str]]  # (file, action, status)
    errors: list[str]
    warnings: list[str]
    file_diffs: list[tuple[Path, str, str]]  # (file, old_content, new_content)


class RoleProcessor:
    """Main processor for Ansible role documentation."""

    def __init__(
        self,
        dry_run: bool = False,
        template_readme: Path | None = None,
        toc_bullet_style: str | None = None,
        format_type: str = "auto",
        role_path: Path | None = None,
        defaults_comments_nested: bool = True,
    ):
        self.dry_run = dry_run
        self.template_readme = template_readme
        self.toc_bullet_style = toc_bullet_style
        self.role_path = role_path

        # Resolve format type
        if format_type.lower() == "auto" and role_path:
            self.format_type = detect_format_from_role(role_path)
        elif format_type.lower() == "auto":
            # Defer format detection until role_path is known
            self.format_type = "auto"
        else:
            self.format_type = format_type.lower()

        # Initialize components
        self.parser = ArgumentSpecParser()

        # For auto format, defer generator initialization until format is resolved
        if self.format_type == "auto":
            self.doc_generator = None
            self.readme_updater = None
        else:
            self.doc_generator = create_documentation_generator(
                format_type=self.format_type, template_file=template_readme
            )
            self.readme_updater = ReadmeUpdater(
                format_type=self.format_type, toc_bullet_style=toc_bullet_style
            )

        self.defaults_generator = DefaultsCommentGenerator(
            nested_options=defaults_comments_nested
        )

    def _resolve_auto_format(self, role_path: Path) -> None:
        """Resolve auto format detection and initialize generators if needed."""
        if self.format_type == "auto":
            self.format_type = detect_format_from_role(role_path)
            # Initialize generators now that format is resolved
            self.doc_generator = create_documentation_generator(
                format_type=self.format_type, template_file=self.template_readme
            )
            self.readme_updater = ReadmeUpdater(
                format_type=self.format_type, toc_bullet_style=self.toc_bullet_style
            )

    def validate_role(
        self,
        role_path: Path,
        validate_readme: bool = True,
        validate_argument_specs: bool = True,
    ) -> dict:
        """
        Validate role structure and return metadata with further check results
        (like consistency, unknown keys).
        """
        # Resolve auto format if needed
        self._resolve_auto_format(role_path)

        try:
            # Basic structure validation
            role_data = self.parser.validate_structure(role_path)
            role_data.setdefault("errors", [])
            role_data.setdefault("warnings", [])
            role_data.setdefault("notices", [])

            if validate_argument_specs:
                # Parse the raw (unnormalized) specs once; several validators
                # need this view to distinguish explicitly set keys from
                # normalization artifacts
                original_specs = self._parse_original_specs(role_data["spec_file"])

                # Add consistency validation
                errors, warnings, notices = self._validate_defaults_consistency(
                    role_path, role_data["specs"], original_specs
                )
                role_data["errors"].extend(errors)
                role_data["warnings"].extend(warnings)
                role_data["notices"].extend(notices)

                # Add unknown keys validation
                warnings = self._validate_unknown_keys(original_specs)
                role_data["warnings"].extend(warnings)

                # Add mutually exclusive keys validation
                exclusive_errors = self._validate_mutually_exclusive_keys(
                    original_specs
                )
                role_data["errors"].extend(exclusive_errors)

                # Add Ansible markup linting
                markup_warnings = self._validate_markup(original_specs)
                role_data["warnings"].extend(markup_warnings)

            if validate_readme:
                # Add README marker validation
                readme_errors = self._validate_readme_markers(role_path)
                role_data["errors"].extend(readme_errors)

                # Add TOC marker validation
                toc_errors, toc_notices = self._validate_readme_toc_markers(role_path)
                role_data["errors"].extend(toc_errors)
                role_data["notices"].extend(toc_notices)

            # Fail validation if errors found
            if role_data.get("errors"):
                error_msg = "Validation failed:\n" + "\n".join(role_data["errors"])
                raise ValidationError(error_msg)

            return role_data
        except ValidationError:
            raise
        except Exception as e:
            raise ProcessingError(f"Validation failed: {e}")

    def process_role(
        self,
        role_path: Path,
        generate_readme: bool = True,
        update_defaults: bool = True,
    ) -> ProcessingResults:
        """Process the entire role for documentation generation."""

        # Resolve auto format if needed
        self._resolve_auto_format(role_path)

        results = ProcessingResults(
            operations=[], errors=[], warnings=[], file_diffs=[]
        )

        try:
            # Validate and parse role
            role_data = self.validate_role(role_path, validate_readme=generate_readme)
            specs = role_data["specs"]
            role_name = role_data["role_name"]

            # Generate README documentation
            if generate_readme:
                self._process_readme(role_path, specs, role_name, results)

            # Update defaults with comments
            if update_defaults:
                self._process_defaults(role_path, specs, results)

        except (ValidationError, ProcessingError) as e:
            results.errors.append(str(e))
        except Exception as e:
            results.errors.append(f"Unexpected error: {e}")

        return results

    def _process_readme(
        self, role_path: Path, specs: dict, role_name: str, results: ProcessingResults
    ):
        """Generate/update README file."""

        # Determine README file extension based on format
        readme_ext = "rst" if self.format_type == "rst" else "md"
        readme_path = role_path / f"README.{readme_ext}"

        try:
            # Generate documentation content
            doc_content = self.doc_generator.generate_role_documentation(
                specs, role_name, role_path
            )

            # Read original content for diff comparison
            existed_before = readme_path.exists()
            original_content = ""
            if existed_before:
                original_content = readme_path.read_text(encoding="utf-8")

            # Get the new content that would be written
            if self.dry_run:
                # For dry-run, we need to simulate what update_readme would produce
                new_content = self.readme_updater._get_updated_content(
                    readme_path, doc_content
                )
                results.file_diffs.append((readme_path, original_content, new_content))
            else:
                # Update README
                self.readme_updater.update_readme(readme_path, doc_content)

            action = "Updated" if existed_before else "Created"
            results.operations.append((readme_path, action, "✅"))

        except Exception as e:
            results.errors.append(f"README generation failed: {e}")

    def _process_defaults(
        self, role_path: Path, specs: dict, results: ProcessingResults
    ):
        """Add inline comments to defaults files for all entry points."""

        # Find defaults files for all entry points
        defaults_files = self._find_defaults_files(role_path, specs)

        if not defaults_files:
            results.warnings.append(
                "No defaults files found for any entry points - "
                "skipping comment injection"
            )
            return

        for entry_point, defaults_path in defaults_files.items():
            try:
                # Create a spec dict containing only this entry point
                entry_point_specs = {entry_point: specs[entry_point]}
                updated_content = self.defaults_generator.add_comments(
                    defaults_path, entry_point_specs
                )

                if updated_content:
                    # Read original content for diff comparison
                    original_content = ""
                    if defaults_path.exists():
                        original_content = defaults_path.read_text(encoding="utf-8")

                    # Store diff information for dry-run display
                    if self.dry_run:
                        results.file_diffs.append(
                            (defaults_path, original_content, updated_content)
                        )
                    else:
                        # Write updated content directly (no backup)
                        defaults_path.write_text(
                            updated_content, encoding="utf-8", newline="\n"
                        )

                    results.operations.append((defaults_path, "Comments added", "✅"))
                else:
                    results.operations.append(
                        (defaults_path, "Skipped (no variables found)", "⚠️")
                    )

            except Exception as e:
                results.errors.append(f"Defaults update failed for {entry_point}: {e}")

    def _find_defaults_files(self, role_path: Path, specs: dict) -> dict[str, Path]:
        """Find defaults files for all entry points."""
        defaults_files = {}

        for entry_point in specs.keys():
            for ext in ["yml", "yaml"]:
                defaults_path = role_path / "defaults" / f"{entry_point}.{ext}"
                if defaults_path.exists():
                    defaults_files[entry_point] = defaults_path
                    break

        return defaults_files

    def _extract_variables_from_defaults(self, defaults_path: Path) -> set[str]:
        """Extract variable names from a defaults YAML file."""
        try:
            with open(defaults_path, encoding="utf-8") as file:
                data = self.parser.yaml.load(file)
                if data and isinstance(data, dict):
                    return set(data.keys())
        except Exception:
            pass  # Ignore parsing errors, handled elsewhere
        return set()

    def _extract_defaults_values_from_file(self, defaults_path: Path) -> dict[str, Any]:
        """Extract variable names and their values from a defaults YAML file."""
        try:
            with open(defaults_path, encoding="utf-8") as file:
                data = self.parser.yaml.load(file)
                if data and isinstance(data, dict):
                    return data
        except Exception:
            pass  # Ignore parsing errors, handled elsewhere
        return {}

    def _validate_unknown_keys(self, original_specs: dict) -> list[str]:
        """Validate that only known keys are used in argument_specs.

        Args:
            original_specs: Raw (unnormalized) argument specs as returned
                by _parse_original_specs(), which preserve unknown keys.
        """
        warnings = []
        if not original_specs:
            return warnings

        # Warnings might also indicate DocSmith is outdated if the official
        # format spec was extended (even though it was stable for years). In
        # doubt, check the sources named at the constant definitions.
        for entry_point, spec in original_specs.items():
            if not isinstance(spec, dict):
                continue

            # Check role-level keys
            unknown_role_keys = set(spec.keys()) - SPEC_VALID_ENTRYPOINT_KEYS
            if unknown_role_keys:
                warnings.append(
                    f"Entry point '{entry_point}': Unknown keys in argument_specs: "
                    f"{sorted(unknown_role_keys)}. This might be an error in your "
                    f"role."
                )

            # Check option-level keys (including nested options)
            options = spec.get("options", {})
            if isinstance(options, dict):
                self._check_unknown_option_keys(entry_point, options, warnings, path="")

        return warnings

    def _validate_markup(self, original_specs: dict) -> list[str]:
        """Lint Ansible markup in all descriptions of the argument specs.

        Invalid markup (like ``M()`` without a FQCN) is left verbatim by
        the generators; these warnings point role authors at the mistake.

        Args:
            original_specs: Raw (unnormalized) argument specs as returned
                by _parse_original_specs().
        """
        warnings = []

        def _lint(texts, location: str) -> None:
            if isinstance(texts, str):
                texts = [texts]
            if not isinstance(texts, list):
                return
            for item in texts:
                for message in lint_ansible_markup(str(item)):
                    warnings.append(f"{location}: Invalid Ansible markup: {message}")

        def _walk_options(options: dict, entry_point: str, path: str) -> None:
            for var_name, var_spec in options.items():
                if not isinstance(var_spec, dict):
                    continue
                display_name = f"{path}{var_name}"
                _lint(
                    var_spec.get("description"),
                    f"Entry point '{entry_point}', variable '{display_name}'",
                )
                nested = var_spec.get("options")
                if isinstance(nested, dict):
                    _walk_options(nested, entry_point, f"{display_name}.")

        for entry_point, spec in original_specs.items():
            if not isinstance(spec, dict):
                continue
            for key in ("short_description", "description"):
                _lint(spec.get(key), f"Entry point '{entry_point}' ({key})")
            options = spec.get("options", {})
            if isinstance(options, dict):
                _walk_options(options, entry_point, path="")

        return warnings

    def _check_unknown_option_keys(
        self, entry_point: str, options: dict, warnings: list[str], path: str
    ) -> None:
        """Recursively warn about unknown keys in (nested) option specs."""
        for var_name, var_spec in options.items():
            if not isinstance(var_spec, dict):
                continue

            display_name = f"{path}{var_name}"
            unknown_var_keys = set(var_spec.keys()) - SPEC_VALID_OPTION_KEYS
            if unknown_var_keys:
                warnings.append(
                    f"Entry point '{entry_point}', variable '{display_name}': "
                    f"Unknown keys: {sorted(unknown_var_keys)}. This might "
                    f"be an error in your role."
                )

            nested = var_spec.get("options")
            if isinstance(nested, dict):
                self._check_unknown_option_keys(
                    entry_point, nested, warnings, path=f"{display_name}."
                )

    def _parse_original_specs(self, spec_file: Path) -> dict:
        """
        Parse the original specs file without normalization to check for
        default keys.
        """
        try:
            with open(spec_file, encoding="utf-8") as file:
                data = self.parser.yaml.load(file)
                return data.get("argument_specs", {})
        except Exception:
            return {}

    def _validate_mutually_exclusive_keys(self, original_specs: dict) -> list[str]:
        """Validate that default and required: true are not used together.

        Args:
            original_specs: Raw (unnormalized) argument specs as returned
                by _parse_original_specs().
        """
        errors = []
        if not original_specs:
            return errors

        for entry_point, spec in original_specs.items():
            if not isinstance(spec, dict):
                continue

            options = spec.get("options", {})
            if not isinstance(options, dict):
                continue

            for var_name, var_spec in options.items():
                if not isinstance(var_spec, dict):
                    continue

                # Check for the conflict: both default and required: true
                has_default = "default" in var_spec
                is_required = var_spec.get("required") is True

                if has_default and is_required:
                    errors.append(
                        f"Entry point '{entry_point}': Variable '{var_name}' has "
                        f"both 'default' and 'required: true' which are mutually "
                        f"exclusive. Remove either the default value or set "
                        f"required to false."
                    )

        return errors

    def _validate_defaults_consistency(
        self,
        role_path: Path,
        specs: dict,
        original_specs: dict | None = None,
    ) -> tuple[list[str], list[str], list[str]]:
        """Validate consistency between defaults files and argument_specs.

        Args:
            role_path: Path to the role directory
            specs: Normalized argument specs
            original_specs: Raw (unnormalized) argument specs. Used to
                distinguish explicitly set keys (like "default") from
                normalization artifacts; the normalized specs are used as
                fallback when not provided.
        """
        errors = []
        warnings = []
        notices = []

        defaults_files = self._find_defaults_files(role_path, specs)

        for entry_point, spec in specs.items():
            spec_vars = set(spec.get("options", {}).keys())
            defaults_vars = set()

            # Raw option specs preserve which keys were explicitly set
            original_options = None
            if original_specs:
                entry = original_specs.get(entry_point, {})
                if isinstance(entry, dict):
                    original_options = entry.get("options", {}) or {}

            if entry_point in defaults_files:
                # Parse defaults file to get variables
                defaults_vars = self._extract_variables_from_defaults(
                    defaults_files[entry_point]
                )

                # ERROR: Variables in defaults but not in specs
                undefined_vars = defaults_vars - spec_vars
                if undefined_vars:
                    errors.append(
                        f"Entry point '{entry_point}': Variables present in defaults/"
                        f"{entry_point}.yml but missing from argument_specs.yml: "
                        f"{sorted(undefined_vars)}"
                    )

            # ERROR: Variables with defaults in specs but missing from defaults file
            # Check which variables have explicit defaults (not
            # parser-added None)
            spec_with_defaults = set()
            if original_options is not None:
                for name, var_spec in original_options.items():
                    if isinstance(var_spec, dict) and "default" in var_spec:
                        spec_with_defaults.add(name)
            else:
                # Fallback: treat variables with non-None defaults as having explicit
                # defaults
                for name, var_spec in spec.get("options", {}).items():
                    if (
                        isinstance(var_spec, dict)
                        and "default" in var_spec
                        and var_spec["default"] is not None
                    ):
                        spec_with_defaults.add(name)
            missing_defaults = spec_with_defaults - defaults_vars
            if missing_defaults:
                defaults_file = f"defaults/{entry_point}.yml"
                errors.append(
                    f"Entry point '{entry_point}': Variables have defaults in "
                    f"argument_specs.yml but are missing from {defaults_file}: "
                    f"{sorted(missing_defaults)}"
                )

            # NOTICE: Variables in specs but not in defaults (potential oversight)
            # Skip variables that are required (no need for defaults)
            if defaults_vars:
                missing_in_defaults = spec_vars - defaults_vars
                if missing_in_defaults:
                    # Filter out required variables - they don't need defaults
                    non_required_missing = set()
                    source_options = (
                        original_options
                        if original_options is not None
                        else spec.get("options", {})
                    )
                    for var_name in missing_in_defaults:
                        var_spec = source_options.get(var_name, {})
                        if not (
                            isinstance(var_spec, dict)
                            and var_spec.get("required") is True
                        ):
                            non_required_missing.add(var_name)

                    if non_required_missing:
                        notices.append(
                            f"Entry point '{entry_point}': Variables in "
                            f"argument_specs.yml but not in defaults/{entry_point}.yml "
                            f"(may be intentional): {sorted(non_required_missing)}"
                        )

                # WARNING: Default value mismatches between specs and defaults files
                if entry_point in defaults_files:
                    defaults_values = self._extract_defaults_values_from_file(
                        defaults_files[entry_point]
                    )

                    # Get spec defaults from original file (not normalized)
                    spec_defaults = {}
                    if original_options is not None:
                        for name, var_spec in original_options.items():
                            if isinstance(var_spec, dict) and "default" in var_spec:
                                spec_defaults[name] = var_spec["default"]
                    else:
                        # Fallback: use processed specs
                        for name, var_spec in spec.get("options", {}).items():
                            if (
                                isinstance(var_spec, dict)
                                and "default" in var_spec
                                and var_spec["default"] is not None
                            ):
                                spec_defaults[name] = var_spec["default"]

                    # Compare values for variables that exist in both places
                    for var_name in spec_defaults:
                        if var_name in defaults_values:
                            spec_value = spec_defaults[var_name]
                            defaults_value = defaults_values[var_name]
                            if spec_value != defaults_value:
                                warnings.append(
                                    f"Entry point '{entry_point}': Default value "
                                    f"mismatch for variable '{var_name}': "
                                    f"argument_specs.yml defines {spec_value!r} but "
                                    f"defaults/{entry_point}.yml defines "
                                    f"{defaults_value!r}"
                                )

        return errors, warnings, notices

    def _validate_readme_markers(self, role_path: Path) -> list[str]:
        """Validate that existing README file contains required markers."""
        errors = []

        # Resolve auto format if needed
        self._resolve_auto_format(role_path)

        # Check for README files in order of preference based on format
        readme_ext = "rst" if self.format_type == "rst" else "md"
        readme_path = role_path / f"README.{readme_ext}"

        # If format-specific file doesn't exist, check the other format
        if not readme_path.exists():
            alt_ext = "md" if readme_ext == "rst" else "rst"
            alt_readme_path = role_path / f"README.{alt_ext}"
            if alt_readme_path.exists():
                readme_path = alt_readme_path

        if not readme_path.exists():
            # No README exists - that's fine, generate will create one
            return errors

        try:
            content = readme_path.read_text(encoding="utf-8")
            start_marker = self.readme_updater.start_marker
            end_marker = self.readme_updater.end_marker

            has_start = start_marker in content
            has_end = end_marker in content

            if not has_start and not has_end:
                errors.append(
                    f"README.{readme_path.suffix[1:]} exists but is missing "
                    f"required markers. Add '{start_marker}' and '{end_marker}' "
                    f"to allow ansible-docsmith to manage documentation sections."
                )
            elif not has_start:
                errors.append(
                    f"README.{readme_path.suffix[1:]} is missing "
                    f"start marker: '{start_marker}'"
                )
            elif not has_end:
                errors.append(
                    f"README.{readme_path.suffix[1:]} is missing "
                    f"end marker: '{end_marker}'"
                )

        except Exception as e:
            errors.append(f"Error reading README.{readme_path.suffix[1:]}: {e}")

        return errors

    def _validate_readme_toc_markers(
        self, role_path: Path
    ) -> tuple[list[str], list[str]]:
        """Validate TOC markers in README file.

        Returns:
            Tuple of (errors, notices)
        """
        errors = []
        notices = []

        # Resolve auto format if needed
        self._resolve_auto_format(role_path)

        # Use same logic as _validate_readme_markers for file detection
        readme_ext = "rst" if self.format_type == "rst" else "md"
        readme_path = role_path / f"README.{readme_ext}"

        if not readme_path.exists():
            alt_ext = "md" if readme_ext == "rst" else "rst"
            alt_readme_path = role_path / f"README.{alt_ext}"
            if alt_readme_path.exists():
                readme_path = alt_readme_path

        if not readme_path.exists():
            return errors, notices

        try:
            content = readme_path.read_text(encoding="utf-8")
            toc_start_marker = self.readme_updater.toc_start_marker
            toc_end_marker = self.readme_updater.toc_end_marker

            has_toc_start = toc_start_marker in content
            has_toc_end = toc_end_marker in content

            if not has_toc_start and not has_toc_end:
                notices.append(
                    f"README.{readme_path.suffix[1:]} does not contain TOC markers. "
                    f"Add '{toc_start_marker}' and '{toc_end_marker}' to enable "
                    f"automatic Table of Contents generation."
                )
            elif has_toc_start and not has_toc_end:
                errors.append(
                    f"README.{readme_path.suffix[1:]} is missing "
                    f"TOC end marker: '{toc_end_marker}'"
                )
            elif not has_toc_start and has_toc_end:
                errors.append(
                    f"README.{readme_path.suffix[1:]} is missing "
                    f"TOC start marker: '{toc_start_marker}'"
                )

            # TOC-FULL markers (optional, so no notice when absent)
            tocfull_start = self.readme_updater.tocfull_start_marker
            tocfull_end = self.readme_updater.tocfull_end_marker
            has_tocfull_start = tocfull_start in content
            has_tocfull_end = tocfull_end in content

            if has_tocfull_start and not has_tocfull_end:
                errors.append(
                    f"README.{readme_path.suffix[1:]} is missing "
                    f"TOC-FULL end marker: '{tocfull_end}'"
                )
            elif not has_tocfull_start and has_tocfull_end:
                errors.append(
                    f"README.{readme_path.suffix[1:]} is missing "
                    f"TOC-FULL start marker: '{tocfull_start}'"
                )
            elif has_tocfull_start and readme_path.suffix == ".md":
                notices.extend(self._check_tocfull_anchor_notices(content, readme_path))

        except Exception as e:
            errors.append(
                f"Error reading README.{readme_path.suffix[1:]} for TOC validation: {e}"
            )

        return errors, notices

    @staticmethod
    def _check_tocfull_anchor_notices(content: str, readme_path: Path) -> list[str]:
        """Notice headings without explicit anchors in TOC-FULL documents.

        TOC-FULL lists all headings. For headings without an explicit
        ``<a id="..."></a>`` anchor, the link target has to be derived
        from the heading text, which approximates - but cannot guarantee -
        the anchor generated by the rendering platform.
        """
        from .toc import MarkdownTocGenerator

        notices = []
        for heading in MarkdownTocGenerator()._extract_headings(content):
            if f'<a id="{heading["anchor"]}"' not in content:
                notices.append(
                    f"README.{readme_path.suffix[1:]}: TOC-FULL includes the "
                    f"heading '{heading['text']}' which has no explicit "
                    f"anchor. Add '<a id=\"{heading['anchor']}\"></a>' to it "
                    f"to guarantee a working link."
                )
        return notices
