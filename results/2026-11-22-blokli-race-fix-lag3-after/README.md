# Fixed client, new notes reported 3 s late, after the 20 s runs

**Measured:** two more connects with the fixed build and a 3 s lag, right after the two runs with a 20 s lag that
left two deposits deferred.

**Repository commit:** `4dc838e` (clean working tree; recorded in `measurement.json`, which names the
packaged client version 1.1.0 although the binaries were the build named in `client_build`)

**Result:** Both deposits were recorded after 7 looks each and confirmed by the exit. The pool reconciled the
deferred deposit of the run before at the start of run 1.

Part of the series described in [2026-11-22-blokli-race](../2026-11-22-blokli-race/README.md), which has the method and the per-run table.
