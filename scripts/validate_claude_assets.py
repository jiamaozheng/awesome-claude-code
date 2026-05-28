#!/usr/bin/env python3
"""Validate Claude customization assets for required structure and best practices.

Scope:
- agents/*.md
- instructions/*.md
- skills/**/SKILL.md
- hooks/*/{README.md,hooks.json}
- workflows/*.md

Behavior:
- Fails on ERROR findings
- Reports WARN findings for recommended best practices
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]

LOWER_HYPHEN_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CLAUDE_MODEL_RE = re.compile(r"^(inherit|sonnet|opus|haiku|claude-(?:sonnet|opus|haiku)-[A-Za-z0-9.-]+)$")
PLACEHOLDER_RE = re.compile(
    r"\$\{(?!\{|input:|openMarker|closeMarker|github\.workspace|[A-Z0-9_.-]+\})[^}]+\}"
    r"|(?<![A-Za-z0-9_])<[A-Z][A-Za-z0-9_\-]*>"
)

OFFICIAL_AGENT_KEYS = {
    "name",
    "description",
    "tools",
    "disallowedTools",
    "model",
    "permissionMode",
    "maxTurns",
    "skills",
    "mcpServers",
    "hooks",
    "memory",
    "background",
    "effort",
    "isolation",
    "color",
    "initialPrompt",
}

LEGACY_AGENT_KEY_WARNINGS = {
    "argument-hint": "Legacy GitHub Copilot frontmatter key 'argument-hint'; Claude Code has no direct equivalent, so keep only if this repo intentionally preserves Copilot metadata",
    "disable-model-invocation": "Legacy GitHub Copilot frontmatter key 'disable-model-invocation'; review whether this behavior needs a Claude Code replacement or should remain repo-specific metadata",
    "mcp-servers": "Legacy GitHub Copilot frontmatter key 'mcp-servers'; official Claude Code docs use 'mcpServers'",
    "user-invocable": "Legacy GitHub Copilot frontmatter key 'user-invocable'; review whether this should remain repo-specific metadata or be removed for Claude Code compatibility",
}

# Known upstream artifact warning that should not block strict sync validation.
SUPPRESSED_WARNINGS: set[tuple[str, str]] = {
    (
        "skills/flowstudio-power-automate-monitoring/SKILL.md",
        "description length should be 10-1024 characters",
    ),
    (
        "agents/ai-readiness-reporter.agent.md",
        "Legacy GitHub Copilot frontmatter key 'argument-hint'; Claude Code has no direct equivalent, so keep only if this repo intentionally preserves Copilot metadata",
    ),
    (
        "agents/azure-verified-modules-owner-triage.agent.md",
        "Legacy GitHub Copilot frontmatter key 'argument-hint'; Claude Code has no direct equivalent, so keep only if this repo intentionally preserves Copilot metadata",
    ),
}


@dataclass
class Finding:
    level: str  # ERROR | WARN
    path: str
    message: str


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def agent_slug(path: Path) -> str:
    if path.name.endswith(".agent.md"):
        return path.name[: -len(".agent.md")]
    return path.stem


def extract_frontmatter(path: Path) -> Tuple[str | None, str | None]:
    """Return (frontmatter, error)."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return None, f"Failed to read file: {exc}"

    # Must start with ---
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return None, "Missing YAML frontmatter at file start"

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "Invalid YAML frontmatter start delimiter"

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None, "Missing YAML frontmatter end delimiter"

    fm = "\n".join(lines[1:end_idx])
    return fm, None


def key_exists(frontmatter: str, key: str) -> bool:
    return re.search(rf"(?m)^\s*{re.escape(key)}\s*:", frontmatter) is not None


def key_value(frontmatter: str, key: str) -> str | None:
    lines = frontmatter.splitlines()
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(.*)$")

    for i, line in enumerate(lines):
        m = key_re.match(line)
        if not m:
            continue

        value = m.group(1).strip()

        # YAML block scalar support: description: | or description: >
        if value in {"|", ">"} or value.startswith("|-") or value.startswith("|+") or value.startswith(">-") or value.startswith(">+"):
            block_lines: list[str] = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.startswith(" ") or next_line.startswith("\t") or next_line == "":
                    block_lines.append(next_line)
                    j += 1
                    continue
                break
            block = "\n".join(block_lines).strip()
            return block if block else None

        # remove inline comments
        value = re.sub(r"\s+#.*$", "", value).strip()
        # strip quotes
        if (value.startswith("\"") and value.endswith("\"")) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        return value or None

    return None


def frontmatter_keys(frontmatter: str) -> list[str]:
    keys: list[str] = []
    for line in frontmatter.splitlines():
        match = re.match(r"^([A-Za-z0-9_-]+)\s*:", line)
        if match:
            keys.append(match.group(1))
    return keys


def frontmatter_has_placeholders(frontmatter: str) -> bool:
    sanitized = re.sub(r"\$\{\{[^\n]+?\}\}", "", frontmatter)
    return PLACEHOLDER_RE.search(sanitized) is not None


def validate_agents() -> List[Finding]:
    findings: List[Finding] = []
    for path in sorted((ROOT / "agents").glob("*.md")):
        slug = agent_slug(path)
        fm, err = extract_frontmatter(path)
        if err:
            findings.append(Finding("ERROR", rel(path), err))
            continue

        desc = key_value(fm, "description")
        if not desc:
            findings.append(Finding("ERROR", rel(path), "Missing or empty frontmatter 'description'"))

        name = key_value(fm, "name")
        if not name:
            findings.append(Finding("WARN", rel(path), "Missing frontmatter 'name'; official Claude Code subagents require a lowercase-hyphen identifier"))
        else:
            if not LOWER_HYPHEN_RE.match(name):
                findings.append(Finding("WARN", rel(path), f"Agent 'name' should be a lowercase-hyphen identifier for Claude Code compatibility: {name}"))
            if name != slug:
                findings.append(Finding("WARN", rel(path), f"Agent 'name' does not match file name stem '{slug}'"))

        if not LOWER_HYPHEN_RE.match(slug):
            findings.append(Finding("WARN", rel(path), f"Agent file name should be lowercase-hyphen: {slug}"))

        if not key_exists(fm, "model"):
            findings.append(Finding("WARN", rel(path), "Missing recommended frontmatter 'model'"))
        else:
            model = key_value(fm, "model")
            if model and not CLAUDE_MODEL_RE.match(model):
                findings.append(Finding("WARN", rel(path), f"Model value is not in a standard Claude Code format (inherit/sonnet/opus/haiku/full claude-* id): {model}"))

        if frontmatter_has_placeholders(fm):
            findings.append(Finding("WARN", rel(path), "Frontmatter appears to contain unresolved template placeholders"))

        for key in frontmatter_keys(fm):
            if key in LEGACY_AGENT_KEY_WARNINGS:
                findings.append(Finding("WARN", rel(path), LEGACY_AGENT_KEY_WARNINGS[key]))
            elif key not in OFFICIAL_AGENT_KEYS:
                findings.append(Finding("WARN", rel(path), f"Unrecognized agent frontmatter key for official Claude Code docs: {key}"))

    return findings


def validate_instructions() -> List[Finding]:
    findings: List[Finding] = []
    for path in sorted((ROOT / "instructions").glob("*.md")):
        fm, err = extract_frontmatter(path)
        if err:
            findings.append(Finding("ERROR", rel(path), err))
            continue

        desc = key_value(fm, "description")
        if not desc:
            findings.append(Finding("ERROR", rel(path), "Missing or empty frontmatter 'description'"))

        # Claude-migrated rule uses paths (mapped from applyTo)
        if not key_exists(fm, "paths"):
            findings.append(Finding("ERROR", rel(path), "Missing required frontmatter 'paths'"))
        if frontmatter_has_placeholders(fm):
            findings.append(Finding("WARN", rel(path), "Frontmatter appears to contain unresolved template placeholders"))

    return findings


def validate_skills() -> List[Finding]:
    findings: List[Finding] = []
    for path in sorted((ROOT / "skills").glob("**/SKILL.md")):
        fm, err = extract_frontmatter(path)
        if err:
            findings.append(Finding("ERROR", rel(path), err))
            continue

        folder = path.parent.name
        rel_parts = path.relative_to(ROOT).parts
        # Top-level skill: skills/<name>/SKILL.md
        is_top_level_skill = len(rel_parts) == 3 and rel_parts[0] == "skills"

        name = key_value(fm, "name")
        if not name:
            findings.append(Finding("ERROR", rel(path), "Missing or empty frontmatter 'name'"))
        else:
            if is_top_level_skill and name != folder:
                findings.append(Finding("ERROR", rel(path), f"'name' ({name}) must match folder name ({folder})"))
            if not LOWER_HYPHEN_RE.match(name):
                findings.append(Finding("ERROR", rel(path), f"'name' must be lowercase-hyphen: {name}"))

        desc = key_value(fm, "description")
        if not desc:
            findings.append(Finding("ERROR", rel(path), "Missing or empty frontmatter 'description'"))
        else:
            if len(desc) < 10 or len(desc) > 1024:
                findings.append(Finding("WARN", rel(path), "description length should be 10-1024 characters"))
        if frontmatter_has_placeholders(fm):
            findings.append(Finding("WARN", rel(path), "Frontmatter appears to contain unresolved template placeholders"))

    return findings


def validate_hooks() -> List[Finding]:
    findings: List[Finding] = []
    hooks_root = ROOT / "hooks"
    if not hooks_root.exists():
        return findings

    for d in sorted([p for p in hooks_root.iterdir() if p.is_dir()]):
        readme = d / "README.md"
        hooks_json = d / "hooks.json"

        if not readme.exists():
            findings.append(Finding("ERROR", rel(readme), "Missing README.md"))
        else:
            fm, err = extract_frontmatter(readme)
            if err:
                findings.append(Finding("ERROR", rel(readme), err))
            else:
                if not key_value(fm, "name"):
                    findings.append(Finding("ERROR", rel(readme), "Missing or empty frontmatter 'name'"))
                if not key_value(fm, "description"):
                    findings.append(Finding("ERROR", rel(readme), "Missing or empty frontmatter 'description'"))
                if frontmatter_has_placeholders(fm):
                    findings.append(Finding("WARN", rel(readme), "Frontmatter appears to contain unresolved template placeholders"))

        if not hooks_json.exists():
            findings.append(Finding("ERROR", rel(hooks_json), "Missing hooks.json"))
        else:
            try:
                json.loads(hooks_json.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                findings.append(Finding("ERROR", rel(hooks_json), f"Invalid JSON: {exc}"))

    return findings


def validate_workflows() -> List[Finding]:
    findings: List[Finding] = []
    workflows_dir = ROOT / "workflows"
    if not workflows_dir.exists():
        return findings

    for path in sorted(workflows_dir.glob("*.md")):
        fm, err = extract_frontmatter(path)
        if err:
            findings.append(Finding("ERROR", rel(path), err))
            continue

        if not key_value(fm, "name"):
            findings.append(Finding("ERROR", rel(path), "Missing or empty frontmatter 'name'"))
        if not key_value(fm, "description"):
            findings.append(Finding("ERROR", rel(path), "Missing or empty frontmatter 'description'"))
        if not key_exists(fm, "on"):
            findings.append(Finding("ERROR", rel(path), "Missing frontmatter 'on'"))
        if not key_exists(fm, "permissions"):
            findings.append(Finding("ERROR", rel(path), "Missing frontmatter 'permissions'"))
        if not key_exists(fm, "safe-outputs"):
            findings.append(Finding("WARN", rel(path), "Missing recommended frontmatter 'safe-outputs' for safer Claude Code workflow automation"))
        if frontmatter_has_placeholders(fm):
            findings.append(Finding("WARN", rel(path), "Frontmatter appears to contain unresolved template placeholders"))

    return findings


def print_report(findings: Iterable[Finding], strict: bool) -> int:
    findings = [
        f
        for f in findings
        if not (f.level == "WARN" and (f.path, f.message) in SUPPRESSED_WARNINGS)
    ]
    errors = [f for f in findings if f.level == "ERROR"]
    warnings = [f for f in findings if f.level == "WARN"]

    print("Claude asset validation summary:")
    print(f"- errors: {len(errors)}")
    print(f"- warnings: {len(warnings)}")

    if findings:
        print("\nFindings:")
        level_order = {"ERROR": 0, "WARN": 1}
        for f in sorted(findings, key=lambda x: (level_order.get(x.level, 9), x.path, x.message)):
            print(f"- [{f.level}] {f.path}: {f.message}")

    if not errors:
        print("\n✅ Claude asset validation passed")
        if strict and warnings:
            print("⚠️ Strict mode enabled: warnings are treated as failures")
            return 1
        return 0

    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Claude customization assets and best practices")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures",
    )
    args = parser.parse_args()

    findings: List[Finding] = []
    findings.extend(validate_agents())
    findings.extend(validate_instructions())
    findings.extend(validate_skills())
    findings.extend(validate_hooks())
    findings.extend(validate_workflows())
    return print_report(findings, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
