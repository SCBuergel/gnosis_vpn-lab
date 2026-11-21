#!/bin/bash
# Download a file and refuse it unless its SHA-256 matches.
# Usage: fetch.sh URL SHA256 DESTINATION
set -euo pipefail
URL=$1 SHA256=$2 DESTINATION=$3
curl -fsSL -o "$DESTINATION" "$URL"
printf '%s  %s\n' "$SHA256" "$DESTINATION" | sha256sum -c - >/dev/null
