# 2026-11-26: relay ladder from 9 down to 1, before and after hoprnet PR #8760

**Measured:** one ladder run per client build on vpn-lab3, and one shorter diagnosis run with the fixed
build. The client has channels to 9 relays (3 lab relays, 6 public relays). After 5 minutes of baseline,
one relay is cut off from the exit every 5 minutes until 1 is left; then all cuts are removed and the run
goes on for 5 more minutes. Load: a ping every 0.2 s and a 2 MB download every 30 s through the tunnel.
Builds and exit as in `../2026-11-26-fix8760-relay-fault-n9/`.

**How a relay is cut:** the exit drops every packet arriving from that relay. The relay still answers
the client. Order: the 6 public relays, then lab relay 1, then lab relay 2; lab relay 3 stays. The exit
has channels only to the 3 lab relays, so replies can only come back through those.

## Result

| Step | Relays left | Before the fix: download median Mbit/s, ping loss, ping median | Fixed: download median Mbit/s, ping loss, ping median |
| --- | --- | --- | --- |
| Baseline | 9 | 12.1, 0.3%, 35 ms | 11.9, 0.4%, 36 ms |
| The 6 public relays cut, one per step | 8 to 3 | 12.1 to 18.6, 0.3 to 0.4%, 35 to 36 ms | 11.6 to 15.8, 0.3 to 0.4%, 35 to 36 ms |
| Lab relay 1 cut | 2 | 1.0, 9.3%, 39 ms | **0.5 (2 of 5 downloads failed), 36.9%, 2833 ms** |
| Lab relay 2 cut | 1 | 0.6 (1 of 5 failed), 17.2%, 44 ms | **0.4 (2 of 4 failed), 66.2%, 3032 ms** |
| All cuts removed | 9 | 16.1, 7.0%, 35 ms | 16.2, 11.7%, 38 ms |

The full per-step tables are in `tables.md`.

- **With 2 and 1 relays left, the fixed build did worse than the build before the fix.** Ping loss was
  37% and 66% against 9% and 17%, and ping round trips rose to about 3 s.
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
- **The ladder does not test 9, 8, ... 4 working relays.** A session in this lab effectively uses the 3
  lab relays; the public relays only matter as replacements. The same holds for the test of 2026-11-23.
  A real 9-relay ladder needs the exit to have channels to all 9.
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
