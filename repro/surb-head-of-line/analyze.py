#!/usr/bin/env python3
"""Summarise the SURB head-of-line repro arms.

Usage: analyze.py ARM_DIR [ARM_DIR ...]

Each ARM_DIR is an output folder of run-arm.sh holding:
  ping.txt       `ping -D` output of the victim through the tunnel during the arm
  exit.log.gz    the exit's hoprd journal for the arm's window (absent in the attacker-off baseline)

The victim probe is a light ping, deliberately NOT a competing download: each echo reply forces the
exit to ORIGINATE a return packet to the victim, which is exactly the traffic the head-of-line stall
withholds, while a ping (unlike a second bulk download) does not compete for the exit's bandwidth and
so does not confound the measurement.

For each arm it reports the victim RTT distribution, how many pings exceeded 500 ms (a stall), how
many SURB-wait drops the exit logged, and — the causal link — how many of those >500 ms pings fall
within 1.5 s of an exit drop.

The claim under test: in the treatment arm (attacker with bridge retransmission) the victim's RTT
tail blows up and each spike coincides with an exit SURB drop; in the baseline (attacker off) and the
contention control (attacker downloading the same, no retransmission) the tail stays clean.
"""
import sys, gzip, re, datetime, statistics


def parse_pings(path):
    """Return [(epoch, rtt_ms)] from `ping -D` output lines like `[1699.123] ... time=12.3 ms`."""
    out = []
    for line in open(path):
        mt = re.search(r"\[(\d+\.\d+)\]", line)
        mr = re.search(r"time=([\d.]+) ms", line)
        if mt and mr:
            out.append((float(mt.group(1)), float(mr.group(1))))
    return out


def exit_drops(path):
    times = []
    try:
        fh = gzip.open(path, "rt", errors="replace")
    except OSError:
        return times
    for line in fh:
        if "no SURB" in line:
            m = re.match(r"(\S+)", line)
            try:
                times.append(datetime.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).timestamp())
            except ValueError:
                pass
    return times


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))]


def analyze(d):
    d = d.rstrip("/")
    name = d.split("/")[-1]
    pings = parse_pings(d + "/ping.txt")
    rtt = [r for _, r in pings]
    drops = exit_drops(d + "/exit.log.gz")
    spikes = [t for t, r in pings if r > 500]
    aligned = sum(1 for t in spikes if any(abs(t - dd) < 1.5 for dd in drops))
    if not rtt:
        print(f"{name:20} (no ping data)")
        return
    print(
        f"{name:20} n={len(rtt):3d}  "
        f"median={statistics.median(rtt):4.0f} p90={q(rtt,0.9):4.0f} p99={q(rtt,0.99):5.0f} max={max(rtt):5.0f} ms  "
        f">500ms={len(spikes):2d}  >200ms={sum(1 for r in rtt if r>200):2d}  "
        f"exit_drops={len(drops):2d}  spikes_aligned_to_drops={aligned}/{len(spikes)}"
    )


if __name__ == "__main__":
    for d in sys.argv[1:]:
        try:
            analyze(d)
        except Exception as e:  # noqa: BLE001
            print(f"{d}: {type(e).__name__}: {e}")
