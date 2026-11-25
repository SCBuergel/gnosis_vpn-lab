#!/usr/bin/env bash
# The victim pings through the tunnel while the second client connects and disconnects three times,
# with no traffic of its own. The exit's per-thread CPU time is sampled every 0.1 s. See README.md.
# Usage: run.sh <output-dir>
set -uo pipefail
OUT="${1:?usage: run.sh <output-dir>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
LAB="${LAB:-$(cd "$HERE/../.." && pwd)}"
S="ssh -F $LAB/state/ssh_config -o BatchMode=yes"
EXIT_IP="$(python3 -c "import json;print(json.load(open('$LAB/state/inventory.json'))['exit']['public'])")"
ctl() { $S "$1" "runuser -u gvpnlab -- gnosis_vpn-ctl $2" >/dev/null 2>&1 || true; }
mkdir -p "$OUT"; : > "$OUT/events.txt"
$S lab-exit "cat > /root/lab/threads.py" < "$HERE/threads.py"
ctl lab-client2-priv disconnect
ctl lab-client-priv "start-client 120m"; ctl lab-client-priv "connect lab"
for i in $(seq 1 50); do
  [ "$($S lab-client-priv "curl -4 -s -m 8 https://1.1.1.1/cdn-cgi/trace | sed -n 's/^ip=//p'" 2>/dev/null)" = "$EXIT_IP" ] && break
  [ $((i % 12)) = 0 ] && { $S lab-client-priv "systemctl restart gnosisvpn; sleep 4"; ctl lab-client-priv "start-client 120m"; ctl lab-client-priv "connect lab"; }
  sleep 6
done
sleep 15
T0=$(date +%s)
$S lab-exit "python3 /root/lab/threads.py \$(pidof hoprd) 150" > "$OUT/threads.txt" &
$S lab-client-priv "ping -D -i 0.2 -W 3 -w 150 1.1.1.1" > "$OUT/ping.txt" 2>&1 &
sleep 20
for n in 1 2 3; do
  echo "connect $n $(date +%s.%N)" >> "$OUT/events.txt"
  ctl lab-client2-priv "start-client 120m"; ctl lab-client2-priv "connect lab"
  sleep 28
  echo "disconnect $n $(date +%s.%N)" >> "$OUT/events.txt"
  ctl lab-client2-priv disconnect
  sleep 12
done
wait
T1=$(date +%s)
$S lab-exit "journalctl -u hoprd --since @$T0 --until @$T1 --no-pager -o short-iso-precise | sed -E 's/\x1b\[[0-9;]*m//g' \
  | grep -E 'SSA batch|fully committed for verification|no SURB|new session established|session closed session_id' | gzip" > "$OUT/exit.log.gz"
$S lab-exit "echo \$(hoprd --version) \$(sha256sum /usr/local/bin/hoprd | cut -c1-16) cpu_threads=\$(sed -n 's/^HOPRD_NUM_CPU_THREADS=//p' /etc/hoprd/hoprd.env | grep . || echo default) vcpu=\$(nproc)" > "$OUT/exit-build.txt"
cat "$OUT/exit-build.txt"; tail -2 "$OUT/ping.txt"
