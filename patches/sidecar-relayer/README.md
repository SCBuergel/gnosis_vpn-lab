# Patches: relayer side-car session and hold until paid

The client changes measured in `results/2026-11-22-fix-sidecar-and-hold/`, as `git format-patch` output.

| File | Applies to | Content |
| --- | --- | --- |
| `edge-client.patch` | `hoprnet/edge-client` at `7bafb47` (the commit client 1.1.0 uses) | A switch for where the payment pool's relayer traffic goes at run time |
| `gnosis_vpn-client.patch` | `gnosis/gnosis_vpn-client` at `v1.1.0` | Opens the side-car session when connecting, holds the tunnel until the first payment is confirmed, closes it on disconnect |

Build: check both repositories out side by side, apply each patch with `git am`, then in
`gnosis_vpn-client`: `cargo build --release -p gnosis_vpn-root -p gnosis_vpn-worker -p gnosis_vpn-ctl`.
The client patch points cargo at `../edge-client`. On Ubuntu 24.04 the build needs
`build-essential pkg-config libssl-dev libmnl-dev libnftnl-dev libsqlite3-dev clang cmake` and Rust 1.99;
it took 14 minutes on 8 dedicated vCPUs.

The exit must list `api.curvy.box:443` in `session_ip_forwarding.target_allow_list` (see
`templates/exit.cfg.yaml`).
