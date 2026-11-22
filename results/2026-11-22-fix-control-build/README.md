# fix control build

**Measured:** two iterations of the connect-and-download test with client 1.1.0 built from unmodified source (the control for the patched build), against the lab exit.

**Repository commit:** `aba40f5` (clean working tree; recorded in `measurement.json`)

**Result:** The control build behaves like the packaged client: connected in 5.1 s, interruption of 14.8 and 16.8 s after 13.3 MB.

Part of the series described in [2026-11-22-fix-sidecar-and-hold](../2026-11-22-fix-sidecar-and-hold/README.md), which has the comparison, the method and what the patched
client changes. Numbers: `iterations.csv`, `bytes-per-second.csv`. Raw samples and counters are under
`raw/2026-11-22-fix-control-build/` (not in git).
