#!/usr/bin/env bash
# The whole test: for each exit build in turn, the three arms. See README.md.
# Usage: run-all.sh <results-dir> <build> [<build> ...]     e.g. run-all.sh ../../results/x stock src pr8763
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RESULTS="${1:?usage: run-all.sh <results-dir> <build>...}"; shift
DUR="${DUR:-180}"
for build in "$@"; do
  "$HERE/set-exit-build.sh" "${build%%-*}" || { echo "cannot install build $build" >&2; exit 1; }
  sleep 120   # the exit rejoins the network; each arm then waits for working tunnels
  for arm in quiet control starved; do
    out="$RESULTS/$build-$arm"
    "$HERE/run-arm.sh" "$arm" "$out" "$DUR" || { echo "retrying $build-$arm"; "$HERE/run-arm.sh" "$arm" "$out" "$DUR" || echo "FAILED $build-$arm"; }
  done
done
echo; python3 "$HERE/analyze.py" "$RESULTS"/*-quiet "$RESULTS"/*-control "$RESULTS"/*-starved
