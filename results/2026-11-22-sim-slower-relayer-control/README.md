# sim slower relayer control

**Measured:** one iteration with the unmodified client while the lab exit delayed every packet towards the payment relayer by 3 s. This reproduces what the laptop outside the lab showed.

**Repository commit:** `aba40f5` (clean working tree; recorded in `measurement.json`)

**Result:** The download stopped after 13.4 MB and never resumed (182 s until the test ended). The exit gave up after its 3-minute limit, and the client reconnected and committed to a second payment.

Part of the series described in [2026-11-22-fix-sidecar-and-hold](../2026-11-22-fix-sidecar-and-hold/README.md), which has the comparison, the method and what the patched
client changes. Numbers: `iterations.csv`, `bytes-per-second.csv`. Raw samples and counters are under
`raw/2026-11-22-sim-slower-relayer-control/` (not in git).
