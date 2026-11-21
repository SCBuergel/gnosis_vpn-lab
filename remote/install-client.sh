#!/bin/bash
# Install a pinned Gnosis VPN package with the lab configuration; the worker is not started. Run as root.
# Usage: install-client.sh INSTALLER CHANNEL NETWORK INDEXER PKG_URL PKG_SHA256 PKG_VERSION WORKER_USER LOG_FILTER
# INSTALLER is the official install.sh, already downloaded and hash-checked. Expects /root/lab/client.toml.
set -euo pipefail
INSTALLER=$1 CHANNEL=$2 NETWORK=$3 INDEXER=$4 PKG_URL=$5 PKG_SHA256=$6 PKG_VERSION=$7 WORKER_USER=$8 LOG_FILTER=$9
export DEBIAN_FRONTEND=noninteractive
cd /root/lab
# The official installer sets up the apt source and the service for the channel.
bash "$INSTALLER" --channel="$CHANNEL" --network="$NETWORK" > install.log 2>&1
# Then pin the exact package: verify its hash before installing it.
curl -fsSL "$PKG_URL" -o pinned.deb
printf '%s  %s\n' "$PKG_SHA256" pinned.deb | sha256sum -c - >/dev/null
GNOSISVPN_NETWORK="$NETWORK" GNOSISVPN_HOPR_BLOKLI_URL="$INDEXER" \
    apt-get install -y --allow-downgrades -o Dpkg::Options::=--force-confold ./pinned.deb > pin.log 2>&1
test "$(dpkg-query -W -f='${Version}' gnosisvpn)" = "$PKG_VERSION"
id "$WORKER_USER" >/dev/null 2>&1 || useradd --create-home --user-group --shell /usr/sbin/nologin "$WORKER_USER"
# The package links config.toml to its network preset; a regular file replaces the link and is kept on upgrades.
rm -f /etc/gnosisvpn/config.toml
install -m 644 client.toml /etc/gnosisvpn/config.toml
# Log filter through a drop-in, so the packaged environment file stays untouched. Later files win.
printf 'RUST_LOG=%s\n' "$LOG_FILTER" > /etc/gnosisvpn/lab-log.env
mkdir -p /etc/systemd/system/gnosisvpn.service.d
printf '[Service]\nEnvironmentFile=/etc/gnosisvpn/lab-log.env\n' > /etc/systemd/system/gnosisvpn.service.d/10-lab-log.conf
cat > /etc/sysctl.d/90-gvpn-lab.conf <<'SYSCTL'
net.core.rmem_default = 8388608
net.core.rmem_max = 16777216
net.core.wmem_default = 8388608
net.core.wmem_max = 16777216
SYSCTL
sysctl -q --system
systemctl daemon-reload
systemctl restart gnosisvpn
gnosis_vpn-ctl --version
