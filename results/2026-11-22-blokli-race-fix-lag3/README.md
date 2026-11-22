# Fixed client, new notes reported 3 s late

**Measured:** two connects with the fixed build (main at `e6b33f36` with `hopr-strategy` at `d6ad33ff`) while the
proxy reported new Curvy notes 3 s late.

**Repository commit:** `4dc838e` (clean working tree; recorded in `measurement.json`, which names the
packaged client version 1.1.0 although the binaries were the build named in `client_build`)

**Result:** Both deposits were recorded by the client after 7 and 8 looks (`funded`, 1 of 1 chunks paid) and
confirmed by the exit. In run 2 Blokli itself did not know the note at the first look and knew it
0.54 s later.

Part of the series described in [2026-11-22-blokli-race](../2026-11-22-blokli-race/README.md), which has the method and the per-run table.
