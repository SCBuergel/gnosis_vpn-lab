# sim slow relayer control

**Measured:** one iteration with the unmodified client while the lab exit delayed every packet towards the payment relayer by 1.5 s.

**Repository commit:** `aba40f5` (clean working tree; recorded in `measurement.json`)

**Result:** The interruption doubled to 33.4 s but ended by itself: the payment request was already under way when the exit began to hold traffic.

Part of the series described in [2026-11-22-fix-sidecar-and-hold](../2026-11-22-fix-sidecar-and-hold/README.md), which has the comparison, the method and what the patched
client changes. Numbers: `iterations.csv`, `bytes-per-second.csv`. Raw samples and counters are under
`raw/2026-11-22-sim-slow-relayer-control/` (not in git).
