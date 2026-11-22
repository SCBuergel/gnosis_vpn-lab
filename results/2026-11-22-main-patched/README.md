# 2026-11-22: the side-car session and the hold, rebuilt on the client's current main

**Measured:** the connect-and-download test with two builds of `gnosis_vpn-client` at `e6b33f36` (main,
version 1.1.1) on the lab client, against the lab exit: unmodified, and with the three commits of the
branch `sidecar-relayer-hold`. Two iterations of the patched build under normal conditions are in this
folder; the unmodified build and the patched build with the exit's packets to the payment relayer delayed
by 3 s are in the two folders linked below.

**Repository commit:** `91b833f` for all three folders (clean working tree). `measurement.json` names
client 1.1.0 because it reads the packaged version from `lab.toml`; the binaries were the builds
described here, swapped in by hand.

## Result

| Condition | Build | `connect` until connected | Held back by the exit | Download of 100 MB |
| --- | --- | --- | --- | --- |
| Normal ([main-control](../2026-11-22-main-control/README.md)) | unmodified | 5.0 s | 18.7 s, after 13.3 MB | complete, 79 s |
| Normal (this folder, run 2) | patched | 42.0 s | 0.0 s | complete, 82 s |
| Normal (this folder, run 1) | patched | 155.5 s | 0.0 s | complete, 82 s |
| Packets to the relayer delayed 3 s ([main-patched-delay](../2026-11-22-main-patched-delay/README.md)) | patched | 67.1 s | 0.0 s | complete, 82 s |

- **No run of the patched build was held back by the exit.** Its counter of time spent holding traffic
  stayed at 0.0 s in all three.
- **The unmodified main build behaves like the packaged 1.1.0:** connected in 5 s, then an 18.7 s pause
  after 13.3 MB.
- **With the delayed relayer the patched build connects in 67 s.** The same condition stops the
  unmodified client for good ([payment-deadlock](../2026-11-22-payment-deadlock/README.md)). That
  comparison was made with client 1.1.0 and was not repeated with the unmodified main build.

## What changed since the first version of the patch

The first version is described in
[2026-11-22-fix-sidecar-and-hold](../2026-11-22-fix-sidecar-and-hold/README.md).

- **Rebased** from `v1.1.0` onto main, split into a side-car commit and a hold commit, formatted and
  linted with the projects' own settings. The override variable for the hold time is gone.
- **The relayer connection is opened when the route is set,** in parallel with the paid session,
  instead of when the payment code first needs it.

| Step, seconds after `connect` was issued | First version | This version (run 2) |
| --- | --- | --- |
| First relayer session ready | 4.0 | 1.8 |
| Payment proof computed | 10.1 | 8.1 |
| Relayer accepted the deposit | 14.5 | 14.5 |
| Client notices and starts the 22 s wait | 17.0 | 16.9 |
| Connected | 42.1 | 42.0 |

The early opening brings everything up to the proof forward by 2 s. In this run the relayer then took
6.4 s to answer the submission instead of 4.5 s, so the total did not change. One run of each version;
the gain is not shown end to end.

## Weaknesses seen in these runs

- **The 155 s connect of run 1 is the hold waiting for nothing.** The exit confirmed that session's
  deposit 39 s after the commitment. The client's pool had logged `deposit flush deferred until an
  earlier Curvy operation is reconciled`, so its own state never showed the deposit as made, and the
  hold ran into its 150 s limit. The earlier operation was the failed payment of the deadlock test an
  hour before. The same happened once with the first version, also after a failed payment.
- **The fixed 22 s wait is not an upper bound.** From the relayer accepting the deposit to the exit
  confirming it took 26.0 s in run 2 and 18.6 s in the delay run (first version: 20.6 to 21.5 s). In
  run 2 the client attached the tunnel 1.7 s before the exit's confirmation. The download still met no
  hold, because attaching and the check ping take 3 s.
- **The payment state the hold reads is refreshed every 5 s,** so the hold notices a payment 2 to 3 s
  late.
- **Short gaps remain:** every run, with either build, has gaps of 1 to 2 s in the download that are
  not the exit holding traffic back. Not explained.

## Builds

Built with `cargo build --release --locked` on Ubuntu 24.04, Rust 1.99.1, 8 dedicated vCPUs (15 and 20
minutes with both builds running at once). On the patched tree `cargo clippy` reported nothing for the
changed crates and the 561 unit tests of `gnosis_vpn-lib` passed. Only the full branch
(`sidecar-relayer-hold`) was built and run; the branch with the side-car commit alone was not built
separately.

Numbers: `iterations.csv`, `bytes-per-second.csv`. Raw samples and counters are under `raw/` (not in git).
