# Results

One folder per run, named by date and a short label. Only small, readable summaries are committed
here: numbers, tables and findings. Raw logs and counter snapshots stay in `raw/<same label>/`, which
git ignores because they can be large and contain machine addresses.

| Run | What | Outcome |
| --- | --- | --- |
| [2026-11-21-first-test](2026-11-21-first-test/README.md) | First lab build on DigitalOcean and a first connection | Traffic confined to the three relays; 21 to 24 Mbit/s steady; the post-connect stall reproduced |
| [2026-11-21-connect-stall](2026-11-21-connect-stall/README.md) | Three connects, each followed at once by a 100 MB download | Connected in 5 to 6 s; after 17 s of download the transfer stopped for 13 to 17 s, until the exit saw the payment |
| [2026-11-21-german-exit](2026-11-21-german-exit/README.md) | The same test, one iteration, against the production exit GVPN-GER-1 | Same 16 s interruption; forward paths through our relays, return paths through other operators' relays; rate capped near 10 Mbit/s |
| [2026-11-21-edinburgh-exit](2026-11-21-edinburgh-exit/README.md) | The same test, one iteration, against the Edinburgh exit | Same 15 s interruption; connecting took 28 s because the exit's first answer was lost and the client waited a fixed 20 s |
| [2026-11-22-laptop-client](2026-11-22-laptop-client/README.md) | The same test, two iterations, from a laptop on a home connection through the lab relays and exit | With an immediate download: stopped at 13 MB and never resumed, because the client could not reach the payment relayer while the exit held the traffic back. With 90 s idle first: no interruption at all |
| [2026-11-22-payment-deadlock](2026-11-22-payment-deadlock/README.md) | Packaged client 1.1.0 while the exit delays its packets to the payment relayer by 3 s; logs of both sides checked for any other fault | Download stopped at 13.4 MB and never resumed; the exit closed the session after 3 minutes. Registration, session and both path directions were healthy: the late payment alone causes it |
| [2026-11-22-fix-sidecar-and-hold](2026-11-22-fix-sidecar-and-hold/README.md) | A patched client (payment through its own session, tunnel held until paid) against an unmodified build, under normal conditions and with the laptop's failure simulated by delaying the exit's packets to the payment relayer; five run folders | Patched: no interruption in any run, at the price of a 42 s connect. The laptop's failure reproduced with the unmodified client and gone with the patched one |
| [2026-11-22-main-patched](2026-11-22-main-patched/README.md) | The patch rebuilt on the client's current main, with the relayer connection opened in parallel; unmodified and patched, normal and with the relayer delayed; three run folders | Patched: never held back by the exit; connect 42 s, 67 s with the delayed relayer. One connect took 155 s because the hold waited for a payment that had already arrived |
| [2026-11-22-blokli-race](2026-11-22-blokli-race/README.md) | A made deposit that the client does not record: the pool looks for the deposit's notes on Blokli once, right after the relayer reports inclusion. Unmodified and fixed `hopr-strategy`, with a proxy that reports new notes late; six run folders | Notes 3 s late: unmodified client recorded 0 of 3 deposits, fixed client 4 of 4; the exit confirmed all. Without injected lag Blokli was behind in 2 of 15 connects |

Every experiment is recorded here. Its `README.md` starts with two things:

- **Measured:** a brief summary of what was measured.
- **Repository commit:** the commit of this repository the measurement was made with.

`./lab stall-test` writes both into `measurement.json` by itself (with a flag when tracked files had
uncommitted changes); the README repeats them for the reader.

A run folder holds:

- `README.md`: what was measured, at which commit, the numbers and what they mean.
- `measurement.json`: what, when, commit, software versions, provider and destination (newer runs).
- `iterations.csv`, `bytes-per-second.csv`: output of `./lab stall-test`; `iterations.csv` alone: `./lab payment-test`.
- `throughput.csv`: one row per timed download (`./lab measure`). A failed download has an empty rate, never zero.
- `verify-*.json`: output of the `./lab verify` commands.
- `*-excerpt.txt`: short, filtered parts of the logs that a finding rests on.
