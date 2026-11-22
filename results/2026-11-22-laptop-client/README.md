# 2026-11-22: the lab client's setup on a laptop outside the lab

**Measured:** three iterations of the connect-and-download test (two with an immediate download, one with
90 s idle first) from a second client, a laptop on a home
connection, configured like the lab client (gnosisvpn 1.1.0, lab exit pinned, channels only to the three
lab relays). Client-side numbers come from the test script's output on the laptop; the payment timeline
comes from the lab exit's log and, for the cause, from the laptop's own log.

**Repository commit:** `1f5c2c4`. The laptop ran `connect-stall-test.py` as installed by
`local-client/setup.sh` at that commit for the first two runs; the third run is described below.

## Result

| | Laptop, run 1 | Laptop, run 2 | Lab client (4 runs) |
| --- | --- | --- | --- |
| `connect` issued until `connected` | 6.9 s | 5.3 s | 5.1 to 6.6 s |
| Download runs before it stops | 17.0 s | 17.0 s | 16.8 to 17.1 s |
| Data received before it stops | 13.3 MB | 13.4 MB | 13.2 to 13.4 MB |
| **Interruption** | **245 s, never resumed** | **245 s, never resumed** | 13.2 to 16.6 s |
| Download complete | no, 13 % | no, 13 % | yes |

Both runs are the same: the download stopped at the usual place and never came back.

## What the exit saw

| Step | Run 1 (UTC) | Run 2 (UTC) |
| --- | --- | --- |
| Commitment of the first session received | 00:29:42.6 | 00:35:11.1 |
| Exit gives up: `DepositTimeout` after its 3-minute limit, session closed | 00:32:42.6 | about 00:38:11 |
| Client has reconnected and its new commitment arrives | 00:32:44.8 | 00:38:12.9 |
| Deposit of the **new** session confirmed | 00:33:53.9 (69 s) | 00:38:44.3 (31 s) |

- In both runs the first session's payment did not arrive within 180 s, the exit closed the session,
  and the client reconnected within 0.2 s and paid again.
- In both runs the payment of the session after the reconnect went through quickly.
- Each run therefore cost two payments (11.88 wxHOPR) for 13 MB.

## Third run: 90 seconds idle before the download

**Repository commit:** `18cd375` (`lab 1 90` as installed by `local-client/setup.sh` at that commit).

| | Laptop, idle run |
| --- | --- |
| `connect` issued until `connected` | 6.9 s |
| Client reports the payment made | 12 s after connecting |
| Download after the 90 s idle time | 100 MB complete in 54.9 s, 15.3 Mbit/s |
| Interruptions | none |

With no download running when the payment is submitted, everything works: no interruption at all, not
even the 15 s one the lab client always has.

## Cause, from the laptop's own log

The payment request to the outside payment service (the Curvy relayer, `api.curvy.box`) cannot get
through while the download is running:

| Time (UTC), run 2 | Laptop log |
| --- | --- |
| 00:35:09.5 | payment commitment generated, deposit queued |
| 00:35:13.8 | connected; the download starts |
| 00:35:40.6 | `the Curvy relayer is unreachable: error sending request for url (https://api.curvy.box/...)` |
| every 10.6 s until 00:37:58 | the same line, 14 times |
| 00:35:58.7 | `inbound stalled while the exit awaits PIX payment - holding` |
| 00:38:09.1 | `deposit flush failed ... the Curvy relayer is unreachable` |
| 00:38:10.7 | `PIX deposit failed during payment hold - reconnecting` |
| 00:38:18.6 | after the reconnect: proof built in 1.07 s |
| 00:38:23.4 | `single deposit flushed successfully`, 12 s after the new commitment |

Run 1 shows the same lines, 15 times between 00:30:13 and 00:32:41.

- **Confirmed:** while the exit holds back the session's traffic, the client cannot reach the relayer,
  so the payment that would end the hold cannot be made. The hold lasts until a timeout: the exit's
  3 minutes in run 1, the client's own 3-minute payment limit in run 2.
- **Confirmed:** as soon as a fresh session exists and no download is using it, the same request
  succeeds within 12 s. The laptop's processor is not the problem: its proofs take 1.0 s, faster than
  the lab client's 2.1 s.
- **Confirmed, and costly:** in run 1 the payment for the first session was sent at 00:32:56, 14 s
  after the exit had closed that session. That 5.94 wxHOPR went to a session that no longer exists.
  Run 1 therefore paid twice, run 2 once after a failed attempt.
- **Not yet explained:** why the laptop's first request, sent before the exit starts holding traffic,
  already fails, while the lab client's gets through with about 5 s to spare. The first failure is
  logged 30 s after the request was due, which matches the relayer request's 30 s timeout, so that
  first request seems to hang from the start. Two candidates: it competes with the download for the
  tunnel during the slow first seconds, or it uses a connection opened before the tunnel came up.

Run 1 had one more delay on top: a new client's payment pool is empty, and it first moved 35.35 wxHOPR
from its Safe into the pool (00:29:42 to 00:30:07), which alone outlasts the free allowance.

## Next steps

1. In the lab, check which route the lab client's traffic to the relayer takes while connected, and
   make it lose the race on purpose (delay that traffic) to reproduce the 3-minute hold there.
2. Test whether the first request fails because of the download: start the download 5 s, 10 s and 20 s
   after connecting instead of at once.
3. Compare with the unmerged upstream changes that touch exactly this (gnosis_vpn-client `a209848`,
   edge-client `c579727`).

Raw files (three result files, the log excerpt with addresses removed, the path check) are in
`raw/2026-11-22-laptop-client/upload-1/`, not in git. The path check passed: all 284 forward and 284
return candidate sets in the laptop's log name only relay1, relay2 and relay3.
