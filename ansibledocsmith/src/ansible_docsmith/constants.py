"""Global constants for ansible-docsmith."""

# README section markers for managed documentation sections (content only)
MARKER_README_MAIN_START = "ANSIBLE DOCSMITH MAIN START"
MARKER_README_MAIN_END = "ANSIBLE DOCSMITH MAIN END"

# TOC section markers for table of contents (content only)
MARKER_README_TOC_START = "ANSIBLE DOCSMITH TOC START"
MARKER_README_TOC_END = "ANSIBLE DOCSMITH TOC END"

# Markdown comment markers
MARKER_COMMENT_MD_BEGIN = "<!-- "
MARKER_COMMENT_MD_END = " -->"

# ReStructuredText comment
MARKER_COMMENT_RST_BEGIN = ".. "
MARKER_COMMENT_RST_END = ""

# Default maximum length for variable description shown in tables
TABLE_DESCRIPTION_MAX_LENGTH = 250

# Maximum nesting depth for documenting nested options ("dict attributes")
# in entry-point file comments. Matches the depth limit of the built-in
# README templates.
COMMENT_MAX_NESTED_DEPTH = 3

# Valid keys in role argument specs, used to warn about unknown (likely
# misspelled) keys. Based on the role argument spec documentation schema
# maintained by the Ansible community (antsibull-docs, role.py /
# OptionsSchema) plus keys accepted and honored by ansible-core's runtime
# argument validation. If DocSmith seems outdated, compare with
# https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html
SPEC_VALID_ENTRYPOINT_KEYS = frozenset(
    {
        "author",
        "attributes",
        "deprecated",
        "description",
        "examples",
        "notes",
        "options",
        "requirements",
        "seealso",
        "short_description",
        "todo",
        "version_added",
    }
)
SPEC_VALID_OPTION_KEYS = frozenset(
    {
        "aliases",
        "apply_defaults",
        "choices",
        "context",
        "default",
        "deprecated_aliases",
        "description",
        "elements",
        "mutually_exclusive",
        "no_log",
        "options",
        "removed_at_date",
        "removed_from_collection",
        "removed_in_version",
        "required",
        "required_by",
        "required_if",
        "required_one_of",
        "required_together",
        "type",
        "version_added",
        "version_added_collection",
    }
)

# CLI branding (please keep rendered length under 75 chars)
CLI_HEADER = (
    "Welcome to "
    "[link=https://foundata.com/en/projects/ansible-docsmith/]DocSmith[/link] "
    "for Ansible v{version} (developed by [link=https://foundata.com]foundata[/link])"
)
