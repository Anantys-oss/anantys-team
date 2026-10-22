#!/usr/bin/env python3
"""Forbid depth-dependent links in skill templates.

A template under `skills/<skill>/templates/` is copied into a directory whose depth
the skill cannot know: `anantys.qa plan` writes `qa-plan.md` into a spec-kit dir
(`specs_dir` is operator-configurable) or into `.anantys/qa/<slug>/`, one level
deeper. Any relative link containing a `..` segment therefore resolves differently
per layout, so at most one layout gets a live link and the rest get a dead one.

The invariant: a relative link in a template may address the directory the template
lands in, and nothing above it. Paths outside it are written from the repo root as
plain code spans.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = "plugins/*/skills/*/templates/*.md"

# Inline links and reference definitions; bare autolinks cannot be relative.
LINK = re.compile(r"\]\(\s*<?([^)>\s]+)")


def escaping_links(text: str) -> list[tuple[int, str]]:
    """Relative link targets that climb above the template's own directory."""
    found = []
    for match in LINK.finditer(text):
        target = match.group(1)
        if "://" in target or target.startswith(("#", "/", "mailto:")):
            continue
        if ".." in target.split("/"):
            found.append((text.count("\n", 0, match.start()) + 1, target))
    return found


def main() -> int:
    templates = sorted(ROOT.glob(TEMPLATES))
    if not templates:
        print(f"check_template_paths: no templates matched {TEMPLATES}")
        return 1
    failures = 0
    for path in templates:
        for line, target in escaping_links(path.read_text(encoding="utf-8")):
            print(
                f"{path.relative_to(ROOT)}:{line}: link `{target}` climbs out of the "
                f"feature directory; write the path from the repo root as a code span"
            )
            failures += 1
    print(f"check_template_paths: {len(templates)} templates, {failures} escaping link(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
