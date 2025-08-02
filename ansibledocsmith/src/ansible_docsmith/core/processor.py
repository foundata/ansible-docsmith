"""Main processor for ansible-docsmith operations."""

from dataclasses import dataclass
from pathlib import Path

from .exceptions import ProcessingError, ValidationError
from .generator import DefaultsCommentGenerator, DocumentationGenerator, ReadmeUpdater
from .parser import ArgumentSpecParser


@dataclass
class ProcessingResults:
    """Results from role processing operation."""

    operations: list[tuple[Path, str, str]]  # (file, action, status)
    errors: list[str]
    warnings: list[str]
    file_diffs: list[tuple[Path, str, str]]  # (file, old_content, new_content)


class RoleProcessor:
    """Main processor for Ansible role documentation."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

        # Initialize components
        self.parser = ArgumentSpecParser()
        self.doc_generator = DocumentationGenerator()
        self.defaults_generator = DefaultsCommentGenerator()
        self.readme_updater = ReadmeUpdater()

    def validate_role(self, role_path: Path) -> dict:
        """Validate role structure and return metadata."""
        try:
            return self.parser.validate_structure(role_path)
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
        """Generate/update README.md file."""

        readme_path = role_path / "README.md"

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
                "No defaults files found for any entry points - skipping comment injection"
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
