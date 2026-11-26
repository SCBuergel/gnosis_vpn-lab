#!/usr/bin/env python3
"""Summarise one arm of the relay-fault test and write its clean log bundle.

Usage: pack.py RAW_DIR OUT_DIR
"""
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

raw, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
t0, t1 = int((raw / "t0").read_text()), int((raw / "t1").read_text())
start, end = int((raw / "start").read_text()), int((raw / "end").read_text())
mode = "fault" if "FAULT ON" in (raw / "phases.txt").read_text() else "control"


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%S")


marks = [
    (t0, "FAULT ON: relay1 starts dropping its packets to the exit" if mode == "fault" else "CONTROL MARK: a fault would start here; none is injected"),
    (t1, "FAULT OFF: relay1 forwards to the exit again" if mode == "fault" else "CONTROL MARK END: a fault would end here"),
]
NOISE = re.compile(r"\b(DEBUG|TRACE)\b")


def clean(source: str, target: str) -> tuple[int, int]:
    """INFO and above, with marker lines at the fault times. Returns (lines kept, lines read)."""
    pending = sorted(marks)
    kept = read = 0
    with open(raw / source, errors="replace") as src, open(out / target, "w") as dst:
        for line in src:
            read += 1
            stamp = line[:19]
            while pending and stamp[:4] == "2026" and stamp >= iso(pending[0][0]):
                t, text = pending.pop(0)
                dst.write(f"########## {iso(t)}Z {text} ##########\n")
            if NOISE.search(line[:120]):
                continue
            dst.write(line)
            kept += 1
    return kept, read


counts = {}
for source, target in [
    ("client-worker.full.log", "client-worker.log"),
    ("exit.full.log", "exit.log"),
    ("relay1.full.log", "relay1.log"),
    ("relay2.full.log", "relay2.log"),
    ("relay3.full.log", "relay3.log"),
]:
    if (raw / source).exists():
        counts[target] = clean(source, target)

# Downloads: one line per 2 MB download.
rows = []
for line in (raw / "curl.txt").read_text().splitlines():
    parts = line.split()
    if len(parts) == 3:
        t, size, secs = int(parts[0]), int(parts[1]), float(parts[2])
        rows.append((t, size, secs, size * 8 / secs / 1e6 if secs > 0 else 0.0))
with open(out / "downloads.csv", "w") as f:
    f.write("utc,seconds_after_mark,bytes,seconds,mbit_per_s,complete\n")
    for t, size, secs, rate in rows:
        f.write(f"{iso(t)}Z,{t - t0},{size},{secs:.2f},{rate:.2f},{'yes' if size >= 2000001 else 'no'}\n")

# Ping: loss and median per phase.
sent = {}
for line in (raw / "ping.txt").read_text().splitlines():
    m = re.match(r"\[(\d+\.\d+)\] (.*)", line)
    if not m:
        continue
    t = float(m.group(1))
    seq = re.search(r"icmp_seq=(\d+)", m.group(2))
    rtt = re.search(r"time=([\d.]+) ms", m.group(2))
    if seq and rtt:
        sent[int(seq.group(1))] = (t, float(rtt.group(1)))
first_t = min(v[0] for v in sent.values())
last_seq = max(sent)
phases = [("before", start, t0), ("during", t0, t1), ("after", t1, end)]
ping_rows = []
for name, a, b in phases:
    got = sorted(r for (t, r) in sent.values() if a <= t < b)
    # Sequence numbers advance every 0.2 s whether or not a reply comes.
    lo, hi = max(a, first_t), min(b, first_t + last_seq * 0.2)
    expected = max(1, round((hi - lo) / 0.2))
    loss = max(0.0, 1 - len(got) / expected)
    ping_rows.append((name, len(got), expected, loss, got[len(got) // 2] if got else None))


def band(a: int, b: int) -> str:
    rates = [r for (t, s, _, r) in rows if a <= t - t0 < b]
    if not rates:
        return "none"
    return f"{min(rates):.1f} to {max(rates):.1f} Mbit/s ({len(rates)} downloads)"


summary = [
    f"mode: {mode}",
    f"mark (fault on): {iso(t0)}Z, mark end (fault off): {iso(t1)}Z",
    f"downloads before the mark:        {band(-10**6, 0)}",
    f"download starting at the mark:    {band(0, 30)}",
    f"+30 s to +150 s:                  {band(30, 150)}",
    f"+150 s to the end mark:           {band(150, t1 - t0)}",
    f"after the end mark:               {band(t1 - t0, 10**6)}",
] + [
    f"ping {name}: {got} replies of about {exp} sent, loss {loss * 100:.1f}%, median {med} ms"
    for name, got, exp, loss, med in ping_rows
]
(out / "summary.txt").write_text("\n".join(summary) + "\n")
for name in ("phases.txt", "channels.txt", "drops.txt", "exit-acct.txt"):
    if (raw / name).exists():
        shutil.copy(raw / name, out / name)
shutil.copy(raw / "config.toml", out / "client-config.toml")
print("\n".join(summary))
print({k: v for k, v in counts.items()})
