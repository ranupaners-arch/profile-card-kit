"""Monospace column layout shared by the card template and the stats updater."""
from __future__ import annotations

import datetime as dt

from dateutil import relativedelta

LINE_W = 72   # width of an info row, in characters
COL = 44      # column of the " | " separator


def dots(width: int) -> str:
    """Filler `width` characters wide: ' ..... '."""
    if width <= 0:
        return ""
    if width == 1:
        return " "
    if width == 2:
        return ". "
    return " " + "." * (width - 2) + " "


def fmt(n) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


def layout(v: dict) -> dict:
    """Return {id: text} for every dynamic value plus its right-aligning dots."""
    out = {k: fmt(x) for k, x in v.items()}
    # . Uptime: ...... 22 years, 4 months, 16 days
    out["age_data_dots"] = dots(LINE_W - len(". Uptime:") - len(out["age_data"]))
    # . Repos: .. 12 {Contributed: 15} | Stars: ...... 3
    left = len(". Repos:") + len(out["repo_data"]) + len(" {Contributed: ") + len(out["contrib_data"]) + 1
    out["repo_data_dots"] = dots(COL - left)
    out["star_data_dots"] = dots(LINE_W - COL - len(" | Stars:") - len(out["star_data"]))
    # . Commits: ...... 1,234 | Followers: ..... 5
    out["commit_data_dots"] = dots(COL - len(". Commits:") - len(out["commit_data"]))
    out["follower_data_dots"] = dots(LINE_W - COL - len(" | Followers:") - len(out["follower_data"]))
    # . Lines of Code on GitHub: ... 12,345 ( 15,000++, 2,655-- )
    tail = len(" ( ") + len(out["loc_add"]) + len("++, ") + len(out["loc_del"]) + len("-- )")
    out["loc_data_dots"] = dots(LINE_W - len(". Lines of Code on GitHub:") - len(out["loc_data"]) - tail)
    return out


def uptime(birthday: dt.date, today: dt.date | None = None) -> str:
    """'22 years, 4 months, 16 days' since `birthday`."""
    today = today or dt.date.today()
    diff = relativedelta.relativedelta(today, birthday)

    def pl(n: int) -> str:
        return "s" if n != 1 else ""

    return "{} year{}, {} month{}, {} day{}{}".format(
        diff.years, pl(diff.years), diff.months, pl(diff.months), diff.days, pl(diff.days),
        " \U0001F382" if (diff.months == 0 and diff.days == 0) else "",
    )
