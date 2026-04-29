#!/usr/bin/env python3
"""Validate plugin migration and manifest compliance.

Checks:
- Every plugins/<name>/ directory contains README.md and .github/plugin/plugin.json
- plugin.json required fields: name, description, version (semver)
- plugin.json name matches folder name
- optional keywords are lowercase-hyphen strings
- optional agents/commands/skills arrays reference existing paths
- plugins/external.json exists and has valid entries
- docs/migration-inventory.csv includes plugin rows for each plugin manifest + external.json
"""

from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = ROOT / "plugins"
INVENTORY_CSV = ROOT / "docs" / "migration-inventory.csv"

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
LOWER_HYPHEN_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass
class Issue:
    severity: str
    path: str
    message: str


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> tuple[dict | list | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def list_plugin_dirs() -> List[Path]:
    if not PLUGINS_DIR.exists():
        return []
    return sorted([p for p in PLUGINS_DIR.iterdir() if p.is_dir()])


def validate_plugin_manifest(plugin_dir: Path) -> List[Issue]:
    issues: List[Issue] = []
    readme = plugin_dir / "README.md"
    manifest = plugin_dir / ".github" / "plugin" / "plugin.json"

    if not readme.exists():
        issues.append(Issue("HIGH", rel(readme), "Missing README.md"))

    if not manifest.exists():
        issues.append(Issue("CRITICAL", rel(manifest), "Missing .github/plugin/plugin.json"))
        return issues

    data, err = load_json(manifest)
    if err is not None or not isinstance(data, dict):
        issues.append(Issue("CRITICAL", rel(manifest), f"Invalid JSON: {err or 'root must be object'}"))
        return issues

    folder_name = plugin_dir.name

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        issues.append(Issue("CRITICAL", rel(manifest), "Missing or empty name"))
    elif name != folder_name:
        issues.append(Issue("HIGH", rel(manifest), f"name '{name}' does not match folder '{folder_name}'"))

    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        issues.append(Issue("HIGH", rel(manifest), "Missing or empty description"))

    version = data.get("version")
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        issues.append(Issue("HIGH", rel(manifest), f"Invalid semver version: {version!r}"))

    keywords = data.get("keywords")
    if keywords is not None:
        if not isinstance(keywords, list):
            issues.append(Issue("MEDIUM", rel(manifest), "keywords must be an array when present"))
        else:
            for kw in keywords:
                if not isinstance(kw, str) or not LOWER_HYPHEN_RE.match(kw):
                    issues.append(Issue("MEDIUM", rel(manifest), f"keywords contains invalid value: {kw!r}"))

    for key in ("agents", "commands", "skills"):
        val = data.get(key)
        if val is None:
            continue
        if not isinstance(val, list):
            issues.append(Issue("HIGH", rel(manifest), f"{key} must be an array when present"))
            continue

        for entry in val:
            if not isinstance(entry, str) or not entry.strip():
                issues.append(Issue("HIGH", rel(manifest), f"{key} contains non-string/empty entry"))
                continue
            target = plugin_dir / entry
            if not target.exists():
                issues.append(Issue("HIGH", rel(manifest), f"{key} references missing path: {entry}"))

    return issues


def validate_external_json() -> List[Issue]:
    issues: List[Issue] = []
    external_path = PLUGINS_DIR / "external.json"

    if not external_path.exists():
        issues.append(Issue("HIGH", rel(external_path), "Missing external.json"))
        return issues

    data, err = load_json(external_path)
    if err is not None or not isinstance(data, list):
        issues.append(Issue("CRITICAL", rel(external_path), f"Invalid JSON: {err or 'root must be array'}"))
        return issues

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            issues.append(Issue("HIGH", rel(external_path), f"entry[{i}] must be object"))
            continue

        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            issues.append(Issue("HIGH", rel(external_path), f"entry[{i}] missing/empty name"))

        description = entry.get("description")
        if not isinstance(description, str) or not description.strip():
            issues.append(Issue("HIGH", rel(external_path), f"entry[{i}] missing/empty description"))

        version = entry.get("version")
        if not isinstance(version, str) or not SEMVER_RE.match(version):
            issues.append(Issue("HIGH", rel(external_path), f"entry[{i}] invalid semver version: {version!r}"))

        source = entry.get("source")
        if not isinstance(source, dict):
            issues.append(Issue("HIGH", rel(external_path), f"entry[{i}] missing source object"))
        else:
            if not any(k in source for k in ("repo", "url", "package")):
                issues.append(Issue("HIGH", rel(external_path), f"entry[{i}] source missing repo/url/package"))

    return issues


def parse_inventory_plugin_targets() -> set[str]:
    if not INVENTORY_CSV.exists():
        return set()

    targets: set[str] = set()
    with INVENTORY_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("type") != "plugin":
                continue
            target = row.get("target") or ""
            target = target.strip()
            if target:
                # Resolve relative paths against repo root so they compare against
                # absolute paths produced by expected_inventory_targets().
                resolved = str((ROOT / target).resolve())
                targets.add(resolved)
    return targets


def expected_inventory_targets(plugin_dirs: Iterable[Path]) -> set[str]:
    expected = set()
    for d in plugin_dirs:
        expected.add(str((d / ".github" / "plugin" / "plugin.json").resolve()))
    expected.add(str((PLUGINS_DIR / "external.json").resolve()))
    return expected


def validate_inventory(plugin_dirs: Iterable[Path]) -> List[Issue]:
    issues: List[Issue] = []

    if not INVENTORY_CSV.exists():
        issues.append(Issue("HIGH", rel(INVENTORY_CSV), "Missing docs/migration-inventory.csv"))
        return issues

    actual = parse_inventory_plugin_targets()
    expected = expected_inventory_targets(plugin_dirs)

    missing = sorted(expected - actual)
    extras = sorted(actual - expected)

    for m in missing:
        issues.append(Issue("HIGH", rel(INVENTORY_CSV), f"Missing plugin target row: {m}"))
    for e in extras:
        issues.append(Issue("MEDIUM", rel(INVENTORY_CSV), f"Unexpected plugin target row: {e}"))

    return issues


def print_report(issues: List[Issue], plugin_dirs: List[Path]) -> None:
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    issues_sorted = sorted(issues, key=lambda i: (severity_order.get(i.severity, 99), i.path, i.message))

    print(f"Plugin directories: {len(plugin_dirs)}")
    print(f"Total issues: {len(issues_sorted)}")

    if not issues_sorted:
        print("✅ Plugin validation passed")
        return

    print("\nIssues:")
    for issue in issues_sorted:
        print(f"- [{issue.severity}] {issue.path}: {issue.message}")


def main() -> int:
    if not PLUGINS_DIR.exists():
        print("plugins directory does not exist")
        return 1

    plugin_dirs = list_plugin_dirs()
    issues: List[Issue] = []

    for plugin_dir in plugin_dirs:
        issues.extend(validate_plugin_manifest(plugin_dir))

    issues.extend(validate_external_json())
    issues.extend(validate_inventory(plugin_dirs))

    print_report(issues, plugin_dirs)

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
