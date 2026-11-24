# Exit: the PIX withdrawal proof stalls traffic for seconds and reloads its 97 MB key every time

Suggested repository: `hoprnet/hopr-strategy`. The code to change is in `0xCurvy/rs-sdk`
(`curvy-sdk`, `curvy-witnesscalc`).

## Summary

Every time an exit sweeps a received payment it makes one `pix-withdrawal-bound(10,30)` proof. On a
4-CPU exit this takes 5 to 7 s, and while it runs the exit's traffic drops to a fraction. Two things
make it worse than it has to be:

1. **The proof runs on the global Rayon pool, which `hoprd` also uses for per-packet work.** Small jobs
   on that pool wait a median of 235 ms and up to 1 s while a proof runs.
2. **The proving key and the witness graph are read, hashed and parsed again for every proof.** That is
   1.3 s of 5.1 s.

Both can be removed without touching the prover.

## What we see on an exit

Exit: `hoprd` 5.0.4, 4 vCPU Xeon Platinum 8168, one client downloading at about 12 Mbit/s.

```
curvy_witnesscalc: Curvy proof timing circuit="pix-withdrawal" graph_load_ms=220 prover_load_ms=1929 witness_ms=290 groth16_ms=4506 total_ms=6884
```

- 9 proofs: 6.5 to 7.2 s each.
- In 9 of 9 the client's download fell from about 12 Mbit/s to 0.3 to 2 Mbit/s for 3 to 4 s during the
  Groth16 phase. Example, per second: 12.6, 12.3, 12.5, 5.0, 0.7, 1.8, 1.9, 15.6 Mbit/s.
- `udp queue dispatch took too long` (150 to 540 ms) was logged inside the proof window in 5 of 9.
- One proof per recovered payment, so about once per 630 MiB per client.

## Benchmark in isolation

Standalone program with `curvy-witnesscalc` 0.2.2 and `curvy-prover` 0.1.5, the exit's own key and
graph, on an idle exit of the same type. 5 proofs per condition. Source and full output:
https://github.com/SCBuergel/gnosis_vpn-lab/tree/main/results/2026-11-24-exit-proof-benchmark

**Key kept loaded** (2 threads, as `hoprd` sizes the pool on 4 CPUs):

| | Per proof |
| --- | --- |
| `Circuit::prove` as today | 4.91 to 5.42 s, median 5.06 |
| `load_calculator` and `load_prover` once, then `calculate` and `prove_assignment` | 3.62 to 3.85 s, median 3.72 |

The process holds 218 MB with the key loaded, against 184 to 189 MB when loading every time.

**Proof on a pool of its own.** One 0.1 ms job per millisecond on a 2-thread global pool
(`rayon::spawn_fifo`), time from submission to completion:

| Proof runs on | Median | 99% | Longest | Proof time |
| --- | --- | --- | --- | --- |
| nothing | 0.11 ms | 0.21 ms | 1.2 ms | |
| the global pool (as today) | 235 ms | 854 ms | 987 ms | 3.95 to 4.34 s |
| its own 2-thread pool, via `ThreadPool::install` | 0.11 ms | 0.21 ms | 3.1 ms | 4.28 to 4.59 s |

More threads are not the answer: 4 threads were only 13% faster than 2 on this machine.

## Where

- `curvy-sdk` 0.2.2 `src/client.rs:144`: `tokio::task::spawn_blocking(move || circuit().prove_bound(&input))`.
  The blocking thread is outside any Rayon pool, so the proof's parallel work goes to the global pool.
- `curvy-witnesscalc` 0.2.2 `src/lib.rs:506-523`: `Circuit::prove` calls `load_calculator()` and
  `load_prover()` on every call.
- `hopr-lib` sizes the global Rayon pool to half the CPUs, and the packet pipeline submits to it with
  `spawn_fifo_blocking`.

## Proposal

1. Run proofs inside a dedicated Rayon pool: `pool.install(|| circuit.prove_bound(&input))`. One or two
   threads, ideally configurable by the host.
2. Keep the calculator and the prover of a circuit loaded after first use (`curvy-prover` already has
   `ResidentProver`), or let the host opt in to it.

## Not verified

- `hoprd` was not changed. That its packet work waits like the stand-in jobs is inferred from the code
  and from the dips above.
- The build flags of the published `hoprd` image are unknown; the benchmark used `opt-level = 3` and
  fat LTO.
- Whether newer `curvy-sdk` versions than 0.2.2 already changed this was not checked.
