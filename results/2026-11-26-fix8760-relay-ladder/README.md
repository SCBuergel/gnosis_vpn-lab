# 2026-11-26: relay cuts with 3 relays in use, before and after hoprnet PR #8760

**This run was planned as a ladder from 9 relays down to 1 and does not show that.** The client has
channels to 9 relays (3 lab relays, 6 public relays), but the exit has channels only to the 3 lab relays.
Replies can only return through those 3, and the client also sent its outgoing traffic almost only
through them. The 6 public relays were idle spares. Cutting them changed nothing because they carried no
traffic, not because the fault of hoprnet#8750 failed to appear. What the run does show is 3 relays in
use going to 2 and to 1, with spares that cannot reach the exit.

**Measured:** one run per client build on vpn-lab3, and one shorter diagnosis run with the fixed build.
After 5 minutes of baseline, one relay is cut off from the exit every 5 minutes; then all cuts are removed
and the run goes on for 5 more minutes. Load: a ping every 0.2 s and a 2 MB download every 30 s through
the tunnel. Builds and exit as in `../2026-11-26-fix8760-relay-fault-n9/`.

**How a relay is cut:** the exit drops every packet arriving from that relay. The relay still answers
the client. Order: the 6 idle public relays, then lab relay 1, then lab relay 2; lab relay 3 stays.

## Result

| Step | Relays in use that still work | Before the fix: download median Mbit/s, ping loss, ping median | Fixed: download median Mbit/s, ping loss, ping median |
| --- | --- | --- | --- |
| Baseline | 3 of 3 | 12.1, 0.3%, 35 ms | 11.9, 0.4%, 36 ms |
| The 6 idle public relays cut, one per step | 3 of 3 | 12.1 to 18.6, 0.3 to 0.4%, 35 to 36 ms | 11.6 to 15.8, 0.3 to 0.4%, 35 to 36 ms |
| Lab relay 1 cut | 2 of 3 | 1.0, 9.3%, 39 ms | **0.5 (2 of 5 downloads failed), 36.9%, 2833 ms** |
| Lab relay 2 cut | 1 of 3 | 0.6 (1 of 5 failed), 17.2%, 44 ms | **0.4 (2 of 4 failed), 66.2%, 3032 ms** |
| All cuts removed | 3 of 3 | 16.1, 7.0%, 35 ms | 16.2, 11.7%, 38 ms |

The full per-step tables are in `tables.md`; their column "relays left" counts all 9 channels, idle ones
included.

- **The fault of hoprnet#8750 reproduced with the build before the fix** at the first cut of a relay in
  use: downloads fell to about 1 Mbit/s, as in the single-outage test.
- **With 2 and 1 working relays in use, the fixed build did worse than the build before the fix.** Ping
  loss was 37% and 66% against 9% and 17%, and ping round trips rose to about 3 s. The reason is the
  spares, see below.
- **Both builds recover at once when the cuts are removed.**
- **Cutting the 6 public relays changed nothing, because neither build was using them.** See below.

## What the logs show

The client logs the set of first-hop relays it draws forward paths from (`forward-sets.log.gz` per run).

| Phase | Before the fix | Fixed |
| --- | --- | --- |
| Baseline and public cuts | the 3 lab relays, always | the 3 lab relays; a public relay in a few rebuilds of the baseline |
| Lab relay 1 cut | still the 3 lab relays; the dead one at weight 0.010 against 0.327 | the 2 live lab relays plus one **cut public relay at weight 0.31** |
| Lab relay 2 cut | still the 3 lab relays, two of them at 0.010 | the 1 live lab relay plus **two cut public relays at 0.32 each** |

- **Before the fix** the dead relay keeps its forward slot at a small weight. Few packets are lost on the
  way out; the loss is on the reply side (the bug of hoprnet#8750).
- **With the fix** the dead relay leaves the forward set and a public relay takes its slot at full weight.
  In this run those public relays could not reach the exit, so about one third and then two thirds of the
  outgoing packets were lost, which matches the ping loss. The client did not drop these relays within
  the 5 minutes of a step.
- **This is why the single-outage test looked good:** there the public relay that took the slot was
  healthy.

**Diagnosis run (fixed build)** confirms it in one session:

| Step | Download median Mbit/s | Ping loss | Ping median |
| --- | --- | --- | --- |
| Lab relay 1 cut, public relays healthy (4 min) | 8.2 | 1.2% | 40 ms |
| Cut removed | 16.1 | 0.3% | 35 ms |
| The 6 public relays cut (3 min) | 9.0 | 0.3% | 36 ms |
| Lab relay 1 cut as well (4 min) | 0.5 | 31.8% | 2834 ms |

## Not shown

- **Why the fixed client keeps a relay that cannot reach the exit in its forward set.** The fixed build
  contains hoprnet #8702 ("judge forward relayers from the Exit's receipts"); whether that judgement ran
  and what it concluded was not analysed. Which of the five hoprnet commits between the two builds
  changed the forward-set behaviour was not isolated.
- **Where the 3 s ping round trips come from.** Not analysed.
- **Nothing about 9, 8, ... 4 relays in use.** That needs an exit with channels to all 9 relays.
- **Why the client sent its outgoing traffic almost only through the 3 relays that can carry replies,**
  although it has channels to 9. Not analysed.
- Six relays that the client can reach and the exit cannot hear is an artificial state. One such relay
  is not: the fixed client would then lose up to a third of its outgoing packets after another relay fails.
- One run per build.

## Files

| File | Content |
| --- | --- |
| `tables.md` | Per-step numbers of all three runs |
| `ladder-before/`, `ladder-after/`, `diag-after/` | `phases.txt`, `steps.txt` (time of each cut), `curl.txt` (downloads), `ping.txt`, `drops.txt` (packets dropped per cut on the exit), client and exit logs at INFO and above, `forward-sets.log.gz` |
| `../../repro/relay-fault-n9/` | `ladder.sh`, `diag.sh` (drivers), `ladder-pack.py` (tables) |

Full logs including DEBUG lines are under `raw/2026-11-26-ladder-*` and `raw/2026-11-26-diag-after` (not in git).
