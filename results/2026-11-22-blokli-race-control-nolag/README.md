# Unmodified client, Blokli through the proxy without lag

**Measured:** three connects with the unmodified build of `gnosis_vpn-client` (main at `e6b33f36`), reading Blokli
through the lag proxy with the lag off. Per connect: whether the client recorded the session's first
deposit and when the exit confirmed it.

**Repository commit:** `4dc838e` (clean working tree; recorded in `measurement.json`, which names the
packaged client version 1.1.0 although the binaries were the build named in `client_build`)

**Result:** All 3 deposits were recorded by the client (`funded`, 1 of 1 chunks paid) and confirmed by the
exit. The proxy by itself changes nothing. Run 2 paid 35 s later than the others; not explained.

Part of the series described in [2026-11-22-blokli-race](../2026-11-22-blokli-race/README.md), which has the method and the per-run table.
