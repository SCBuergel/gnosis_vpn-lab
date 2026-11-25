# The exit stalls for all clients when a session is established

Harness for [results/2026-11-25-reconnect-stall](../../results/2026-11-25-reconnect-stall/README.md).
It needs a lab with two clients (see [`../pr8763-before-after`](../pr8763-before-after/README.md)).

```bash
./run.sh ../../results/x/my-run     # 150 s: victim pings, second client connects and disconnects 3 times
./analyze.py ../../results/x/my-run # each stall of the victim with what the exit did at that moment
```

`run.sh` samples the CPU time of every thread of the exit's hoprd every 0.1 s with `threads.py`.
To change the size of hoprd's CPU pool, set `HOPRD_NUM_CPU_THREADS` in `/etc/hoprd/hoprd.env` on the
exit and restart hoprd.
