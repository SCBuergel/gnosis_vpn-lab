#!/bin/bash
# Sudden outages of 1 .. 8 relays with the client before and after the fix. Waits for the ladders to finish.
cd "$(dirname "$0")"
# run-ladders9.sh is started with its output redirected to raw/run-ladders9.log
until grep -q ALL-DONE ../../raw/run-ladders9.log; do sleep 20; done
./brutal9.sh 2026-11-26-brutal9-before main-20edcc6f
./brutal9.sh 2026-11-26-brutal9-after main-hoprnet-7486609
echo ALL-DONE
