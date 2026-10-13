#!/usr/bin/env python3
"""Check that an `mcp__…` grant names a server this plugin provides and a tool that server lists.

`check_platform.py` holds the *shape* of a tool identifier: `mcp__server__tool`,
with the plugin-namespaced form `mcp__plugin_<plugin>_<server>__<tool>` accepted
because the loader builds that prefix and the author does not choose it. A
well-shaped identifier is still only a claim. Two ways it comes out false, and
both have shipped here:

  * **The server has no provider.** Three roles grant 24 browser tools under
    `mcp__claude-in-chrome__…`; `plugin.json` declares no `mcpServers`. On a bare
    install the names resolve to nothing, and `anantys.debug`'s own hard
    precondition — call `tabs_context_mcp` first, STOP if the browser tools are
    not available — fires on every invocation. Nothing in `scripts/` read the
    field, so nothing could say so.
  * **The tool does not exist.** `anantys.ops` granted
    `mcp__claude-in-chrome__update_plan` for nineteen days. The Claude-in-Chrome
    server advertises 22 tools and `update_plan` is not one of them. The grant is
    well-shaped, the prose exercises it, and both existing grant gates pass it:
    one compares prose to grants, the other compares the grant to a regex.

So this gate asks the provider. It reads the declared `mcpServers`, launches each
one, speaks MCP over stdio (`initialize`, then `tools/list`), and checks every
grant against the answer.

**Where each error is charged.** A grant that names an undeclared server is not a
defect of the role that holds it when *no* server is declared at all: twenty-four
role-file errors would name twenty-four remedies for one missing manifest field.
That case is charged once, to the manifest. Once the field exists, a grant whose
server segment does not resolve is the role's own — the remedy is inside its
frontmatter — and so is a tool name the server does not list.

**A server that will not launch is a warning, not an error.** The remedy is not in
any diff: CI may have no `claude` on PATH, and a browser extension's server
answers `tools/list` whether or not a browser is attached, but a different server
might not run at all. An unprobed server's tool names go unverified and the gate
says which, in the pattern `check_platform.py` set for the loader it also cannot
always run.

Errors that predate this gate are declared in `mcp-grants-baseline.txt` rather
than fixed here — a gate may not fix its own subject, or it forces an order on
changes that have none.

Usage: python3 scripts/check_mcp_grants.py [root]
Exit 1 on undeclared errors, 0 on warnings and declared ones.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

BASELINE = Path(__file__).with_name("mcp-grants-baseline.txt")

#: `mcp__<server>__<tool>`. Deliberately looser than `check_platform.py`'s
#: `TOOL_SHAPE`: a malformed identifier is that gate's finding, and re-reporting
#: it here would give one edit two diagnoses. What this needs from the string is
#: only its two segments, so it splits on the first `__` pair and takes the rest
#: as the tool — `mcp__a__b__c` yields server `a`, tool `b__c`, which no server
#: lists, which is the right answer for it.
GRANT = re.compile(r"^mcp__([^_].*?)__(.+)$")

#: How the loader exposes a server declared in `plugin.json`, measured on CLI
#: 2.1.278: the manifest's `claude-in-chrome` under plugin `anantys-team-agents`
#: is granted as `mcp__plugin_anantys-team-agents_claude-in-chrome__computer`.
#: `claude mcp list` prints the same server with colons
#: (`plugin:anantys-team-agents:claude-in-chrome`) — a different rendering of one
#: name, and not the one a grant is written in.
def exposed(plugin: str, server: str) -> str:
    return f"plugin_{plugin}_{server}"


def probe(spec: dict, timeout: float = 20.0) -> set[str] | None:
    """The tool names a server advertises, or ``None`` if it could not be asked.

    One stdio session: `initialize`, the `initialized` notification, `tools/list`.
    Reads line-delimited JSON and skips anything that is not the reply to the
    request it sent — a server is free to emit notifications in between, and a
    probe that assumed the next line was its answer would report a server with no
    tools, which is the one wrong answer that reads as a finding.
    """
    cmd = [spec.get("command", "")] + list(spec.get("args") or [])
    if not cmd[0]:
        return None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env={**os.environ, **(spec.get("env") or {})},
        )
    except OSError:
        return None
    try:
        hello = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "check_mcp_grants", "version": "1"},
        }
        out, _ = proc.communicate(
            "\n".join(
                json.dumps(m)
                for m in (
                    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": hello},
                    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                )
            )
            + "\n",
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        proc.kill()
        return None
    finally:
        if proc.poll() is None:
            proc.kill()
    for line in out.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == 2 and "result" in msg:
            return {t["name"] for t in msg["result"].get("tools") or [] if "name" in t}
    return None


def check(plugin, servers, roles, advertised):
    """Errors and warnings for one plugin.

    ``servers`` maps a declared server name to its launch spec, ``roles`` is
    ``(path, grants)`` pairs, and ``advertised`` maps a declared server name to
    the tool names it lists or to ``None`` when it could not be asked. Pure, so
    the tests inject all three rather than installing a plugin.
    """
    errors: list[tuple[str, str]] = []
    warnings: list[tuple[str, str]] = []
    manifest = f"plugins/{plugin}/.claude-plugin/plugin.json"
    # server name -> the grant prefix a role must write it as
    prefixes = {exposed(plugin, s): s for s in servers}
    named: set[str] = set()

    for path, grants in roles:
        for grant in grants:
            m = GRANT.match(grant)
            if not m:
                continue
            segment, tool = m.groups()
            if not servers:
                # Charged to the manifest below, once. The role is not wrong to
                # want a browser; the plugin is wrong not to ship one.
                named.add(segment)
                continue
            server = prefixes.get(segment)
            if server is None:
                if segment in servers:
                    errors.append(
                        (
                            path,
                            f"`{grant}` names the server as `{segment}`, but a server declared "
                            f"in `plugin.json` is exposed as `{exposed(plugin, segment)}` — the "
                            f"loader builds that prefix, so the bare name is some other "
                            f"server the session may or may not hold",
                        )
                    )
                else:
                    errors.append(
                        (
                            path,
                            f"`{grant}` depends on an MCP server `{segment}` that "
                            f"`plugin.json` does not declare; it provides "
                            f"{', '.join(sorted(prefixes)) or 'none'}",
                        )
                    )
                continue
            named.add(server)
            tools = advertised.get(server)
            if tools is not None and tool not in tools:
                errors.append(
                    (
                        path,
                        f"`{grant}` names the tool `{tool}`, which `{server}` does not "
                        f"advertise; it lists {len(tools)}: {', '.join(sorted(tools))}",
                    )
                )

    if named and not servers:
        errors.append(
            (
                manifest,
                f"declares no `mcpServers`, so {len(named)} granted server "
                f"({', '.join(sorted(named))}) has no provider on a bare install — every "
                f"grant to it resolves to nothing, and a role whose precondition is a call "
                f"to one of those tools stops on every invocation",
            )
        )

    for server in sorted(set(servers) - named):
        warnings.append(
            (
                manifest,
                f"declares the MCP server `{server}` that no role grants — its tools are "
                f"connected and unaudited in every session the plugin is enabled",
            )
        )
    for server in sorted(s for s in servers if advertised.get(s) is None):
        warnings.append(
            (
                manifest,
                f"`{server}` could not be asked for its tool list, so the tool half of every "
                f"grant to it went unverified",
            )
        )
    return errors, warnings


def grants_of(path: Path) -> list[str]:
    """The last-declared `allowed-tools:`/`tools:` value of a role file, as tokens.

    Last, not first: YAML resolves a repeated key to its final occurrence.
    Split on commas and line breaks only — a scoped grant holds a space
    (`Bash(git diff:*)`) and is one token. A file with no readable frontmatter
    yields nothing; `check_platform.py` owns that error.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return []
    block, sep, _ = text[4:].partition("\n---\n")
    if not sep:
        return []
    found = re.findall(r"^(?:allowed-tools|tools):(.*(?:\n[ \t]+.*)*)$", block, re.MULTILINE)
    if not found:
        return []
    raw = found[-1].strip().strip("[]")
    return [t.strip().strip("\"'- ") for t in re.split(r"[,\n]", raw) if t.strip(" -\"'")]


def baseline() -> set[str]:
    """Errors this gate was introduced alongside, and so may not fail on.

    Same contract as `tool-grants-baseline.txt`: one `<path>: <message>` per
    line, and a declared error that no longer occurs is a warning — the fix
    landing must not turn this gate red in its turn.
    """
    if not BASELINE.is_file():
        return set()
    lines = BASELINE.read_text(encoding="utf-8").splitlines()
    return {s for s in (line.strip() for line in lines) if s and not s.startswith("#")}


def main(root: Path) -> int:
    manifests = sorted(root.glob("plugins/*/.claude-plugin/plugin.json"))
    if not manifests:
        print(f"no plugin manifests found under {root}", file=sys.stderr)
        return 1

    declared, matched = baseline(), set()
    failed = False
    for manifest in manifests:
        plugin_dir = manifest.parent.parent
        plugin = plugin_dir.name
        try:
            servers = json.loads(manifest.read_text(encoding="utf-8")).get("mcpServers") or {}
        except json.JSONDecodeError as exc:
            print(f"ERROR {manifest.relative_to(root)}: unreadable manifest ({exc})")
            failed = True
            continue
        roles = [
            (str(p.relative_to(root)), grants_of(p))
            for p in sorted(plugin_dir.glob("skills/*/SKILL.md")) + sorted(
                plugin_dir.glob("agents/*.md")
            )
        ]
        advertised = {name: probe(spec) for name, spec in servers.items()}
        errors, warnings = check(plugin, servers, roles, advertised)
        for path, message in errors:
            entry = f"{path}: {message}"
            if entry in declared:
                matched.add(entry)
                print(f"BASE  {entry} (declared in {BASELINE.name})")
            else:
                print(f"ERROR {entry}")
                failed = True
        for path, message in warnings:
            print(f"WARN  {path}: {message}")

    for stale in sorted(declared - matched):
        print(f"WARN  fixed, so delete from {BASELINE.name}: {stale}")

    print("mcp-grant check: FAILED" if failed else "mcp-grant check: OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
