# 2026-11-22: the lab client's setup on a laptop outside the lab

**Measured:** two iterations of the connect-and-download test from a second client, a laptop on a home
connection, configured like the lab client (gnosisvpn 1.1.0, lab exit pinned, channels only to the three
lab relays). Client-side numbers come from the test script's output on the laptop; the payment timeline
comes from the lab exit's log.

**Repository commit:** `1f5c2c4`. The laptop ran `connect-stall-test.py` as installed by
`local-client/setup.sh` at that commit. The laptop's own log has not been collected yet.

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

## Hypothesis (not yet proven)

The client's payment has to be submitted to an outside service (the Curvy relayer). If that request
travels through the VPN tunnel, it is caught by the very interruption it is supposed to end: once the
exit has parked the session's return traffic, the answer to the payment request cannot come back.

What fits:

- The lab client finishes submitting 16 s after the commitment (proof done after 7.5 s, relayer answer
  after 16 s), and its download uses up the free allowance about 22 s after the commitment. It wins a
  race by about 5 s. Anything slower loses it.
- After a reconnect no download is running (the old one is dead), so nothing uses up the new session's
  allowance, and the payment goes through in 31 to 69 s.
- An unmerged upstream change (gnosis_vpn-client `a209848`, GNO-1472) says the armed killswitch lets the
  relayer through only via an attached tunnel.

What is missing: the laptop's log, which shows when its proof was done and whether the relayer request
failed or hung.

## Next steps

1. Collect the laptop's log excerpt (`lab-send`).
2. On the laptop, connect and stay idle for 90 s before downloading (`lab 1 90`). If the hypothesis
   holds, the payment is confirmed during the idle time and the download runs without the long stop.
3. In the lab, make the lab client lose the race on purpose, for example by delaying its traffic to the
   relayer, and see whether the 3-minute timeout and paid reconnect appear there too.
