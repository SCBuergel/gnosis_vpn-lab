# 2026-11-23: a public relay that swallows a client's traffic towards the exit

**Measured:** four runs of an Android client (an emulator on AWS Stockholm, a new node with channels to
public relays only) against the Frankfurt lab exit, each a connect, a 38 MB download and an idle phase
with one ping per second. Between the runs the client's set of first-hop relays was changed: two suspect
relays in, out, out, and one of them in again. The lab recorded the exit's side: per session the frames
it discarded, the deposit times, its payment counters, per-minute packet counters of the lab's three
relays, and for run 4 a capture of packet headers between the exit and five relays. Download times, ping
loss, timeouts and the times each relay was in the client's forward set were reported by the session that
ran the client; the lab did not measure them. One connect of a phone to the same exit earlier that night
is included.

**Repository commit:** `1fe9aa3` in the first lab's folder (clean working tree). No `./lab` command was
used: the exit and relays were read over SSH by hand, with `tcpdump` for the capture and the relays'
`/metrics` for the counters.

**Result:** With the relay `0xadfa665d5b37c6ac0829feeb1f64e892e8fbf572` among the client's first hops,
the exit discarded 36 to 39 % of the frames it received from the client; with it and
`0x7f704ac62b02e50a705e1a1d6350ec2256c9c943` out, none. When the first was allowed again, the exit
discarded frames only in the four half-minute windows in which the client used it, and no packets above
background arrived at the exit from that relay.

## The four runs

Same exit, same node, same night. "Discarded" is the share of the session's frames the exit received and
dropped, from its loss reports; the exit logs such a report only for a window in which something was
dropped.

| Run (UTC) | Suspect relays among the first hops | Discarded at the exit | 38 MB download | Ping loss while idle | Probe failures, session-open timeouts |
| --- | --- | --- | --- | --- | --- |
| 1 (02:15) | both, at times | 36 to 39 % in every window of the download; 6 to 52 % while idle | 139 s | 22 % (107 of 476) | 11 and 8 |
| 2 (02:47) | none | no report | not comparable: no deposit, ran on the free allowance | 0.2 % (1 of 480) | none |
| 3 (03:02) | none | no report | 35 s | 1 % | none |
| 4 (03:23) | `0xadfa665d…` for 95 s of the idle phase | reports in four windows only: 10, 20, 17 and 9 % | 35 s | 3 % | not reported |

The last three columns are the client session's figures.

## Run 1: the discards follow the client's choice of first hops

| Period (UTC) | Suspect relay among the client's first hops | Discarded at the exit, per 30 s window |
| --- | --- | --- |
| 02:15 to 02:18 (download) | `0xadfa665d…` | 36, 39, 38, 39, 39 % |
| 02:18:54 to 02:20:49 | `0x7f704ac6…` | 38, 38, 33, 33 % |
| 02:20:54 to 02:23:39 | neither | 8 %, then no report for four windows, then 6 % |
| from 02:23:39 | both back | 33, 27, 52, 43, 25 % |

The periods are the client's; the discard shares are the exit's. The other relays the client used
(`0x880f8bef…`, `0xd88064f7…`, `0xdac87d21…`) were first hops in the clean and in the bad periods alike.

## Runs 2 and 3: with both relays excluded

The client's channels to both relays were closed and its first hops pinned to the others.

- **Run 2** had no deposit: the node's Safe was too low to refill its payment pool. The exit closed the
  session after its 180 s deposit limit (`DepositTimeout`), the client reconnected, and that session's
  deposit was confirmed 66 s later. No loss report for any of its sessions.
- **Run 3** was a complete paid connect. Deposit made 03:02:22, confirmed by the exit 03:02:38, tunnel
  attached 03:02:45. No loss report in the whole session. Exit counters over the run: payment gate 0
  blocks and 0.0 s, 0 packets sent before the deposit, 48,066 as funded.

## Run 4: one relay back, and what arrived from it

A channel to `0xadfa665d…` was opened again, so the client could choose it next to the clean relays. Its
planner gave it a low weight and used it only between 03:28:25 and 03:29:55, on and off, for about 27 %
of the packets while it was in.

- **Deposit:** confirmed 03:23:33, 7 s before the client was connected.
- **Loss reports of the session, all there are:** 03:28:42 37 / 4, 03:29:16 44 / 11, 03:29:48 29 / 6,
  03:30:18 32 / 3 (frames passed on / discarded). None during the download or the first four minutes of
  the idle phase, none after.
- **Packets arriving at the exit from the relay's address** (`57.129.119.98:9088`), mean per 10 s:

| Period (UTC) | Relay among the client's first hops | Packets per 10 s from the relay to the exit |
| --- | --- | --- |
| 03:24:40 to 03:28:20 | no | 4.9 |
| 03:28:20 to 03:30:10 | yes | 5.2 |
| 03:30:10 to 03:36:40 | no | 4.5 |

At the client's rate (about 1.3 frames per second reaching the exit) and the relay's share of the draws,
a relay that forwarded would have added about 3 packets per 10 s. The background varies by about 2
between windows. The background itself, 3 to 4 small packets and a burst of about 7.7 kB every 30 to
40 s, is what the exit exchanges with every node that carries no traffic of this client, including the
other suspect and the idle clean relay.

## What was ruled out

- **The lab's own relays.** All return traffic from the exit passes through them. Sampled once a minute
  from 02:19, each forwarded a near-equal third of what the exit sent (1,580 to 1,960 packets a minute
  each), and no packet-rejection counter moved on any of them or on the exit.
- **The exit's connection to the suspect relays.** It is up in both directions, at the same background
  level as to every other idle node, and the exit's log has no dial or connection error for them.
- **The hosts.** Both suspects are single nodes on machines that run many: 12 on `57.129.119.98` (ports
  9081 to 9092), 10 on `46.62.219.99` (9091 to 9100). The clean relay `0xdac87d21…` is one of 30 on
  `213.133.109.149`.
- **Android.** In a separate test the same symptoms were produced on a Linux client by making one lab
  relay drop its traffic to the exit
  ([sidecar-retransmission](../2026-11-23-sidecar-retransmission/README.md)).

## The phone's connect

01:31:22 UTC, a phone with the same code base and channels to public relays only, first connect to the
Frankfurt exit.

- The exit set up the phone's first probe session at 01:31:21 and bridged it to its API server.
- In the next 62 s it passed nothing from that session to the API server and discarded one frame
  (`emitted=0 discarded=1`). The request had arrived incomplete.
- The client's version check timed out after 60 s; its retry opened a new session at 01:32:21 and passed.
  The probe step took 66 s instead of under 1 s, the connect 105 s.
- The paid session then showed 26 to 34 % discarded in every idle window and 1 % in the window with a
  download. Which relays the phone used was not recorded.

## Reported by the client session, not checked here

- The client's graph keeps a relay as long as any positive evidence for it exists, and this relay
  answers the client's own loop-back probes (`hopr-network-graph` 0.13, `weight.rs`, `delivers_at`).
- A Windows client's node had no channel to either relay; its runs that night were clean
  ([windows-both-labs](../2026-11-23-windows-both-labs/README.md)).

## Not shown by these runs

- **Where the packets are lost.** The exit sees that they do not arrive from the relay. Whether the relay
  receives them and drops them, or never gets them from the client, is between the client and the relay.
- **`0x7f704ac6…` alone.** It is implicated by the timeline of run 1 only.
- **Whether the relay drops everybody's traffic or this node's,** and whether towards every destination
  or this exit. One node, one exit, one night.
- **The count in the capture is of packets, not of their content.** "Nothing arrived" means nothing above
  the background.
- **The first minutes of run 1 and the download of run 4** are not in the per-minute counters and the
  capture table: sampling started at 02:19 and the capture used here at 03:21:50.

## Reproduce the exit's side

```bash
# on the exit, as root: packet headers between the exit and the relays, counted elsewhere per 10 s
tcpdump -n -q -tt -i eth0 'udp and ((host 57.129.119.98 and port 9088) or (host 135.181.133.157 and port 11101))'
# on the exit: the frames it dropped, per session and 30 s window
journalctl -u hoprd | grep loss_report
```

## Files

| File | Content |
| --- | --- |
| `loss-reports.csv` | Every loss report of the sessions named here: frames passed on, discarded, share |
| `run4-capture.csv` | The capture of run 4: packets and bytes per relay, direction and 10 s, 03:21:50 to 03:36:40 |

The filtered copy of the exit's log and the relays' per-minute counters are in the second lab's `raw/`
folder (not in git).
