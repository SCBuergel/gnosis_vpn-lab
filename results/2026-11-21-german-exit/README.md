# 2026-11-21: the same test against a production exit (GVPN-GER-1)

**Measured:** one iteration of the connect-and-download test (connection time, when and for how long a
full-speed 100 MB download is interrupted), with the lab client connecting to the production exit
GVPN-GER-1 instead of the lab exit; and which relays the client's paths to and from that exit used.

**Repository commit:** `2281af5` (clean working tree; recorded in `measurement.json`).

The request was for "the Berlin exit". No exit on `piz-palu-prod` carries that name; the exit named
Berlin exists only on the older `jura` network, which this client cannot join. GVPN-GER-1
(`0xe5ce4ae09ac49e74f3a4d649b93cf0e2cf1de7bf`, listed with country DE) is the German exit here and was
used on that assumption. Its city is not published.

## Result

| | GVPN-GER-1 (this run) | Lab exit (3 runs, [connect-stall](../2026-11-21-connect-stall/README.md)) |
| --- | --- | --- |
| `connect` issued until `connected` | 6.8 s | 5.1 to 6.4 s |
| Download runs before it stops | 16.2 s | 16.8 to 17.1 s |
| Data received before it stops | 13.0 MB | 13.3 to 13.4 MB |
| **Interruption** | **16.4 s** | **13.2 to 16.6 s** |
| Further interruptions of 1 s or more | none | one or two, 1.0 to 1.7 s |
| Rate after the interruption | steady 9.6 Mbit/s | 23 to 28 Mbit/s, then about 12 Mbit/s |
| Peak rate in any second | 14.4 Mbit/s | 27 to 30 Mbit/s |
| 100 MB download, total | 108.9 s | 76.8 to 77.7 s |
| Average rate over the download | 7.7 Mbit/s | 10.8 to 10.9 Mbit/s |

In words:

- **The interruption is the same.** It starts after 13 MB and lasts 16 s, as with the lab exit. It
  does not depend on our exit or on our relays carrying the return traffic.
- **Connecting is as fast** as to the lab exit.
- **The rate afterwards is lower and flat**, 1.2 MB per second almost every second. Production exits
  cap each client at 10 Mbit/s (the appliance's per-peer limit); the lab exit has no such limit.

## Which relays carried this session

From the client's planner log (`planner-paths.json`, 45 candidate sets per direction):

| Direction | Relays in the candidate paths |
| --- | --- |
| Forward, client to exit | relay1, relay2, relay3, and only those |
| Return, exit to client | 8 relays of other operators, none of ours |

- The forward direction is confined by the client's own channels, which exist only to our relays. Our
  three relays forwarded 9,834, 10,181 and 10,022 packets during the run.
- The return direction needs a funded channel from the exit to its first relay. GVPN-GER-1 holds 8
  open channels, none to a lab relay, so every return path used someone else's relay.
- This is the expected limit of the design: only an exit we configure can keep the return traffic on
  our relays. With a production exit, half of the session is outside the lab.

## Cost

One session payment of 5.94 wxHOPR from the client's pool, to an exit that is not ours. The session
carried 100 MB, below the roughly 400 MB after which an exit can collect a payment.

## Files

- `measurement.json`: what, when, commit, software, destination.
- `iterations.csv`, `bytes-per-second.csv`: the measurement.
- `planner-paths.json`: relays named in the client's candidate paths, per direction.
- Raw sample, counters and client log: `raw/2026-11-21-german-exit/` (not in git).
