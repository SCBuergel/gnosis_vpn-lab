# main control

**Measured:** one iteration of the connect-and-download test with an unmodified build of
`gnosis_vpn-client` at `e6b33f36` (main, version 1.1.1) against the lab exit.

**Repository commit:** `91b833f` (clean working tree; recorded in `measurement.json`, which names the
packaged client version 1.1.0 although the binaries were this build)

**Result:** Connected in 5.0 s. The download paused for 18.7 s after 13.3 MB, held back by the exit, and
then completed in 79 s. The same behaviour as the packaged 1.1.0.

Part of the series described in [2026-11-22-main-patched](../2026-11-22-main-patched/README.md).
