#!/bin/bash
# The ladder over 9 lab relays with the client before and after the fix.
cd "$(dirname "$0")"
./ladder9.sh 2026-11-26-ladder9-before main-20edcc6f
./ladder9.sh 2026-11-26-ladder9-after main-hoprnet-7486609
echo ALL-DONE
