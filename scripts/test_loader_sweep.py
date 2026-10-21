#!/usr/bin/env python3
"""Fixture tests for loader_sweep — run: python3 -m unittest discover scripts"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import loader_sweep as L  # noqa: E402


DETAILS = """anantys-team-agents 0.6.1
  Description: Turn Claude into a specialized mini-team of roles.
  Source: anantys-team-agents@anantys-oss

Component inventory
  Skills (5)  anantys.debug, anantys.design, anantys.ops, anantys.qa, anantys.review
  Agents (2)  anantys.spec-tester, anantys.code-auditor
  Hooks (0)
  MCP servers (0)

Projected token cost
  Always-on:   ~716 tok   added to every session

Per-component (rounded)
  component             always-on  on-invoke
  anantys.qa                 ~190      ~8.6k
  anantys.debug               ~80       ~950
"""


class ParseDetails(unittest.TestCase):
    def test_reads_version_inventory_and_budget(self):
        got = L.parse_details(DETAILS)
        self.assertEqual(got["version"], "0.6.1")
        self.assertEqual(got["always_on"], 716)
        self.assertEqual(got["inventory"]["Agents"],
                         ["anantys.code-auditor", "anantys.spec-tester"])
        self.assertEqual(len(got["inventory"]["Skills"]), 5)

    def test_sorts_names_so_loader_ordering_is_not_drift(self):
        # `details` prints agents in load order, not alphabetically; comparing
        # two heads must not report that ordering as a change.
        self.assertEqual(L.parse_details(DETAILS)["inventory"]["Agents"],
                         sorted(L.parse_details(DETAILS)["inventory"]["Agents"]))

    def test_a_zero_kind_is_an_empty_list_not_a_missing_key(self):
        # "the loader rejected every hook" and "the loader never printed a Hooks
        # line" are different failures, and only the second is a dead install.
        self.assertEqual(L.parse_details(DETAILS)["inventory"]["Hooks"], [])

    def test_a_dead_install_has_no_inventory_at_all(self):
        self.assertEqual(L.parse_details("command not found")["inventory"], {})

    def test_expands_the_abbreviated_thousands_details_prints(self):
        self.assertEqual(L.parse_details("  Always-on:   ~1.2k tok")["always_on"], 1200)

    def test_version_comes_from_the_plugin_line_not_a_later_mention(self):
        text = "anantys-team-agents 0.6.1\n  Requires 9.9.9\n"
        self.assertEqual(L.parse_details(text)["version"], "0.6.1")

    def test_reads_the_thousands_separator_a_four_digit_count_carries(self):
        # The loader prints `1,034` once the total passes a thousand — which is
        # the only range `ALWAYS_ON_MAX` is about. A reader that stops at the
        # comma leaves the number unread on exactly the heads it exists to price.
        self.assertEqual(L.parse_details("  Always-on:   ~1,034 tok")["always_on"], 1034)

    def test_reads_the_floor_the_loader_prints_instead_of_a_small_count(self):
        # Under its reporting floor the loader prints `< 20`, not `~N`.
        self.assertEqual(L.parse_details("  Always-on:   < 20 tok")["always_on"], 20)

    def test_collects_the_per_component_on_invoke_column(self):
        got = L.parse_details(DETAILS)["on_invoke"]
        self.assertEqual(got, {"anantys.qa": 8600, "anantys.debug": 950})

    def test_a_table_the_loader_never_printed_is_empty_not_missing(self):
        self.assertEqual(L.parse_details("command not found")["on_invoke"], {})


BASE = {"inventory": {"Skills": ["a", "b"], "Agents": ["x"]}}


class Drift(unittest.TestCase):
    def test_no_drift_against_itself(self):
        self.assertEqual(L.lost(BASE, BASE), [])
        self.assertEqual(L.gained(BASE, BASE), [])

    def test_a_dropped_skill_is_reported_with_its_kind(self):
        head = {"inventory": {"Skills": ["a"], "Agents": ["x"]}}
        self.assertEqual(L.lost(BASE, head), ["Skills:b"])

    def test_an_added_skill_is_reported_but_separately_from_a_loss(self):
        # A branch adding a sixth role is doing its job; only losses are errors.
        head = {"inventory": {"Skills": ["a", "b", "c"], "Agents": ["x"]}}
        self.assertEqual(L.lost(BASE, head), [])
        self.assertEqual(L.gained(BASE, head), ["Skills:c"])

    def test_a_whole_kind_vanishing_is_a_loss_of_each_of_its_members(self):
        self.assertEqual(L.lost(BASE, {"inventory": {"Skills": ["a", "b"]}}), ["Agents:x"])

    def test_a_dead_install_loses_everything(self):
        self.assertEqual(L.lost(BASE, {}), ["Agents:x", "Skills:a", "Skills:b"])


class Misnamed(unittest.TestCase):
    def test_a_matching_name_is_silent(self):
        self.assertEqual(L.misnamed({"anantys.qa": "anantys.qa"}, ["anantys.qa"]), [])

    def test_a_renamed_frontmatter_field_is_reported(self):
        # The case on the queue: `name:` rewritten to hyphens while the
        # directory — the only thing the loader reads — stays dotted.
        self.assertEqual(L.misnamed({"anantys.qa": "anantys-qa"}, ["anantys.qa"]),
                         [("anantys.qa", "anantys-qa")])

    def test_an_absent_name_key_is_not_a_finding(self):
        # Deleting `name:` changes nothing the loader exposes, so it misleads
        # nobody. Whether the field is required belongs to the validator.
        self.assertEqual(L.misnamed({"anantys.qa": None}, ["anantys.qa"]), [])

    def test_a_directory_the_loader_never_exposed_is_not_judged_on_its_name(self):
        # If the loader dropped the skill entirely, `lost` owns that finding;
        # reporting its `name:` too would double-count one defect.
        self.assertEqual(L.misnamed({"anantys.qa": "wrong"}, []), [])

    def test_every_mismatch_is_listed_not_just_the_first(self):
        declared = {"a": "a-x", "b": "b", "c": "c-x"}
        self.assertEqual(L.misnamed(declared, ["a", "b", "c"]),
                         [("a", "a-x"), ("c", "c-x")])


class DeclaredNames(unittest.TestCase):
    def write(self, body):
        tree = Path(self.enterContext(tempfile.TemporaryDirectory()))
        skill = tree / "plugins" / L.PLUGIN / "skills" / "anantys.qa"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(body, encoding="utf-8")
        return L.declared_names(tree)

    def test_reads_the_name_from_frontmatter(self):
        self.assertEqual(self.write("---\nname: anantys.qa\n---\nbody\n"),
                         {"anantys.qa": "anantys.qa"})

    def test_a_name_in_the_body_is_not_frontmatter(self):
        # Role prose quotes `name: …` in examples; only the opening block counts.
        self.assertEqual(self.write("---\ndescription: d\n---\nname: from-the-body\n"),
                         {"anantys.qa": None})

    def test_a_file_with_no_frontmatter_declares_nothing(self):
        self.assertEqual(self.write("# just prose\n"), {"anantys.qa": None})

    def test_keeps_a_value_containing_a_colon(self):
        self.assertEqual(self.write("---\nname: plugin:anantys.qa\n---\n"),
                         {"anantys.qa": "plugin:anantys.qa"})


class Overspent(unittest.TestCase):
    """`overspent` splits a budget finding by who owns its remedy."""

    def tree(self, always_on, **on_invoke):
        return {"always_on": always_on, "on_invoke": on_invoke}

    def test_a_head_under_both_ceilings_reports_nothing(self):
        base = self.tree(716, **{"anantys.qa": 8600})
        self.assertEqual(L.overspent(base, base), ([], []))

    def test_a_head_that_crosses_the_always_on_ceiling_owns_it(self):
        raised, inherited = L.overspent(self.tree(716), self.tree(L.ALWAYS_ON_MAX + 34))
        self.assertEqual(inherited, [])
        self.assertIn("always-on 1034", raised[0])

    def test_a_head_that_only_inherits_an_overflow_owns_no_remedy(self):
        over = L.ALWAYS_ON_MAX + 34
        raised, inherited = L.overspent(self.tree(over), self.tree(over))
        self.assertEqual(raised, [])
        self.assertEqual(len(inherited), 1)

    def test_lowering_an_inherited_overflow_without_clearing_it_is_not_a_failure(self):
        raised, inherited = L.overspent(self.tree(L.ALWAYS_ON_MAX + 100),
                                        self.tree(L.ALWAYS_ON_MAX + 10))
        self.assertEqual(raised, [])
        self.assertEqual(len(inherited), 1)

    def test_a_component_the_baseline_never_had_is_the_head_s_own(self):
        # Absent from the baseline must not read as "was 0, so under the limit".
        raised, _ = L.overspent(self.tree(716),
                                self.tree(716, **{"new.role": L.ON_INVOKE_MAX + 1}))
        self.assertIn("new here", raised[0])

    def test_each_over_budget_component_is_its_own_finding(self):
        raised, _ = L.overspent(
            self.tree(716),
            self.tree(716, **{"a": L.ON_INVOKE_MAX + 1, "b": L.ON_INVOKE_MAX + 2}),
        )
        self.assertEqual(len(raised), 2)

    def test_an_unreadable_count_rules_on_nothing(self):
        # `None` is "the table could not be read", never "measured zero".
        self.assertEqual(L.overspent(self.tree(716), self.tree(None)), ([], []))


if __name__ == "__main__":
    unittest.main()
