#!/usr/bin/env bash
# For each finished arm, fetch the exit's log lines about sessions opening and closing in the arm's
# window (from the exit's journal, which outlives hoprd restarts) into <arm>/exit-sessions.log.gz.
# Usage: collect-session-events.sh ARM_DIR [ARM_DIR ...]
set -euo pipefail
LAB="${LAB:-$(cd "$(dirname "$0")/../.." && pwd)}"
EXIT_SSH="${EXIT_SSH:-ssh -F $LAB/state/ssh_config -o BatchMode=yes lab-exit}"
for dir in "$@"; do
  read -r t0 t1 < <(python3 -c "
import json, sys, datetime
w = json.load(open(sys.argv[1] + '/arm-meta.json'))['window_utc']
print(*(int(datetime.datetime.fromisoformat(t.replace('Z', '+00:00')).timestamp()) for t in w))" "$dir")
  $EXIT_SSH "journalctl -u hoprd --since @$t0 --until @$t1 --no-pager -o short-iso-precise | sed -E 's/\x1b\[[0-9;]*m//g' \
    | grep -E 'new session established|session closed session_id|pix supervisor closed the session|closing PIX SSA' | gzip" \
    > "$dir/exit-sessions.log.gz"
  echo "$dir: $(zcat "$dir/exit-sessions.log.gz" | wc -l) session events"
done
