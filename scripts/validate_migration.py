#!/usr/bin/env python3
"""Validate Copilot->Claude migration integrity across artifact types.

Checks:
- docs/migration-inventory.csv exists and has required columns
- Every inventory target path exists
- Every migrated artifact file in repo has a corresponding inventory row
- Inventory rows do not reference out-of-scope or unknown types

Artifact mapping:
- instruction -> instructions/*.md
- agent       -> agents/*.md
- skill       -> skills/*/SKILL.md
- hook        -> hooks/*/hooks.json
- plugin      -> plugins/*/.github/plugin/plugin.json + plugins/external.json
- workflow    -> workflows/*.md
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "migration-inventory.csv"

KNOWN_TYPES = {"instruction", "agent", "skill", "hook", "plugin", "workflow"}


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


def discover_artifacts() -> Dict[str, Set[str]]:
    artifacts: Dict[str, Set[str]] = {
        "instruction": set(),
        "agent": set(),
        "skill": set(),
        "hook": set(),
        "plugin": set(),
        "workflow": set(),
    }

    for p in (ROOT / "instructions").glob("*.md"):
        if p.is_file():
            artifacts["instruction"].add(str(p.resolve()))

    for p in (ROOT / "agents").glob("*.md"):
        if p.is_file():
            artifacts["agent"].add(str(p.resolve()))

    for p in (ROOT / "skills").glob("**/SKILL.md"):
        if p.is_file():
            artifacts["skill"].add(str(p.resolve()))

    for p in (ROOT / "hooks").glob("*/hooks.json"):
        if p.is_file():
            artifacts["hook"].add(str(p.resolve()))

    for p in (ROOT / "plugins").glob("*/.github/plugin/plugin.json"):
        if p.is_file():
            artifacts["plugin"].add(str(p.resolve()))

    external = ROOT / "plugins" / "external.json"
    if external.exists() and external.is_file():
        artifacts["plugin"].add(str(external.resolve()))

    workflows_dir = ROOT / "workflows"
    if workflows_dir.exists() and workflows_dir.is_dir():
        for p in workflows_dir.glob("*.md"):
            if p.is_file():
                artifacts["workflow"].add(str(p.resolve()))

    return artifacts


def load_inventory() -> tuple[List[dict], List[Issue]]:
    issues: List[Issue] = []
    if not INVENTORY.exists():
        issues.append(Issue("CRITICAL", rel(INVENTORY), "Missing migration inventory CSV"))
        return [], issues

    rows: List[dict] = []
    with INVENTORY.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"type", "source", "target"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            issues.append(Issue("CRITICAL", rel(INVENTORY), "CSV must include columns: type,source,target"))
            return [], issues

        for idx, row in enumerate(reader, start=2):
            rtype = (row.get("type") or "").strip()
            source = (row.get("source") or "").strip()
            target = (row.get("target") or "").strip()

            if rtype not in KNOWN_TYPES:
                issues.append(Issue("HIGH", rel(INVENTORY), f"Line {idx}: unknown type '{rtype}'"))
            if not source:
                issues.append(Issue("HIGH", rel(INVENTORY), f"Line {idx}: empty source path"))
            if not target:
                issues.append(Issue("HIGH", rel(INVENTORY), f"Line {idx}: empty target path"))

            rows.append({"line": idx, "type": rtype, "source": source, "target": target})

    return rows, issues


def validate_inventory_targets_exist(rows: Iterable[dict]) -> List[Issue]:
    issues: List[Issue] = []
    for row in rows:
        rtype = row["type"]
        if rtype not in KNOWN_TYPES:
            continue
        t = Path(row["target"])
        if not t.exists():
            issues.append(Issue("HIGH", rel(INVENTORY), f"Line {row['line']}: missing target file {row['target']}"))
            continue
        if not t.is_file():
            issues.append(Issue("HIGH", rel(INVENTORY), f"Line {row['line']}: target is not a file {row['target']}"))
    return issues


def validate_inventory_vs_artifacts(rows: Iterable[dict], artifacts: Dict[str, Set[str]]) -> List[Issue]:
    issues: List[Issue] = []

    inventory_targets_by_type: Dict[str, Set[str]] = {k: set() for k in KNOWN_TYPES}

    for row in rows:
        rtype = row["type"]
        if rtype not in KNOWN_TYPES:
            continue
        inventory_targets_by_type[rtype].add(str(Path(row["target"]).resolve()))

    for rtype in sorted(KNOWN_TYPES):
        expected = artifacts[rtype]
        actual = inventory_targets_by_type[rtype]

        missing_rows = sorted(expected - actual)
        extra_rows = sorted(actual - expected)

        for m in missing_rows:
            issues.append(Issue("HIGH", rel(INVENTORY), f"Missing inventory row for {rtype} target: {m}"))
        for e in extra_rows:
            issues.append(Issue("MEDIUM", rel(INVENTORY), f"Unexpected inventory row for {rtype} target: {e}"))

    return issues


def print_report(issues: List[Issue], artifacts: Dict[str, Set[str]], rows_count: int) -> None:
    print("Migration artifact counts:")
    for t in sorted(KNOWN_TYPES):
        print(f"- {t}: {len(artifacts[t])}")
    print(f"Inventory rows: {rows_count}")
    print(f"Total issues: {len(issues)}")

    if not issues:
        print("✅ Migration validation passed")
        return

    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    for i in sorted(issues, key=lambda x: (order.get(x.severity, 9), x.path, x.message)):
        print(f"- [{i.severity}] {i.path}: {i.message}")


def main() -> int:
    artifacts = discover_artifacts()
    rows, issues = load_inventory()

    if rows:
        issues.extend(validate_inventory_targets_exist(rows))
        issues.extend(validate_inventory_vs_artifacts(rows, artifacts))

    print_report(issues, artifacts, len(rows))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
