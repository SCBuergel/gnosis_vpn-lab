#!/bin/bash
# gnosis_vpn-server with the session target address, a WireGuard interface and NAT. Run as root.
# Usage: install-exit-server.sh SERVER_BINARY HOOKS_SCRIPT
set -euo pipefail
SERVER_BINARY=$1 HOOKS_SCRIPT=$2
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -q wireguard-tools iptables >/dev/null
install -m 755 "$SERVER_BINARY" /usr/local/bin/gnosis_vpn-server
install -m 755 "$HOOKS_SCRIPT" /usr/local/bin/exit-wg-hooks.sh
echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/91-exit-forward.conf
sysctl -q --system
install -d -m 700 /etc/gnosisvpn-server /var/lib/gnosisvpn-server
umask 077
[ -s /etc/gnosisvpn-server/wg.key ] || wg genkey > /etc/gnosisvpn-server/wg.key
# gnosis_vpn-server keeps this [Interface] section and appends the [Peer] sections it manages.
if [ ! -s /var/lib/gnosisvpn-server/wggvpn.conf ]; then
    {
        echo "[Interface]"
        echo "Address = 10.128.0.1/32"
        echo "ListenPort = 51820"
        echo "PrivateKey = $(cat /etc/gnosisvpn-server/wg.key)"
        echo "MTU = 1420"
        echo "PostUp = /usr/local/bin/exit-wg-hooks.sh up"
        echo "PreDown = /usr/local/bin/exit-wg-hooks.sh down"
    } > /var/lib/gnosisvpn-server/wggvpn.conf
fi
cat > /etc/gnosisvpn-server/config.toml <<'CONFIG'
allowed_client_ips = { start = "10.128.0.2", end = "10.128.0.21" }
wireguard_config_path = "/var/lib/gnosisvpn-server/wggvpn.conf"
endpoint = "172.30.0.1:8000"
client_handshake_timeout_s = 300
client_cleanup_interval_s = 180
CONFIG
# 172.30.0.1 is the session target address built into the Gnosis VPN client.
cat > /etc/systemd/system/exit-loopback-alias.service <<'UNIT'
[Unit]
Description=Session target address 172.30.0.1 on lo (built into the Gnosis VPN client)
Before=hoprd.service gnosisvpn-server.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'ip addr replace 172.30.0.1/32 dev lo'

[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/gnosisvpn-server.service <<'UNIT'
[Unit]
Description=GnosisVPN server (vpn-lab exit)
Requires=exit-loopback-alias.service
After=network-online.target exit-loopback-alias.service
StartLimitIntervalSec=0

[Service]
Environment=RUST_LOG=info
WorkingDirectory=/var/lib/gnosisvpn-server
ExecStart=/usr/local/bin/gnosis_vpn-server --config-file /etc/gnosisvpn-server/config.toml serve --periodically-run-cleanup --sync-wg-interface
ExecStopPost=-/usr/bin/wg-quick down /var/lib/gnosisvpn-server/wggvpn.conf
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable -q --now exit-loopback-alias.service gnosisvpn-server.service
