"""Global constants for ansible-docsmith."""

# README section markers for managed documentation sections (content only)
MARKER_README_MAIN_START = "BEGIN ANSIBLE DOCSMITH"
MARKER_README_MAIN_END = "END ANSIBLE DOCSMITH"

# Markdown comment markers for different output formats
MARKER_COMMENT_MARKDOWN_BEGIN = "<!-- "
MARKER_COMMENT_MARKDOWN_END = " -->"

# CLI branding (please keep rendered length under 75 chars)
CLI_HEADER = (
    "Welcome to [link=https://github.com/foundata/ansible-docsmith]DocSmith[/link] "
    "for Ansible v{version} (developed by [link=https://foundata.com]foundata[/link])"
)
