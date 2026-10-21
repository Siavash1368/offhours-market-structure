# Table A2b. Diagnostics

| | (D1) Winsorized 1/99 | (D2) Common stocks | (D3) ETPs | (D4) Any overnight trading (LPM) |
|---|---|---|---|---|
| log price (t-1) | 0.0159*** | 0.0293* | 0.0268 | 0.6905 |
| | (0.0039) | (0.0174) | (0.0233) | (1.0420) |
| log dollar volume (t-1) | 0.0039*** | 0.0041 | 0.0028 | 3.5879*** |
| | (0.0007) | (0.0133) | (0.0025) | (0.2758) |
| realized vol., % (t-1) | 0.0018*** | 0.0002 | 0.0055** | 0.0874 |
| | (0.0004) | (0.0002) | (0.0026) | (0.1068) |
| |weekly return|, % (t-1) | -0.0002 | -0.0002 | -0.0001 | 0.0925** |
| | (0.0002) | (0.0002) | (0.0013) | (0.0444) |
| earnings week | 0.0048*** | 0.0052*** |  | 5.5574*** |
| | (0.0006) | (0.0016) |  | (0.8295) |
| off-exch. short share, % (t-1) | -0.0001*** | -0.0002*** | -0.0001*** | -0.0016 |
| | (0.0000) | (0.0001) | (0.0000) | (0.0057) |
| Fixed effects | stock, week | stock, week | stock, week | stock, week |
| Observations | 551,003 | 210,418 | 340,585 | 551,003 |
| Stocks | 3,180 | 1,133 | 2,047 | 3,180 |
| Weeks | 196 | 196 | 196 | 196 |
| R2 (overall if no FE, else within) | 0.030 | 0.016 | 0.003 | 0.030 |
| Mean of outcome | 0.016 | 0.016 | 0.032 | 34.744 |

Diagnostics for Table A2, column (3) specification (stock and week fixed effects, standard errors clustered by stock and week). **Added after inspecting the main results and the outcome distribution** (65% zeros; the top 0.1% of stock-weeks carry about a fifth of the outcome's sum), so they are not pre-specified. D1 winsorizes the outcome and continuous regressors at the 1st/99th percentiles; D2/D3 split common stocks and ETPs; D4 is a linear probability model for any overnight-venue trading, in percentage points. Source: `src/offhours/analysis/a2_panel.py` (`diagnostics`).
