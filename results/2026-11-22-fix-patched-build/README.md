# fix patched build

**Measured:** two iterations of the connect-and-download test with the patched client (relayer side-car session, tunnel held until the first payment is confirmed), against the lab exit.

**Repository commit:** `aba40f5` (clean working tree; recorded in `measurement.json`)

**Result:** No interruption by the exit in either run (its hold counter stayed at 0.0 s). Connecting took 42 s in run 1. In run 2 it took 155 s, because the client's own bookkeeping did not register a payment that had in fact arrived after 34 s.

Part of the series described in [2026-11-22-fix-sidecar-and-hold](../2026-11-22-fix-sidecar-and-hold/README.md), which has the comparison, the method and what the patched
client changes. Numbers: `iterations.csv`, `bytes-per-second.csv`. Raw samples and counters are under
`raw/2026-11-22-fix-patched-build/` (not in git).
