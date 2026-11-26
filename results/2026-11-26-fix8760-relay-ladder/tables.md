
### 2026-11-26-ladder-before

| step | relays left | downloads done/started | Mbit/s min | median | max | ping loss | ping median ms | frames discarded/emitted | judged dead, revived |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 9 | 10/10 | 9.1 | 12.1 | 20.1 | 0.3% | 35.4 | 0/0 | 0, 0 |
| cut pub-880f | 8 | 10/10 | 8.5 | 15.7 | 20.3 | 0.4% | 35.4 | 0/0 | 0, 0 |
| cut pub-dac8 | 7 | 9/9 | 12.7 | 16.8 | 19.0 | 0.3% | 35.7 | 0/0 | 0, 0 |
| cut pub-1388 | 6 | 10/10 | 9.4 | 18.6 | 19.7 | 0.3% | 35.4 | 0/0 | 0, 0 |
| cut pub-d880 | 5 | 10/10 | 8.6 | 12.1 | 21.1 | 0.3% | 35.9 | 0/0 | 0, 0 |
| cut pub-5b7b | 4 | 10/10 | 8.4 | 15.9 | 19.7 | 0.4% | 35.7 | 0/0 | 0, 0 |
| cut pub-0d38 | 3 | 10/10 | 8.6 | 15.5 | 20.3 | 0.3% | 35.4 | 0/0 | 0, 0 |
| cut relay1 | 2 | 7/7 | 0.6 | 1.0 | 17.3 | 9.3% | 39.3 | 148/8568 | 2, 1 |
| cut relay2 | 1 | 4/5 | 0.4 | 0.6 | 0.9 | 17.2% | 43.8 | 389/8476 | 2, 1 |
| all cuts removed | 9 | 9/9 | 9.0 | 16.1 | 21.4 | 7.0% | 35.1 | 53/1420 | 0, 2 |

### 2026-11-26-ladder-after

| step | relays left | downloads done/started | Mbit/s min | median | max | ping loss | ping median ms | frames discarded/emitted | judged dead, revived |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 9 | 9/9 | 9.7 | 11.9 | 16.7 | 0.4% | 35.6 | 0/0 | 0, 0 |
| cut pub-880f | 8 | 10/10 | 8.4 | 15.0 | 19.6 | 0.3% | 36.1 | 0/0 | 0, 0 |
| cut pub-dac8 | 7 | 10/10 | 8.3 | 12.8 | 22.0 | 0.3% | 35.6 | 0/0 | 0, 0 |
| cut pub-1388 | 6 | 10/10 | 7.7 | 12.6 | 20.1 | 0.3% | 36.1 | 0/0 | 0, 0 |
| cut pub-d880 | 5 | 9/9 | 9.3 | 11.6 | 19.0 | 0.3% | 35.4 | 0/0 | 0, 0 |
| cut pub-5b7b | 4 | 10/10 | 7.8 | 11.9 | 18.6 | 0.3% | 35.9 | 0/0 | 0, 0 |
| cut pub-0d38 | 3 | 10/10 | 9.9 | 15.8 | 18.3 | 0.4% | 35.5 | 0/0 | 0, 0 |
| cut relay1 | 2 | 3/5 | 0.3 | 0.5 | 2.7 | 36.9% | 2833.0 | 64/3405 | 3, 2 |
| cut relay2 | 1 | 2/4 | 0.3 | 0.4 | 0.4 | 66.2% | 3032.0 | 334/2164 | 2, 1 |
| all cuts removed | 9 | 8/8 | 0.8 | 16.2 | 17.6 | 11.7% | 38.3 | 0/0 | 0, 2 |

### 2026-11-26-diag-after

| step | relays left | downloads done/started | Mbit/s min | median | max | ping loss | ping median ms | frames discarded/emitted | judged dead, revived |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 9 | 3/3 | 12.7 | 17.9 | 17.9 | 0.3% | 36.5 | 0/0 | 0, 0 |
| cut relay1 only | 8 | 8/8 | 2.3 | 8.2 | 17.8 | 1.2% | 40.0 | 22/5288 | 2, 1 |
| cut removed | 9 | 5/5 | 8.5 | 16.1 | 19.1 | 0.3% | 35.1 | 0/0 | 0, 1 |
| cut the 6 public relays | 3 | 5/5 | 8.6 | 9.0 | 18.4 | 0.3% | 36.3 | 0/0 | 0, 0 |
| cut relay1 too | 2 | 5/5 | 0.4 | 0.5 | 2.0 | 31.8% | 2834.0 | 19/5022 | 2, 1 |
| all cuts removed | 9 | 3/3 | 7.9 | 8.9 | 19.1 | 7.8% | 39.1 | 0/0 | 0, 1 |
