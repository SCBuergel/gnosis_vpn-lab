#!/usr/bin/env python3
"""Summarise ladder runs per step. Usage: ladder-pack.py RAW_DIR... (prints a Markdown table per run).

A download counts in the step in which it started.
"""
import re
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path


def ts(stamp: str) -> float:
    return datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC).timestamp()


for raw in map(Path, sys.argv[1:]):
    start, t1, end = (int((raw / n).read_text()) for n in ("start", "t1", "end"))
    steps = [line.split() for line in (raw / "steps.txt").read_text().splitlines()]
    # The measurement starts with the ping; the baseline ends at the first cut.
    pings = {}
    for line in (raw / "ping.txt").read_text().splitlines():
        m = re.match(r"\[(\d+\.\d+)\] .*icmp_seq=(\d+).*time=([\d.]+) ms", line)
        if m:
            pings[int(m.group(2))] = (float(m.group(1)), float(m.group(3)))
    first = min(t for t, _ in pings.values()) - 0.2 * min(pings)
    # The ping and the download loop stop on a fixed timeout: "load total=N" in phases.txt, or
    # base + fail + after + 30 s in the runs of 2026-11-26, which did not log it.
    # while the steps overrun by a few seconds each, so the last step is only partly covered.
    phases = (raw / "phases.txt").read_text()
    m = re.search(r"load total=(\d+)", phases)
    total = int(m.group(1)) if m else sum(map(int, re.search(r"base=(\d+) fail=(\d+) after=(\d+)", phases).groups())) + 30
    ping_end = first + total
    bounds = [(first, "baseline", "-", 9)]
    bounds += [(int(t), ("cut " if len(p) == 4 else "") + " ".join(p[1:-2]), "-", int(p[-1])) for p in steps for t in [p[0]]]
    bounds.append((t1, "all cuts removed", "-", 9))
    downloads = []
    for line in (raw / "curl.txt").read_text().splitlines():
        p = line.split()
        if len(p) == 3:
            downloads.append((int(p[0]), int(p[1]), float(p[2])))
    losses = []
    for line in (raw / "client-worker.full.log").read_text(errors="replace").splitlines():
        if "loss_report" in line:
            m = re.search(r"emitted=(\d+) discarded=(\d+)", line)
            if m:
                losses.append((ts(line), int(m.group(1)), int(m.group(2))))
    events = [
        (ts(line), re.search(r"surb_telemetry: (.*?) relayer=", line).group(1))
        for line in (raw / "client-worker.full.log").read_text(errors="replace").splitlines()
        if "surb_telemetry" in line and re.search(r"judged dead|revived|lapsed", line)
    ]
    print(f"\n### {raw.name}\n")
    print("| step | relays left | downloads done/started | Mbit/s min | median | max | ping loss | ping median ms | frames discarded/emitted | judged dead, revived |")
    print_note = lambda: print(f"\nThe ping ran for the first {ping_end - bounds[-1][0]:.0f} s of the last step; its ping loss covers that time only.")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for i, (a, name, addr, left) in enumerate(bounds):
        b = bounds[i + 1][0] if i + 1 < len(bounds) else end - 35
        d = [(size, secs) for t, size, secs in downloads if a <= t < b]
        ok = [size * 8 / secs / 1e6 for size, secs in d if size >= 2000001]
        got = sorted(r for t, r in pings.values() if a <= t < b)
        expected = max(1, round((min(b, ping_end) - a) / 0.2))
        emitted = sum(e for t, e, _ in losses if a <= t < b)
        discarded = sum(x for t, _, x in losses if a <= t < b)
        dead = sum(1 for t, e in events if a <= t < b and "judged dead" in e)
        rev = sum(1 for t, e in events if a <= t < b and "revived" in e)
        rate = (f"{min(ok):.1f} | {statistics.median(ok):.1f} | {max(ok):.1f}") if ok else "- | - | -"
        print(
            f"| {name} | {left} | {len(ok)}/{len(d)} | {rate} | {max(0.0, 1 - len(got) / expected) * 100:.1f}% | "
            f"{got[len(got) // 2] if got else '-'} | {discarded}/{emitted} | {dead}, {rev} |"
        )
    print_note()
