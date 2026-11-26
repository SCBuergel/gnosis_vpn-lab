#!/bin/bash
# The ladder with the client before and after the fix.
cd "$(dirname "$0")"
./ladder.sh 2026-11-26-ladder-before main-20edcc6f
./ladder.sh 2026-11-26-ladder-after main-hoprnet-7486609
echo ALL-DONE
