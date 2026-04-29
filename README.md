# Awesome Claude Code

A community-driven collection of Claude Code customizations — instructions, agents, skills, hooks, workflows, and plugins — migrated from [github/awesome-copilot](https://github.com/github/awesome-copilot).

## What's included

| Folder | Contents |
|---|---|
| `instructions/` | Path-aware coding guidance (`.md` files) |
| `agents/` | Custom Claude subagents |
| `skills/` | Reusable skill workflows |
| `hooks/` | Hook definitions and scripts |
| `workflows/` | Agentic workflow files |
| `plugins/` | Plugin packages and external catalog |
| `docs/` | `migration-inventory.csv` — source-of-truth mapping |
| `scripts/` | Validation and sync automation |
| `CLAUDE.md` | Always-on project guidance |
| `settings.json` | Shared project settings |
| `.mcp.json` | MCP server definitions (optional) |

## Getting started

1. Clone this repo and open it in Claude Code.
2. Claude automatically picks up `CLAUDE.md`, `instructions/`, `agents/`, and `skills/`.
3. Run `python3 scripts/validate_claude_assets.py --strict` to verify everything is valid.

## Upstream sync

This repository tracks [github/awesome-copilot](https://github.com/github/awesome-copilot) daily via GitHub Actions.

**Automated (daily):**
- `.github/workflows/sync-awesome-copilot.yml` clones upstream, syncs mapped files, runs validators, and opens a PR.
- If new upstream files are detected that aren't in the inventory, a second PR is opened automatically on `chore/inventory-update`.

**Manual:**
```bash
git clone --depth 1 https://github.com/github/awesome-copilot.git .upstream/awesome-copilot-main
python3 scripts/sync_from_awesome.py --source-root .upstream/awesome-copilot-main --dry-run
```

The sync is driven by `docs/migration-inventory.csv` (780 rows, relative paths). New upstream files are detected automatically and proposed via PR — no manual CSV editing needed.

## Validation

```bash
# Full validation suite
python3 scripts/validate_migration.py
python3 scripts/validate_claude_assets.py --strict
python3 scripts/validate_plugins.py
```

All three run automatically in CI on every PR and push (`.github/workflows/validate-migration.yml`).

## Pre-commit hooks

```bash
# Quick setup
bash scripts/setup_dev.sh

# Or manually
python3 -m pip install pre-commit
pre-commit install
```

Hooks run all three validators before each commit (configured in `.pre-commit-config.yaml`).

## Website

A website is available at `website/`.

```bash
cd website
npm install
npm run dev   # local dev server
npm run build # production build
```

## Contributing

Contributions are welcome. To add a new agent, instruction, skill, hook, workflow, or plugin:

1. Add the file to the appropriate directory following the naming convention (lowercase, hyphen-separated).
2. Ensure markdown files have valid frontmatter (`description`, `name`, etc.).
3. Run `python3 scripts/validate_claude_assets.py --strict` — it must pass with 0 errors and 0 warnings.
4. Open a PR targeting `main`.


