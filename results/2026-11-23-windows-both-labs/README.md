# 2026-11-23: the patched Windows client against both lab exits, with normal routing

**Measured:** four connects of a Windows client (a machine on AWS), alternating between the Frankfurt and
the New York lab exit, each followed at once by a 100 MB download. The client had no channels to the
labs' relays and no relay allow-list: it reached the exits through public relays. The lab recorded the
exits' side: their payment counters before and after the run and, per session, when the deposit was seen
and confirmed. Hold and attach times, downloads and timeouts were reported by the session that ran the
client; the lab did not measure them.

**Repository commit:** `1fe9aa3` in the first lab's folder and `65f4c82` (branch `lab2`) in the second
lab's, clean working trees. No `./lab` command was used: the counters and logs were read by hand.

**Result:** Four of four connected, paid through the side-car and completed the download without a
stall. Neither exit's payment gate held any traffic. In one connect the tunnel attached 3.5 s before the
exit had confirmed the deposit.

## The run

Build 0.2.6 of the Windows client: `gnosis_vpn-client` at `8a0e3be` with the side-car and hold commits
cherry-picked (`98de0384`), hoprnet master `ff0076ef`, hopr-strategy `2c209bd3` (the fix for deposits
the client does not record, as revised upstream). 01:30 to 01:43 UTC.

| Connect | Exit | Hold lasted | Exit confirmed the deposit, after the client's deposit | Against the tunnel attaching | Download |
| --- | --- | --- | --- | --- | --- |
| 1 | Frankfurt | 42.2 s | 22.6 s | 4.2 s before | 100 MB, no stall |
| 2 | New York | 47.2 s | 26.3 s | 0.5 s before | 100 MB, no stall |
| 3 | Frankfurt | 47.2 s | 26.0 s | **3.5 s after** | 100 MB, no stall |
| 4 | New York | about 43 s | 18.5 s | about 6 s before | 100 MB, no stall |

Exit counters over the run (01:28 to 01:44 UTC):

| Exit | Payment gate blocks | Seconds held | Packets sent before a deposit | Packets sent as funded |
| --- | --- | --- | --- | --- |
| Frankfurt | 0 | 0.0 | 25 | 201,729 |
| New York | 0 | 0.0 | 0 | 161,587 |

- **A client without channels to a lab's relays can use its exit.** The lab exits have return channels
  only to their own three relays; the client found those paths by itself. No session-open timeout was
  reported.
- **The fixed 22 s wait of the hold was too short in connect 3** and nearly so in connect 2. The 25
  packets Frankfurt sent before a deposit are that gap. Nothing was held, because a new session still
  has its whole free allowance of 10,000 packets.
- **The counters also cover one connect of a phone** to the Frankfurt exit at 01:33 UTC
  ([relay-blackhole-android](../2026-11-23-relay-blackhole-android/README.md)); its tunnel attached after
  the exit's confirmation.
- **The exit discarded few of this client's frames:** 11 % and 0 % in the two windows reported for
  connect 1, against 26 to 39 % for the two Android clients on the same exit that night.

## Not shown by this run

- **Four connects, one evening.**
- **Client-side numbers are second-hand,** from the Windows session's own test.
- **Which public relays the client used** was not recorded here. By the Android session's report its
  node had no channel to the two relays that lost an Android client's traffic the same night.

## Files

| File | Content |
| --- | --- |
| `sessions.csv` | Per connect: the client's hold, deposit and attach times as reported, and the exit's commitment, note and confirmation times from its log |
| `exit-counters.csv` | Both exits' payment-gate and packet counters before and after the run |
