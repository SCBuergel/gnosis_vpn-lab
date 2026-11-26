#!/usr/bin/env python3
"""Per step: share of path slots (3 per rebuild) that sit on relays still working, forward and return.

Usage: sets-pack.py RAW_DIR...   (reads client-worker.full.log, steps.txt, t0, t1, config.toml order)
Relays are relay1..relay9 in the order of RELAYS below; a ladder step "relayN" cuts relay1..relayN in
total, a sudden-outage step "cut relay1..relayN" cuts relay1..relayN, "restored"/"all cuts removed" none.
"""
import re, sys, os, calendar, time
RELAYS = ["c67e2d03", "6cefd8bf", "83e8bcfe", "9eca7f9e", "e89cd2bd", "598d5911", "2cd1a3ae", "764bbac3", "439c27a8"]
EXIT = "d9a917e2"
pat = re.compile(r'validated path \[0x([0-9a-f]{8})[0-9a-f]*, 0x([0-9a-f]{8})[0-9a-f]*\]", ([0-9.e-]+)')
def ts(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
for d in sys.argv[1:]:
    t0 = int(open(os.path.join(d, "t0")).read()); t1 = int(open(os.path.join(d, "t1")).read())
    steps = [(t0 - 300, "baseline", 0)]
    for line in open(os.path.join(d, "steps.txt")):
        p = line.split()
        name = " ".join(p[1:-2])
        m = re.search(r"relay(\d+)$", name)
        cut = int(m.group(1)) if m and "restored" not in name else 0
        steps.append((int(p[0]), name, cut))
    steps.append((t1, "all cuts removed", 0))
    acc = [dict(f=[0, 0, 0.0, 0.0], r=[0, 0, 0.0, 0.0]) for _ in steps]
    for line in open(os.path.join(d, "client-worker.full.log"), errors="replace"):
        if "rebuilt weighted path collection" not in line: continue
        t = ts(line)
        if t < steps[0][0] or t > t1 + 300: continue
        i = max(k for k, s in enumerate(steps) if s[0] <= t)
        cut = steps[i][2]
        for first, last, w in pat.findall(line):
            if first not in RELAYS: continue
            a = acc[i]["f" if last == EXIT else "r"]
            live = RELAYS.index(first) >= cut
            a[0] += live; a[1] += 1; a[2] += float(w) * live; a[3] += float(w)
    print(f"\n### {os.path.basename(d.rstrip('/'))}\n")
    print("| step | relays cut | forward: slots on working relays | forward: weight on working relays | return: slots on working relays | return: weight on working relays |")
    print("| --- | --- | --- | --- | --- | --- |")
    for (t, name, cut), a in zip(steps, acc):
        def pc(n, m): return f"{100*n/m:.0f}%" if m else "-"
        f, r = a["f"], a["r"]
        print(f"| {name} | {cut} | {pc(f[0], f[1])} | {pc(f[2], f[3])} | {pc(r[0], r[1])} | {pc(r[2], r[3])} |")
