#!/usr/bin/env bash
# A minimal repo in the shape anantys.review is built for: a base branch and one
# agent-pushed branch on top of it, both committed, working tree clean.
set -euo pipefail

git init -q -b main .
git config user.email eval@example.invalid
git config user.name "Eval Fixture"

printf 'def widgets(items):\n    return len(items)\n' > widgets.py
git add widgets.py
git commit -qm "feat: count widgets"

git checkout -q -b feature/widget-cap
printf 'def widgets(items):\n    return min(len(items), 100)\n' > widgets.py
git commit -qam "feat: cap the widget count at 100"
git checkout -q main
