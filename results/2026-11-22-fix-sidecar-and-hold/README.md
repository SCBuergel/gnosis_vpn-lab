# 2026-11-22: a client that pays through its own session and waits for the payment

**Measured:** the connect-and-download test with two builds of client 1.1.0 on the lab client, against the
lab exit: an unmodified build from source (control) and a patched build. Each was run under normal lab
conditions and under a simulated slow path to the payment relayer that reproduces the failure seen on
the laptop outside the lab.

**Repository commit:** `aba40f5` for every run (clean working tree). The client patches are in
`patches/sidecar-relayer/`: `edge-client` at `7bafb47` plus one commit, `gnosis_vpn-client` at `v1.1.0`
plus two commits.

## Result

| Condition | Build | `connect` until connected | Interruption by the exit | Download of 100 MB |
| --- | --- | --- | --- | --- |
| Normal | control | 5.1 s, 5.1 s | 14.8 s, 16.8 s | complete, 78 s |
| Normal | **patched** | 42.1 s, 155.0 s | **none, none** | complete, 81 to 82 s |
| Packets to the relayer delayed 1.5 s | control | 4.9 s | 33.4 s | complete, 83 s |
| Packets to the relayer delayed 3 s (the laptop's failure) | control | 5.1 s | **never resumed** (182 s until the test ended) | stopped at 13.4 MB |
| Packets to the relayer delayed 3 s | **patched** | 92.1 s | **none** | complete, 82 s |

**About the 92 s:** this is the cost of the injected delay, not a connect time a user would see. Without
the delay the same build connects in 42 s. The delay holds every packet from the exit to the relayer back
by 3 s, far more than a real network would, because that reliably makes the unmodified client lose the
race. One payment is about 20 exchanges with the relayer in this version of the patch, so the payment
alone took about 62 s; the rest is the same as without delay (sessions 2 s, noticing the payment 2 to 3 s,
the fixed 22 s wait, attaching 3 s). The rebuilt patch opens the relayer connection early and reuses it:
67 s under the same delay ([2026-11-22-main-patched](../2026-11-22-main-patched/README.md)).

In words:

- **The patched client has no interruption after connecting**, in every run. The exit's own counter of
  time spent holding traffic back stayed at 0.0 s.
- **The price is a longer connect:** about 42 s instead of 5 s under normal conditions. The time the
  user waits is the same as the time the unmodified client needs before the connection really works
  (5 s connect + 17 s of download + 15 s interruption); it is spent before "connected" instead of after.
- **The laptop's failure is reproduced in the lab and fixed.** With the relayer 3 s slower, the
  unmodified client's download stops for good, the exit times out after 3 minutes, and the client
  reconnects and commits to paying again. The patched client connects in 92 s and then just works.
- **One run of the patched client waited needlessly** (155 s): see "Known gaps".

Each run also had gaps of 1 to 2.3 s in the download, with either build. They are not the exit holding
traffic back (the counter does not move) and are not explained.

## What the patched client does differently

1. **The payment relayer gets its own session.** When connecting to an exit, the client opens one more
   unpaid session through that exit to `api.curvy.box:443` and sends the payment pool's relayer requests
   there. They no longer travel in the VPN tunnel, which the exit holds back until it sees the deposit,
   and they pass the client's killswitch before the tunnel exists. This is the approach from the
   developers' discussion; the pool's hook for it shipped in hopr-strategy 9.2.0.
2. **The tunnel is attached only after the first payment is confirmed.** The client opens the paid
   session, waits until its pool reports the deposit as made, waits 22 s more for the exit to see it,
   and only then brings up the tunnel and reports "connected". The user's traffic never runs on the
   exit's free 13 MB allowance.
3. **Fallback:** if no payment is made within 150 s (for example an exit that does not allow the relayer
   as a session target), the client drops the side-car route and connects the old way.

The exit needs one configuration line: `api.curvy.box:443` in its session target allow-list.

## How the laptop's failure was simulated

`tc netem` on the lab exit delays every packet from the exit towards the relayer's addresses, and only
those (`./lab relayer-delay`, [remote/relayer-delay.sh](../../remote/relayer-delay.sh)). HOPR traffic and
the download are not delayed. Both the tunnel's traffic and the side-car session's traffic to the relayer
leave through that interface, so the delay hits both builds alike.

- **1.5 s:** the unmodified client's payment request is already in flight when the exit starts holding
  traffic back (17 s into the download). Requests still go out during the hold; only answers cannot come
  back. The deposit lands and the hold ends after 33 s.
- **3 s:** the requests the client needs answers to before it can build its payment have not returned
  when the hold starts. The answers never arrive, the payment is never built, and nothing ends the hold.
  The client's log shows the same line the laptop's did, repeated: `the Curvy relayer is unreachable`.

## First attempt of the patched build (failed, fixed)

The first patched build gave the side-car session the client's smallest reply buffer (16 KB). The
relayer's network list is 31 KB, the request timed out every time, and no payment could be made: the
hold ran into its 150 s limit and the download then stalled as with the unmodified client. The second
commit on the client gives that session the 1 MB tier. Raw data: `raw/2026-11-22-fix-patched-build-attempt1/`.

## Known gaps

- **The 22 s wait is a fixed number,** not a real confirmation. It is the measured time from "relayer
  accepted" to "exit sees it" (20.6 to 21.5 s), which is three block confirmations plus the pool
  operator's commit. A proper version would watch the chain for the same event the exit watches.
- **The client's own bookkeeping decides when the hold ends, and it can lose a deposit.** In one run the
  deposit was made and the exit saw it after 34 s, but the client kept waiting until the 150 s limit. Its
  pool had logged `deposit flush deferred until an earlier Curvy operation is reconciled`. Despite the
  wording, no earlier operation was involved: the same happened again in
  [2026-11-22-main-patched](../2026-11-22-main-patched/README.md), where it is traced to the pool
  looking the new notes up through Blokli once, at the moment the relayer reports inclusion, and giving
  up when Blokli has not indexed them yet. The unmodified client does the same. An earlier version of
  this text blamed the failed first attempt; that was wrong.
- **No new connection phase is reported.** During the hold, status shows "opening main connection".
- **Only the first payment is held for.** Later payments in a long session still happen while traffic
  flows; they go through the side-car session too.
- **Built with cargo on Ubuntu 24.04,** not with the project's own release build, and not reviewed.

## Runs

| Folder | Condition, build |
| --- | --- |
| [2026-11-22-fix-control-build](../2026-11-22-fix-control-build/README.md) | normal, control |
| [2026-11-22-fix-patched-build](../2026-11-22-fix-patched-build/README.md) | normal, patched |
| [2026-11-22-sim-slow-relayer-control](../2026-11-22-sim-slow-relayer-control/README.md) | packets to the relayer delayed 1.5 s, control |
| [2026-11-22-sim-slower-relayer-control](../2026-11-22-sim-slower-relayer-control/README.md) | packets to the relayer delayed 3 s, control |
| [2026-11-22-sim-slower-relayer-patched](../2026-11-22-sim-slower-relayer-patched/README.md) | packets to the relayer delayed 3 s, patched |
