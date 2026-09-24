# SPDX-FileCopyrightText: 2026, foundata GmbH (https://foundata.com)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the foundata Markdown guide's invocation over this repository."""

import argparse
import subprocess
from pathlib import Path

# The guide's .rumdl.toml, copied verbatim; tests/unit/test_markdown_gate.py
# compares the copy with the guide. Naming the file explicitly makes rumdl
# ignore any other configuration it would discover.
CONFIG = ".rumdl.toml"

# Recorded inputs and expected output of the Markdown generator under test:
# byte-exact oracles, plus one deliberately non-conformant input. Linting them
# would report the point of the fixture as a defect, and formatting them would
# rewrite the oracle the tests compare against.
FIXTURES = "tests/fixtures"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", action="store_true")
    args = parser.parse_args()
    # One argument list for both verbs, so the exclusion cannot be carried by
    # the check and forgotten by the run that writes.
    return subprocess.run(
        [
            "rumdl",
            "fmt" if args.format else "check",
            "--config",
            CONFIG,
            "--deny-config-warnings",
            "--no-cache",
            "--exclude",
            FIXTURES,
            ".",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        timeout=120,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
