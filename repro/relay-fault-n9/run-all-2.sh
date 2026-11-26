#!/bin/bash
# Second batch of 2026-11-26: controls and a repeat for the single outage, then the ladder with both builds.
cd "$(dirname "$0")"
B=main-20edcc6f A=main-hoprnet-7486609
./arm.sh 2026-11-26-fix8760-before-control control $B
./arm.sh 2026-11-26-fix8760-after-control control $A
./arm.sh 2026-11-26-fix8760-before-2 fault $B
./ladder.sh 2026-11-26-ladder-before $B
./ladder.sh 2026-11-26-ladder-after $A
echo ALL-DONE
