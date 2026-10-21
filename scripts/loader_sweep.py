#!/usr/bin/env python3
"""Install every open head with the real Claude Code loader and diff what it exposes.

Fourteen checkers in `scripts/` read this plugin as text. `gate_matrix.py` runs
them over every head, which is the right cross-product for *our* rules. None of
it asks the one party whose opinion ships: the loader. A tree that every gate
passes can still install and expose four skills instead of five, and the first
place that shows up is a user's session.

The loader is cheap to ask and needs no credentials. `claude plugin install`
into a sealed `HOME` plus `claude plugin details` takes about a second per head
and answers three questions no text gate can:

  * **Does it install at all?** `claude plugin validate .` resolves `.` to the
    marketplace file and stops, so it passes a tree whose `plugin.json` is gone.
    Installing is the only check that reaches the plugin.
  * **Is every component exposed?** The inventory is the loader's own count. A
    skill whose frontmatter the loader rejects is missing from it, silently —
    there is no error, just a shorter list.
  * **What does it cost?** `details` prices both of the loader's budgets per
    head — the always-on total and each component's on-invoke row — against the
    ceilings `check_cost` enforces. `check_cost` rules on one tree and its merge
    base; this is where those ceilings meet their whole population, and the only
    column in which a fold over `anantys.qa` can be priced at all.

Two findings from the first run are why the report is shaped this way.

`claude agents --json` lists *user* agents only — it returns `[]` with this
plugin installed and both its agents resolvable. A gate built on it would pass
vacuously forever. The surface that does enumerate plugin agents is the failure
message of `claude --agent <unknown>`, which names them plugin-qualified:
`anantys-team-agents:anantys.code-auditor`. That is also the evidence that agent
names are *not* sanitized the way skill names are — dots survive in an agent's
dispatch name, so the skill rename on the queue correctly leaves the two agents
alone.

Drift is reported against `origin/main`, not against an expected list written
here. A list in this file would be one more claim about the product; the
baseline tree is the product.

    python3 scripts/loader_sweep.py                      # every open PR head
    python3 scripts/loader_sweep.py origin/koan/a-head   # just these refs

Exit 1 if any ref fails to install or exposes fewer components than the
baseline. Both are errors with a remedy wholly inside the head's own diff, so
neither forces an order on the queue.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from check_plugins import ALWAYS_ON_MAX, LOADER_ROW, LOADER_TOTAL, ON_INVOKE_MAX, tokens

PLUGIN = "anantys-team-agents"

# `details` prints one `Label (n)  a, b, c` line per component kind.
INVENTORY = re.compile(r"^\s*(Skills|Agents|Hooks|MCP servers|LSP servers)\s*\((\d+)\)\s*(.*)$")
VERSION = re.compile(r"^" + re.escape(PLUGIN) + r"\s+(\S+)")


def run(*args, **kw):
    """Capture a command; never raise — a failing loader call is data."""
    return subprocess.run(args, capture_output=True, text=True, **kw)


def parse_details(text):
    """The loader's own report, as a dict. Absent kinds are absent, not empty.

    Distinguishing "the loader printed Skills (0)" from "the loader never got
    far enough to print a Skills line" is the whole point: the first is a tree
    whose skills were all rejected, the second is an install that died.
    """
    out = {"version": None, "always_on": None, "inventory": {}}
    for line in text.splitlines():
        if out["version"] is None:
            m = VERSION.match(line)
            if m:
                out["version"] = m.group(1)
        m = INVENTORY.match(line)
        if m:
            kind, _count, names = m.groups()
            # The declared count and the printed names can disagree; trust the
            # names, because a name is what a session can actually invoke.
            out["inventory"][kind] = sorted(n for n in (p.strip() for p in names.split(",")) if n)
    if m := LOADER_TOTAL.search(text):
        out["always_on"] = tokens(m.group(1))
    out["on_invoke"] = {c: tokens(oi) for c, _, oi in LOADER_ROW.findall(text)}
    return out


def lost(baseline, head):
    """Components the baseline exposes that this head does not, as `Kind:name`.

    A head is answerable for keeping what `main` already ships. Additions are
    reported but never an error — a branch that adds a sixth skill is doing its
    job, and failing it here would make the gate an argument about scope.
    """
    missing = []
    for kind, names in sorted(baseline.get("inventory", {}).items()):
        have = set(head.get("inventory", {}).get(kind, []))
        missing += [f"{kind}:{n}" for n in names if n not in have]
    return missing


def gained(baseline, head):
    """Components this head exposes that the baseline does not."""
    extra = []
    for kind, names in sorted(head.get("inventory", {}).items()):
        base = set(baseline.get("inventory", {}).get(kind, []))
        extra += [f"{kind}:{n}" for n in names if n not in base]
    return extra


def overspent(baseline, head):
    """Loader budgets this head is over, as `(raised, inherited)` finding lists.

    `check_cost` in `check_plugins.py` enforces these two ceilings against one
    tree and its merge base. Every head in the queue is measured against the
    same `origin/main`, so the sweep is the only place the ceilings meet their
    whole population — and the only place the fold can be priced, which is what
    `ON_INVOKE_MAX`'s own note asks for: twelve heads append to `anantys.qa`,
    each passes alone, and which one is handed the error is decided by merge
    order.

    The split is `crossing`'s, for `crossing`'s reason: a head that is over a
    budget the baseline was already over, without raising it, owns no remedy.
    Reporting that as a failure would force an order on changes that have none.
    """
    raised, inherited = [], []
    rows = [("always-on", head.get("always_on"), baseline.get("always_on"), ALWAYS_ON_MAX)]
    rows += [(c, n, baseline.get("on_invoke", {}).get(c), ON_INVOKE_MAX)
             for c, n in sorted(head.get("on_invoke", {}).items())]
    for what, now, before, limit in rows:
        if now is None or now <= limit:
            continue
        finding = f"{what} {now} > {limit}"
        # A component the baseline never had is this head's own, so `None` must
        # not read as "was under the limit and is over now".
        if before is not None and before > limit and now <= before:
            inherited.append(finding)
        else:
            raised.append(finding + (f" (base {before})" if before is not None else " (new here)"))
    return raised, inherited


def declared_names(tree):
    """Each skill's directory name and the `name:` its frontmatter declares.

    Returns `{directory: declared or None}`. A skill with no `name:` key maps to
    `None`, which is not a finding — see `misnamed`.
    """
    out = {}
    root = Path(tree) / "plugins" / PLUGIN / "skills"
    for skill in sorted(p for p in root.glob("*/SKILL.md")):
        declared, fences = None, 0
        for line in skill.read_text(encoding="utf-8").splitlines():
            if line.rstrip() == "---":
                fences += 1
                if fences == 2:
                    break
                continue
            if fences == 1 and line.startswith("name:"):
                declared = line.split(":", 1)[1].strip()
                break
        out[skill.parent.name] = declared
    return out


def misnamed(declared, exposed):
    """Skills whose frontmatter `name:` is not the name the loader exposes.

    The loader takes a skill's identity from its **directory**. Rewriting
    `name:` in frontmatter changes nothing a session sees: on `origin/main`'s
    tree, replacing all five with hyphens, with garbage, or deleting the key
    outright each leaves `plugin details` reporting the five directory names.

    So a mismatch is never a rename — it is a second, unreachable answer to
    "what is this skill called", and the one a reader believes. The remedy is
    `git mv` on the directory (and the `name:` follows), never the field alone.

    A missing `name:` is not reported here. The field is inert, so its absence
    misleads nobody; whether it is *required* is a question for the validator,
    which is a different claim with a different owner.
    """
    seen = set(exposed)
    return [(d, n) for d, n in sorted(declared.items())
            if n is not None and n != d and d in seen]


def marketplace_name(tree):
    """The marketplace a tree declares, so `install` can name its source."""
    return json.loads((Path(tree) / ".claude-plugin" / "marketplace.json").read_text())["name"]


def export(ref, dest):
    """Materialise ``ref``'s tree at ``dest`` without touching the worktree."""
    archive = Path(dest) / "tree.tar"
    with archive.open("wb") as fh:
        proc = subprocess.run(["git", "archive", "--format=tar", ref],
                              stdout=fh, stderr=subprocess.DEVNULL)
    if proc.returncode != 0:
        return None
    tree = Path(dest) / "tree"
    tree.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(tree)
    archive.unlink()
    return tree


def inventory(ref):
    """Install ``ref`` in a throwaway HOME and return the loader's report.

    On any failure the loader's own stderr is carried through as ``error``.
    Paraphrasing it would lose the only diagnostic the operator gets.
    """
    with tempfile.TemporaryDirectory(prefix="loader-sweep-") as scratch:
        tree = export(ref, scratch)
        if tree is None:
            return {"error": f"git archive failed for {ref}"}
        home = Path(scratch) / "home"
        home.mkdir()
        env = {"HOME": str(home), "PATH": os.environ["PATH"]}
        try:
            source = marketplace_name(tree)
        except (OSError, ValueError, KeyError) as exc:
            return {"error": f"unreadable marketplace.json: {exc}"}
        add = run("claude", "plugin", "marketplace", "add", str(tree), env=env)
        if add.returncode != 0:
            return {"error": "marketplace add: " + (add.stderr or add.stdout).strip()}
        install = run("claude", "plugin", "install", f"{PLUGIN}@{source}", env=env)
        if install.returncode != 0:
            return {"error": "install: " + (install.stderr or install.stdout).strip()}
        details = run("claude", "plugin", "details", PLUGIN, env=env)
        if details.returncode != 0:
            return {"error": "details: " + (details.stderr or details.stdout).strip()}
        report = parse_details(details.stdout)
        if not report["inventory"]:
            return {"error": "details printed no component inventory"}
        # Read the tree while it still exists, and compare it to what the
        # loader just said about that same tree.
        report["misnamed"] = misnamed(declared_names(tree),
                                      report["inventory"].get("Skills", []))
        return report


def open_heads():
    """The open PR heads, as `(number, ref)` — the queue the loader never sees."""
    proc = run("gh", "pr", "list", "--state", "open", "--limit", "200",
               "--json", "number,headRefName")
    if proc.returncode != 0:
        return []
    rows = json.loads(proc.stdout)
    return [(r["number"], "origin/" + r["headRefName"]) for r in rows]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("refs", nargs="*", help="refs to sweep (default: every open PR head)")
    parser.add_argument("--baseline", default="origin/main")
    args = parser.parse_args(argv)

    base = inventory(args.baseline)
    if "error" in base:
        print(f"baseline {args.baseline} does not install: {base['error']}")
        return 1
    kinds = {k: v for k, v in base["inventory"].items() if v}
    print(f"baseline {args.baseline}: v{base['version']}, ~{base['always_on']} tok always-on")
    for kind, names in sorted(kinds.items()):
        print(f"  {kind} ({len(names)}): {', '.join(names)}")
    for directory, declared in base["misnamed"]:
        print(f"  baseline name drift: {directory}/ declares `name: {declared}`")

    targets = [(None, r) for r in args.refs] or open_heads()
    if not targets:
        print("\nno refs to sweep")
        return 0

    failures = []
    print(f"\n{'ref':52} {'ver':7} {'Δtok':>9}  drift")
    for number, ref in targets:
        label = (f"#{number} " if number else "") + ref.replace("origin/koan/", "…/")
        head = inventory(ref)
        if "error" in head:
            print(f"{label:52} {'—':7} {'—':>9}  INSTALL FAILED: {head['error'][:60]}")
            failures.append((label, head["error"]))
            continue
        missing, extra = lost(base, head), gained(base, head)
        raised, inherited = overspent(base, head)
        notes = (["LOST " + ", ".join(missing)] if missing else []) + \
                (["added " + ", ".join(extra)] if extra else []) + \
                ([f"NAME IGNORED x{len(head['misnamed'])}"] if head["misnamed"] else []) + \
                (["OVER " + ", ".join(raised)] if raised else []) + \
                (["inherits " + ", ".join(inherited)] if inherited else [])
        # Both counts are optional: a table this script cannot read leaves `None`,
        # and subtracting it is how the sweep used to die on the heads it exists for.
        cost = f"{head['always_on'] - base['always_on']:+d}" \
            if None not in (head["always_on"], base["always_on"]) else "?"
        print(f"{label:52} {head['version'] or '?':7} {cost:>9}  "
              f"{'; '.join(notes) or 'same inventory'}")
        if missing:
            failures.append((label, "exposes fewer components: " + ", ".join(missing)))
        for finding in raised:
            failures.append((label, f"over a loader budget this head raised: {finding}"))
        for directory, declared in head["misnamed"]:
            failures.append((label, f"{directory}/ declares `name: {declared}`; the loader "
                                    f"exposes `{directory}` and discards the field"))

    print(f"\n{len(targets)} ref(s), {len(failures)} error(s)")
    for label, why in failures:
        print(f"  {label}: {why}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
