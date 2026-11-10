"""neofetch-style card: ASCII portrait on the left, info and live GitHub stats on the right.

Dynamic values carry an id (age_data, repo_data, ...). `render` writes the static
card; `update_stats` refills those ids from the GitHub API.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from lxml import etree

from .. import ascii_art, github, layout as lay
from ..config import UPTIME_TOKEN, Config
from ..layout import LINE_W, dots, fmt, layout
from ..themes import resolve

NAME = "neofetch"
WIDTH, HEIGHT = 1100, 550
ASCII_X, INFO_X, TOP, LH = 15, 390, 30, 20
ASCII_FS, ASCII_LH = 12, 14

# Starting values before `stats` has run.
SAMPLE = dict(age_data="0 years, 0 months, 0 days", repo_data=0, contrib_data=0,
              star_data=0, commit_data=0, follower_data=0, loc_data=0, loc_add=0, loc_del=0)


def out_path(cfg: Config, theme: str) -> Path:
    return cfg.output_dir / NAME / f"{theme}.svg"


def rule(label: str) -> str:
    """'label -————...-—-' as wide as LINE_W."""
    n = LINE_W - len(label) - len(" -") - len("-—-")
    return " -" + "—" * max(n, 3) + "-—-"


def key(k: str) -> str:
    return ".".join(f'<tspan class="key">{escape(p)}</tspan>' for p in k.split("."))


def tspan(y: int, body: str = "") -> str:
    return f'<tspan x="{INFO_X}" y="{y}" class="cc">. </tspan>{body}'


def kv(y: int, k: str, v: str) -> str:
    if not k:  # continuation row: ("", "value") has no label
        d = dots(LINE_W - len(". ") - len(v))
        return tspan(y, f'<tspan class="cc">{d}</tspan><tspan class="value">{escape(v)}</tspan>')
    d = dots(LINE_W - len(". ") - len(k) - 1 - len(v))
    return tspan(y, f'{key(k)}:<tspan class="cc">{d}</tspan><tspan class="value">{escape(v)}</tspan>')


def current_values(cfg: Config, theme: str) -> dict:
    """Stats already in the SVG, so a rebuild does not reset them to zero."""
    vals = dict(SAMPLE)
    path = out_path(cfg, theme)
    if path.exists():
        root = etree.parse(str(path)).getroot()
        for k in SAMPLE:
            el = root.find(f".//*[@id='{k}']")
            if el is not None and el.text:
                vals[k] = el.text
    return vals


def build(cfg: Config, theme: str, values: dict | None = None) -> str:
    c = resolve(cfg.colors)[theme]
    v = layout(values if values is not None else current_values(cfg, theme))
    s = lambda i: f'<tspan class="value" id="{i}">{escape(v[i])}</tspan>'  # noqa: E731
    d = lambda i: f'<tspan class="cc" id="{i}_dots">{v[i + "_dots"]}</tspan>'  # noqa: E731
    art = ascii_art.load(cfg.ascii_path)

    out = [f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,Menlo,monospace" width="{WIDTH}px" height="{HEIGHT}px" font-size="16px">
<style>
@font-face {{
src: local('Consolas'), local('Consolas Bold');
font-family: 'ConsolasFallback';
font-display: swap;
-webkit-size-adjust: 109%;
size-adjust: 109%;
}}
.key {{fill: {c['key']};}}
.value {{fill: {c['value']};}}
.addColor {{fill: {c['add']};}}
.delColor {{fill: {c['dele']};}}
.cc {{fill: {c['cc']};}}
text, tspan {{white-space: pre;}}
</style>
<rect width="{WIDTH}px" height="{HEIGHT}px" fill="{c['bg']}" rx="15"/>
<text x="{ASCII_X}" y="{TOP}" fill="{c['fg']}" font-size="{ASCII_FS}px" class="ascii">"""]
    for i, row in enumerate(art):
        out.append(f'<tspan x="{ASCII_X}" y="{TOP + i * ASCII_LH}">{escape(row)}</tspan>')
    out.append(f'</text>\n<text x="{INFO_X}" y="{TOP}" fill="{c["fg"]}">')

    y = TOP
    out.append(f'<tspan x="{INFO_X}" y="{y}">{escape(cfg.name)}</tspan>{rule(cfg.name)}')
    for item in cfg.info:
        if item is not None and item[1] == UPTIME_TOKEN and cfg.birthday is None:
            continue  # no birthday configured: drop the Uptime row
        y += LH
        if item is None:
            out.append(tspan(y))
        elif item[1] == UPTIME_TOKEN:
            out.append(tspan(y, f'{key(item[0])}:{d("age_data")}{s("age_data")}'))
        else:
            out.append(kv(y, *item))
    if cfg.contact:
        y += 2 * LH
        out.append(f'<tspan x="{INFO_X}" y="{y}">- Contact</tspan>{rule("- Contact")}')
        for item in cfg.contact:
            y += LH
            out.append(tspan(y) if item is None else kv(y, *item))
    y += 2 * LH
    out.append(f'<tspan x="{INFO_X}" y="{y}">- GitHub Stats</tspan>{rule("- GitHub Stats")}')
    y += LH
    out.append(tspan(y, f'{key("Repos")}:{d("repo_data")}{s("repo_data")} {{{key("Contributed")}: '
                        f'{s("contrib_data")}}} | {key("Stars")}:{d("star_data")}{s("star_data")}'))
    y += LH
    out.append(tspan(y, f'{key("Commits")}:{d("commit_data")}{s("commit_data")} | '
                        f'{key("Followers")}:{d("follower_data")}{s("follower_data")}'))
    y += LH
    out.append(tspan(y, f'{key("Lines of Code on GitHub")}:{d("loc_data")}{s("loc_data")} ( '
                        f'<tspan class="addColor" id="loc_add">{v["loc_add"]}</tspan><tspan class="addColor">++</tspan>, '
                        f'<tspan class="delColor" id="loc_del">{v["loc_del"]}</tspan><tspan class="delColor">--</tspan> )'))
    y += 2 * LH
    # Blinking prompt cursor.
    out.append(f'<tspan x="{INFO_X}" y="{y}" class="key">&gt; </tspan><tspan class="value">█'
               '<animate attributeName="opacity" values="1;0" dur="1.06s" calcMode="discrete" '
               'repeatCount="indefinite"/></tspan>')
    out.append("</text>\n</svg>\n")
    # The card grows to fit extra rows or a taller portrait.
    h = max(HEIGHT, y + 20, TOP + (len(art) - 1) * ASCII_LH + 14)
    out[0] = out[0].replace(f'height="{HEIGHT}px"', f'height="{h}px"')
    return "\n".join(out)


def render(cfg: Config, values: dict | None = None, out_dir: Path | None = None) -> list[Path]:
    """Write dark.svg and light.svg. Returns the paths written."""
    paths = []
    for theme in resolve(cfg.colors):
        path = (out_dir / f"{theme}.svg") if out_dir else out_path(cfg, theme)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(build(cfg, theme, values), encoding="utf-8")
        paths.append(path)
    return paths


def collect(cfg: Config) -> dict:
    info = github.user_info(cfg.username)
    contributed = github.all_repos(cfg.username, "[OWNER, COLLABORATOR, ORGANIZATION_MEMBER]")
    owned = [r for r in contributed if r["nameWithOwner"].split("/")[0].lower() == cfg.username.lower()]
    add, dele, commits = github.loc_query(cfg.username, contributed, info["id"], cfg.cache_dir)
    return {
        "age_data": lay.uptime(cfg.birthday) if cfg.birthday else SAMPLE["age_data"],
        "repo_data": info["repos"],
        "contrib_data": len(contributed),
        "star_data": sum(r["stargazerCount"] for r in owned),
        "commit_data": commits,
        "follower_data": info["followers"],
        "loc_data": add - dele,
        "loc_add": add,
        "loc_del": dele,
    }


def update_stats(cfg: Config) -> dict:
    """Fetch stats from GitHub and write them into the existing cards."""
    for theme in resolve(cfg.colors):
        if not out_path(cfg, theme).exists():
            render(cfg)  # first run: create the cards
            break
    values = collect(cfg)
    print(json.dumps({k: fmt(x) for k, x in values.items()}, ensure_ascii=False, indent=2))
    texts = layout(values)
    for theme in resolve(cfg.colors):
        path = out_path(cfg, theme)
        tree = etree.parse(str(path))
        for k, text in texts.items():
            el = tree.getroot().find(f".//*[@id='{k}']")
            if el is not None:
                el.text = text
        tree.write(str(path), encoding="utf-8", xml_declaration=True)
        print(f"updated: {path}")
    return values
