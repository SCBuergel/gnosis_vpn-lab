#!/bin/bash
# Take the hoprd build with exit payments, its config validator and the proving files out of the
# published container image. The GitHub release binary is built without exit payments.
# Usage: extract-exit-hoprd.sh IMAGE HOPRD_SHA256 OUTPUT_DIR PROVING_FILES_DIR
set -euo pipefail
IMAGE=$1 HOPRD_SHA256=$2 OUTPUT_DIR=$3 PROVING_FILES_DIR=$4
export DEBIAN_FRONTEND=noninteractive
command -v docker >/dev/null || apt-get install -y -q docker.io >/dev/null
docker pull -q "$IMAGE" >/dev/null
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
docker run --rm --entrypoint /bin/sh -v "$OUTPUT_DIR":/out "$IMAGE" -c \
    'cp "$(readlink -f /bin/hoprd)" /out/hoprd && cp "$(readlink -f /bin/hoprd-cfg)" /out/hoprd-cfg \
     && mkdir -p /out/curvy-zk && cp -aL /nix/store/*-curvy-zk-artifacts-*/. /out/curvy-zk/'
printf '%s  %s\n' "$HOPRD_SHA256" "$OUTPUT_DIR/hoprd" | sha256sum -c - >/dev/null
mkdir -p "$PROVING_FILES_DIR"
cp -a "$OUTPUT_DIR/curvy-zk/." "$PROVING_FILES_DIR/"
chmod -R a+rX "$PROVING_FILES_DIR"
