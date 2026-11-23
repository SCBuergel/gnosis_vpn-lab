# 2026-11-23: the side-car build against the production exit "Bonnie Prince Charlie"

**Measured:** one connect of the lab client to the production exit "Bonnie Prince Charlie" (Edinburgh,
`0xE7FD1aBD8DAA1BfA58D96a2620d6e827A64cB2fc`) with the side-car build (`gnosis_vpn-client` at `e6b33f36`
plus the branch `sidecar-relayer-hold`), followed by a 100 MB download; the client's log, and the exit's
log and configuration read on the exit itself. The test was stopped during its second connect.

**Repository commit:** `779b76c` (clean working tree; recorded in `measurement.json`, which names the
packaged client version 1.1.0 although the binaries were the side-car build)

**Result:** The side-car does not work on this exit, because the exit does not allow the payment relayer
as a session target. Connecting took 190.9 s and the download received nothing. The first stall after
connecting could not be tested.

## What happened

| Seconds after `connect` | Source | Event |
| --- | --- | --- |
| 23 to 35 | client | two session-open timeouts and two timeouts of the WireGuard registration before the paid session came up |
| 35 | client | side-car session opened; `holding the tunnel back until the first payment is confirmed` |
| 35 to 185 | client | every relayer request through the side-car failed: `the Curvy relayer is unreachable` |
| 185 | client | `first payment not confirmed through the relayer side-car - connecting without the hold reason=no deposit made within 150s` |
| 190.9 | client | connected; download started |
| 216 | client | `wg pump exited - requesting reconnect reason=NetworkClosed`; the download ended with 0 bytes |

## Why

The exit refuses the side-car's target. Its log, for every side-car session:

```
hopr_session_server_forwarder: TCP target resolved session_id=41f4be4ca1dc852379fc tcp_target=api.curvy.box:443 resolution=[<two addresses>]
hopr_lib::builder: session processing failed session_id=41f4be4ca1dc852379fc error=target not admitted: not all of [<two addresses>] are allowed by the target allow list
```

Its configuration, `/usr/share/gvpn-exit/hoprd.cfg.yaml`, lists two targets under
`session_ip_forwarding.target_allow_list`: `172.30.0.1:8000` and `172.30.0.1:51820`. The lab exit has a
third entry, `"api.curvy.box:443"` ([templates/exit.cfg.yaml](../../templates/exit.cfg.yaml)).

- **On the client this shows as sessions that get no answer:** each side-car session sent 268 bytes (the
  start of the TLS handshake) and received 0. On the lab exit such a session receives 4,362 bytes.
- **The exit itself reaches the relayer:** a request from the exit's own shell was answered in 0.12 s.
- **`hoprd` on the exit was last started on 2026-11-22 05:48 UTC.** A change to the allow list made
  after that, or made outside the file named above, is not in effect.

## Not shown by this run

- **Whether the first stall occurs on this exit with a working side-car.** That needs the allow-list
  entry on the exit and a restart of its `hoprd`.
- **Why the download failed after the fallback connect.** The tunnel closed 26 s after connecting; not
  looked into.
- One connect. The slow session opening (two timeouts) was not compared with an unmodified client.

One deposit of 5.94 wxHOPR was paid to the exit, by the session opened on the reconnect.
