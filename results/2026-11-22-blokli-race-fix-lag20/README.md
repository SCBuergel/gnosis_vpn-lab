# Fixed client, new notes reported 20 s late

**Measured:** two connects with the fixed build while the proxy reported new Curvy notes 20 s late, longer than
the 9.5 s the fix keeps looking.

**Repository commit:** `4dc838e` (clean working tree; recorded in `measurement.json`, which names the
packaged client version 1.1.0 although the binaries were the build named in `client_build`)

**Result:** Both deposits were logged as `deferred` after 20 failed looks, 9.5 s after the first, and the
sessions stayed at `payment_pending`. The exit confirmed both. This is the limit of the fix: the
outcome is the same as with the unmodified client, 9.5 s later.

Part of the series described in [2026-11-22-blokli-race](../2026-11-22-blokli-race/README.md), which has the method and the per-run table.
