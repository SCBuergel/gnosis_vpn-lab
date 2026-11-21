# 2026-11-21: connection time and the interruption after connecting

**Measured:** how long the client takes to connect to the lab exit, and when and for how long a
full-speed download started at the moment of connection is interrupted. Three iterations.

**Repository commit:** `77e113e`. The measurement script was run from the working tree on top of
`42bee5c` and committed unchanged, together with these results, as `77e113e`.

Three iterations on the lab as first built (client, exit and relays in one region, released software).
Each iteration: issue `connect`, and the moment the client reports `connected`, start a 100 MB download
at full speed. `remote/connect-stall-test.py` ran on the client and sampled the connection phase every
0.2 s and the download's progress every 0.1 s. A stall is at least 1 s without a single new byte.

## Result

| | Iteration 1 | Iteration 2 | Iteration 3 |
| --- | --- | --- | --- |
| `connect` issued until `connected` | 6.4 s | 5.1 s | 5.1 s |
| Download runs before it stops | 16.9 s | 16.8 s | 17.1 s |
| Data received before it stops | 13.4 MB | 13.3 MB | 13.3 MB |
| **Interruption, measured on the client** | **16.5 s** | **13.2 s** | **16.6 s** |
| Same interruption, the exit's own counter | 16.1 s | 13.2 s | 16.6 s |
| Payment: exit has the commitment until it sees the deposit | 35.6 s | 32.6 s | 36.3 s |
| Payment confirmed, counted from `connect` issued | 39.4 s | 35.1 s | 38.8 s |
| 100 MB download, total | 77.5 s | 76.8 s | 77.7 s |
| Average rate over the download | 10.8 Mbit/s | 10.9 Mbit/s | 10.8 Mbit/s |

In words:

- **Connecting takes 5 to 6 seconds** here. About 3 s of that is the client's verification ping.
- **The download then runs for 17 seconds and stops for 13 to 17 seconds.** It stops after 13.3 MB
  every time. That is the 10 000 packets the exit serves before it has seen the client's payment.
- **The interruption ends when the exit sees the payment**, 35 to 39 s after `connect` was issued.
  The client-side measurement and the exit's counter
  `hopr_pix_gate_block_seconds_sum{reason="predeposit_exhausted"}` agree to within 0.4 s.
- So the interruption is the payment time minus the time the free allowance lasts. A faster line
  would use up the allowance sooner and wait longer; a slow one may never notice.

## Shape of the transfer

`bytes-per-second.csv` has the per-second series. All three runs look the same:

| Phase | Seconds into the download | Rate |
| --- | --- | --- |
| Ramp-up | 0 to 17 | rises from 2 to 10 Mbit/s |
| Interruption | 17 to about 31 to 34 | 0 |
| Full speed | the next 17 to 20 s | 23 to 28 Mbit/s |
| Slower tail | from about 50 s to the end | about 12 Mbit/s, with one or two further gaps of 1 to 1.7 s |

Two things here are not explained yet:

- The ramp-up limits the rate before the interruption. The client raises its reply-block budget over
  20 s after connecting, which fits, but this run does not prove it.
- The rate halves about 50 s into the download and stays there. Sessions that had been up for
  minutes ran at 21 to 24 Mbit/s throughout ([first test](../2026-11-21-first-test/README.md)).

## Cost

Three sessions, three payments of 5.94 wxHOPR each from the client's pool. None was collected by the
exit: each session carried 100 MB and a collection needs about 400 MB. The client was topped up with
20 wxHOPR beforehand so that its pool refill could not fail during the third run.

## Files

- `iterations.csv`: one row per iteration with the numbers above.
- `bytes-per-second.csv`: bytes received in each second of the download, per iteration.
- Raw samples, exit counters and exit log excerpts: `raw/2026-11-21-connect-stall/` (not in git).

## How to repeat

With the client worker running (`./lab client start`) and disconnected:

```bash
./lab stall-test my-label --iterations 3
```

These three iterations were run by hand with the same script, before that command existed.
