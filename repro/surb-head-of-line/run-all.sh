#!/usr/bin/env bash
# Run the three arms of the SURB head-of-line reproduction back to back, then analyse them.
# See README.md. Each arm measures the victim's ping for DUR seconds (default 90).
#
# The attacker's connection to the exit can be slow/flaky to establish after a config swap, so each
# arm waits for a working tunnel and verifies the exit-side condition (drops / no drops). If an arm
# aborts because the attacker did not come up, re-run that arm alone with run-arm.sh.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DUR="${DUR:-90}"
STAMP="$(date -u +%H%M)"

ARMS=(
  "baseline   ping-baseline"
  "contention ping-contention"
  "treatment  ping-treatment"
)

dirs=()
for spec in "${ARMS[@]}"; do
  set -- $spec
  OUT="$HERE/../../results/2026-11-25-surb-head-of-line/$2" "$HERE/run-arm.sh" "$1" "$2" "$DUR"
  dirs+=("$HERE/../../results/2026-11-25-surb-head-of-line/$2")
  sleep 10
done

echo
echo "=== summary ==="
python3 "$HERE/analyze.py" "${dirs[@]}"
