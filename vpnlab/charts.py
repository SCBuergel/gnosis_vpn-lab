"""Charts for result folders, written as plain SVG so they render on GitHub without any tool."""

from __future__ import annotations

import csv
from pathlib import Path
from xml.sax.saxutils import escape

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#1f1f1d", "#6b6a63", "#e4e3dd"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")  # fixed order: first build, second build, ...
FONT = "font-family='system-ui, -apple-system, Segoe UI, Helvetica, Arial, sans-serif'"


def read_rates(folder: Path) -> dict[str, list[float]]:
    """Megabytes per second for every column of bytes-per-second.csv."""
    with (folder / "bytes-per-second.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    names = [name for name in rows[0] if name != "second"] if rows else []
    return {name: [int(row[name]) / 1e6 for row in rows if row[name] != ""] for name in names}


def rate_panels(
    panels: list[tuple[str, str, list[list[float]]]], seconds: int, title: str, subtitle: str, columns: int = 2
) -> str:
    """Small multiples of download rate per second: one panel per (title, colour, runs).

    Every panel has the same axes, so panels compare by eye. Runs of one panel share its colour and are
    drawn as thin lines over each other.
    """
    top = max((value for _, _, runs in panels for run in runs for value in run), default=1.0)
    y_max = float(max(1, int(top) + 1))  # next whole megabyte
    panel_w, panel_h, left, gap_x, gap_y, head = 400, 150, 54, 46, 62, 86
    rows = (len(panels) + columns - 1) // columns
    width = left + columns * panel_w + (columns - 1) * gap_x + 24
    height = head + rows * (panel_h + gap_y)
    out = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}' "
        f"role='img' aria-label='{escape(title)}'>",
        f"<rect width='{width}' height='{height}' fill='{SURFACE}'/>",
        f"<text x='{left}' y='28' {FONT} font-size='16' font-weight='600' fill='{INK}'>{escape(title)}</text>",
        f"<text x='{left}' y='48' {FONT} font-size='12' fill='{MUTED}'>{escape(subtitle)}</text>",
    ]
    x_ticks = [tick for tick in range(0, seconds + 1, 30)]
    y_step = 1 if y_max <= 6 else 2
    y_ticks = [float(tick) for tick in range(0, int(y_max) + 1, y_step)]
    for index, (name, colour, runs) in enumerate(panels):
        x0 = left + (index % columns) * (panel_w + gap_x)
        y0 = head + (index // columns) * (panel_h + gap_y)
        out.append(
            f"<text x='{x0}' y='{y0 - 10}' {FONT} font-size='12' font-weight='600' fill='{INK}'>{escape(name)}</text>"
        )
        for tick in y_ticks:
            y = y0 + panel_h - tick / y_max * panel_h
            out.append(f"<line x1='{x0}' y1='{y:.1f}' x2='{x0 + panel_w}' y2='{y:.1f}' stroke='{GRID}'/>")
            out.append(
                f"<text x='{x0 - 6}' y='{y + 4:.1f}' {FONT} font-size='10' fill='{MUTED}' text-anchor='end'>"
                f"{tick:g}</text>"
            )
        for tick in x_ticks:
            x = x0 + tick / seconds * panel_w
            out.append(
                f"<text x='{x:.1f}' y='{y0 + panel_h + 14}' {FONT} font-size='10' fill='{MUTED}' "
                f"text-anchor='middle'>{tick}</text>"
            )
        for run in runs:
            points = " ".join(
                f"{x0 + (second + 0.5) / seconds * panel_w:.1f},{y0 + (1 - min(value, y_max) / y_max) * panel_h:.1f}"
                for second, value in enumerate(run[:seconds])
            )
            out.append(
                f"<polyline points='{points}' fill='none' stroke='{colour}' stroke-width='1.3' "
                "stroke-linejoin='round' stroke-opacity='0.7'/>"
            )
        if index % columns == 0:
            out.append(
                f"<text transform='translate({x0 - 38},{y0 + panel_h / 2}) rotate(-90)' {FONT} font-size='10' "
                f"fill='{MUTED}' text-anchor='middle'>MB per second</text>"
            )
        if index // columns == rows - 1:
            out.append(
                f"<text x='{x0 + panel_w / 2}' y='{y0 + panel_h + 32}' {FONT} font-size='10' fill='{MUTED}' "
                "text-anchor='middle'>seconds after the download started</text>"
            )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def comparison_chart(folder: Path, seconds: int) -> Path:
    """download-rate.svg for a compare-builds folder: one panel per build and Blokli lag."""
    rates = read_rates(folder)
    with (folder / "iterations.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    builds = list(dict.fromkeys(row["build"] for row in rows))
    lags = sorted({float(row["blokli_lag_s"]) for row in rows})
    panels = []
    for lag in lags:
        for build in builds:
            keys = [
                f"{int(row['connect']):02d}_{build}_lag{lag:g}"
                for row in rows
                if row["build"] == build and float(row["blokli_lag_s"]) == lag
            ]
            runs = [rates[key] for key in keys if key in rates]
            condition = "Blokli on time" if lag == 0 else f"new notes reported {lag:g} s late"
            panels.append((f"{build}, {condition} ({len(runs)} connects)", SERIES[builds.index(build)], runs))
    svg = rate_panels(
        panels,
        seconds,
        "Download rate, second by second",
        "One line per connect; every panel has the same axes. The download starts the moment the client is connected.",
        columns=len(builds),
    )
    path = folder / "download-rate.svg"
    path.write_text(svg)
    return path
