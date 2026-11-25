"""Render the GitHub contribution calendar as a dark-theme SVG heatmap.

Reads the calendar from the GraphQL API, which includes private contributions
(as anonymous counts) when "Private contributions" is enabled on the profile.

Usage: GITHUB_TOKEN=... python3 contrib_graph.py <username> <out.svg>
"""

import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""

# GitHub dark palette, empty -> most active.
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
CELL, GAP = 28, 6
PITCH = CELL + GAP
LEFT, TOP = 52, 84
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"


def fetch_calendar(login: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def level_for(count: int, thresholds: list[int]) -> int:
    """Map a day's count to a colour level 0-4 using quartiles of active days."""
    if count == 0:
        return 0
    for i, t in enumerate(thresholds, start=1):
        if count <= t:
            return i
    return 4


def quartiles(counts: list[int]) -> list[int]:
    active = sorted(c for c in counts if c > 0)
    if not active:
        return [1, 1, 1]
    return [active[min(len(active) - 1, len(active) * q // 4)] for q in (1, 2, 3)]


def render(cal: dict) -> str:
    weeks = cal["weeks"]
    total = cal["totalContributions"]
    width = LEFT + len(weeks) * PITCH + 24
    height = TOP + 7 * PITCH + 46
    thresholds = quartiles([d["contributionCount"] for w in weeks for d in w["contributionDays"]])

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"<style>.t{{font:600 14px {FONT}}}.b{{font:500 11px {FONT}}}.l{{font-family:{FONT};font-size:10px;fill:#8b949e}}</style>",
        f'<rect width="{width}" height="{height}" fill="#0d1117" rx="8"/>',
        f'<rect width="{width}" height="3" fill="#39d353" rx="8"/>',
        '<circle cx="32" cy="28" r="5" fill="#39d353" opacity=".2"/><circle cx="32" cy="28" r="2.5" fill="#39d353"/>',
        '<text x="42" y="32" class="t" fill="#58a6ff">Contributions</text>',
        f'<rect x="{width - 184}" y="14" width="160" height="22" rx="11" fill="#39d353" opacity=".12"/>',
        f'<text x="{width - 104}" y="29" text-anchor="middle" class="b" fill="#39d353">{total:,} contributions</text>',
        f'<line x1="24" y1="60" x2="{width - 24}" y2="60" stroke="#30363d" stroke-width=".5"/>',
    ]

    # Month labels: label the first week whose first day starts a new month.
    last_month = None
    for wi, week in enumerate(weeks):
        month = dt.date.fromisoformat(week["contributionDays"][0]["date"]).month
        if month != last_month:
            if last_month is not None or wi == 0:
                label = dt.date(2000, month, 1).strftime("%b")
                out.append(f'<text x="{LEFT + wi * PITCH}" y="74" class="l">{label}</text>')
            last_month = month

    for wd, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="22" y="{TOP + wd * PITCH + 18}" class="l">{name}</text>')

    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            n = day["contributionCount"]
            x, y = LEFT + wi * PITCH, TOP + day["weekday"] * PITCH
            fill = LEVELS[level_for(n, thresholds)]
            out.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="3" fill="{fill}">'
                f"<title>{escape(day['date'])}: {n}</title></rect>"
            )
            # Shrink the in-cell number so 3-digit days still fit.
            size = 17.36 if n < 10 else 13 if n < 100 else 10
            color, opacity = ("#e6edf3", "1") if n else ("#8b949e", ".55")
            out.append(
                f'<text x="{x + CELL / 2}" y="{y + CELL / 2 + size * 0.35:.1f}" text-anchor="middle" '
                f'font-family="monospace" font-size="{size}" font-weight="700" fill="{color}" '
                f'opacity="{opacity}" pointer-events="none">{n}</text>'
            )

    ly = TOP + 7 * PITCH + 12
    out.append(f'<text x="{LEFT}" y="{ly + 14}" font-family="{FONT}" font-size="11" fill="#8b949e">Less</text>')
    for i, c in enumerate(LEVELS):
        out.append(f'<rect x="{LEFT + 36 + i * 31}" y="{ly}" width="26" height="26" rx="3" fill="{c}"/>')
    out.append(
        f'<text x="{LEFT + 36 + 5 * 31 + 6}" y="{ly + 14}" font-family="{FONT}" font-size="11" fill="#8b949e">More</text>'
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    login, path = sys.argv[1], sys.argv[2]
    svg = render(fetch_calendar(login, os.environ["GITHUB_TOKEN"]))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
