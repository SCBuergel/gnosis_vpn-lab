# 2026-11-25: the exit stalls for all clients when a client's session is established

**Measured:** the ping latency of one Gnosis VPN client (the *victim*) while a second client connects
to the same exit and disconnects again, three times, sending no traffic of its own. The CPU time of
every thread of the exit's hoprd was sampled every 0.1 s.

**Result:** every connect of the second client stalls the victim for 1.2 to 1.5 s. The stall ends
within 0.1 s of the exit finishing the new session's payment commitment (PIX SSA). It is not the
Curvy proof. The cause below is read from the source and fits the measurements; the last step of it
is inferred.

This is the "other stall" of the [PR #8763 test](../2026-11-25-pr8763-before-after/README.md), where
it appeared once in each of 8 arms.

## Setup

Lab `vpn-lab3` as in the PR #8763 test: exit with 4 vCPU running hoprd 5.0.6 built from source
(`4e33b171…`, unpatched), victim on gnosisvpn 1.1.0, second client on client main `5d902a6`. The
victim pings `1.1.1.1` every 0.2 s for 150 s. Harness: [`repro/reconnect-stall/`](../../repro/reconnect-stall/README.md).

## What was measured

| Run | Connects | Stalls ending when a commitment finished | Their length | Exit CPU during them |
| --- | --- | --- | --- | --- |
| CPU pool at its default (2 threads) | 3 | 3 | 1.27, 1.29, 1.47 s | 2 threads at about 51 % each |
| CPU pool set to 4 threads | 3 | 3 | 1.20, 1.28, 1.37 s | 4 threads at about 25 % each |

- **Every connect gives one stall**, 6 of 6, and each ends within 0.1 s of the exit logging
  `SSA is fully committed for verification` for the new session.
- **The same holds for the 8 stalls of the PR #8763 test:** each ends within 0.03 s of that log line.
- **The work is one core's worth however many threads share it:** about 100 % in total, split evenly
  over the pool's threads, 2 or 4. Doubling the pool did not shorten the stall.
- **No Curvy proof is involved:** the exit logged nothing about Curvy, proofs or withdrawals within
  1 s of any of the 8 stalls of the PR #8763 test, and a connect needs no proof (the exit proves when
  it withdraws).

Each stall with its timing is in [`summary.md`](summary.md).

## Cause, from the source (hoprnet `fa69827`, pinned by hoprd 5.0.6)

1. A new session with payments has the client send its commitment: 4096 group elements, split over
   many Start-protocol messages (`SsaClientCommitmentMessage::new_multiple`).
2. The exit handles each message in `handle_ssa_commit` (`transport/session/src/manager.rs:10815`),
   which runs `insert_coefficient_commitments` as a job on the shared Rayon CPU pool
   (`hopr_utils::parallelize::cpu::spawn_blocking`).
3. That pool also encodes and decodes every packet of the node (`spawn_encode_blocking`,
   `spawn_decode_blocking` in `transport/hopr/src/protocol/pipeline/mod.rs`). It has half the
   machine's vCPUs: 2 threads on this exit (`prepare_tokio_runtime`, `hopr/hopr-lib/src/lib.rs`).
4. Each job decodes its commitments and checks each for the prime-order subgroup
   (`decode_commitment`, `protocols/pix/src/lib.rs:650`) **while it holds the lock of that session's
   commitment builder** (`protocols/pix/src/reconstructor/mod.rs:1781`). 4096 of them take about
   1.3 s, which is about 0.3 ms each.
5. The jobs of one session therefore run one at a time. One pool thread computes, and every other
   pool thread has picked up another job of the burst and waits for the lock. That is the measured
   picture: one core of work spread evenly over all pool threads.
6. *Inferred:* with every pool thread either computing or waiting for that lock, no thread is left to
   encode or decode packets until the burst is done, so all traffic through the exit stops for that
   time. The victim's pings come back together when it ends.

## What this means

- **Any client that opens a session stalls every other client of that exit** for about 1.3 s on a
  4-vCPU exit. It needs no misconfiguration and no traffic.
- **More CPU threads do not fix it** while the jobs wait for one lock; a bigger pool only helps once
  it is larger than the number of jobs waiting.
- Directions for a fix, none tested here: decode and check the commitments before taking the lock;
  run this work outside the pool that packets use; or keep some pool threads for packets.

## Not shown / caveats

- **Step 6 is inferred.** The queueing of packet jobs behind the burst was not observed directly
  (for example through the pool's queue-wait metric).
- **The number of commitment messages and the cost split** between decompression and the subgroup
  check were not measured.
- **Other moments may trigger it too.** With the 4-thread pool one more commitment finished at 87.6 s,
  with no connect, next to a 0.9 s stall. A session's later payment cycles would send the same burst;
  this was not followed up.
- **Stalls at a disconnect are a different thing.** Three stalls of 1.5 to 2.6 s end at a
  `no SURB for its return path` drop with the exit idle: that is hoprnet#8753 on this unpatched
  build (the second client still had its retransmission configuration).
- One exit size (4 vCPU), one day, 6 connects.

## Files

| Path | Content |
| --- | --- |
| `cpu-threads-default/`, `cpu-threads-4/` | `ping.txt` (victim), `threads.txt` (epoch, thread id, name, CPU ticks of the exit's hoprd), `events.txt` (connects and disconnects), `exit.log.gz` (the exit's session, commitment and SURB-drop lines), `exit-build.txt` |
| `summary.md` | output of `analyze.py` |
