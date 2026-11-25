# Reproducing the exit SURB head-of-line stall across two clients

This reproduces [hoprnet#8753](https://github.com/hoprnet/hoprnet/issues/8753) and, beyond that
issue's single-client evidence, shows the stall reaching a **second, independent client**: one
client's starving session delays another client's traffic through the same exit.

## The mechanism, in one paragraph

On an exit, every packet the node originates (the return-path traffic of every client) passes through
one ordered routing-resolution stage. A return packet that finds no SURB is retried there for up to
`surb_resolution_wait` (1 s on hoprd) and, because the stage emits in submission order (`buffered`),
it withholds every packet queued behind it meanwhile — for *all* sessions, not just the starving one.
A Gnosis VPN bridge session with retransmission enabled and no SURB balancer is such a session: the
exit owes it more return packets (acks, resends) than it holds SURBs for.

## Setup

Two Gnosis VPN clients connected to the **same** exit at the same time:

| Role | Who | Build | Bridge | What it does |
| --- | --- | --- | --- | --- |
| **victim** | vpn-lab client (Frankfurt), node `0x7F26…` | client main, no fix | default (no retransmission) | pings through the tunnel; this is what we measure |
| **attacker** | vpn-lab2 client (New York), node `0xf8cB…` | `control-main-5d902a6` | **retransmission** (treatment) | downloads; its bridge session starves the exit of SURBs |
| **exit** | vpn-lab2 exit (New York), node `0xe18960…` | hoprd 5.0.4 (pre-fix) | — | shared by both clients; its journal is the ground truth |

Both clients pin the exit by address (it is unannounced) with a 1-hop path **through vpn-lab2's three
relays** — the exit is only reachable via the relays it keeps channels to, and that path is stable
(routing an unannounced exit over unrelated public relays is not). Each client therefore needs funded
channels to those three relays before the run; `gnosis_vpn-ctl` has no channel command, so the client
strategy opens them from its config's allowlist (`configs/`), which needs the client's Safe funded.

Each lab has only one client, so the second client is the other lab's client, repointed to this exit.
Nothing about the stall depends on where the clients sit — only that they are distinct nodes sharing
one exit.

## Why the victim *pings* instead of downloading

The victim probe is a light ping, **deliberately not a competing download**. Each echo reply forces
the exit to *originate* a return packet to the victim — the exact traffic the head-of-line stall
withholds — while a ping does not compete for the exit's bandwidth. A second bulk download does **not**
work as a probe here: on this 4-vCPU exit two concurrent downloads collapse each other (bandwidth and
PIX-deposit limits) *regardless of retransmission*, which masks the effect. Ping sidesteps that: in
the contention control the victim's ping stays clean even while the attacker downloads at full rate.

## The three arms

Each arm pings the victim for `DUR` seconds (90 by default). Only the attacker differs:

1. **baseline** — attacker disconnected. The victim has the exit to itself.
2. **contention** — attacker connected and downloading, bridge **without** retransmission. Same load
   on the exit, nothing starves (0 SURB drops). This is the control.
3. **treatment** — attacker connected and downloading, bridge **with** retransmission. Its bridge
   session starves; the exit logs `no SURB for its return path`.

The difference between contention and treatment isolates the head-of-line stall from the ordinary
cost of a second client's load.

## Run it

```bash
# one arm
./run-arm.sh <baseline|contention|treatment> <label> [duration_s]

# all three arms back to back, then print the summary
DUR=90 ./run-all.sh

# re-analyse collected arms
./analyze.py ../../results/2026-11-25-surb-head-of-line/ping-*
```

Roles are set by environment variables at the top of `run-arm.sh`. The harness, per arm: sets the
attacker's config, waits for a **working tunnel** (connected *and* the interface up — after a config
swap the client can report connected for minutes with no interface, so it restarts the worker to
unstick it), starts a persistent attacker download as a `systemd-run` transient unit (`atk-dl`; an
in-tunnel-DNS-independent `curl --resolve`), verifies the exit-side condition (drops for treatment,
none for contention), then pings the victim and collects the exit journal.

## Files

| File | What |
| --- | --- |
| `configs/victim.toml` | victim client config (pins the exit, 1 hop, no retransmission) |
| `configs/attacker-retx.toml` | attacker config **with** bridge retransmission (treatment) |
| `configs/attacker-noretx.toml` | attacker config **without** it (contention control) |
| `run-arm.sh` | one arm: set up the attacker, ping the victim, collect the exit journal |
| `run-all.sh` | the three arms, then `analyze.py` |
| `analyze.py` | victim RTT distribution, >500 ms count, exit drops, and spike↔drop correlation |

Results and the write-up are under `results/2026-11-25-surb-head-of-line/`.
