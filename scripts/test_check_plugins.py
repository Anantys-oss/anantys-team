#!/usr/bin/env python3
"""The ceiling is on the load, not on the file — these are the cases that differ."""

import contextlib
import io
import json
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
        cp.ROOT = Path(self.tmp.name).resolve()  # check_load resolves its links
        self.addCleanup(self.tmp.cleanup)
        cp.ROLE_MAX_LINES = 10
        cp.BASE = None
        self.addCleanup(setattr, cp, "at", cp.at)

    def write(self, name: str, n: int) -> None:
        (cp.ROOT / name).write_text(lines(n), encoding="utf-8")

    def check(self, text: str) -> list[str]:
        path = cp.ROOT / "SKILL.md"
        path.write_text(text, encoding="utf-8")
        cp.check_load(path)
        return cp.warnings

    def baseline(self, **texts: str) -> None:
        """Pretend `texts` (file name -> content) is what the baseline commit held."""
        cp.BASE = "base"
        held = {cp.ROOT / name: text for name, text in texts.items()}
        cp.at = lambda commit, path: held.get(path)


class CheckLoad(Harness):
    def test_role_alone_under_the_ceiling_is_silent(self) -> None:
        self.assertEqual(self.check("one\ntwo\n"), [])

    def test_a_preamble_link_counts_toward_the_load(self) -> None:
        self.write("CONTRACT.md", 20)
        warning, = self.check("Read the [contract](CONTRACT.md) before acting.\n")
        self.assertIn("loads 21 lines", warning)
        self.assertIn("1 SKILL.md + 20 CONTRACT.md", warning)

    def test_a_link_below_the_first_heading_does_not(self) -> None:
        self.write("CONTRACT.md", 20)
        self.assertEqual(self.check("preamble\n\n## Step\n\n[c](CONTRACT.md)\n"), [])

    def test_a_link_to_a_file_that_is_not_there_is_ignored(self) -> None:
        self.assertEqual(self.check("[gone](MISSING.md)\n"), [])


class TheRemedyIsCountedToo(Harness):
    """reference/ is where the remedy puts the load, so it is part of the load."""

    def reference(self, name: str, n: int) -> None:
        (cp.ROOT / "reference").mkdir(exist_ok=True)
        (cp.ROOT / "reference" / name).write_text(lines(n), encoding="utf-8")

    def test_a_named_topic_file_counts_toward_the_load(self) -> None:
        self.reference("run.md", 20)
        warning, = self.check("| run | `reference/run.md` |\n")
        self.assertIn("loads 21 lines", warning)
        self.assertIn("20 reference/run.md", warning)

    def test_only_the_largest_topic_file_counts(self) -> None:
        # One action reads one topic, so the bound is the worst action, not the sum.
        self.reference("small.md", 4)
        self.reference("big.md", 20)
        warning, = self.check("`reference/small.md` `reference/big.md`\n")
        self.assertIn("loads 21 lines", warning)
        self.assertIn("20 reference/big.md", warning)
        self.assertNotIn("small.md", warning)

    def test_a_topic_file_no_action_names_is_not_counted(self) -> None:
        self.reference("unused.md", 20)
        self.assertEqual(self.check("preamble only\n"), [])

    def test_a_named_topic_file_that_is_not_there_is_ignored(self) -> None:
        self.assertEqual(self.check("`reference/gone.md`\n"), [])

    def test_splitting_into_one_big_topic_file_is_not_a_pass(self) -> None:
        # The defect this closes: relocating prose into a file every action still
        # reads took a role from over-ceiling to clean without lowering the load.
        self.baseline(**{"SKILL.md": lines(20)})
        self.reference("all.md", 16)
        warning, = self.check("`reference/all.md`\n" + lines(2))
        self.assertIn("loads 19 lines (> 10), down from 20", warning)

    def test_the_baseline_counts_its_own_topic_file(self) -> None:
        self.baseline(**{
            "SKILL.md": "`reference/run.md`\n" + lines(5),
            "reference/run.md": lines(20),
        })
        warning, = self.check(lines(14))
        self.assertIn("down from 26", warning)


class ATemplateIsReadLikeATopic(Harness):
    """templates/ is the other directory an action reads, so it is priced the same."""

    def companion(self, folder: str, name: str, n: int) -> None:
        (cp.ROOT / folder).mkdir(exist_ok=True)
        (cp.ROOT / folder / name).write_text(lines(n), encoding="utf-8")

    def test_a_named_template_counts_toward_the_load(self) -> None:
        # The hole: a template the action is told to follow was read and never charged.
        self.companion("templates", "plan.md", 20)
        warning, = self.check("Write it following `templates/plan.md`.\n")
        self.assertIn("loads 21 lines", warning)
        self.assertIn("20 templates/plan.md", warning)

    def test_only_the_largest_template_counts(self) -> None:
        self.companion("templates", "small.md", 4)
        self.companion("templates", "big.md", 20)
        warning, = self.check("`templates/small.md` `templates/big.md`\n")
        self.assertIn("20 templates/big.md", warning)
        self.assertNotIn("small.md", warning)

    def test_a_topic_and_a_template_are_both_charged(self) -> None:
        # One action can read both, so the two directories sum — they do not compete.
        self.companion("reference", "run.md", 8)
        self.companion("templates", "plan.md", 9)
        warning, = self.check("`reference/run.md` `templates/plan.md`\n")
        self.assertIn("loads 18 lines", warning)
        self.assertIn("8 reference/run.md", warning)
        self.assertIn("9 templates/plan.md", warning)

    def test_moving_prose_into_a_template_is_not_a_pass(self) -> None:
        # Same defect reference/ already closed, through the sibling directory.
        self.baseline(**{"SKILL.md": lines(20)})
        self.companion("templates", "plan.md", 16)
        warning, = self.check("`templates/plan.md`\n" + lines(2))
        self.assertIn("loads 19 lines (> 10), down from 20", warning)

    def test_a_template_no_action_names_is_not_counted(self) -> None:
        self.companion("templates", "unused.md", 20)
        self.assertEqual(self.check("preamble only\n"), [])


class AgainstTheBaseline(Harness):
    """A ceiling report is only actionable if it says what *this* change did to it."""

    def test_a_change_that_pushes_a_role_over_is_named_as_the_cause(self) -> None:
        self.baseline(**{"SKILL.md": lines(8)})
        warning, = self.check(lines(20))
        self.assertIn("pushes the load over the ceiling, 8 -> 20", warning)

    def test_a_role_this_change_adds_is_its_own_cause(self) -> None:
        self.baseline()  # the role is not in the baseline tree at all
        warning, = self.check(lines(20))
        self.assertIn("pushes the load over the ceiling, 0 -> 20", warning)

    def test_growing_an_already_over_role_reports_the_delta(self) -> None:
        self.baseline(**{"SKILL.md": lines(20)})
        warning, = self.check(lines(26))
        self.assertIn("grows a load already over the ceiling, 20 -> 26 (+6)", warning)

    def test_an_untouched_over_role_is_not_blamed_on_this_change(self) -> None:
        self.baseline(**{"SKILL.md": lines(20)})
        warning, = self.check(lines(20))
        self.assertIn("loads 20 lines", warning)
        self.assertNotIn("this change", warning)

    def test_the_baseline_load_counts_its_own_links(self) -> None:
        # Dropping a linked contract is a shrink, so the baseline must be priced
        # by the same rule as the working tree — not by the role file alone.
        self.baseline(**{"SKILL.md": "[c](CONTRACT.md)\n" + lines(5), "CONTRACT.md": lines(20)})
        warning, = self.check(lines(14))
        self.assertIn("down from 26", warning)

    def test_without_a_baseline_the_absolute_warning_still_fires(self) -> None:
        cp.BASE = None
        warning, = self.check(lines(20))
        self.assertIn("loads 20 lines (> 10)", warning)


class TheContractBinds(Harness):
    """The ceiling counts the contract, so unlinking it is the cheapest way to pass."""

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

    def test_shrinking_under_the_ceiling_by_unlinking_is_not_a_pass(self) -> None:
        # The whole point: 25 lines with the contract is over a ceiling of 10, and
        # dropping the link takes it under. The load goes quiet; the binding does not.
        self.write(cp.CONTRACT, 20)
        self.assertEqual(self.check(lines(5)), [])
        cp.check_contract(cp.ROOT / "SKILL.md", cp.ROOT / cp.CONTRACT)
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

    def test_keeping_the_label_and_deleting_the_body_is_a_drop(self) -> None:
        # The label set is identical, so the drop check above sees nothing, and the
        # roles that link the contract all load less — the one edit that unbinds every
        # role at once while reading as five load warnings turning into one.
        error, = self.clauses(
            "## C1 — Observation\n\n## C2 — A stop is a result\n",
            before="## C1 — Observation\n\nobserve it\n\n## C2 — A stop is a result\n\nsay so\n",
        )
        self.assertIn("C1, C2 kept the label and lost the body", error)

    def test_a_clause_that_only_shrinks_warns_rather_than_erroring(self) -> None:
        # Content does move out of this file; a gate whose remedy is "put the lines
        # back" would forbid the split it asked for. Silence is the thing it may not be.
        self.assertEqual(
            self.clauses("## C1 — a\n\nkeep\n", before="## C1 — a\n\nkeep\nand this\n"), []
        )
        self.assertIn("C1 2 -> 1 lost body lines", cp.warnings[-1])

    def test_a_clause_that_was_already_empty_is_not_a_drop(self) -> None:
        self.assertEqual(self.clauses("## C1 — a\n", before="## C1 — a\n"), [])
        self.assertEqual(cp.warnings, [])

    def test_a_clause_that_grows_is_neither(self) -> None:
        self.assertEqual(self.clauses("## C1 — a\n\nx\ny\n", before="## C1 — a\n\nx\n"), [])
        self.assertEqual(cp.warnings, [])

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


if __name__ == "__main__":
    unittest.main()
