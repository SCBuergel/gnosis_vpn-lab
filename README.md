# vpn-lab

A five-machine lab for Gnosis VPN in the production HOPR network (`piz-palu-prod`): one client, three
relays and one exit, all ours. The client and the exit are configured so that their traffic can only
cross the three lab relays, which makes every hop observable.

Everything runs released software. The lab topology is configuration only; nothing is built from source.

| Machine | Software | Role |
| --- | --- | --- |
| `relay1`, `relay2`, `relay3` | hoprd 5.0.4 (GitHub release binary) | Relay and redeem tickets; open no channels of their own |
| `exit` | hoprd 5.0.4 from the published container image, gnosis_vpn-server 0.7.1 | VPN exit; not registered as an exit and publishes no address |
| `client` | gnosisvpn 1.1.0 package | VPN client with the exit pinned by address |

Background, source citations and the reasoning behind the design are in
[docs/research.md](docs/research.md). Results of runs are in [results/](results/README.md).

## How the traffic is confined to the lab relays

A HOPR path needs a funded payment channel from the sender to the first relay. Neither the client nor
the exit can name its relays, but both can restrict which nodes they open channels to:

- **Client** ([templates/client.toml](templates/client.toml)): `[strategy.channel_allowlist]` lists the
  three relays. Forward paths (client to relay to exit) can therefore only start at a lab relay.
- **Exit** ([templates/exit.cfg.yaml](templates/exit.cfg.yaml)): `ChannelLifecycle.eligibility.allowlist`
  lists the same three. The client plans the return paths too, and a return path (exit to relay to
  client) needs a funded channel from the exit to its first relay.
- **Relays** ([templates/relay.cfg.yaml](templates/relay.cfg.yaml)): no channel strategy, so they open
  no channels.

With 1 hop, which is the client's default, each packet crosses one of the three relays, chosen per
packet. `./lab verify` checks the result three ways (see [Verify](#verify)).

What this does not restrict:

- Other operators can open channels to the lab relays and relay their own traffic through them.
- The client still holds direct connections to every announced node of the network and sends each a
  few unpaid probe packets per minute. Only relayed traffic is confined
  ([first test](results/2026-11-21-first-test/README.md#what-else-the-client-talks-to)).

## Layout

| Path | Content | In git |
| --- | --- | --- |
| `lab.toml` | The whole deployment: provider, region, size, versions and hashes, funding amounts | yes |
| `vpnlab/` | The CLI. `providers/` holds the cloud-specific code | yes |
| `remote/` | Static install scripts that run on the machines | yes |
| `templates/` | Node configuration templates | yes |
| `results/` | Small summaries per run: numbers, tables, findings | yes |
| `docs/` | Research report, how to add a provider | yes |
| `raw/` | Raw logs and counters, possibly large | no |
| `state/` | Inventory, addresses, SSH config, transaction journal | no |
| `secrets/` | SSH key, node identities, passwords, API tokens, payment-state backups | no |
| `cache/` | Downloaded tools | no |

## Prerequisites

- Python 3.11 or newer, `ssh`, `ssh-keygen`, a systemd user instance (for the deletion timer).
- A DigitalOcean API token in the file named by `[providers.digitalocean] token_file`.
- For the funding steps only: a checkout of
  [gnosis_vpn-bench](https://github.com/SCBuergel/gnosis_vpn-bench) with its `.venv` (web3), and the
  funding key file it uses. The lab reuses the bench's wallet, which journals every transaction before
  broadcasting it and never sends one twice. `./lab` picks the bench's interpreter automatically.

## Set up the lab

Each step is safe to repeat. Steps that cost money or delete machines ask first; `--yes` skips the
question. Expect about 30 minutes and, at 2026-11-21 prices, about 216 wxHOPR and 0.08 xDAI.

```bash
./lab provision        # 1. five machines (DigitalOcean: 5 x c-4 = $0.63 per hour)
./lab timer set --hours 48   # 2. billing cap: delete them after 48 hours
./lab identities       # 3. node identities for relays and exit, created locally
./lab safes            # 4. one Safe and node module per hoprd node, owned by the funding account
./lab fund-nodes       # 5. wxHOPR to the Safes, xDAI to the nodes
./lab install relays   # 6. hoprd on the relays; they announce themselves on chain
./lab install exit     # 7. hoprd with exit payments, VPN server, WireGuard, NAT
./lab verify channels  #    repeat until it reports the exit as "ok" (about 2 minutes; the client is "not created" yet)
./lab install client   # 8. the client package with the lab configuration
./lab fund-client      # 9. starts the client, backs up its identity, then sends what it asks for
./lab client start     # 10. waits until the lab exit is routable (about 3 minutes on first start)
./lab verify channels  #     client and exit must each list exactly the three relays
```

Step 9 refuses to send anything unless the local copy of the client's identity matches the machine's,
the address the client asks to fund is the address of that backed-up key, and the amount is below
`client_max_wxhopr` in `lab.toml`. A key of an earlier client found in the backup folder is set aside,
never overwritten.
The identities of the other nodes are created locally in step 3, so every key is on this machine
before its node is funded.

## Run a test

```bash
./lab counters before --label my-test
./lab client connect                 # connects to the lab exit; prints the time it took
./lab measure my-test --count 3      # timed 100 MB downloads -> results/my-test/throughput.csv
./lab counters after --label my-test
./lab verify paths --label my-test      # fetches the client's log of today into raw/my-test/
./lab verify contacts --label my-test   # add --cached to analyse the copy already fetched
./lab client disconnect              # also stops the worker
```

To time a connection and the interruption that follows it, in one step:

```bash
./lab stall-test my-test --iterations 3            # the lab exit
./lab stall-test my-test-2 --destination <id>      # any exit the client lists (`./lab client status`)
```

It connects, starts a full-speed download the moment the client is connected, samples the download
every 0.1 s, and writes `results/<label>/` including the commit of this repository it ran at.
Commit your changes first, so that commit describes what was measured.

Every new connection pays the exit up front (5.94 wxHOPR at the packaged price). The exit collects a
payment only after about 400 MB of return traffic in that session, so short sessions leave their
payment uncollected.

The client's worker stops itself 30 minutes after the last `./lab client` command.

## Verify

| Command | Evidence | Passes when |
| --- | --- | --- |
| `./lab verify channels` | On-chain channels of client and exit, from the indexer | Each has open outgoing channels to the lab relays and to nobody else |
| `./lab verify paths` | The client's path-planner log. The planner logs every candidate path set at debug level, and draws each packet's path and each reply's return path from those sets | Every candidate path to or from the exit goes through a lab relay, in both directions |
| `./lab verify contacts` | The client's once-a-minute state dumps | Informational: how many peers it is connected to and how many other nodes it sent packets to |
| `./lab counters NAME` | Packet, ticket and payment-gate counters of relays and exit | Compare two snapshots: packets forwarded by the relays should match the exit's sent plus received |

## Access

```bash
ssh -F state/ssh_config lab-relay1        # also lab-relay2, lab-relay3, lab-exit, lab-client
ssh -F state/ssh_config lab-client-priv   # the client through relay1 over the private network
```

Use `lab-client-priv` while the VPN is connected: the client's killswitch cuts SSH from public
addresses but allows private ranges. The CLI always uses this path for the client.

On each hoprd node: API on `127.0.0.1:3001` with base path `/api/v4` and the token from
`/etc/hoprd/hoprd.env`; logs with `journalctl -u hoprd`. The exit's VPN server logs under
`journalctl -u gnosisvpn-server`. The client's worker log is
`/home/gvpnlab/.local/state/gnosisvpn/worker.log.<date>`.

## Tear down

```bash
./lab destroy          # backs up payment state, deletes every machine tagged vpn-lab, checks none is left
./lab timer status     # the timer runs the same command at its deadline
./lab timer cancel
```

`destroy` refuses while the keys of a created node are missing on this machine, because deleting such
a machine could strand its funds. Machines whose node was never created are deleted without that check. It does not move funds. To get them back, before or after deletion:

1. Close the outgoing channels of the exit and the client and wait the 300-second grace period.
2. Withdraw each Safe's wxHOPR to the funding Safe. The four hoprd Safes are owned by the funding
   account; the client's Safe is owned by the client's node key (`secrets/identities/client/`).

This recovery is not automated yet.

The timer is a systemd user timer on the machine that set it. It fires only while that machine and
the user's session are running; a missed deadline is caught up at the next start. A run that fails or
is refused is repeated every 30 minutes. A completed `destroy` disarms the timer.

## Use another cloud

The lab talks to the cloud through four methods (`create`, `list`, `delete`, `hourly_price`). See
[docs/adding-a-provider.md](docs/adding-a-provider.md).

## Development

```bash
ruff format . && ruff check . && python -m pytest
```

Tests are offline: they never touch a cloud, a machine, a wallet or the chain. The commands that
create machines or move funds were exercised by hand when the first lab was built
([first test](results/2026-11-21-first-test/README.md)); the read-only commands were run against that
live lab.
