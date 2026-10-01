#!/usr/bin/env python3
"""The ceiling is on the load, not on the file — these are the cases that differ."""

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


if __name__ == "__main__":
    unittest.main()
