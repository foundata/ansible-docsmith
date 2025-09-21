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

# CLI branding (please keep rendered length under 75 chars)
CLI_HEADER = (
    "Welcome to [link=https://github.com/foundata/ansible-docsmith]DocSmith[/link] "
    "for Ansible v{version} (developed by [link=https://foundata.com]foundata[/link])"
)
