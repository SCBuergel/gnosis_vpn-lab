# main patched, payment relayer delayed

**Measured:** one iteration of the connect-and-download test with the patched build of
`gnosis_vpn-client` (main at `e6b33f36` plus the branch `sidecar-relayer-hold`) against the lab exit,
while the exit delayed its packets to the payment relayer by 3 s.

**Repository commit:** `91b833f` (clean working tree; recorded in `measurement.json`, which names the
packaged client version 1.1.0 although the binaries were this build)

**Result:** Connected in 67.1 s, of which the payment through the delayed relayer took 37 s. The
download completed in 82 s and the exit held nothing back (0.0 s). The first version of the patch
needed 92 s under the same delay.

Part of the series described in [2026-11-22-main-patched](../2026-11-22-main-patched/README.md).
