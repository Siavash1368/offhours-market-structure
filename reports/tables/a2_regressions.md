# Table A2. Who trades overnight? Stock-week panel

| | (1) Pooled OLS | (2) Stock FE | (3) Stock + week FE |
|---|---|---|---|
| constant | -0.1879*** |  |  |
| | (0.0329) |  |  |
| log price (t-1) | -0.0095*** | 0.0386*** | 0.0301*** |
| | (0.0020) | (0.0101) | (0.0104) |
| log dollar volume (t-1) | 0.0108*** | 0.0084*** | 0.0037 |
| | (0.0016) | (0.0024) | (0.0026) |
| realized vol., % (t-1) | 0.0075*** | 0.0010 | 0.0008 |
| | (0.0028) | (0.0007) | (0.0007) |
| |weekly return|, % (t-1) | -0.0000 | -0.0002 | -0.0001 |
| | (0.0012) | (0.0004) | (0.0004) |
| earnings week | 0.0068*** | 0.0051*** | 0.0054*** |
| | (0.0012) | (0.0009) | (0.0013) |
| off-exch. short share, % (t-1) | -0.0002*** | -0.0002*** | -0.0002*** |
| | (0.0000) | (0.0000) | (0.0000) |
| ETP | 0.0650*** |  |  |
| | (0.0094) |  |  |
| Fixed effects | none | stock | stock, week |
| Observations | 551,003 | 551,003 | 551,003 |
| Stocks | 3,180 | 3,180 | 3,180 |
| Weeks | 196 | 196 | 196 |
| R2 (overall if no FE, else within) | 0.018 | 0.004 | 0.004 |
| Mean of outcome | 0.026 | 0.026 | 0.026 |

NMS Tier 1 stocks and ETPs. Dependent variable: overnight-ATS share of consolidated weekly share volume, in percentage points (mean shown; median 0). Standard errors (in parentheses) clustered by stock and week. *** p<0.01, ** p<0.05, * p<0.10. Source: `src/offhours/analysis/a2_panel.py`.
