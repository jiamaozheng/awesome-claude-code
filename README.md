# Awesome Claude Code

A community-driven collection of Claude Code customizations — instructions, agents, skills, hooks, workflows, and plugins.

## What is included

- `CLAUDE.md`: always-on project guidance
- `settings.json`: shared project settings
- `instructions/`: path-aware guidance files
- `skills/`: reusable skill workflows
- `agents/`: custom subagents
- `hooks/`: migrated hook definitions and scripts
- `workflows/`: migrated agentic workflow files
- `plugins/`: migrated plugin packages
- `.mcp.json`: MCP server definitions (optional)

## Quick start

1. Open this folder in your terminal.
2. Start Claude Code in this repository.
3. Run `/memory` to verify loaded instruction files.
4. Run `/agents` to see the project subagent.
5. Run `/review-pr` to test the sample skill.

## Suggested first edits

- Update `CLAUDE.md` with your team conventions.
- Tighten permissions in `settings.json`.
- Add project-specific rules in `instructions/`.
- Add your own skills under `skills/`.
- Add additional subagents under `agents/`.

## Copilot to Claude migration pack

Use the migration pack in `migration-pack/` to port existing GitHub Copilot customization into Claude Code:

- `migration-pack/playbook.md`
- `migration-pack/mapping-reference.md`
- `migration-pack/checklist.md`
- `migration-pack/templates/`

## Full migration status

This starter now includes a full one-by-one migration from:

- `/Users/jiamaozheng/Downloads/awesome-copilot-main`

Migrated artifacts are available in:

- `instructions/`
- `agents/`
- `skills/`
- `hooks/`
- `workflows/`
- `plugins/`

Validation artifacts:

- `docs/claude-migration-notes.md`
- `docs/migration-inventory.csv`

## Upstream Sync (awesome-copilot)

To keep this repository aligned with daily updates from `github/awesome-copilot`:

1. Scheduled automation:
	- `.github/workflows/sync-awesome-copilot.yml` runs daily and opens/updates a PR with upstream changes.
2. Manual sync (local):
	- `git clone --depth 1 https://github.com/github/awesome-copilot.git .upstream/awesome-copilot-main`
	- `python3 scripts/sync_from_awesome.py --source-root .upstream/awesome-copilot-main`
3. Drift visibility:
	- The sync script reports `potential unmapped upstream files` so newly added artifacts in upstream are visible and can be added to `docs/migration-inventory.csv`.
4. Validate before merge:
	- `python3 scripts/validate_migration.py`
	- `python3 scripts/validate_claude_assets.py --strict`
	- `python3 scripts/validate_plugins.py`

The sync process uses `docs/migration-inventory.csv` as the source-to-target mapping contract.

## Notes

- Keep `CLAUDE.md` concise.
- Use rules for path-specific behavior.
- Use skills for task playbooks.
- Use subagents for focused, isolated work.

## Plugin Compliance Guardrail

To prevent future plugin migration drift or manifest issues:

1. Run `python3 scripts/validate_plugins.py` locally before committing plugin changes.
2. Ensure `docs/migration-inventory.csv` includes plugin rows for each `plugin.json` plus `plugins/external.json`.
3. CI runs `.github/workflows/validate-plugins.yml` on PRs and pushes that touch plugin or inventory files.

## Full Migration Guardrail

To prevent migration issues across all GitHub Copilot customization artifacts:

1. Run `python3 scripts/validate_migration.py` locally before committing migration changes.
2. Keep `docs/migration-inventory.csv` synchronized with all migrated targets in:
	- `instructions/`
	- `agents/`
	- `skills/`
	- `hooks/`
	- `workflows/`
	- `plugins/`
3. CI runs `.github/workflows/validate-migration.yml` on PRs and pushes that touch migration artifacts or inventory.

Additional best-practice validation is enforced by:

- `python3 scripts/validate_claude_assets.py` (frontmatter, naming, and required fields for agents/instructions/skills/hooks/workflows)

Use strict mode to fail on warnings as well:

- `python3 scripts/validate_claude_assets.py --strict`

## Local Pre-commit Guardrail

To run migration checks automatically before each commit:

Quick bootstrap (recommended):

1. `bash scripts/setup_dev.sh`

Manual setup:

1. Install pre-commit: `python3 -m pip install pre-commit`
2. Install hooks in this repository: `pre-commit install`
3. (Optional) Run all hooks immediately: `pre-commit run --all-files`

Configured hooks are defined in `.pre-commit-config.yaml` and run:

- `python3 scripts/validate_migration.py`
- `python3 scripts/validate_claude_assets.py`
- `python3 scripts/validate_plugins.py`

## Website

This repository now includes a website (modeled after the original awesome-copilot site) at `website/`.

Run locally:

1. `cd website`
2. `npm install`
3. `npm run dev`

Build for production:

1. `cd website`
2. `npm run build`
