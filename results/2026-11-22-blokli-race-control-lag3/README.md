# Unmodified client, new notes reported 3 s late

**Measured:** three connects with the unmodified build of `gnosis_vpn-client` (main at `e6b33f36`) while the
proxy reported new Curvy notes 3 s late.

**Repository commit:** `4dc838e` (clean working tree; recorded in `measurement.json`, which names the
packaged client version 1.1.0 although the binaries were the build named in `client_build`)

**Result:** None of the 3 deposits was recorded by the client: each was logged as `deferred` after one look
and the session stayed at `payment_pending`, 0 of 1 chunks paid. The exit confirmed all 3, 35 to 40 s
after `connect`. In run 2 Blokli itself answered "unknown"; the proxy changed nothing in that run.

Part of the series described in [2026-11-22-blokli-race](../2026-11-22-blokli-race/README.md), which has the method and the per-run table.
