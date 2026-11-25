#!/usr/bin/env bash
# One arm of the SURB head-of-line reproduction (see README.md).
#
# It measures ONE victim client's ping latency through the tunnel while an ATTACKER client is either
# absent (baseline), downloading without bridge retransmission (contention control), or downloading
# with bridge retransmission (treatment). Both clients connect to the SAME exit and share its routing
# resolve stage. The attacker's retransmission starves its bridge session's SURBs on the exit; the
# question is whether that stalls the victim's traffic.
#
# Why ping, not a download, for the victim: each echo reply forces the exit to ORIGINATE a return
# packet to the victim, which is exactly what the head-of-line stall withholds — but a ping does not
# compete for the exit's bandwidth, so it isolates the stall from ordinary contention. (A second bulk
# download does not work as a probe: on a small exit two concurrent downloads collapse each other via
# bandwidth/PIX-deposit limits regardless of retransmission, masking the effect.)
#
# Everything is driven over SSH from this host. Roles are set by the environment variables below.
set -euo pipefail

ARM="${1:?usage: run-arm.sh <baseline|contention|treatment> <label> [duration_s]}"
LABEL="${2:?missing label}"
DUR="${3:-90}"

HERE="$(cd "$(dirname "$0")" && pwd)"
CFG="$HERE/configs"
OUT="${OUT:-$HERE/../../results/2026-11-25-surb-head-of-line/$LABEL}"

VICTIM_SSH="${VICTIM_SSH:-ssh -F /home/user/vpn-lab/state/ssh_config lab-client-priv}"
VICTIM_IF="${VICTIM_IF:-wg0_gnosisvpn}"
VICTIM_DEST="${VICTIM_DEST:-lab2exit}"
ATTACKER_SSH="${ATTACKER_SSH:-ssh -F /home/user/vpn-lab2/state/ssh_config lab-client-priv}"
ATTACKER_BUILD="${ATTACKER_BUILD:-/root/lab/control-main-5d902a6}"  # a build that accepts the retransmission capability
ATTACKER_DEST="${ATTACKER_DEST:-lab2exit}"
ATTACKER_IF="${ATTACKER_IF:-wg0_gnosisvpn}"
EXIT_SSH="${EXIT_SSH:-ssh -F /home/user/vpn-lab2/state/ssh_config lab-exit}"

DL_URL="${DL_URL:-https://nyc.download.datapacket.com/10000mb.bin}"
DL_HOST="$(printf '%s' "$DL_URL" | sed -E 's#^https?://([^/]+)/.*#\1#')"
# Pin the download host to one IPv4: the clients' in-tunnel DNS does not resolve through the tunnel.
DL_IP="${DL_IP:-$(getent ahostsv4 "$DL_HOST" | awk '{print $1; exit}')}"

actl() { $ATTACKER_SSH "runuser -u gvpnlab -- gnosis_vpn-ctl $*"; }
a_connected() { $ATTACKER_SSH "runuser -u gvpnlab -- gnosis_vpn-ctl -o json status" 2>/dev/null | grep -q '"connected"'; }
a_iface_up() { [ -n "$($ATTACKER_SSH "ip -o link show 2>/dev/null | grep -o '$ATTACKER_IF' | head -1")" ]; }

mkdir -p "$OUT"
echo "$(date -u +%FT%TZ) arm=$ARM label=$LABEL dur=${DUR}s  download $DL_HOST -> $DL_IP"

# --- attacker setup ------------------------------------------------------------------------------
$ATTACKER_SSH "systemctl stop atk-dl 2>/dev/null || true"   # stop any prior load
if [ "$ARM" = "baseline" ]; then
  actl "disconnect" >/dev/null 2>&1 || true
  actl "stop-client" >/dev/null 2>&1 || true
else
  case "$ARM" in
    contention) acfg=attacker-noretx.toml ;;
    treatment)  acfg=attacker-retx.toml ;;
    *) echo "unknown arm $ARM" >&2; exit 2 ;;
  esac
  echo "attacker: build $(basename "$ATTACKER_BUILD"), config $acfg"
  actl "disconnect" >/dev/null 2>&1 || true
  actl "stop-client" >/dev/null 2>&1 || true
  cat "$CFG/$acfg" | $ATTACKER_SSH "cat > /etc/gnosisvpn/config.toml" || true
  $ATTACKER_SSH "for b in root worker ctl; do install -m 755 $ATTACKER_BUILD/gnosis_vpn-\$b /usr/bin/gnosis_vpn-\$b; done
    systemctl restart gnosisvpn; sleep 4" || true
  actl "start-client 120m" >/dev/null 2>&1 || true
  actl "connect $ATTACKER_DEST" >/dev/null 2>&1 || true
  # Wait for a WORKING data plane: connected AND the tunnel interface actually up. After a config
  # swap the client can report "connected" for minutes with no interface; a worker restart fixes it.
  ok=0
  for i in $(seq 1 40); do
    if a_connected && a_iface_up; then ok=1; break; fi
    if [ "$i" = 12 ] || [ "$i" = 24 ]; then          # kick a stuck connection
      $ATTACKER_SSH "systemctl restart gnosisvpn; sleep 4" || true
      actl "start-client 120m" >/dev/null 2>&1 || true
      actl "connect $ATTACKER_DEST" >/dev/null 2>&1 || true
    fi
    sleep 6
  done
  [ "$ok" = 1 ] || { echo "ERROR: attacker never brought up a working tunnel; aborting $ARM" >&2; exit 3; }
  actl "--version" 2>&1 | head -1 > "$OUT/attacker-build.txt" || true
  # Persistent attacker download as a transient unit (survives this SSH call, unlike nohup here).
  $ATTACKER_SSH "systemd-run --unit=atk-dl --collect bash -c \
    'while true; do curl -4 -s --interface $ATTACKER_IF --resolve ${DL_HOST}:443:${DL_IP} -o /dev/null -m 120 -r 0-9000000000 $DL_URL; done'" >/dev/null 2>&1 || true
  # Confirm the arm's intended exit-side condition before measuring: treatment must show SURB drops,
  # contention must not. (Verification only; the measurement below stands on its own.)
  sleep 20
  tnow=$(date +%s)
  sleep 20
  d=$($EXIT_SSH "journalctl -u hoprd --since @$tnow --no-pager -o cat | sed -E 's/\x1b\[[0-9;]*m//g' | grep -c 'no SURB'" 2>/dev/null || echo 0)
  echo "attacker loaded; exit SURB drops in a 20s pre-check: $d (treatment expects >0, contention 0)"
fi

# --- victim measurement: ping through the tunnel -------------------------------------------------
T0=$(date +%s)
echo "$(date -u +%FT%TZ) pinging from victim for ${DUR}s"
$VICTIM_SSH "ping -D -i 0.3 -W 2 -w $DUR 1.1.1.1" > "$OUT/ping.txt" 2>&1 || true
T1=$(date +%s)

# --- collect -------------------------------------------------------------------------------------
$EXIT_SSH "journalctl -u hoprd --since @$T0 --until @$T1 --no-pager -o short-iso-precise | sed -E 's/\x1b\[[0-9;]*m//g' | gzip" > "$OUT/exit.log.gz" 2>/dev/null || true
[ "$ARM" != "baseline" ] && $ATTACKER_SSH "systemctl stop atk-dl 2>/dev/null || true"
python3 - "$ARM" "$DUR" "$T0" "$T1" > "$OUT/arm-meta.json" <<'PY'
import sys,json,datetime
arm,dur,t0,t1=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4])
print(json.dumps({"arm":arm,"duration_s":dur,
  "window_utc":[datetime.datetime.fromtimestamp(t,datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ") for t in (t0,t1)]},indent=1))
PY
echo "$(date -u +%FT%TZ) arm $ARM done -> $OUT"
