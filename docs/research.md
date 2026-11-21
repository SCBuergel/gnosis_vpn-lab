# vpn-lab: research report

> This is the research that preceded the lab, kept as written. It has two addenda: A (cost,
> off-the-shelf start, unannounced exit), B (the lab as first built and tested). Paths such as
> `~/vpn-lab/RESEARCH.md` in the text refer to this file before it moved to `docs/`.

Date: 2026-11-21. Research only: nothing was built, deployed, rented or funded.
The only outside contacts were `git clone` of public repositories, read-only
GraphQL queries to the public production indexer, one `eth_blockNumber` call to
a public Gnosis RPC, and read-only commands on the NUC.

## How to read this report

Every claim carries one of three marks:

| Mark | Meaning |
| --- | --- |
| **[V]** | Verified by me directly: I read the code or config, ran the live query, or saw it on the NUC. |
| **[R]** | Read in the source by one of six delegated readers, with file and line. I spot-checked the claims the design depends on (they are marked [V]) but not every [R] line. |
| **[I]** | Inferred. Not stated by code or docs; needs a measurement in the lab. |

Citations are `repo/path:line`. Repositories were cloned to
`/tmp/claude-1000/-home-user-vpn-lab/a4f99e48-cf03-4e11-b8be-a0fb6b500d59/scratchpad/src`
(temporary; step 1 of the plan makes durable checkouts). Line numbers refer to
the commits in section 1.2.

## Summary

1. **The lab is feasible in the production network without patching anything
   for the default 1-hop case.** Neither client nor exit has a "use these
   relays" option. But a path needs a funded channel from the sender to the
   first relay, and both the client and hoprd have an allowlist for which
   peers they open channels to. A fresh client and a fresh exit that only ever
   open channels to our 3 relays can only route through them (section 3).
2. **"3 exits" should be read as "3 relays".** A session ends at exactly one
   exit; there is no multi-exit routing in the client (section 3.7).
3. **With 1 hop, each packet crosses one of the 3 relays, not all 3.** The
   client draws a relay per packet, in each direction. A chain through all 3
   needs the experimental multi-hop switch, and its order cannot be fixed
   without a small patch (section 3.3).
4. **We cannot keep other users off our relays.** hoprd has no switch to
   refuse relaying. Our own traffic is confined to our relays; our relays are
   not confined to our traffic (section 3.6).
5. **The code already contains a concrete mechanism for each of the three
   issues**, with timers, log lines and metrics to watch (section 4.1). The
   exit serves 10 000 packets (about 14.5 MB) before the client's payment is
   confirmed and then parks all return traffic until it is.
6. **The stock builds hide part of what we need.** Per-session metrics are
   stripped from hoprd's `/metrics`, the chain-lag metrics are not compiled
   into hoprd 5.0.4, packet capture is a non-default build feature, and the
   client has no metrics endpoint at all. The lab needs instrumented builds
   from the start, not only later for fixes (section 4).
7. **Money mostly circulates between our own nodes.** The client pays our
   relays (tickets) and our exit (PIX). Unavoidable loss is about 50 wxHOPR of
   one-time key-binding fees (5 nodes × 10 wxHOPR), plus gas and pool fees.
   Working capital is about 210 to 360 wxHOPR and about 0.1 xDAI (section 5).
8. **The public indexer runs 4 blocks (20 s) behind the chain head** [V],
   by design (3 blocks finality). Every node learns of every payment and
   channel event at least that late.

---

## 1. Repositories

### 1.1 What is needed

The node software was split into many repositories for v5. `hoprnet/hoprnet`
no longer contains the node daemon.

| Repository | Purpose | Needed for |
| --- | --- | --- |
| `gnosis/gnosis_vpn-client` | The VPN client: `gnosis_vpn-root` (privileged service), `gnosis_vpn-worker` (runs the HOPR node in-process), `gnosis_vpn-ctl` (CLI). | Client |
| `hoprnet/edge-client` | Crate `edgli`: wraps hopr-lib for embedding; sets the client's strategy and path-planner presets, exit discovery. | Client |
| `hoprnet/hoprnet` | hopr-lib and the protocol crates: packet format, sessions, PIX supervision (`transport/session`), path planner (`transport/hopr`). | Client, relays, exit |
| `hoprnet/hoprd` | The node daemon with REST API. A relay is a plain hoprd; the exit is a hoprd built with PIX. | Relays, exit |
| `hoprnet/hopr-strategy` | Channel lifecycle, auto-redeem and the PIX strategy with the Curvy pool code (deposits, withdrawals). | Client, relays, exit |
| `hoprnet/hopr-impls` | Chain connector (talks to Blokli), network graph, probing, ticket manager, session-server forwarder (the exit's target allow-list). | Client, relays, exit |
| `hoprnet/hopr-api`, `hopr-types`, `hopr-utilities` | Shared traits and types; path validation and the channel-funding rule live in `hopr-api/src/graph`. | All (dependencies) |
| `gnosis/gnosis_vpn-server` | Exit-side HTTP server that registers WireGuard peers. No HOPR code. | Exit |
| `hoprnet/hopli` | CLI: identity creation, Safe and module deployment, service registry. | Onboarding all 4 hoprd nodes |
| `hoprnet/blokli` | The chain indexer every v5 node depends on (GraphQL). Nodes have no RPC setting; they read chain state and submit transactions through it. | Optional own instance |
| `gnosis/gnosis_vpn` | Installer and packages (`.deb`), per-network config presets. | Client install |
| `gnosis/gnosis_vpn-exit_os` (local) | The exit appliance image. Source of the exit's config, units and firewall. | Exit (as reference or as the exit) |
| `hoprnet/hopr-docs` | Official docs, versioned to 5.0.4. | Reference |
| `hoprnet/rfc` | RFC-0012 (PIX) on branch `pix`. | Reference |
| `gnosis/gnosis_vpn-app` | GUI. Not needed. | — |

Not public or not found: `gnosis_vpn-testenv`, `gnosis_vpn-infrastructure`
(referenced, not cloned) [R]. The Curvy pool (`curvy-*` crates, relayer
`api.curvy.box`) is third-party and only available as published crates.

### 1.2 Latest versions (as of 2026-11-21) [V]

| Component | Latest tag | `main`/`master` head | Pins |
| --- | --- | --- | --- |
| gnosis_vpn-client | `v1.1.0` (2026-11-19) | `d88588b`, 7 commits ahead | edgli 5.3.0 `7bafb47`; hopr-lib 5.0.0-rc.6 at hoprnet `2acc3a58`; hopr-strategy 9.2.0 (main: git `97bfc19`); blokli-client 0.37.1 |
| hoprd | `v5.0.4` | `d0629e2` (version 5.0.5) | hoprnet `2a67ecc9` at the tag [R], `efb3d4cc` on main [V]; hopr-strategy 9.2.0; hopr-chain-connector 0.33 at the tag [R] |
| hoprnet | no v5 tag; v5 is `master` | `efb3d4cc` | — |
| hopr-strategy | `v9.2.0` | `97bfc19` | — |
| gnosis_vpn-server | `v0.7.1` | `2003df0` (0.7.2, no source change [R]) | — |
| hopli | `v0.20.1` | `901c240` | — |
| blokli | `v0.14.6` | `21478ec` | The hosted production instance reports `version: 0.24.0` [V]; I could not map that number to a tag. |
| gnosis_vpn (installer) | `v1.1.0` | `af534f8` | — |
| gnosis_vpn-exit_os | local checkout `00271e4` | — | Pins hoprd `5.0.3-pr.261`, server 0.7.0, hopli 0.20.1 |

Two things to know:

- **The NUC does not match the local exit_os checkout.** The NUC runs hoprd
  5.0.4 and its config has `price_per_byte` 9 000 000 000 wei and
  `max_deposit_wait: 3m`; the local checkout pins 5.0.3-pr.261 with
  1 000 000 000 wei [V]. The checkout is older than the deployed image. I did
  not fetch, because the repository was to be treated as read-only.
- **"Latest" is ambiguous.** `main` of the client already changes behaviour
  relevant to issue 1 (`d88588b`: fund the PIX pool at startup). Decision 1.

### 1.3 Dependencies and compatibility

```
gnosis_vpn-client ── edgli (git, branch main) ── hopr-lib (git, hoprnet master)
        │                    └── hopr-strategy, hopr-chain-connector (crates.io)
        └── hopr-utils-session (git, hoprnet master)

hoprd ── hopr-lib (git rev) ── transport/session, protocols/pix, ...
   └── hopr-strategy, hopr-chain-connector, hopr-network-graph,
       hopr-session-server-forwarder, curvy-* (crates.io)

exit = hoprd (PIX build) + gnosis_vpn-server + WireGuard + firewall/NAT
```

- **Wire compatibility.** The libp2p protocol id is `/hopr/mix/1.1.0` in both
  hoprd and edgli, the session start protocol is version 4, and
  `hopr-protocol-pix` is 0.3.1 on both sides at all three pinned commits [R].
  No release-name or app-version check between nodes was found [R]. The
  network identity comes from the indexer (`chainInfo.network` =
  `piz-palu-prod` [V]).
- **PIX must match on both ends** [R]:
  - Same pool at build time: client default `pix-curvy`, exit
    `strategy-pix-curvy`. A `pix-test` build on either side refuses every
    paid session.
  - Same geometry: 4096 / 32 / 79 in the client preset
    (`gnosis_vpn/linux/resources/config-piz-palu-prod.toml`) and on the NUC
    [V].
- **Client and server.** The server checks nothing; the client requires "v1"
  in the server's `/versions` (`gnosis_vpn-lib/src/route_health.rs:201-228`)
  [R].
- **Client ↔ ctl.** IPC protocol 3 in v1.1.0, 5 on main; mixing them fails
  with `protocol_mismatch` [R]. Root, worker and ctl must come from one build.
- **The production network is called piz-palu-prod** [V]. The older `jura`
  network is the frozen hoprd v4 line (`gnosis_vpn-client/docs/branch-strategy.md`)
  [V] and is out of scope.

---

## 2. Builds

### 2.1 Cheat-sheet [R]

All repositories build with Nix flakes; a plain `cargo build` is the
documented developer path. This machine has cargo and docker but no nix [V].

| Component | Toolchain | Nix output | Cargo |
| --- | --- | --- | --- |
| hoprd, relay | Rust 1.99 (MSRV 1.98) | `.#binary-hoprd-x86_64-linux` | `cargo build --release -p hoprd --bin hoprd` |
| hoprd, exit (PIX) | same | `.#binary-hoprd-pix-curvy-x86_64-linux`; zk files `.#curvy-zk-artifacts` | `cargo build --locked --release -p hoprd --bin hoprd --features strategy-pix-curvy` |
| hoprd, instrumented | same | `.#binary-hoprd-dev-x86_64-linux` (dev profile + curvy + `capture`) | add `--features capture` |
| hoprd, fast iteration | same | `.#hoprd-candidate` (no LTO, opt 2, no PIX) | `--profile candidate` |
| Client | Rust 1.99 (MSRV 1.94) | `.#binary-gnosis_vpn-x86_64-linux` (musl static) or `just build` | `cargo build`; needs libmnl, libnftnl, sqlite, openssl dev packages |
| gnosis_vpn-server | Rust 1.99 | `.#binary-gnosis_vpn-server-x86_64-linux` | `cargo build --release` [I] |
| hopli | Rust 1.96 | `.#binary-hopli-x86_64-linux` | `cargo build --release` |
| blokli | Rust 1.99 | `.#binary-bloklid-x86_64-linux` | `just build-release` |

hoprd feature notes (`hoprd/hoprd/Cargo.toml:15-103`) [R]:

- Defaults: `runtime-tokio, telemetry, transport-quic, allocator-jemalloc, session-server, state-dump`.
- Exactly one of `strategy-pix-curvy` / `strategy-pix-test`, or neither.
- `.cargo/config.toml` sets `--cfg tokio_unstable` and a 16 MB minimum stack;
  setting `CARGO_BUILD_RUSTFLAGS` yourself replaces that.

### 2.2 Cost [I]

No build durations are recorded in the repositories. From CI runner sizes
(4 to 8 CPU, 16 GB, client timeout 240 min) and the release profile (fat LTO,
one codegen unit) the readers estimate, for a cold build on 8 vCPU / 16 GB:

| Build | Time | Peak RAM |
| --- | --- | --- |
| hoprd release | 25 to 45 min | 6 to 10 GB at link |
| hoprd `candidate` | 10 to 15 min, minutes when incremental | less |
| Client release | 30 to 60 min | similar |
| Server | under 5 min | small |

Disk: 15 to 25 GB of `target` per repository and profile, plus about 10 GB of
Nix store. These are estimates; the first build in the lab should be timed.

### 2.3 Prebuilt artifacts [R]

- **GitHub releases:** `<binary>-x86_64-linux` with `.asc` and `.sha256`.
  **The released hoprd binary has no PIX** (`hoprd/hoprd/Cargo.toml:14`:
  "No `strategy-pix-*` pairing here, deliberately"). It is fine for relays,
  not for the exit.
- **OCI images** at `europe-west3-docker.pkg.dev/hoprassociation/docker-images/`:
  `hoprd` (PIX-enabled, carries the Curvy zk files), `bloklid`, `hopli`,
  `gnosis_vpn-server`. Tags `<version>`, `<version>-pr.<N>`, `latest`,
  `stable`. Whether a `5.0.4` tag exists was not checked (no pull in this
  step).
- **Client `.deb`** from `download.gnosisvpn.io`, channels `stable` and
  `snapshot`: binaries in `/usr/bin/gnosis_vpn-{root,worker,ctl,...}`,
  `gnosisvpn.service`, one config preset per network, the zk files.
  Patched binaries can replace the three in `/usr/bin` [I].
- **Curvy zk files:** from the 0xCurvy rs-sdk release v0.2.0. The client ships
  two files (about 40 MB); the full hoprd set size is unknown.

### 2.4 Patching across repositories

The pieces we will most likely patch (session supervision, path planner, PIX
strategy) are not in the top-level repositories, so every patch crosses a
dependency boundary:

| To patch | Mechanism [I] |
| --- | --- |
| hoprnet crates in hoprd | Change `rev` in `hoprd/Cargo.toml` to a fork commit, or `[patch."https://github.com/hoprnet/hoprnet"]` with local paths. |
| hoprnet crates in the client | One `[patch]` table for that URL covers both edgli and the client. |
| hopr-strategy, hopr-impls crates | `[patch.crates-io] <crate> = { path = ... }`. The client already does this for hopr-strategy on main (`Cargo.toml:97-99`) [R]. |
| edgli | `[patch."https://github.com/hoprnet/edge-client.git"]`. |

Hazards [R]:

- **Do not run `cargo update` in the client.** edgli is pinned by
  `branch = "main"`, and edge-client main currently points hopr-lib at a
  feature branch. An update would silently move the client to different code.
  Build with `--locked` and change pins deliberately.
- Nix builds need `outputHashes` re-synced after a git dependency changes
  (`scripts/update-nix-git-hashes.sh` in the client). Plain cargo builds avoid
  this; for the lab cargo is the simpler route.
- For pre-testing patches without spending funds, hoprd has a local cluster
  (`hoprd/localcluster/`, with an anvil-backed Blokli and a PIX soak test).

---

## 3. Custom topology in the production network

### 3.1 How paths are chosen

- **The client decides both directions.** For every packet it resolves a
  forward path and bakes return paths into the reply blocks (SURBs) it sends
  along (`hoprnet/transport/hopr/src/path/planner.rs:1291-1364`) [R]. The exit
  replies by using a reply block; it does not choose a route
  (`planner.rs:1366-1377`) [R]. `gnosis_vpn-server` has no HOPR settings at
  all [R].
- **Config carries only a hop count.** In config version 7 a destination's
  path is `Hops(u8)` and nothing else
  (`gnosis_vpn-lib/src/config/v7.rs:679-681`) [V]. Older `intermediates = [...]`
  syntax is rejected in v6/v7 and was only ever counted, not honoured [R].
- **Default is 1 hop, both ways** (`connection/destination.rs:18-23`,
  `probe.rs:612-615`) [R]. 0 hops needs `--allow-insecure`; 2 or more needs
  `--allow-experimental`.
- **Candidates come from the node's channel graph** (on-chain channels from
  the indexer, plus probe measurements). The selector weights them by
  latency, capacity and probe score, keeps all of them unless
  `min_paths_anonymity_floor` caps the count, and draws one per packet with
  10 % random exploration (`path/selector.rs:766-913`, `planner.rs:126-165`)
  [R]. There is no relay allow-list in the planner config, and unknown keys
  are rejected [R].
- **Explicit paths exist but are not wired into the client.** hopr-lib has
  `connect_to_using_explicit_path` behind a deprecated `explicit-path`
  feature. hoprd's REST API enables it; edgli and the client do not [R].

### 3.2 The lever: channels

A path is only a candidate if its paying edges are funded:

| Edge (1-hop each way) | Channel needed? | Who funds it | Evidence |
| --- | --- | --- | --- |
| client → R | Yes, open and funded for at least one ticket | Client | `hopr-api/src/graph/function.rs:85-99` [V] |
| R → exit (last forward hop) | No. "the final hop: zero-value ticket, no channel needed" | — | same [V] |
| exit → R | Yes, open and funded | Exit | `function.rs:316` [V] |
| R → client (last return hop) | No, but R must be connected to the client | — | `function.rs:302-311` [V] |

So the set of relays our traffic can use is the set of relays the client and
the exit hold funded channels to. Both sides can restrict that set:

- **Client:** `[strategy.channel_allowlist]` with `enabled` and `peers`,
  present in v1.1.0 (`config/v7.rs:498-553`, `documented-config.toml:259-263`)
  [V]. It maps to the strategy's eligibility allowlist, a hard gate before any
  peer is ranked (`hopr-strategy/src/channel_lifecycle/pipeline.rs:1194-1201`)
  [V].
- **Exit and relays (hoprd):** `ChannelLifecycle.eligibility.allowlist` in
  `hoprd.cfg.yaml`. The NUC's config has `allowlist: ~` (none) [V].

Proposed client config (keys verified; behaviour to be confirmed in the lab):

```toml
version = 7

[destinations.lab]
address = "<EXIT_NODE_ADDRESS>"
path = { hops = 1 }

[strategy]
min_open_channels = 3
target_open_channels = 3

[strategy.channel_allowlist]
enabled = true
peers = ["<R1>", "<R2>", "<R3>"]
```

Proposed exit strategy fragment (field names verified at
`hopr-strategy/src/channel_lifecycle/config.rs:96`; the YAML address format is
[I]):

```yaml
strategy:
  strategies:
    - ChannelLifecycle:
        population: { min_open_channels: 3, target_open_channels: 3 }
        eligibility: { allowlist: ["<R1>", "<R2>", "<R3>"] }
    - AutoRedeeming: { ... }
    - Pix: { ... }        # as on the NUC
```

Conditions and caveats:

- **Use fresh identities and Safes for client and exit.** The allowlist gates
  opening only; no code closes existing channels to other peers [R]. The NUC
  already has channels to arbitrary relays, so it cannot serve as the lab exit
  without closing them first.
- **Without the exit allowlist the return path leaves our relays.** A stock
  hoprd opens 5 to 20 channels to whichever peers score best [R].
- **Relays need no outgoing channels for 1-hop.** They can run with
  `AutoRedeeming` only [R].
- **Sufficiency is inferred, not proven.** That these two allowlists confine
  100 % of session packets follows from the code read, but must be shown by
  measurement: per-relay forwarded-packet counts must add up to the client's
  and exit's packet counts (section 4.3). This is the first experiment the lab
  should run.

### 3.3 Multi-hop and hard pins

- **2 or 3 hops through our relays** additionally needs funded relay-to-relay
  channels (R1→R2, R2→R3, by relay allowlists) and `--allow-experimental` on
  the client [R]. The planner still picks the order per packet.
- **A fixed order needs a patch.** Two candidate points [R]:
  1. Smallest: filter candidates in `HoprGraphPathSelector::select_path`
     (`hoprnet/transport/hopr/src/path/selector.rs`, around line 866).
  2. Cleaner: enable the `explicit-path` feature of `hopr-utils-session` in
     the client and re-add an intermediates variant to the config
     (`gnosis_vpn-lib/src/hopr/api.rs:123-200`, `config/v7.rs:678`). This
     allows separate forward and return pins.
- Production uses 1 hop, so the three issues are best studied at 1 hop first.

### 3.4 How the exit is made known to the client

Two ways [R], both confirmed live [V]:

- **Pinned by address** in `[destinations.<id>]`. The client then uses the
  built-in session targets `172.30.0.1:8000` (server API) and
  `172.30.0.1:51820` (WireGuard). The NUC is used this way.
- **Discovered** from the on-chain service registry: nodes registered as
  `gvpn:exit` with JSON metadata (`edge-client/src/discovery.rs:25-150`).
  Registering burns **1000 wxHOPR**, an update 100; 8 exits are registered
  [V, live query].

For the lab: pin, do not register. It costs nothing and keeps the exit out of
other users' lists. The exit must still be announced on-chain (that happens
at node start), because the client needs its packet key [R].

### 3.5 On-chain requirements per hoprd node

Steps (`hopr-docs/versioned_docs/version-v5.0.4/node/node-binary.md:55-140`) [R]:

1. `hopli identity create` (keystore plus password).
2. `hopli safe-module create --network piz-palu-prod --provider-url <RPC>
   --admin-address <OWNER> ...`: one transaction deploys the Safe and the
   node module and includes the node. The signing key only pays gas.
3. Fund the node address with xDAI and the Safe with wxHOPR.
4. Start hoprd with the Safe and module addresses. It registers the Safe and
   announces itself (`hoprnet/hopr/hopr-lib/src/builder.rs:709-808`).

Facts that matter:

- **No network registry, no minimum stake, no waitlist.** The docs call the
  network open, the production contract set has no registry address, and
  hopli's registry flag is "accepted for backwards compatibility. Currently
  unused" [R]. `hoprnet/NETWORK_REGISTRY.md` is stale.
- **Key-binding fee: 10 wxHOPR per node, once, from the Safe** [V, live
  `keyBindingFee`]. The docs still say "at least 1 wxHOPR". With less in the
  Safe, hoprd waits 200 s and exits (`builder.rs:757-776`) [R].
- **One Safe per node or a shared Safe** are both possible
  (`hopli safe-module add-node`) [R]. Separate Safes keep per-node accounting
  clean, which the lab wants.
- **The client is different:** it deploys its own Safe from funds sent to its
  node address, owned solely by the node key [R].
- **Transactions go through the indexer.** hoprd v5 has only `blokli_url`; no
  RPC [R]. hopli is the one tool that needs an RPC URL.

Production contracts (chain id 100) [V, live `chainInfo.contractAddresses`]:

| Contract | Address |
| --- | --- |
| wxHOPR token | `0xd4fdec44db9d44b8f2b6d529620f9c0c7066a2c1` |
| channels | `0x75ce59332721e3ae3064cb9652bce35ffce3f8e6` |
| announcements | `0x70219cdf30a44c4c31f5c20f1b7d62ebcef83a32` |
| node_safe_registry | `0x11a69afb66d70b48244a90689f190abcdbf9218c` |
| node_stake_factory | `0xeb83b9b9381b7acdbf71be86c52049f89e5f59b4` |
| module_implementation | `0xcf0c509ba63f85e21188ddefdc65b4717ff1af46` |
| ticket_price_oracle | `0x97f1f28b2d2278e1ca7aecc3081db966b9ed1a77` |
| winning_probability_oracle | `0x1a82a09f7b6410da54106a720cf97ffb7b815908` |
| service_registry | `0xc9323cdf98c7fad2dfac182d37cbf3ef38c2540c` |
| curvy_vault | `0x6997910940349e82811ba89f0d74412d11c68988` |
| curvy_aggregator | `0x3f2b578c6844b8d65b67dba4107db61d51b9020c` |
| curvy_shield_router | `0x863a6500f89eee7e90f8ae4c59759c5946e5c032` |

### 3.6 What cannot be restricted

- **Other users relaying through our relays.** No hoprd option refuses
  relaying, and there is no peer allow or deny list [R]. Anyone who opens a
  funded channel to one of our relays can use it, and other nodes' strategies
  may pick our relays by score. `min_incoming_ticket_price` exists but would
  price out our own traffic too.
- **Other clients using our exit.** Sessions are pseudonymous; there is no
  per-client admission [R]. Available controls are the target allow-list,
  per-target PIX enforcement, a session limit and the server's slot count.
  An unregistered exit is only reachable by someone who knows its address.
- **Probing.** Other nodes ping our announced nodes and may send loopback
  probes through our relays. Our nodes probe all their peers too. Cover
  traffic is off by default [R].
- **Dependencies we do not control:** the hosted indexer, and the Curvy
  relayer and batch prover used for PIX payments (section 4.4).

Consequence: relay counters include third-party packets. Attribution of our
own traffic needs either quiet relays (new, low-scoring nodes will attract
little) or packet capture (section 4.2).

### 3.7 Reading of "3 exits under our control"

"3 relays" is the right reading. The client connects to one destination; it
has no way to chain or spread a connection over several exits. The only
exit-flavoured alternative is three separate exits used one at a time, which
contradicts the target lab (1 exit) and the word "route".

---

## 4. Observability

### 4.1 The three issues: mechanisms found in the code

These are leads to observe, not conclusions. No fix is proposed here.

**Issue 1: stall right after connecting under load.**

- The exit serves at most 10 000 return packets before the payment for the
  first chunk (SSA) is confirmed, then parks all return data
  (`hoprnet/transport/session/src/supervision/mod.rs:556`: "`max_predeposit_packets`
  | 10000") [V]. At 1452 bytes that is about 14.5 MB: 2.3 s at 50 Mbit/s,
  12 s at 10 Mbit/s, 58 s at 2 Mbit/s. Under load the allowance is gone
  before the payment can arrive.
- The payment path is long [R]:
  1. The client debounces 500 ms.
  2. If its pool float is below the floor, it first moves funds from the Safe
     into the pool (up to 5 min).
  3. It builds a zero-knowledge proof.
  4. It submits to the Curvy relayer and polls for inclusion every 2 s.
  5. Curvy's batch prover commits on its own schedule.
  6. The indexer adds 3 blocks of finality (15 s).
  7. The exit polls the indexer's note index every 250 ms.
- The exit waits `max_deposit_wait` for the payment, 60 s by default and
  3 min on the NUC [V], then closes the session.
- The client holds instead of reconnecting when it knows a payment is
  pending, and reports `awaiting_payment_since` from 8 s [R].
- Suspects that would lengthen the payment [R, I]: the relayer call going
  through the tunnel whose return direction is parked (suggested by unmerged
  client commit `a209848`); a stale relayer connection (unmerged edge-client
  `c579727`); the pool refill (v1.1.0 ships `fund_at_startup = false`, main
  changes it to true).
- The same gate applies again when a new chunk reaches the front unfunded,
  roughly every 630 MiB [R].

**Issue 2: slow establishment.** Fixed, stacked timers [R]:

| Stage | Timer |
| --- | --- |
| Fresh install: Safe deployment, then waiting for a routable path | Strategy ticks every 60 s and opens at most 2 channels per tick; each channel event arrives 15 to 25 s after mining [I] |
| Each session open | Waits 5 s × (hops forward + hops back + 2) = 20 s at 1 hop; 3 tries, 2 s apart: about 86 s worst case (`transport/hopr/src/constants.rs`) |
| Probe session to the server (TCP, unpaid) | 4 outer retries; `http_timeout` 60 s per request |
| WireGuard registration | 10 s timeout, 3 retries |
| Main session (UDP, paid) | 3 outer retries around the 86 s |
| Verification ping | 15 s timeout, 3 pings, 5 retries |

A connect therefore consists of two HOPR session openings plus two HTTP
exchanges plus a ping, each with its own retry ladder. Which stage dominates
in practice is not known from the code; the lab must time each phase.

**Issue 3: paid re-establishment loop on poor paths.**

- Every reconnect opens a new session with a new random pseudonym; a payment
  is bound to its session and "never outlives its session"
  (`gnosis_vpn-ipc/src/protocol.rs:944`) [R].
- One payment is `price_per_byte × 660 160 512 bytes`: **about 5.94 wxHOPR**
  at the production client price of 9 000 000 000 wei per byte [R]. It buys
  660 MB of return traffic.
- There is no refund: the code says the money "is stranded rather than
  refunded" (`supervision/mod.rs:1179-1181`) [R].
- The client orders the payment as soon as its commitment burst is handed to
  the transport, before the exit has confirmed receiving it [R]. If the burst
  does not arrive complete within 20 s, the exit closes the session and the
  payment is already on its way.
- `reconnect_in_place` has no delay and no counter
  (`gnosis_vpn-lib/src/core/mod.rs:2540`) [R]. Triggers: 3 failed tunnel
  pings, 20 s without inbound bytes, a reply slower than 3 s combined with an
  inbound stall. Several are latency-sensitive.
- The only spend limits are per payment and 10 000 wxHOPR per hour, kept in
  memory and reset on restart [R].
- Unmerged upstream work addresses exactly this: hoprnet branches
  `feat/8711-entry-pix-continuity` and `feat/8711-exit-takeover` let a
  reconnecting client resume its paid session [R]. Worth watching before
  writing our own fix.

### 4.2 What each component exposes

**hoprd (relays and exit)** [R unless marked]:

- REST API on `127.0.0.1:3001`, base path **`/api/v4`** (not v5), header
  `X-Auth-Token`. Useful: `/channels` (balances, ticket index),
  `/tickets/statistics`, `/network/price`, `/network/probability`,
  `/network/connected` (latency and score per peer), `/network/graph`,
  `/node/status`, `/account/balances`. The NUC confirms `/api/v4` [V].
- Not available over REST: a ticket list, incoming sessions on the exit,
  per-session statistics, per-peer packet counters.
- Prometheus at `/metrics` (same token). On the NUC I counted 73 metric
  families [V]. The ones that matter:

| Question | Metric |
| --- | --- |
| Did this relay carry packets? | `hopr_packets_count{type}` (forwarded / received / sent) |
| Were packets or tickets refused? | `hopr_packet_rejected_count{reason}`, `hopr_packet_ticket_validation_errors{type}`, `hopr_tickets_count{type}` |
| Is the exit parking traffic, and why? | `hopr_pix_gate_blocks_total{reason}` (`predeposit_exhausted`, `share_lag`), `hopr_pix_gate_block_seconds`, `hopr_pix_sessions_stalled{cause}` |
| How long did the payment take? | `hopr_pix_cycle_phase_seconds{phase}` (`awaiting_commitment`, `awaiting_deposit`, `recovering`), `hopr_strategy_pix_deposit_tracking_total{outcome}` |
| Why did a session end? | `hopr_pix_closures_total{reason}`, `hopr_pix_admission_rejections_total{reason}` |
| How much was paid and collected? | `hopr_pix_deposits_confirmed_uhopr_total`, `hopr_strategy_auto_redeem_redeem_count` |
| Reply-block supply | `hopr_surb_balancer_*`, `hopr_surb_store_*` |

- Logs: `RUST_LOG` filter syntax; `HOPRD_LOG_FORMAT=json` for JSON lines.
  The NUC already runs with `hopr_strategy::pix`, `hopr_protocol_pix`,
  `hopr_transport_session`, `hopr_session_server_forwarder` and
  `blokli_client` at debug [V]. Key exit lines: "retrieved first client SSA
  commitment and deposit address", "ssa deposit confirmed", "pix supervisor
  closed the session".
- State dumps: one INFO record per minute for chain, graph and transport
  (`HOPR_STATE_DUMP_INTERVAL`, 5 s minimum).
- OpenTelemetry: `HOPRD_OTLP_ENDPOINT`, signals traces/logs/metrics. Spans are
  per node; there is no trace across hops.

**Gaps in stock hoprd 5.0.4** [R]:

| Gap | Consequence | Remedy |
| --- | --- | --- |
| All `hopr_session_*` series are stripped from `/metrics` (`hoprd/rest-api/src/root.rs:5-20`); `hoprnet/OTLP.md` says otherwise | No per-session bytes, reply-block levels or gate state by scraping | Run an OTLP collector, or patch the filter |
| `hopr_chain_*` (indexed head, transaction outcome and duration) arrived in connector 0.34; 5.0.4 pins 0.33 and no hoprd feature enables them | No in-node view of indexing lag or transaction latency | Build from main with the connector's telemetry enabled, or measure lag from outside |
| No metric has a peer label | Cannot attribute relayed packets to a sender from metrics | Build with `capture` (pcapng with peer ids and tickets, file named by `HOPR_CAPTURE_PACKETS`) |
| No session-establishment duration metric | Establishment time must be timed from outside | Log timestamps, client status polling |

**Client** [R]:

- No HTTP or OTLP endpoint. Metrics of the embedded node are only reachable
  as text through `gnosis_vpn-ctl telemetry`.
- `gnosis_vpn-ctl -o json status`: phase and time in phase, tunnel ping,
  `stall.awaiting_payment_since`, and per connection the payment state
  (`phase`, `chunks_committed`, `chunks_paid`, `chunks_failed`, bytes).
  `nerd-stats`: ticket price, strategy counters, WireGuard counters,
  reply-block buffer. `balance`: Safe, node and pool float.
- Logs: root at `/var/log/gnosisvpn/gnosisvpn.log`, worker at
  `~/.local/state/gnosisvpn/worker.log.<date>`; `RUST_LOG` only, text only.
  Phase transitions are logged at DEBUG and there is no duration summary.
- Key lines: "inbound stalled while the exit awaits PIX payment - holding",
  "inbound counters stalled - reconnecting", "reconnecting in place",
  "connection failed - retrying in place".

**gnosis_vpn-server** [R; the NUC confirms the two outputs, V]:

- `GET /api/v1/status` (slots, load average), `GET /metrics` with a single
  gauge `gnosisvpn_registered_clients`. A successful registration is not
  logged at all.

**Indexer (Blokli)** [V, live]:

- GraphQL at `<url>/graphql`; subscriptions over server-sent events.
- `chainInfo` returns `blockNumber` (last indexed), `ticketPrice`,
  `minTicketWinningProbability`, `finality` (3), `expectedBlockTime` (5),
  `channelClosureGracePeriod` (300), `keyBindingFee`.
- Queries for `channels`, `accounts`, `safes`, balances,
  `ticketRedemptionStats`, `transaction`, and the Curvy note index
  (`curvyPendingNotes`, `curvyCommittedNotes`, `curvyNoteStatus`).
- **Measured now:** indexed block 49 399 384 against head 49 399 388, a
  constant 4 blocks in three samples.
- Its own `/metrics` and `/readyz` (with lag) exist in the code [R]; whether
  the hosted instance exposes them was not tested.

### 4.3 Proposed lab instrumentation

1. **Prometheus** scraping the 4 hoprd nodes, the server, and node_exporter on
   all 5 machines at a short interval (1 to 5 s; the interesting events last
   seconds).
2. **A client sidecar** that polls `ctl status`, `ctl balance` and
   `ctl telemetry` every second and exposes or stores the result. This gives
   phase timings and money per attempt.
3. **Central JSON logs** from all nodes with synchronized clocks (chrony), so
   one timeline shows client, relay and exit lines side by side.
4. **An OTLP collector** for the per-session series hoprd hides from
   `/metrics`.
5. **A chain probe**: indexed block against head every second; the client's
   and exit's channels, Safe balances and Curvy notes from the indexer. This
   turns "the exit does not know about the payment yet" into a measured
   interval between mined, indexed and seen by the exit.
6. **Capture builds** (`capture` feature) on all hoprd nodes when hop-by-hop
   proof is needed. Captures on relays contain other users' packet metadata
   (decision 9).
7. **Controlled impairment.** Because we own every hop, `tc netem` on our own
   relays or exit can add delay and loss on demand. That reproduces a "very
   distant exit" repeatably and cheaply, instead of depending on geography
   alone. [I: netem is my suggestion, not something found in the repos.]
8. **The topology proof** from section 3.2: the sum of `forwarded` over the 3
   relays must match the session packets counted at client and exit, and the
   exit's and client's on-chain channels must list only our relays.

The existing work on this machine covers part of it: `~/exit-logging` already
parses the exit's PIX log lines and samples the node, chain and channels;
`~/gnosis_vpn-bench` drives the client and measures throughput.

### 4.4 What stays invisible

- The Curvy relayer queue and batch prover schedule: third-party, outside all
  repositories. We can only time the request and observe the on-chain result.
- The hosted indexer's internals, unless we run our own. The docs support a
  private instance for production nodes (`hopr-docs/.../run-blokli-locally.md`:
  bloklid plus PostgreSQL, 2 GB RAM, a Gnosis RPC, sync from block
  48 530 952) [R]. Caveat: the PIX pool needs an indexer with Curvy indexing
  enabled (off by default), and has its own `blokli_url` separate from the
  node's.

---

## 5. Costs and prerequisites

### 5.1 Economic parameters [V, live 2026-11-21]

| Parameter | Value |
| --- | --- |
| Ticket price | 0.00000216 wxHOPR per packet per paid hop |
| Minimum winning probability | 8.64e-7 |
| Value of one winning ticket (1 hop) | 2.16e-6 / 8.64e-7 = 2.5 wxHOPR |
| Channel closure grace period | 300 s |
| Key-binding fee | 10 wxHOPR |
| Gas price | about 0.005 gwei; a 1M-gas transaction costs about 0.000005 xDAI |

Derived [I]:

- Relay cost per GB per direction per paid hop: 1e9 / 1452 × 2.16e-6 ≈
  **1.49 wxHOPR**, paid as one 2.5 wxHOPR win per about 1.16 million packets
  (1.68 GB). Payment is lumpy: a short test may pay nothing or 2.5.
- Exit payment (PIX): 5.94 wxHOPR per 660 MB chunk at the production client
  price, about **9 wxHOPR per GB**. The local exit_os template and the bench
  config for the NUC use 1e9 wei per byte instead (1 wxHOPR per GB). Whether
  the exit enforces its own price or accepts any non-zero payment was not
  settled [R: "any non-zero confirmation funds the cycle; sufficiency is the
  pool's verdict"].

### 5.2 Funding per node

Assumptions: prices above, 1-hop paths, separate Safe per hoprd node,
allowlists as in section 3.2. Amounts are the readers' derivations [I] from
the strategy code; the client's own recommendation is the authority at run
time (it asked for 225.36 wxHOPR and 0.005 xDAI on 2026-11-16, per the bench
profiles).

| Node | xDAI on node key | wxHOPR | Use | Lost or recoverable |
| --- | --- | --- | --- | --- |
| Client, stock config | 0.005 | 225.36 (to node address) | 10 fee; 35.35 pool float; 8 channels plus top-ups | Fee lost; the rest goes to our relays and exit or stays in channels |
| Client, 3 allow-listed channels | 0.005 | about 120 | 10 + 35.35 + 5 × 15 | same |
| Relay × 3 | 0.01 each | about 12 each | 10 fee plus margin | Fee lost |
| Exit, 3 allow-listed channels | 0.01 | about 55 | 10 fee; 3 channels of 7.5; top-ups | Fee lost; rest recoverable |
| Deployer key (hopli) | 0.02 to 0.05 | 0 | 4 Safe deployments | Gas |

- **Total working capital:** about 210 wxHOPR tuned, about 360 with stock
  settings, plus about 0.1 xDAI.
- **Unavoidable loss:** 50 wxHOPR key-binding fees, gas (well under
  0.01 xDAI), Curvy pool and relayer fees (level unknown).
- **Risk of loss:** payments stranded in sessions that die before the exit
  collects them (the subject of issue 3; about 5.94 wxHOPR each at the
  production price), and funds on any node whose keys are lost.
- Recovery takes the 300 s closure period per channel. The bench has this
  for clients; hoprd nodes with hopli-created Safes need an owner-signed
  withdrawal that the bench does not have.

### 5.3 Machines, ports, reachability

| Node | Size | Network |
| --- | --- | --- |
| Relay × 3 | Docs minimum: 4 cores, 4 GB RAM, 5 GB disk, 10 Mbit/s [R] | Public IPv4, inbound 9091 TCP and UDP. hoprd has no hole punching (libp2p autonat only) [R] |
| Exit | exit_os asks 8 vCPU / 16 GiB for a VM [V]; a plain hoprd plus server should need less [I] | Public IPv4 and inbound 9091 recommended. API 3001, server 8000 and WireGuard 51820 stay private: they are reached only through HOPR sessions |
| Client | The bench uses 4-vCPU droplets | Outbound only. **Connecting installs a killswitch that cuts SSH**; the `test-gnosis-vpn` skill's guards (ssh-keeper, deadman) are mandatory |
| Build host | 8 vCPU, 16 to 32 GB, 60+ GB disk [I] | This machine or a rented one (decision 5) |

Exit as a plain VM needs, from the appliance's own files [R]: PIX hoprd and
`hoprd-cfg`, the zk files with `CURVY_ZK_KEYS_DIR`, `gnosis_vpn-server`,
`172.30.0.1/32` on `lo`, WireGuard on 10.128.0.0/24, IP forwarding,
masquerade, an MSS clamp, and the session target allow-list in
`hoprd.cfg.yaml`. Both `blokli_url` entries (top level and the PIX pool's)
must be set; the second has no environment override.

### 5.4 Where code and docs disagree (code wins)

| Topic | Docs | Code or live state |
| --- | --- | --- |
| Safe funding to start | "at least 1 wxHOPR" (hopr-docs) | Key-binding fee is 10 wxHOPR [V] |
| Network registry | `hoprnet/NETWORK_REGISTRY.md` describes one | None exists in v5 [R] |
| REST base path for v5 | — | `/api/v4` [V] |
| Session metrics | `OTLP.md`: on `/metrics` by default | Always filtered out [R] |
| Default indexer URL | Docs: hosted piz-palu endpoint | Code default `http://localhost:8080`; must be set [R] |
| `chain.network`, `chain.provider` | hoprd compose README | Not in the v5 config [R] |
| PIX strategy, session forwarding | Not documented at all | Code only |
| Client PIX price default | — | Library default is 1 wxHOPR per byte, which would refuse every payment; the installer preset sets it [R] |
| Exit onboarding via support e-mail | exit_os `first-install.md` | Superseded by the on-chain registry [I] |
| Exit payment wait | Code default 60 s | The NUC runs 3 min [V]; production exits unknown |

### 5.5 Open questions and risks

Open questions (each is a measurement the lab should make):

1. Do the two allowlists confine all session packets to our relays? (3.2)
2. When exactly is the first payment ordered, and how long is each leg of its
   path to "confirmed" on the exit? (4.1)
3. Does the client's relayer traffic go through the tunnel?
4. What do production exits run for `max_deposit_wait` and the PIX price, and
   does an exit reject an under-priced payment?
5. Can an exit collect a partly used payment after the session closed, or is
   it lost to both sides?
6. Ratio of client-paid forward packets to exit-paid return packets for a
   download (reply blocks and acknowledgements).
7. Real build times and whether an OCI image tagged 5.0.4 exists.
8. Does a new relay with no history get selected at all by the client's
   planner soon enough (probe scores start empty)?

Risks:

- **Version skew.** Client v1.1.0, hoprd v5.0.4 and main all pin different
  hoprnet commits. They interoperate today, but a finding on one build may not
  hold on another. Fix one baseline and record it with every measurement.
- **Third-party traffic** on relays blurs counters (3.6).
- **External dependencies** (hosted indexer, Curvy) can dominate timings and
  cannot be instrumented.
- **Funds.** Five identities and five Safes; lost keys strand funds. Back up
  identities before funding, as the bench does.
- **Lock-out** of the client machine by the killswitch.
- **Moving target.** Upstream is actively changing the exact code paths under
  study (several unmerged fixes listed in 4.1).

---

## 6. Proposed plan

Each step ends with a check. Nothing here was started.

1. **Fix the baseline and get the sources.** Durable checkouts of the
   repositories in 1.1 at the chosen versions (decision 1), with forks or
   patch branches prepared for hoprnet, hopr-strategy and the client.
   Check: versions and commit hashes recorded in the lab's notes.
2. **Set up the build host and build everything unmodified.** hoprd (plain
   and PIX), client, server, hopli. Time the builds. Check: binaries report
   the expected versions; a PIX hoprd validates the exit config with
   `hoprd-cfg`.
3. **Dry run on a local cluster** (hoprd `localcluster`, no real funds): the
   topology with allowlists, 1 client, 3 relays, 1 exit. Check: all session
   packets cross only the 3 relays. This tests the central assumption of 3.2
   for free.
4. **Write the lab tooling** in `~/vpn-lab`: provisioning of 5 machines with a
   deletion timer, hoprd install and config, hopli onboarding, funding with a
   journal, recovery. Reuse the bench's wallet, journal, backup and droplet
   code. Check: a complete create and destroy cycle with no funds involved.
5. **Deploy the monitoring first** (4.3, items 1 to 5) on empty machines.
   Check: dashboards and logs show all 5 machines and the chain probe.
6. **Onboard the 3 relays** in production: identities, Safes, funding,
   announce. Check: all three appear in the indexer and connect to peers.
7. **Onboard the exit** with the allowlist and the pinned PIX config. Check:
   its only outgoing channels are to our 3 relays.
8. **Install and fund the client** with the allowlist and the pinned exit.
   Check: its only outgoing channels are to our 3 relays; it connects.
9. **Prove the topology** on production (4.3, item 8). Check: packet counts
   add up; otherwise stop and switch to the patch in 3.3.
10. **Baseline measurements** of the three issues, unmodified: phase timings
    of 20 or more connects; a loaded transfer right after connecting with the
    payment timeline; a degraded path (netem and/or a distant exit) with the
    money spent per cycle. Check: each issue reproduced and attributed to a
    stage, or shown not to reproduce in the lab.
11. **Instrumented builds** where the baseline left gaps (session metrics,
    chain metrics, capture). Repeat step 10.
12. **Report and review** before any fix work starts.

Rough running cost while the lab is up [I]: 5 machines plus a build host on
DigitalOcean at roughly 0.5 to 1 USD per hour in total, depending on sizes.
I did not look up current prices.

## 7. Decisions needed

1. **Version baseline.** Latest tags (client v1.1.0, hoprd v5.0.4, server
   v0.7.1), or `main` of each? I recommend the tags as baseline, because they
   are what users run, with `main` as a second configuration.
2. **Reading of "3 exits".** Confirm it means 3 relays, with 1 exit.
3. **Hop count.** 1 hop only (production default; each packet crosses one of
   the 3 relays), or also a chain through all 3 (experimental, needs the patch
   in 3.3 for a fixed order)? I recommend 1 hop first.
4. **Exit form.** A plain VM with hoprd and the server (my recommendation:
   fastest to patch and instrument), the exit_os image in a VM (closest to
   production exits), or the NUC (not suitable as is: existing channels to
   other relays, residential NAT)?
5. **Where to build.** This machine (needs nix or the dev packages installed)
   or a rented build host?
6. **Provider, regions and impairment.** DigitalOcean as with the bench?
   Which regions, and is a distant exit wanted, `tc netem` on our own nodes,
   or both?
7. **Funding.** Approve working capital of about 250 to 400 wxHOPR and
   0.2 xDAI from the funding Safe, of which about 50 wxHOPR is lost to
   key-binding fees. Who owns the node Safes: the funding account (my
   recommendation), with one Safe per node?
8. **PIX price in the lab.** Production client price (9e9 wei per byte, about
   5.94 wxHOPR per payment, realistic for issue 3) or the lower 1e9?
9. **Third-party data.** Relays will carry other users' packets. May we run
   packet capture on them, and with what retention? Without capture, only
   aggregate counters.
10. **Own indexer.** Run a private Blokli for the lab nodes to instrument
    indexing delay ourselves, or use the hosted one and measure from outside
    (my recommendation to start)?
11. **Lifetime.** A long-lived lab (monthly machine cost, funds parked) or
    created per experiment with deletion timers, as the bench does?
12. **Tooling home.** Extend `gnosis_vpn-bench` (public repository) with
    relay and exit support, or keep lab tooling in `~/vpn-lab` and import
    from the bench? Should `~/vpn-lab` become a git repository, private?
13. **Exit registration.** Confirm the exit stays unregistered and pinned
    (registration burns 1000 wxHOPR and invites other users).

---

# Addendum A (2026-11-21): 48-hour cost, off-the-shelf start, unannounced exit

Still research only. New outside contacts: read-only DigitalOcean API calls
(size list, droplet count) with the existing token, AWS public price files,
the public container registry tag lists, the GitHub releases API and the apt
package index. Marks as in the main report.

Confirmed by you: one exit, 1 hop, 3 different relays. Decisions 2 and 3 of
section 7 are closed.

## A.1 Machine choice

Five machines of 4 vCPU / 8 GB each, x86-64:

- hoprd's documented minimum is 4 cores and 4 GB [R]; the bench runs clients
  on 4-vCPU droplets [V].
- The exit is a plain hoprd plus `gnosis_vpn-server`, not the appliance, so
  the appliance's 8 vCPU / 16 GiB VM figure does not apply [I].
- No build host, because the start is off the shelf (A.3).
- Optional sixth machine (2 vCPU / 4 GB) for Prometheus and logs. Monitoring
  could also run on this machine instead.

Dedicated vCPUs are the like-for-like comparison and what I recommend for
timing measurements: HOPR packet processing is CPU-bound, and a noisy shared
host would blur exactly the stalls we want to measure. Shared vCPUs are shown
as the cheap option.

## A.2 Cost for 48 hours

Prices read on 2026-11-21 [V]: DigitalOcean from its API, AWS from its public
price files (publication date 2026-11-21).

| Option | Instance | Per hour | 5 machines, 48 h | Public IPv4 | Disk | **Total, 5 machines** | With monitoring box |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DigitalOcean, shared CPU | `s-4vcpu-8gb` | $0.07143 | $17.14 | included | 160 GB included | **$17.14** | $18.86 |
| DigitalOcean, dedicated CPU | `c-4` | $0.125 | $30.00 | included | 50 GB included | **$30.00** | $31.71 |
| AWS Mumbai, dedicated (AMD) | `c6a.xlarge` | $0.0935 | $22.44 | $1.20 | $0.90 (5 × 30 GB gp3) | **$24.54** | $27.20 |
| AWS Ohio / N. Virginia / Oregon | `c6a.xlarge` | $0.153 | $36.72 | $1.20 | $0.79 | **$38.71** | $42.78 |
| AWS Stockholm (cheapest EU, Intel) | `c7i-flex.xlarge` | $0.1815 | $43.56 | $1.20 | $0.82 | **$45.58** | — |

How the figures arise:

- **DigitalOcean prices are the same in every region.** Both sizes are
  marked available in 11 to 12 regions, including `fra1`, `ams3`, `lon1`,
  `nyc1`, `sgp1`, `syd1` [V]. IPv4, disk and a traffic allowance are included.
- **AWS prices differ by region.** Mumbai is far cheaper for AMD instances
  than any other region I checked (`c6a.xlarge` $0.0935 against $0.153 in the
  US and $0.164 to $0.20 elsewhere). `c6a` is not offered in Stockholm.
- **AWS adds per-item charges:** $0.005 per hour per public IPv4, gp3 disk at
  $0.08 per GB-month ($0.0912 in Mumbai), and traffic.
- **Traffic.** On AWS, internet egress costs $0.09 per GB ($0.1093 in Mumbai)
  after a free 100 GB per month, and traffic between instances over public
  addresses in one region costs about $0.01 per GB in each direction (this
  last figure is from memory, not from the price file). HOPR nodes talk to
  each other over public addresses. One GB of VPN payload crosses two node
  links per direction, so 100 GB of test traffic would add a few dollars. On
  DigitalOcean the allowance accrues hourly: about 350 GB per `c-4` in 48 h,
  pooled over the account [I from the 5 TB monthly figure].
- **Cheaper AWS variants I do not recommend for a first run:** Arm instances
  (`c6g.xlarge`, $0.0852 in Mumbai; Arm binaries and the Arm `.deb` exist,
  but I did not check the container image), burstable `t3a` (CPU credits
  distort measurements), and spot instances (can be reclaimed while holding
  funded node keys).

**Availability** is where the two differ most:

- DigitalOcean: sizes confirmed available through the API. The token cannot
  read the account's droplet limit (same as the bench reports). The account
  currently has 2 droplets [V]; I did not look at what they are.
- AWS: appearing in the price list is not capacity or permission. There is no
  AWS configuration or CLI on this machine [V], so I could not check an
  account, its vCPU quota (20 vCPUs are needed; new accounts often start
  below that) or instance capacity. AWS would also need new tooling: the
  bench's provisioning, tagging and deletion timer are DigitalOcean-only.

**Recommendation:** DigitalOcean `c-4` in `fra1` or `ams3`, **about $30 for
48 hours** ($32 with a monitoring box). AWS Mumbai is nominally $5 cheaper but
needs an account, quota and tooling we do not have, and it sits far from most
of the network and the indexer. If the budget matters more than clean
timings, `s-4vcpu-8gb` halves it to about $17.

The machines are the small part of the bill. The token side is unchanged
from section 5.2: about 210 to 360 wxHOPR of working capital, of which 50
wxHOPR is lost to key-binding fees.

## A.3 Starting with off-the-shelf software

**Viable: yes.** Every component exists as a published artifact, and the
whole lab topology is configuration, not code.

| Component | Published artifact | Verified today |
| --- | --- | --- |
| Client | `gnosisvpn` 1.1.0 `.deb` in the stable apt channel; also on the GitHub release | [V] apt index and release assets |
| Relay | `hoprd` v5.0.4: signed binary on GitHub (with `hoprd-cfg`), and container image tag `5.0.4` | [V] both exist |
| Exit, node | The `hoprd` container image `5.0.4`. This is the PIX build and carries the proving files; the GitHub binary has no PIX | [V] tag exists; PIX content [R] from the build definition, and the NUC runs 5.0.4 with PIX [V] |
| Exit, VPN server | `gnosis_vpn-server` v0.7.1 signed binary on GitHub. The container registry path has no tags | [V] |
| Onboarding | `hopli` v0.20.1 signed binary on GitHub | [V] |

What "off the shelf" still requires us to write:

- **Client config** (pinned exit, channel allowlist): a replacement
  `/etc/gnosisvpn/config.toml`. No flags are needed, since 1 hop is the
  default.
- **Relay config:** a `hoprd.cfg.yaml` with `AutoRedeeming` only. Left at
  defaults a relay opens 5 to 20 channels to strangers [R].
- **Exit config and host setup:** there is no installer for an exit on a
  cloud VM. The only packaged exit is the appliance image, which needs a
  TPM and an ISO installation [V, `docs/architecture.md`: "`identity`
  requires a TPM2"]; neither provider offers that simply [I]. So the exit is
  the stock image plus the appliance's own files adapted by hand:
  `hoprd.cfg.yaml` with the allowlist, the loopback alias `172.30.0.1`,
  the WireGuard interface, forwarding and NAT rules (section 5.3). This is
  configuration glue, not custom software, but it is the largest manual piece.

What the stock builds give us for observation:

- Available: hoprd `/metrics`, REST API, JSON logs at debug level, state
  dumps, and OpenTelemetry export (in the default build [R]), which is the
  way to get the per-session series that `/metrics` hides. On the client:
  `gnosis_vpn-ctl status`, `balance`, `telemetry`, and its logs.
- Not available without building: packet capture, the chain-lag metrics, and
  any new log line. For a baseline of the three issues the stock signals in
  section 4.2 should be enough to place each delay; they will not prove
  hop-by-hop attribution on a relay that also carries strangers' traffic.

**Skipping the local test environment is reasonable**, with one consequence:
the central assumption (the two allowlists confine all session traffic to our
relays) is tested for the first time with real funds. The exposure is small
and can be staged so each step is checked before more money moves:

1. Onboard the 3 relays, then the exit. Check on the indexer that the exit's
   only outgoing channels go to our relays. Sunk cost so far: 40 wxHOPR of
   key-binding fees.
2. Only then fund the client. Check its channels the same way.
3. Connect and compare packet counts across client, relays and exit.

If step 1 or 2 shows a channel to a foreign relay, stop there: the fallback
is the patch in section 3.3, which ends the off-the-shelf phase.

## A.4 Running the exit without announcing it

There are three separate things that could be called "announcing". Only one
of them makes an exit appear in other clients.

| Layer | What it is | Can we skip it? |
| --- | --- | --- |
| Key binding | An on-chain record linking the node's address to its packet key, plus its Safe. Costs 10 wxHOPR once. | **No.** |
| Address announcement | Publishing the node's IP and port on-chain so others can dial it. | **Yes** (`announce: false`). |
| Service registration | An entry of type `gvpn:exit` in the service registry. Burns 1000 wxHOPR. | **Yes, and this is the one that matters.** |

Evidence:

- **Key binding is mandatory on both ends.**
  - hoprd always sends the announcement transaction; with `announce: false`
    it sends it with an empty address list and still waits for its key
    binding (`hoprnet/hopr/hopr-lib/src/builder.rs:733-808`) [V].
  - The client refuses a destination without it: "destination has no packet
    key on chain - not routable"
    (`gnosis_vpn-client/gnosis_vpn-lib/src/hopr/api.rs:490-494`) [V]. It needs
    that key to encrypt packets for the exit.
  - So an exit with no on-chain footprint at all is not possible. The node
    will be one of the 488 accounts the indexer lists [V], as a node, not as
    an exit.
- **Other clients only list registered exits.** The client builds its
  destination list from its config file and from `gvpn:exit` service entries
  (`edge-client/src/discovery.rs:99-150`,
  `gnosis_vpn-lib/src/core/runner.rs:415`) [V]. Without the registry entry no
  other client shows the exit. Eight exits are registered today [V].
- **Our client can still use it** by address in `[destinations.<id>]`
  (section 3.4). Your NUC is the working example: unregistered, pinned in the
  bench's client config, and it has served bench runs [V, bench target file
  and results].
- **Not publishing an address should also work, but I have not seen it run.**
  - The path planner does not need a measured relay-to-exit link: it appends
    the destination to any funded first hop
    (`hoprnet/transport/hopr/src/path/selector.rs:663-737`) [V].
  - A node with `publish` off is exactly what every VPN client is (the
    default is off, `hopr-lib/src/config.rs:74` [V], and the client never
    turns it on), and clients receive their return traffic through relays.
  - The NUC publishes an address but drops all inbound connections, and the
    appliance starts hoprd unannounced when address discovery fails [V,
    `docs/architecture.md`].
  - What remains [I]: that an unannounced hoprd dials our relays early enough
    for them to deliver to it. One check in the lab settles it: the relays
    list the exit among their connected peers.

Recommendation: do not register the exit (this is what keeps it out of other
clients), and pin it in our client. Publishing its address is a separate,
smaller choice. `announce: false` also hides the IP and stops others from
dialing it; on a cloud VM with a public address, publishing is the
better-trodden path. I would start unpublished as you propose and fall back
to publishing if the relays do not connect.

One limit either way: the exit is also an ordinary HOPR node. It connects to
other peers, and nothing stops another operator from opening a channel to it
or sending it packets as a relay (section 3.6).

## A.5 Changes to the plan in section 6

For the off-the-shelf start, steps 1 to 4 and 11 shrink:

1. Record the artifact versions and checksums (no source checkouts, no build
   host, no local cluster).
2. Write the three configs and the exit host setup.
3. Provision 5 machines (plus monitoring) with a deletion timer, reusing the
   bench's DigitalOcean code where it fits.
4. Monitoring first, then relays, exit, client in the staged order of A.3.
5. Topology proof, then the baseline measurements of the three issues.
6. Report. Custom builds only where the baseline leaves a question open.

Decisions still open from section 7: 4 (exit form; this addendum assumes a
plain VM with the stock image), 6 (provider and region; recommendation above),
7 (funding), 8 (PIX price), 10 (own indexer; not for this phase), 11
(lifetime; this addendum assumes 48 hours with a deletion timer), 12 (tooling
home), 13 (closed if you agree with A.4: unregistered and pinned). New: A.2
dedicated or shared CPUs, and A.4 exit address published or not.

---

# Addendum B (2026-11-21): the lab is running; first test results

The lab was built on DigitalOcean (5 × `c-4`, Frankfurt) with released software only. Operating
notes are in the repository's `README.md`; this run's results are in
`results/2026-11-21-first-test/`. Everything here was observed directly [V].

## B.1 What was set up

- Relays: hoprd 5.0.4 release binary, `AutoRedeeming` only.
- Exit: hoprd 5.0.4 extracted from the published container image, `gnosis_vpn-server` 0.7.1,
  `announce: false`, not registered as an exit, channel allowlist of our 3 relays.
- Client: `gnosisvpn` 1.1.0 package, exit pinned by address, channel allowlist of our 3 relays.

Three predictions of the research held:

- The client accepted the allowlist and asked for exactly 120.35 wxHOPR (75 channels, 35.35 pool,
  10 fee), as derived in section 5.2.
- An exit with no published address and no registry entry works: the client found it by its on-chain
  key binding and connected in about 10 seconds.
- Other operators use our relays: within 15 minutes each relay had 8 incoming channels, 6 of them
  from nodes that are not ours. Nobody opened a channel to the unannounced exit.

One correction to section 3.2: hoprd reads allowlist addresses as lists of 20 decimal byte values,
not hex strings (the address type uses plain derived serialization). The client's TOML takes hex.

## B.2 Verification that client and exit use only our relays

| Evidence | Result |
| --- | --- |
| On-chain channels (`./lab verify channels`) | Client: 3 outgoing channels, to relay1, relay2, relay3. Exit: the same 3. No other channel in either direction. |
| Client status, route walk | 3 forward paths with 3 distinct first relays, 3 return paths. |
| Client planner log, session 2 (`./lab verify paths`) | 33 forward and 33 return candidate sets over the session; every one lists exactly relay1, relay2 and relay3 and nothing else. The planner draws each packet's path and each reply block's return path from these sets. |
| Packet counters, session 2 (100 MB download) | Relays forwarded 36,908 + 36,706 + 37,151 = 110,765 packets. The exit sent 80,697 and received 31,917 = 112,614, which includes its direct probe traffic to peers (about 1.6 %). The exit's paid-session egress alone was 79,543. |
| Rejected packets on relays | None. |

The traffic was spread evenly: each relay carried a third.

## B.3 First observations on the three issues

- **Issue 1 reproduced on the first connection.** The exit's metric
  `hopr_pix_gate_blocks_total{reason="predeposit_exhausted"}` counted one block of 41.3 s in
  session 1 and one of 15.8 s in session 2. In session 1 the exit logged "ssa deposit confirmed"
  63 s after the session started. A 30 MB download started 20 s after connecting averaged
  4.6 Mbit/s; the same path later ran at a steady 23 to 24 Mbit/s (100 MB in 35 to 37 s).
- **Issue 2 did not show** in this co-located setup: both connects took about 10 s.
- **Issue 3, the cost side, is visible.** Each session paid 5.94 wxHOPR up front, and session 1
  paid a second 5.94 wxHOPR for the next chunk once the first was 85 % used. The exit rebuilt the
  first key after about 400 MB and swept 5.93 wxHOPR into its Safe. The two later payments
  (11.88 wxHOPR) were not collected before the sessions ended.

## B.4 Open items

- No deletion timer is set; the droplets bill about $0.63 per hour.
- No central monitoring yet (Prometheus, log collection, chain probe from section 4.3).
- The funding Safe's balance moved by amounts I did not send during the build (−225.35 and later
  +241.01 wxHOPR), consistent with a bench run elsewhere using the same Safe and owner account.
  Two processes sending from one account can collide on transaction nonces.
