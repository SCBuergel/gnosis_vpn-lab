#!/bin/bash
# One arm of the relay-fault test on vpn-lab (lab 1). Adapted from the vpn-lab2 test of 2026-11-23.
# Usage: arm.sh LABEL fault|control [BASE_S FAIL_S AFTER_S]
# fault:   relay1 drops every packet it sends to the exit (still answers the client) for FAIL_S seconds.
# control: the same timeline with no fault; the "fault" marks are only time marks.
set -u
LABEL=$1 MODE=$2 BASE=${3:-150} FAIL=${4:-480} AFTER=${5:-90} N=9
D=$(cd "$(dirname "$0")" && pwd); OUT=/home/user/vpn-lab/raw/$LABEL; mkdir -p "$OUT"
SSH="ssh -F /home/user/vpn-lab/state/ssh_config -o BatchMode=yes"
C="$SSH lab-client-priv"; R1="$SSH lab-relay1"; X="$SSH lab-exit"
EXIT_PUB=164.92.129.245 EXIT_PRIV=10.114.0.10
NODE=0x7F2665228570F3300973B550754186080283d437
log() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$OUT/phases.txt"; }
unfault() { $R1 "iptables -D OUTPUT -d $EXIT_PUB -j DROP 2>/dev/null; iptables -D OUTPUT -d $EXIT_PRIV -j DROP 2>/dev/null; true"; }
ACCT_IPS="164.92.188.29 10.114.0.2 161.35.223.183 10.114.0.3 167.172.97.202 10.114.0.9 135.181.133.157 213.133.109.149 34.40.106.121 72.18.214.152"
acct_on() { $X "iptables -N RCACCT 2>/dev/null; iptables -F RCACCT; for ip in $ACCT_IPS; do iptables -A RCACCT -s \$ip -j RETURN; done; iptables -C INPUT -j RCACCT 2>/dev/null || iptables -I INPUT -j RCACCT; iptables -Z RCACCT"; }
acct_off() { $X "iptables -D INPUT -j RCACCT 2>/dev/null; iptables -F RCACCT 2>/dev/null; iptables -X RCACCT 2>/dev/null; true"; }
SAMPLER=
trap 'unfault; acct_off; [ -n "$SAMPLER" ] && kill $SAMPLER 2>/dev/null; log "trap: fault removed, accounting off"' EXIT
trap 'exit 130' INT TERM HUP
unfault
cp "$D/config.toml" "$OUT/config.toml"
ctl() { $C "runuser -u gvpnlab -- gnosis_vpn-ctl $*"; }
log "arm $LABEL mode=$MODE N=$N base=$BASE fail=$FAIL after=$AFTER"
START=$(date +%s); echo $START > "$OUT/start"
$C "runuser -u gvpnlab -- gnosis_vpn-ctl disconnect >/dev/null 2>&1; sleep 5; cat > /etc/gnosisvpn/config.toml; systemctl reset-failed gnosisvpn; systemctl restart gnosisvpn; sleep 8; runuser -u gvpnlab -- gnosis_vpn-ctl start-client 60m; sha256sum /usr/bin/gnosis_vpn-worker" < "$OUT/config.toml" >> "$OUT/ctl.txt" 2>&1
for i in $(seq 1 60); do
  m=$(ctl -o json status 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["run_mode"]["type"])' 2>/dev/null)
  [ "$m" = running ] && break; sleep 5; done
log "worker run_mode=$m"
[ "$m" = running ] || { log "ABORT: worker not running"; exit 2; }
for i in $(seq 1 80); do
  o=$(cd $D && python3 nodechan.py $NODE 2>/dev/null | head -1 | awk '{print $5}')
  [ "${o:-0}" -ge "$N" ] && break; sleep 15; done
log "open channels: $o"
[ "${o:-0}" -ge "$N" ] || { log "ABORT: fewer than $N channels"; exit 2; }
(cd $D && python3 nodechan.py $NODE) > "$OUT/channels.txt" 2>&1
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
  # The client can fail to record a made deposit (hopr-strategy 9.2.x). Trust the exit's confirmation instead.
  $X "journalctl -u hoprd --since @$START --no-pager | grep -q 'ssa deposit confirmed'" && log "exit confirmed the deposit; client state does not show it" || { log "ABORT: no paid chunk"; exit 2; }
fi
$C "curl -s -m 120 -o /dev/null -w '%{size_download} %{time_total}\n' -r 0-5000000 http://deb.debian.org/debian/dists/stable/main/Contents-all.gz" > "$OUT/warmup.txt" 2>&1
log "warm-up 5 MB: $(cat $OUT/warmup.txt)"
TOTAL=$((BASE+FAIL+AFTER+30))
$C "mkdir -p /root/exp; rm -f /root/exp/$LABEL.*; nohup timeout $TOTAL ping -D -i 0.2 -W 2 1.1.1.1 > /root/exp/$LABEL.ping 2>&1 &
 nohup timeout $TOTAL sh -c 'while true; do echo \"\$(date +%s) \$(curl -s -m 50 -o /dev/null -w \"%{size_download} %{time_total}\" -r 0-2000000 http://deb.debian.org/debian/dists/stable/main/Contents-all.gz)\"; sleep 30; done' > /root/exp/$LABEL.curl 2>&1 &"
acct_on
( while true; do t=$(date +%s); $X "iptables -L RCACCT -v -x -n" | awk -v t=$t '$3=="RETURN"{print t, $8, $1}' >> "$OUT/exit-acct.txt"; sleep 15; done ) &
SAMPLER=$!
log "baseline start"; sleep $BASE
[ "$MODE" = fault ] && $R1 "iptables -I OUTPUT -d $EXIT_PUB -j DROP; iptables -I OUTPUT -d $EXIT_PRIV -j DROP"
T0=$(date +%s); echo "$T0" > "$OUT/t0"
[ "$MODE" = fault ] && log "FAULT ON t0=$T0" || log "CONTROL MARK (no fault) t0=$T0"
end=$((T0+FAIL))
while [ $(date +%s) -lt $end ]; do
  echo "$(date +%s) $($R1 "iptables -L OUTPUT -v -x -n | awk '/DROP/{s+=\$1} END{print s+0}'")" >> "$OUT/drops.txt"; sleep 15; done
unfault; T1=$(date +%s); echo $T1 > "$OUT/t1"
[ "$MODE" = fault ] && log "FAULT OFF t1=$T1" || log "CONTROL MARK END t1=$T1"
sleep $AFTER
log "after done"; sleep 35
for f in ping curl; do $C "cat /root/exp/$LABEL.$f" > "$OUT/$f.txt"; done
ctl -o json status > "$OUT/status-end.json" 2>&1
ctl disconnect >> "$OUT/ctl.txt" 2>&1
kill $SAMPLER 2>/dev/null; SAMPLER=; acct_off
sleep 8; END=$(date +%s); echo $END > "$OUT/end"
DAY=$(date -u +%F)
$SSH lab-client "cat /home/gvpnlab/.local/state/gnosisvpn/worker.log.$DAY" 2>/dev/null | awk -v a="$(date -u -d @$START +%FT%T)" '$1>=a' > "$OUT/client-worker.full.log" || true
[ -s "$OUT/client-worker.full.log" ] || $C "cat /home/gvpnlab/.local/state/gnosisvpn/worker.log.$DAY" | awk -v a="$(date -u -d @$START +%FT%T)" '$1>=a' > "$OUT/client-worker.full.log"
for h in exit relay1 relay2 relay3; do
  u="-u hoprd"; [ $h = exit ] && u="-u hoprd -u gnosisvpn-server"
  $SSH lab-$h "journalctl $u --since @$START --until @$END --utc -o short-iso-precise --no-pager" > "$OUT/$h.full.log" 2>&1; done
log "ARM DONE $LABEL"
