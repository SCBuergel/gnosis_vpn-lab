# 2026-11-23: retransmission on the side-car and on the control sessions, with one relay black-holed

**Measured:** 7 connects of lab 2's client (New York) to lab 2's exit while one of the three relays dropped
everything between itself and the exit. Builds of `gnosis_vpn-client` main at `c7dc58f6` with the
merged hopr-strategy fix, the side-car session and the hold; three variants: as it is, with
retransmission added to the side-car session in code, and with retransmission switched on for all
control sessions in the client's configuration. Each connect had 300 s to come up and was followed at
once by a download cut off after 120 s. This folder has the first 4 connects;
[control-retransmission](../2026-11-23-control-retransmission/README.md) has the other 3.

**Repository commit:** `0bfab9b` for this folder, `0156666` for the other (branch `sidecar-retransmission`,
clean working tree; `measurement.json` names the packaged client version 1.1.0 although the binaries were
the builds named in `builds`)

**Result:** With one relay black-holed, the client as it is never began to connect in 300 s (2 of 2).
With retransmission on all control sessions it connected and paid in 3 of 3 (52, 70 and 230 s). With
retransmission on the side-car alone it connected in 1 of 2. The failures come before the side-car is
used: the client's checks before connecting run over sessions without retransmission and time out.

| Variant | Connects | Came up within 300 s | `connect` until connected | Deposit accepted, after it was requested | Relayer errors |
| --- | --- | --- | --- | --- | --- |
| As it is | 2 | **0** | | | |
| Retransmission on the side-car only (code) | 2 | 1 | 67 s | 38.7 s | 0 |
| Retransmission on all control sessions (configuration) | 3 | **3** | 52, 70, 230 s | 17.6, 19.2, 22.1 s | 0 |

## What fails, and where

- **The same lines as on Android.** The client's log has `probe check failed check=Version`, `check=Ping`
  and `check=Load` after 60 s timeouts, `probe session never became ready - backing off`, and
  `session initiation attempt timed out`.
- **The checks before connecting are the first to break.** In both connects of the unmodified variant
  the client stayed in "disconnected" for the whole 300 s: its probe of the exit never passed, so it
  never started the connection. No deposit was requested, and nothing was paid.
- **These checks, the registration, the ping and the side-car all use the "bridge" capabilities,**
  `segmentation` and `no_rate_control`. A request whose frame is lost is never repeated; the client waits
  for a timeout. `gnosis_vpn-lib/src/config/v7.rs` says: "Bridge capabilities must never include
  retransmissions — those require additional SURBs."
- **Opening a session is not covered by retransmission.** The variant with retransmission on all control
  sessions still logged 5, 0 and 1 session-open timeouts; the 230 s connect is the one with 5.
- **The download stays poor with a black-holed relay in every variant:** 5.7 to 28.6 MB in 120 s, with
  11 to 15 gaps of 1 to 2 s. The tunnel session has no retransmission by design.

## The fault that was injected

`./lab relay-blackhole relay3 on` adds two firewall rules on that relay which drop all UDP to and from the
exit's address ([remote/relay-blackhole.sh](../../remote/relay-blackhole.sh)). The relay keeps its
connections to everyone else, so it stays a candidate for paths.

- **The loss was mostly on the way back.** The relay forwarded 290 to 655 packets per connect against
  8,500 to 18,000 for each of the other two: the client's planner had mostly stopped sending through it.
  Replies from the exit that the client had routed through that relay are lost.
- **The exit's log has no report of dropped frames for these sessions,** which fits loss in the reply
  direction. The counts of lost frames in `iterations.csv` are therefore all 0 and say nothing here.

## The three variants

| Name in the files | What it is |
| --- | --- |
| `sidecar-2666503` | Branch `sidecar-on-c7dc58f`: client main `c7dc58f6`, hopr-strategy pinned to the merged `2c209bd3`, side-car session, hold |
| `sidecar-retx-31d71dd` | The same plus one commit: the side-car session asks for `RetransmissionNack` and `RetransmissionAck` |
| `sidecar-2666503` with a configuration entry | The first build, with `[connection.bridge] capabilities = ["segmentation", "retransmission", "retransmission_ack_only", "no_rate_control"]` in `config.toml`. The side-car takes its capabilities from the same entry |

Both branches are local, in the client repository's working copy; they are not pushed.

## Not shown by these runs

- **That the side-car loses data when the rest works.** No relayer request failed in any connect that
  reached the payment. The Android runs that prompted this test did not show it either.
- **What retransmission costs in SURBs.** Not measured. That cost is the stated reason it is off.
- **A milder fault.** A relay that loses everything is the extreme case; with it, the comparison of the
  side-car alone could not be made, because the client rarely got that far.
- **Small numbers:** 2, 2 and 3 connects, limited by the funds on lab 2's client.
- **The clean path.** Not run here; 10 of 10 connects with the earlier side-car build had come up on this
  lab the evening before.

## Reproduce

```bash
./lab relay-blackhole relay3 on          # also: off, status
./lab compare-builds my-label --builds sidecar-2666503 sidecar-retx-31d71dd --rounds 2 --seconds 120
./lab relay-blackhole relay3 off
```

## Files

| File | Content |
| --- | --- |
| `iterations.csv` | One row per connect: build, whether and when it connected, deposit, relayer errors, relay counters |
| `bytes-per-second.csv`, `download-rate.svg` | Bytes per second of each download |
| `measurement.json` | What, when, commit, worker checksums, which relay was black-holed |

Raw samples and logs are in `raw/lab2/2026-11-23-sidecar-retransmission/` (not in git).
