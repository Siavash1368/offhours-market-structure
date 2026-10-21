# Data audit

Generated 2026-10-20 by `src/offhours/analysis/audit.py` from the Parquet store.

Sample weeks: **2023-01-02** to **2026-09-28** (FINRA week-start Mondays; latest NMS Tier 1 week published at build time).

## Tables

| Table | Rows | First | Last | Symbols/tickers |
|---|---|---|---|---|
| ats_overnight | 950,525 | 2023-01-02 | 2026-09-28 | 12,350 |
| ats_symbol (T1) | 436,353 | 2023-01-02 | 2026-09-28 | 3,393 |
| otc_symbol (T1) | 437,572 | 2023-01-02 | 2026-09-28 | 3,398 |
| ats_venue | 12,108 | 2023-01-02 | 2026-09-28 | 39 |
| regsho_daily | 10,033,384 | 2022-12-01 | 2026-10-02 | 19,187 |
| prices_daily | 5,450,832 | 2017-12-01 | 2026-10-05 | 3,188 |
| earnings | 50,326 | 2005-08-01 | 2027-02-22 | 1,208 |
| universe | 3,393 |  |  | 3,393 |

## Missing weeks

- T1 venue totals (ATS_W_FIRM), 2023-01-02 to 2026-09-28: 0 missing []
- T2 venue totals (ATS_W_FIRM), 2023-01-02 to 2026-09-14: 0 missing []
- BLUE (T1): first week 2023-01-02, last 2026-09-28, 196 weeks with data, 0 gaps after first
- BOSS (T1): first week 2025-03-10, last 2026-09-28, 81 weeks with data, 1 gaps after first
- IEOS (T1): first week 2023-01-02, last 2026-09-28, 196 weeks with data, 0 gaps after first
- MOON (T1): first week 2025-01-27, last 2026-09-28, 85 weeks with data, 3 gaps after first
- Reg SHO: 962 trading days; weekdays with no file (holidays): 40

## Venues found in the FINRA weekly file (Tier 1, sample period)

| MPID | Participant name | Overnight venue | Sample shares (bn) |
|---|---|---|---|
| UBSA | UBSA UBS ATS |  | 137.05 |
| INCR | INCR INTELLIGENT CROSS LLC |  | 136.91 |
| SGMT | SGMT SIGMA X2 |  | 89.89 |
| EBXL | EBXL LEVEL ATS |  | 72.72 |
| MLIX | MLIX INSTINCT X |  | 56.00 |
| MSPL | MSPL MS POOL (ATS-4) |  | 50.32 |
| MSTX | MSTX MS TRAJECTORY CROSS (ATS-1) |  | 48.39 |
| JPMX | JPMX JPM-X |  | 42.05 |
| BIDS | BIDS BIDS ATS |  | 33.98 |
| LATS | LATS THE BARCLAYS ATS |  | 31.78 |
| PURE | PURE PURESTREAM |  | 29.48 |
| CGXS | CGXS ONECHRONOS |  | 24.98 |
| KCGM | KCGM VIRTU MATCHIT ATS |  | 21.83 |
| JPBX | JPBX JPB-X |  | 20.67 |
| IATS | IATS IBKR ATS |  | 17.44 |
| XSTM | XSTM CROSSSTREAM |  | 15.18 |
| ITGP | ITGP POSIT |  | 15.03 |
| DLTA | DLTA DEALERWEB |  | 10.92 |
| ICBX | ICBX CBX |  | 10.26 |
| BNPX | BNPX BNPP CORTEX ATS |  | 8.40 |
| ONEC | ONEC CITI-ONE ATS |  | 8.20 |
| MSRP | MSRP MS RPOOL (ATS-6) |  | 7.46 |
| LQNA | LQNA LIQUIDNET H2O ATS |  | 6.47 |
| BLKX | BLKX INSTINET BLOCKCROSS |  | 5.26 |
| BLUE | BLUE BOATS | yes | 4.80 |
| CROS | CROS CROSSFINDER |  | 3.75 |
| LQNT | LQNT LIQUIDNET NEGOTIATION ATS |  | 2.14 |
| LMNX | LMNX LUMINEX ATS |  | 1.66 |
| CODA | CODA CODA MARKETS, INC. |  | 1.53 |
| ALPX | ALPX ALPHAX US |  | 1.02 |
| BOSS | BOSS BRUCE MARKETS, LLC. | yes | 0.41 |
| IEOS | IEOS IBKR EOS ATS | yes | 0.26 |
| STFX | STFX STIFEL X |  | 0.16 |
| MOON | MOON MOON ATS | yes | 0.11 |
| PJCX | PJCX XE |  | 0.01 |
| CODX | CODX CODA MARKETS, INC. |  | 0.01 |
| MOAT | MOAT MOSAIC ATS |  | 0.01 |
| MSAB | MSAB MS CLOSING CROSS (ATS-7) |  | 0.00 |

## Overnight venues: operating hours (Form ATS-N)

| MPID | Venue | Matching hours (ET) | Outside 8 pm-4 am | Source |
|---|---|---|---|---|
| BLUE | Blue Ocean ATS (BOATS) | 20:00-04:00 | None in normal operation. Matching may continue for < 1 minute after 04:00 while resting orders clear. | Form ATS-N/UA filed 2026-10-08, Part III Item 4(a); https://www.sec.gov/Archives/edgar/data/1795131/000090266426004092/primary_doc.xml |
| BOSS | Bruce ATS | 20:00-04:00 | None. Orders received outside operating hours are rejected; open orders expire at 04:00. | Form ATS-N/UA filed 2026-04-03; https://www.sec.gov/Archives/edgar/data/1767041/000176704126000004/primary_doc.xml |
| MOON | MOON ATS | 19:30-04:00 | Operates from 19:30, so up to 30 minutes per session fall in the SEC memo's Late Extended session (16:00-20:00). Weekly FINRA data cannot split this out, so MOON volume slightly overstates 8 pm-4 am volume. MOON is under 2% of overnight-ATS volume (memo Table 1), so the effect on totals is small. | Form ATS-N/UA filed 2026-07-29; https://www.sec.gov/Archives/edgar/data/1491895/000149189526000016/primary_doc.xml |
| IEOS | IBKR Eos ATS | 20:00-03:50 | Sessions that start on a day the NYSE is closed (holidays) trade from 18:00, so holiday evenings include up to 2 hours of 16:00-20:00 volume. Normal sessions end at 03:50. | Form ATS-N/MA filed 2026-06-24 and ATS-N/UA filed 2026-06-12; https://www.sec.gov/Archives/edgar/data/922792/000090266426002887/primary_doc.xml |

## Symbol coverage

- Tier 1 symbols in the sample: 3,393 (2,113 ETPs, 1,280 other)
- ETP flag source: {'nasdaqtrader': 3184, 'issue_name': 209}
- With Yahoo price data: 3,188 (94.0%)
- Common stocks with Yahoo earnings dates: 1,208 (94.4%)
- Earnings timing classes: {'after_close': 24995, 'before_open': 24525, 'during': 764, 'unknown': 42}
- Share of Tier 1 overnight-venue volume in symbols with price data: 99.5%

## Source quirks and other tables

- Rows sharing a table key in the FINRA files, merged by summing (store.py `collapse_duplicates`): {'ats_overnight': 2, 'ats_symbol': 48, 'otc_symbol': 50, 'ats_venue': 0}. Example: LND on BLUE, Tier 2, week of 2024-07-01, two rows differing only in the encoding of the issue name.
- Overnight symbols, both tiers: 12,350 (4,701 ETPs; ETP flag source {'nasdaqtrader': 9675, 'issue_name': 2675}).
- Cboe consolidated NMS volume: 1,203 trading days, 2022-01-03 to 2026-10-19 (source: Cboe Exchange, Inc.).

## Denominator check

- Stock-weeks with overnight-venue shares and price data: 191,917
- Overnight-venue shares exceed consolidated weekly volume: **10** (0.005%); listed in `reports/tables/a2_denominator_violations.csv`

Downloaded: FINRA weekly files and Yahoo data on the dates recorded in each cached file (`downloaded` field).
