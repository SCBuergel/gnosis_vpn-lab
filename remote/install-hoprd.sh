#!/bin/bash
# Install hoprd from binaries already on the machine, with a systemd unit. Run as root.
# Usage: install-hoprd.sh HOPRD_BINARY HOPRD_CFG_BINARY
# Expects /root/lab/hoprd.cfg.yaml, /root/lab/hoprd.env and /root/lab/node.id.
set -euo pipefail
HOPRD_BINARY=$1 HOPRD_CFG_BINARY=$2
install -m 755 "$HOPRD_BINARY" /usr/local/bin/hoprd
install -m 755 "$HOPRD_CFG_BINARY" /usr/local/bin/hoprd-cfg
id hoprd >/dev/null 2>&1 || useradd --system --home-dir /var/lib/hoprd --shell /usr/sbin/nologin hoprd
install -d -o hoprd -g hoprd -m 700 /var/lib/hoprd /etc/hoprd
install -o hoprd -g hoprd -m 600 /root/lab/node.id /etc/hoprd/node.id
install -o root -g root -m 600 /root/lab/hoprd.env /etc/hoprd/hoprd.env
install -o hoprd -g hoprd -m 644 /root/lab/hoprd.cfg.yaml /etc/hoprd/hoprd.cfg.yaml
# hoprd's QUIC sockets inherit the default buffer sizes (same values as the exit appliance).
cat > /etc/sysctl.d/90-hoprd.conf <<'SYSCTL'
net.core.rmem_default = 4194304
net.core.rmem_max = 4194304
net.core.wmem_default = 4194304
net.core.wmem_max = 4194304
SYSCTL
sysctl -q --system
cat > /etc/systemd/system/hoprd.service <<'UNIT'
[Unit]
Description=hoprd node (vpn-lab)
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=0

[Service]
User=hoprd
Group=hoprd
EnvironmentFile=/etc/hoprd/hoprd.env
WorkingDirectory=/var/lib/hoprd
ExecStart=/usr/local/bin/hoprd --configurationFilePath /etc/hoprd/hoprd.cfg.yaml
KillSignal=SIGINT
TimeoutStopSec=90
Restart=always
RestartSec=30
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
# Validate the effective configuration (file plus environment) before the node is started.
set -a
# shellcheck disable=SC1091
. /etc/hoprd/hoprd.env
set +a
/usr/local/bin/hoprd-cfg --validate-args -- --configurationFilePath /etc/hoprd/hoprd.cfg.yaml >/dev/null
systemctl enable -q --now hoprd
/usr/local/bin/hoprd --version
