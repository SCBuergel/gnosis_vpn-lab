# hoprnet PR #8763 on a real exit: before and after

[PR #8763](https://github.com/hoprnet/hoprnet/pull/8763) fixes
[#8753](https://github.com/hoprnet/hoprnet/issues/8753): on an exit, one session that runs out of SURBs
delays the traffic of every other session for up to 1 s per waiting packet. The PR was measured with
in-process nodes. This harness measures it on a lab exit in the production network, with two real
Gnosis VPN clients.

## Setup

One lab (`./lab`, see the repository README): three relays, one exit, and **two** clients. The lab CLI
knows one client; the second machine is created with the same tag and driven through
[`second-client`](../surb-head-of-line/second-client).

| Role | Machine | Software | What it does |
| --- | --- | --- | --- |
| victim | `client` | gnosisvpn 1.1.0 package, lab configuration | pings `1.1.1.1` every 0.3 s and fetches `https://1.1.1.1/cdn-cgi/trace` once a second, through the tunnel |
| attacker | `client2` | client main `5d902a6` (accepts the retransmission capability) | absent, or downloads a large file through the tunnel |
| exit | `exit` | one of three hoprd builds, see below | shared by both clients |

## The three exit builds

| Name | What |
| --- | --- |
| `stock` | hoprd 5.0.6 from the published image, as the lab installs it |
| `src` | hoprd 5.0.6 built from source: tag `v5.0.6` of hoprnet/hoprd with its pinned hoprnet revision `fa69827` |
| `pr8763` | the same build with the PR's change to `transport/hopr/src/` applied to that hoprnet revision |

`src` and `pr8763` come from one build tree and differ only by the patch.
`transport/hopr/src/path/resolve.rs` at `fa69827` is byte-identical to the PR's base, so the patch
applies unchanged. [`build-hoprd.sh`](build-hoprd.sh) is the build as it ran (Ubuntu 24.04, 16 vCPU,
about 25 minutes, `cargo build --release -p hoprd -F strategy-pix-curvy`).

## The three arms

Each arm measures the victim for `DUR` seconds (180). Only the attacker differs:

| Arm | Attacker |
| --- | --- |
| `quiet` | disconnected |
| `control` | downloading, bridge session at client defaults |
| `starved` | downloading, bridge capabilities `segmentation, retransmission, retransmission_ack_only, no_rate_control`: its bridge session runs out of SURBs on the exit |

An arm with an attacker starts measuring only once the download has passed 40 MB and is still moving.
A new session is held back at about 13 MB until its first payment is visible, and an arm measured
during that hold would have an idle attacker.

## Run it

```bash
./set-exit-build.sh pr8763                      # put a build on the exit and restart it
./run-arm.sh starved ../../results/x/pr8763-starved 180
./run-all.sh ../../results/x src pr8763 pr8763-2 src-2    # every arm on each build, in this order
./collect-session-events.sh ../../results/x/*/  # sessions opened and closed on the exit, per arm
./analyze.py ../../results/x/*/                 # Markdown table
```

A build name may carry a suffix (`src-2`): the part before the first `-` names the build, the whole
name labels the round.

## Files

| File | What |
| --- | --- |
| `configs/attacker-default.toml`, `configs/attacker-retx.toml` | the attacker's configuration for `control` and `starved`; they differ by the `[connection.bridge]` section |
| `build-hoprd.sh` | builds `src` and `pr8763` |
| `set-exit-build.sh` | installs one build on the exit |
| `run-arm.sh`, `run-all.sh` | one arm; all arms on a list of builds |
| `collect-session-events.sh` | the exit's session log lines per arm |
| `analyze.py` | the summary table |
