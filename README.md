# offhours-market-structure

[![ci](https://github.com/Siavash1368/offhours-market-structure/actions/workflows/ci.yml/badge.svg)](https://github.com/Siavash1368/offhours-market-structure/actions/workflows/ci.yml)

Independent research on public data about overnight (8 pm–4 am ET) trading of US NMS stocks on
alternative trading systems (ATSs). Two questions: which stocks trade overnight, and whether more
overnight trading goes with better price discovery around after-close earnings announcements.
No CAT or other non-public data; results are associations, not causal effects.

**Status:** Study A complete (data, A1–A3, robustness, note and brief). Studies on tokenized
equities and order-level data are not part of this build.

## Results

<!-- BEGIN GENERATED:summary -->
Main results (every number generated from `reports/tables/` by `src/offhours/report.py`):

- **Growth.** Overnight-ATS volume rose from 2.6M to 121M shares per night
  (47x) between the first and last 13 of 194 weeks (2023-01-02 to
  2026-09-14); 0.68% of NMS share volume and 0.53% of dollar volume
  in the last 13 weeks.
- **Concentration.** Top-10 symbols: 46.1% of overnight volume; ETPs 47.3%;
  Blue Ocean 82.5% of overnight-ATS volume in 2026Q3.
- **Reconciliation to the SEC staff memo.** 7 of 9 reproducible figures
  within pre-set tolerances; 2 open gaps; 2 not reproducible (below).
- **Who trades overnight (Tier 1 panel, 551,003 stock-weeks).** Overnight share 21%
  higher in earnings weeks; lower with a higher off-exchange short share; little explained
  within stocks.
- **Price discovery (7,108 after-close earnings events).** Opening prices capture more of
  the move in stocks with more overnight trading (0.77 vs 0.65), but the
  same gap existed in 2018-2020 (change +0.009, 95% CI -0.055 to +0.076): it
  reflects stock type, not overnight trading.

Documents: [research note](reports/note/note.md), [two-page brief](reports/note/brief.md),
[data audit](reports/data_audit.md), [build log](reports/build_log.md).
<!-- END GENERATED:summary -->

## Data

| Source | Use |
|---|---|
| FINRA OTC Transparency weekly ATS data (Query API `otcMarket/weeklySummary`) | Overnight volume = weekly volume on the overnight-only ATSs BLUE, BOSS, IEOS, MOON (`configs/overnight_venues.yaml`, hours from Form ATS-N) |
| FINRA Reg SHO daily short-sale volume | Off-exchange short share (A2) |
| Cboe Exchange, Inc., U.S. equities historical market volume | Daily consolidated NMS share and dollar volume (A1 denominator) |
| Yahoo Finance via yfinance | Daily OHLCV and earnings dates (Tier 1 symbols) |
| SEC staff memo, Overnight Trading Roundtable (Sept 2026) | Published figures to reconcile to (`configs/reconciliation_targets.yaml`) |

**Tier coverage.** NMS Tier 2 stocks carry most overnight *share* volume, while Tier 1 carries
most overnight *dollar* volume (table below): Tier 2 overnight trading is concentrated in
low-priced stocks. A1 (market-level facts and every reconciliation) uses Tier 1 + Tier 2. A2 and
A3 use Tier 1 only, because prices and earnings dates are cleaner for Tier 1 and FINRA publishes
it with a 2-week delay instead of 4. A2 and A3 therefore describe Tier 1 stocks, not the
overnight market as a whole.

<!-- BEGIN GENERATED:coverage -->
Tier 1 share of overnight-ATS volume (A2 and A3 use Tier 1 only; A1 uses both tiers). Source: `reports/tables/a1_tier_coverage.csv`.

| Period | Venue | Tier 1 share of shares | Tier 1 share of dollars |
|---|---|---|---|
| full sample (both-tier weeks) | BLUE | 14.2% | 62.4% |
| full sample (both-tier weeks) | BOSS | 17.9% | 63.7% |
| full sample (both-tier weeks) | IEOS | 23.9% | 69.1% |
| full sample (both-tier weeks) | MOON | 11.9% | 54.6% |
| full sample (both-tier weeks) | ALL | 14.7% | 62.7% |
| 2026-08 (complete weeks) | BLUE | 15.6% | 62.3% |
| 2026-08 (complete weeks) | BOSS | 22.2% | 65.7% |
| 2026-08 (complete weeks) | IEOS | 22.9% | 66.9% |
| 2026-08 (complete weeks) | MOON | 18.0% | 58.8% |
| 2026-08 (complete weeks) | ALL | 16.6% | 62.9% |
| last 13 both-tier weeks | BLUE | 13.8% | 61.2% |
| last 13 both-tier weeks | BOSS | 18.3% | 63.9% |
| last 13 both-tier weeks | IEOS | 17.1% | 66.0% |
| last 13 both-tier weeks | MOON | 11.9% | 51.5% |
| last 13 both-tier weeks | ALL | 14.3% | 61.5% |
<!-- END GENERATED:coverage -->

## Known gaps and figures not reproducible with public data

<!-- BEGIN GENERATED:gaps -->
Reconciliation targets from the SEC staff memo (Sept 2026) that this repo does not match. Gaps: `reports/tables/a1_reconciliation.csv`; reasons: `configs/reconciliation_targets.yaml`; checks: `reports/tables/checks.json`.

- `ats_adv_overnight` (open gap). Memo 1.115e+08, ours 9.654e+07 (-13.4%). Weekly ATS data (T1+T2, four complete Aug 2026 weeks) are below the memo's ATS ADV by a similar proportion for every venue and in dollars. Ruled out by checks: truncated or incomplete pulls (pull_complete_live, pull_complete_cached), missing Tier 2 (tier_coverage), partial weeks (week_convention), the missing trade date Aug 31 (window_bound). Remaining candidates, not verifiable with public data: Rule 4552 ATS self-reports vs CAT-linked TRF reports (incl. suppressed reports), revisions after publication.
- `ats_advt_overnight` (open gap). Memo 5.2e+09, ours 4.517e+09 (-13.1%). Same shortfall as ats_adv_overnight, in dollars: the share and dollar gaps are nearly equal, so it is not a price or tier-mix effect. Same checks and same unverified candidates.
- `overnight_share_of_nms_volume` (not reproducible). The memo's numerator is all overnight-session volume, ATS and non-ATS (non-ATS = 33.1M of 144.6M shares/day, Table 1). Non-ATS OTC volume is public only weekly and not by session, so the numerator cannot be built. The denominator can (Cboe consolidated NMS volume).
- `top10_share_rth` (not reproducible). Needs regular-trading-hours share volume by symbol for all NMS stocks. Public daily volume mixes sessions, and prices were downloaded for Tier 1 symbols only, so neither the top-10 set nor its RTH volume can be built.
<!-- END GENERATED:gaps -->

## Rebuild

```
python -m venv .venv
.venv\Scripts\activate            # Windows; source .venv/bin/activate elsewhere
pip install -e ".[dev]"
python -m offhours.pipeline --phase all
pytest -q
```

`--phase` takes `data`, `store`, `a1`, `a2`, `a3`, `robust`, `report` or `all`. Downloads are
cached in `data/raw/` and never fetched twice. Set `OFFHOURS_DATA_DIR` in `.env` to keep the data
store elsewhere (useful on Windows, where long paths can exceed 260 characters). No credentials
are needed; the FINRA weekly dataset is public.

## Tests

`pytest -q` runs estimator unit tests, synthetic end-to-end tests of A1–A3, and the
reconciliation to the SEC memo. Each reconciliation target has one status:

- **pass**: within the tolerance fixed in `configs/reconciliation_targets.yaml` before any comparison;
- **explained**: expected failure (`xfail`, strict) naming a passing check in `reports/tables/checks.json`;
- **open**: expected failure (`xfail`, strict), reason starts with `OPEN GAP` and prints the gap;
- **not reproducible**: skipped with the reason.

Every open gap and not-reproducible target must be listed above and in the note's limitations
section (`tests/test_docs.py`). CI (`.github/workflows/ci.yml`) runs `ruff` and `pytest` on a
synthetic fixture and the committed output tables; it needs no network and no data store.

## Repository layout

```
configs/            sample, venues (Form ATS-N hours), memo targets and gap statuses, outages
src/offhours/
  data/             one loader per source (FINRA weekly, Reg SHO, Cboe, Yahoo, symbol lists)
  store.py          Parquet tables + DuckDB views, schema checks
  measures.py       returns, overnight share, concentration, WPC (formulas in docstrings)
  analysis/         a1_facts, a2_panel, a3_earnings, robustness, checks, earnings_check, audit
  report.py         note, brief and headline_figures.md from output tables
  templates/        prose of the note and brief (numbers are placeholders)
tests/              unit, synthetic end-to-end, reconciliation and disclosure tests
notebooks/          display-only views of the outputs
reports/            tables/, figures/, note/, data_audit.md, build_log.md, headline_figures.md
```

Every number in the note, brief, README results and `reports/headline_figures.md` is generated
from `reports/tables/` by `src/offhours/report.py`; each document ends with its source files.

Cboe volume data: please cite Cboe Exchange, Inc. as the source.

## License

MIT (see `LICENSE`). Data are not redistributed; rebuild them from the public sources above.
