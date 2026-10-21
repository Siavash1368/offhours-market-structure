# Table A3a. Opening-price efficiency: r_d on r_n

| | (1) Earnings | (2) Earnings | (3) Earnings | (4) Earnings | (5) Non-earnings | (6) Pooled |
|---|---|---|---|---|---|---|
| constant | -0.001 | -0.001 | 0.001 | 0.023** | 0.000 | 0.000 |
| | (0.001) | (0.001) | (0.001) | (0.011) | (0.000) | (0.000) |
| night return r_n | 0.019* | 0.024** | 0.039* | 0.173 | -0.126* | -0.126* |
| | (0.011) | (0.012) | (0.024) | (0.203) | (0.064) | (0.064) |
| r_n x intensity (pp) |  | -0.188** |  | -0.137 | 0.037 | 0.037 |
| |  | (0.085) |  | (0.103) | (0.027) | (0.027) |
| intensity (pp) |  | -0.003 |  | 0.003 | -0.002 | -0.002 |
| |  | (0.007) |  | (0.007) | (0.002) | (0.002) |
| tercile 2 |  |  | -0.003** |  |  |  |
| |  |  | (0.002) |  |  |  |
| r_n x tercile 2 |  |  | -0.015 |  |  |  |
| |  |  | (0.029) |  |  |  |
| tercile 3 |  |  | -0.002 |  |  |  |
| |  |  | (0.002) |  |  |  |
| r_n x tercile 3 (highest) |  |  | -0.041 |  |  |  |
| |  |  | (0.026) |  |  |  |
| r_n x log dollar volume |  |  |  | -0.007 |  |  |
| |  |  |  | (0.010) |  |  |
| log dollar volume |  |  |  | -0.001** |  |  |
| |  |  |  | (0.001) |  |  |
| earnings night |  |  |  |  |  | -0.001 |
| |  |  |  |  |  | (0.001) |
| r_n x earnings night |  |  |  |  |  | 0.150** |
| |  |  |  |  |  | (0.065) |
| intensity x earnings |  |  |  |  |  | -0.001 |
| |  |  |  |  |  | (0.008) |
| r_n x intensity x earnings |  |  |  |  |  | -0.225*** |
| |  |  |  |  |  | (0.087) |
| Sample | earnings | earnings | earnings | earnings | non-earnings | pooled |
| Observations | 7,108 | 7,108 | 7,108 | 7,108 | 968,153 | 975,261 |
| Stocks | 682 | 682 | 682 | 682 | 1,139 | 1,139 |
| Dates | 588 | 588 | 588 | 588 | 928 | 928 |
| R2 | 0.001 | 0.002 | 0.002 | 0.003 | 0.006 | 0.006 |

Dependent variable: next-day session return r_d = ln(Close_{t+1}/Open_{t+1}). Intensity = average overnight-ATS share of weekly volume over the 4 weeks before the event week, in percentage points. Tercile cut-offs (earnings events): 0.000 and 0.002 pp. Standard errors clustered by stock and date. *** p<0.01, ** p<0.05, * p<0.10. Source: `src/offhours/analysis/a3_earnings.py`.
