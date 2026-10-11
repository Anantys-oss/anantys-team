#!/usr/bin/env python3
"""Where this gate's checks decide differently from the obvious reading of their rule."""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import check_plugins as cp


def lines(n: int) -> str:
    return "\n".join(["x"] * n) + "\n"


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        cp.errors.clear()
        cp.warnings.clear()
        self.tmp = tempfile.TemporaryDirectory()
        cp.ROOT = Path(self.tmp.name).resolve()  # the checks resolve their links
        self.addCleanup(self.tmp.cleanup)
        cp.BASE = None
        self.addCleanup(setattr, cp, "at", cp.at)

    def write(self, name: str, n: int) -> None:
        (cp.ROOT / name).write_text(lines(n), encoding="utf-8")

    def baseline(self, **texts: str) -> None:
        """Pretend `texts` (file name -> content) is what the baseline commit held."""
        cp.BASE = "base"
        held = {cp.ROOT / name: text for name, text in texts.items()}
        cp.at = lambda commit, path: held.get(path)


#: A real `claude plugin details` cost table, trimmed to the part this gate reads.
DETAILS = """\
Projected token cost
  Always-on:   ~716 tok   added to every session

Per-component (rounded)
  component             always-on  on-invoke
  anantys.review             ~100      ~1.3k
  anantys.qa                 ~190      ~8.6k
  tiny                       < 20       < 20
"""


def details(always_on: str, **components: str) -> str:
    """A cost table with `always_on` as the total and one row per component."""
    rows = "\n".join(f"  {name}  ~70  {cost}" for name, cost in components.items())
    return f"Projected token cost\n  Always-on:   {always_on} tok\n\n{rows}\n"


class CostIsPricedInTheLoadersCurrency(Harness):
    """The two budgets are read out of `claude plugin details`, not computed from lines."""

    def cost(self, table: str | None) -> list[str]:
        cp.check_cost(cp.ROOT, "p", table)
        return cp.errors + cp.warnings

    def test_a_table_under_both_budgets_is_silent(self) -> None:
        self.assertEqual(self.cost(DETAILS), [])

    def test_an_always_on_total_over_budget_is_an_error(self) -> None:
        error, = self.cost(details("~1.4k", a="~900"))
        self.assertIn("1400 always-on tokens (> 1000)", error)
        self.assertIn("`description`", error)

    def test_a_component_over_the_on_invoke_budget_is_an_error(self) -> None:
        error, = self.cost(details("~700", fat="~73k"))
        self.assertIn("fat: 73000 tokens on invoke (> 12000)", error)

    def test_the_remedy_names_reference_which_the_loader_charges_this_column_nothing(self) -> None:
        error, = self.cost(details("~700", fat="~20k"))
        self.assertIn("`reference/`", error)

    def test_each_component_is_judged_on_its_own_row(self) -> None:
        self.assertEqual(len(self.cost(details("~700", a="~20k", b="~1.3k", c="~40k"))), 2)

    def test_a_k_suffix_is_thousands_not_a_literal(self) -> None:
        # `~8.6k` under a 12000 budget is 8600 and passes; read as 8.6 it would also
        # pass, and read as 86 it would too — so the case that separates them is one
        # where the suffix decides the verdict.
        self.assertEqual(self.cost(details("~700", a="~11.9k")), [])
        self.assertEqual(len(self.cost(details("~700", b="~12.1k"))), 1)

    def test_a_four_digit_count_carries_a_thousands_separator(self) -> None:
        # The loader prints `~1,736 tok` once the total has four digits — the real
        # notation that first ran this check into a ValueError, which is the one
        # outcome a gate may not have: no verdict at all.
        self.assertEqual(cp.tokens("1,736"), 1736)
        error, = self.cost(details("~1,736", a="~900"))
        self.assertIn("1736 always-on tokens", error)

    def test_a_cost_under_the_reporting_floor_is_read_as_its_bound_not_skipped(self) -> None:
        # The loader prints `< 20` instead of `~N` below its floor. A row that matches
        # no pattern is a row this gate passes in silence, which is the whole defect
        # the line ceiling had: a measurement that quietly declines to measure.
        self.assertEqual(cp.tokens("20"), 20)
        self.assertEqual(self.cost("Projected token cost\n  Always-on:   < 20 tok\n"), [])

    def test_a_table_whose_shape_changed_is_an_error_not_a_pass(self) -> None:
        error, = self.cost("Projected token cost\n  Nothing recognisable here\n")
        self.assertIn("printed no always-on total", error)

    def test_a_cli_that_did_not_run_warns_rather_than_passing_or_failing(self) -> None:
        # A gate that cannot measure must not rule: an error would redden every tree
        # without the CLI installed, and silence would report a budget it never read.
        warning, = self.cost(None)
        self.assertIn("did not run", warning)
        self.assertEqual(cp.errors, [])


@unittest.skipIf(shutil.which("claude") is None, "needs the Claude Code CLI")
class TheLoaderChargesTheBodyOnInvokeAndCompanionsNotAtAll(unittest.TestCase):
    """The measurement the retired 200-line ceiling asserted without taking.

    Its premise was *a role loads in full, every invocation*, and it summed the role
    file, its preamble links, the largest `reference/` topic and the largest
    `templates/` file into one line count. Both halves of that are wrong, and these
    two cases are the ones that say so — run against the real loader, because a
    fixture of its output could only repeat whatever this file already believes.
    """

    def plugin(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        (root / ".claude-plugin").mkdir()
        (root / ".claude-plugin/plugin.json").write_text(
            json.dumps({"name": "p", "version": "0.1.0", "description": "d"}), encoding="utf-8"
        )
        (root / "skills/s").mkdir(parents=True)
        self.skill = root / "skills/s/SKILL.md"
        self.skill.write_text(
            "---\nname: s\ndescription: A role that does a thing.\n---\n\n" + lines(400),
            encoding="utf-8",
        )
        return root

    def measure(self, root: Path) -> tuple[int, int]:
        """`(always-on total, the one component's on-invoke cost)`."""
        table = cp.loader_details(root, "p")
        self.assertIsNotNone(table, "the CLI is installed but printed no cost table")
        total = cp.tokens(cp.LOADER_TOTAL.search(table).group(1))
        (_, _, on_invoke), = cp.LOADER_ROW.findall(table)
        return total, cp.tokens(on_invoke)

    def test_the_body_is_charged_on_invoke_and_not_always_on(self) -> None:
        root = self.plugin()
        before_total, before_invoke = self.measure(root)
        with self.skill.open("a", encoding="utf-8") as handle:
            handle.write(lines(4000))
        after_total, after_invoke = self.measure(root)
        self.assertGreater(after_invoke, before_invoke * 4)
        self.assertEqual(after_total, before_total)

    def test_a_companion_the_role_names_is_charged_to_neither_column(self) -> None:
        root = self.plugin()
        before = self.measure(root)
        (self.skill.parent / "reference").mkdir()
        (self.skill.parent / "reference/huge.md").write_text(lines(4000), encoding="utf-8")
        with self.skill.open("a", encoding="utf-8") as handle:
            handle.write("\nFollow `reference/huge.md` for the detail.\n")
        after_total, after_invoke = self.measure(root)
        self.assertEqual(after_total, before[0])
        # The one added sentence is the whole difference; 4000 lines cost nothing.
        self.assertLess(after_invoke - before[1], 100)


class TheContractBinds(Harness):
    """The contract asserts that every role points here; these cases read the link."""

    def contract(self, text: str) -> list[str]:
        self.write(cp.CONTRACT, 20)
        path = cp.ROOT / "SKILL.md"
        path.write_text(text, encoding="utf-8")
        cp.check_contract(path, cp.ROOT / cp.CONTRACT)
        return cp.errors

    def test_a_preamble_link_to_the_contract_satisfies_it(self) -> None:
        self.assertEqual(self.contract(f"[team contract]({cp.CONTRACT}) binds you.\n"), [])

    def test_a_role_that_links_nothing_is_an_error(self) -> None:
        error, = self.contract("You are a role.\n")
        self.assertIn("does not link TEAM-CONTRACT.md", error)

    def test_a_contract_link_below_the_first_heading_does_not_count(self) -> None:
        # Nothing below `## ` is read before the role acts, so a link there binds
        # it no earlier than not linking at all — and it would pass a substring test.
        error, = self.contract(f"preamble\n\n## Step\n\n[c]({cp.CONTRACT})\n")
        self.assertIn("does not link TEAM-CONTRACT.md", error)

    def test_unlinking_the_contract_costs_the_role_nothing_and_is_still_an_error(self) -> None:
        # The retired line ceiling counted the contract, so unlinking it was the
        # cheapest way to pass. `check_cost` charges it nothing — the loader does not
        # load it — so the incentive is gone and this is the only check that notices.
        path = cp.ROOT / "SKILL.md"
        path.write_text(lines(5), encoding="utf-8")
        cp.check_cost(cp.ROOT, "p", DETAILS)
        self.assertEqual(cp.errors, [])
        cp.check_contract(path, cp.ROOT / cp.CONTRACT)
        self.assertEqual(len(cp.errors), 1)


class ContractClauses(Harness):
    """`check_contract` holds the link. These hold what the link points at."""

    def clauses(self, now: str, *, before: str | None = None) -> list[str]:
        path = cp.ROOT / cp.CONTRACT
        path.write_text(now, encoding="utf-8")
        if before is not None:
            self.baseline(**{cp.CONTRACT: before})
        cp.check_contract_clauses(path)
        return cp.errors

    def test_a_dropped_clause_is_an_error(self) -> None:
        error, = self.clauses(
            "# Team contract\n\n## C1 — Observation\n",
            before="# Team contract\n\n## C1 — Observation\n\n## C2 — A stop is a result\n",
        )
        self.assertIn("C2 present at the baseline and gone here", error)

    def test_relabelling_a_clause_is_a_drop(self) -> None:
        # The role files cite the label (`say so and stop (C2)`), so the label is the
        # identity. Renaming the heading is how the deletion would have arrived.
        error, = self.clauses(
            "## Zzz — nothing\n", before="## C2 — A stop is a result\n"
        )
        self.assertIn("C2", error)

    def test_rewording_the_title_is_not_a_drop(self) -> None:
        self.assertEqual(
            self.clauses("## C2 — the run you did not finish\n", before="## C2 — A stop\n"),
            [],
        )

    def test_adding_a_clause_is_how_the_contract_grows(self) -> None:
        self.assertEqual(self.clauses("## C1 — a\n\n## C2 — b\n", before="## C1 — a\n"), [])

    def test_a_contract_that_arrives_on_this_branch_is_not_a_drop(self) -> None:
        self.baseline()  # BASE set, nothing held there
        path = cp.ROOT / cp.CONTRACT
        path.write_text("## C1 — a\n", encoding="utf-8")
        cp.check_contract_clauses(path)
        self.assertEqual(cp.errors, [])

    def test_a_contract_new_at_the_baseline_says_so_rather_than_passing(self) -> None:
        # This is the branch the whole queue takes until the contract lands on main.
        # Silent here and the check ships inert, which is the gap it closes.
        self.baseline()
        path = cp.ROOT / cp.CONTRACT
        path.write_text("## C1 — a\n", encoding="utf-8")
        cp.check_contract_clauses(path)
        self.assertIn("new at the baseline", cp.warnings[0])

    def test_no_baseline_warns_rather_than_passing_silently(self) -> None:
        cp.BASE = None
        path = cp.ROOT / cp.CONTRACT
        path.write_text("## C1 — a\n", encoding="utf-8")
        cp.check_contract_clauses(path)
        self.assertEqual(cp.errors, [])
        self.assertIn("no baseline", cp.warnings[0])


class DeletingTheContractIsNotAnAbsentContract(unittest.TestCase):
    """A dropped clause is an error. Deleting the file drops every clause at once.

    ``check_contract_clauses`` holds the clause set, and ``main`` only reaches it when
    the file is on disk — absence took the "some other change lands it" branch and
    printed a warning. So the cheapest way to unbind every role was not to relabel a
    clause but to delete the file: zero errors, and five roles under the ceiling.

    These go through ``main`` because the short circuit is in ``main``; the function
    itself already errors when handed a tree with no contract in it.
    """

    def setUp(self) -> None:
        cp.errors.clear()
        cp.warnings.clear()
        self.tmp = tempfile.TemporaryDirectory()
        cp.ROOT = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, cp, "at", cp.at)
        self.addCleanup(setattr, cp, "merge_base", cp.merge_base)
        cp.merge_base = lambda: "base"  # the tmp tree is not a git repo

        plugin = cp.ROOT / "plugins/p"
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / "skills").mkdir()
        (plugin / "agents").mkdir()
        entry = {"name": "p", "version": "1.0.0", "description": "a plugin"}
        (plugin / ".claude-plugin/plugin.json").write_text(json.dumps(entry))
        (cp.ROOT / ".claude-plugin").mkdir()
        (cp.ROOT / ".claude-plugin/marketplace.json").write_text(
            json.dumps({"plugins": [dict(entry, source="plugins/p")]})
        )
        (cp.ROOT / "README.md").write_text("")
        self.contract = plugin / cp.CONTRACT

    def held(self, text: str | None) -> None:
        """What the baseline commit held at the contract's path."""
        cp.at = lambda commit, path: text if path == self.contract else None

    def run_main(self) -> int:
        with contextlib.redirect_stdout(io.StringIO()):
            return cp.main()

    def test_a_contract_present_at_the_baseline_and_gone_here_is_an_error(self) -> None:
        self.held("# Team contract\n\n## C1 — Observation\n")
        self.assertEqual(self.run_main(), 1)
        error, = cp.errors
        self.assertIn(cp.CONTRACT, error)
        self.assertIn("gone here", error)

    def test_a_tree_that_never_held_a_contract_is_still_only_a_warning(self) -> None:
        # Absence is legitimate until some other change lands the file; this is the
        # branch every open head takes, and reddening it would force an order on them.
        self.held(None)
        self.assertEqual(self.run_main(), 0)
        self.assertEqual(cp.errors, [])
        self.assertTrue(cp.warnings)


class ARoleIsDescribedNotJustNamed(unittest.TestCase):
    """README's mention has to be prose, because prose is what a user reads.

    The membership test ran over the whole file. The "Repository layout" block names
    every role's path, so that listing alone answered for all of them: the role table
    could be deleted with zero errors, and a new role joined the user-facing surface
    on one line of ASCII tree. The install and usage snippets do the same.
    """

    def setUp(self) -> None:
        cp.errors.clear()
        cp.warnings.clear()
        self.tmp = tempfile.TemporaryDirectory()
        cp.ROOT = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, cp, "merge_base", cp.merge_base)
        cp.merge_base = lambda: None  # the tmp tree is not a git repo

        plugin = cp.ROOT / "plugins/p"
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / "agents").mkdir()
        role = plugin / "skills/anantys.newrole"
        role.mkdir(parents=True)
        (role / "SKILL.md").write_text(
            "---\nname: anantys.newrole\ndescription: d\n---\n", encoding="utf-8"
        )
        entry = {"name": "p", "version": "1.0.0", "description": "a plugin"}
        (plugin / ".claude-plugin/plugin.json").write_text(json.dumps(entry))
        (cp.ROOT / ".claude-plugin").mkdir()
        (cp.ROOT / ".claude-plugin/marketplace.json").write_text(
            json.dumps({"plugins": [dict(entry, source="plugins/p")]})
        )

    def readme(self, text: str) -> list[str]:
        (cp.ROOT / "README.md").write_text(text, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            cp.main()
        return [e for e in cp.errors if "README" in e]

    def test_a_prose_description_satisfies_it(self) -> None:
        self.assertEqual(self.readme("`anantys.newrole` refines a page.\n"), [])

    def test_a_path_in_a_layout_block_does_not(self) -> None:
        errors = self.readme("```\nskills/anantys.newrole/SKILL.md\n```\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("outside a code block", errors[0])

    def test_a_usage_snippet_does_not(self) -> None:
        self.assertEqual(len(self.readme("```bash\n/anantys.newrole go\n```\n")), 1)

    def test_prose_between_two_blocks_survives_the_strip(self) -> None:
        # A non-greedy fence match that spanned block-to-block would eat the middle.
        self.assertEqual(self.readme("```\na\n```\nanantys.newrole\n```\nb\n```\n"), [])

    def test_a_role_named_nowhere_is_still_an_error(self) -> None:
        self.assertEqual(len(self.readme("# anantys-team\n")), 1)


class TheInstallSnippetIsExecuted(unittest.TestCase):
    """The one fenced block the strip above may not drop.

    `/plugin install <plugin>@<marketplace>` is the only text in the repo a user
    runs, and both its names are ones the drift check already reads. Stripping every
    fence left it gated by nothing: renaming the catalog in both manifests, deleting
    the Install section, and naming a plugin that exists nowhere were each 0 errors.
    """

    def setUp(self) -> None:
        # Same one-role tree, borrowed rather than copied — but not by subclassing, or
        # that class's READMEs would be re-run against a check they were not written for.
        ARoleIsDescribedNotJustNamed.setUp(self)
        catalog = cp.ROOT / ".claude-plugin/marketplace.json"
        catalog.write_text(json.dumps(dict(json.loads(catalog.read_text()), name="m")))

    def install(self, text: str) -> list[str]:
        prose = "`anantys.newrole` refines a page.\n"  # satisfies the prose check
        (cp.ROOT / "README.md").write_text(prose + text, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            cp.main()
        return [e for e in cp.errors if "install snippet" in e]

    def test_the_command_in_a_fenced_block_satisfies_it(self) -> None:
        self.assertEqual(self.install("```bash\n/plugin install p@m\n```\n"), [])

    def test_no_install_command_at_all_is_an_error(self) -> None:
        self.assertEqual(len(self.install("")), 1)

    def test_a_renamed_marketplace_breaks_the_command(self) -> None:
        # Both manifests agreeing is what the drift check tests; it is not this.
        self.assertEqual(len(self.install("```\n/plugin install p@anantys-oss\n```\n")), 1)

    def test_a_plugin_that_exists_nowhere_is_an_error(self) -> None:
        self.assertEqual(len(self.install("```\n/plugin install nope@m\n```\n")), 1)

    def test_a_longer_name_does_not_satisfy_a_shorter_one(self) -> None:
        self.assertEqual(len(self.install("```\n/plugin install p@my-other-market\n```\n")), 1)

    def test_a_catalog_with_no_name_is_a_warning_naming_what_went_unmeasured(self) -> None:
        catalog = cp.ROOT / ".claude-plugin/marketplace.json"
        catalog.write_text(json.dumps({"plugins": json.loads(catalog.read_text())["plugins"]}))
        self.assertEqual(self.install(""), [])
        self.assertTrue(any("unmeasured" in w for w in cp.warnings))


class ANamedCompanionMustBeThere(Harness):
    """A name that resolves to nothing is not the same state as no name at all.

    Two tests above assert that an absent companion is *ignored* — correct for
    pricing a load, and the whole diagnosis for everything else: the role instructs
    an action to read a page that is not there, and no checker in the tree says so.
    """

    def companion(self, folder: str, name: str, n: int) -> None:
        (cp.ROOT / folder).mkdir(exist_ok=True)
        (cp.ROOT / folder / name).write_text(lines(n), encoding="utf-8")

    def companions(self, text: str) -> list[str]:
        path = cp.ROOT / "SKILL.md"
        path.write_text(text, encoding="utf-8")
        cp.check_companions(path)
        return cp.errors

    def test_a_role_whose_companions_all_exist_is_silent(self) -> None:
        self.companion("reference", "run.md", 3)
        self.companion("templates", "plan.md", 3)
        self.assertEqual(self.companions("`reference/run.md` `templates/plan.md`\n"), [])

    def test_a_preamble_link_to_a_file_that_is_not_there_is_an_error(self) -> None:
        error, = self.companions("Read [the contract](CONTRACT.md) first.\n")
        self.assertIn("names `CONTRACT.md`, which is not in the tree", error)

    def test_a_named_topic_that_is_not_there_is_an_error(self) -> None:
        error, = self.companions("The `run` action reads `reference/gone.md`.\n")
        self.assertIn("names `reference/gone.md`", error)

    def test_a_named_template_that_is_not_there_is_an_error(self) -> None:
        error, = self.companions("Follow `templates/gone.md`.\n")
        self.assertIn("names `templates/gone.md`", error)

    def test_a_template_named_only_in_a_named_topic_is_checked(self) -> None:
        # The surface `named_companions` reaches: a role's own split moves the
        # template mention into the topic, so a dangling one hides there too.
        self.companion("reference", "sources.md", 3)
        (cp.ROOT / "reference/sources.md").write_text("Follow `templates/gone.md`.\n")
        error, = self.companions("`reference/sources.md`\n")
        self.assertIn("names `templates/gone.md`", error)

    def test_a_markdown_link_below_the_first_heading_is_out_of_scope(self) -> None:
        # Stated boundary, not an oversight: widening discovery past the preamble is
        # a question the two grant gates answer the same way, and one must not widen
        # alone. `load_parts` draws the line in the same place.
        self.assertEqual(self.companions("pre\n\n## Step\n\n[x](GONE.md)\n"), [])

    def test_only_the_dangling_one_of_two_citations_is_reported(self) -> None:
        # The present companion is not a finding and the absent one is exactly one:
        # this check reports a name, not a count, so a role that cites both reports
        # neither twice nor not at all.
        self.companion("reference", "big.md", 16)
        error, = self.companions("`reference/big.md` `reference/gone.md`\n")
        self.assertIn("names `reference/gone.md`", error)


class DelistingATreeIsNotRemovingIt(DeletingTheContractIsNotAnAbsentContract):
    """Deleting the contract drops every clause. Deleting the entry drops every check.

    The same shape one level up: ``check_contract_clauses`` is reached only when the
    file is on disk, and *everything* is reached only when the catalog names the tree.
    So the cheapest way to unbind a plugin was never to edit a role — it was to drop
    four lines of JSON. These go through ``main`` because the loop is in ``main``.
    """

    def delist(self) -> None:
        (cp.ROOT / ".claude-plugin/marketplace.json").write_text(json.dumps({"plugins": []}))

    def test_an_unlisted_tree_is_an_error(self) -> None:
        self.held(None)
        self.delist()
        self.assertEqual(self.run_main(), 1)
        error, = cp.errors
        self.assertIn("plugins/p/.claude-plugin/plugin.json", error)
        self.assertIn("no marketplace.json entry", error)

    def test_delisting_does_not_silence_the_tree_it_hides(self) -> None:
        # The point of the check: a role that would fail still fails after the edit.
        self.held(None)
        skill = cp.ROOT / "plugins/p/skills/s"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: wrong\n---\n")
        self.assertEqual(self.run_main(), 1)
        listed = list(cp.errors)
        cp.errors.clear()
        cp.warnings.clear()
        self.delist()
        self.assertEqual(self.run_main(), 1)
        self.assertTrue(any("!= `s`" in e for e in listed))
        self.assertFalse(any("!= `s`" in e for e in cp.errors))  # the edit still hides it
        unlisted, = cp.errors  # but the hiding is itself the one error left
        self.assertIn("governed by nothing", unlisted)

    def test_removing_the_entry_and_the_tree_together_is_silent(self) -> None:
        self.held(None)
        shutil.rmtree(cp.ROOT / "plugins/p")
        self.delist()
        self.assertEqual(self.run_main(), 0)
        self.assertEqual(cp.errors, [])


if __name__ == "__main__":
    unittest.main()
