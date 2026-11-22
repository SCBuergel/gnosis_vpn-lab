# Patches: relayer side-car session and hold until paid

The client changes measured in `results/2026-11-22-main-patched/`, as `git format-patch` output. The
same commits are on the branches named below.

| File | Applies to | Branch | Content |
| --- | --- | --- | --- |
| `edge-client.patch` | `hoprnet/edge-client` at `b1537f5` (main) | `SCBuergel/edge-client@sidecar-relayer` | A switch for where the payment pool's relayer traffic goes at run time; opens the first connection when set |
| `gnosis_vpn-client.patch` | `gnosis/gnosis_vpn-client` at `e6b33f36` (main) | `SCBuergel/gnosis_vpn-client@sidecar-relayer-hold` | Three commits: build against the edge-client branch; open the side-car session when connecting; hold the tunnel until the first payment is confirmed |

The branch `SCBuergel/gnosis_vpn-client@sidecar-relayer` ends after the second commit (no hold).

Build: `cargo build --release --locked -p gnosis_vpn-root -p gnosis_vpn-worker -p gnosis_vpn-ctl` in
`gnosis_vpn-client`. On Ubuntu 24.04 the build needs
`build-essential pkg-config libssl-dev libmnl-dev libnftnl-dev libsqlite3-dev clang cmake protobuf-compiler`
and Rust 1.99; it took 15 minutes on 8 dedicated vCPUs.

The exit must list `api.curvy.box:443` in `session_ip_forwarding.target_allow_list` (see
`templates/exit.cfg.yaml`).

The first version of these patches, on `v1.1.0`, is in this repository's history at commit `584019c`.
