# Does post-earnings drift happen mostly after the stock clears its earnings-day high?

**Round 1 research assessment, final report.** Author: Lei Kam Fai (Woody). Data: Massive REST API (US equities) and SEC EDGAR. Code and logs: this repository. Written 13 September 2026.

## 1. Research question

After a strong earnings reaction, does the subsequent abnormal return arrive steadily from the next session, or is it concentrated after the stock first closes above the high of the reaction session? The question is about *when* any drift occurs, not how large it is.

## 2. Final hypothesis

**H1 (timing).** Among US common stocks whose day-0 abnormal return is in the top decile, the per-day abnormal return *after* the first close above the day-0 high exceeds the unconditional per-day abnormal return over the same event days. **H0.** Post-breakout per-day abnormal return equals the unconditional path. Secondary (the proposal's original formulation): a rule that waits for the breakout (Rule B) earns a higher window return than a rule that buys at the next open (Rule A).

Pre-registered ex-ante predictions (written in `docs/PLAN.md` before any result): if H1 holds, the primary statistic is positive with a season-bootstrap 95% CI excluding zero in both the selection and the hold-out period, and unanchored triggers (D1-D3) and a fixed-delay entry (Rule C) do not reproduce it. If the pattern appears equally for the unanchored triggers, the earnings-day high is not a special anchor. If it appears in the no-news placebo, it is mechanical.

## 3. Motivation and mechanism

Post-earnings-announcement drift is one of the oldest anomalies (Ball and Brown 1968; Bernard and Thomas 1989, 1990), but Martineau (2022) reports that it has vanished for large US stocks since about 2006. Practitioner material teaches buying the breakout from a post-earnings consolidation, which is rarely tested against a passive alternative. Two behavioural stories imply a late move: disposition-driven profit taking by holders sitting on gains absorbs demand until that supply clears (Frazzini 2006; Grinblatt and Han 2005), and a close above a salient reference price removes an anchor (George and Hwang 2004; Huddart, Lang and Yetman 2009 study exactly this for 52-week highs). Attention stories (DellaVigna and Pollet 2009; Hirshleifer, Lim and Teoh 2009) predict that any delayed reaction should be larger for Friday announcements. Note that this study sorts on the announcement return, not on the earnings surprise; Foster, Olsen and Shevlin (1984) found little short-horizon drift on that sort, and Chan, Jegadeesh and Lakonishok (1996) found it mainly at 6-12 months, so a small Rule A baseline was expected.

## 4. How the project differed from the proposal

Each change is also a dated row in `logs/decision_log.csv`.

| # | Proposal | What was found | Already tested when changed | Revised approach | Lesson |
|---|---|---|---|---|---|
| 1 | Classify before-open vs after-close reports by comparing the Massive 8-K Item 2.02 timestamp to 16:00 ET | Massive 8-K Disclosures, 8-K Text and SEC Index expose `filing_date` only; Disclosures start 2020-01-02 and tagged only 9 earnings releases among 205 classified filings on a peak earnings day | Docs read, live probes run, nothing modelled yet | SEC EDGAR submissions JSON: `acceptanceDateTime` and `items` for every 8-K; 321,077 Item 2.02 filings for 9,679 CIKs | Read field lists, not endpoint names; verify coverage on a known heavy day |
| 2 | Rank events into deciles within each quarter | The quarter's cross-section is unknown when early-season events trade (look-ahead) | Nothing run | Threshold = 90th percentile of day-0 abnormal returns over the previous four quarters, known at day 0 | Every selection rule must be computable at the trade date |
| 3 | "Rule B buys once the stock closes above its earnings-day high" | Trading at the signal close is unattainable; the difference between same-close and next-open entry is itself a timing result | Nothing run | All signal rules enter at the next open; a market-on-close variant is reported as implementation shortfall | Specify fills before specifying hypotheses |
| 4 | Rule B beats Rule A if drift is concentrated after the breakout | On every breakout event A = (run-up) x (post-breakout leg) and B = post-breakout leg only, so A > B by construction; B > A can only come from non-breakout events losing | Nothing run (found in design review) | Primary test = post-breakout per-day abnormal return minus the season- and event-day-matched unconditional path; B vs A kept as secondary with controls C and D1-D3 | Write the algebra of the comparison before writing code |
| 5 | Ticker Events for delistings | Ticker Events supports only symbol changes | Probe | All Tickers `active=false` (`delisted_utc`, `cik`); events mapped through CIK with symbol-reuse validity intervals | Survivorship protection has to be built, not asserted |
| 6 | NBBO quotes for spreads | Tick data infeasible on a 2.4 GiB disk and unnecessary | Probe | Corwin-Schultz (2012) high-low spread from the daily bars | Cost proxies from data already in hand |
| 7 | Benzinga Earnings and Income Statements as optional surprise measures | Benzinga returned HTTP 403 (not entitled) | Probe | Surprise measured by the price reaction only; standardised (z0) and fixed (5%) variants as robustness | Probe entitlements before designing around a dataset |

## 5. Data

**Massive (central).** Daily Market Summary, `adjusted=false`, one call per weekday 2004-01-02 to 2026-09-11 (5,988 calls, 23 yearly parquet files); the row date is the requested date, never the bar timestamp. All Tickers (36,588 rows; 11,929 US common stocks of which 6,609 are delisted). Splits (27,541 rows) used to split-adjust prices ourselves; the cumulative factors match the vendor's `historical_adjustment_factor` for all tickers once same-day double splits are ordered consistently, and our adjusted closes match vendor-adjusted per-ticker bars on split days (`tests/test_api_crosscheck.py`). Ten probe calls established plan history and entitlements (`outputs/probe_access.json`).

**External.** SEC EDGAR submissions API (`data.sec.gov/submissions/CIK##########.json`, with the required User-Agent, under 10 requests per second): every filing's acceptance timestamp (UTC), form and item list. 9,672 of 9,679 CIKs were found; 6,808 have at least one Item 2.02 8-K (the rest are mostly companies that delisted before Item 2.02 existed in August 2004). The data is public and point-in-time by construction: the acceptance time is when the filing became public.

**Cleaning and transformation.** Duplicate (ticker, date) rows removed; trading calendar = dates on which SPY has a bar; returns set to missing across calendar gaps; float32 storage; a 24.9-million-row panel of common stocks plus SPY with rolling pre-event statistics (`src/pead/panel.py`). Raw licensed data is git-ignored; only derived tables and figures are committed.

**Timestamps and information availability.** Day 0 is the first regular session that could react: acceptance before 09:30 ET maps to the same date, at or after 16:00 ET to the next trading day, and 09:30-16:00 ET is flagged `intraday` and excluded from the main sample (36,118 of 181,927 filtered filings). Validation: the absolute abnormal return peaks on the assigned day 0 for 64.8% of after-close and 63.5% of before-open events, on day +1 for 19.6% and 23.1%, and on day -1 for about 15% (`outputs/tables/timing_validation.csv`). The 8-K can lag the press release, so some events are dated one session late; that misdating affects Rule A and Rule B symmetrically and is a stated limitation. All filters use day -1 or earlier data; the selection threshold uses only previous quarters; Rule B's signal is a close and the fill is the next open.

## 6. Methodology

**Universe and filters.** US common stocks on NYSE, Nasdaq or NYSE American; unadjusted close on day -1 >= $5; median dollar volume over days -60..-1 >= $1 million; at least 120 prior bars. Delisted names are retained (21.7% of selected events are in tickers that no longer trade).

**Events.** 271,534 unique company-day-0 events after removing amendments and follow-up filings within 20 sessions; 142,358 pass the filters, are not intraday, and fall in the sample period 2005-01-03 to 2026-06-12; **14,770 selected events** (3,116 tickers, 86 quarters) have a day-0 abnormal return (close -1 to close 0, minus SPY) at or above the trailing-four-quarter 90th percentile (median threshold 8.1%; median event AR0 12.4%, median overnight gap 6.6%).

**Rules** (days are sessions after day 0; H = holding length, W = maximum wait).
- **A**: buy at open(1), sell at close(H).
- **B**: k = first day in 1..W with adjusted close > adjusted day-0 high; buy at open(k+1), sell at close(H); zero return if no breakout.
- **C**: buy at open(m+1) unconditionally, m = median k of Rule B in the selection period (m = 2).
- **D1/D2/D3**: as B with the level set to the day-0 close, 1.03 x day-0 high, and the day-1 high (trigger from day 2), i.e. levels that are not the earnings-day high.
- Abnormal return = stock minus SPY over the same open-to-close span. A stock whose bars end inside the window exits at its last close (17 events).

**Primary statistic.** For each breakout event with entry day e, the per-day abnormal return over days e..H minus the mean per-day abnormal return of *all* selected events in the same season over the same event days (the unconditional path). This removes the mechanical conditioning of the pre-breakout leg while matching season and event time.

**Inference.** Season = calendar quarter of day 0. Every headline number carries a 95% CI from a 5,000-draw block bootstrap over seasons (86 blocks), plus the share of seasons with a positive value. Calendar-time daily equal-weight portfolios of the A book, the B book and their difference (days with at least 10 open positions) are tested with Newey-West standard errors (lag = H).

**Parameters.** Two tunable parameters: W in {5, 10, 15, 20}, H in {20, 40, 60}. Pre-registered default (10, 40). The selection period 2005-2014 chooses the cell with the largest lower CI bound of the primary statistic; the hold-out period 2015-2026 is reported for that cell and for the default; the whole grid is disclosed. Fixed a priori: $5, $1M, 90th percentile, 60-day windows, 5 bp commission per side, Corwin-Schultz window days -25..-6. Parameter optimisation beyond this grid was deliberately not done: the question is descriptive and more tuning would only overfit a null result.

## 7. Main results (default cell W = 10, H = 40; full tables in `outputs/tables/`)

**Rule A baseline.** Mean CAR over 40 sessions is +0.55% [CI -0.50, +1.59] for 2005-2026, +1.43% [+0.57, +2.35] in 2005-2014 and +0.12% [-1.29, +1.55] in 2015-2026 (Figure 1). Drift after extreme positive reactions exists early in the sample and is absent afterwards, consistent with Martineau (2022).

**Breakouts.** 60.8% of events close above the day-0 high within 10 sessions; 44.9% of those do so on day 1 (Figure 4). Breakout timing depends heavily on where the day-0 close sits in the day-0 range: in the top tercile of range placement 72% break out with median k = 1, in the bottom tercile 46% with median k = 3.

**Decomposition** (Table: `main_summary_W10_H40.csv`). Breakout events earn +4.19% under Rule A but only +0.34% under Rule B; non-breakout events earn -5.10% under Rule A. Per day: the pre-breakout leg earns +2.28% per day (mechanical, it is conditioned on the crossing), the post-breakout leg +0.01% per day [-0.02, +0.03], non-breakout events -0.13% per day, all events +0.01% per day.

**Primary test.** Post-breakout per-day abnormal return minus the matched unconditional path: **-0.7 bp per day [CI -3.0, +1.6]** for 2005-2026; -0.0 bp [-3, +2] in the selection period and -1.6 bp [-5, +2] in the hold-out. Figure 2 shows daily abnormal returns aligned on the breakout day: a 365 bp spike on day k, then a path indistinguishable from the unconditional one from the entry open onwards (Figure 3). H1 is rejected; there is no concentration of drift after the breakout.

**Secondary: Rule B vs Rule A.** B minus A is -0.34% [-0.87, +0.20] overall, **-0.92% [-1.41, -0.46] in 2005-2014** (B wins in 28% of seasons) and -0.06% [-0.77, +0.67] in 2015-2026. Calendar-time: the A book earns 2.9 bp per day (Newey-West t = 2.5; 5.2 bp, t = 3.8 in 2005-2014; 0.8 bp, t = 0.5 after), the B book 1.1 bp (t = 1.6), and the daily difference -1.8 bp (t = -2.9). Waiting for the breakout forgoes the run-up and captures nothing extra.

**Controls.** The fixed-delay Rule C earns +0.45% (C minus A -0.09% [-0.25, +0.06]); the unanchored triggers D1, D2, D3 earn +0.40%, +0.08% and +0.12%, and in the selection period their shortfalls against A (-0.46%, -1.13%, -1.06%) bracket Rule B's (-0.92%). Any "wait for a higher close" rule behaves like Rule B; the earnings-day high is not a special level.

**Grid** (Figure 5, `grid_results.csv`). B minus A is negative in all 12 selection-period cells (CI below zero in 11) and its CI includes zero in all 12 hold-out cells. The primary statistic lies within +/- 3 bp per day of zero in every cell and period. The selection rule picked W = 15, H = 40 (primary -0.0 bp [-2.4, +2.5]); its hold-out value is -1.6 bp per day [-5.2, +2.0] and B minus A +0.03% [-0.63, +0.72]. The conclusion does not depend on the parameters.

## 8. Additional experiments and robustness (`robustness_W10_H40.csv`, `costs_W10_H40.csv`, `stratified_W10_H40.csv`)

| Variant | B minus A | Primary (bp/day) | Note |
|---|---|---|---|
| Base | -0.34% [-0.87, +0.20] | -0.7 [-3.0, +1.6] | |
| Trigger from day 2 (drop day-1 breakouts) | -0.37% [-0.94, +0.21] | -0.8 [-3.3, +1.5] | anchor binding only for faders |
| Market-on-close entry for B, C, D | -0.41% [-0.93, +0.13] | -1.0 [-3.4, +1.3] | same-close fills do not rescue B |
| Selection: AR0 >= 5% (26,611 events) | -0.18% [-0.65, +0.29] | -0.6 [-2.7, +1.5] | Rule A CAR +0.32% |
| Selection: z0 >= 2 (35,517 events) | -0.07% [-0.44, +0.34] | -0.3 [-1.7, +1.1] | Rule A CAR +0.11% |
| Intraday filings included | -0.38% [-0.88, +0.12] | -0.7 [-3.0, +1.6] | |
| Placebo: pseudo day 0 sixty sessions earlier | -0.40% [-0.91, +0.10] | +0.4 [-3.0, +3.7] | same B < A pattern with no news: mechanical |
| Short-side mirror (bottom decile, close < day-0 low), gross | -0.50% [-0.98, +0.01] | +0.4 [-3.6, +4.2] | symmetry check only; Reg SHO and borrow ignored |
| Friday day 0 (21.8% of events) | -0.16% [-0.77, +0.42] | -4.0 [-7.2, -0.5] | opposite sign to the attention prediction; one of many splits |
| Liquidity terciles | -0.48% / -0.05% / -0.49% (low/mid/high) | | no concentration in illiquid names |
| Range-placement terciles | -0.70% / -0.31% / -0.01% (low/mid/high) | | B's shortfall is largest where the anchor binds |

**Costs.** Median Corwin-Schultz spread 0.82% (0.73% high-liquidity tercile, 0.92% low). Charging half the spread plus 5 bp per side turns Rule A's +0.55% into **-0.52% [-1.55, +0.52]** and Rule B's +0.21% into -0.45% [-1.01, +0.14]. The 2005-2014 drift (+1.43% gross) would have been roughly break-even net; after 2015 there is nothing to trade.

## 9. Assumptions and limitations

- Event dating relies on the 8-K acceptance time, which can lag the press release; about 20-23% of events peak one session after the assigned day 0. This adds noise to Rule A and shifts some anchors, but treats A and B alike.
- Exchange membership comes from the current ticker master, not point-in-time; symbol reuse is handled with validity intervals but could still misassign rare cases.
- Abnormal returns are SPY-excess price returns: dividends are ignored (short windows) and no beta or size adjustment is made; the matched-path primary statistic and the placebo are the controls for this.
- Costs are estimated, not observed; the spread proxy is coarse for the most illiquid names.
- The placebo's Rule A level (+1.24%) reflects ex-post selection (stocks later chosen for a strong reaction) and is only used for the B-versus-A comparison.
- Earnings cluster in four seasons a year, so 86 season blocks, not 14,770 events, drive the confidence intervals; they are correspondingly wide.
- Ten parameter and design choices are listed in the README; the two tuned ones were selected on 2005-2014 and reported on 2015-2026.

## 10. Conclusion

The hypothesis is **rejected**. Post-breakout abnormal returns are indistinguishable from the unconditional post-announcement path in every period, cell and variant, and the rule that waits for a close above the earnings-day high earns less than buying at the next open, significantly so in 2005-2014 and about zero afterwards. The B-versus-A comparison the proposal put forward is mechanically biased against B on breakout events and is reproduced by unanchored triggers and by a no-news placebo, so even a positive result would not have supported a timing story. What remains is a modest, early-sample drift after extreme positive reactions (+1.4% over 40 sessions before 2015) that disappears after 2015 and is not tradable net of estimated spreads: in the brief's terms, "the original result was caused by a methodological issue" for the timing claim, and "exists before costs but is not practically tradable" (and only before 2015) for the drift itself.

## 11. What I would investigate next

1. Date events by press-release time (Benzinga or newswire timestamps) and measure how much the 8-K lag matters.
2. Condition on a fundamental surprise (EPS or revenue versus consensus) crossed with the price reaction, since the strongest drift evidence is for surprise sorts.
3. Test the anchoring story where the literature places it: nearness to the 52-week high and capital-gains overhang measured *before* the announcement, with volume as the auxiliary prediction.
4. A matched non-earnings control (same-quarter large up-days without filings) to separate earnings-specific continuation from generic short-term momentum.

## References

Ball, R. and Brown, P. (1968), *Journal of Accounting Research* 6, 159-178. Bernard, V. and Thomas, J. (1989), *JAR* 27 (Suppl.), 1-36; (1990), *Journal of Accounting and Economics* 13, 305-340. Chan, L., Jegadeesh, N. and Lakonishok, J. (1996), *Journal of Finance* 51, 1681-1713. Corwin, S. and Schultz, P. (2012), *JF* 67, 719-760. DellaVigna, S. and Pollet, J. (2009), *JF* 64, 709-749. Foster, G., Olsen, C. and Shevlin, T. (1984), *Accounting Review* 59, 574-603. Frazzini, A. (2006), *JF* 61, 2017-2046. George, T. and Hwang, C.-Y. (2004), *JF* 59, 2145-2176. Grinblatt, M. and Han, B. (2005), *Journal of Financial Economics* 78, 311-339. Hirshleifer, D., Lim, S. and Teoh, S. H. (2009), *JF* 64, 2289-2325. Huddart, S., Lang, M. and Yetman, M. (2009), *Management Science* 55, 16-31. Martineau, C. (2022), "Rest in Peace Post-Earnings Announcement Drift", *Critical Finance Review* 11, 613-646.

## Figures

![Figure 1](../outputs/figures/fig1_car_paths.png)
![Figure 2](../outputs/figures/fig2_breakout_aligned.png)
![Figure 3](../outputs/figures/fig3_post_breakout_bars.png)
![Figure 4](../outputs/figures/fig4_breakout_day_and_range.png)
![Figure 5](../outputs/figures/fig5_grid_B_minus_A.png)
![Figure 6](../outputs/figures/fig6_calendar_time.png)
