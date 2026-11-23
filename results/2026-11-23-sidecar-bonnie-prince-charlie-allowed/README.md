# 2026-11-23: side-car against "Bonnie Prince Charlie" with the relayer allowed on the exit

**Measured:** connects of the lab client to the production exit "Bonnie Prince Charlie" (Edinburgh) after
`api.curvy.box:443` was added to the exit's session allow list with a temporary override: the side-car
build (`gnosis_vpn-client` at `e6b33f36` plus the branch `sidecar-relayer-hold`) and, for comparison,
the unmodified build of the same commit. Each connect was followed at once by a download of a 100 MB
file, cut off after 150 s. One usable connect per build.

**Repository commit:** `caf9c23` (clean working tree). `measurement.json` and `iterations.csv` are from
the first connect, run with `./lab stall-test`; the two connects in the table were run with
`connect-stall-test.py` directly and are in `bytes-per-second.csv`.

**Result:** With the side-car build the pause after about 13 MB is gone (1.5 s instead of 13.2 s), but the
download rate collapsed after 40 s and only 62 MB arrived in 150 s; the unmodified build delivered the
100 MB in 75 s. Connecting took 92 s with the side-car build and 72 s without.

| | Side-car build (connect 2) | Unmodified build |
| --- | --- | --- |
| `connect` until connected | 92.2 s, of which 62.1 s is the hold until the payment | 72.3 s, of which 65 s passed before the first connection phase |
| First deposit accepted by the relayer, after the paid session opened | 38.8 s, through the side-car | 12.0 s, through the tunnel |
| Interruption at about 13 MB | 1.5 s | 13.2 s |
| Download | 61.9 MB in 150 s, cut off | 100 MB in 75.2 s |
| Rate in 10 s blocks, MB/s | 0.4, 1.0, 1.4, 1.4, 0.2, 0.1, 0.3, 0.5, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1 | 0.3, 1.0, 0.0, 2.2, 2.4, 2.4, 1.5, 0.7 |
| Client's payment state after the download | funded, 1 of 1 paid | funded, 1 of 1 paid |

## The change on the exit

The exit's `hoprd` renders its configuration from a template named by `GVPN_HOPRD_CFG_TEMPLATE`. A copy
of the image's template with one more line under `session_ip_forwarding.target_allow_list`,
`- "api.curvy.box:443"`, was put at `/etc/hoprd-v5/hoprd.cfg.test.yaml`, and a systemd drop-in
(`/etc/systemd/system/hoprd.service.d/60-test-allow.conf`) points `hoprd` at it. `hoprd` was restarted at
00:54 UTC. After that the exit logged no `target not admitted` for the relayer, and side-car sessions
received the relayer's TLS answer.

Both files are still in place. To undo: remove both, `systemctl daemon-reload`, `systemctl restart hoprd`.

## The first connect after the change failed, for reasons other than the allow list

| UTC | Event |
| --- | --- |
| 00:57:51 | Three minutes after its restart the exit could not answer the payment request: `deposit pool did not supply deposit data for the SSA batch ... within 3s`. The client saw `UnacceptablePixParams`, did not hold, and the tunnel closed. |
| 01:00 to 01:05 | Three reconnects in place. In each the client's deposit failed within 10 s with `Curvy indexer query failed: error sending request for url (https://blokli.../graphql)`, the hold gave up (`reason=the deposit failed`) and the client connected without it. With no deposit made, the download stopped at 13.8 MB and stayed there. |

This Blokli failure has not occurred in any run against the lab exit. It followed a reconnect that resumes
the previous connection each time; a fresh connect (connect 2) paid normally. Cause not found.

## Not shown by these runs

- **Whether the collapse of the rate belongs to the side-car build.** One connect per build. During the
  side-car download the client's pool tried once a minute to refill from a Safe that held too little,
  and the side-car listener kept opening sessions to the relayer, three of which timed out. Whether that
  load on the path is the cause was not tested. A similar loss of rate was reported for the side-car
  build on Windows ([windows-android](../2026-11-22-windows-android/README.md)) and was not seen in 150 s
  downloads through the lab exit.
- **Why opening sessions to this exit is slow.** Both builds logged session-open timeouts; the
  unmodified connect spent 65 s before its first phase.
- The side-car build did not contain the hopr-strategy fix.
