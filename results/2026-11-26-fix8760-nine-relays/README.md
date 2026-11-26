# 2026-11-26: relay outages with 9 relays in use, before and after hoprnet PR #8760

**Measured:** four runs on vpn-lab3 with a dedicated client (`client2`) that has channels to the 9 lab
relays, and an exit that has channels to the same 9. All 9 relays carry traffic in both directions; no
public relay is involved. Two fault patterns, each run once with the client build before the fix and
once with the fixed build:

- **Ladder:** after 5 minutes of baseline one more relay is cut every 5 minutes (relay 1 to relay 8,
  relay 9 stays), then all cuts are removed and the run goes on for 5 more minutes.
- **Sudden outage:** for N = 1 to 8, relays 1 to N are cut at the same moment for 5 minutes, then all 9
  work again for 5 minutes before the next, larger cut.

**How a relay is cut:** the exit drops every packet arriving from that relay. The relay still answers
the client. This is the fault of hoprnet#8750.

**Load:** through the tunnel, a ping every 0.2 s and a loop of one 2 MB download followed by a 30 s
pause. A download is given up after 50 s and counts in the step in which it started.

**Builds:** as in `../2026-11-26-fix8760-relay-fault-n9/`: before = gnosis_vpn-client main `20edcc6f`
(hoprnet `fa69827`), fixed = the same with hopr-lib at `7486609`, the merge commit of PR #8760. The exit
ran the released hoprd 5.0.6, the relays hoprd 5.0.4.

**Repository commit:** `6a1d677` plus the scripts added in the commit that adds this folder.

## Result: ladder

| Relays cut | Relays left | Before the fix: downloads done, median Mbit/s (lowest), ping loss | Fixed: downloads done, median Mbit/s (lowest), ping loss |
| --- | --- | --- | --- |
| none (baseline) | 9 | 9 of 9, 11.4 (8.3), 0.4% | 10 of 10, 13.6 (8.9), 0.4% |
| 1 | 8 | 10 of 10, 14.7 (1.1), 2.0% | 10 of 10, 10.7 (8.4), 0.5% |
| 2 | 7 | 8 of 8, 2.2 (1.0), 2.5% | 10 of 10, 9.8 (4.0), 1.2% |
| 3 | 6 | 5 of 6, 1.8 (0.8), 10.8% | 9 of 9, 14.3 (3.8), 0.4% |
| 4 | 5 | 4 of 5, 0.6 (0.4), 8.6% | 9 of 9, 8.4 (1.4), 1.5% |
| 5 | 4 | **0 of 6**, 90.3% | 10 of 10, 8.5 (2.4), 1.7% |
| 6 | 3 | **0 of 6**, 100% | 9 of 9, 10.3 (3.4), 7.0% |
| 7 | 2 | **0 of 6**, 100% | 9 of 9, 8.3 (1.1), 3.0% |
| 8 | 1 | **0 of 7**, 100% | 8 of 8, 9.6 (0.4), 11.0% |
| all cuts removed | 9 | 1 of 5, 7.6, 93.8% | 10 of 10, 10.5 (8.7), 0.3% |

- **Before the fix the client slows down from the second cut and loses the connection at 4 relays
  left.** With one relay cut the median held and only single downloads were slow (1.1 Mbit/s). It did not come back while relays were cut, and after all cuts were removed only the last of
  five downloads completed.
- **The fixed client completed every download at every step, down to 1 relay left.** Medians stayed
  between 8.3 and 14.3 Mbit/s.
- **The fixed client is not loss-free.** From the second cut on, the slowest download of each step ran at 0.4 to 4.0 Mbit/s,
  and ping loss was 7.0% at 3 relays left and 11.0% at 1.

## Result: sudden outage

| Relays cut at once | Relays left | Before the fix: downloads done, median Mbit/s (lowest), ping loss | Fixed: downloads done, median Mbit/s (lowest), ping loss |
| --- | --- | --- | --- |
| none (baseline) | 9 | 9 of 9, 15.5 (9.3), 0.4% | 9 of 9, 12.7 (8.2), 0.4% |
| 1 | 8 | 9 of 9, 9.8 (1.9), 2.6% | 10 of 10, 10.6 (7.1), 0.6% |
| 2 | 7 | 9 of 9, 10.7 (0.9), 1.8% | 10 of 10, 13.3 (2.3), 1.0% |
| 3 | 6 | 7 of 7, 8.2 (0.5), 4.9% | 10 of 10, 8.0 (4.8), 3.4% |
| 4 | 5 | 8 of 8, 2.8 (0.7), 4.9% | 10 of 10, 9.4 (1.5), 1.5% |
| 5 | 4 | 7 of 7, 1.3 (0.4), 9.1% | 9 of 9, 6.1 (2.8), 6.7% |
| 6 | 3 | **0 of 6**, 99.5% | 8 of 8, 4.9 (0.5), 16.5% |
| 7 | 2 | **0 of 5**, 100% | 9 of 9, 9.0 (0.8), 5.4% |
| 8 | 1 | **0 of 6**, 99.9% | **0 of 6**, 99.6% |

The 5 minutes after each cut, with all 9 relays working again:

| After a cut of | Before the fix: downloads done, median Mbit/s, ping loss | Fixed: downloads done, median Mbit/s, ping loss |
| --- | --- | --- |
| 1 to 5 relays | all done, 10.5 to 15.3, 0.3 to 0.4% | all done, 10.8 to 15.7, 0.3 to 0.4% |
| 6 relays | 5 of 8, 16.9, 25.4% | 9 of 9, 15.9, 0.3% |
| 7 relays | 7 of 8, 10.5, 24.4% | 10 of 10, 15.7, 0.4% |
| 8 relays | 6 of 8, 14.6, 33.3% | 7 of 8, 10.9, 11.6% (session not paid for, see below) |

- **Before the fix the client loses the connection when 6 or more relays are cut at once.** With up to 5
  cut it completes its downloads, at a median of 2.8 and 1.3 Mbit/s for 4 and 5 cut. That is one relay
  more than in the ladder, where the effects of earlier cuts add up.
- **The fixed client keeps downloading with up to 7 relays cut at once, and loses the connection with
  8.** In the ladder the same client worked on that one relay, so one relay is enough to carry the
  traffic; the client did not get there within 5 minutes when the other 8 failed together.
- **Sudden cuts cost the fixed client more than gradual ones.** With 5 and 6 cut at once the median was
  6.1 and 4.9 Mbit/s with 6.7% and 16.5% ping loss; the ladder had 8.5 and 10.3 Mbit/s with 1.7% and
  7.0% at the same number of relays.
- **Both builds recover fully within the next 5 minutes after any outage they survived.** After a total
  outage the first part of the recovery window is lost (12 to 33% of the pings).

## What the logs show

The client rebuilds two sets of 3 paths every few seconds: one for outgoing traffic (client, relay,
exit) and one that it hands to the exit for replies (exit, relay, client). Each path has a weight. The
table gives the share of the total weight that sat on relays that still worked; all steps are in
`tables.md`.

| Step | Before the fix: outgoing, reply | Fixed: outgoing, reply |
| --- | --- | --- |
| Ladder, 4 cut | 94%, 97% | 100%, 100% |
| Ladder, 5 cut | 52%, 96% | 99%, 100% |
| Ladder, 6 cut | 0%, 74% | 99%, 100% |
| Ladder, 8 cut | 0%, 22% | 100%, 100% |
| Sudden, 5 cut | 90%, 90% | 100%, 95% |
| Sudden, 6 cut | 72%, 50% | 85%, 87% |
| Sudden, 7 cut | 0%, 24% | 95%, 92% |
| Sudden, 8 cut | 0%, 15% | 33%, 14% |

- **Before the fix the outgoing set stays on cut relays.** In the ladder it held only relays 1, 2 and 5 from
  the third cut on (in the baseline also relays 6, 7 and 9); once all three were cut, almost no outgoing
  weight was on a working relay and the connection was gone. The reply set keeps sampling all 9 relays, cut ones included.
- **The fixed client moves both sets to working relays** and returns to a cut relay only for a probe,
  once a minute per cut relay (`probe out through a relayer on probation, dead again until its verdict
  lapses`): 4 probes in the first ladder step, 46 in the last.
- **With 8 relays cut at once the fixed client did not move in time.** 33 s after the cut it gave up the
  connection and tried to reconnect. 13 session requests timed out
  (`session initiation attempt timed out`); four sessions were established and closed again, because the
  next step, registering the WireGuard key at the exit through the session, timed out each time
  (`register wg pubkey failed`). No tunnel came up before the cuts were removed. In that step only 14%
  of the reply weight and 33% of the outgoing weight were on the one working relay.

## Not shown

- **One run per build and pattern.** Single figures, such as the fixed client's 16.5% ping loss with 6
  relays cut at once or the exact number of relays at which the client before the fix fails, are not
  established.
- **The difference is not attributed to PR #8760 alone.** The fixed build differs by five hoprnet
  commits: #8702, #8713, #8729, #8746 and #8760.
- **Why the fixed client cannot set up a new session when 8 of 9 relays fail at once** was not analysed
  beyond the log lines above. Whether it would succeed with more than 5 minutes was not tested.
- **The recovery window after 8 relays cut at once is confounded by payment in the fixed run.** From
  16:03 UTC the client could not refill its payment pool (`funding the deposit pool failed`, 35 times;
  the Safe held 24.31 wxHOPR and a refill takes 35.35). The chunk in use had been paid at 16:03, so the
  cuts of 6, 7 and 8 relays ran on a paid session. After the reconnect at 16:33 the new session could
  not be paid for (`the private pool has no committed note large enough`), the client reconnected once
  more at 16:36, and the run ended in `payment_failed`. The figures of that window (7 of 8 downloads,
  11.6% ping loss) are therefore not a clean measure of recovery.
- **The last window of each run is covered by the ping only in part** (246 to 308 s of about 313 s),
  because the ping stops on a fixed timeout and the steps overrun by a few seconds each. Ping loss of
  that window is computed over the time the ping ran.
- **The cut relays are always relays 1 to N, in this order.** Other orders were not tested. In the
  ladder before the fix, the step at which the connection is lost depends on which relays the outgoing
  set happens to hold.
- **One fault type.** The relay stays reachable for the client. A relay that is fully offline was not
  tested.
- Reply paths and outgoing paths are told apart by their last hop in the client's log; what the exit
  did with the reply paths it received was not read from the exit.

## Changes to the lab

- Relays 4 to 9 were added to vpn-lab3 (`lab.toml`), each with a channel to the exit; the exit opened
  channels to all 9.
- `client2` got the configuration `repro/relay-fault-n9/config-9lab.toml`, channels to the 9 lab relays
  and both builds under `/root/lab/`; its earlier configuration is on the machine as
  `/root/config.toml.before-9lab`.

## Files

| File | Content |
| --- | --- |
| `tables.md` | Per-step numbers of all four runs: downloads, ping, frames, relay verdicts, path-set shares |
| `ladder-before/`, `ladder-after/`, `sudden-before/`, `sudden-after/` | `phases.txt` (its first line says `mode=ladder` in the sudden runs too), `steps.txt` (time of each cut and restore), `curl.txt` (downloads), `ping.txt.gz`, `drops.txt` (packets dropped per cut on the exit), `config.toml`, client and exit logs at INFO and above, `path-sets.log.gz` (every rebuild of the two path sets) |
| `../../repro/relay-fault-n9/` | `ladder9.sh`, `brutal9.sh` (drivers), `run-ladders9.sh`, `run-brutal9.sh` (queues), `ladder-pack.py`, `sets-pack.py` (tables), `config-9lab.toml` |

Full logs including DEBUG lines and the relay logs are under `raw/2026-11-26-ladder9-*` and
`raw/2026-11-26-brutal9-*` (not in git).
