# 2026-11-25: the exit SURB head-of-line stall reaches a second client

**Measured:** the ping latency of one Gnosis VPN client (the *victim*) through its tunnel, while a
second, independent client (the *attacker*) on the same exit runs a bridge session with and without
retransmission. This tests the open question in
[hoprnet#8753](https://github.com/hoprnet/hoprnet/issues/8753): does one session's SURB starvation
stall the traffic of *other* clients on the exit? Three arms, 90 s of pings each (every 0.3 s),
victim pinging `1.1.1.1` through the tunnel.

**Repository commit:** `f368bc2` (plus this folder and the harness in
[`repro/surb-head-of-line/`](../../repro/surb-head-of-line/), added in the same commit as these
results).

## Setup

- **Exit:** vpn-lab2 exit (New York), node `0xe18960…`, hoprd **5.0.4** (pre-fix), 4 vCPU.
- **Victim:** vpn-lab client (Frankfurt), node `0x7F26…`, client main (no fix), default bridge
  (no retransmission). A normal user; it only pings.
- **Attacker:** vpn-lab2 client (New York), node `0xf8cB…`, build `control-main-5d902a6`, downloading
  continuously. Its bridge capabilities are the only thing that changes between the two active arms.
- Both clients pinned the exit by address, 1 hop, through vpn-lab2's three relays. Same production
  HOPR network (piz-palu-prod).

The victim **pings** rather than downloads on purpose: each echo reply makes the exit *originate* a
return packet to the victim (the traffic the stall withholds), without competing for the exit's
bandwidth. A second bulk download does not work as a probe — on this 4-vCPU exit two concurrent
downloads collapse each other regardless of retransmission (bandwidth / PIX-deposit limits), masking
the effect. Ping sidesteps that, as the contention arm below confirms.

## Result

| Victim ping, 90 s | **baseline** (attacker off) | **contention** (attacker downloading, no retx) | **treatment** (attacker downloading, **retx**) |
| --- | --- | --- | --- |
| pings received | 299 | 296 | 299 |
| exit SURB-wait drops in window | 0 | 0 | **16** |
| median RTT | 118 ms | 121 ms | 123 ms |
| p90 RTT | 131 ms | 139 ms | **611 ms** |
| p99 RTT | 143 ms | 430 ms | **1103 ms** |
| max RTT | 167 ms | 1038 ms | **1464 ms** |
| pings over 500 ms | 0 | 2 | **34** |
| pings over 200 ms | 0 | 5 | **62** |
| of those >500 ms, within 1.5 s of an exit drop | — | 0 of 2 | **34 of 34** |

- **The median is identical across all three arms (~120 ms).** The stall does not touch normal
  operation; it is purely a tail effect.
- **Only the treatment arm has a tail.** 34 of 299 pings exceeded 500 ms (up to 1.46 s), against 2 in
  contention and 0 in baseline. The spike size matches hoprd's `surb_resolution_wait` of 1 s — the
  resolve stage holds the victim's ping-reply packet for up to that wait.
- **Every treatment spike coincides with an exit SURB drop.** All 34 pings over 500 ms fell within
  1.5 s of a `no SURB for its return path` drop logged by the exit (16 drops; pings are every 0.3 s,
  so each ~1 s stall covers two or three of them).
- **It is not bandwidth contention.** The contention arm ran the attacker's download at the same rate
  (~17–21 Mbit/s) with retransmission off; the victim's ping tail stayed clean (p90 139 ms, 0 drops).
  The difference between contention and treatment is the one `[connection.bridge]` retransmission line.

**Conclusion:** a bridge session with retransmission on one client starves the exit's SURBs, and that
starvation stalls a *different* client's traffic through the same exit by up to ~1 s per affected
packet — the cross-client head-of-line blocking that #8753 described but had not verified. Here it
raised an unrelated client's ping tail from ~130 ms to 0.5–1.5 s.

## Files

| Path | Content |
| --- | --- |
| `ping-baseline/`, `ping-contention/`, `ping-treatment/` | each: `ping.txt` (victim `ping -D`), `exit.log.gz` (exit hoprd journal for the window), `drops.txt`, `arm-meta.json` |
| `../../repro/surb-head-of-line/` | the harness (configs, `run-arm.sh`, `run-all.sh`, `analyze.py`) and its README |

## Reproduce

```bash
cd ../../repro/surb-head-of-line
DUR=90 ./run-all.sh
./analyze.py ../../results/2026-11-25-surb-head-of-line/ping-*
```

## Not shown / caveats

- **One run of each arm**, back to back, on one exit. The spike↔drop correlation is strong (34/34),
  but this is a single session, not a repeated-trial statistic.
- **The attacker and victim are in different regions** (NY exit, FRA victim), which sets the ~120 ms
  baseline RTT. The stall is added on top of that and is region-independent (it is the exit's
  origination wait).
- **This exit cannot host the download-vs-download version of the test**: two concurrent bulk
  downloads collapse each other via bandwidth/PIX-deposit limits with or without retransmission, so
  that comparison is confounded. The ping probe is what isolates the stall; the download confound is
  itself worth noting to anyone sizing an exit.
- **The exit was not modified or rebuilt.** The fix (hoprnet PRs #8755 / #8759) was not tested here;
  this measures the unfixed behaviour on hoprd 5.0.4.
- The attacker's connection to the unannounced exit needed a worker restart to bring up its tunnel
  interface after the config swap (noted in the harness); this is an operational flake, not part of
  the measured effect.
