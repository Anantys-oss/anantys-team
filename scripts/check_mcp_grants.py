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

**Asking the provider means asking it for every page.** `tools/list` is paginated:
the reply carries `nextCursor` when more tools follow, and the server picks the
page size. A probe that read the first page and stopped would not report less — it
would report the tools on page two as tools the server *does not advertise*, which
is an error, on a role file, telling its owner to delete a grant that works. The
`update_plan` case above is what that message looks like when it is true; nothing
in the output tells the two apart. So `probe` follows the cursor, and any exchange
it cannot finish — an unanswered page, a cursor the server never clears — comes
back unprobed, in the same column as a server that would not launch.

**A grant may name no tool at all.** The loader's rule ends in an optional
segment — `mcp__<server>__*` and bare `mcp__<server>` both grant the whole
server — and `check_platform.py` states both forms as the remedy it hands
authors: collapse an enumeration into `__*`, and disambiguate a one-segment
grant by writing `__*`. Read as a tool name, `*` is advertised by no server, so
the gate charged that remedy to the role file as `does not advertise`, in the
same words as the `update_plan` finding above and with the same instruction to
delete it. The bare form missed the regex entirely, which left its server out of
every role's tally and produced a `no role grants it` warning about a server one
role grants in full. Both forms are now the server half of a grant and nothing
else; the tool half of a whole-server grant is the server's whole list, which
this gate has no finding about.

Errors that predate this gate are declared in `mcp-grants-baseline.txt` rather
than fixed here — a gate may not fix its own subject, or it forces an order on
changes that have none.

Usage: python3 scripts/check_mcp_grants.py [root]
Exit 1 on undeclared errors, 0 on warnings and declared ones.
"""

import json
import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path

BASELINE = Path(__file__).with_name("mcp-grants-baseline.txt")

#: Pages of `tools/list` this gate will follow before calling the server unprobed.
#: A server that never clears its cursor would otherwise be read until the
#: deadline; no real server needs ten pages to name its tools.
MAX_PAGES = 10

#: `mcp__<server>` or `mcp__<server>__<tool>`. Deliberately looser than
#: `check_platform.py`'s `TOOL_SHAPE`: a malformed identifier is that gate's
#: finding, and re-reporting it here would give one edit two diagnoses. What this
#: needs from the string is only its segments, so it splits on the first `__`
#: pair and takes the rest as the tool — `mcp__a__b__c` yields server `a`, tool
#: `b__c`, which no server lists, which is the right answer for it.
#:
#: The tool half is optional because the loader's rule makes it optional: a
#: single segment after `mcp__` is a whole-server grant. Requiring it meant the
#: server segment of such a grant was never read, so the server went into no
#: role's tally and the manifest got a `no role grants it` warning naming a
#: server a role does grant, in whole.
GRANT = re.compile(r"^mcp__([^_].*?)(?:__(.+))?$")

#: The two tool segments that mean *every tool this server lists*, per the
#: loader's `^mcp__[\w-]+(?:__(?:[\w.-]+|\*))?$`: the literal `*`, and no segment
#: at all. Neither is a tool name, so neither may be looked up in a `tools/list`
#: answer — `*` is not advertised by any server that advertises anything.
WHOLE_SERVER = (None, "*")

#: How the loader exposes a server declared in `plugin.json`, measured on CLI
#: 2.1.278: the manifest's `claude-in-chrome` under plugin `anantys-team-agents`
#: is granted as `mcp__plugin_anantys-team-agents_claude-in-chrome__computer`.
#: `claude mcp list` prints the same server with colons
#: (`plugin:anantys-team-agents:claude-in-chrome`) — a different rendering of one
#: name, and not the one a grant is written in.
def exposed(plugin: str, server: str) -> str:
    return f"plugin_{plugin}_{server}"


def send(proc, message: dict) -> None:
    """One JSON-RPC message, line-delimited. Silent if the server is already gone.

    A write that fails needs no branch of its own: the only consequence is a reply
    that never arrives, which ``result`` already reports as unprobed.
    """
    try:
        proc.stdin.write((json.dumps(message) + "\n").encode())
        proc.stdin.flush()
    except OSError:
        pass


def replies(stdout, deadline: float):
    """Every JSON message the server writes, until the deadline or EOF.

    Reads *bytes* and splits them here rather than calling ``readline``: one
    ``readline`` on a buffered stream can pull two replies into the stream's own
    buffer, after which ``select`` on the file descriptor blocks for the full
    deadline with the second reply already in hand. That is not a theoretical
    ordering — a server that answers `initialize` and `tools/list` back to back
    writes both into one chunk, which is the common case.
    """
    pending = b""
    while True:
        while b"\n" in pending:
            line, _, pending = pending.partition(b"\n")
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
        if (left := deadline - time.monotonic()) <= 0:
            return
        if not select.select([stdout], [], [], left)[0]:
            return
        if not (chunk := os.read(stdout.fileno(), 65536)):
            return
        pending += chunk


def result(stream, want: int) -> dict | None:
    """The ``result`` of request ``want``, or ``None`` if it never arrives.

    Skips anything that is not that reply — a server is free to emit notifications
    in between, and a probe that assumed the next message was its answer would
    report a server with no tools, which is the one wrong answer that reads as a
    finding. An error reply has no ``result`` and so is unprobed too.
    """
    for msg in stream:
        if msg.get("id") == want:
            return msg.get("result")
    return None


def probe(spec: dict, timeout: float = 20.0) -> set[str] | None:
    """The tool names a server advertises, or ``None`` if it could not be asked.

    One stdio session: `initialize`, the `initialized` notification, then
    `tools/list` until the server stops handing back a cursor.

    **The cursor is not optional.** `tools/list` is a paginated method: the reply
    carries `nextCursor` when more tools follow, and the *server* chooses the page
    size. Reading the first page as the whole list is not a partial measurement —
    it is a false `does not advertise` **error**, charged to a role file, whose
    stated remedy is to delete a grant that works. `update_plan` is this gate's own
    worked example of a real finding; against a server that paginates before it,
    the same code produces that identical message about a tool the server *does*
    list, and nothing in the output distinguishes the two. Reply-matching above
    closed one route to "a server with no tools"; this was the other, and it is the
    one a server reaches by following the spec.

    ``None`` whenever the exchange does not complete — a handshake that is never
    answered, a page that never arrives, a cursor the server never clears. A gate
    that cannot finish measuring must not rule on half an answer, which is the
    whole reason an unprobed server is a warning and not an error.

    The three opening messages are still written without waiting on the
    `initialize` reply, so a lenient server that answers only `tools/list` is read
    exactly as before; the deadline bounds every read after that.
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
            env={**os.environ, **(spec.get("env") or {})},
        )
    except OSError:
        return None
    deadline = time.monotonic() + timeout
    try:
        hello = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "check_mcp_grants", "version": "1"},
        }
        send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": hello})
        send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        stream = replies(proc.stdout, deadline)
        tools: set[str] = set()
        for page in range(2, 2 + MAX_PAGES):
            if page > 2:
                send(proc, {"jsonrpc": "2.0", "id": page, "method": "tools/list",
                            "params": {"cursor": cursor}})
            if (answer := result(stream, page)) is None:
                return None
            tools |= {t["name"] for t in answer.get("tools") or [] if "name" in t}
            if not (cursor := answer.get("nextCursor")):
                return tools
        return None  # still paginating at MAX_PAGES — unprobed, not an empty server
    except OSError:
        return None
    finally:
        if proc.poll() is None:
            proc.kill()


def check(plugin, servers, roles, advertised, manifest):
    """Errors and warnings for one plugin.

    ``servers`` maps a declared server name to its launch spec, ``roles`` is
    ``(path, grants)`` pairs, and ``advertised`` maps a declared server name to
    the tool names it lists or to ``None`` when it could not be asked. Pure, so
    the tests inject all four rather than installing a plugin.

    ``manifest`` is the path the manifest-charged errors are reported at, and it
    is passed rather than derived. It used to be `f"plugins/{plugin}/..."`, built
    from the plugin's *name* — two different claims spliced into one string. For
    the one plugin in this tree the two coincide, so the synthesis was invisible;
    for a plugin the catalog sources from anywhere else it names a file that does
    not exist, and `baseline()` matches declared errors by that exact string, so
    no baseline line could ever name the real file either. A reported path is an
    answer about the tree, never a guess from a name.
    """
    errors: list[tuple[str, str]] = []
    warnings: list[tuple[str, str]] = []
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
            if tool in WHOLE_SERVER:
                # Every tool the server lists, so there is no name to look up.
                # `check_platform.py` tells authors to write exactly this — it
                # fails a seven-tool enumeration into `mcp__<server>__*` and
                # resolves the one-segment ambiguity with "write `…__*` for the
                # server". Looked up as a tool name, `*` came back as
                # `does not advertise` on the role file, in the same words as a
                # true finding, telling its owner to delete a grant that holds
                # the whole server.
                continue
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
    # Every plugin in the tree, at whatever depth. `plugins/*/` was not the tree's
    # rule for where a plugin lives — `marketplace.json`'s `source` is, and it is a
    # free-form relative path. `check_plugins` reads the catalog and so already
    # walks `**`: a plugin at `vendor/extra` is listed there, installable, and
    # validated. To this file it did not exist, so its granted-but-unprovided MCP
    # servers went unreported while CI stayed green — the same error this gate's own
    # baseline declares for the one plugin it could see. `**` skips hidden
    # directories, so `.git` is not in the sweep, and over-inclusion is the loud
    # direction: a non-plugin manifest gets read and complained about.
    manifests = sorted(root.glob("**/.claude-plugin/plugin.json"))
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
        errors, warnings = check(
            plugin, servers, roles, advertised, str(manifest.relative_to(root))
        )
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
