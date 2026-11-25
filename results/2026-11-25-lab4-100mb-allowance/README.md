# 2026-11-25: the exit OS canary's 100 MB pre-deposit allowance against the connect stall

**Measured:** whether a free allowance of 100 MB before the first deposit (as in exit OS canary
`5ed6c0b`) removes the interruption right after connecting, and whether the exit really serves 100 MB
before it holds a session back.

**Lab:** `vpn-lab4` (ams3), commit `3977455`. Exit hoprd `5.0.7-commit.ce54e11` (the binary of the
exit OS canary, same sha256), relays hoprd 5.0.4, client gnosisvpn 1.1.0, gnosis_vpn-server 0.7.1.
The only setting changed between runs is the exit's
`incoming_session_pix.max_predeposit_packets`: 68871 (100 MB, the canary's value) or the default 10000
(about 13 MB).

## Result

Each run: connect, then at once a full-speed download of 100 MB (1 GB in the blocked-payment run).

| Run | Allowance | Payment | Data before the exit held traffic back | Exit blocked the session for | Download |
| --- | --- | --- | --- | --- | --- |
| [100 MB, 1 to 3](iterations.csv) | 100 MB | confirmed 38 to 70 s after connect | never held back | 0 s | 100 MB in 78 to 80 s, 10.5 to 10.7 Mbit/s |
| [control, 1 to 3](../2026-11-25-lab4-default-allowance/iterations.csv) | 13 MB (default) | never; deposit tracking timed out | 13.4 MB after 17 s | 160 s, then the session was closed | **stopped at 13.4 MB for good** |
| [payment blocked](../2026-11-25-lab4-payment-blocked/iterations.csv) | 100 MB | delayed 200 s on purpose, never arrived | **93.3 MB after 75 s** | 101 s, then the session was closed after the 3-minute deposit wait | stopped at 93.3 MB |

In words:

- **The 100 MB allowance is real.** With the payment blocked, the client received 93.3 MB of payload,
  1355 bytes for each of the 68871 packets; the rest of each 1452-byte packet is tunnel overhead.
- **It removes the connect stall in this lab.** All three downloads ran through with no hold-back
  (exit counter `hopr_pix_gate_block_seconds_sum{reason="predeposit_exhausted"}` stayed at 0). The
  only gaps left are the 1 to 2 s ones also seen before.
- **With the default allowance, the same exit deadlocks every time,** with no fault injected: the
  13.4 MB run out at 17 s, the payment (which travels through the held-back tunnel) never completes,
  and the exit closes the session 3 minutes later. This is the
  [payment deadlock](../2026-11-22-payment-deadlock/README.md); on the earlier labs it needed a delay
  to show up.
- **The margin is thin.** The slowest payment took 70 s, by which point the 11 to 12 Mbit/s
  download had used about 90 of the 100 MB. A client that draws faster than about 12 Mbit/s for the
  first minute, or a payment slower than that, still runs into the same deadlock: the allowance
  makes it less likely; it does not change that the payment waits behind the gated tunnel.

## Cost

Three deposits of 5.94 wxHOPR from the client's pool (the 100 MB runs); the control and the blocked
run paid nothing.
