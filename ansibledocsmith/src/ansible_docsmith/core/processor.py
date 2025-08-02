"""Main processor for ansible-docsmith operations."""

from pathlib import Path
from typing import NamedTuple
from dataclasses import dataclass

from .parser import ArgumentSpecParser
from .generator import DocumentationGenerator, DefaultsCommentGenerator, ReadmeUpdater
from .exceptions import ValidationError, ProcessingError


@dataclass
class ProcessingResults:
    """Results from role processing operation."""
    operations: list[tuple[Path, str, str]]  # (file, action, status)
    errors: list[str]
    warnings: list[str]


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
        update_defaults: bool = True
    ) -> ProcessingResults:
        """Process the entire role for documentation generation."""

        results = ProcessingResults(operations=[], errors=[], warnings=[])

        try:
            # Validate and parse role
            role_data = self.validate_role(role_path)
            specs = role_data['specs']
            role_name = role_data['role_name']

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
        self,
        role_path: Path,
        specs: dict,
        role_name: str,
        results: ProcessingResults
    ):
        """Generate/update README.md file."""

        readme_path = role_path / "README.md"

        try:
            # Generate documentation content
            doc_content = self.doc_generator.generate_role_documentation(
                specs, role_name, role_path
            )

            if not self.dry_run:
                # Update README
                self.readme_updater.update_readme(readme_path, doc_content)

            action = "Updated" if readme_path.exists() else "Created"
            results.operations.append((readme_path, action, "✅"))

        except Exception as e:
            results.errors.append(f"README generation failed: {e}")

    def _process_defaults(
        self,
        role_path: Path,
        specs: dict,
        results: ProcessingResults
    ):
        """Add inline comments to defaults/main.yml."""

        defaults_path = self._find_defaults_file(role_path)

        if not defaults_path:
            results.warnings.append("No defaults/main.yml found - skipping comment injection")
            return

        try:
            updated_content = self.defaults_generator.add_comments(
                defaults_path, specs
            )

            if updated_content and not self.dry_run:
                # Create backup
                backup_path = defaults_path.with_suffix(f"{defaults_path.suffix}.bak")
                if not backup_path.exists():  # Don't overwrite existing backups
                    defaults_path.rename(backup_path)

                    # Write updated content
                    defaults_path.write_text(updated_content, encoding='utf-8')
                else:
                    # Backup exists, just write new content
                    defaults_path.write_text(updated_content, encoding='utf-8')

            results.operations.append((defaults_path, "Comments added", "✅"))

        except Exception as e:
            results.errors.append(f"Defaults update failed: {e}")

    def _find_defaults_file(self, role_path: Path) -> Path | None:
        """Find defaults file (supports both .yml and .yaml)."""
        for ext in ['yml', 'yaml']:
            defaults_path = role_path / 'defaults' / f'main.{ext}'
            if defaults_path.exists():
                return defaults_path
        return None


