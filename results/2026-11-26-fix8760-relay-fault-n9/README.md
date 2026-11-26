# 2026-11-26: hoprnet PR #8760 tested against the nine-relay fault of hoprnet#8750

**Measured:** six runs of 12 minutes each on the vpn-lab3 client with channels to 9 relays (the 3 lab
relays plus the same 6 public relays as on 2026-11-23). Load: a ping every 0.2 s and a 2 MB download every
30 s through the tunnel. In the fault runs lab relay 1 dropped every packet it sent to the exit for
8 minutes while still answering the client. Per client build: two fault runs and one control run with the
same timeline and no fault.

No snapshot package contains the fix (the snapshot and experimental apt channels are empty, and client main
`20edcc6f` still locks hoprnet `fa69827`), so both clients were built from source:

| Build | Source | Worker sha256 |
| --- | --- | --- |
| before | gnosis_vpn-client main `20edcc6f`, lock file as committed (hoprnet `fa69827`) | `6ef79cf11ee9b63f` |
| after | the same, with `cargo update -p hopr-lib --precise 7486609` (the merge commit of PR #8760) | `368e975c5dc013bd` |

The exit ran the released hoprd 5.0.6 in all runs.

## Result

The window compared is from 150 s after the fault began until it ended (5.5 minutes), where the slowdown
was reported.

| Run | Downloads before the fault, median Mbit/s | Downloads in the window, median (lowest) | Session frames discarded in the window | Ping loss during the fault | Relay judged dead again after probation |
| --- | --- | --- | --- | --- | --- |
| before, fault 1 | 14.9 | **1.0** (0.9) | 320 of 16,995 (1.9%) | 2.5% | never |
| before, fault 2 | 11.0 | **0.9** (0.6) | 341 of 17,079 (2.0%) | 1.9% | never |
| after, fault 1 | 17.3 | **10.0** (6.3) | 5, one per minute | 0.6% | 8 times, once a minute |
| after, fault 2 | 10.9 | **8.6** (5.8) | 3, one per minute | 1.0% | 8 times, once a minute |
| before, control | 10.7 | 16.8 (10.4) | 0 | 0.3% | - |
| after, control | 14.1 | 11.5 (8.2) | 0 | 0.3% | - |

- **The late slowdown is gone.** Before the fix, every download in the window ran at about 1 Mbit/s in
  both runs, as on 2026-11-23. With the fix the median was 8.6 and 10.0 Mbit/s and no download fell
  below 5.8.
- **The mechanism is the one the PR describes.** The fixed client logs
  `probe out through a relayer on probation, dead again until its verdict lapses` one second after each
  lapse into probation, and loses one frame per minute, which is that probe.
- **The relay is used again after the fault ends**, 14 s and 16 s later (`relayer revived by a reply`).
- **The two builds do not differ without a fault.** Both controls ran between 8 and 23 Mbit/s with 0.3%
  ping loss and no discarded frame. Download rates on this path vary that much from one download to the
  next with either build.

## Not shown

- **Whether a small cost remains during the fault.** The fixed runs had a median of 8.6 and 10.0 Mbit/s in
  the window against 11.5 and 16.8 in the controls. With this spread and two runs that is not established
  either way. One of three reply relays is out in that window.
- The "after" build differs from "before" by five hoprnet commits, not only the fix: #8702, #8713, #8729,
  #8746 and #8760. The fix does not apply alone to `fa69827` (it builds on #8702).
- One fault type, one relay, 8 minutes. A fully offline relay was not tested. For more relays failing see
  `../2026-11-26-fix8760-relay-ladder/`.
- The first 30 s after the fault still lose frames with the fix (20 and 83 in the first window).

## Changes to the lab

- The client's Safe received 115 wxHOPR and its node 0.01 xDAI for six channels of 15 wxHOPR to public
  relays (35 wxHOPR of it went into the client's payment top-up), and 40 wxHOPR more when that payment pool
  ran empty after the sixth run. The 9-relay configuration and the fixed
  build are left installed; the original configuration is on the client as `/root/config.toml.lab-original`.
- Deletion timer: fires 2026-11-26 12:08 UTC.

## Files

| File | Content |
| --- | --- |
| `before/`, `before-2/`, `after/`, `after-2/`, `before-control/`, `after-control/` | Per run: `summary.txt`, `downloads.csv`, `phases.txt`, logs at INFO and above |
| `../../repro/relay-fault-n9/` | `arm.sh` (driver), `config.toml` (client), `pack.py` (summaries) |

Full logs including DEBUG lines are under `raw/2026-11-26-fix8760-*/` (not in git).
