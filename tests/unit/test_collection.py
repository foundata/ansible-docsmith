"""Tests for collection detection and processing (core/collection.py)."""

from pathlib import Path

from ansible_docsmith.core.collection import (
    CollectionProcessor,
    detect_project_type,
    find_collection_roles,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "example-collection"


class TestDetection:
    """Role vs. collection path detection."""

    def test_detects_role(self) -> None:
        role = Path(__file__).parent.parent / "fixtures" / "example-role-simple"
        assert detect_project_type(role) == "role"

    def test_detects_collection(self) -> None:
        assert detect_project_type(FIXTURE) == "collection"

    def test_detects_nothing(self, temp_dir: Path) -> None:
        assert detect_project_type(temp_dir) is None

    def test_role_wins_over_collection_layout(self, temp_dir: Path) -> None:
        # A (hypothetical) role with an own roles/ subdirectory is
        # treated as a role
        (temp_dir / "meta").mkdir()
        (temp_dir / "meta" / "argument_specs.yml").write_text("---\n")
        (temp_dir / "roles" / "sub" / "meta").mkdir(parents=True)
        (temp_dir / "roles" / "sub" / "meta" / "argument_specs.yml").write_text("---\n")
        assert detect_project_type(temp_dir) == "role"

    def test_find_collection_roles_sorted(self) -> None:
        roles = find_collection_roles(FIXTURE)
        assert list(roles.keys()) == ["first", "second"]
        assert roles["first"] == FIXTURE / "roles" / "first"

    def test_find_collection_roles_ignores_roles_without_specs(
        self, temp_dir: Path
    ) -> None:
        (temp_dir / "roles" / "with_spec" / "meta").mkdir(parents=True)
        (temp_dir / "roles" / "with_spec" / "meta" / "argument_specs.yml").write_text(
            "---\n"
        )
        (temp_dir / "roles" / "without_spec" / "tasks").mkdir(parents=True)

        roles = find_collection_roles(temp_dir)
        assert list(roles.keys()) == ["with_spec"]


class TestCollectionValidation:
    """Collection README marker validation."""

    def test_orphaned_role_marker_warns(self, temp_dir: Path) -> None:
        import shutil

        collection = temp_dir / "example-collection"
        shutil.copytree(FIXTURE, collection)
        readme = collection / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8")
            + "\n<!-- ANSIBLE DOCSMITH TOC no_such_role START -->\n"
            "<!-- ANSIBLE DOCSMITH TOC no_such_role END -->\n",
            encoding="utf-8",
        )

        processor = CollectionProcessor(collection_path=collection)
        summary = processor.validate_collection()

        assert any("unknown role 'no_such_role'" in w for w in summary["warnings"])

    def test_mismatched_named_marker_is_error(self, temp_dir: Path) -> None:
        import shutil

        collection = temp_dir / "example-collection"
        shutil.copytree(FIXTURE, collection)
        readme = collection / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8")
            + "\n<!-- ANSIBLE DOCSMITH MAIN second START -->\n",
            encoding="utf-8",
        )

        processor = CollectionProcessor(collection_path=collection)
        summary = processor.validate_collection()

        assert any("ANSIBLE DOCSMITH MAIN second END" in e for e in summary["errors"])

    def test_unreferenced_roles_produce_notice(self, temp_dir: Path) -> None:
        import shutil

        collection = temp_dir / "example-collection"
        shutil.copytree(FIXTURE, collection)
        readme = collection / "README.md"
        # Remove all markers for role "second"
        content = readme.read_text(encoding="utf-8")
        content = (
            content.replace("TOC-FULL second START", "X")
            .replace("TOC-FULL second END", "X")
            .replace("TOC second START", "X")
            .replace("TOC second END", "X")
        )
        readme.write_text(content, encoding="utf-8")

        processor = CollectionProcessor(collection_path=collection)
        summary = processor.validate_collection()

        assert any(
            "no DocSmith marker sections for: second" in n for n in summary["notices"]
        )

    def test_clean_fixture_validates_without_collection_findings(self) -> None:
        processor = CollectionProcessor(collection_path=FIXTURE)
        summary = processor.validate_collection()

        assert summary["errors"] == []
        assert summary["warnings"] == []
        assert summary["notices"] == []
        assert list(summary["roles"].keys()) == ["first", "second"]
