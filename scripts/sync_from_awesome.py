#!/usr/bin/env python3
"""Sync migrated artifacts from awesome-copilot into this repository.

This script uses docs/migration-inventory.csv as the single source of truth.
It maps each inventory source path (captured from an older local clone path)
onto a current upstream checkout path, then copies the matching file into the
tracked target location in this repository.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Row:
    kind: str
    source: Path
    target: Path


def _load_rows(inventory_path: Path) -> list[Row]:
    rows: list[Row] = []
    with inventory_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"type", "source", "target"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError("Inventory must contain columns: type, source, target")
        for rec in reader:
            rows.append(Row(kind=rec["type"], source=Path(rec["source"]), target=Path(rec["target"])))
    return rows


def _copy_file(src: Path, dst: Path, dry_run: bool) -> None:
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _collect_candidate_source_files(source_root: Path) -> set[Path]:
    patterns = [
        "instructions/*.instructions.md",
        "agents/*.md",
        "skills/**/SKILL.md",
        "hooks/*/hooks.json",
        "workflows/*.md",
        "plugins/**/.github/plugin/plugin.json",
        "plugins/external.json",
    ]

    files: set[Path] = set()
    for pattern in patterns:
        for path in source_root.glob(pattern):
            if path.is_file():
                files.add(path.relative_to(source_root))
    return files


def _infer_type(rel: Path) -> str:
    parts = rel.parts
    if parts[0] == "instructions":
        return "instruction"
    if parts[0] == "agents":
        return "agent"
    if parts[0] == "skills":
        return "skill"
    if parts[0] == "hooks":
        return "hook"
    if parts[0] == "workflows":
        return "workflow"
    if parts[0] == "plugins":
        return "plugin"
    return "unknown"


def _write_unmapped_csv(unmapped: list[Path], out_path: Path) -> None:
    """Write new inventory rows for unmapped upstream files.

    Both source and target are relative paths, consistent with the new CSV format.
    """
    rows_to_write: list[dict[str, str]] = []
    for rel in unmapped:
        kind = _infer_type(rel)
        rows_to_write.append({"type": kind, "source": str(rel), "target": str(rel)})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "source", "target"])
        writer.writeheader()
        writer.writerows(rows_to_write)
    print(f"\nWrote {len(rows_to_write)} new inventory row(s) to: {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync files from awesome-copilot using migration inventory")
    parser.add_argument("--source-root", required=True, help="Path to current awesome-copilot checkout")
    parser.add_argument("--inventory", default="docs/migration-inventory.csv", help="Path to migration inventory CSV")
    parser.add_argument("--repo-root", default=".", help="Path to this repository root")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without copying")
    parser.add_argument(
        "--fail-on-unmapped",
        action="store_true",
        help="Return non-zero if potential upstream files are not covered by inventory",
    )
    parser.add_argument(
        "--emit-unmapped-csv",
        metavar="PATH",
        help="Write unmapped upstream files as new inventory rows to this CSV path",
    )
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    repo_root = Path(args.repo_root).resolve()
    inventory_path = Path(args.inventory).resolve()

    if not source_root.exists():
        print(f"ERROR: source root does not exist: {source_root}", file=sys.stderr)
        return 2
    if not inventory_path.exists():
        print(f"ERROR: inventory not found: {inventory_path}", file=sys.stderr)
        return 2

    rows = _load_rows(inventory_path)

    copied = 0
    missing = 0
    outside_repo = 0

    mapped_source_rels: set[Path] = set()

    for row in rows:
        src_rel = row.source
        mapped_source_rels.add(src_rel)
        dst_rel = row.target

        src_now = source_root / src_rel
        dst_now = repo_root / dst_rel

        try:
            dst_now.relative_to(repo_root)
        except Exception:  # noqa: BLE001
            outside_repo += 1
            print(f"SKIP (outside repo): {dst_now}")
            continue

        if not src_now.exists():
            missing += 1
            print(f"MISSING SOURCE: {src_rel}")
            continue

        _copy_file(src_now, dst_now, args.dry_run)
        copied += 1
        action = "WOULD COPY" if args.dry_run else "COPIED"
        print(f"{action}: {src_rel} -> {dst_rel}")

    print("\nSync summary")
    print(f"- rows processed: {len(rows)}")
    print(f"- files copied: {copied}")
    print(f"- missing sources: {missing}")
    print(f"- outside repo skipped: {outside_repo}")

    candidate_sources = _collect_candidate_source_files(source_root)
    unmapped = sorted(candidate_sources - mapped_source_rels)
    print(f"- potential unmapped upstream files: {len(unmapped)}")
    if unmapped:
        print("\nPotential unmapped upstream files (review and add to inventory if needed):")
        for rel in unmapped:
            print(f"  - {rel}")

        if args.emit_unmapped_csv:
            _write_unmapped_csv(unmapped, Path(args.emit_unmapped_csv))

    if missing:
        print("\nNOTE: Missing source files usually indicate upstream moved/deleted artifacts.")

    if args.fail_on_unmapped and unmapped:
        print("\nERROR: Unmapped upstream files found.", file=sys.stderr)
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
