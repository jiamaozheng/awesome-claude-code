#!/usr/bin/env bash
set -euo pipefail

# Bootstrap local developer tooling for migration guardrails.
# - Installs pre-commit if missing
# - Installs git hooks
# - Runs all hooks once for baseline validation

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but was not found in PATH."
  exit 1
fi

if ! command -v pre-commit >/dev/null 2>&1; then
  echo "Installing pre-commit..."
  python3 -m pip install --user pre-commit
  # Ensure user-level Python bin is discoverable in current shell when possible.
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v pre-commit >/dev/null 2>&1; then
  echo "Error: pre-commit installation completed but command still not found."
  echo "Try adding your user Python bin to PATH, then re-run this script."
  exit 1
fi

echo "Installing git pre-commit hooks..."
pre-commit install

echo "Running all pre-commit hooks for baseline validation..."
pre-commit run --all-files

echo "✅ Development guardrails are configured."
