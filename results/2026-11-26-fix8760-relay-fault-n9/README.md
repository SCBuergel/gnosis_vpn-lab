# 2026-11-26: hoprnet PR #8760 tested against the nine-relay fault of hoprnet#8750

**Measured:** three runs of 12 minutes each on the vpn-lab3 client with channels to 9 relays (the 3 lab
relays plus the same 6 public relays as on 2026-11-23). Load: a ping every 0.2 s and a 2 MB download every
30 s through the tunnel. In each run lab relay 1 dropped every packet it sent to the exit for 8 minutes
while still answering the client. One run with the client before the fix, two with the fix.

No snapshot package contains the fix (the snapshot and experimental apt channels are empty, and client main
`20edcc6f` still locks hoprnet `fa69827`), so both clients were built from source:

| Build | Source | Worker sha256 |
| --- | --- | --- |
| before | gnosis_vpn-client main `20edcc6f`, lock file as committed (hoprnet `fa69827`) | `6ef79cf11ee9b63f` |
| after | the same, with `cargo update -p hopr-lib --precise 7486609` (the merge commit of PR #8760) | `368e975c5dc013bd` |

The exit ran the released hoprd 5.0.6 in all runs.

## Result

| | before | after, run 1 | after, run 2 |
| --- | --- | --- | --- |
| Downloads before the fault, Mbit/s | 14.6 to 16.8 | 6.9 to 20.2 | 7.9 to 13.4 |
| Download starting with the fault | 5.4 | 7.0 | 7.2 |
| +30 s to +150 s | 8.4 to 18.8 | 15.8 to 21.2 | 6.6 to 14.9 |
| +150 s to the end of the fault | **0.9 to 1.8** | **6.3 to 17.3** | **5.8 to 17.8** |
| After the fault | 9.5 to 16.7 | 7.7 to 8.3 | 8.9 to 19.5 |
| Ping loss before, during, after | 0.3%, 2.5%, 0.0% | 0.3%, 0.6%, 0.0% | 0.3%, 1.0%, 0.0% |
| Session frames discarded per 30 s window, from +150 s | 7 to 45 in every window | 1, in five windows | 1, in three windows |
| "judged dead again" after probation | never | 8 times, once a minute | 8 times, once a minute |

- **The late slowdown is gone.** Before the fix, every download from 162 s after the fault ran at about
  1 Mbit/s until the fault ended, as on 2026-11-23. With the fix no download fell below 5.8 Mbit/s.
- **The mechanism is the one the PR describes.** The fixed client logs
  `probe out through a relayer on probation, dead again until its verdict lapses` one second after each
  lapse into probation, and loses one frame per minute, which is that probe.
- **The relay is used again after the fault ends**, 14 s and 16 s later (`relayer revived by a reply`).

## Not shown

- **The fixed build's download rates vary more, also before the fault** (6.9 to 20.2 and 7.9 to 13.4
  against 14.6 to 16.8). No control run without a fault was made with this build, so whether that comes
  from the build or from the public relays at that hour is open.
- The "after" build differs from "before" by five hoprnet commits, not only the fix: #8702, #8713, #8729,
  #8746 and #8760. The fix does not apply alone to `fa69827` (it builds on #8702).
- One fault type, one relay, 9 relays, 8 minutes. Fewer relays and a fully offline relay were not tested.
- The first 30 s after the fault still lose frames (20 and 83 in the first window), as before the fix.

## Changes to the lab

- The client's Safe received 115 wxHOPR and its node 0.01 xDAI for six channels of 15 wxHOPR to public
  relays (35 wxHOPR of it went into the client's payment top-up). The 9-relay configuration and the fixed
  build are left installed; the original configuration is on the client as `/root/config.toml.lab-original`.
- Deletion timer set to 4 hours: fires 2026-11-26 11:08 UTC.

## Files

| File | Content |
| --- | --- |
| `before/`, `after/`, `after-2/` | Per run: `summary.txt`, `downloads.csv`, `phases.txt`, logs at INFO and above |
| `../../repro/relay-fault-n9/` | `arm.sh` (driver), `config.toml` (client), `pack.py` (summaries) |

Full logs including DEBUG lines are under `raw/2026-11-26-fix8760-*/` (not in git).
