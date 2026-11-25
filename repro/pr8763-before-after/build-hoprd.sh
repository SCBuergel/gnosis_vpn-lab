#!/bin/bash
# Build hoprd 5.0.6 from source twice: unpatched, and with hoprnet PR #8763 applied to the pinned hoprnet revision.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive
HOPRNET_REV=fa6982739334f84ae458a1b1195a21bf27956dd0
apt-get update -q >/dev/null
apt-get install -y -q build-essential clang cmake pkg-config libssl-dev protobuf-compiler git curl >/dev/null
command -v cargo >/dev/null || curl -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain none >/dev/null
. /root/.cargo/env
mkdir -p /root/src /root/out && cd /root/src
[ -d hoprd ] || git clone -q --branch v5.0.6 --depth 1 https://github.com/hoprnet/hoprd
[ -d hoprnet ] || { git clone -q https://github.com/hoprnet/hoprnet && git -C hoprnet checkout -q $HOPRNET_REV; }
cd hoprd
sed -i -E "s#^hopr-lib = \{ git = \"[^\"]+\", rev = \"$HOPRNET_REV\"#hopr-lib = { path = \"/root/src/hoprnet/hopr/hopr-lib\"#; s#^hopr-utils-session = \{ git = \"[^\"]+\", rev = \"$HOPRNET_REV\"#hopr-utils-session = { path = \"/root/src/hoprnet/utils-session\"#" Cargo.toml
grep -n "^hopr-lib\|^hopr-utils-session" Cargo.toml
cargo build --release -p hoprd -F strategy-pix-curvy
cp target/release/hoprd /root/out/hoprd-5.0.6-src
git -C /root/src/hoprnet apply --include='transport/hopr/src/*' /root/pr8763.diff   # the PR diff: https://github.com/hoprnet/hoprnet/pull/8763.diff at head c5867a3
git -C /root/src/hoprnet diff --stat
cargo build --release -p hoprd -F strategy-pix-curvy
cp target/release/hoprd /root/out/hoprd-5.0.6-pr8763
sha256sum /root/out/*
echo BUILD-DONE
