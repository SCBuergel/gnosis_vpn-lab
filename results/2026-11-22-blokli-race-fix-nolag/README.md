# Fixed client, Blokli through the proxy without lag

**Measured:** three connects with the fixed build (main at `e6b33f36` with `hopr-strategy` at `d6ad33ff`), reading
Blokli through the proxy with the lag off.

**Repository commit:** `4dc838e` (clean working tree; recorded in `measurement.json`, which names the
packaged client version 1.1.0 although the binaries were the build named in `client_build`)

**Result:** All 3 deposits were recorded at the first look and confirmed by the exit. The fix adds no wait
when Blokli already knows the notes.

Part of the series described in [2026-11-22-blokli-race](../2026-11-22-blokli-race/README.md), which has the method and the per-run table.
