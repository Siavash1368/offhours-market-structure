# Robustness checks (A3)

Coefficient shown: r_n x intensity (R1, R3, R4) or r_n x top stock-type tercile (R2). Standard errors clustered by stock and date. Source: `src/offhours/analysis/robustness.py`.

| Check | Group | coef | se | p | N | b on r_n |
|---|---|---|---|---|---|---|
| A3 main (for reference) | all earnings events | -0.1885 | 0.0848 | 0.026 | 7,108 | 0.0240 |
| R1 size tercile | size tercile 1 | 0.5620 | 1.4020 | 0.689 | 2,370 | 0.0292 |
| R1 size tercile | size tercile 2 | -1.2832 | 0.4186 | 0.002 | 2,369 | 0.0249 |
| R1 size tercile | size tercile 3 | -0.1127 | 0.0850 | 0.185 | 2,369 | 0.0251 |
| R2 placebo | 2018-2020 (placebo) | 0.0948 | 0.0388 | 0.015 | 4,599 | -0.0588 |
| R2 placebo | 2023 onward | -0.0065 | 0.0303 | 0.830 | 7,121 | 0.0292 |
| R3 excl. outage weeks | 186 events dropped | -0.1836 | 0.0852 | 0.031 | 6,922 | 0.0215 |
| R4 alt. intensity | log(1 + avg overnight shares) | -0.0053 | 0.0026 | 0.044 | 7,108 | 0.0407 |
| R4 alt. intensity | percentile rank within event week | -0.0430 | 0.0376 | 0.253 | 7,108 | 0.0419 |
| R5 no timing-flag filter | all after-close events | -0.1978 | 0.0855 | 0.021 | 8,205 | 0.0223 |

## R2 placebo: night WPC by stock-type tercile

| period                                                             |   type_tercile |   wpc_night |   ci_lo |   ci_hi |   n_events |
|:-------------------------------------------------------------------|---------------:|------------:|--------:|--------:|-----------:|
| 2018-2020 (placebo)                                                |              1 |       0.580 |   0.535 |   0.617 |       1507 |
| 2018-2020 (placebo)                                                |              2 |       0.646 |   0.606 |   0.680 |       1412 |
| 2018-2020 (placebo)                                                |              3 |       0.713 |   0.682 |   0.744 |       1680 |
| 2023 onward                                                        |              1 |       0.616 |   0.585 |   0.645 |       2284 |
| 2023 onward                                                        |              2 |       0.685 |   0.656 |   0.717 |       2056 |
| 2023 onward                                                        |              3 |       0.758 |   0.736 |   0.779 |       2781 |
| change in top-minus-bottom gap, 2023 onward vs 2018-2020 (placebo) |              0 |       0.009 |  -0.055 |   0.076 |      11720 |
