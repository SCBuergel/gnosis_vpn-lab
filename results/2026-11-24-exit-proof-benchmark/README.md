# 2026-11-24: the exit's payment-withdrawal proof, benchmarked alone

**Measured:** the Groth16 proof an exit makes to sweep a received payment (`pix-withdrawal-bound(10,30)`,
one real note padded to 10), run by a standalone program on the lab exit (4 vCPU Xeon Platinum 8168,
`hoprd` 5.0.4 running but idle, no client connected). Same crates as the exit binary:
`curvy-witnesscalc` 0.2.2 and `curvy-prover` 0.1.5, with the exit's own proving key and witness graph.
Three questions: what loading the key for every proof costs, what more threads give, and what a proof
does to small jobs that share its thread pool. 5 proofs per condition, one run.

**Repository commit:** `8ee8e8f` (plus this folder; the program is in `proofbench/`, not part of `./lab`).

## Result

Loading the key once saves 1.3 s of 5.1 s per proof. Running the proof on a thread pool of its own
keeps small jobs on the shared pool at 0.1 ms; on the shared pool they wait a median of 235 ms and up
to 1 s. Four threads are only 13% faster than two.

### Loading the key and graph for every proof

| Threads | As today: load for every proof | Key and graph kept loaded | Saved |
| --- | --- | --- | --- |
| 2 (what `hoprd` gives the pool on 4 CPUs) | 4.91 to 5.42 s, median 5.06 | 3.62 to 3.85 s, median 3.72 | 1.3 s, 26% |
| 4 | 4.56 to 4.94 s, median 4.65 | 3.18 to 3.35 s, median 3.24 | 1.4 s, 30% |

- **"As today"** is `Circuit::prove`, the call `curvy-sdk` 0.2.2 makes (`src/client.rs:144`). It reads,
  hashes and parses the 97 MB key and the graph each time (`curvy-witnesscalc` 0.2.2 `src/lib.rs:506-523`).
- **"Kept loaded"** calls `load_calculator` and `load_prover` once (1.44 s) and then only
  `calculate` and `prove_assignment`. Both are public functions of the same crate.
- **Memory:** the process holds 218 MB with the key kept loaded. Loading every time, it stays at 184 to
  189 MB after the first proof anyway.

### A proof and small jobs on the same pool

One job of about 0.1 ms was submitted every millisecond with `rayon::spawn_fifo` to a global pool of
2 threads, as a stand-in for per-packet work. Time from submission to completion:

| Proof runs on | Median | 90% | 99% | Longest | Jobs over 100 ms | Proof time |
| --- | --- | --- | --- | --- | --- | --- |
| nothing (idle) | 0.11 ms | 0.13 ms | 0.21 ms | 1.2 ms | 0 of 4,667 | |
| the same pool (as today) | 235 ms | 678 ms | 854 ms | 987 ms | 12,949 of 19,112 | 3.95 to 4.34 s |
| its own pool, 2 threads | 0.11 ms | 0.12 ms | 0.21 ms | 3.1 ms | 0 of 20,622 | 4.28 to 4.59 s |
| its own pool, 1 thread | 0.11 ms | 0.12 ms | 0.16 ms | 1.9 ms | 0 of 36,542 | 7.43 to 8.15 s |

- **The own pool is used through `ThreadPool::install` around the unchanged prover call.** The prover
  needs no change for this.
- **Cost:** with 2 threads of its own next to the 2 shared ones, the proof took about 8% longer.

## Not shown

- **`hoprd` itself was not changed or measured.** That its packet work waits behind the proof in the
  same way is inferred from its code (`hopr-lib` sizes the global Rayon pool to half the CPUs and the
  packet pipeline uses `spawn_fifo_blocking`) and from the download dips seen on the second lab's exit
  during every proof. The stand-in job is not `hoprd`'s packet code.
- **The 6.5 to 7.2 s seen on the second lab's exit** were measured while that exit forwarded about
  12 Mbit/s. This idle exit needs 5.1 s for the same proof. The difference is presumably the shared pool.
- One run of 5 proofs per condition, on one machine type. On the build machine (i7-1165G7, 2 threads)
  the proof took 3.4 s loading every time and 3.0 s with the key kept loaded.
- The benchmark was built with `opt-level = 3`, fat LTO, one codegen unit. The build settings of the
  published `hoprd` image are not known.

## Reproduce

```bash
cd proofbench && cargo build --release
export CURVY_ZK_KEYS_DIR=/usr/local/share/curvy-zk     # the exit's artifacts
RAYON_NUM_THREADS=2 ./target/release/proofbench cold 5
RAYON_NUM_THREADS=2 ./target/release/proofbench resident 5
./target/release/proofbench interfere 5 2 2            # proofs, shared pool threads, own pool threads
```

## Files

| File | Content |
| --- | --- |
| `lab1-exit.txt` | Complete output of the run on the lab exit |
| `proofbench/` | The benchmark program; its input is the one of the crate's test `pix_profiles.rs` |
| `issue-draft.md` | Draft of an issue for the developers; not filed |
