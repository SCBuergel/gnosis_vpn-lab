# Retransmission on all control sessions, one relay black-holed

**Measured:** 3 connects of lab 2's client to lab 2's exit while one of the three relays dropped
everything between itself and the exit, with the build `sidecar-2666503` (client main `c7dc58f6`, merged
hopr-strategy fix, side-car, hold) and this entry added to the client's `config.toml`:
`[connection.bridge] capabilities = ["segmentation", "retransmission", "retransmission_ack_only",
"no_rate_control"]`. Each connect was followed by a download cut off after 120 s.

**Repository commit:** `0156666` (branch `sidecar-retransmission`, clean working tree; `measurement.json`
names the packaged client version 1.1.0 although the binaries were the build named in `builds`)

**Result:** All 3 connects came up, in 229.6, 52.3 and 70.3 s, and paid their deposit through the
side-car 17.6, 22.1 and 19.2 s after it was requested, without a relayer error. The same build without
the entry never began to connect in 300 s, twice. The downloads were poor: 28.6, 5.7 and 7.6 MB in 120 s.

Part of the series described in
[2026-11-23-sidecar-retransmission](../2026-11-23-sidecar-retransmission/README.md).
