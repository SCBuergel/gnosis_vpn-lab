# Results

One folder per run, named by date and a short label. Only small, readable summaries are committed
here: numbers, tables and findings. Raw logs and counter snapshots stay in `raw/<same label>/`, which
git ignores because they can be large and contain machine addresses.

| Run | What | Outcome |
| --- | --- | --- |
| [2026-11-21-first-test](2026-11-21-first-test/README.md) | First lab build on DigitalOcean and a first connection | Traffic confined to the three relays; 21 to 24 Mbit/s steady; the post-connect stall reproduced |
| [2026-11-21-connect-stall](2026-11-21-connect-stall/README.md) | Three connects, each followed at once by a 100 MB download | Connected in 5 to 6 s; after 17 s of download the transfer stopped for 13 to 17 s, until the exit saw the payment |

Every experiment is recorded here. Its `README.md` starts with two things:

- **Measured:** a brief summary of what was measured.
- **Repository commit:** the commit of this repository the measurement was made with.

`./lab stall-test` writes both into `measurement.json` by itself (with a flag when tracked files had
uncommitted changes); the README repeats them for the reader.

A run folder holds:

- `README.md`: what was measured, at which commit, the numbers and what they mean.
- `measurement.json`: what, when, commit, software versions, provider and destination (newer runs).
- `iterations.csv`, `bytes-per-second.csv`: output of `./lab stall-test`.
- `throughput.csv`: one row per timed download (`./lab measure`). A failed download has an empty rate, never zero.
- `verify-*.json`: output of the `./lab verify` commands.
