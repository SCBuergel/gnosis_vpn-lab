#!/bin/bash
# Fault injection on the exit: delay every packet the exit sends to the payment relayer.
#
#   relayer-delay.sh HOST on MILLISECONDS | HOST off | HOST status
#
# Only packets to the addresses of HOST are delayed, in the outgoing direction. HOPR traffic and the
# traffic of VPN users to any other destination are untouched. A client's requests to the relayer leave
# the exit through this interface whether they travel in the VPN tunnel or in a session of their own, so
# the delay applies to both.
#
# The last line of output is always "relayer delay: off" or "relayer delay: N ms".
set -euo pipefail

host=$1
action=$2
dev=$(ip -4 route show default | awk '{print $5; exit}')

report() {
    local delay
    delay=$(tc qdisc show dev "$dev" | awk '/netem/ {for (i = 1; i < NF; i++) if ($i == "delay") print $(i + 1)}' | head -1)
    case "$delay" in
        "") echo "relayer delay: off" ;;
        *ms) echo "relayer delay: ${delay%ms} ms" ;;
        *s) echo "relayer delay: $(awk -v s="${delay%s}" 'BEGIN {printf "%d", s * 1000}') ms" ;;
        *) echo "relayer delay: $delay" ;;
    esac
}

case "$action" in
    status) ;;
    off)
        tc qdisc del dev "$dev" root 2>/dev/null || true
        ;;
    on)
        ms=$3
        [[ "$ms" =~ ^[0-9]+$ ]] && [ "$ms" -gt 0 ] || { echo "delay must be a positive number of milliseconds" >&2; exit 2; }
        addresses=$(getent ahostsv4 "$host" | awk '{print $1}' | sort -u)
        [ -n "$addresses" ] || { echo "cannot resolve $host" >&2; exit 1; }
        tc qdisc del dev "$dev" root 2>/dev/null || true
        # Band 4 is used by no priority value, so only the filters below put packets into it.
        tc qdisc add dev "$dev" root handle 1: prio bands 4 priomap 1 2 2 2 1 2 0 0 1 1 1 1 1 1 1 1
        tc qdisc add dev "$dev" parent 1:4 handle 40: netem delay "${ms}ms"
        for address in $addresses; do
            tc filter add dev "$dev" protocol ip parent 1:0 prio 1 u32 match ip dst "$address/32" flowid 1:4
            echo "delaying packets to $address"
        done
        ;;
    *)
        echo "usage: relayer-delay.sh HOST on MILLISECONDS | HOST off | HOST status" >&2
        exit 2
        ;;
esac
report
