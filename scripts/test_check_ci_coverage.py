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
         [("a.yml", ON_PR + "      - run: python3 scripts/check_a.py\n")])
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


def test_no_workflows_at_all_orphans_every_checker(tmp_path):
    tree(tmp_path, ["check_a.py", "check_b.py"])
    errors, _ = scan_and_check(tmp_path)
    assert len(errors) == 2, errors


def test_a_tree_with_no_checkers_is_clean(tmp_path):
    tree(tmp_path, [], [("a.yml", ON_PR + "      - run: echo hi\n")])
    assert main([str(tmp_path)]) == 0


def scan_and_check(root):
    checkers, named, gating = scan(root)
    return check(checkers, named, gating, {p.name for p in (root / "scripts").glob("*.py")})


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
