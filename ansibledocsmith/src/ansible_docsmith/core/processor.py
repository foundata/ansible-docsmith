"""Main processor for ansible-docsmith operations."""

from dataclasses import dataclass
from pathlib import Path

from .exceptions import ProcessingError, ValidationError
from .generator import (
    DefaultsCommentGenerator,
    ReadmeUpdater,
    create_documentation_generator,
)
from .parser import ArgumentSpecParser


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
        template_readme: Path = None,
        toc_bullet_style: str | None = None,
        format_type: str = "auto",
        role_path: Path | None = None,
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

        self.defaults_generator = DefaultsCommentGenerator()

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

    def validate_role(self, role_path: Path) -> dict:
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

            # Add consistency validation
            errors, warnings, notices = self._validate_defaults_consistency(
                role_path, role_data["specs"], role_data["spec_file"]
            )
            role_data["errors"].extend(errors)
            role_data["warnings"].extend(warnings)
            role_data["notices"].extend(notices)

            # Add unknown keys validation
            warnings = self._validate_unknown_keys(role_data["spec_file"])
            role_data["warnings"].extend(warnings)

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
            role_data = self.validate_role(role_path)
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
            original_content = ""
            if readme_path.exists():
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

            action = "Updated" if readme_path.exists() else "Created"
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
                        defaults_path.write_text(updated_content, encoding="utf-8")

                results.operations.append((defaults_path, "Comments added", "✅"))

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
            with open(defaults_path) as file:
                data = self.parser.yaml.load(file)
                if data and isinstance(data, dict):
                    return set(data.keys())
        except Exception:
            pass  # Ignore parsing errors, handled elsewhere
        return set()

    def _validate_unknown_keys(self, spec_file: Path) -> list[str]:
        """Validate that only known keys are used in argument_specs."""
        warnings = []
        valid_role_keys = {
            "short_description",
            "description",
            "version_added",
            "author",
            "options",
        }
        valid_option_keys = {
            "description",
            "version_added",
            "type",
            "required",
            "default",
            "choices",
            "elements",
            "options",
        }

        # Parse original specs to preserve unknown keys
        original_specs = self._parse_original_specs(spec_file)
        if not original_specs:
            return warnings

        # Warnings might also indicate DocSmith is outdated of the official format
        # spec was extended (even though it was stable for years). In doubt, check
        # https://docs.ansible.com/ansible/latest/playbook_guide/ where all valid
        # keys are listed
        for entry_point, spec in original_specs.items():
            if not isinstance(spec, dict):
                continue

            # Check role-level keys
            unknown_role_keys = set(spec.keys()) - valid_role_keys
            if unknown_role_keys:
                warnings.append(
                    f"Entry point '{entry_point}': Unknown keys in argument_specs: "
                    f"{sorted(unknown_role_keys)}. This might be an error in your "
                    f"role."
                )

            # Check option-level keys
            for var_name, var_spec in spec.get("options", {}).items():
                if isinstance(var_spec, dict):
                    unknown_var_keys = set(var_spec.keys()) - valid_option_keys
                    if unknown_var_keys:
                        warnings.append(
                            f"Entry point '{entry_point}', variable '{var_name}': "
                            f"Unknown keys: {sorted(unknown_var_keys)}. This might "
                            f"be an error in your role."
                        )

        return warnings

    def _parse_original_specs(self, spec_file: Path) -> dict:
        """
        Parse the original specs file without normalization to check for
        default keys.
        """
        try:
            with open(spec_file) as file:
                data = self.parser.yaml.load(file)
                return data.get("argument_specs", {})
        except Exception:
            return {}

    def _validate_defaults_consistency(
        self, role_path: Path, specs: dict, spec_file: Path = None
    ) -> tuple[list[str], list[str], list[str]]:
        """Validate consistency between defaults files and argument_specs."""
        errors = []
        warnings = []
        notices = []

        defaults_files = self._find_defaults_files(role_path, specs)

        for entry_point, spec in specs.items():
            spec_vars = set(spec.get("options", {}).keys())
            defaults_vars = set()

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
            if spec_file:
                original_specs = self._parse_original_specs(spec_file)
                original_options = original_specs.get(entry_point, {}).get(
                    "options", {}
                )
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
            if defaults_vars:
                missing_in_defaults = spec_vars - defaults_vars
                if missing_in_defaults:
                    notices.append(
                        f"Entry point '{entry_point}': Variables in "
                        f"argument_specs.yml but not in defaults/{entry_point}.yml "
                        f"(may be intentional): {sorted(missing_in_defaults)}"
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
                    f"README.{readme_path.suffix[1:]} exists but is missing required markers. "
                    f"Add '{start_marker}' and '{end_marker}' to allow "
                    f"ansible-docsmith to manage documentation sections."
                )
            elif not has_start:
                errors.append(
                    f"README.{readme_path.suffix[1:]} is missing start marker: '{start_marker}'"
                )
            elif not has_end:
                errors.append(
                    f"README.{readme_path.suffix[1:]} is missing end marker: '{end_marker}'"
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
                    f"README.{readme_path.suffix[1:]} is missing TOC end marker: '{toc_end_marker}'"
                )
            elif not has_toc_start and has_toc_end:
                errors.append(
                    f"README.{readme_path.suffix[1:]} is missing TOC start marker: '{toc_start_marker}'"
                )

        except Exception as e:
            errors.append(
                f"Error reading README.{readme_path.suffix[1:]} for TOC validation: {e}"
            )

        return errors, notices
