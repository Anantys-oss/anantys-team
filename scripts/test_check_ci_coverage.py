#!/usr/bin/env python3
"""Tests for check_ci_coverage. Run: python3 scripts/test_check_ci_coverage.py"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_ci_coverage import check, main, scan  # noqa: E402

ON_PR = "on:\n  pull_request:\n\njobs:\n  j:\n    steps:\n"
ON_PUSH = "on:\n  push:\n    branches: [main]\n\njobs:\n  j:\n    steps:\n"
JOBS = "\njobs:\n  j:\n    steps:\n"
RUN_A = "      - run: python3 scripts/check_a.py\n"
DISCOVER = "      - run: python3 -m unittest discover -s scripts\n"


def tree(root, scripts=(), workflows=()):
    (root / "scripts").mkdir()
    for name in scripts:
        (root / "scripts" / name).write_text("#\n")
    (root / ".github/workflows").mkdir(parents=True)
    for name, text in workflows:
        (root / ".github/workflows" / name).write_text(text)
    return root


def test_a_checker_run_on_pull_request_is_covered(tmp_path):
    tree(tmp_path, ["check_a.py"], [("a.yml", ON_PR + "      - run: python3 scripts/check_a.py\n")])
    assert main([str(tmp_path)]) == 0


def test_a_checker_no_workflow_runs_is_an_error(tmp_path):
    tree(tmp_path, ["check_a.py"], [("a.yml", ON_PR + "      - run: echo hi\n")])
    assert main([str(tmp_path)]) == 1


def test_a_checker_run_only_after_merge_is_an_error(tmp_path):
    tree(tmp_path, ["check_a.py"], [("a.yml", ON_PUSH + "      - run: python3 scripts/check_a.py\n")])
    errors, _ = scan_and_check(tmp_path)
    assert len(errors) == 1, errors
    assert "does not trigger" in errors[0], errors[0]


def test_unittest_discovery_alone_does_not_cover_a_checker(tmp_path):
    tree(tmp_path, ["check_a.py", "test_check_a.py"],
         [("a.yml", ON_PR + "      - run: python3 -m unittest discover -s scripts\n")])
    errors, _ = scan_and_check(tmp_path)
    assert any("guards nothing" in e for e in errors), errors


def test_a_workflow_naming_a_missing_script_is_an_error(tmp_path):
    tree(tmp_path, ["check_a.py"],
         [("a.yml", ON_PR + "      - run: python3 scripts/check_a.py\n"
                            "      - run: python3 scripts/check_gone.py\n")])
    errors, _ = scan_and_check(tmp_path)
    assert len(errors) == 1, errors
    assert "does not exist" in errors[0], errors[0]


def test_a_test_module_needs_no_workflow_of_its_own(tmp_path):
    tree(tmp_path, ["check_a.py", "test_check_a.py"],
         [("a.yml", ON_PR + RUN_A + DISCOVER)])
    assert main([str(tmp_path)]) == 0


def test_a_test_module_nothing_discovers_is_an_error(tmp_path):
    tree(tmp_path, ["check_a.py", "test_check_a.py"], [("a.yml", ON_PR + RUN_A)])
    errors, _ = scan_and_check(tmp_path)
    assert len(errors) == 1, errors
    assert "unittest discover" in errors[0], errors[0]


def test_discovery_that_reports_after_the_merge_does_not_count(tmp_path):
    tree(tmp_path, ["check_a.py", "test_check_a.py"],
         [("a.yml", ON_PR + RUN_A), ("late.yml", ON_PUSH + DISCOVER)])
    errors, _ = scan_and_check(tmp_path)
    assert any("unittest discover" in e for e in errors), errors


def test_a_tree_with_no_test_modules_needs_no_discovery(tmp_path):
    tree(tmp_path, ["check_a.py"], [("a.yml", ON_PR + RUN_A)])
    assert main([str(tmp_path)]) == 0


def test_any_pull_request_workflow_satisfies_coverage(tmp_path):
    tree(tmp_path, ["check_a.py", "check_b.py"],
         [("shared.yml", ON_PR + "      - run: python3 scripts/check_a.py\n"
                                 "      - run: python3 scripts/check_b.py\n")])
    assert main([str(tmp_path)]) == 0


def test_pull_request_inside_an_expression_is_not_a_trigger(tmp_path):
    tree(tmp_path, ["check_a.py"],
         [("a.yml", ON_PUSH + "      - run: echo ${{ github.event.pull_request.number }}\n"
                              "      - run: python3 scripts/check_a.py\n")])
    assert main([str(tmp_path)]) == 1


def test_types_that_exclude_the_open_pr_reports_too_late(tmp_path):
    tree(tmp_path, ["check_a.py"],
         [("a.yml", "on:\n  pull_request:\n    types: [closed]\n" + JOBS + RUN_A)])
    errors, _ = scan_and_check(tmp_path)
    assert len(errors) == 1, errors
    assert "only for closed, all after the decision" in errors[0], errors[0]


def test_types_listed_as_a_block_are_read_the_same_way(tmp_path):
    tree(tmp_path, ["check_a.py"],
         [("a.yml", "on:\n  pull_request:\n    types:\n      - closed\n      - labeled\n"
                    + JOBS + RUN_A)])
    assert main([str(tmp_path)]) == 1


def test_types_that_include_a_preventive_event_still_gate(tmp_path):
    tree(tmp_path, ["check_a.py"],
         [("a.yml", "on:\n  pull_request:\n    types: [opened, synchronize, closed]\n"
                    + JOBS + RUN_A)])
    assert main([str(tmp_path)]) == 0


def test_a_path_filtered_trigger_is_not_coverage(tmp_path):
    tree(tmp_path, ["check_a.py"],
         [("a.yml", "on:\n  pull_request:\n    paths:\n      - 'docs/**'\n" + JOBS + RUN_A)])
    errors, _ = scan_and_check(tmp_path)
    assert len(errors) == 1, errors
    assert "selected paths" in errors[0], errors[0]


def test_paths_ignore_is_a_filter_too(tmp_path):
    tree(tmp_path, ["check_a.py"],
         [("a.yml", "on:\n  pull_request:\n    paths-ignore:\n      - '**.md'\n" + JOBS + RUN_A)])
    assert main([str(tmp_path)]) == 1


def test_a_branch_filter_on_the_pr_target_is_not_a_path_filter(tmp_path):
    tree(tmp_path, ["check_a.py"],
         [("a.yml", "on:\n  pull_request:\n    branches: [main]\n" + JOBS + RUN_A)])
    assert main([str(tmp_path)]) == 0


def test_a_push_path_filter_does_not_disqualify_the_pr_trigger(tmp_path):
    tree(tmp_path, ["check_a.py"],
         [("a.yml", "on:\n  push:\n    paths:\n      - 'docs/**'\n  pull_request:\n"
                    + JOBS + RUN_A)])
    assert main([str(tmp_path)]) == 0


def test_the_flow_sequence_form_of_on_is_a_pull_request_trigger(tmp_path):
    tree(tmp_path, ["check_a.py"], [("a.yml", "on: [push, pull_request]\n" + JOBS + RUN_A)])
    assert main([str(tmp_path)]) == 0


def test_a_quoted_on_key_is_still_the_trigger_block(tmp_path):
    tree(tmp_path, ["check_a.py"], [("a.yml", '"on":\n  pull_request:\n' + JOBS + RUN_A)])
    assert main([str(tmp_path)]) == 0


def test_pull_request_target_is_not_matched_as_pull_request(tmp_path):
    tree(tmp_path, ["check_a.py"],
         [("a.yml", "on:\n  pull_request_target:\n    types: [closed]\n" + JOBS + RUN_A)])
    assert main([str(tmp_path)]) == 1


def test_no_workflows_at_all_orphans_every_checker(tmp_path):
    tree(tmp_path, ["check_a.py", "check_b.py"])
    errors, _ = scan_and_check(tmp_path)
    assert len(errors) == 2, errors


def test_a_tree_with_no_checkers_is_clean(tmp_path):
    tree(tmp_path, [], [("a.yml", ON_PR + "      - run: echo hi\n")])
    assert main([str(tmp_path)]) == 0


def scan_and_check(root):
    checkers, named, gating, why, discovers = scan(root)
    present = {p.name for p in (root / "scripts").glob("*.py")}
    return check(checkers, named, gating, present, why, discovers)


def load_tests(loader, tests, pattern):
    """Expose the bare `test_*` functions above to `unittest discover`.

    The repo's CI step is `python3 -m unittest discover -s scripts`, which
    collects TestCase subclasses only. A module of bare functions collects
    *zero* tests and reports OK — a green wall in front of an empty room. This
    adapter registers each one and supplies the temp directory pytest would
    have injected as `tmp_path`, so one suite runs under both runners.
    """
    suite = unittest.TestSuite()
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue

        def run(case, fn=fn):
            if fn.__code__.co_argcount:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()

        suite.addTest(type(name, (unittest.TestCase,), {name: run})(name))
    return suite


if __name__ == "__main__":
    unittest.main(verbosity=2)
