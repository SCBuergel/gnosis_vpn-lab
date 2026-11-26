#!/bin/bash
# Sudden outages on vpn-lab3: n relays are cut off from the exit at once (n = 1 .. 8), held HOLD seconds,
# then all 9 are restored for HOLD seconds before the next, larger cut.
# The cut is made on the exit: it drops every packet arriving from that relay (the relay still answers the client).
# All 9 relays are lab machines and the exit has channels to all of them. Order: relay1 .. relay8; relay9 stays.
# Then all cuts are removed. The client is the lab's second client (CLIENT_HOST, default client2).
# Usage: brutal9.sh LABEL BUILD [HOLD_S]
# BUILD:   a directory /root/lab/BUILD on the client holding gnosis_vpn-{root,worker,ctl}; installed first.
# Before running: raw/ must not hold a folder LABEL; the client needs both builds and a funded Safe
# (a connect buys a 5.94 wxHOPR chunk; a pool top-up takes 35.35 wxHOPR).
set -u
LABEL=$1 BUILD=$2 HOLD=${3:-300} N=9 MODE=sudden BASE=$HOLD FAIL=$((15*HOLD)) AFTER=$HOLD
D=$(cd "$(dirname "$0")" && pwd); LAB=$(cd "$D/../.." && pwd); OUT=$LAB/raw/$LABEL; mkdir -p "$OUT"
SSH="ssh -F $LAB/state/ssh_config -o BatchMode=yes"
C="$SSH lab-${CLIENT_HOST:-client2}-priv"; X="$SSH lab-exit"
log() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$OUT/phases.txt"; }
# name:address:match on the exit's INPUT chain (several matches separated by ';')
# Built from the lab state: relay1 .. relay8 are cut in that order, relay9 stays.
STEPS=$(python3 - "$LAB" <<'PY'
import json, sys
lab = sys.argv[1]
inv = json.load(open(lab + "/state/inventory.json")); nodes = json.load(open(lab + "/state/nodes.json"))
for i in range(1, 9):
    n = f"relay{i}"
    print(f"{n}:{nodes[n]['address'][:10]}:-s {inv[n]['public']};-s {inv[n]['private']}")
PY
)
unfault() { $X "iptables -D INPUT -j LADDER 2>/dev/null; iptables -F LADDER 2>/dev/null; iptables -X LADDER 2>/dev/null; true"; }
trap 'unfault; log "trap: fault removed"' EXIT
trap 'exit 130' INT TERM HUP
unfault
cp "$D/${CONFIG:-config-9lab.toml}" "$OUT/config.toml"
ctl() { $C "runuser -u gvpnlab -- gnosis_vpn-ctl $*"; }
log "arm $LABEL mode=$MODE build=$BUILD N=$N base=$BASE fail=$FAIL after=$AFTER"
START=$(date +%s); echo $START > "$OUT/start"
$C "runuser -u gvpnlab -- gnosis_vpn-ctl disconnect >/dev/null 2>&1; sleep 5; cat > /etc/gnosisvpn/config.toml; systemctl stop gnosisvpn; sleep 2
 for b in root worker ctl; do install -m 755 /root/lab/$BUILD/gnosis_vpn-\$b /usr/bin/gnosis_vpn-\$b || exit 3; done
 systemctl reset-failed gnosisvpn; systemctl start gnosisvpn; sleep 8; runuser -u gvpnlab -- gnosis_vpn-ctl start-client 60m; sha256sum /usr/bin/gnosis_vpn-worker" < "$OUT/config.toml" >> "$OUT/ctl.txt" 2>&1
log "worker $(tail -1 "$OUT/ctl.txt" | cut -c1-16)"
for i in $(seq 1 60); do
  m=$(ctl -o json status 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["run_mode"]["type"])' 2>/dev/null)
  [ "$m" = running ] && break; sleep 5; done
log "worker run_mode=$m"
[ "$m" = running ] || { log "ABORT: worker not running"; exit 2; }
chans() { ctl -o json balance 2>/dev/null | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["data"]["channels_out"]))' 2>/dev/null; }
for i in $(seq 1 80); do o=$(chans); [ "${o:-0}" -ge "$N" ] && break; sleep 15; done
log "open channels: $o"
[ "${o:-0}" -ge "$N" ] || { log "ABORT: fewer than $N channels"; exit 2; }
ctl -o json balance > "$OUT/channels.json" 2>&1
sleep 60   # let the planner see the full relay set
ctl connect lab >> "$OUT/ctl.txt" 2>&1
log "connect sent"
for i in $(seq 1 120); do
  $C "ip route get 1.1.1.1 | grep -q wg && ping -c1 -W2 1.1.1.1 >/dev/null" && break; sleep 3; done
log "tunnel after ~$((i*3)) s"
# No user traffic before the first paid chunk: past the exit's ~13 MB free allowance the payment can deadlock.
pix() { ctl -o json status | python3 -c 'import sys,json;p=json.load(sys.stdin)["data"]["connection"].get("pix") or {};print(p.get("chunks_paid") or 0, p.get("phase"), "failed", p.get("chunks_failed"))'; }
for i in $(seq 1 36); do p=$(pix 2>/dev/null); [ "${p%% *}" -ge 1 ] 2>/dev/null && break; sleep 5; done
log "pix after ~$((i*5)) s: paid $p"
if ! [ "${p%% *}" -ge 1 ] 2>/dev/null; then
  $X "journalctl -u hoprd --since @$START --no-pager | grep -q 'ssa deposit confirmed'" && log "exit confirmed the deposit; client state does not show it" || { log "ABORT: no paid chunk"; exit 2; }
fi
$C "curl -s -m 120 -o /dev/null -w '%{size_download} %{time_total}\n' -r 0-5000000 http://deb.debian.org/debian/dists/stable/main/Contents-all.gz" > "$OUT/warmup.txt" 2>&1
log "warm-up 5 MB: $(cat $OUT/warmup.txt)"
# 120 s of slack: every step overruns by a few seconds, and the ping must cover the last one.
TOTAL=$((BASE+FAIL+AFTER+120)); log "load total=$TOTAL"
$C "mkdir -p /root/exp; rm -f /root/exp/$LABEL.*; nohup timeout $TOTAL ping -D -i 0.2 -W 2 1.1.1.1 > /root/exp/$LABEL.ping 2>&1 &
 nohup timeout $TOTAL sh -c 'while true; do echo \"\$(date +%s) \$(curl -s -m 50 -o /dev/null -w \"%{size_download} %{time_total}\" -r 0-2000000 http://deb.debian.org/debian/dists/stable/main/Contents-all.gz)\"; sleep 30; done' > /root/exp/$LABEL.curl 2>&1 &" < /dev/null > /dev/null 2>&1
$X "iptables -N LADDER; iptables -I INPUT -j LADDER"
log "baseline start"; sleep $HOLD
T0=$(date +%s); echo "$T0" > "$OUT/t0"
mapfile -t RULES <<< "$STEPS"
for n in 1 2 3 4 5 6 7 8; do
  cmd=""
  for i in $(seq 0 $((n-1))); do
    IFS=';' read -ra ms <<< "${RULES[$i]##*:}"; for m in "${ms[@]}"; do cmd="$cmd iptables -A LADDER $m -j DROP;"; done
  done
  $X "$cmd" < /dev/null
  t=$(date +%s); echo "$t cut relay1..relay$n - $((9-n))" >> "$OUT/steps.txt"
  log "CUT relay1..relay$n at once t=$t relays left: $((9-n))"
  end=$((t+HOLD))
  while [ $(date +%s) -lt $end ]; do
    echo "$(date +%s) $($X "iptables -L LADDER -v -x -n | awk 'NR>2{printf \"%s \", \$1}'" < /dev/null)" >> "$OUT/drops.txt"; sleep 15; done
  if [ $n -lt 8 ]; then
    $X "iptables -F LADDER" < /dev/null
    t=$(date +%s); echo "$t restored after $n - 9" >> "$OUT/steps.txt"
    log "RESTORED all 9 t=$t"; sleep $HOLD
  fi
done
unfault; T1=$(date +%s); echo $T1 > "$OUT/t1"
log "ALL CUTS REMOVED t1=$T1"
sleep $AFTER
log "after done"; sleep 35
for f in ping curl; do $C "cat /root/exp/$LABEL.$f" > "$OUT/$f.txt"; done
ctl -o json status > "$OUT/status-end.json" 2>&1
ctl disconnect >> "$OUT/ctl.txt" 2>&1
sleep 8; END=$(date +%s); echo $END > "$OUT/end"
DAY=$(date -u +%F)
$C "cat /home/gvpnlab/.local/state/gnosisvpn/worker.log.$DAY" | awk -v a="$(date -u -d @$START +%FT%T)" '$1>=a' > "$OUT/client-worker.full.log"
for h in exit relay1 relay2 relay3 relay4 relay5 relay6 relay7 relay8 relay9; do
  u="-u hoprd"; [ $h = exit ] && u="-u hoprd -u gnosisvpn-server"
  $SSH lab-$h "journalctl $u --since @$START --until @$END --utc -o short-iso-precise --no-pager" > "$OUT/$h.full.log" 2>&1; done
log "ARM DONE $LABEL"
