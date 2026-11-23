#!/bin/bash
# Fault injection on a relay: drop everything between this relay and one other node.
#
#   relay-blackhole.sh on ADDRESS | off | status
#
# The relay keeps its connections to every other node, so clients still pick it for their paths, but
# what it should hand to ADDRESS (and what ADDRESS sends it) is lost. Only UDP is dropped; SSH stays.
# The last line of output is always "relay blackhole: off" or "relay blackhole: ADDRESS".
set -euo pipefail

tag=vpn-lab-blackhole
clear_rules() {
    for chain in INPUT OUTPUT; do
        { iptables -S "$chain" | grep -- "--comment $tag" || true; } | sed 's/^-A/-D/' | while read -r rule; do
            # shellcheck disable=SC2086
            iptables $rule
        done
    done
}

case "${1:-}" in
    status) ;;
    off) clear_rules ;;
    on)
        address=$2
        [[ "$address" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "not an IPv4 address: $address" >&2; exit 2; }
        clear_rules
        iptables -I OUTPUT -p udp -d "$address" -m comment --comment "$tag" -j DROP
        iptables -I INPUT -p udp -s "$address" -m comment --comment "$tag" -j DROP
        ;;
    *)
        echo "usage: relay-blackhole.sh on ADDRESS | off | status" >&2
        exit 2
        ;;
esac
target=$({ iptables -S OUTPUT | grep -- "--comment $tag" || true; } | grep -o -- '-d [0-9.]*' | head -1 | cut -d' ' -f2 || true)
echo "relay blackhole: ${target:-off}"
