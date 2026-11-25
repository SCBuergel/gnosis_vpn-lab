## cpu-threads-default: hoprd 5.0.6 4e33b1710ed27a95 cpu_threads=default vcpu=4
second client: connect1 at 18.8 s, disconnect1 at 49.0 s, connect2 at 63.0 s, disconnect2 at 93.4 s, connect3 at 106.6 s, disconnect3 at 136.8 s
exit finished a session's payment commitment at: 23.10 s, 67.35 s, 110.78 s
pings: 745 answered, 29 over 200 ms, max 1457 ms

| Stall: first ping sent | last ping back | length | commitment finished | SURB drop | busiest exit threads |
| --- | --- | --- | --- | --- | --- |
| 21.63 s | 23.10 s | 1.47 s | -0.01 s from its end | none within 0.5 s | 51 %, 50 %, 5 %, 5 % |
| 48.18 s | 50.73 s | 2.55 s | none within 0.5 s | -0.03 s from its end | 2 %, 1 %, 1 %, 1 % |
| 66.09 s | 67.36 s | 1.27 s | -0.00 s from its end | none within 0.5 s | 51 %, 51 %, 2 %, 2 % |
| 109.48 s | 110.78 s | 1.29 s | -0.00 s from its end | none within 0.5 s | 51 %, 51 %, 2 %, 2 % |

## cpu-threads-4: hoprd 5.0.6 4e33b1710ed27a95 cpu_threads=4 vcpu=4
second client: connect1 at 18.8 s, disconnect1 at 49.1 s, connect2 at 63.0 s, disconnect2 at 93.2 s, connect3 at 106.4 s, disconnect3 at 136.7 s
exit finished a session's payment commitment at: 23.09 s, 67.53 s, 87.58 s, 110.65 s
pings: 738 answered, 30 over 200 ms, max 1355 ms

| Stall: first ping sent | last ping back | length | commitment finished | SURB drop | busiest exit threads |
| --- | --- | --- | --- | --- | --- |
| 21.65 s | 23.02 s | 1.37 s | +0.07 s from its end | none within 0.5 s | 26 %, 26 %, 26 %, 24 % |
| 66.25 s | 67.46 s | 1.20 s | +0.07 s from its end | none within 0.5 s | 27 %, 27 %, 24 %, 23 % |
| 87.22 s | 88.11 s | 0.89 s | none within 0.5 s | none within 0.5 s | 17 %, 12 %, 12 %, 12 % |
| 109.31 s | 110.59 s | 1.28 s | +0.06 s from its end | none within 0.5 s | 25 %, 25 %, 25 %, 25 % |
| 132.24 s | 133.77 s | 1.53 s | none within 0.5 s | -0.04 s from its end | 3 %, 3 %, 2 %, 1 % |
| 136.28 s | 137.78 s | 1.50 s | none within 0.5 s | -0.04 s from its end | 3 %, 2 %, 1 %, 1 % |

