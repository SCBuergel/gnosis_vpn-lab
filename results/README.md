# Results

One folder per run, named by date and a short label. Only small, readable summaries are committed
here: numbers, tables and findings. Raw logs and counter snapshots stay in `raw/<same label>/`, which
git ignores because they can be large and contain machine addresses.

| Run | What | Outcome |
| --- | --- | --- |
| [2026-11-21-first-test](2026-11-21-first-test/README.md) | First lab build on DigitalOcean and a first connection | Traffic confined to the three relays; 21 to 24 Mbit/s steady; the post-connect stall reproduced |

A run folder holds:

- `README.md`: what was run, the numbers and what they mean.
- `throughput.csv`: one row per timed download (`./lab measure`). A failed download has an empty rate, never zero.
- `verify-*.json`: output of the `./lab verify` commands.
