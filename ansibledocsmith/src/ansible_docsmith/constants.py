"""Global constants for ansible-docsmith."""

# README section markers for managed documentation sections
README_START_MARKER = "<!-- BEGIN ANSIBLE DOCSMITH -->"
README_END_MARKER = "<!-- END ANSIBLE DOCSMITH -->"

# CLI branding (please keep rendered length under 75 chars)
CLI_HEADER = (
    "Welcome to [link=https://github.com/foundata/ansible-docsmith]DocSmith[/link] "
    "for Ansible v{version} (developed by [link=https://foundata.com]foundata[/link])"
)
