#!/bin/bash
# Forwarding, NAT and isolation for the lab exit's WireGuard interface.
# A reduced form of the exit appliance's wg-hooks.sh: no blocklist, no traffic shaping.
# Usage: exit-wg-hooks.sh up|down
set -euo pipefail
WG=wggvpn UPLINK=eth0 POOL=10.128.0.0/24 SERVER=10.128.0.1 MSS=1380
rules() {
    local op=$1
    # VPN clients may ping the server address (the client's verification ping); nothing else on the host.
    iptables "$op" INPUT -i $WG -s $POOL -d $SERVER -p icmp --icmp-type echo-request -j ACCEPT
    iptables "$op" INPUT -i $WG -j DROP
    # VPN clients must not reach private ranges (the provider's private network, link-local, carrier NAT).
    for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 169.254.0.0/16 127.0.0.0/8; do
        iptables "$op" FORWARD -i $WG -d $net -j DROP
    done
    iptables "$op" FORWARD -i $WG -o $UPLINK -s $POOL -j ACCEPT
    iptables "$op" FORWARD -i $UPLINK -o $WG -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    iptables -t mangle "$op" FORWARD -o $WG -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss $MSS
    iptables -t mangle "$op" FORWARD -i $WG -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss $MSS
    iptables -t nat "$op" POSTROUTING -s $POOL -o $UPLINK -j MASQUERADE
}
case "$1" in
up) rules -A ;;
down) rules -D || true ;;
*) echo "usage: $0 up|down" >&2; exit 2 ;;
esac
