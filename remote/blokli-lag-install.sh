#!/bin/bash
# Install or remove the Blokli lag proxy (blokli-lag-proxy.py) on this machine.
#
#   blokli-lag-install.sh install LISTEN_ADDRESS PORT UPSTREAM_URL ALLOWED_CLIENT | remove
#
# The lag in seconds is the number in /run/blokli-lag/seconds; the proxy's record of every note-status
# query is /var/log/blokli-lag-proxy.log.
set -euo pipefail

unit=/etc/systemd/system/blokli-lag-proxy.service
case "$1" in
    install)
        export DEBIAN_FRONTEND=noninteractive
        python3 -c 'import aiohttp' 2>/dev/null || apt-get install -y -q python3-aiohttp >/dev/null
        cat > "$unit" <<UNIT
[Unit]
Description=Lab fault injection: Blokli proxy that reports new Curvy notes late
After=network-online.target

[Service]
RuntimeDirectory=blokli-lag
RuntimeDirectoryPreserve=yes
ExecStart=/usr/bin/python3 /root/lab/blokli-lag-proxy.py $2 $3 $4 /run/blokli-lag/seconds /var/log/blokli-lag-proxy.log $5
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
        systemctl daemon-reload
        systemctl enable -q blokli-lag-proxy
        systemctl restart blokli-lag-proxy
        sleep 2
        systemctl is-active -q blokli-lag-proxy
        ;;
    remove)
        systemctl disable -q --now blokli-lag-proxy 2>/dev/null || true
        rm -f "$unit"
        systemctl daemon-reload
        ;;
    *)
        echo "usage: blokli-lag-install.sh install LISTEN_ADDRESS PORT UPSTREAM_URL ALLOWED_CLIENT | remove" >&2
        exit 2
        ;;
esac
