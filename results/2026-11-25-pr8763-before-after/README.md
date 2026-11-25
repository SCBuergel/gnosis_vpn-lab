# 2026-11-25: hoprnet PR #8763 on a real exit, before and after

**Measured:** the ping and HTTPS latency of one Gnosis VPN client (the *victim*) while a second
client (the *attacker*) on the same exit is absent, downloads normally, or downloads with a bridge
session that runs out of SURBs on the exit. Each on three hoprd builds on the exit: the released
5.0.6, 5.0.6 built from source, and that source build with
[hoprnet PR #8763](https://github.com/hoprnet/hoprnet/pull/8763) applied. 15 arms of 180 s.

**Result:** with the PR, a session that runs out of SURBs no longer delays the other client. Without
it, the victim had 14 to 22 stalls of up to 1.6 s in 180 s; with it, none, although the exit dropped
as many packets of the starving session. One other, rarer stall is not addressed by the PR: about
1.3 s on the victim each time the exit closes the attacker's session and the attacker reconnects.

Harness and build recipe: [`repro/pr8763-before-after/`](../../repro/pr8763-before-after/README.md).

## Setup

- **Lab:** `vpn-lab3`, DigitalOcean `ams3`, 4 dedicated vCPU per machine, production network
  `piz-palu-prod`. Three relays (hoprd 5.0.4), one exit, two clients; both clients reach the exit
  over 1 hop through the three lab relays.
- **Victim:** gnosisvpn 1.1.0 package. Pings `1.1.1.1` every 0.3 s and fetches
  `https://1.1.1.1/cdn-cgi/trace` once a second (a new TLS connection each time).
- **Attacker:** client main `5d902a6`. Downloads a 10 GB file from `ams.download.datapacket.com`.
- **Exit builds:** `stock` is the published 5.0.6 image binary (sha256 `a6452f3d…`). `src`
  (`4e33b171…`) is tag `v5.0.6` of hoprnet/hoprd built from source with its pinned hoprnet revision
  `fa69827`. `pr8763` (`2fe674b4…`) is the same build tree with the PR's change to
  `transport/hopr/src/` (PR head `c5867a3`) applied; `resolve.rs` at `fa69827` is byte-identical to
  the PR's base. `surb_resolution_wait` is hoprd's 1 s on all three.
- **Order:** stock; then src, pr8763, pr8763 again, src again, with a restart of hoprd at each change.

## The session that runs out of SURBs (what the PR fixes)

Arm `starved`: the attacker's bridge session has retransmission enabled.

| Exit build | Exit drops (SURB wait ran out) | Victim stalls at such a drop | Pings over 500 ms | Ping p99 | HTTPS p95 |
| --- | --- | --- | --- | --- | --- |
| stock 5.0.6 | 25 | 15 | 47 of 598 | 1372 ms | 972 ms |
| src, round 1 | 18 | 14 | 34 of 598 | 1016 ms | 893 ms |
| src, round 2 | 37 | 22 | 71 of 598 | 1570 ms | 1275 ms |
| **pr8763, round 1** | 33 | **0** | 3 of 599 | 107 ms | 181 ms |
| **pr8763, round 2** | 20 | **0** | 3 of 599 | 76 ms | 182 ms |

- A stall is a run of pings slower than 200 ms. It counts as "at a drop" when one of its pings came
  back within 0.3 s after the exit logged `no SURB for its return path within the wait`: the pings
  held behind that packet leave together when its wait ends.
- **Before:** on both unpatched builds most drops stall the victim, and a page fetch that falls into a
  stall takes 0.9 to 1.3 s instead of 0.15 s.
- **After:** the exit logs the same drops (20 and 33), and no stall of the victim falls at one. Ping
  p99 and HTTPS p95 equal those of the arms without an attacker (58 to 78 ms, 173 to 191 ms).
- The 3 pings over 500 ms that remain per arm belong to the other stall, below.
- A few stalls on the unpatched builds are not at a drop (1 or 2 per arm): by timing they fit shorter
  waits that ended when a SURB arrived, which the exit does not log. This is inferred.
- The released binary and the source build behave alike, so the source build is a fair "before".
- The PR's limit on waiting packets was never reached: `too many packets are waiting for a SURB` was
  logged 0 times (the exit ran with `hopr_transport::path::resolve=debug`).

## Another stall, not caused by SURBs and not fixed by the PR

In 8 of the 10 arms with an attacker the victim had exactly one stall of 1.2 to 1.4 s that is not at
a SURB drop (4 pings, one HTTPS fetch of 0.8 to 1.3 s). It is there on all three builds and in control
arms with 0 drops.

- In each of the 8 arms the exit established a new session for the attacker in the 3 s before the
  stall. In 7 of them the exit had just closed the attacker's tunnel session
  (`pix supervisor closed the session … reason=deposit_timeout`, the
  [late first payment](../2026-11-22-payment-deadlock/README.md)); in `pr8763-starved` it had closed
  it with `reason=EmptyRead`.
- The 2 arms with an attacker and no such stall are `src-control` and `stock-starved`. They are also
  the only 2 in which the exit closed and established no session, and the attacker's download ran
  throughout.
- The cause is not established. The stall begins 0.6 to 0.9 s after the attacker's new tunnel session
  is requested and lasts about 1.35 s.

This is a second way in which one client delays another on the same exit. It is far rarer than the
SURB stall (once per reconnect of the other client), and it needs its own look.

## All arms

Stalls are given as total (at a SURB drop / after a new session / other).

| Arm | Attacker Mbit/s | Exit drops | Ping median | Ping p99 | Pings >200 ms | Pings >500 ms | Stalls | HTTPS median | HTTPS p95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `stock-quiet` | 0.0 | 0 | 36 ms | 78 ms | 3 | 0 | 1 (0 / 0 / 1) | 145 ms | 173 ms |
| `src-quiet` | 0.0 | 0 | 36 ms | 62 ms | 0 | 0 | 0 (0 / 0 / 0) | 151 ms | 180 ms |
| `src-2-quiet` | 0.0 | 0 | 35 ms | 58 ms | 0 | 0 | 0 (0 / 0 / 0) | 149 ms | 177 ms |
| `pr8763-quiet` | 0.0 | 0 | 36 ms | 58 ms | 0 | 0 | 0 (0 / 0 / 0) | 152 ms | 178 ms |
| `pr8763-2-quiet` | 0.0 | 0 | 36 ms | 61 ms | 0 | 0 | 0 (0 / 0 / 0) | 149 ms | 191 ms |
| `stock-control` | 0.6 | 0 | 36 ms | 118 ms | 5 | 4 | 1 (0 / 1 / 0) | 149 ms | 178 ms |
| `src-control` | 11.5 | 0 | 35 ms | 64 ms | 0 | 0 | 0 (0 / 0 / 0) | 151 ms | 189 ms |
| `src-2-control` | 0.6 | 0 | 37 ms | 75 ms | 4 | 3 | 1 (0 / 1 / 0) | 150 ms | 181 ms |
| `pr8763-control` | 0.6 | 0 | 36 ms | 106 ms | 4 | 3 | 1 (0 / 1 / 0) | 153 ms | 185 ms |
| `pr8763-2-control` | 0.6 | 0 | 36 ms | 77 ms | 4 | 3 | 1 (0 / 1 / 0) | 149 ms | 175 ms |
| `stock-starved` | 14.2 | 25 | 40 ms | 1372 ms | 83 | 47 | 16 (15 / 0 / 1) | 160 ms | 972 ms |
| `src-starved` | 0.6 | 18 | 39 ms | 1016 ms | 60 | 34 | 16 (14 / 1 / 1) | 151 ms | 893 ms |
| `src-2-starved` | 0.6 | 37 | 41 ms | 1570 ms | 121 | 71 | 23 (22 / 1 / 0) | 158 ms | 1275 ms |
| `pr8763-starved` | 0.5 | 33 | 36 ms | 107 ms | 4 | 3 | 1 (0 / 1 / 0) | 151 ms | 181 ms |
| `pr8763-2-starved` | 0.6 | 20 | 36 ms | 76 ms | 4 | 3 | 1 (0 / 1 / 0) | 150 ms | 182 ms |

The full table with every column is [`summary.md`](summary.md). All pings were answered except one in
`src-starved` and none in the other arms (598 or 599 of 598 or 599).

## Not shown / caveats

- **The attacker's download did not run throughout.** Every arm started measuring with the download
  running (over 40 MB transferred), but in most arms the exit then closed the attacker's tunnel
  session for a missing first payment, and the download averaged 0.5 to 0.6 Mbit/s over the arm. It
  ran throughout only in `src-control` (11.5 Mbit/s) and `stock-starved` (14.2 Mbit/s). The exit's
  drops show that the bridge session starved in every `starved` arm regardless. The effect of the PR
  under a second client's sustained bulk download is therefore covered by the starving arms only as
  far as that download ran.
- **Stock arms ran before a change to the harness.** They did not wait for the download to pass
  the first-payment hold (`stock-control` measured an attacker that was mostly idle).
- **Two rounds per source build**, one exit, one day. The before/after difference is large and the
  same in both rounds (14 and 22 stalls at a drop against 0 and 0), but it is not a statistic.
- **The treatment changes two bridge capabilities** against the control (`retransmission` and
  `no_rate_control`), as in the [first measurement](../2026-11-25-surb-head-of-line/README.md).
- **The PR's limit of 1024 waiting packets was not exercised.** Drops came at 0.1 to 0.2 per second;
  the limit needs about a thousand per second.
- **Only `transport/hopr/src/` of the PR was applied**, on hoprnet `fa69827`, not on the PR's base
  `c0ad8d7`. The version bump in the manifests was left out.
- The starving session itself is no better off with the PR: its packets are still dropped.

## Files

| Path | Content |
| --- | --- |
| `<build>-<arm>/ping.txt`, `http.txt` | the victim's `ping -D` output and one line per HTTPS fetch (start, seconds, status) |
| `<build>-<arm>/exit-surb.log.gz` | the exit's log lines about SURB waits in the arm's window |
| `<build>-<arm>/exit-sessions.log.gz` | sessions established and closed on the exit in the window |
| `<build>-<arm>/arm-meta.json` | arm, exit build and hash, window, attacker download rate |
| `summary.md` | output of `analyze.py` over all arms |
| `run-stock.log`, `run-src-pr.log` | console output of the runs |
