#!/usr/bin/env python3
"""Stalls of the victim's ping in a run of run.sh, with what the exit did at that moment.

Usage: analyze.py RUN_DIR [RUN_DIR ...]

A stall is a run of pings slower than 200 ms with no gap over 2 s. For each one: when its first ping
was sent and its last came back, the nearest "SSA is fully committed" and SURB drop in the exit's log,
and the CPU use of the exit's busiest threads during the stall (100 % = one core).
"""
import collections
import datetime
import gzip
import re
import sys


def analyze(d):
    pings = [
        (float(m.group(1)), float(m.group(2)))
        for m in (re.match(r"\[(\d+\.\d+)\].*time=([\d.]+) ms", line) for line in open(d + "/ping.txt"))
        if m
    ]
    t0 = pings[0][0]
    groups = []
    for back, rtt in pings:
        if rtt <= 200:
            continue
        if groups and back - groups[-1][-1][0] <= 2:
            groups[-1].append((back, rtt))
        else:
            groups.append([(back, rtt)])
    log = [(datetime.datetime.fromisoformat(line.split()[0]).timestamp(), line) for line in gzip.open(d + "/exit.log.gz", "rt")]
    committed = [t for t, line in log if "fully committed for verification" in line]
    drops = [t for t, line in log if "no SURB" in line]
    samples = collections.defaultdict(dict)
    for line in open(d + "/threads.txt"):
        t, tid, _name, ticks = line.split()
        samples[float(t)][tid] = int(ticks)
    times = sorted(samples)
    events = [(line.split()[0] + line.split()[1], float(line.split()[2]) - t0) for line in open(d + "/events.txt")]
    print(f"## {d.rstrip('/').split('/')[-1]}: {open(d + '/exit-build.txt').read().strip()}")
    print("second client:", ", ".join(f"{name} at {t:.1f} s" for name, t in events))
    print(f"exit finished a session's payment commitment at: {', '.join(f'{t - t0:.2f} s' for t in committed)}")
    print(f"pings: {len(pings)} answered, {sum(r > 200 for _, r in pings)} over 200 ms, max {max(r for _, r in pings):.0f} ms\n")
    print("| Stall: first ping sent | last ping back | length | commitment finished | SURB drop | busiest exit threads |")
    print("| --- | --- | --- | --- | --- | --- |")
    for group in groups:
        sent, back = min(b - r / 1000 for b, r in group), max(b for b, _ in group)
        near = lambda xs: min(xs, key=lambda x: abs(x - back), default=None)  # noqa: E731
        c, s = near(committed), near(drops)
        a, b = min(times, key=lambda x: abs(x - sent)), min(times, key=lambda x: abs(x - back))
        use = sorted(((samples[b][t] - samples[a].get(t, 0)) / (b - a) for t in samples[b]), reverse=True) if b > a else []
        print(
            f"| {sent - t0:.2f} s | {back - t0:.2f} s | {back - sent:.2f} s "
            f"| {f'{c - back:+.2f} s from its end' if c is not None and abs(c - back) < 0.5 else 'none within 0.5 s'} "
            f"| {f'{s - back:+.2f} s from its end' if s is not None and abs(s - back) < 0.5 else 'none within 0.5 s'} "
            f"| {', '.join(f'{u:.0f} %' for u in use[:4])} |"
        )
    print()


if __name__ == "__main__":
    for directory in sys.argv[1:]:
        analyze(directory)
