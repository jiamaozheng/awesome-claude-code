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


MIGRATED_FRONTMATTER_KINDS = {"agent", "instruction"}
DEFAULT_AGENT_MODEL = "gpt-5.3-codex"
CLAUDE_COMPATIBLE_AGENT_MODEL = "sonnet"
TEXT_FILE_SUFFIXES = {
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
    ".csv",
    ".toml",
    ".ini",
}


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


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return None, text

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None, text

    frontmatter = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :])
    return frontmatter, body


def _normalize_instruction_frontmatter(frontmatter: str) -> str:
    """Convert upstream instruction frontmatter to repository schema.

    Upstream instruction files use `applyTo`; this repo validates `paths`.
    """
    lines = frontmatter.splitlines()
    has_paths = any(line.strip().startswith("paths:") for line in lines)
    if has_paths:
        return frontmatter

    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if stripped.startswith("applyTo:"):
            out.append(f"{indent}paths:{stripped[len('applyTo:'):]}")
        else:
            out.append(line)
    return "\n".join(out)


def _normalize_agent_frontmatter(frontmatter: str) -> str:
    """Backward-compatible wrapper; prefer the slug-aware variant below."""
    lines = frontmatter.splitlines()
    has_model = any(line.strip().startswith("model:") for line in lines)
    if has_model:
        return frontmatter
    return "\n".join([*lines, f"model: {DEFAULT_AGENT_MODEL}"])


def _set_or_append_scalar_key(frontmatter: str, key: str, value: str) -> str:
    lines = frontmatter.splitlines()
    key_prefix = f"{key}:"
    for idx, line in enumerate(lines):
        if line.lstrip().startswith(key_prefix):
            indent = line[: len(line) - len(line.lstrip())]
            lines[idx] = f"{indent}{key}: {value}"
            return "\n".join(lines)
    return "\n".join([*lines, f"{key}: {value}"])


def _agent_slug_from_path(path: Path) -> str:
    if path.name.endswith(".agent.md"):
        return path.name[: -len(".agent.md")]
    return path.stem


def _normalize_agent_frontmatter_for_claude(frontmatter: str, dst: Path) -> str:
    normalized = _set_or_append_scalar_key(frontmatter, "name", _agent_slug_from_path(dst))
    normalized = _set_or_append_scalar_key(normalized, "model", CLAUDE_COMPATIBLE_AGENT_MODEL)
    return normalized


def _copy_with_frontmatter(frontmatter: str, body: str, dst: Path) -> None:
    dst.write_text(f"---\n{frontmatter}\n---\n\n{body.lstrip()}", encoding="utf-8")


def _copy_plugin_bundle(src_manifest: Path, dst_manifest: Path) -> None:
    """Copy entire plugin directory for plugin manifest inventory rows."""
    src_plugin_root = src_manifest.parents[2]
    dst_plugin_root = dst_manifest.parents[2]
    for src_file in src_plugin_root.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_plugin_root)
        dst_file = dst_plugin_root / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)


def _read_text_with_fallback(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Some upstream text files occasionally ship in cp1252; normalize to UTF-8 on copy.
        return path.read_text(encoding="cp1252")


def _copy_text_as_utf8(src: Path, dst: Path) -> None:
    dst.write_text(_read_text_with_fallback(src), encoding="utf-8")


def _copy_file(kind: str, src: Path, dst: Path, dry_run: bool) -> None:
    if dry_run:
        return

    dst.parent.mkdir(parents=True, exist_ok=True)

    if kind == "plugin" and src.name == "plugin.json" and src.parts[-3:] == (".github", "plugin", "plugin.json"):
        _copy_plugin_bundle(src, dst)
        return

    if kind in MIGRATED_FRONTMATTER_KINDS and dst.exists():
        src_text = _read_text_with_fallback(src)
        dst_text = dst.read_text(encoding="utf-8")
        dst_frontmatter, _ = _split_frontmatter(dst_text)
        _, src_body = _split_frontmatter(src_text)

        if dst_frontmatter is not None:
            frontmatter_to_keep = dst_frontmatter
            if kind == "agent":
                frontmatter_to_keep = _normalize_agent_frontmatter_for_claude(dst_frontmatter, dst)
            _copy_with_frontmatter(frontmatter_to_keep, src_body, dst)
            return

    if kind == "instruction":
        src_text = _read_text_with_fallback(src)
        src_frontmatter, src_body = _split_frontmatter(src_text)
        if src_frontmatter is not None:
            normalized = _normalize_instruction_frontmatter(src_frontmatter)
            _copy_with_frontmatter(normalized, src_body, dst)
            return

    if kind == "agent":
        src_text = _read_text_with_fallback(src)
        src_frontmatter, src_body = _split_frontmatter(src_text)
        if src_frontmatter is not None:
            normalized = _normalize_agent_frontmatter_for_claude(src_frontmatter, dst)
            _copy_with_frontmatter(normalized, src_body, dst)
            return

    if src.suffix.lower() in TEXT_FILE_SUFFIXES:
        _copy_text_as_utf8(src, dst)
        return

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

        _copy_file(row.kind, src_now, dst_now, args.dry_run)
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
