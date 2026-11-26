# Per-step tables

Made with `repro/relay-fault-n9/ladder-pack.py` and `sets-pack.py` from the raw run folders.

## Downloads, ping, frames

### 2026-11-26-ladder9-before

| step | relays left | downloads done/started | Mbit/s min | median | max | ping loss | ping median ms | frames discarded/emitted | judged dead, revived |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 9 | 9/9 | 8.3 | 11.4 | 16.3 | 0.4% | 34.7 | 0/0 | 0, 0 |
| cut relay1 | 8 | 10/10 | 1.1 | 14.7 | 21.4 | 2.0% | 35.9 | 79/12266 | 2, 1 |
| cut relay2 | 7 | 8/8 | 1.0 | 2.2 | 9.6 | 2.5% | 36.8 | 183/13534 | 1, 0 |
| cut relay3 | 6 | 5/6 | 0.8 | 1.8 | 1.9 | 10.8% | 39.5 | 516/10737 | 1, 0 |
| cut relay4 | 5 | 4/5 | 0.4 | 0.6 | 1.2 | 8.6% | 41.3 | 530/9705 | 2, 1 |
| cut relay5 | 4 | 0/6 | - | - | - | 90.3% | 53.1 | 126/1378 | 2, 1 |
| cut relay6 | 3 | 0/6 | - | - | - | 100.0% | - | 0/0 | 0, 0 |
| cut relay7 | 2 | 0/6 | - | - | - | 100.0% | - | 0/0 | 0, 0 |
| cut relay8 | 1 | 0/7 | - | - | - | 100.0% | - | 0/0 | 0, 0 |
| all cuts removed | 9 | 1/5 | 7.6 | 7.6 | 7.6 | 95.1% | 37.5 | 0/0 | 0, 5 |

### 2026-11-26-ladder9-after

| step | relays left | downloads done/started | Mbit/s min | median | max | ping loss | ping median ms | frames discarded/emitted | judged dead, revived |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 9 | 10/10 | 8.9 | 13.6 | 19.7 | 0.4% | 35.4 | 0/0 | 0, 0 |
| cut relay1 | 8 | 10/10 | 8.4 | 10.7 | 18.3 | 0.5% | 36.1 | 11/1781 | 2, 1 |
| cut relay2 | 7 | 10/10 | 4.0 | 9.8 | 20.1 | 1.2% | 36.2 | 353/8312 | 1, 0 |
| cut relay3 | 6 | 9/9 | 3.8 | 14.3 | 19.4 | 0.4% | 35.9 | 142/12275 | 1, 0 |
| cut relay4 | 5 | 9/9 | 1.4 | 8.4 | 19.1 | 1.5% | 36.4 | 193/7297 | 1, 0 |
| cut relay5 | 4 | 10/10 | 2.4 | 8.5 | 18.3 | 1.7% | 35.7 | 29/10509 | 1, 0 |
| cut relay6 | 3 | 9/9 | 3.4 | 10.3 | 16.2 | 7.0% | 37.2 | 246/7076 | 2, 1 |
| cut relay7 | 2 | 9/9 | 1.1 | 8.3 | 18.2 | 3.0% | 37.9 | 424/8432 | 1, 0 |
| cut relay8 | 1 | 8/8 | 0.4 | 9.6 | 15.8 | 11.0% | 37.0 | 209/8981 | 1, 0 |
| all cuts removed | 9 | 10/10 | 8.7 | 10.5 | 20.5 | 1.9% | 35.9 | 0/0 | 0, 8 |

### 2026-11-26-brutal9-before

| step | relays left | downloads done/started | Mbit/s min | median | max | ping loss | ping median ms | frames discarded/emitted | judged dead, revived |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 9 | 9/9 | 9.3 | 15.5 | 18.1 | 0.4% | 35.5 | 0/0 | 0, 0 |
| cut relay1..relay1 | 8 | 9/9 | 1.9 | 9.8 | 17.4 | 2.6% | 36.5 | 232/8877 | 1, 0 |
| restored after 1 | 9 | 10/10 | 8.7 | 15.3 | 19.2 | 0.4% | 35.0 | 0/0 | 0, 1 |
| cut relay1..relay2 | 7 | 9/9 | 0.9 | 10.7 | 17.0 | 1.8% | 37.0 | 224/12703 | 2, 0 |
| restored after 2 | 9 | 10/10 | 8.4 | 10.5 | 17.3 | 0.4% | 34.7 | 1/1744 | 0, 2 |
| cut relay1..relay3 | 6 | 7/7 | 0.5 | 8.2 | 11.3 | 4.9% | 37.8 | 259/7556 | 3, 0 |
| restored after 3 | 9 | 10/10 | 7.9 | 10.7 | 17.8 | 0.3% | 35.2 | 1/1742 | 0, 3 |
| cut relay1..relay4 | 5 | 8/8 | 0.7 | 2.8 | 16.9 | 4.9% | 38.4 | 663/9162 | 4, 0 |
| restored after 4 | 9 | 9/9 | 11.8 | 14.8 | 17.3 | 0.3% | 36.1 | 25/1790 | 0, 4 |
| cut relay1..relay5 | 4 | 7/7 | 0.4 | 1.3 | 11.2 | 9.1% | 39.1 | 398/6252 | 7, 2 |
| restored after 5 | 9 | 9/9 | 8.6 | 14.6 | 18.8 | 0.3% | 35.7 | 41/5407 | 0, 5 |
| cut relay1..relay6 | 3 | 0/6 | - | - | - | 99.5% | 1612.0 | 131/99 | 4, 0 |
| restored after 6 | 9 | 5/8 | 8.4 | 16.9 | 17.7 | 25.4% | 35.8 | 0/0 | 0, 4 |
| cut relay1..relay7 | 2 | 0/5 | - | - | - | 100.0% | - | 178/621 | 2, 1 |
| restored after 7 | 9 | 7/8 | 0.6 | 10.5 | 20.4 | 24.4% | 36.4 | 0/0 | 0, 1 |
| cut relay1..relay8 | 1 | 0/6 | - | - | - | 99.9% | 40.0 | 81/79 | 1, 0 |
| all cuts removed | 9 | 6/8 | 7.2 | 14.6 | 19.7 | 39.3% | 35.7 | 0/0 | 0, 1 |

### 2026-11-26-brutal9-after

| step | relays left | downloads done/started | Mbit/s min | median | max | ping loss | ping median ms | frames discarded/emitted | judged dead, revived |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 9 | 9/9 | 8.2 | 12.7 | 19.4 | 0.4% | 35.7 | 0/0 | 0, 0 |
| cut relay1..relay1 | 8 | 10/10 | 7.1 | 10.6 | 18.1 | 0.6% | 36.0 | 7/5290 | 2, 1 |
| restored after 1 | 9 | 9/9 | 8.1 | 10.8 | 17.3 | 0.4% | 35.8 | 0/0 | 0, 1 |
| cut relay1..relay2 | 7 | 10/10 | 2.3 | 13.3 | 18.3 | 1.0% | 35.6 | 62/7014 | 2, 0 |
| restored after 2 | 9 | 10/10 | 7.7 | 13.9 | 18.0 | 0.3% | 36.0 | 0/0 | 0, 2 |
| cut relay1..relay3 | 6 | 10/10 | 4.8 | 8.0 | 18.8 | 3.4% | 35.9 | 175/8871 | 3, 0 |
| restored after 3 | 9 | 9/9 | 8.4 | 13.5 | 17.9 | 0.3% | 36.3 | 0/0 | 0, 3 |
| cut relay1..relay4 | 5 | 10/10 | 1.5 | 9.4 | 20.6 | 1.5% | 36.1 | 211/10080 | 4, 0 |
| restored after 4 | 9 | 10/10 | 8.0 | 15.7 | 20.6 | 0.4% | 35.9 | 2/3527 | 0, 4 |
| cut relay1..relay5 | 4 | 9/9 | 2.8 | 6.1 | 14.1 | 6.7% | 37.0 | 361/12074 | 6, 1 |
| restored after 5 | 9 | 9/9 | 7.8 | 14.3 | 17.9 | 0.3% | 35.1 | 3/1962 | 0, 5 |
| cut relay1..relay6 | 3 | 8/8 | 0.5 | 4.9 | 20.1 | 16.5% | 42.6 | 260/9230 | 8, 2 |
| restored after 6 | 9 | 9/9 | 10.6 | 15.9 | 19.6 | 0.3% | 35.6 | 1/1774 | 0, 6 |
| cut relay1..relay7 | 2 | 9/9 | 0.8 | 9.0 | 18.0 | 5.4% | 36.4 | 148/7374 | 8, 1 |
| restored after 7 | 9 | 10/10 | 10.5 | 15.7 | 19.8 | 0.4% | 35.9 | 0/0 | 0, 7 |
| cut relay1..relay8 | 1 | 0/6 | - | - | - | 99.6% | 283.0 | 41/1641 | 2, 0 |
| all cuts removed | 9 | 7/8 | 1.6 | 10.9 | 17.1 | 27.5% | 36.9 | 0/0 | 0, 2 |

## Share of the client's path sets on relays that still work

### 2026-11-26-ladder9-before

| step | relays cut | forward: slots on working relays | forward: weight on working relays | return: slots on working relays | return: weight on working relays |
| --- | --- | --- | --- | --- | --- |
| baseline | 0 | 100% | 100% | 100% | 100% |
| relay1 | 1 | 74% | 98% | 91% | 100% |
| relay2 | 2 | 40% | 94% | 83% | 99% |
| relay3 | 3 | 33% | 94% | 67% | 98% |
| relay4 | 4 | 33% | 94% | 55% | 97% |
| relay5 | 5 | 5% | 52% | 44% | 96% |
| relay6 | 6 | 0% | 0% | 32% | 74% |
| relay7 | 7 | 0% | 0% | 22% | 44% |
| relay8 | 8 | 0% | 0% | 11% | 22% |
| all cuts removed | 0 | 100% | 100% | 100% | 100% |

### 2026-11-26-ladder9-after

| step | relays cut | forward: slots on working relays | forward: weight on working relays | return: slots on working relays | return: weight on working relays |
| --- | --- | --- | --- | --- | --- |
| baseline | 0 | 100% | 100% | 100% | 100% |
| relay1 | 1 | 99% | 100% | 98% | 100% |
| relay2 | 2 | 95% | 100% | 96% | 100% |
| relay3 | 3 | 95% | 100% | 94% | 99% |
| relay4 | 4 | 96% | 100% | 91% | 100% |
| relay5 | 5 | 91% | 99% | 91% | 100% |
| relay6 | 6 | 83% | 99% | 82% | 100% |
| relay7 | 7 | 72% | 100% | 71% | 100% |
| relay8 | 8 | 60% | 100% | 54% | 100% |
| all cuts removed | 0 | 100% | 100% | 100% | 100% |

### 2026-11-26-brutal9-before

| step | relays cut | forward: slots on working relays | forward: weight on working relays | return: slots on working relays | return: weight on working relays |
| --- | --- | --- | --- | --- | --- |
| baseline | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay1 | 1 | 87% | 98% | 96% | 100% |
| restored after 1 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay2 | 2 | 88% | 100% | 87% | 98% |
| restored after 2 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay3 | 3 | 87% | 98% | 74% | 96% |
| restored after 3 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay4 | 4 | 86% | 98% | 62% | 92% |
| restored after 4 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay5 | 5 | 60% | 90% | 57% | 90% |
| restored after 5 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay6 | 6 | 40% | 72% | 35% | 50% |
| restored after 6 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay7 | 7 | 0% | 0% | 23% | 24% |
| restored after 7 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay8 | 8 | 0% | 0% | 13% | 15% |
| all cuts removed | 0 | 100% | 100% | 100% | 100% |

### 2026-11-26-brutal9-after

| step | relays cut | forward: slots on working relays | forward: weight on working relays | return: slots on working relays | return: weight on working relays |
| --- | --- | --- | --- | --- | --- |
| baseline | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay1 | 1 | 100% | 100% | 97% | 99% |
| restored after 1 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay2 | 2 | 100% | 100% | 95% | 99% |
| restored after 2 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay3 | 3 | 100% | 100% | 92% | 98% |
| restored after 3 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay4 | 4 | 100% | 100% | 88% | 95% |
| restored after 4 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay5 | 5 | 100% | 100% | 86% | 95% |
| restored after 5 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay6 | 6 | 78% | 85% | 77% | 87% |
| restored after 6 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay7 | 7 | 80% | 95% | 75% | 92% |
| restored after 7 | 0 | 100% | 100% | 100% | 100% |
| cut relay1..relay8 | 8 | 33% | 33% | 10% | 14% |
| all cuts removed | 0 | 100% | 100% | 100% | 100% |
