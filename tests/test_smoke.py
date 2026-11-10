"""Offline smoke tests. Run: python -m unittest discover tests"""
import contextlib
import datetime as dt
import io
import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from unittest import mock

import requests
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


class YamlTextTests(unittest.TestCase):
    def test_values_stay_as_typed(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load(write_cfg(tmp, "github_username: a\ninfo:\n  - Pets: no\n  - Remote: yes\n"
                                       "  - Version: 1.10\n  - Zip: 01234\n  - Since: 2020-01-01\n"))
            self.assertEqual(cfg.info, [("Pets", "no"), ("Remote", "yes"), ("Version", "1.10"),
                                        ("Zip", "01234"), ("Since", "2020-01-01")])

    def test_birthday_is_still_a_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load(write_cfg(tmp)).birthday, dt.date(2000, 1, 31))

    def test_pacman_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(load(write_cfg(tmp)).pacman)
            off = load(write_cfg(tmp, BASE + "pacman: false\n"))
            self.assertFalse(off.pacman)
            self.assertNotIn("pacman", cli.write_snippet(off).read_text())
            with self.assertRaises(ConfigError):
                load(write_cfg(tmp, BASE + "pacman: maybe\n"))

    def test_ci_info(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("USER_NAME", None)
            cfg = load(write_cfg(tmp))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.cmd_ci_info(cfg, None)
            self.assertEqual(buf.getvalue().split(), ["username=octocat", "pacman=true"])

    def test_username_falls_back_to_repository_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cfg(tmp, "name: x\n")
            with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY_OWNER": "someone"}):
                os.environ.pop("USER_NAME", None)
                self.assertEqual(load(path).username, "someone")


class GithubTests(unittest.TestCase):
    def reply(self, status, payload=None):
        r = mock.Mock(status_code=status, text="boom")
        r.json.return_value = payload or {}
        return r

    def test_retries_server_errors_then_succeeds(self):
        from profilecard import github
        ok = self.reply(200, {"data": {"x": 1}})
        with mock.patch.object(github, "token", return_value="t"), mock.patch.object(github.time, "sleep"), \
                mock.patch.object(github.requests, "post", side_effect=[self.reply(502), self.reply(502), ok]) as post:
            self.assertEqual(github.gql("q", {}), {"x": 1})
            self.assertEqual(post.call_count, 3)

    def test_gives_up_with_a_clear_message(self):
        from profilecard import github
        with mock.patch.object(github, "token", return_value="t"), mock.patch.object(github.time, "sleep"), \
                mock.patch.object(github.requests, "post", side_effect=requests.ConnectionError("down")):
            with self.assertRaisesRegex(RuntimeError, "failed after 3 attempts"):
                github.gql("q", {})

    def test_bad_token_is_not_retried(self):
        from profilecard import github
        with mock.patch.object(github, "token", return_value="t"), \
                mock.patch.object(github.requests, "post", return_value=self.reply(401)) as post:
            with self.assertRaisesRegex(RuntimeError, "rejected the token"):
                github.gql("q", {})
            self.assertEqual(post.call_count, 1)

    def test_cli_reports_api_errors_without_traceback(self):
        from profilecard import github
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cfg(tmp)
            err = io.StringIO()
            with mock.patch.object(github, "user_info", side_effect=RuntimeError("no such user")), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(["-c", str(path), "stats"])
            self.assertEqual(code, 1)
            self.assertIn("error: no such user", err.getvalue())


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


class AsciiTests(unittest.TestCase):
    def test_placeholder_fits_grid(self):
        from profilecard import ascii_art
        art = ascii_art.placeholder()
        self.assertEqual(len(art), ascii_art.ROWS)
        self.assertLessEqual(max(map(len, art)), ascii_art.COLS)

    def test_too_wide_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "wide.txt").write_text("x" * 80 + "\n")
            cfg = load(write_cfg(tmp, BASE + "ascii: wide.txt\n"))
            with self.assertRaises(ConfigError):
                neofetch.build(cfg, "dark")

    def test_taller_portrait_grows_the_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tall.txt").write_text("\n".join(["x" * 10] * 60) + "\n")
            cfg = load(write_cfg(tmp, BASE + "ascii: tall.txt\n"))
            svg = neofetch.build(cfg, "dark")
            self.assertNotIn('height="550px"', svg.split("\n")[1])

    def test_non_square_photo_is_not_stretched(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("opencv not installed")
        from profilecard import ascii_art
        tall = np.zeros((600, 400, 3), np.uint8)             # 2:3 portrait
        tall[:, :200] = (255, 255, 255)                      # left half white, right half black
        out = ascii_art.to_square(tall)
        self.assertEqual(out.shape[:2], (400, 400))
        row = out[200, :, 0]
        edge = int(np.argmax(row < 128))                     # where white turns black
        self.assertAlmostEqual(edge, 200, delta=3)           # centre of the canvas: halves stay equal

    def test_backdrop_mask_handles_shadow_but_keeps_skin_and_hair(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("opencv not installed")
        from profilecard import ascii_art
        # Cream wall, bright at the top and fading to a deep shadow on the right.
        wall_lab = np.zeros((400, 400, 3), np.float32)
        xs = np.linspace(0, 1, 400)[None, :]
        wall_lab[..., 0] = 225 - 95 * xs ** 2                 # lightness 225 -> 130
        wall_lab[..., 1] = 128 - 1.0 * xs                     # hue barely moves
        wall_lab[..., 2] = 134 + 9.0 * xs
        img = cv2.cvtColor(np.clip(wall_lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
        cv2.circle(img, (150, 220), 62, cv2.cvtColor(np.uint8([[[170, 140, 142]]]), cv2.COLOR_LAB2BGR)[0, 0].tolist(), -1)  # skin
        cv2.ellipse(img, (150, 170), (66, 40), 0, 180, 360, (20, 20, 20), -1)                                                # hair
        bg = ascii_art.backdrop_mask(img)
        self.assertEqual(bg[40, 20], 1)        # lit wall
        self.assertEqual(bg[200, 380], 1)      # deep shadow on the wall
        self.assertEqual(bg[240, 150], 0)      # skin kept
        self.assertEqual(bg[160, 150], 0)      # dark hair kept

    def test_auto_mode_on_synthetic_portrait(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("opencv not installed")
        from profilecard import ascii_art
        img = np.full((400, 400, 3), (200, 80, 20), np.uint8)       # plain blue backdrop
        cv2.circle(img, (200, 150), 70, (120, 150, 200), -1)         # head
        cv2.rectangle(img, (150, 215), (250, 400), (120, 150, 200), -1)  # neck and body
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "p.png")
            cv2.imwrite(path, img)
            lines = ascii_art.from_image(path, auto=True).split("\n")
        self.assertEqual(len(lines), ascii_art.ROWS)
        self.assertLessEqual(max(map(len, lines)), ascii_art.COLS)
        self.assertTrue(any(line.strip() for line in lines[:20]))   # head found
        self.assertEqual(lines[0][:5].strip(), "")                   # backdrop removed at the corner


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
    def test_missing_svgs_give_a_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "generate the Pac-Man SVGs first"):
                pacman.add_counter(load(write_cfg(tmp)))

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
