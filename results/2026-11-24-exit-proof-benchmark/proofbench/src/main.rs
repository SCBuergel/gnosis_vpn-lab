//! Benchmark of the PIX withdrawal proof (the exit's sweep proof) in isolation.
//!
//!   proofbench cold N [NOTES]        N proofs the way hopr-strategy 9.2.0 makes them today:
//!                                    `Circuit::prove`, which loads graph and key for each proof
//!   proofbench resident N [NOTES]    load graph and key once, then N proofs
//!   proofbench interfere N POOL DED  small jobs on the global Rayon pool (POOL threads) while
//!                                    proofs run on that pool (shared) and on a pool of their
//!                                    own with DED threads (dedicated)
//!
//! The global Rayon pool is sized by RAYON_NUM_THREADS (cold, resident) or POOL (interfere).
//! Artifacts are found through CURVY_ZK_KEYS_DIR. The input is the one of the crate's own
//! test `pix_profiles.rs`, with NOTES real notes (default 1, as the exit sweeps) padded to 10.

use std::sync::mpsc;
use std::sync::{
    Arc,
    atomic::{AtomicBool, Ordering},
};
use std::time::{Duration, Instant};

use curvy_core::babyjubjub::BabyJubPoint;
use curvy_core::calldata::bind_calldata;
use curvy_core::eddsa::{ScalarSigningKey, ephemeral_pub_key};
use curvy_core::field::{Bn254Fr, Fr, fr_to_dec};
use curvy_core::imt::{Imt, IndexedMerkleTree};
use curvy_core::witness::{KnownOwner, Note, NoteSigner, Proof};
use curvy_witnesscalc::pix::build_pix_multi_owner_withdrawal;
use curvy_witnesscalc::{Circuit, WitnessCalculator, words};
use num_bigint::BigUint;
use serde_json::Value;

const TREE_DEPTH: usize = 30;
const TOKEN_ID: u64 = 1;

fn scalar_key(value: u64) -> ScalarSigningKey {
    ScalarSigningKey::from_decimal(&value.to_string()).expect("valid test scalar")
}

fn note_for(owner: BabyJubPoint, amount: u64, nonce: u64) -> Note {
    KnownOwner::new(owner, Bn254Fr::from_fr(Fr::from(10_000 + nonce))).note(
        Fr::from(amount),
        Fr::from(TOKEN_ID),
        ephemeral_pub_key(&BigUint::from(20_000 + nonce)),
        Fr::from(nonce & 0xff),
    )
}

/// `real` notes of different owners, padded to 10 with zero-amount slots, bound to its words.
fn withdrawal_input(circuit: &Circuit, real: usize) -> String {
    let keys = (0..real as u64)
        .map(|index| scalar_key(50_000 + index))
        .collect::<Vec<_>>();
    let mut notes = keys
        .iter()
        .enumerate()
        .map(|(index, key)| note_for(*key.verifying_key(), 100 + index as u64, 500 + index as u64))
        .collect::<Vec<_>>();
    let tree = Imt::from_leaves(TREE_DEPTH, &notes.iter().map(Note::id).collect::<Vec<_>>());
    let mut proofs = (0..notes.len())
        .map(|index| {
            let proof = tree.create_proof(index);
            Proof {
                leaf_index: proof.index as u64,
                siblings: proof.siblings,
            }
        })
        .collect::<Vec<_>>();
    let mut signers = keys
        .iter()
        .map(|key| key as &dyn NoteSigner)
        .collect::<Vec<_>>();
    while notes.len() < 10 {
        notes.push(note_for(*keys[0].verifying_key(), 0, 600 + notes.len() as u64));
        proofs.push(Proof {
            leaf_index: 0,
            siblings: vec![Fr::from(0u64); TREE_DEPTH],
        });
        signers.push(&keys[0]);
    }
    let witness = build_pix_multi_owner_withdrawal(
        &notes,
        &signers,
        &proofs,
        tree.root(),
        Fr::from(0xbeefu64),
        Fr::from(TOKEN_ID),
    )
    .expect("withdrawal witness");
    let mut input: Value = serde_json::to_value(&witness).expect("serialize witness");
    let words = words::from_input(circuit.layout, &input).expect("calldata words");
    let binding = bind_calldata(&words).expect("bind calldata words");
    input["x"] = fr_to_dec(&binding.x).into();
    input.to_string()
}

fn rss_mb() -> u64 {
    std::fs::read_to_string("/proc/self/status")
        .ok()
        .and_then(|s| {
            s.lines()
                .find(|l| l.starts_with("VmRSS:"))
                .and_then(|l| l.split_whitespace().nth(1)?.parse::<u64>().ok())
        })
        .unwrap_or(0)
        / 1024
}

fn ms(d: Duration) -> f64 {
    d.as_secs_f64() * 1e3
}

/// About 50 microseconds of arithmetic: stands in for one packet's cryptography.
fn small_job() -> u64 {
    let mut x = 0x9e3779b97f4a7c15u64;
    for i in 0..60_000u64 {
        x = (x ^ i).wrapping_mul(0xbf58476d1ce4e5b9).rotate_left(31);
    }
    std::hint::black_box(x)
}

/// Submits one small job per millisecond to the global pool until `stop`; returns the time
/// each took from submission to completion, in microseconds.
fn probe(stop: Arc<AtomicBool>) -> Vec<u64> {
    let (tx, rx) = mpsc::channel::<u64>();
    let mut sent = 0usize;
    while !stop.load(Ordering::Relaxed) {
        let tx = tx.clone();
        let submitted = Instant::now();
        rayon::spawn_fifo(move || {
            small_job();
            let _ = tx.send(submitted.elapsed().as_micros() as u64);
        });
        sent += 1;
        std::thread::sleep(Duration::from_millis(1));
    }
    drop(tx);
    let mut out: Vec<u64> = rx.iter().collect();
    assert_eq!(out.len(), sent);
    out.sort_unstable();
    out
}

fn report(label: &str, lat: &[u64], proof_ms: &[f64]) {
    let q = |p: f64| lat[((lat.len() - 1) as f64 * p) as usize] as f64 / 1e3;
    let over = |limit: u64| lat.iter().filter(|&&v| v > limit).count();
    let proofs = if proof_ms.is_empty() {
        "-".to_string()
    } else {
        proof_ms
            .iter()
            .map(|v| format!("{v:.0}"))
            .collect::<Vec<_>>()
            .join(",")
    };
    println!(
        "{label:<10} jobs={:<6} p50={:.2}ms p90={:.2}ms p99={:.2}ms max={:.1}ms over10ms={} over100ms={} proof_ms=[{proofs}]",
        lat.len(),
        q(0.5),
        q(0.9),
        q(0.99),
        q(1.0),
        over(10_000),
        over(100_000),
    );
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mode = args.get(1).map(String::as_str).unwrap_or("resident");
    let n: usize = args.get(2).and_then(|v| v.parse().ok()).unwrap_or(5);
    let circuit = Circuit::pix_withdrawal();

    if mode == "interfere" {
        let pool_threads: usize = args.get(3).and_then(|v| v.parse().ok()).unwrap_or(2);
        let dedicated_threads: usize = args.get(4).and_then(|v| v.parse().ok()).unwrap_or(2);
        rayon::ThreadPoolBuilder::new()
            .num_threads(pool_threads)
            .build_global()
            .expect("global pool");
        let dedicated = rayon::ThreadPoolBuilder::new()
            .num_threads(dedicated_threads)
            .build()
            .expect("dedicated pool");
        let input = withdrawal_input(&circuit, 1);
        let calc = circuit.load_calculator().expect("graph");
        let prover = circuit.load_prover().expect("key");
        println!("interfere: global pool {pool_threads} threads, dedicated pool {dedicated_threads} threads, {n} proofs per arm");
        for arm in ["idle", "shared", "dedicated"] {
            let stop = Arc::new(AtomicBool::new(false));
            let handle = {
                let stop = stop.clone();
                std::thread::spawn(move || probe(stop))
            };
            let mut proof_ms = Vec::new();
            match arm {
                "idle" => std::thread::sleep(Duration::from_secs(5)),
                _ => {
                    for _ in 0..n {
                        let started = Instant::now();
                        let assignment = calc.calculate(&input).expect("witness");
                        if arm == "shared" {
                            // As today: called from a thread outside the pool, the proof's
                            // parallel work lands on the global pool.
                            prover.prove_assignment(&assignment).expect("proof");
                        } else {
                            dedicated
                                .install(|| prover.prove_assignment(&assignment))
                                .expect("proof");
                        }
                        proof_ms.push(ms(started.elapsed()));
                    }
                }
            }
            stop.store(true, Ordering::Relaxed);
            let lat = handle.join().expect("probe");
            report(arm, &lat, &proof_ms);
        }
        return;
    }

    let real: usize = args.get(3).and_then(|v| v.parse().ok()).unwrap_or(1);
    let input = withdrawal_input(&circuit, real);
    println!(
        "mode={mode} proofs={n} notes={real} rayon_threads={} cpus={} rss_start={}MB",
        rayon::current_num_threads(),
        std::thread::available_parallelism().map(|v| v.get()).unwrap_or(0),
        rss_mb()
    );
    match mode {
        "cold" => {
            for i in 0..n {
                let started = Instant::now();
                let bundle = circuit.prove(&input).expect("proof");
                println!(
                    "cold {i} total_ms={:.0} signals={} rss={}MB",
                    ms(started.elapsed()),
                    bundle.public_signals.len(),
                    rss_mb()
                );
            }
        }
        "resident" => {
            let started = Instant::now();
            let calc = circuit.load_calculator().expect("graph");
            let graph_ms = ms(started.elapsed());
            let started = Instant::now();
            let prover = circuit.load_prover().expect("key");
            println!(
                "load graph_load_ms={graph_ms:.0} prover_load_ms={:.0} rss={}MB",
                ms(started.elapsed()),
                rss_mb()
            );
            for i in 0..n {
                let started = Instant::now();
                let assignment = calc.calculate(&input).expect("witness");
                let witness_ms = ms(started.elapsed());
                let phase = Instant::now();
                let bundle = prover.prove_assignment(&assignment).expect("proof");
                println!(
                    "resident {i} witness_ms={witness_ms:.0} groth16_ms={:.0} total_ms={:.0} signals={} rss={}MB",
                    ms(phase.elapsed()),
                    ms(started.elapsed()),
                    bundle.public_signals.len(),
                    rss_mb()
                );
            }
        }
        other => panic!("unknown mode {other}"),
    }
}
