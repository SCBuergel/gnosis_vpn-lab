#!/bin/bash
# Diagnosis for the ladder result: relay 1 cut alone, then relay 1 cut after the 6 public relays.
# The cut is made on the exit: it drops every packet arriving from that relay (the relay still answers the client).
# Order: the 6 public relays, then lab relay 1 and 2; lab relay 3 stays. Then all cuts are removed.
# Usage: ladder.sh LABEL BUILD [HOLD_S]
# BUILD:   a directory /root/lab/BUILD on the client holding gnosis_vpn-{root,worker,ctl}; installed first.
# fault:   relay1 drops every packet it sends to the exit (still answers the client) for FAIL_S seconds.
# control: the same timeline with no fault; the "fault" marks are only time marks.
set -u
LABEL=$1 BUILD=$2 HOLD=${3:-300} N=9 MODE=ladder BASE=120 FAIL=810 AFTER=120
D=$(cd "$(dirname "$0")" && pwd); LAB=$(cd "$D/../.." && pwd); OUT=$LAB/raw/$LABEL; mkdir -p "$OUT"
SSH="ssh -F $LAB/state/ssh_config -o BatchMode=yes"
C="$SSH lab-client-priv"; R1="$SSH lab-relay1"; X="$SSH lab-exit"
EXIT_PUB=64.225.79.193 EXIT_PRIV=10.110.0.5
log() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$OUT/phases.txt"; }
# name:address:match on the exit's INPUT chain (several matches separated by ';')
STEPS="pub-880f:0x880f8bef:-s 135.181.133.157 -p udp --sport 11101
pub-dac8:0xdac87d21:-s 213.133.109.149 -p udp --sport 9093
pub-1388:0x1388e447:-s 34.40.106.121
pub-d880:0xd88064f7:-s 135.181.133.157 -p udp --sport 11102
pub-5b7b:0x5b7b57c7:-s 213.133.109.149 -p udp --sport 9098
pub-0d38:0x0d38ffed:-s 72.18.214.152 -p udp --sport 9090
relay1:0xc67e2d03:-s 167.71.70.24;-s 10.110.0.2
relay2:0x6cefd8bf:-s 188.166.6.48;-s 10.110.0.3"
unfault() { $X "iptables -D INPUT -j LADDER 2>/dev/null; iptables -F LADDER 2>/dev/null; iptables -X LADDER 2>/dev/null; true"; }
trap 'unfault; log "trap: fault removed"' EXIT
trap 'exit 130' INT TERM HUP
unfault
cp "$D/config.toml" "$OUT/config.toml"
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
TOTAL=$((BASE+FAIL+AFTER+30))
$C "mkdir -p /root/exp; rm -f /root/exp/$LABEL.*; nohup timeout $TOTAL ping -D -i 0.2 -W 2 1.1.1.1 > /root/exp/$LABEL.ping 2>&1 &
 nohup timeout $TOTAL sh -c 'while true; do echo \"\$(date +%s) \$(curl -s -m 50 -o /dev/null -w \"%{size_download} %{time_total}\" -r 0-2000000 http://deb.debian.org/debian/dists/stable/main/Contents-all.gz)\"; sleep 30; done' > /root/exp/$LABEL.curl 2>&1 &" < /dev/null > /dev/null 2>&1
$X "iptables -N LADDER; iptables -I INPUT -j LADDER"
PUB="iptables -A LADDER -s 135.181.133.157 -p udp --sport 11101 -j DROP; iptables -A LADDER -s 213.133.109.149 -p udp --sport 9093 -j DROP; iptables -A LADDER -s 34.40.106.121 -j DROP; iptables -A LADDER -s 135.181.133.157 -p udp --sport 11102 -j DROP; iptables -A LADDER -s 213.133.109.149 -p udp --sport 9098 -j DROP; iptables -A LADDER -s 72.18.214.152 -p udp --sport 9090 -j DROP"
R1CUT="iptables -A LADDER -s 167.71.70.24 -j DROP; iptables -A LADDER -s 10.110.0.2 -j DROP"
step() { t=$(date +%s); echo "$t $1 - $2" >> "$OUT/steps.txt"; log "STEP $1 t=$t relays left: $2"; }
log "baseline start"; sleep 120
T0=$(date +%s); echo "$T0" > "$OUT/t0"
$X "$R1CUT" < /dev/null; step "cut relay1 only" 8; sleep 240
$X "iptables -F LADDER" < /dev/null; step "cut removed" 9; sleep 150
$X "$PUB" < /dev/null; step "cut the 6 public relays" 3; sleep 180
$X "$R1CUT" < /dev/null; step "cut relay1 too" 2; sleep 240
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
for h in exit relay1 relay2 relay3; do
  u="-u hoprd"; [ $h = exit ] && u="-u hoprd -u gnosisvpn-server"
  $SSH lab-$h "journalctl $u --since @$START --until @$END --utc -o short-iso-precise --no-pager" > "$OUT/$h.full.log" 2>&1; done
log "ARM DONE $LABEL"
