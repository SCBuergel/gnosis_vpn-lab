#!/usr/bin/env bash
# Put one of the hoprd builds in /root/lab/builds/<name>/hoprd on the exit and restart the node.
# Usage: set-exit-build.sh <stock|src|pr8763>
set -euo pipefail
NAME="${1:?usage: set-exit-build.sh <stock|src|pr8763>}"
LAB="${LAB:-$(cd "$(dirname "$0")/../.." && pwd)}"
EXIT_SSH="${EXIT_SSH:-ssh -F $LAB/state/ssh_config -o BatchMode=yes lab-exit}"
$EXIT_SSH "set -e; test -x /root/lab/builds/$NAME/hoprd
  install -m 755 /root/lab/builds/$NAME/hoprd /usr/local/bin/hoprd
  systemctl restart hoprd; sleep 5; systemctl is-active hoprd >/dev/null
  echo \"exit build $NAME: \$(hoprd --version) sha256 \$(sha256sum /usr/local/bin/hoprd | cut -c1-16)\""
