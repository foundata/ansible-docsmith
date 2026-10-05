"""Owned comment sections for variables without defaults."""

import re
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from ansible_docsmith.core.defaults_comments import (
    MISSING_END,
    MISSING_START,
    DefaultsCommentGenerator,
)
from ansible_docsmith.core.exceptions import FileOperationError

SPECS: dict[str, Any] = {
    "main": {
        "options": {
            "app_host": {"description": "Server hostname.", "required": True},
        }
    }
}
SECTION = """# ANSIBLE DOCSMITH MISSING START
#
# The following variables have no default values. They are documented
# here as comments for easier discovery:
#
# Server hostname.
#
# - Type: str
# - Required: Yes
# app_host:
#
# ANSIBLE DOCSMITH MISSING END
"""


@pytest.mark.parametrize(
    "original", ["", "# Keep this introduction.\n", "---\n", "{}\n"]
)
def test_empty_defaults_and_exact_marker_spacing(original: str) -> None:
    generator = DefaultsCommentGenerator(include_missing=True)

    updated = generator.build_updated_content(original, SPECS)

    assert updated == original + SECTION
    assert YAML().load(updated) == YAML().load(original)
    assert generator.build_updated_content(updated, SPECS) == updated
    assert DefaultsCommentGenerator().build_updated_content(updated, SPECS) == original


def test_missing_file_is_prepared_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "defaults/main.yml"
    generator = DefaultsCommentGenerator(include_missing=True)
    assert generator.add_comments(path, SPECS) == "---\n" + SECTION
    assert not path.parent.exists()
    assert generator.build_updated_content(None, {"main": {"options": {}}}) is None
    assert DefaultsCommentGenerator().add_comments(path, SPECS) is None


@pytest.mark.parametrize("nested", [True, False])
def test_missing_selection_and_existing_metadata_rendering(nested: bool) -> None:
    options: dict[str, Any] = {
        "app_host": {"description": "Server hostname.", "required": True},
        "app_tls": {
            "type": "dict",
            "description": "Optional TLS settings.",
            "options": {
                "certificate": {"type": "path", "description": "Certificate file."}
            },
        },
        "without_description": {"type": "list", "elements": "str"},
        "credential": {"no_log": True, "aliases": ["old_credential"]},
        "mode": {"choices": ["first", "second"]},
        "spec_null": {"default": None},
        "spec_default": {"default": "value"},
        "present_null": {},
        "present_false": {},
        "present_zero": {},
        "present_empty": {},
        "present_quoted": {},
        "present_merged": {},
    }
    original = (
        "base: &base\n  present_merged: value\n<<: *base\n"
        "present_null:\npresent_false: false\npresent_zero: 0\n"
        'present_empty: ""\n"present_quoted": value\n'
        "# A hand-written example stays here.\n# app_host:\n"
    )
    generator = DefaultsCommentGenerator(nested_options=nested, include_missing=True)

    updated = generator.build_updated_content(original, {"main": {"options": options}})

    assert updated is not None
    section = updated[updated.index(MISSING_START) :]
    expected_names = [
        "app_host",
        "app_tls",
        "without_description",
        "credential",
        "mode",
    ]
    assert [
        line[2:-1] for line in section.splitlines() if re.fullmatch(r"# \w+:", line)
    ] == expected_names
    for name in expected_names:
        assert "\n".join(generator._format_block_comment(options[name])) in section
    assert ("#   - certificate:" in section) is nested
    assert "# certificate:" not in section
    assert "# - Default:" not in section
    assert original in updated
    assert YAML().load(updated) == YAML().load(original)


def test_replaces_only_owned_section_and_prunes_obsolete_entries() -> None:
    generator = DefaultsCommentGenerator(include_missing=True)
    original = "---\n# Hand-written example.\n# app_host:\n" + SECTION
    replacement_specs = {"main": {"options": {"new_option": {"type": "int"}}}}

    updated = generator.build_updated_content(original, replacement_specs)

    assert updated is not None
    assert updated.startswith("---\n# Hand-written example.\n# app_host:\n")
    assert "# new_option:" in updated
    assert "Server hostname." not in updated
    assert updated.count(MISSING_START) == 1
    assert generator.build_updated_content(updated, replacement_specs) == updated


@pytest.mark.parametrize("assignment", ["app_host: example.org\n", "app_host:\n"])
def test_real_assignment_outside_section_removes_placeholder(assignment: str) -> None:
    generator = DefaultsCommentGenerator(include_missing=True)
    original = "---\n" + SECTION + assignment

    updated = generator.build_updated_content(original, SPECS)

    assert updated is not None
    assert MISSING_START not in updated
    assert assignment in updated
    assert "# Server hostname." in updated
    assert YAML().load(updated) == YAML().load(original)
    assert generator.build_updated_content(updated, SPECS) == updated


@pytest.mark.parametrize("include_missing", [True, False])
@pytest.mark.parametrize(
    "section",
    [
        MISSING_START + "\n",
        MISSING_END + "\n",
        MISSING_END + "\n" + MISSING_START + "\n",
        SECTION + SECTION,
        MISSING_START + "\n" + SECTION + MISSING_END + "\n",
    ],
)
def test_malformed_markers_are_rejected(section: str, include_missing: bool) -> None:
    generator = DefaultsCommentGenerator(include_missing=include_missing)
    with pytest.raises(FileOperationError, match="ordered pair"):
        generator.build_updated_content(section, SPECS)


@pytest.mark.parametrize("include_missing", [True, False])
def test_uncommented_assignments_inside_section_are_never_removed(
    include_missing: bool,
) -> None:
    generator = DefaultsCommentGenerator(include_missing=include_missing)
    original = SECTION.replace("# app_host:", "app_host:")
    with pytest.raises(FileOperationError, match="move assignments outside"):
        generator.build_updated_content(original, SPECS)


@pytest.mark.parametrize("style", ["|", "|-", "|+", ">", ">-", ">+"])
@pytest.mark.parametrize("ending", ["\n", "\n\n"])
def test_section_does_not_change_trailing_block_scalar(style: str, ending: str) -> None:
    original = f"message: {style}\n  text{ending}"
    generator = DefaultsCommentGenerator(include_missing=True)

    updated = generator.build_updated_content(original, SPECS)

    assert updated is not None
    assert YAML().load(updated) == YAML().load(original)
    assert generator.build_updated_content(updated, SPECS) == updated
    assert DefaultsCommentGenerator().build_updated_content(updated, SPECS) == original


@pytest.mark.parametrize("original", ["[]\n", "false\n", "a scalar\n", "key: [\n"])
def test_invalid_defaults_are_rejected(original: str) -> None:
    with pytest.raises(FileOperationError):
        DefaultsCommentGenerator(include_missing=True).build_updated_content(
            original, SPECS
        )


def test_marker_text_inside_quoted_yaml_is_not_silently_deleted() -> None:
    original = 'message: "before\n' + SECTION + 'after"\n'
    with pytest.raises(FileOperationError, match="would change defaults values"):
        DefaultsCommentGenerator(include_missing=True).build_updated_content(
            original, SPECS
        )


def test_invalid_variable_name_cannot_inject_yaml() -> None:
    specs: dict[str, Any] = {"main": {"options": {"foo\ninjected": {}}}}
    with pytest.raises(FileOperationError, match="Invalid missing variable name"):
        DefaultsCommentGenerator(include_missing=True).build_updated_content("", specs)


@pytest.mark.parametrize("style", ["|+", ">+"])
def test_existing_comments_do_not_extend_preceding_scalar(style: str) -> None:
    original = f"---\nmessage: {style}\n  text\nnext: false\n"
    specs = {
        "main": {
            "options": {
                "message": {"description": "Message."},
                "next": {"description": "Next setting."},
                **SPECS["main"]["options"],
            }
        }
    }
    generator = DefaultsCommentGenerator(include_missing=True)

    updated = generator.build_updated_content(original, specs)

    assert updated is not None
    assert YAML().load(updated) == YAML().load(original)
    assert generator.build_updated_content(updated, specs) == updated


@pytest.mark.parametrize(
    "original",
    [
        "value: !vault |\n  encrypted\n",
        "value: !unsafe '{{ not_a_template }}'\n",
        "value: &base {nested: 1}\nalias: *base\n",
        "value: &self [*self]\n",
        "value: .nan\n",
    ],
)
def test_tags_and_aliases_are_preserved(original: str) -> None:
    generator = DefaultsCommentGenerator(include_missing=True)
    updated = generator.build_updated_content(original, SPECS)
    assert updated == original + SECTION
    assert generator.build_updated_content(updated, SPECS) == updated


def test_section_follows_new_specification_order() -> None:
    generator = DefaultsCommentGenerator(include_missing=True)
    specs: dict[str, Any] = {"main": {"options": {"first": {}, "second": {}}}}
    original = generator.build_updated_content("", specs)
    specs["main"]["options"] = {"second": {}, "first": {}}

    updated = generator.build_updated_content(original, specs)

    assert updated is not None
    assert updated.index("# second:") < updated.index("# first:")
    assert generator.build_updated_content(updated, specs) == updated


@pytest.mark.parametrize("marker", [MISSING_START, MISSING_END])
def test_description_cannot_emit_reserved_markers(marker: str) -> None:
    specs = {"main": {"options": {"value": {"description": marker.removeprefix("# ")}}}}
    with pytest.raises(FileOperationError, match="ordered pair"):
        DefaultsCommentGenerator(include_missing=True).build_updated_content("", specs)
