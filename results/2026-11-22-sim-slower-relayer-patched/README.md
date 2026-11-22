# sim slower relayer patched

**Measured:** one iteration with the patched client under the same 3 s relayer delay.

**Repository commit:** `aba40f5` (clean working tree; recorded in `measurement.json`)

**Result:** The download completed with no interruption by the exit (hold counter 0.0 s). Connecting took 92 s: the payment needed 65 s through the slow relayer, plus the 22 s wait for the exit to see it.

Part of the series described in [2026-11-22-fix-sidecar-and-hold](../2026-11-22-fix-sidecar-and-hold/README.md), which has the comparison, the method and what the patched
client changes. Numbers: `iterations.csv`, `bytes-per-second.csv`. Raw samples and counters are under
`raw/2026-11-22-sim-slower-relayer-patched/` (not in git).
