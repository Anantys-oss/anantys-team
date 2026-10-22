#!/usr/bin/env python3
"""A depth-dependent link is only wrong relative to a layout, so every case names one.

`resolution` is the evidence the gate cannot print: it shows where each link lands
in each feature-directory layout the skill declares, which is what makes `..` a
defect rather than a style choice.
"""

import contextlib
import io
import posixpath
import tempfile
import unittest
from pathlib import Path

import check_template_paths as ctp

# The layouts `anantys.qa` declares a feature directory can take (SKILL.md,
# "Locating the feature"): a spec-kit dir under a configurable `specs_dir`, and
# `.anantys/qa/<slug>/` for every brief-, linear- or PR-derived campaign.
LAYOUTS = (
    "specs/206-checkout",
    "docs/specs/206-checkout",
    ".anantys/qa/sku-231",
)


class Resolution(unittest.TestCase):
    def test_dotdot_link_resolves_differently_per_layout(self) -> None:
        landings = {posixpath.normpath(posixpath.join(b, "../../.anantys/qa.md")) for b in LAYOUTS}
        self.assertEqual(len(landings), len(LAYOUTS))
        self.assertIn(".anantys/.anantys/qa.md", landings)

    def test_dot_link_resolves_inside_every_layout(self) -> None:
        for base in LAYOUTS:
            landing = posixpath.normpath(posixpath.join(base, "./qa-runs.md"))
            self.assertTrue(landing.startswith(base + "/"), landing)


class EscapingLinks(unittest.TestCase):
    def test_flags_parent_segment(self) -> None:
        text = "a\nb\nEnvironment: [`qa.md`](../../.anantys/qa.md).\n"
        self.assertEqual(ctp.escaping_links(text), [(3, "../../.anantys/qa.md")])

    def test_allows_same_directory(self) -> None:
        self.assertEqual(ctp.escaping_links("[a](./tasks.md) [b](brief.md)"), [])

    def test_allows_descending(self) -> None:
        self.assertEqual(ctp.escaping_links("[a](./sub/dir/x.md)"), [])

    def test_ignores_absolute_anchor_and_external(self) -> None:
        text = "[a](/abs.md) [b](#head) [c](https://x/../y) [d](mailto:a@b)"
        self.assertEqual(ctp.escaping_links(text), [])

    def test_does_not_flag_dotdot_inside_a_filename(self) -> None:
        self.assertEqual(ctp.escaping_links("[a](./weird..name.md)"), [])

    def test_tolerates_angle_brackets_and_padding(self) -> None:
        self.assertEqual(ctp.escaping_links("[a](< ../x.md>)"), [])
        self.assertEqual(ctp.escaping_links("[a]( ../x.md)"), [(1, "../x.md")])

    def test_reports_every_offender(self) -> None:
        text = "[a](../x.md)\n[b](./ok.md)\n[c](../../y.md)\n"
        self.assertEqual(ctp.escaping_links(text), [(1, "../x.md"), (3, "../../y.md")])


class Gate(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.dir = self.root / "plugins/p/skills/s/templates"
        self.dir.mkdir(parents=True)
        previous = ctp.ROOT
        ctp.ROOT = self.root
        self.addCleanup(setattr, ctp, "ROOT", previous)

    def run_gate(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ctp.main()
        return code, out.getvalue()

    def test_green_on_contained_links(self) -> None:
        (self.dir / "qa-plan.md").write_text("[a](./tasks.md)\n", encoding="utf-8")
        code, out = self.run_gate()
        self.assertEqual(code, 0)
        self.assertIn("1 templates, 0 escaping link(s)", out)

    def test_red_and_located_on_escaping_link(self) -> None:
        (self.dir / "qa-plan.md").write_text("x\n[a](../../.anantys/qa.md)\n", encoding="utf-8")
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("plugins/p/skills/s/templates/qa-plan.md:2", out)
        self.assertIn("../../.anantys/qa.md", out)

    def test_red_when_no_template_matched(self) -> None:
        for path in self.dir.glob("*.md"):
            path.unlink()
        self.dir.rmdir()
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("no templates matched", out)


class ThisRepo(unittest.TestCase):
    def test_shipped_templates_pass(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(ctp.main(), 0, out.getvalue())


if __name__ == "__main__":
    unittest.main()
