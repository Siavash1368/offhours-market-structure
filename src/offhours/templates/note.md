# Who prices the stock when the exchange is closed? Overnight ATS trading and price discovery around earnings

*Independent research on public data (FINRA, Cboe, Yahoo Finance). No CAT or other non-public
data. All results are associations. Code and data lineage: this repository.*

## 1. Question

Trading in US NMS stocks between 8 pm and 4 am ET now runs every weeknight on four
overnight-only alternative trading systems. The SEC staff's September 2026 memo for the 24-hour
trading roundtable documents how much trades overnight and who trades, but does not ask what
overnight trading does for prices. This note asks two questions with public data:

1. **Which stocks trade overnight?** How large, how concentrated and how fast-growing is the
   overnight session, and which stock characteristics go with a higher overnight share?
2. **Is more overnight trading associated with better price discovery?** After an earnings
   announcement released after the close, does the next morning's opening price capture more of
   the information in stocks that trade more overnight?

## 2. Data

**Overnight volume.** FINRA publishes weekly volume by symbol for every ATS (Rule 4552). Four
ATSs operate only overnight: Blue Ocean (BLUE), Bruce (BOSS), IBKR Eos (IEOS) and MOON; their
operating hours are taken from each venue's Form ATS-N. Their weekly volume is overnight volume.
MOON opens at 7:30 pm and IBKR Eos at 6 pm on holiday evenings, so the measure slightly overstates
8 pm-4 am trading. Non-ATS overnight trading (a material part of overnight volume in the SEC
memo's Table 1) is not public by session and is excluded throughout.

**Other sources.** Cboe's consolidated U.S. equities volume files give total NMS share and dollar
volume by day (source: Cboe Exchange, Inc.). FINRA's daily Reg SHO files give off-exchange
short-sale volume. Yahoo Finance gives daily prices and earnings dates with announcement times.
The store holds {rows_all} rows, including {rows_ovn} overnight-venue symbol-week records.
Before use, the FINRA pulls were checked for truncation and internal consistency (symbol rows sum
to venue totals in all {ck_venue_weeks} cached venue-week-tier totals) and the earnings timing flags were
checked against returns ({et_amc_contra} of {et_amc} after-close events have a larger move in the
night before the announcement than after it; these are dropped from the event study).

**Sample.** Market-level facts use NMS Tier 1 + Tier 2 for the {a1_weeks} weeks from
{a1_first_week} to {a1_last_week}. The stock-level analyses use Tier 1 only (S&P 500, Russell 1000
and selected exchange-traded products), where prices and earnings data are cleaner.

**Tier coverage.** Tier 2 stocks carry most overnight *share* volume but Tier 1 carries most
overnight *dollar* volume (table below). The market-level facts and the reconciliation to the
SEC staff memo use Tier 1 + Tier 2. The stock-level analyses use Tier 1 only, so they describe
Tier 1 stocks, not the overnight market as a whole.

<!-- BEGIN GENERATED:coverage -->
<!-- END GENERATED:coverage -->

## 3. Method

**Stylized facts and reconciliation (A1).** Weekly overnight volume, its share of NMS volume,
concentration across symbols (top-10 and top-100 shares, Herfindahl index) and venue shares.
Each comparable figure in the SEC memo was reconciled using the memo's definitions as far as
public data allow, with tolerances fixed before any comparison.

**Who trades overnight (A2).** A stock-week panel of Tier 1 stocks: overnight share = overnight-ATS
shares / consolidated weekly shares, regressed on lagged log price, lagged log dollar volume,
lagged realized volatility and absolute return, an earnings-week dummy and the lagged
off-exchange short-volume share. Estimator: OLS with stock and week fixed effects, standard
errors clustered by stock and by week (pooled OLS and stock-only fixed effects alongside).

**Price discovery around earnings (A3).** For an after-close announcement on day t, the night
return is r_n = ln(Open(t+1) / Close(t)) and the next session's return is
r_d = ln(Close(t+1) / Open(t+1)). Regressing r_d on r_n measures opening-price efficiency: a
positive slope means the opening price under-reacts and the day continues the move; a negative
slope means it over-reacts and reverses. The slope is interacted with overnight-trading
intensity, the stock's average overnight share over the four weeks before the event week
(pre-determined). The weighted price contribution (WPC) of the night, the share of the
close-to-close move already in the opening price (Barclay and Warner 1993; van Bommel 2011), is
computed by intensity tercile with stock-bootstrap intervals. Ordinary nights of the same stocks
form the baseline. Standard errors are clustered by stock and date.

## 4. Results

### 4.1 The overnight session is small, fast-growing and concentrated

Overnight ATS volume rose from {adv_first} million shares per night in the first 13 weeks of the
sample to {adv_last} million in the last 13, about {adv_growth_x} times. That is {share_nms_last}
of NMS share volume and {dshare_nms_last} of dollar volume in the last 13 weeks (up from
{share_nms_first}). Growth was not smooth (Figure 1): volume collapsed after Blue Ocean's outage
of 5 August 2024 and stayed low while Korean brokers suspended their US overnight service, then
jumped when that service resumed in late 2025.

![Figure 1](../figures/fig1_overnight_adv_by_venue.png)

Activity is concentrated in a few names: the ten most active symbols take {top10_last} of weekly
overnight volume and the top 100 take {top100_last}, although about {ovn_symbols_last} symbols
trade on an average week. Exchange-traded products account for {etp_share_last} of overnight
volume. One venue dominates: in {last_quarter} Blue Ocean had {vs_BLUE} of overnight-ATS
volume, Bruce {vs_BOSS}, IBKR Eos {vs_IEOS} and MOON {vs_MOON}.

**Reconciliation.** Of {rec_n} figures in the SEC memo, {rec_reproducible} can be built from
public data and {rec_pass} of those match within tolerance, including each venue's average volume,
year-on-year growth ({rec_yoy_ours} against the memo's {rec_yoy_memo}) and the top-10 share
({rec_top10_ours} against {rec_top10_memo}). Total overnight-ATS volume is {rec_adv_short} below the
memo ({rec_adv_ours} against {rec_adv_memo} million shares per night) and dollar volume
{rec_advt_short} below; the shortfall is similar for every venue. The checks rule out truncated pulls,
missing tiers, partial weeks and the one missing trade date. A candidate cause, which public
data cannot verify, is that FINRA's weekly figures are ATS self-reports while the memo builds
volume from CAT-linked trade reports. Two memo figures cannot be reproduced with public data (Section 5).

### 4.2 Who trades overnight

In Tier 1, overnight trading is sparse: the mean overnight share is {a2_mean} percent of weekly
volume and {a2_zero} of stock-weeks have none. Within a stock, the overnight share is {a2_earn_pct}
higher in earnings weeks (p {a2_earn_p}), and earnings weeks raise the chance of any overnight
trading by {a2_d4_earn} percentage points. A one-standard-deviation rise in the off-exchange
short-volume share goes with a {a2_short_pct} lower overnight share. In the cross-section,
being an exchange-traded product adds {a2_etp_rel} times the mean overnight share. Volatility and
past returns add
little, and the characteristics explain little of the within-stock variation (within R-squared
{a2_r2}). These estimates were checked against winsorized data, separate common-stock and ETP
samples and an any-trading model; the earnings and short-share associations hold in all of them.

### 4.3 Overnight trading and price discovery around earnings

The event study covers {a3_events} after-close announcements by {a3_stocks} Tier 1 common stocks.
On earnings nights the opening price under-reacts slightly (slope {a3_b}, p {a3_b_p}); on ordinary
nights it over-reacts and partly reverses (slope {a3_base_b}). The opening price contains
{wpc_earn_all} of the close-to-close move on earnings nights, against {wpc_base_all} on ordinary
nights.

At first sight, overnight trading helps. Stocks with more overnight trading before the
announcement show less continuation after the open (interaction {a3_c}, p {a3_c_p}), and the WPC
of the night rises across intensity terciles from {wpc_earnings_1} to {wpc_earnings_2} to
{wpc_earnings_3} (Figure 2). The association is specific to earnings nights (difference from
ordinary nights {a3_triple}, p {a3_triple_p}).

![Figure 2](../figures/fig5_wpc_by_tercile.png)

**It does not survive the tests for stock type.** Overnight intensity is strongly related to firm
size (rank correlation {a3_corr_size}), and {a3_zero_I} of events have no overnight trading at all.

- *Size.* Allowing the slope to vary with size, the intensity interaction falls to {a3_size_c}
  (p {a3_size_c_p}). Within size terciles it is {r1_c1} (p {r1_p1}), {r1_c2} (p {r1_p2}) and
  {r1_c3} (p {r1_p3}): no consistent pattern.
- *Rank measure.* With intensity measured as a percentile rank, which is not driven by a few
  high-intensity stocks, the interaction is not significant (p {r4_rank_p}).
- *Placebo.* Classifying stocks by their later (2023 onward) overnight intensity and going back to
  2018-2020 earnings, before overnight ATS trading existed at scale (the SEC memo's overnight
  series starts in July 2021, and in early 2023 overnight-ATS volume was still {share_nms_first}
  of NMS volume), the same gradient appears:
  the WPC of the night was {pl_pre_1} in the lowest tercile and {pl_pre_3} in the highest, against
  {pl_post_1} and {pl_post_3} from 2023. The high-minus-low gap changed by {pl_gap}
  (95% interval {pl_gap_lo} to {pl_gap_hi}).

The interaction does survive excluding the outage weeks ({r3_c}, p {r3_p}) and keeping the events
whose timing flags look wrong ({r5_c}, p {r5_p}), but these do not address the stock-type problem.
**The evidence points to stock type, not overnight trading:** the stocks that now trade overnight
already had more informative opening prices after earnings before the overnight venues grew, and
the gap has not widened since.

## 5. Limitations

<!-- BEGIN GENERATED:gaps -->
<!-- END GENERATED:gaps -->

Beyond these: (i) public data are weekly and ATS-only; non-ATS overnight trades and the timing of
trades within the night are not observed, so the night return mixes the after-hours (4-8 pm),
overnight and pre-market (4-9:30 am) sessions; (ii) the stock-level results cover Tier 1, which is
{t1_sh_shares} of overnight shares and {t1_sh_dollars} of overnight dollars; (iii) Yahoo earnings
timestamps can be wrong, which is why flag-contradicting events are dropped (results are the same
without the filter); (iv) the design cannot separate overnight trading from the traits of the
stocks that attract it; a design using variation in venue access, such as the Korean brokers'
suspension and return, would be needed for causal claims.

## 6. Policy implications

**Overnight consolidated data.** The overnight session is now a measurable fraction of NMS
volume and concentrated in one venue, yet public data describe it only weekly, by ATS and
without session timing. The SIPs' planned overnight operation (from December 2026 per the memo)
will cover quotes and trades in real time; a public, delayed, session-level aggregate of ATS and
non-ATS volume would let outside researchers measure overnight liquidity and price discovery
directly and close the reconciliation gaps documented here.

**Investor protection.** With {vs_BLUE} of overnight-ATS volume on one venue, a single outage can
stop the session, as in August 2024, when trades were cancelled after execution. Overnight
volume is concentrated in exchange-traded products and in low-priced Tier 2 stocks, whose
overnight liquidity public data cannot measure. This note finds no evidence that overnight trading itself
makes post-earnings opening prices more efficient; arguments for extended hours that rest on
better price discovery are not supported by these data, though the design cannot rule out
effects too small to detect.

## References

- Barclay, M. and Hendershott, T. (2003). Price discovery and trading after hours. *Review of
  Financial Studies* 16(4).
- Barclay, M. and Warner, J. (1993). Stealth trading and volatility. *Journal of Financial
  Economics* 34.
- Cameron, A. C., Gelbach, J. and Miller, D. (2011). Robust inference with multiway clustering.
  *Journal of Business and Economic Statistics* 29(2).
- Cboe Exchange, Inc. U.S. equities historical market volume data.
- FINRA. OTC (ATS and non-ATS) transparency data; Reg SHO daily short-sale volume files.
- SEC Division of Trading and Markets (2026). Staff memorandum, Roundtable on Preparations for
  24-Hour Trading Supporting Data, File No. 4-913, 10 September 2026.
- van Bommel, J. (2011). Measuring price discovery: the variance ratio, the R2, and the weighted
  price contribution. *Finance Research Letters* 8(3).
