#!/usr/bin/env bash
# One arm of the PR #8763 before/after test (see README.md).
#
# Two Gnosis VPN clients share one exit. The VICTIM is a normal client: it pings through the tunnel
# and fetches a small HTTPS page once a second. The ATTACKER is absent (quiet), downloads with its
# bridge session at client defaults (control), or downloads with a bridge session that runs out of
# SURBs on the exit (starved; the shape of hoprnet#8753).
#
# Usage: run-arm.sh <quiet|control|starved> <output-dir> [duration_s]
set -euo pipefail

ARM="${1:?usage: run-arm.sh <quiet|control|starved> <output-dir> [duration_s]}"
OUT="${2:?missing output dir}"
DUR="${3:-180}"

HERE="$(cd "$(dirname "$0")" && pwd)"
LAB="${LAB:-$(cd "$HERE/../.." && pwd)}"
SSH="ssh -F $LAB/state/ssh_config -o BatchMode=yes"
VICTIM_SSH="${VICTIM_SSH:-$SSH lab-client-priv}"
ATTACKER_SSH="${ATTACKER_SSH:-$SSH lab-client2-priv}"
EXIT_SSH="${EXIT_SSH:-$SSH lab-exit}"
DEST="${DEST:-lab}"
IF="${IF:-wg0_gnosisvpn}"
ATTACKER_BUILD="${ATTACKER_BUILD:-/root/lab/control-main-5d902a6}"   # a client build that accepts the retransmission capability
DL_URL="${DL_URL:-https://ams.download.datapacket.com/10000mb.bin}"
DL_HOST="$(printf '%s' "$DL_URL" | sed -E 's#^https?://([^/]+)/.*#\1#')"
# The download host is pinned to one IPv4 address: the clients' stub resolver does not work through the tunnel.
DL_IP="${DL_IP:-$(getent ahostsv4 "$DL_HOST" | awk '{print $1; exit}')}"
EXIT_IP="$(python3 -c "import json;print(json.load(open('$LAB/state/inventory.json'))['exit']['public'])")"

ctl() { local host="$1"; shift; $host "runuser -u gvpnlab -- gnosis_vpn-ctl $*"; }
connected() { $1 "runuser -u gvpnlab -- gnosis_vpn-ctl -o json status" 2>/dev/null | grep -q '"connected"'; }
iface_up() { [ -n "$($1 "ip -o link show 2>/dev/null | grep -o '$IF' | head -1")" ]; }
# The address a client's traffic leaves from: the exit's when the tunnel carries it.
egress() { $1 "curl -4 -s -m 8 https://1.1.1.1/cdn-cgi/trace | sed -n 's/^ip=//p'" 2>/dev/null || true; }

# Connect a client and wait for a tunnel that carries traffic. After a restart of the exit or a change
# of configuration a client can report "connected" without an interface; restarting its service fixes it.
bring_up() {
  local host="$1" who="$2" i
  for i in $(seq 1 50); do
    if connected "$host" && iface_up "$host" && [ "$(egress "$host")" = "$EXIT_IP" ]; then return 0; fi
    if [ "$i" = 1 ] || [ $((i % 12)) = 0 ]; then
      [ "$i" = 1 ] || $host "systemctl restart gnosisvpn; sleep 4" || true
      ctl "$host" "start-client 120m" >/dev/null 2>&1 || true
      ctl "$host" "connect $DEST" >/dev/null 2>&1 || true
    fi
    sleep 6
  done
  echo "ERROR: $who has no working tunnel through the exit" >&2
  return 3
}

mkdir -p "$OUT"
ATTACKER_LOADED=n/a
echo "$(date -u +%FT%TZ) arm=$ARM dur=${DUR}s out=$OUT"

# --- attacker ------------------------------------------------------------------------------------
$ATTACKER_SSH "systemctl stop atk-dl 2>/dev/null || true"
ctl "$ATTACKER_SSH" "disconnect" >/dev/null 2>&1 || true
if [ "$ARM" != "quiet" ]; then
  case "$ARM" in
    control) acfg=attacker-default.toml ;;
    starved) acfg=attacker-retx.toml ;;
    *) echo "unknown arm $ARM" >&2; exit 2 ;;
  esac
  ctl "$ATTACKER_SSH" "stop-client" >/dev/null 2>&1 || true
  $ATTACKER_SSH "cat > /etc/gnosisvpn/config.toml" < "$HERE/configs/$acfg"
  $ATTACKER_SSH "for b in root worker ctl; do install -m 755 $ATTACKER_BUILD/gnosis_vpn-\$b /usr/bin/gnosis_vpn-\$b; done
    systemctl restart gnosisvpn; sleep 4"
  bring_up "$ATTACKER_SSH" attacker
  # A download that outlives this SSH call, bound to the tunnel interface.
  $ATTACKER_SSH "systemd-run --unit=atk-dl --collect bash -c \
    'while true; do curl -4 -s --interface $IF --resolve ${DL_HOST}:443:${DL_IP} -o /dev/null -m 120 $DL_URL; done'" >/dev/null 2>&1
  # Measure only once the download really runs: a new session is held back around 13 MB until its
  # first payment is visible, and an arm measured during that hold has an idle attacker.
  ATTACKER_LOADED=no
  start=$($ATTACKER_SSH "cat /sys/class/net/$IF/statistics/rx_bytes"); last=$start
  for i in $(seq 1 40); do
    sleep 10
    now=$($ATTACKER_SSH "cat /sys/class/net/$IF/statistics/rx_bytes 2>/dev/null || echo 0")
    if [ $((now - start)) -ge 40000000 ] && [ $((now - last)) -ge 2500000 ]; then ATTACKER_LOADED=yes; break; fi
    last=$now
  done
  echo "attacker download running: $ATTACKER_LOADED ($(( (now - start) / 1000000 )) MB so far)"
fi

# --- victim --------------------------------------------------------------------------------------
bring_up "$VICTIM_SSH" victim
rx() { $ATTACKER_SSH "cat /sys/class/net/$IF/statistics/rx_bytes 2>/dev/null || echo 0"; }
RX0=0; [ "$ARM" = "quiet" ] || RX0=$(rx)
T0=$(date +%s)
echo "$(date -u +%FT%TZ) measuring from the victim for ${DUR}s"
$VICTIM_SSH "rm -f /tmp/http.txt
  ( end=\$((SECONDS+$DUR)); while [ \$SECONDS -lt \$end ]; do s=\$(date +%s.%N)
      r=\$(curl -4 -s -o /dev/null -m 10 -w '%{time_total} %{http_code}' https://1.1.1.1/cdn-cgi/trace)
      echo \"\$s \$r\"; sleep 1; done ) > /tmp/http.txt 2>&1 &
  ping -D -i 0.3 -W 2 -w $DUR 1.1.1.1; wait" > "$OUT/ping.txt" 2>&1 || true
T1=$(date +%s)
RX1=0; [ "$ARM" = "quiet" ] || RX1=$(rx)
$VICTIM_SSH "cat /tmp/http.txt" > "$OUT/http.txt"
VICTIM_EGRESS="$(egress "$VICTIM_SSH")"

# --- collect -------------------------------------------------------------------------------------
$EXIT_SSH "journalctl -u hoprd --since @$T0 --until @$T1 --no-pager -o short-iso-precise | sed -E 's/\x1b\[[0-9;]*m//g' \
  | grep -E 'no SURB|waiting for a SURB|dispatch took too long' | gzip" > "$OUT/exit-surb.log.gz" || true
EXIT_BUILD="$($EXIT_SSH "echo \$(hoprd --version) \$(sha256sum /usr/local/bin/hoprd | cut -c1-16)")"
[ "$ARM" = "quiet" ] || $ATTACKER_SSH "systemctl stop atk-dl 2>/dev/null || true"
python3 - "$ARM" "$DUR" "$T0" "$T1" "$RX0" "$RX1" "$EXIT_BUILD" "$VICTIM_EGRESS" "$EXIT_IP" "$ATTACKER_LOADED" > "$OUT/arm-meta.json" <<'PY'
import sys, json, datetime
arm, dur, t0, t1, rx0, rx1, build, egress, exit_ip, loaded = sys.argv[1:]
t0, t1 = int(t0), int(t1)
print(json.dumps({
    "arm": arm, "duration_s": int(dur), "exit_build": build,
    "window_utc": [datetime.datetime.fromtimestamp(t, datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ") for t in (t0, t1)],
    "attacker_download_mbit_s": round((int(rx1) - int(rx0)) * 8 / 1e6 / max(1, t1 - t0), 2),
    "attacker_download_running_before_measurement": loaded,
    "victim_egress_is_exit": egress == exit_ip,
}, indent=1))
PY
echo "$(date -u +%FT%TZ) arm $ARM done"
