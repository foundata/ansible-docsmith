"""Processing of Ansible collections (multiple roles + collection README).

A collection is detected by the presence of roles with argument specs
below ``roles/``. All discovered roles are processed like single roles;
additionally, role-named marker sections in the collection's README
(``ANSIBLE DOCSMITH <TYPE> <role> START/END``) are updated:

- ``TOC <role>``: table of contents of the role's DocSmith-managed
  variable documentation, linking into the role's README.
- ``TOC-FULL <role>``: table of contents of all headings of the role's
  README, linking into the role's README.

Role-named sections are strictly opt-in: roles without markers in the
collection README are simply not referenced there.
"""

from pathlib import Path

from .processor import ProcessingResults, RoleProcessor, detect_format_from_role
from .readme_updater import MARKER_PATTERN, ReadmeUpdater, marker_comment
from .toc import create_toc_generator


def find_collection_roles(collection_path: Path) -> dict[str, Path]:
    """Discover roles with argument specs, sorted by role name."""
    roles: dict[str, Path] = {}
    roles_dir = collection_path / "roles"
    if not roles_dir.is_dir():
        return roles

    for role_dir in sorted(roles_dir.iterdir()):
        if not role_dir.is_dir():
            continue
        for ext in ("yml", "yaml"):
            if (role_dir / "meta" / f"argument_specs.{ext}").exists():
                roles[role_dir.name] = role_dir
                break

    return roles


def detect_project_type(path: Path) -> str | None:
    """Return "role", "collection" or None for the given path."""
    for ext in ("yml", "yaml"):
        if (path / "meta" / f"argument_specs.{ext}").exists():
            return "role"
    if find_collection_roles(path):
        return "collection"
    return None


class CollectionProcessor:
    """Process all roles of a collection plus the collection README."""

    def __init__(
        self,
        collection_path: Path,
        dry_run: bool = False,
        template_readme: Path | None = None,
        toc_bullet_style: str | None = None,
        format_type: str = "auto",
        defaults_comments_nested: bool = True,
    ):
        self.collection_path = collection_path
        self.dry_run = dry_run
        self.template_readme = template_readme
        self.toc_bullet_style = toc_bullet_style
        self.defaults_comments_nested = defaults_comments_nested
        self.roles = find_collection_roles(collection_path)

        # Format of the collection README (role READMEs are detected
        # per role, independently)
        if format_type.lower() == "auto":
            self.format_type = detect_format_from_role(collection_path)
        else:
            self.format_type = format_type.lower()

    def _role_processor(self, role_path: Path, dry_run: bool) -> RoleProcessor:
        return RoleProcessor(
            dry_run=dry_run,
            template_readme=self.template_readme,
            toc_bullet_style=self.toc_bullet_style,
            format_type="auto",
            role_path=role_path,
            defaults_comments_nested=self.defaults_comments_nested,
        )

    def process_collection(
        self,
        generate_readme: bool = True,
        update_defaults: bool = True,
    ) -> ProcessingResults:
        """Process all roles, then the collection README."""
        combined = ProcessingResults(
            operations=[], errors=[], warnings=[], file_diffs=[]
        )
        # role name -> (role README path, its content after this run)
        role_readmes: dict[str, tuple[Path, str]] = {}

        for role_name, role_path in self.roles.items():
            processor = self._role_processor(role_path, self.dry_run)
            results = processor.process_role(
                role_path,
                generate_readme=generate_readme,
                update_defaults=update_defaults,
            )

            combined.operations.extend(results.operations)
            combined.file_diffs.extend(results.file_diffs)
            combined.errors.extend(
                f"Role '{role_name}': {error}" for error in results.errors
            )
            combined.warnings.extend(
                f"Role '{role_name}': {warning}" for warning in results.warnings
            )

            if results.readme_content is not None:
                readme_ext = "rst" if processor.format_type == "rst" else "md"
                role_readmes[role_name] = (
                    role_path / f"README.{readme_ext}",
                    results.readme_content,
                )

        if generate_readme:
            self._process_collection_readme(role_readmes, combined)

        return combined

    def _find_collection_readme(self) -> Path | None:
        readme_ext = "rst" if self.format_type == "rst" else "md"
        readme_path = self.collection_path / f"README.{readme_ext}"
        return readme_path if readme_path.exists() else None

    def _process_collection_readme(
        self,
        role_readmes: dict[str, tuple[Path, str]],
        results: ProcessingResults,
    ) -> None:
        """Update role-named marker sections in the collection README."""
        readme_path = self._find_collection_readme()
        if readme_path is None:
            return

        try:
            original_content = readme_path.read_text(encoding="utf-8")
            content = original_content

            updater = ReadmeUpdater(
                format_type=self.format_type, toc_bullet_style=self.toc_bullet_style
            )
            collection_toc = updater.toc_generator
            bullet_style = self.toc_bullet_style or collection_toc._detect_bullet_style(
                original_content
            )

            for role_name, (role_readme_path, role_content) in role_readmes.items():
                # Headings are extracted with the ROLE README's format,
                # the list is rendered in the COLLECTION README's format
                role_format = "rst" if role_readme_path.suffix == ".rst" else "markdown"
                role_toc = create_toc_generator(format_type=role_format)
                link_prefix = role_readme_path.relative_to(
                    self.collection_path
                ).as_posix()

                # TOC <role>: variables documentation only
                role_updater = ReadmeUpdater(format_type=role_format)
                main_content = role_updater._extract_main_content(role_content)
                toc_lines = collection_toc._generate_toc_lines(
                    role_toc._extract_headings(main_content),
                    bullet_style,
                    link_prefix,
                )
                updated = updater.replace_named_section(
                    content, toc_lines, "TOC", role_name
                )
                if updated is not None:
                    content = updated

                # TOC-FULL <role>: all headings of the role README
                tocfull_lines = collection_toc._generate_toc_lines(
                    role_toc._extract_headings(role_content),
                    bullet_style,
                    link_prefix,
                )
                updated = updater.replace_named_section(
                    content, tocfull_lines, "TOC-FULL", role_name
                )
                if updated is not None:
                    content = updated

            # Warn about role-named markers referencing unknown roles
            referenced_roles = {
                match.group("role")
                for match in MARKER_PATTERN.finditer(content)
                if match.group("role")
            }
            for unknown in sorted(referenced_roles - set(self.roles)):
                results.warnings.append(
                    f"Collection README references unknown role '{unknown}' "
                    f"in DocSmith markers."
                )

            if self.dry_run:
                results.file_diffs.append((readme_path, original_content, content))
            elif content != original_content:
                readme_path.write_text(content, encoding="utf-8", newline="\n")

            action = "Updated" if content != original_content else "Unchanged"
            results.operations.append((readme_path, action, "✅"))

        except Exception as e:
            results.errors.append(f"Collection README update failed: {e}")

    def validate_collection(
        self,
        validate_readme: bool = True,
        validate_argument_specs: bool = True,
    ) -> dict:
        """Validate all roles and the collection README's markers.

        Returns:
            Dict with "roles" (role name -> role_data of successfully
            validated roles) and collection-level "errors", "warnings"
            and "notices". Role validation failures are collected into
            "errors" instead of raising.
        """
        summary: dict = {"roles": {}, "errors": [], "warnings": [], "notices": []}

        from .exceptions import ProcessingError, ValidationError

        for role_name, role_path in self.roles.items():
            processor = self._role_processor(role_path, dry_run=True)
            try:
                summary["roles"][role_name] = processor.validate_role(
                    role_path,
                    validate_readme=validate_readme,
                    validate_argument_specs=validate_argument_specs,
                )
            except (ValidationError, ProcessingError) as e:
                summary["errors"].append(f"Role '{role_name}': {e}")

        if validate_readme:
            errors, warnings, notices = self._validate_collection_readme_markers()
            summary["errors"].extend(errors)
            summary["warnings"].extend(warnings)
            summary["notices"].extend(notices)

        return summary

    def _validate_collection_readme_markers(
        self,
    ) -> tuple[list[str], list[str], list[str]]:
        """Check role-named markers in the collection README."""
        errors: list[str] = []
        warnings: list[str] = []
        notices: list[str] = []

        readme_path = self._find_collection_readme()
        if readme_path is None:
            return errors, warnings, notices

        content = readme_path.read_text(encoding="utf-8")

        # Unknown roles referenced by markers
        referenced_roles = {
            match.group("role")
            for match in MARKER_PATTERN.finditer(content)
            if match.group("role")
        }
        for unknown in sorted(referenced_roles - set(self.roles)):
            warnings.append(
                f"{readme_path.name} references unknown role '{unknown}' "
                f"in DocSmith markers."
            )

        # Mismatched START/END pairs of role-named markers
        for role_name in sorted(referenced_roles):
            for marker_type in ("MAIN", "TOC", "TOC-FULL"):
                start = marker_comment(
                    marker_type, role_name, format_type=self.format_type
                )
                end = marker_comment(
                    marker_type, role_name, end=True, format_type=self.format_type
                )
                has_start, has_end = start in content, end in content
                if has_start != has_end:
                    missing = end if has_start else start
                    errors.append(f"{readme_path.name} is missing marker: '{missing}'")

        # Roles without any named marker section (opt-in, so only a notice)
        unreferenced = sorted(set(self.roles) - referenced_roles)
        if unreferenced:
            example = marker_comment(
                "TOC", unreferenced[0], format_type=self.format_type
            )
            notices.append(
                f"{readme_path.name} has no DocSmith marker sections for: "
                f"{', '.join(unreferenced)}. Add e.g. '{example}' markers "
                f"if you want DocSmith to maintain content for them."
            )

        return errors, warnings, notices
