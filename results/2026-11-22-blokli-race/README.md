# 2026-11-22: a made deposit that the client does not record, and a fix

**Measured:** 15 connects of the lab client to the lab exit, each paying the session's first deposit
(5.94 wxHOPR), with two builds of `gnosis_vpn-client` main at `e6b33f36`: unmodified, and with
`hopr-strategy` replaced by the fix (one commit, `d6ad33ff`, on `97bfc19a`, the revision main pins).
The client read Blokli through a proxy that could report new Curvy notes late. Per connect: did the
client record the deposit as made, when did the exit confirm it, and what did Blokli answer.

**Repository commit:** `4dc838e` (clean working tree; recorded in each `measurement.json`, which names
the packaged client version 1.1.0 although the binaries were the builds named in `client_build`)

**Result:** With notes reported 3 s late the unmodified client recorded none of 3 deposits and the fixed
client all 4. The exit confirmed every one of the 15 deposits. In 2 of the 15 connects Blokli itself
did not know the note yet at the client's first look, with no lag injected for that look.

| Client build | Notes reported late by | Connects | Deposit recorded by the client | Confirmed by the exit | Folder |
| --- | --- | --- | --- | --- | --- |
| unmodified | 0 s | 3 | 3 | 3 | [control-nolag](../2026-11-22-blokli-race-control-nolag/README.md) |
| unmodified | 3 s | 3 | **0** | 3 | [control-lag3](../2026-11-22-blokli-race-control-lag3/README.md) |
| fixed | 3 s | 4 | **4** | 4 | [fix-lag3](../2026-11-22-blokli-race-fix-lag3/README.md), [fix-lag3-after](../2026-11-22-blokli-race-fix-lag3-after/README.md) |
| fixed | 0 s | 3 | 3 | 3 | [fix-nolag](../2026-11-22-blokli-race-fix-nolag/README.md) |
| fixed | 20 s | 2 | 0 | 2 | [fix-lag20](../2026-11-22-blokli-race-fix-lag20/README.md) |

## The fault

1. The client submits the deposit to the Curvy relayer and polls the relayer every 2 s until it
   reports the transaction as included.
2. The pool then looks the deposit's notes up through Blokli, once.
3. If Blokli has not indexed the transaction yet, the pool returns `AmbiguousAllocation`. The strategy
   logs `deposit flush deferred until an earlier Curvy operation is reconciled` and drops the deposit
   from its state.
4. The deposit is on chain and the exit confirms it. The client's session stays at 0 paid chunks
   (`payment_pending`) until it ends. The pool notices the deposit at its next operation, usually the
   next connect, but does not tell the strategy.

Code: `hopr-strategy`, `src/pix/pools/curvy/sdk.rs`, `reconcile_relay_aggregation_with`, the
`relay_winner` call after `await_inclusion`.

## The fix

Branch `fix/curvy-inclusion-note-race` of `SCBuergel/hopr-strategy`, commit `d6ad33ff`: after the relayer
reports inclusion, the pool looks for the notes up to 20 times, 500 ms apart (9.5 s), before returning
`AmbiguousAllocation`. Nothing is proved or submitted again. About 30 lines including comments, plus
two unit tests.

Not part of the fix: when the notes stay unknown for all 20 looks, the deposit is still dropped from the
client's state as before. The `fix-lag20` runs show that limit.

## How the race was forced

`./lab blokli-lag install` starts a proxy on the first relay and points the client's Blokli address at
it ([remote/blokli-lag-proxy.py](../../remote/blokli-lag-proxy.py)). The proxy forwards everything
unchanged except the query `curvyNoteStatus`: a note Blokli knows is reported as unknown until N
seconds after the proxy first saw Blokli report it. Notes already committed when first asked about
(the pool's older funding notes) are never held back. The proxy records Blokli's real answer and the
answer it gave for every such query.

The exit reads Blokli directly, so its confirmation times are not affected.

## What each run showed

Seconds are counted from `connect`.

| Condition | Run | Client's outcome | at | Looks needed | Exit confirmed at | Client state after |
| --- | --- | --- | --- | --- | --- | --- |
| unmodified, 0 s | 1 | recorded | 15.7 | 1 | 38.8 | funded, 1 of 1 paid |
| unmodified, 0 s | 2 | recorded | 53.4 | 1 | 74.7 | funded, 1 of 1 paid |
| unmodified, 0 s | 3 | recorded | 15.8 | 1 | 39.9 | funded, 1 of 1 paid |
| unmodified, 3 s | 1 | deferred | 17.3 | 1, failed | 39.8 | payment_pending, 0 of 1 paid |
| unmodified, 3 s | 2 | deferred | 15.2 | 1, failed | 37.1 | payment_pending, 0 of 1 paid |
| unmodified, 3 s | 3 | deferred | 13.5 | 1, failed | 35.4 | payment_pending, 0 of 1 paid |
| fixed, 3 s | 1 | recorded | 21.1 | 7 | 36.0 | funded, 1 of 1 paid |
| fixed, 3 s | 2 | recorded | 18.8 | 8 | 37.5 | funded, 1 of 1 paid |
| fixed, 3 s | 3 | recorded | 21.9 | 7 | 46.4 | funded, 1 of 1 paid |
| fixed, 3 s | 4 | recorded | 19.3 | 7 | 37.4 | funded, 1 of 1 paid |
| fixed, 0 s | 1 | recorded | 13.5 | 1 | 37.0 | funded, 1 of 1 paid |
| fixed, 0 s | 2 | recorded | 17.4 | 1 | 40.3 | funded, 1 of 1 paid |
| fixed, 0 s | 3 | recorded | 17.4 | 1 | 44.1 | funded, 1 of 1 paid |
| fixed, 20 s | 1 | deferred | 25.5 | 20, all failed | 34.7 | payment_pending, 0 of 1 paid |
| fixed, 20 s | 2 | deferred | 25.6 | 20, all failed | 37.6 | payment_pending, 0 of 1 paid |

- **The fix costs time only when the race is lost.** With no lag the fixed client recorded the deposit
  at the first look, like the unmodified one. With the 3 s lag it needed 7 or 8 looks, 3 to 3.5 s.
- **Under the 20 s lag the fixed client gives up 9.5 s later than the unmodified one would,** and holds
  the pool's chain lock for that time. The outcome is the same as today.
- **After the 20 s runs the fixed client recovered by itself:** the two following runs (3 and 4 of
  "fixed, 3 s") recorded their deposits, and the pool reconciled the two deferred ones at the next
  connect each.

## The race without injection

In two connects the proxy's record shows Blokli itself answering "unknown" at the client's first look,
before the proxy changed anything ([log-excerpts.txt](log-excerpts.txt)):

- **Unmodified, 3 s, run 2:** the single look at 13:46:21.209 got `blokli=0`. The deposit was deferred.
  This run would have failed without the proxy.
- **Fixed, 3 s, run 2:** the first look at 13:50:57.763 got `blokli=0`, the second at 13:50:58.306 got
  `blokli=1`. Blokli was at most 0.54 s behind the relayer.

That is 2 of 15 connects. In the client's logs of the day before and the morning, 4 of 24 first
deposits were deferred the same way, with no proxy involved.

## Checks on the fix itself

- Unit tests of `hopr-strategy` (`cargo test --workspace --exclude hopr-strategy-integration-tests
  --all-features`): 637 + 55 + 2 + 1 passed, 4 ignored, 0 failed.
- The two new tests fail when the fix is switched off and pass with it.
- `cargo clippy --all-features --all-targets -- -D warnings` and `cargo +nightly fmt --check`: clean.
- The client was built with `cargo build --release --locked`; its only difference from the unmodified
  build is the source of `hopr-strategy` ([client-build.diff](client-build.diff)).

## Not shown by these runs

- **How long Blokli can lag in production.** One natural case measured at most 0.54 s. The 9.5 s limit
  of the fix is a choice, not a measured bound.
- **Frequency.** 2 of 15 and 4 of 24 are small samples from one client and one exit.
- **Traffic.** No download ran in these connects. The fault does not depend on traffic: the deposit is
  requested when the session opens.
- **The integration tests of `hopr-strategy`** (`tests/integration`) were not run.
- Run 2 of "unmodified, 0 s" paid 35 s later than the others (proof at 44 s). The log shows no
  warning for it; not explained here.

## Setup notes

- **The proxy must be on a public address.** The client takes its route to the internet from its route
  to Blokli. A first attempt with the proxy on the private network sent the client's peer traffic out
  of the wrong interface and no connection came up. Its deposit was never submitted; it is not listed.
- **Top-up:** 80 wxHOPR from the funding Safe to the client (`topup-4` in the transaction journal).
  The 15 deposits are 89.1 wxHOPR, not counting the relayer's fees.

## Reproduce

```bash
./lab blokli-lag install                 # proxy on relay1, client pointed at it
./lab client start
./lab blokli-lag on --seconds 3          # also: off, status
./lab payment-test my-label --build main-control --iterations 3 --yes
./lab blokli-lag remove                  # client back to Blokli directly, proxy gone
```

The client binaries are swapped by hand on the client machine; `--build` only names them in the record.

## Files

| File | Content |
| --- | --- |
| `log-excerpts.txt` | Proxy, client and exit log lines of three runs: the two natural cases and one 20 s run |
| `client-build.diff` | The change to `gnosis_vpn-client` for the fixed build |
| `../2026-11-22-blokli-race-*/iterations.csv` | One row per connect |
| `../2026-11-22-blokli-race-*/measurement.json` | What, when, commit, build name, worker checksum, lag |

The full logs of every connect are in `raw/2026-11-22-blokli-race-*/` (not in git).
