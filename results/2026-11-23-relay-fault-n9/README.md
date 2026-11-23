# 2026-11-23: one relay of nine stops forwarding to the exit

**Measured:** two runs of 12 minutes each on the lab client, with the unmodified client main `e6b33f36`
built from source and channels to 9 relays (the 3 lab relays plus 6 public relays). Load: a ping every
0.2 s and a 2 MB download every 30 s through the tunnel. In the fault run, lab relay 1 dropped every packet
it sent to the exit for 8 minutes while still answering the client. The control run is the same timeline
with no fault. This repeats the test made on vpn-lab2 the same day by another session.

**Repository commit:** `a296fce` (plus this folder; the driver is `arm.sh` here, not part of `./lab`).

## Result

| 2 MB downloads, Mbit/s | Fault run | Control run |
| --- | --- | --- |
| Before the fault window | 12.1 to 19.2 | 15.4 to 17.9 |
| Download starting with the window | 1.4 | 12.5 |
| +30 s to +150 s | 7.9 to 16.6 | 9.6 to 17.1 |
| +150 s to the end of the window (8 min) | 0.7 to 1.7 | 11.5 to 18.4 |
| After the window | 12.1 to 17.5 | 15.2 to 18.2 |
| Ping loss before, during, after | 0.3%, 2.6%, 0.0% | 0.3%, 0.4%, 0.0% |

- **The fault run repeats the vpn-lab2 result.** The first download after the fault is slow, the next
  four are normal, and from 169 s after the fault every download runs at about a tenth of the speed
  until the fault is removed. The first download after that is back to normal.
- **The control shows no slowdown.** All 25 downloads completed at 9.6 Mbit/s or more.
- **The slowdown does not end by itself within 8 minutes.** Whether it would later was not tested.

## Not shown

- One run each. The cause of the late slowdown was not analysed here.
- The fault cuts relay 1's packets to the exit in both roles (forward traffic and its own traffic to the
  exit). A relay that is fully offline was not tested.

## Changes to the lab for this test

- The client's Safe received 80 wxHOPR from the funding Safe for six channels of 15 wxHOPR to public
  relays. These channels stay open; forward paths of this client are no longer confined to the lab relays
  while the 9-relay configuration is in place.
- The client's original configuration is on the client as `/root/config.toml.lab-original`.

## Files

| File | Content |
| --- | --- |
| `summary-*.txt`, `downloads-*.csv`, `phases-*.txt` | Numbers and timeline of each run |
| `relay-fault-n9-*-logs.tar.gz` | Client, exit and lab relay logs of each run at INFO and above, with a README |
| `client-config.toml` | The client configuration of both runs |
| `arm.sh`, `pack.py` | Test driver and the script that wrote the summaries and log bundles |

Raw data and full logs including DEBUG lines are under `raw/2026-11-23-relay-fault-n9*/` (not in git).
