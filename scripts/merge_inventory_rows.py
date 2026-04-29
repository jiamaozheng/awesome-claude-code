#!/usr/bin/env python3
"""Append new rows from a candidate CSV into the main migration-inventory.csv.

Only rows whose (type, source) combination does not already exist are appended.
Exits with code 0 if rows were added, 2 if no rows to add (so CI can skip opening a PR).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge new inventory rows into main inventory")
    parser.add_argument("--new-rows", required=True, help="CSV file with candidate new rows")
    parser.add_argument("--inventory", default="docs/migration-inventory.csv", help="Main inventory to update")
    args = parser.parse_args()

    new_rows_path = Path(args.new_rows)
    inventory_path = Path(args.inventory)

    if not new_rows_path.exists():
        print(f"ERROR: new-rows file not found: {new_rows_path}", file=sys.stderr)
        return 1
    if not inventory_path.exists():
        print(f"ERROR: inventory not found: {inventory_path}", file=sys.stderr)
        return 1

    # Load existing keys
    existing_keys: set[tuple[str, str]] = set()
    existing_rows: list[dict[str, str]] = []
    with inventory_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing_rows.append(row)
            existing_keys.add((row["type"], row["source"]))

    # Load candidates
    with new_rows_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        candidates = list(reader)

    added: list[dict[str, str]] = []
    for row in candidates:
        key = (row["type"], row["source"])
        if key not in existing_keys:
            added.append(row)
            existing_keys.add(key)

    if not added:
        print("No new rows to add.")
        return 2  # signal: nothing changed, skip PR

    # Append to inventory
    with inventory_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "source", "target"])
        writer.writerows(added)

    print(f"Added {len(added)} new row(s) to {inventory_path}:")
    for row in added:
        print(f"  {row['type']}: {row['source']} -> {row['target']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
