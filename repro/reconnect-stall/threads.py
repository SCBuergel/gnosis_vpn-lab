#!/usr/bin/env python3
# Sample the CPU time of every thread of a process: one line per thread and sample (epoch, tid, name, ticks).
import os, sys, time
pid, seconds, step = sys.argv[1], float(sys.argv[2]), 0.1
end = time.time() + seconds
while time.time() < end:
    now = time.time()
    for tid in os.listdir(f"/proc/{pid}/task"):
        try:
            raw = open(f"/proc/{pid}/task/{tid}/stat").read()
        except OSError:
            continue
        name = raw[raw.index("(") + 1 : raw.rindex(")")]
        f = raw[raw.rindex(")") + 2 :].split()
        print(f"{now:.3f} {tid} {name.replace(' ', '_')} {int(f[11]) + int(f[12])}")
    time.sleep(max(0, step - (time.time() - now)))
