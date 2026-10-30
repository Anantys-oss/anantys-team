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

    def test_collects_the_per_component_always_on_column_too(self):
        # The column neither budget covers: a dropped description moves this one
        # and leaves `on_invoke` untouched, so reading only the second is what
        # made the sweep silent on it.
        got = L.parse_details(DETAILS)["always_on_each"]
        self.assertEqual(got, {"anantys.qa": 190, "anantys.debug": 80})

    def test_reads_the_floor_in_the_per_component_column(self):
        text = "Per-component\n  anantys.qa                 < 20      ~8.6k\n"
        self.assertEqual(L.parse_details(text)["always_on_each"], {"anantys.qa": 20})
        self.assertEqual(L.parse_details(text)["on_invoke"], {"anantys.qa": 8600})


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


class Undescribed(unittest.TestCase):
    """`undescribed` catches a component the inventory keeps and no model can pick."""

    def tree(self, **always_on_each):
        return {"always_on_each": always_on_each}

    def test_main_s_own_components_report_nothing(self):
        # The seven on `origin/main` measure 70-190; none is near the floor.
        base = self.tree(**{"anantys.qa": 190, "anantys.debug": 80})
        self.assertEqual(L.undescribed(base, base), ([], []))

    def test_a_description_this_head_dropped_is_its_own_error(self):
        raised, inherited = L.undescribed(self.tree(**{"anantys.qa": 190}),
                                          self.tree(**{"anantys.qa": L.ROUTABLE_MIN}))
        self.assertEqual(inherited, [])
        self.assertIn("anantys.qa always-on 20", raised[0])
        self.assertIn("base 190", raised[0])

    def test_a_component_the_baseline_already_shipped_mute_owns_no_remedy(self):
        mute = self.tree(**{"anantys.qa": L.ROUTABLE_MIN})
        raised, inherited = L.undescribed(mute, mute)
        self.assertEqual(raised, [])
        self.assertEqual(len(inherited), 1)

    def test_a_new_component_with_no_description_is_the_head_s_own(self):
        # Absent from the baseline must not read as "was already mute".
        raised, _ = L.undescribed(self.tree(**{"anantys.qa": 190}),
                                  self.tree(**{"anantys.qa": 190, "new.role": 20}))
        self.assertEqual(len(raised), 1)
        self.assertIn("new here", raised[0])

    def test_each_mute_component_is_its_own_finding(self):
        raised, _ = L.undescribed(self.tree(a=190, b=180), self.tree(a=20, b=20))
        self.assertEqual(len(raised), 2)

    def test_a_row_one_token_over_the_floor_is_priced_and_silent(self):
        # The loader printed a number, so it found something to price.
        self.assertEqual(L.undescribed(self.tree(a=190),
                                       self.tree(a=L.ROUTABLE_MIN + 1)), ([], []))

    def test_a_table_the_sweep_could_not_read_rules_on_nothing(self):
        self.assertEqual(L.undescribed(self.tree(a=190), {}), ([], []))


class QueueHeads(unittest.TestCase):
    """`queue_heads` decides what the sweep is a sweep *of*."""

    def test_a_head_with_no_open_pr_is_still_in_the_population(self):
        # The defect this replaced: 42 of 162 branches had no PR, and the two
        # folds over the on-invoke ceiling were among them.
        self.assertEqual(L.queue_heads(["origin/koan/a", "origin/koan/b"], {"koan/a": 7}),
                         [(7, "origin/koan/a"), (None, "origin/koan/b")])

    def test_the_baseline_is_not_a_row(self):
        # `ls-remote` returns `main`; it is the tree every delta is measured
        # from, so pricing it against itself is a row that says nothing.
        self.assertEqual(L.queue_heads(["origin/main", "origin/koan/a"], {}),
                         [(None, "origin/koan/a")])

    def test_a_non_default_baseline_is_the_one_dropped(self):
        self.assertEqual(
            L.queue_heads(["origin/main", "origin/release"], {}, baseline="origin/release"),
            [(None, "origin/main")],
        )

    def test_a_pr_number_survives_a_ref_that_carries_slashes(self):
        # Every branch here is `koan/<name>`; stripping only the remote prefix
        # is what keeps the PR label attached.
        self.assertEqual(L.queue_heads(["origin/koan/a/b"], {"koan/a/b": 9}),
                         [(9, "origin/koan/a/b")])

    def test_rows_are_ordered_by_ref_so_a_missing_number_cannot_break_the_sort(self):
        # Sorting the tuples themselves compares `None` against an `int`.
        got = L.queue_heads(["origin/koan/c", "origin/koan/a", "origin/koan/b"],
                            {"koan/b": 2})
        self.assertEqual([ref for _, ref in got],
                         ["origin/koan/a", "origin/koan/b", "origin/koan/c"])

    def test_a_pr_for_a_branch_nobody_pushed_adds_no_row(self):
        # The PR list is a label lookup, never a source of refs: a stale entry
        # for a deleted branch must not produce a ref the loader cannot export.
        self.assertEqual(L.queue_heads(["origin/koan/a"], {"koan/gone": 3}),
                         [(None, "origin/koan/a")])

    def test_a_duplicate_ref_is_priced_once(self):
        self.assertEqual(len(L.queue_heads(["origin/koan/a", "origin/koan/a"], {})), 1)

    def test_no_pr_access_still_leaves_the_whole_population(self):
        # `pr_numbers` returns `{}` when `gh` is absent. The sweep needs no
        # GitHub credential; losing the labels must not lose the refs.
        self.assertEqual(len(L.queue_heads(["origin/koan/a", "origin/koan/b"], {})), 2)


if __name__ == "__main__":
    unittest.main()
