"""Offline smoke tests. Run: python -m unittest discover tests"""
import datetime as dt
import tempfile
import textwrap
import unittest
from pathlib import Path

from lxml import etree

from profilecard import cli
from profilecard.config import ConfigError, load
from profilecard.layout import LINE_W, dots, layout, uptime
from profilecard.templates import links, neofetch, pacman

ROOT = Path(__file__).resolve().parent.parent
BASE = textwrap.dedent("""\
    github_username: octocat
    name: Test User
    birthday: 2000-01-31
    info:
      - OS: Linux
      - Uptime: "{uptime}"
      - ""
      - Languages.Real: English
    contact:
      - Email: a@b.c
    links:
      - {type: website, url: "https://a.b"}
      - {type: email, url: a@b.c}
""")


def write_cfg(tmp: str, text: str = BASE) -> Path:
    p = Path(tmp) / "profile.yaml"
    p.write_text(text, encoding="utf-8")
    return p


class ConfigTests(unittest.TestCase):
    def test_shipped_configs_load(self):
        for p in (ROOT / "profile.yaml", ROOT / "examples" / "ranupane" / "profile.yaml"):
            cfg = load(p)
            self.assertTrue(cfg.username)
            self.assertTrue(cfg.info)

    def test_bad_link_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write_cfg(tmp, BASE + "  - {type: nope, url: x}\n")
            with self.assertRaises(ConfigError):
                load(p)

    def test_bad_info_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write_cfg(tmp, "github_username: a\ninfo:\n  - just a string\n")
            with self.assertRaises(ConfigError):
                load(p)

    def test_email_gets_mailto(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load(write_cfg(tmp))
            self.assertEqual(cfg.links[1].url, "mailto:a@b.c")


class RenderTests(unittest.TestCase):
    def test_build_produces_valid_svg_and_snippet(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load(write_cfg(tmp))
            cli.cmd_build(cfg, None)
            files = list(cfg.output_dir.rglob("*.svg"))
            self.assertEqual(len(files), 2 + 2 * 2)  # 2 cards + 2 links x 2 themes
            for f in files:
                etree.parse(str(f))  # well-formed
            self.assertIn("1-website", (cfg.output_dir / "snippet.md").read_text())

    def test_no_birthday_drops_uptime_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load(write_cfg(tmp, BASE.replace("birthday: 2000-01-31\n", "")))
            self.assertNotIn("Uptime", neofetch.build(cfg, "dark"))

    def test_rebuild_keeps_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load(write_cfg(tmp))
            neofetch.render(cfg)
            path = neofetch.out_path(cfg, "dark")
            tree = etree.parse(str(path))
            tree.getroot().find(".//*[@id='repo_data']").text = "42"
            tree.write(str(path), encoding="utf-8", xml_declaration=True)
            neofetch.render(cfg)
            self.assertEqual(etree.parse(str(path)).getroot().find(".//*[@id='repo_data']").text, "42")

    def test_link_geometry_fits_card(self):
        for n in range(2, 6):
            slot, button, gap = links.geometry(n)
            self.assertAlmostEqual(n * button + (n - 1) * gap, neofetch.WIDTH, places=6)
            self.assertEqual(button % links.PX, 0)
        _, button, gap = links.geometry(1)  # a single button spans the card, within one pixel step
        self.assertEqual(gap, 0)
        self.assertLessEqual(neofetch.WIDTH - button, links.PX)

    def test_custom_colors(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load(write_cfg(tmp, BASE + 'colors:\n  dark:\n    key: "#123456"\n'))
            self.assertIn("#123456", neofetch.build(cfg, "dark"))
            self.assertNotIn("#123456", neofetch.build(cfg, "light"))


class LayoutTests(unittest.TestCase):
    def test_dots_width(self):
        for w in range(0, 20):
            self.assertEqual(len(dots(w)), max(w, 0))

    def test_layout_rows_are_right_aligned(self):
        v = layout(dict(age_data="1 year", repo_data=3, contrib_data=4, star_data=5,
                        commit_data=6, follower_data=7, loc_data=8, loc_add=9, loc_del=1))
        row = ". Uptime:" + v["age_data_dots"] + v["age_data"]
        self.assertEqual(len(row), LINE_W)

    def test_uptime(self):
        self.assertEqual(uptime(dt.date(2000, 1, 31), dt.date(2022, 5, 1)), "22 years, 3 months, 1 day")


def fake_pacman_svg(today: dt.date) -> str:
    """Minimal stand-in for the generator's output: one eaten square per active day."""
    cells = []
    end_dow = (today.weekday() + 1) % 7
    start = today - dt.timedelta(days=52 * 7 + end_dow)
    for n, d in enumerate([today - dt.timedelta(days=k) for k in (0, 1, 2)]):
        w, dow = (d - start).days // 7, (d.weekday() + 1) % 7
        t = 0.2 + 0.2 * n
        cells.append(f'<rect id="c-{w}-{dow}" x="0" y="0" fill="#ebedf0"><animate attributeName="fill" '
                     f'dur="10000ms" repeatCount="indefinite" calcMode="discrete" '
                     f'values="#216e39;#ebedf0;#ebedf0" keyTimes="0;{t};1"/></rect>')
    return (f'<svg width="900" height="200"><generatedOn>{today.isoformat()}T00:00:00Z</generatedOn>'
            f'<g id="pacman"><animate dur="10000ms" repeatCount="indefinite" values="1;2" keyTimes="0;1"/></g>'
            + "".join(cells) + "</svg>")


class PacmanTests(unittest.TestCase):
    def test_counter_totals_match_calendar(self):
        today = dt.date(2026, 6, 15)
        calendar = {today: 5, today - dt.timedelta(days=1): 3, today - dt.timedelta(days=2): 2}
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load(write_cfg(tmp))
            path = Path(tmp) / "p.svg"
            path.write_text(fake_pacman_svg(today), encoding="utf-8")
            total = pacman.process(path, "dark", calendar, cfg)
            self.assertEqual(total, 10)
            out = path.read_text(encoding="utf-8")
            etree.fromstring(out.encode())
            self.assertIn(">10<", out)
            self.assertIn('height="226"', out)  # 200 + EXTRA_H
            self.assertIn("Contributions", out)


if __name__ == "__main__":
    unittest.main()
