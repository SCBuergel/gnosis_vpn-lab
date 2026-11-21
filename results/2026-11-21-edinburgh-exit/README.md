# 2026-11-21: the same test against the Edinburgh exit (Bonnie Prince Charlie)

**Measured:** one iteration of the connect-and-download test (connection time, when and for how long a
full-speed 100 MB download is interrupted), with the lab client connecting to the production exit
"Bonnie Prince Charlie" (Edinburgh, `0xE7FD1aBD8DAA1BfA58D96a2620d6e827A64cB2fc`); which relays the
client's paths used; and, from the logs of both ends, why connecting took longer.

**Repository commit:** `a306231` (clean working tree; recorded in `measurement.json`).

This exit is the operator's own appliance behind a home connection, so its log could be read as well.

## Result

| | Edinburgh (this run) | GVPN-GER-1 ([run](../2026-11-21-german-exit/README.md)) | Lab exit ([3 runs](../2026-11-21-connect-stall/README.md)) |
| --- | --- | --- | --- |
| `connect` issued until `connected` | **28.3 s** | 6.8 s | 5.1 to 6.4 s |
| Download runs before the long stop | 17.2 s | 16.2 s | 16.8 to 17.1 s |
| Data received before the long stop | 13.0 MB | 13.0 MB | 13.3 to 13.4 MB |
| **Long interruption** | **14.9 s** | 16.4 s | 13.2 to 16.6 s |
| Other interruptions of 1 s or more | 2.8 s (5 s in), 1.1 s (72 s in) | none | one or two, 1.0 to 1.7 s |
| Rate after the interruption | 18 to 20 Mbit/s, then about 12 | steady 9.6 Mbit/s | 23 to 28 Mbit/s, then about 12 |
| 100 MB download, total | 77.0 s | 108.9 s | 76.8 to 77.7 s |
| Exit: commitment received until deposit seen | 34.5 s | not visible | 32.6 to 36.3 s |

In words:

- **The interruption after connecting is the same again:** it starts at 13.0 MB and lasts 15 s.
- **Connecting took 28 s instead of 5 to 7 s**, and the logs show exactly why (next section).

## Why connecting took 28 seconds

Before it registers with an exit, the client opens a first session to it. Here that first attempt
failed in one direction only:

| Time (UTC) | Where | Event |
| --- | --- | --- |
| 23:37:44.849 | client | sends the session request |
| 23:37:44.890 | exit | receives it 41 ms later and logs "new session established" |
| — | client | the exit's answer never arrives |
| 23:38:04.849 | client | "session initiation attempt timed out", exactly 20.0 s after sending |
| 23:38:07.039 | client | second request, after a 2 s pause |
| 23:38:07.128 | client | "new session established", 89 ms later |

- The request reached the exit at once; the answer was lost on the way back. The way back runs
  through a relay of another operator (see below), which the lab cannot observe.
- The client then waited its full fixed timeout. The 20 s is not adaptive: it is 5 s times (hops there
  + hops back + 2), and the retry succeeded in under 0.1 s.
- So 22 of the 28 seconds were one lost answer plus a fixed wait. This is the first observation in the
  lab of slow connection establishment, and it points at the timeout rather than at the network.

## Which relays carried this session

From the client's planner log (`planner-paths.json`, 39 candidate sets per direction):

| Direction | Relays in the candidate paths |
| --- | --- |
| Forward, client to exit | relay1, relay2, relay3, and only those (about 10,000 packets each) |
| Return, exit to client | 5 relays of other operators, none of ours |

The exit holds 5 open channels, none to a lab relay. As with GVPN-GER-1, the return half of the
session is outside the lab.

## Open observation

At the end of the download the client still reported the payment as pending (`payment_pending`,
0 chunks paid), although the exit had logged the deposit as confirmed 43 s earlier and traffic was
flowing. Not investigated.

## Cost

One session payment of 5.94 wxHOPR from the client's pool to this exit. The session carried 100 MB,
below the roughly 400 MB after which an exit can collect a payment.

## Files

- `measurement.json`: what, when, commit, software, destination.
- `iterations.csv`, `bytes-per-second.csv`: the measurement.
- `planner-paths.json`: relays named in the client's candidate paths, per direction.
- Raw sample, counters and client log: `raw/2026-11-21-edinburgh-exit/` (not in git).
