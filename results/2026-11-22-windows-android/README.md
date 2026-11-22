# 2026-11-22: the patched client on Windows and Android against the lab exit

**Measured:** connects of two experimental clients, one on Windows (a machine on AWS, eu-north-1) and one
on Android (an emulator), through the three lab relays to the lab exit, each connect followed by a
download. Builds with and without the side-car session and the hold, on two versions of the client's
code. The lab recorded the exit's side: its payment counters at the start and end of each block of
connects, and its log. The client-side numbers (connect times, pauses, stalls, timeouts) were reported by
the two sessions that ran the clients; the lab did not measure them.

**Repository commit:** `1fe9aa3` (clean working tree). The clients were not driven by `./lab`, so there
is no `measurement.json`.

**Result:** With the hold, the exit's payment gate never held traffic back: 0 s in 8 Windows connects,
against 103 s in 6 connects without it. The side-car carried the relayer's traffic on both platforms.
It only works on an exit that allows the relayer as a session target; on two production exits it failed
and the connect waited 150 s.

## Builds

| Name here | Client code | Side-car and hold | hopr-strategy |
| --- | --- | --- | --- |
| main, unmodified | `gnosis_vpn-client` at `e6b33f36` | no | fix `d6ad33ff` |
| patched on main | `e6b33f36` plus branch `sidecar-relayer-hold` (`c768ccf1`) | yes | fix `d6ad33ff` |
| older base, unmodified | `8a0e3be` (one commit after v1.1.0) | no | 9.2.0 |
| patched on older base | `8a0e3be` with the same three commits cherry-picked (`98de0384`) | yes | fix `d6ad33ff` |

Each build also carries its platform's own changes, which this repository does not contain. The fix
`d6ad33ff` is the one described in [2026-11-22-blokli-race](../2026-11-22-blokli-race/README.md).

## Windows: four blocks under the same conditions

Four connects per block, each followed at once by a 100 MB download with a 180 s limit. One client node,
the lab's configuration from [local-client](../../local-client/README.md), no delay injected. The blocks
ran back to back in the order shown.

| Block (UTC) | Build | Connects that came up | Held by the exit's payment gate | Packets sent before a deposit | Downloads | Late stalls | Session-open timeouts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 (18:19 to 18:45) | main, unmodified | 2 of 4 | 2 times, 20.1 s | 20,000 | not reported | both, one for 85 s to the end | 21 |
| 2 (18:46 to 19:07) | patched on main | 4 of 4 | **0 times, 0.0 s** | **0** | 4 of 4 complete | 2, of 5 s and 16 s | 3 |
| 3 (19:07 to 19:25) | patched on older base | 4 of 4 | **0 times, 0.0 s** | **0** | 4 of 4 complete | none | 2 |
| 4 (19:25 to 19:42) | main, unmodified | 4 of 4 | 4 times, 83.2 s | 40,000 | one stopped at 30.8 MB | 2 | 2 |

The two gate columns and the packet column are differences of the exit's counters between the snapshots
in `exit-counters.csv`. The other columns are the Windows session's report.

- **The pause after connecting is the payment gate, and the hold removes it.** Every paid connect
  without the hold was held back (one for 36 s); none of the eight with the hold was. Without the hold
  each session sent exactly its free allowance of 10,000 packets before the deposit; with it, none.
- **With the hold the tunnel attached after the exit's confirmation** in blocks 2 and 3, by 2 to 6 s, in
  the 7 of 8 connects where the exit's confirmation line survived.
- **Holds lasted 42 to 47 s.** Connect times in block 3 were 47 to 71 s; the rest is session opening.
- **Block 1's failures were the hour, not the build.** The same build repeated as block 4 connected four
  times with 2 timeouts.
- **Late stalls** (after 85 s or more of download) are not payment: the exit's gate counter did not move
  in block 2, where two of them happened. They were most frequent on main without the patch
  (4 of 6 paid connects), fewer with it (2 of 4, short) and absent on the older base (0 of 4). Not
  explained.
- **The hopr-strategy fix was needed twice in block 3:** the client logged `indexed a relayed Curvy
  aggregation after the relayer reported it` for two deposits. Without the fix those two connects would
  have waited for the hold's 150 s limit.

### An earlier Windows run the same day

16:57 to 17:33 UTC, four connects each, no counter snapshots taken:

| Build | `connect` until connected | Pause after connecting | 100 MB download | Session-open timeouts |
| --- | --- | --- | --- | --- |
| patched on main | 69 to 173 s | none early | 2 of 4 complete; late stalls in the other two | 10 |
| older base, unmodified | 4 to 5 s in three, 40 s in one | 7 s, 8 s, 3 s, none | 4 of 4 complete | 0 |

The exit confirmed all eight deposits. For the patched build it confirmed 20 to 23 s after the client's
deposit; in one connect the tunnel attached about 1 s before the confirmation.

## Android

Up to three connects with a 38 MB download each, build "patched on main", 17:35 to 18:18 UTC. The
emulator killed the app or restarted Android every few minutes, so six sessions were paid and four of
them were abandoned before or just after the tunnel attached.

- **The side-car carried the relayer's traffic:** 30 short relayer sessions in the client's log, 16 of
  them with the 4,362 bytes of the relayer's TLS answer.
- **Paid after 15.0 to 20.1 s, held 37.0 to 42.1 s.**
- **The two full downloads had no pause at 13 MB** and no stall over 1 s.
- **No session-open timeouts.**
- **In the two sessions the exit's log still held,** the tunnel attached about 1 s before the exit's
  confirmation (23 s and 26 s after the client's deposit).
- **Without the side-car an Android client cannot run into the payment deadlock:** the app is excluded
  from its own VPN, so its relayer traffic goes out directly. Its baseline still showed the pause.

## On production exits the side-car fails

Before these runs both clients tried the patched build on a production exit (Windows on GVPN-GER-1,
Android on "Bonnie Prince Charlie"). The side-car session opened, every relayer request then failed with
`the Curvy relayer is unreachable`, and the hold waited its full 150 s before connecting the old way.
Neither exit is known to allow `api.curvy.box:443` as a session target; the lab exit does. That the
missing entry is the cause was not verified on those exits. Opening the session succeeds either way,
because the exit connects to the target only when data arrives. The patch does not test the route
before it starts waiting.

## Other observations

- **Sessions of vanished clients stay alive on the exit.** Three paid sessions whose clients were killed
  or whose machine was deleted were still alive on the exit more than an hour later and filled its log
  with keep-alive lines at debug level, about 26,000 lines a minute.
- **The fixed 22 s wait is marginal on every platform.** From the client's deposit to the exit's
  confirmation: 18 to 26 s in these runs. Three connects attached about 1 s before the confirmation.
- **One slow payment without any error:** in block 4 the first deposit took 37 s from being queued to
  being accepted, with no retry or failure in the client's log, right after a session-open timeout.

## Not shown by these runs

- **Four connects per block.** The differences in late stalls and timeouts between builds are small
  samples; only the payment-gate result is clear-cut.
- **What causes the late stalls.** The builds on main differ from the older base by a new probing
  scheme, among other changes. That is a suspect, not a finding.
- **The exit's log is incomplete.** The exit's journal dropped between 110,000 and 205,000 messages per
  block because of the leftover sessions, and for the Android runs it only reached back 10 minutes when
  it was read. Missing times in `sessions.csv` are lines that were lost, not events that did not
  happen. The counters are not affected.
- **Client-side numbers are second-hand.** They come from the two client sessions' own logs and tests.
- **Android ran in an unstable emulator,** not on a device.

## Files

| File | Content |
| --- | --- |
| `exit-counters.csv` | The exit's payment-gate and packet counters at each block boundary |
| `sessions.csv` | Per paid session: the client's deposit and attach times as reported, and the exit's commitment, note and confirmation times from its log |

Counter snapshots and the copy of the exit's log are in `raw/gvpndows-2026-11-22/` (not in git).
