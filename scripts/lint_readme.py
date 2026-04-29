#!/usr/bin/env python3
"""Lint README.md for stale or disallowed content."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"

# Patterns that must NOT appear in README.md
BANNED: list[tuple[str, str]] = [
    # Absolute local paths
    (r"/Users/\w+/", "absolute local path (/Users/...)"),
    (r"/home/\w+/", "absolute local path (/home/...)"),
    # Deleted directories/files
    (r"migration-pack/", "reference to deleted migration-pack/"),
    (r"claude-migration-notes\.md", "reference to deleted docs/claude-migration-notes.md"),
    # Old repo name
    (r"claude-code-customization-starter", "old repo name (use awesome-claude-code)"),
    # Duplicate section headings — caught separately below
]


def main() -> int:
    text = README.read_text(encoding="utf-8")
    lines = text.splitlines()

    errors: list[str] = []

    # Check banned patterns
    for pattern, description in BANNED:
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                errors.append(f"  Line {i}: {description!r} — {line.strip()!r}")

    # Check for duplicate section headings
    headings: dict[str, int] = {}
    for i, line in enumerate(lines, 1):
        if line.startswith("## "):
            heading = line.strip()
            if heading in headings:
                errors.append(
                    f"  Line {i}: duplicate heading {heading!r} (first at line {headings[heading]})"
                )
            else:
                headings[heading] = i

    if errors:
        print(f"README.md lint FAILED ({len(errors)} issue(s)):")
        for e in errors:
            print(e)
        return 1

    print("README.md lint passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
