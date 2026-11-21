# 2026-11-21: first lab build and first test

The lab was built on DigitalOcean (5 × `c-4`, Frankfurt, Ubuntu 24.04) between 21:47 and 22:01 UTC,
with released software only: hoprd 5.0.4, gnosis_vpn-server 0.7.1, gnosisvpn 1.1.0. The steps were run
by hand; this repository's CLI was written from them afterwards. All times are UTC.

## Result in short

- The client and the exit used only the three lab relays, in both directions.
- The client still talks directly to the rest of the network: it stayed connected to about 228 nodes
  and probed about 60 of them every minute. That traffic is unpaid and not relayed.
- Steady throughput was 21 to 24 Mbit/s. The first download after connecting was much slower because
  the exit held traffic back while it waited for the client's payment.

## Nodes

| Node | Node address | Safe |
| --- | --- | --- |
| relay1 | `0xc8e2faf5b2d4afd01f5ca86666f04045199926cd` | `0x159c89cb77e97019417efe5367d72d6713501891` |
| relay2 | `0x826d7d57a992ede72e0da79176e4cf3731a7f0dc` | `0x57286fbb11c9147c728b8075ef380c9def664961` |
| relay3 | `0x6bc768ea0e3f0f42042718a70d0984842fe32a52` | `0xa0c76b228750612788ddf268d73c4453b93e33b0` |
| exit | `0xa532c96b39275210a3756c93f84338bd4661a55d` | `0x29fb1318a5e8dfcfbe1644e31db7832a655dc41a` |
| client | `0x7F2665228570F3300973B550754186080283d437` | `0xbec6044449F0E43b99E922F9007d2FB5Ad6E932a` |

The exit is not registered as `gvpn:exit` and runs with `announce: false`. The client found it through
its on-chain key binding and connected in about 10 seconds, both times.

## Only the lab relays carried the session

| Evidence | Result | File |
| --- | --- | --- |
| On-chain channels | Client: 3 open outgoing channels, to relay1, relay2, relay3. Exit: the same 3. No other channel in either direction. | `verify-channels.json` |
| Client path-planner log | 41 forward and 41 return candidate sets between 22:19:01 and 22:21:14; every set lists exactly the three relays. No foreign relay, no other path shape. | `verify-paths.json` |
| Packet counters, second session (100 MB download) | The relays forwarded 36,908 + 36,706 + 37,151 = 110,765 packets. The exit sent 80,697 and received 31,917, together 112,614; the 1.6 % difference is the exit's direct probe traffic. | raw counters |
| Rejected packets on the relays | None. | raw counters |

The planner draws each packet's forward path and each reply's return path from its candidate sets, so
a relay that never appears in them cannot have carried session traffic. The load was spread evenly:
each relay carried a third.

## What else the client talks to

The client is a full HOPR node, and its log shows that it does not limit itself to the three relays:

| Observation (client state dumps, once a minute, 22:00 to 22:21) | Value |
| --- | --- |
| Peers with an open direct connection | 220 to 228 in all 20 dumps (the indexer listed 228 announced nodes) |
| Other nodes it sent packets to, per minute | 63 to 64 |
| Packets to each of those, per minute | about 2 in steady state; up to 19 in the first two minutes after a start |
| Paths the planner built for anything but client-to-exit and exit-to-client | none |

What this means:

- These packets are direct probes to neighbours: no relay is involved and no ticket is paid. The
  client uses them to score peers. The planner built relayed paths only between client and exit.
- So the answer to "does the client only reach the three relays" is no for direct network contact,
  and yes for everything relayed and paid.
- The channel allowlist does not change this; it only decides whom the client pays. Nothing in the
  client's configuration limits which peers it connects to. A firewall on the client machine that
  allows only the relays' addresses would be configuration only, but it is untested and may degrade
  the client's view of the network.

Details per interval are in `verify-contacts.json`. The dumps list the 16 busiest destinations and
count the rest, so the packet totals cover the listed ones only.

## Throughput

All downloads ran on the client through the tunnel (`throughput.csv`; start times of rows 2 to 6 are
approximate to a few seconds).

| When | Download | Time | Rate |
| --- | --- | --- | --- |
| Session 1, 20 s after connecting | 30 MB | 52.3 s | 4.6 Mbit/s |
| Session 1, 12 minutes in | 3 × 100 MB | 35.1 to 36.7 s | 22.9 to 23.9 Mbit/s |
| Session 1, 14 minutes in | 2 × 100 MB | 39.4 to 39.5 s | 21.3 Mbit/s |
| Session 2, right after connecting | 100 MB | 76.1 s | 11.0 Mbit/s |

`speed.cloudflare.com` answered HTTP 403 to requests of 100 MB and more from the exit's address, so
the larger downloads used a Hetzner test file.

## First observations on the three issues

- **Stall after connecting: reproduced in both sessions.** The exit's counter
  `hopr_pix_gate_blocks_total{reason="predeposit_exhausted"}` recorded one block of 41.3 s in session 1
  and one of 15.8 s in session 2. In session 1 the exit logged "ssa deposit confirmed" 63 s after the
  session started. This explains the slow first downloads above.
- **Slow establishment: not seen.** Both connects took about 10 s with all machines in one region.
- **Cost per session: visible.** Each session paid 5.94 wxHOPR up front, and session 1 paid a second
  5.94 wxHOPR for the next chunk. The exit rebuilt the first payment's key after about 400 MB and
  swept 5.93 wxHOPR into its Safe. The two later payments (11.88 wxHOPR) were not collected before
  their sessions ended.

## Other findings

- Within 15 minutes each relay had 8 incoming channels: 2 from the lab and 6 from other operators.
  Nobody opened a channel to the unannounced exit.
- hoprd's YAML wants allowlist addresses as lists of 20 decimal bytes, not hex strings. The client's
  TOML takes hex strings.
- The config validator from the GitHub release rejects a configuration with exit payments; the exit
  needs the validator from the container image.

## Funds

Sent from the funding Safe: 216.36 wxHOPR and 0.076 xDAI.

| To | wxHOPR | xDAI |
| --- | --- | --- |
| Three relay Safes and nodes | 12 each | 0.01 each |
| Exit Safe and node | 60 | 0.01 |
| Client node address | 120.36 | 0.006 |
| Deployer key (gas for four Safe deployments) | — | 0.03 |

After the test: 50 wxHOPR spent on five key-binding fees, 90 wxHOPR locked in six channels (15 each),
about 2 wxHOPR in each relay Safe, 10.9 in the exit Safe, 30 in the client Safe, and the rest in the
client's payment pool or paid to the exit.

## Mistakes made during the build

- The client was funded before its identity backup had succeeded: the backup command failed and the
  transfer still ran. The backup was repeated and verified immediately afterwards. `./lab fund-client`
  now refuses to send unless the local copies match the machine's.
- The first five machines were deleted and recreated after a few minutes, because they forced a root
  password change that blocks scripted SSH. The provider's first-boot configuration now lifts it.
