# 2026-11-22: a second lab in New York, and cold-start connects of the patched client

**Measured:** on a second, separate copy of the lab (five machines in DigitalOcean `nyc3`, name
`vpn-lab2`): first the lab's standard test with the packaged client 1.1.0, twice, to see whether the new
lab behaves like the first one in Frankfurt. Then cold-start connects, each after a restart of the
client's node: 10 with the patched client to the lab's own exit, 3 with the patched client and 10 with
the unmodified client to the production exit GVPN-GER-1. The cold-start connects time each step of
connecting from the client's log; no download follows them.

**Repository commit:** `65f4c82` on branch `lab2` (clean working tree for the two standard tests, as
recorded in their `measurement.json`). That branch is `main` plus one commit: a deletion timer named
after the lab, and a `lab.toml` with the second lab's name and region. The cold-start connects were run
with `remote/cold-connect-test.py`, which was added after that commit and started by hand on the client.

**Result:** The new lab behaves like the first: connected in 5 s, 10.8 Mbit/s, and a pause when the
exit's free allowance is used up, 23 to 26 s here against 13 to 17 s in Frankfurt. All 10 cold-start
connects of the patched client to the lab's exit succeeded, in 42 to 72 s, seven of them in 47 s. The
65 s delay in the probe step that an Android client showed in 2 of 6 connects did not appear in any of
the 23 cold-start connects.

## The new lab against the first one

The standard test: connect, start a 100 MB download at once, time every interruption. Packaged client
1.1.0, nothing injected.

| Test | Run | Connect | Pause when the allowance is used up | Held by the exit's payment gate | 100 MB download |
| --- | --- | --- | --- | --- | --- |
| First (22:46 UTC) | 1 | 5.2 s | never resumed | 160.6 s | stopped at 13.5 MB |
| First | 2 | 5.1 s | never resumed | 160.1 s | stopped at 13.5 MB |
| First | 3 | 5.1 s | 19.8 s | 19.8 s | complete in 77 s, 10.8 Mbit/s |
| Repeat (22:57 UTC) | 1 | 5.1 s | 25.3 s | 25.2 s | complete in 78 s, 10.7 Mbit/s |
| Repeat | 2 | 5.1 s | 22.9 s | 22.8 s | stopped at 16.3 MB after a further stall of 75 s |
| Repeat | 3 | 5.0 s | 25.5 s | 25.5 s | complete in 77 s, 10.9 Mbit/s |
| Frankfurt ([connect-stall](../2026-11-21-connect-stall/README.md)) | 1 to 3 | 5.1 to 6.4 s | 13.2 to 16.6 s | 13.2 to 16.6 s | complete in 77 to 78 s, 10.8 to 10.9 Mbit/s |

- **Runs 1 and 2 of the first test are the payment deadlock, with nothing injected.** On its very first
  connect the client's payment pool was empty and had to be filled from its Safe first, which took 26 s
  (`funding the deposit pool from the Safe` at 22:46:15, confirmed at 22:46:41). By then the exit was
  holding the session's traffic, the relayer could no longer be reached through it, and the exit closed
  the session after its 180 s deposit limit. Run 2 failed the same way while the client was still
  paying deposits for the sessions of run 1; its cause was not traced further.
- **Two deposits were paid for sessions the exit had already closed** (flushed at 22:49:37 and 22:50:18,
  for sessions closed at 22:49:16 and before), 5.94 wxHOPR each.
- **From the third connect on, the lab behaves like the first one,** with a pause about 9 s longer.
- **The 75 s stall in run 2 of the repeat is not the payment gate:** the gate held traffic for 22.8 s
  only. It is a stall of the kind seen late in downloads on Windows
  ([windows-android](../2026-11-22-windows-android/README.md)). Not explained.

## Cold-start connects of the patched client to the lab's own exit

Build: `gnosis_vpn-client` at `c768ccf1` (branch `sidecar-relayer-hold`: side-car session and hold),
without the hopr-strategy fix. Before each connect the worker was stopped and started again; the connect
was issued 30 s after the exit was reported routable (14 to 20 s after the start). Times are seconds
after `connect` was issued.

| Attempt | Probe step took | Proof ready | Relayer reports the deposit included | Hold notices | Hold ends | Connected |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.11 | 12.1 | 19.3 | 21.8 | 43.8 | 47.1 |
| 2 | 0.12 | 36.8 | 43.4 | 46.9 | 68.9 | **72.2** |
| 3 | 0.16 | 13.7 | 20.4 | 21.8 | 43.8 | 47.1 |
| 4 | 0.15 | 11.4 | 18.6 | 21.9 | 43.9 | 47.2 |
| 5 | 0.15 | 11.5 | 29.2 | 31.8 | 53.8 | **57.0** |
| 6 | 0.16 | 11.3 | 18.4 | 21.9 | 43.9 | 47.1 |
| 7 | 0.11 | 11.1 | 16.1 | 16.8 | 38.8 | 42.1 |
| 8 | 0.14 | 10.7 | 18.5 | 21.9 | 43.9 | 47.1 |
| 9 | 0.14 | 12.6 | 19.8 | 21.8 | 43.8 | 47.1 |
| 10 | 0.17 | 10.8 | 17.9 | 21.8 | 43.8 | 47.1 |

- **10 of 10 connected.** No session-open timeout, no failed probe check, no failed relayer request, no
  deposit the client lost track of.
- **Where the 47 s go** (attempt 4): the exit asks for the deposit at 0.8 s; the client talks to the
  relayer until about 9.4 s; the proof takes 2 s; the relayer reports the deposit included 7.2 s later;
  the hold notices 3.3 s after that, waits its fixed 22 s, and attaching takes 3.3 s.
- **The steps of 5 s:** the client's payment state is refreshed every 5 s, so the hold notices a payment
  at 16.8, 21.8, 26.8 s and so on. Deposits reported between 16.8 and 21.8 s all give a 47 s connect.
- **The two slower connects were slow in the payment,** with no warning or error in the log: in attempt 2
  the proof was ready 25 s later than usual, so the time went into the requests before it; in attempt 5
  the relayer's report came 11 s later than usual.
- **About 5 s slower than in Frankfurt** (42 s there,
  [main-patched](../2026-11-22-main-patched/README.md)): the requests before the proof take about 8.6 s
  here against about 5.5 s there.

## Cold-start connects to the production exit GVPN-GER-1

An Android client with the same code base had shown a 65 s delay in the probe step, the check that
precedes connecting, in 2 of 6 cold-start connects to this exit: the probe's version check timed out
after 60 s and passed when retried.

| Build | Attempts | Probe step took | Connected after | Session-open timeouts |
| --- | --- | --- | --- | --- |
| patched (`c768ccf1`) | 3, then stopped | 0.54 to 0.60 s | 155.8 to 156.5 s | 0 |
| main, unmodified (`e6b33f36`) | 10 | 0.51 to 0.77 s | 5.7 to 10.5 s | 0 |

- **The delay did not appear** in 13 connects to this exit, nor in the 10 to the lab's exit.
- **The patched client needs 156 s on this exit for a known reason:** the exit does not let the side-car
  reach the relayer, every relayer request fails, and the hold waits its 150 s limit before connecting
  the old way. That series was stopped after three attempts because its connect time was predetermined.
  The unmodified build has the same probe code and no hold.
- **No deposit was paid in these 13 connects:** each was disconnected within seconds of being connected,
  before the deposit was made.

## Not shown by these runs

- **Why the Android client was delayed.** It ran from another network (AWS Stockholm) with its own
  platform changes and 17 channels to public relays. 23 clean connects from one Linux client make a
  general fault of the code base unlikely; they do not rule out something specific to that exit's
  return paths, that network or that build.
- **The hopr-strategy fix was not in the patched Linux build.** No deposit was lost track of in these
  10 connects; in earlier runs that happened in about one of six.
- **Downloads after the cold-start connects.** They time connecting only.
- **One client, one evening.** The second lab's client had been funded two hours earlier.

## Setup notes

- **Two labs side by side.** The second lab has its own folder (state, keys, raw data), its own machine
  tag and its own deletion timer. The timer's systemd unit used to be `vpn-lab-destroy` for every
  deployment, so setting it for a second lab would have replaced the first lab's deadline; it is now
  named after the lab.
- **Deletion timer of the second lab:** 2026-11-24 22:35 UTC.
- **Funds:** 96 wxHOPR to the four node Safes, 240.36 wxHOPR to the client (120.36 at setup, 120 as a
  top-up before the series), about 0.08 xDAI.

## Reproduce

```bash
./lab stall-test my-label --iterations 3 --yes        # the standard test

# cold-start connects, on the client as root (public SSH is cut while connected: use lab-client-priv)
python3 cold-connect-test.py gvpnlab lab 10 30 300    # user, destination id, attempts, wait, limit
```

## Files

| File | Content |
| --- | --- |
| `first-test-iterations.csv`, `first-test-measurement.json` | The first standard test |
| `repeat-test-iterations.csv`, `repeat-test-measurement.json` | Its repeat |
| `cold-start-attempts.csv` | One row per cold-start connect of all three series, with the time of every step |

Raw samples, counters and the test script's full output are in the second lab's `raw/` folder (not in
git).
