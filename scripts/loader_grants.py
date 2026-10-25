"""The one tokenization of `allowed-tools:`/`tools:` the loader performs.

Four gates in this tree read that field and three of them say, in a comment,
that it is split on commas and line breaks only — `check_platform` spells out
the reasoning: "a scoped grant is one token even when it holds a space
(`Bash(git diff:*)`). Splitting on whitespace instead is how a grant checker
comes to reject every narrowed grant it was written to encourage."

The concern is real and the rule drawn from it is wrong. Claude Code 2.1.278
tokenizes the field with this, verbatim from the shipped binary:

    function Rp(e){if(e.length===0)return[];let n=[];for(let t of e){
      if(!t)continue;let r="",s=!1;for(let o of t)switch(o){
      case"(":s=!0,r+=o;break;
      case")":s=!1,r+=o;break;
      case",":if(s)r+=o;else{if(r.trim())n.push(r.trim());r=""}break;
      case" ":if(s)r+=o;else if(r.trim())n.push(r.trim()),r="";break;
      default:r+=o}if(r.trim())n.push(r.trim())}return n}

A space *is* a separator, exactly as much as a comma. What protects a scoped
grant is not the absence of space-splitting but `s`: the `(` suspends both
separators until `)`. So the loader-faithful rule keeps every narrowed grant
and still ends a token at the space outside the parentheses.

The gap this closes is not cosmetic. One missing comma —

    allowed-tools: Read, Bash (git log:*), Grep

— loads as `Read`, **bare `Bash`**, `(git log:*)`, `Grep`. The role holds an
unrestricted shell. Under comma-only splitting the middle token is the opaque
string `Bash (git log:*)`, which is neither `"Bash"` (so
`check_tool_grants`'s bare-`Bash` census, the one measurement in this tree
whose whole job is to find unrestricted shell, stays silent) nor a `Bash(`
prefix (so the narrowing checks stay silent too). Invisible in both
directions, from one keystroke.

`\n` is a separator here and is not in `Rp`, because `Rp` is handed a value
YAML already parsed: a block sequence reaches it as a list of strings, and a
line break never survives inside one grant. These gates read the frontmatter
as raw text, where the line break is that same list boundary.

A tab is *not* a separator, in `Rp` or here: it falls to `default`, lands
inside the token, and is removed by the per-token trim.
"""

PAREN_SUSPENDED = {",", " "}


def grant_tokens(raw):
    """Split a raw `allowed-tools:`/`tools:` value into the loader's tokens.

    Tokenization only — no unquoting and no `[]`/`- ` stripping, so each gate
    keeps the YAML-noise handling it already has and gains only the one rule
    they all got wrong.
    """
    out, cur, in_paren = [], "", False
    for ch in raw:
        if ch == "(":
            in_paren, cur = True, cur + ch
        elif ch == ")":
            in_paren, cur = False, cur + ch
        elif ch == "\n" or (ch in PAREN_SUSPENDED and not in_paren):
            if cur.strip():
                out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out
