# Overnight stock trading: what public data show (brief)

*Independent research on public FINRA, Cboe and market data. Two-page summary of the research
note (`reports/note/note.md`). Findings are associations, not causal effects.*

## Why it matters

US stocks now trade every weeknight between 8 pm and 4 am on four alternative trading systems
that operate only overnight. Regulators are preparing for longer trading days, and the SIPs plan
overnight operation. The SEC staff's September 2026 memo measured how much trades overnight.
This brief adds two questions: which stocks trade overnight, and does overnight trading make
prices more accurate when news arrives after the close?

## What we found

**1. Overnight trading has grown fast but is still small.** Overnight volume on these venues rose
from {adv_first} million shares a night to {adv_last} million, about {adv_growth_x} times, over
the {a1_weeks} weeks to {a1_last_week}. That is still only {share_nms_last} of all US stock-trading
volume (shares) and {dshare_nms_last} by value.

**2. It is concentrated: a few names, a few products, one venue.** Ten stocks and funds account for
{top10_last} of overnight volume in a typical week. Exchange-traded funds are {etp_share_last} of
it. One venue, Blue Ocean, handles {vs_BLUE}. When that venue failed on 5 August 2024, the
overnight session stopped and trades were cancelled.

**3. Most overnight shares are in smaller, low-priced stocks, but most overnight dollars are in
large ones.** Large-company stocks (NMS Tier 1) are {t1_sh_shares} of overnight shares but
{t1_sh_dollars} of overnight dollars.

**4. Overnight trading rises around news.** In large-company stocks, the overnight share of trading
is {a2_earn_pct} higher in weeks with an earnings announcement.

**5. No evidence that overnight trading makes post-earnings prices more accurate.** After
{a3_events} earnings announcements released after the close, stocks with more overnight trading
did have opening prices that captured more of the eventual price move ({wpc_earnings_3} of it in
the most-traded third, {wpc_earnings_1} in the least). But the same stocks showed the same pattern
in 2018-2020, before overnight trading existed at scale ({pl_pre_3} against {pl_pre_1}), and the
gap has not changed since. The difference reflects the kind of stock (mostly larger companies),
not the overnight trading.

## How sure are we

- We matched {rec_pass} of the {rec_reproducible} SEC memo figures that public data can rebuild.
  Our total overnight volume is {rec_adv_gap} below the memo; we checked our data pulls and
  believe the gap comes from differences between the public weekly reports and the regulators'
  audit-trail data. Two memo figures cannot be rebuilt from public data at all.
- Public data are weekly and do not show the exact time of trades or overnight trades outside
  these four venues. The price-discovery result covers large-company stocks only.
- The study can show what goes together, not what causes what.

## What it suggests for policy

- **Data.** A public, session-level summary of overnight volume, covering ATS and other
  off-exchange trades, would let outside researchers measure overnight liquidity and price
  discovery directly.
- **Resilience.** With most overnight volume on one venue, the session's reliability depends on
  that venue's systems; the August 2024 failure is the example.
- **Claims about benefits.** Arguments that extended hours improve price discovery after news are
  not supported by these public data, although effects too small to detect cannot be ruled out.
