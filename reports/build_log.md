# Build log

Each entry: date, phase, what was done, data counts, problems, open decisions. Newest last.

## 2026-10-20 — Phase 0: environment

- Created the repo skeleton, `pyproject.toml` (Python >= 3.11; pandas, numpy,
  scipy, duckdb, pyarrow, statsmodels, linearmodels, matplotlib, requests, pyyaml, yfinance, pypdf;
  dev: pytest, ruff), `.gitignore` (provided), `.env.example`. `git init` (local only, no remote).
- `git check-ignore` confirms `_private/` (local planning notes), `.env` and `data/*` are
  ignored.
- **Problem:** the project folder path is long enough that `pip` fails on Windows' 260-character
  path limit when installing into `.venv/` inside the repo. The virtual environment therefore
  lives at a short path outside the repo (Python 3.12.10). On a machine with a shorter path,
  or with long paths enabled, `python -m venv .venv` in the repo works as documented.
- Unit tests for the estimators (`tests/test_measures.py`, 11 tests) pass.

Source checks before coding (all 2026-10-20):
- FINRA Query API `otcMarket/weeklySummary`: **public access works without credentials.** Max 5,000
  records per call; sorting needs both partition keys (`weekStartDate`, `tierIdentifier`) as
  equality filters, so the loader requests one week x one tier x one record type at a time. An
  empty result returns HTTP 204. Tier codes `T1`, `T2`.
- Reg SHO consolidated daily file `CNMSshvolYYYYMMDD.txt` reachable; fields
  `Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market`.
- SEC staff memo downloaded (26 pages; dated **September 10, 2026** inside, file name ...090926).
  Tables 1–3 are images; targets were read from the rendered pages and recorded with page
  numbers in `configs/reconciliation_targets.yaml`. Tolerances were set before any comparison.
- The memo lists **four** overnight ATSs (BLUE, BOSS, IEOS, MOON). The original plan named three. IBKR Eos
  (IEOS) is an overnight-only ATS in the FINRA file too, so it is included
  (`configs/overnight_venues.yaml`, `include: true`); it can be switched off.
- Venue hours confirmed from each venue's latest Form ATS-N on EDGAR (cached in
  `data/raw/sec/ats_n/`). MOON operates from 7:30 pm and IEOS from 6:00 pm on holiday sessions, so
  their weekly volume slightly overstates 8 pm–4 am volume (documented in the YAML).
- Nasdaq earnings calendar: robots.txt asks for a 30-second crawl delay (about 18 hours for
  2018–2026 by date), and historical rows often say `time-not-supplied`. **Decision:** use
  yfinance `get_earnings_dates` (per ticker, ET timestamps back to ~2014) as the earnings source.
- Sample: weeks 2023-01-02 to **2026-09-28** (latest NMS Tier 1 week published as of 2026-10-20).
  Latest Tier 2 week: 2026-09-14.

## 2026-10-20 — Pre-A1 checks (requested before A1)

**Repo location.** The repo was first built in a temporary working folder on branch `main`;
the intended destination folder did not exist on this machine. Open decision: which folder to
use (asked). `git config core.longpaths true` set locally (long path).

**Blue Ocean gap: no pull problem.** Code: `src/offhours/analysis/checks.py` ->
`reports/tables/checks.json`.
- (a) Live re-pull of every record for each overnight MPID, both tiers, weeks overlapping Aug 2026
  (40 venue-week-tiers): rows = API record-total; summed ATS_W_SMBL_FIRM = ATS_W_FIRM in shares and
  notional (`pull_complete_live`: pass). Same identity on every cached overnight venue-week-tier
  (`pull_complete_cached`: pass, 842 venue-week-tiers when run). The loader now stores
  record-total and raises if a pull returns fewer rows.
- (b) FINRA week = Monday-Friday trade dates; overnight sessions are reported for the next trade
  date, so the week of Aug 3 holds the Sun Aug 2 to Thu Aug 6 night sessions. All four complete
  August weeks have 5 trading days (`week_convention`: pass). `lastReportedDate` = last update
  sent by the firm (API spec v0.4), so later dates are corrections.
- (c) **Cause of the "7x" gap: Tier 2.** 83% of overnight-venue shares in Aug 2026 are Tier 2
  stocks (`tier_coverage`); Blue Ocean, week of Aug 3: T1 68.5M + T2 430.9M shares. My earlier
  warning compared a Tier 1-only weekly total to the memo's all-NMS daily average; it was wrong.
- (d) Definitions compared in `checks.json` -> `definitions`. With T1+T2 the four complete August
  weeks give an overnight-ATS ADV about 13% below the memo, by a similar proportion for every
  venue and in dollars. The missing trade date (Aug 31) cannot close it (`window_bound`).
  Remaining candidates (Rule 4552 self-reports vs CAT-linked TRF reports incl. suppressed
  reports; revisions) cannot be verified with public data -> recorded under `open_gaps`, test
  stays a failure.
- The FINRA monthly dataset (`monthlySummary`) holds only non-ATS OTC volume, so it cannot be
  used for a calendar-month ATS check.

**Test rule changed** (`tests/test_reconciliation.py`): a gap is xfail only if
`documented_gaps.<target>.verified_by` names a check in `checks.json` with status `pass`;
otherwise it fails (a reason without a verifying check is printed but does not excuse).
Unit-tested (`test_explained_requires_passing_check`).

**Bugs found and fixed.**
- YAML read `111.5e6`-style targets as strings (YAML 1.1 needs `e+6`); targets rewritten as plain
  numbers; new test `test_targets_are_numbers`.
- First version of `pull_complete_cached` raced with the running download (loaded symbol and
  venue files at different times); now reads one file-list snapshot.
- A3: flag-contradicting events must be removed only after the "within one day of an
  announcement" baseline exclusion, otherwise their neighbours leak into the baseline. Fixed.

**Earnings timing flag.** Code: `src/offhours/analysis/earnings_check.py` (runs in the store
phase) -> `reports/tables/earnings_timing_check.csv`, `earnings_timing_summary.json`.
Primary test compares the two candidate nights (the flag decides which night carries the
news): contradiction = |other night| > |news night|. The literal form of the request
(AMC: |night after t| vs |day t|; BMO: the reverse) is reported too; for BMO it is weak because
BMO news lands in the night *into* t. Rule (config `earnings.drop_contradicting: true`): drop
contradicting after-close events from A3, no reclassification (reclassifying by returns selects
on the outcome); A3 re-run without the filter as robustness R5. Preliminary run on the first 330
tickers (2018 onward): 15.5% of after-close events contradict (6.9% among events with a clear
move); 20.2% of before-open events. Final shares come from the full run.

## 2026-10-20 — Repo moved

Repo moved to its permanent local folder (branch `main`, cloned with its history from the
temporary working folder; `_private/` and `.env` copied, both still ignored). The editable
install points here; the data store stays outside the repo (`OFFHOURS_DATA_DIR` in `.env`), so
a synced folder holds code and
reports only. Tests: 21 passed, 1 skipped (reconciliation, before A1).
Data status: FINRA weekly (2023-01-02 to 2026-09-28, T1; T2 to 2026-09-14), Reg SHO and prices
downloaded; earnings dates still downloading. Next: finish earnings, store build, A1.

## 2026-10-20 — Blue Ocean check rerun on complete FINRA data

`offhours.analysis.checks` rerun after the FINRA download finished: all checks pass
(`pull_complete_cached` now covers 1,082 venue-week-tiers, 0 mismatches). Blue Ocean, four
complete Aug 2026 weeks (20 nights): Tier 1 only 12.7M shares/night (-86% vs memo 93.7M);
Tier 1 + Tier 2 81.3M/night (-13%), $3.66B/night vs memo $4.2B (-13%). All four venues
96.5M/night vs memo ATS 111.5M (-13.4%). The large gap was the omitted Tier 2; the residual
~13% stays an open (failing) gap. Old repo copy in the temporary working folder kept until the
GitHub push is confirmed by the user.

## 2026-10-20 — Tiers, NMS denominator, test statuses (requested before A1)

**Tiers.** A1 rewritten: every market-level fact and every reconciliation uses Tier 1 + Tier 2,
restricted to weeks with both tiers published (194 weeks, 2023-01-02 to 2026-09-14; Tier 1 alone
runs to 2026-09-28). ETP flags now cover every overnight symbol in both tiers
(`symbols_overnight`). The stock-level ETP comparison needs prices, so it moved to A2
(`a2_etp_vs_common_tier1`). A2 and A3 stay on Tier 1. Tier 1 coverage by venue:
`reports/tables/a1_tier_coverage.csv` (Tier 1 is a small minority of overnight shares but a
majority of overnight dollars), shown in README and the note's Data section via generated
blocks (`src/offhours/docs.py`).

**NMS denominator.** Source: Cboe Exchange, Inc., U.S. equities historical market volume
(`src/offhours/data/cboe.py`; yearly CSVs on cdn.cboe.com, from UTDF/CTS consolidated feeds,
all exchanges + FINRA TRFs; robots.txt-disallowed path not used; citation requested). Aug 2026
average 16.38B shares/day over 21 days, close to the sum of the memo's session totals.
The memo's 0.9% numerator includes non-ATS overnight volume, which is not public by session, so
`overnight_share_of_nms_volume` is marked **not reproducible**; an ATS-only share of Cboe volume
is reported descriptively in `a1_summary.json`. `top10_share_rth` is also not reproducible
(needs RTH volume by symbol for all NMS stocks). No approximation is reconciled.

**Test statuses** (replaces the previous rule; tolerances unchanged): pass / explained (strict
xfail naming a passing check) / open (strict xfail, reason "OPEN GAP ...") / not reproducible
(skip). Logic in `src/offhours/reconciliation.py`, unit-tested. New `tests/test_docs.py` fails if
any open gap or not-reproducible target is missing from README.md or the note's Limitations
section, or if the tier-coverage statement is missing from README or the note's Data section.
README.md and reports/note/note.md created (skeleton; results pending).
Tests: 25 passed, 1 skipped (reconciliation rows appear after A1 runs).

## 2026-10-20 — Phase 1 complete: data, store, audit

Downloads finished (all cached under `$OFFHOURS_DATA_DIR/raw`): FINRA weekly (2,342
requests; T1 weeks 2023-01-02 to 2026-09-28, T2 to 2026-09-14), Reg SHO (962 trading days),
Cboe NMS volume (2022-01-03 to 2026-10-19), Yahoo prices (3,188 of 3,393 Tier 1 symbols; the rest
mostly delisted), Yahoo earnings dates (1,208 common stocks). Store built; counts, coverage,
missing weeks, venues and venue hours in `reports/data_audit.md`.
- Schema check caught duplicate keys in FINRA files (rows differing only in the encoding of
  the issue name, e.g. LND on BLUE, T2, week of 2024-07-01). Merged by summing
  (`store.collapse_duplicates`), which keeps symbol sums = venue totals; counts in the audit.
- Denominator check: 10 of 191,917 Tier 1 stock-weeks have overnight-venue shares above Yahoo
  consolidated weekly volume; listed in `a2_denominator_violations.csv` after A2.
- All integrity checks pass on the complete data (`checks.json`).
- Open item for robustness R3: BOSS has 1 and MOON 3 weeks without Tier 1 rows after they
  started (audit); check against venue notices before treating them as outages.

**Earnings timing, final** (`earnings_timing_check.csv`, 2018 onward): after-close 17,837 events,
15.4% contradict the flag (7.0% among clear moves), 2,753 dropped under the stated rule;
before-open 16,684 events, 19.4% contradict.

## 2026-10-20 — Phase 2 complete: A1 (Tier 1 + Tier 2)

`python -m offhours.pipeline --phase a1`: tables `a1_weekly`, `a1_venue_shares`,
`a1_tier_coverage`, `a1_summary.json`, `a1_reconciliation`; figures fig1-fig3.
Reconciliation (Aug 2026, four complete weeks, 20 trade dates): pass for all four venue ADVs,
Y/Y growth, top-10 and top-100 overnight shares; open for `ats_adv_overnight` (-13.4%) and
`ats_advt_overnight` (-13.1%, same shortfall in dollars, added to `open_gaps`); not reproducible:
`overnight_share_of_nms_volume`, `top10_share_rth`. README and note gap/coverage blocks
regenerated. Tests: 32 passed, 2 skipped, 2 xfailed (open gaps). Next: A2.

## 2026-10-20 — Phase 3 complete: A2 (Tier 1 stock-week panel)

`python -m offhours.pipeline --phase a2`: `a2_regressions.md/.csv` (pooled OLS, stock FE,
stock + week FE; two-way clustered SEs), `a2_diagnostics.md/.csv`, `a2_descriptives.csv`,
`a2_etp_vs_common_tier1.csv`, `a2_denominator_violations.csv`, `a2_summary.json`.
Panel: 551,003 stock-weeks, 3,180 Tier 1 symbols, 196 weeks (561,358 rows before dropping
missing lags). Outcome mean 0.026 pp, median 0; 65% of stock-weeks have no overnight trading;
the top 0.1% of stock-weeks carry about a fifth of the outcome's sum. 10 denominator violations
(overnight shares above Yahoo weekly volume) set to missing.

**Problems found.** (1) Pooled column was labelled "R2 (within)"; fixed (label now states
overall vs within). (2) 3-decimal formatting hid coefficients; now 4 decimals. (3) Extreme
values: top overnight shares are thinly traded crypto/commodity/China ETPs (genuine); NFE shows a
$0.006 close and 683% weekly RV (likely a Yahoo reverse-split error) - not removed; D1 shows
winsorized results.

**Decision (disclosed in the table note):** diagnostics D1-D4 (winsorized 1/99; common stocks;
ETPs; extensive-margin LPM) were added *after* seeing the main results and the outcome
distribution, so they are labelled as not pre-specified. The main table is unchanged from the
pre-specified design.

Results (associations): earnings week robustly positive in all specifications; off-exchange
short share robustly negative on the intensive margin; log price positive within stock but
negative across stocks; dollar volume matters mainly on the extensive margin; volatility and
past returns mostly insignificant; ETPs much higher in the pooled cross-section. Within-stock
R2 is small. Relative magnitudes in `a2_summary.json` (`relative_to_mean_two_way`).
Tests: 34 passed, 2 skipped, 2 xfailed.

## 2026-10-20 — Phase 4 complete: A3 (after-close earnings, Tier 1 common stocks)

`python -m offhours.pipeline --phase a3`: `a3_efficiency.md/.csv`, `a3_wpc.csv`,
`a3_event_list.csv`, `a3_summary.json`, figures fig4 (binscatter) and fig5 (WPC by tercile).
Events: 7,108 after-close announcements, 682 stocks, 2023-01-23 to 2026-10-01; dropped 1,097
flag-contradicting events (stated rule) and 119 nights with |r| > 0.5. Baseline: 968,153
non-earnings nights, 1,139 stocks.

Results (associations):
- Earnings nights: slight continuation, b on r_n = +0.019 (p = 0.10). Higher pre-event
  intensity goes with less continuation: r_n x intensity = -0.188 (p = 0.03).
- Non-earnings nights: partial reversal, b = -0.126 (p < 0.10); intensity interaction n.s.
  Pooled triple interaction r_n x intensity x earnings = -0.225 (p = 0.01).
- WPC of the night (earnings): 0.65 / 0.68 / 0.77 by intensity tercile, stock-bootstrap CIs of
  terciles 1 and 3 do not overlap; baseline nights 0.22 / 0.21 / 0.25.
- Tercile interaction (col. 3): r_n x top tercile -0.041, not significant.
- **Size confound:** rank correlation of intensity with pre-event log dollar volume = 0.64;
  with r_n x size added (col. 4) the intensity interaction is -0.137 and not significant.
  Intensity and size cannot be separated in this design; robustness R1 (size terciles) and R2
  (2018-2020 placebo) are the next tests.

Problems / open decisions: intensity is zero for 36% of events, so tercile cut-offs are 0 and
0.002 pp and the continuous interaction leans on a long tail (as in A2). Binscatter (fig4) is
too noisy to be informative; fig5 carries the WPC result. Tests: 34 passed, 2 skipped,
2 xfailed.

## 2026-10-20 — Phase 5a: robustness checks R1-R5

`python -m offhours.pipeline --phase robust`: `robustness.md/.csv`, `robustness_placebo_wpc.csv`,
`robustness_summary.json`. Coefficient = r_n x intensity unless stated; SEs clustered by stock
and date.
- R1 size terciles: interaction +0.56 (p 0.69) small, -1.28 (p 0.002) middle, -0.11 (p 0.19)
  large. Not consistent across size groups.
- R2 placebo (2018-2020 after-close events, stocks classified by their 2023+ average overnight
  share; same timing-flag filter as A3 in both periods): night WPC by stock-type tercile
  0.58 / 0.65 / 0.71 in 2018-2020 vs 0.62 / 0.69 / 0.76 from 2023. Change in the top-minus-bottom
  gap = +0.009, stock-bootstrap 95% CI [-0.055, 0.076] (`measures.wpc_gap_change`, added for
  this check, unit-tested). Regression form: r_n x top type tercile +0.095 (p 0.015) in
  2018-2020, -0.007 (p 0.83) from 2023.
- R3 excluding the BLUE outage weeks and the 4 weeks after (186 events): -0.184 (p 0.03).
  BOSS/MOON weeks without Tier 1 rows (audit) not verified as outages, so not excluded.
- R4 alternative intensity: log(1 + avg overnight shares) -0.0053 (p 0.04); percentile rank
  within event week -0.043 (p 0.25).
- R5 without the timing-flag filter (8,205 events): -0.198 (p 0.02).

**Reading.** The A3 intensity association survives the outage exclusion, the timing filter and a
log transform, but not a size control, a rank measure, or the placebo: the gradient in
opening-price completeness across stock types already existed in 2018-2020 and did not widen
after overnight ATS trading grew. The evidence points to stock type (size and related traits),
not overnight trading. Write-up must say this plainly.

**Fixed:** `a3.validated_after_close` returned an object-dtype flag, so `~` produced integers
(robustness crashed; main A3 cast to bool and was unaffected). Now returns bool.

## 2026-10-20 — Phases 5 and 6 complete: note, brief, headline figures, README, CI

- `src/offhours/report.py` builds a fact table from `reports/tables/` (each fact records its
  source file) and renders `src/offhours/templates/{note,brief}.md` into `reports/note/`
  and `reports/headline_figures.md` (5 headline results, each with numbers, files and code).
  Templates reference facts by name; an unknown name raises, so no number is typed by hand.
  Each document ends with its source files. README results, coverage and gaps blocks are
  generated the same way (`src/offhours/docs.py`).
- Note (~4 pages): question, data (with tier coverage), method, results, limitations (open and
  not-reproducible gaps), policy implications, references. Brief (~2 pages, non-technical).
  The price-discovery result is reported as a null: the association reflects stock type.
- Self-review fixes before committing: removed hand-derived or unsupported phrases ("about a
  quarter", "about a fifth", ETP underlying claim, "thin displayed liquidity"); "likely cause"
  of the open gap reworded as an unverified candidate; doubled negatives; p-value style.
- PDF not produced: pandoc is not installed on this machine.
- CI: a clean clone with an empty `OFFHOURS_DATA_DIR`, no `.env` and no `_private/` passes ruff
  and pytest (Python 3.12 locally; the workflow uses 3.11, which is not installed here, so the
  first GitHub run is the 3.11 check). Temporary check folder kept outside the repo.
- Tests: 45 passed, 2 skipped (not reproducible), 2 xfailed (open gaps).
- Open: GitHub repository not created and nothing pushed yet.

## 2026-10-21 — Published

Before publishing: project instructions file untracked (`.gitignore`), local paths and private
references removed from tracked files, the headline-figures file given a neutral name, MIT
`LICENSE` and CI badge added, and history rebuilt as a single commit authored with a GitHub
noreply address. Pushed `main` to https://github.com/Siavash1368/offhours-market-structure
(public). First CI run (Python 3.11, ruff + pytest on fixtures and committed tables, no
network): success.
