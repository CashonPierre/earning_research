"""Single source of text for the report. Edit here, then run scripts/build_notebook.py."""
TITLE = "Does post-earnings drift wait for the stock to clear its earnings-day high?"

SETUP_CODE = '''
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from IPython.display import Image, display
ROOT = Path.cwd() if (Path.cwd() / "outputs").exists() else Path.cwd().parent
T, F = ROOT / "outputs" / "tables", ROOT / "outputs" / "figures"
def load(name, **kw): return pd.read_csv(T / name, **kw)
pd.set_option("display.width", 180); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 60)
print("tables:", T)
'''

PCT = "{:+.2%}"; BP = "{:+.1f}"; F4 = "{:.4f}"

SECTIONS = [
{"md": """
**Author:** Lei Kam Fai (Woody). **Submission for:** Quant Team Recruitment, Round 1. **Date:** 13 September 2026.
**Data:** Massive REST API (US stock prices and reference data) and SEC EDGAR (filing timestamps). **Code:** this repository.

## Summary in plain words

Many traders are taught: after a great earnings report, do not buy straight away; wait until the stock closes above the high of the earnings day, then buy the "breakout". I tested whether the extra return after good earnings really arrives *after* that breakout.

I looked at 14,770 cases from 2005 to 2026 where a US stock had a top-10% price reaction on its earnings day. I compared two simple rules on exactly the same cases and the same 40-day window:

* **Rule A** buys at the open of the next day and sells 40 trading days after the earnings day.
* **Rule B** waits, buys at the open after the first close above the earnings-day high, and sells on the same day as Rule A. If the stock never breaks out, Rule B does nothing.

**Result: the idea does not hold.** After a breakout, the stock does not drift more than it does on average. Rule B earned *less* than Rule A, especially in 2005 to 2014 (about 0.9% less per case, and the gap is statistically clear), and about the same in 2015 to 2026. The reason is partly mechanical: on every case that does break out, Rule B skips the run-up that Rule A collected, and Rule B can only win if the cases that never break out fall a lot. "Wait for a higher close" rules that use other price levels behave exactly like Rule B, and so does a placebo test on days with no news. Buying right after the report earned a modest +1.4% over 40 days before 2015 and nothing after, and even the early drift disappears once realistic trading costs are charged.

So the honest conclusion is: **the hypothesis is rejected**, the original way of testing it was flawed, and the small drift that exists is old and not tradable.
"""},

{"md": """
## 1. The research question

After a strong earnings reaction, does the stock's extra return (relative to the market) arrive steadily from the next day, or does most of it arrive only after the stock first closes above the high of the earnings day? This is a question about *when* returns arrive, not about how large they are.
"""},

{"md": """
## 2. The hypothesis, and what would count as evidence

**Hypothesis (H1).** For stocks with a top-decile earnings-day reaction, the average abnormal return *per day* after the first close above the earnings-day high is higher than the average abnormal return per day that these stocks earn anyway over the same days.

**The null (H0).** Returns per day after the breakout are no different from the normal path.

**Secondary version (the proposal's original wording).** Rule B earns a higher 40-day return than Rule A.

I wrote down in advance (in `docs/PLAN.md`) what would count as support: the primary statistic (defined in section 8) must be positive with a 95% confidence interval that excludes zero in *both* the 2005 to 2014 period and the 2015 to 2026 period, and the control rules (section 7) must *not* show the same pattern. If the pattern also appears in the no-news placebo, the effect is mechanical rather than real.
"""},

{"md": """
## 3. Why we thought the effect might exist

* **Post-earnings drift is a classic finding.** Ball and Brown (1968) and Bernard and Thomas (1989, 1990) showed that after earnings news, prices keep moving in the same direction for weeks. But Martineau (2022) argues this drift has disappeared for large US stocks since about 2006. So I expected the drift itself to be small.
* **Two behavioural stories predict a late move.** First, holders sitting on gains sell into good news (the "disposition effect", Frazzini 2006; Grinblatt and Han 2005); their selling can hold the price down until it is absorbed. Second, a price level such as a recent high can act as an anchor; once it is cleared, buying may accelerate (George and Hwang 2004; Huddart, Lang and Yetman 2009 study this for the 52-week high).
* **Attention.** If the late move is a delayed reaction, it should be bigger when fewer people are paying attention, for example for Friday announcements (DellaVigna and Pollet 2009; Hirshleifer, Lim and Teoh 2009).
* **A caution.** My "strong report" is defined by the price reaction, not by the earnings surprise. Foster, Olsen and Shevlin (1984) found little short-term drift when sorting on the reaction, and Chan, Jegadeesh and Lakonishok (1996) found it mostly at 6 to 12 months. So a small Rule A return was the expected baseline.
"""},

{"md": """
## 4. What changed from the proposal, and why

The proposal was written before I had API access. Once I could read the documentation in detail and run probe calls, several things had to change. Each change is a dated row in `logs/decision_log.csv`.

| # | What the proposal said | What I found | What had been tested at that point | What I did instead | What I learned |
|---|---|---|---|---|---|
| 1 | Classify reports as before-open or after-close from the timestamp on the Massive 8-K endpoint | That endpoint has a filing *date* but no time. Its earnings tags also start only in 2020 and missed most earnings releases on a test day | Nothing modelled yet, only probes | Used the SEC EDGAR "submissions" feed, which gives the exact time the SEC accepted each 8-K and whether it contains Item 2.02 (results of operations) | Check the field list, not just the endpoint name |
| 2 | Rank events into the top 10% *within each quarter* | You do not know the quarter's ranking when the first events of the quarter happen: that is look-ahead | Nothing run | Threshold = 90th percentile of reactions over the *previous* four quarters, known on the day | Every selection rule must be computable on the trade date |
| 3 | Rule B "buys once the stock closes above the high" | You cannot buy at a closing price you have not seen yet | Nothing run | All rules buy at the *next open* after the signal; a "buy at the close" version is reported as a robustness check | Define the fill price before the hypothesis |
| 4 | Rule B beating Rule A would show that drift is concentrated after the breakout | On every case that breaks out, Rule A's return contains Rule B's return *plus* the run-up. So A beats B automatically on those cases; B can only win overall if non-breakout cases fall a lot | Nothing run (found in design review) | Made the primary test a comparison of the per-day return after the breakout with the normal per-day return; kept B versus A as a secondary result with control rules | Write down the algebra of a comparison before coding it |
| 5 | Use "Ticker Events" for delistings | That endpoint only lists symbol changes | Probe | Built the list of dead stocks from the ticker master (active = false) and matched events by company ID (CIK) | Survivorship protection has to be built, not assumed |
| 6 | Estimate spreads from tick-level quotes | Far too much data for the machine, and not needed | Probe | Corwin-Schultz (2012) spread estimate from daily highs and lows | Use what is already downloaded |
| 7 | Use Benzinga earnings data or income statements as a second "surprise" measure | Benzinga returned "not entitled" (HTTP 403) | Probe | Surprise measured by the price reaction only, with two alternative cut-offs as robustness | Probe entitlements before designing around a dataset |
"""},

{"md": """
## 5. Data

### 5.1 Massive (the central dataset)

* **Daily prices for the whole US market**, one API call per weekday from January 2004 to 11 September 2026 (5,988 calls). I asked for *unadjusted* prices and adjusted for stock splits myself using the Splits table, so that price filters use the real historical price level. My adjustment factors match the vendor's own factors, and my adjusted closes match the vendor's adjusted series on split days (`tests/test_api_crosscheck.py`).
* **Ticker master**: 36,588 US tickers including 6,609 delisted common stocks, with the company ID (CIK) needed to link filings to prices.
* **Splits**: 27,541 events.
* The SPY ETF, taken from the same daily file, is the market benchmark.

### 5.2 External data: SEC EDGAR

The SEC's submissions feed (`data.sec.gov/submissions/`) lists every filing a company ever made, with the exact time the SEC accepted it and the item numbers it contains. I downloaded it for 9,679 companies (9,672 found) and kept 8-K filings with Item 2.02, which is the item companies use to furnish their earnings press release: 321,077 filings. The data is free, public and point-in-time by construction, because the acceptance time is the moment the filing became public. I followed the SEC's rules (descriptive User-Agent, under 10 requests per second).

### 5.3 Cleaning

Duplicate rows removed; the trading calendar is the set of days on which SPY traded; returns across missing days are treated as missing; only common stocks (type "CS") on NYSE, Nasdaq and NYSE American are kept. Raw and per-stock data are *not* in the repository because they are licensed; only aggregate tables and figures are committed.

### 5.4 Timestamps and "what was known when"

Every event is dated to **day 0 = the first trading session that could react**:

* accepted before 09:30 New York time: day 0 is that day;
* accepted at or after 16:00: day 0 is the next trading day;
* accepted between 09:30 and 16:00: ambiguous ("intraday"); excluded from the main sample, included in a robustness run.

I checked this dating against the prices: for after-close and before-open filings, the biggest move (in absolute terms) falls on the assigned day 0 in about 64% of cases and on the day after in about 20%. The rest is mostly noise or 8-Ks filed some hours after the press release. This misdating adds noise but affects Rule A and Rule B in the same way. All filters use data from day -1 or earlier, the selection threshold uses only earlier quarters, and every trade happens at the open *after* the signal.
""",
 "code": '''
funnel = load("sample_funnel.csv"); tv = load("timing_validation.csv", index_col=0)
print("How the sample was built (number of events remaining after each step):"); display(funnel)
print("Share of events whose largest daily move falls on day -1, day 0 or day +1:"); display(tv.round(3))
''',
 "tables": [{"csv_path": "outputs/tables/sample_funnel.csv"}, {"csv_path": "outputs/tables/timing_validation.csv", "index": False, "fmt": {"peak_on_d0": "{:.3f}", "peak_on_dm1": "{:.3f}", "peak_on_d1": "{:.3f}", "n": "{:.0f}"}}]},

{"md": """
## 6. Which events we study

From 271,534 company-quarter events, 142,358 pass the filters (price at least $5 on day -1, median daily dollar volume over the previous 60 days at least $1 million, at least 120 days of history, not intraday, inside 2005 to mid-2026). Of these, **14,770 are "strong reports"**: their day-0 abnormal return is at or above the 90th percentile of the previous four quarters (the median cut-off is +8.1%). They cover 3,116 different stocks and 86 quarters, and 21.7% of them are stocks that have since been delisted, so the sample is not biased toward survivors.

Two features matter for everything that follows. First, these are big moves: the median day-0 abnormal return is +12.4% and the median overnight gap is +6.6%. Second, almost half of them close in the top fifth of their day-0 range, so for those the "earnings-day high" is barely above the close and is cleared on day 1 by any small gain.
""",
 "code": '''
desc = load("event_descriptives.csv", index_col=0); display(desc.round(3))
fig, axes = plt.subplots(1, 3, figsize=(15, 3.8))
y = load("events_per_year.csv"); axes[0].bar(y.year, y.n_selected_events); axes[0].set_title("Selected events per year")
h = load("range_pos_hist.csv"); axes[1].bar(h.bin_left, h.n_events, width=0.04, align="edge"); axes[1].set_title("Where the day-0 close sits in the day-0 range\\n(0 = at the low, 1 = at the high)")
k = load("breakout_day_hist_W10_H40.csv"); kk = k[k.k_B != "none"]; axes[2].bar(kk.k_B.astype(int), kk.n_events); axes[2].set_title(f"Day of first close above the day-0 high\\n({int(k[k.k_B=='none'].n_events.iloc[0])} events never do within 10 days)")
plt.tight_layout(); plt.show()
''',
 "figs": [("outputs/figures/fig4_breakout_day_and_range.png", "Figure 4. Left: day of the first close above the day-0 high (W = 10). Right: where the day-0 close sits in the day-0 range.")]},

{"md": """
## 7. The two rules and the controls, with a toy example

All days are trading days counted from day 0. **H** is the holding length (40 in the main run) and **W** is the maximum number of days we are willing to wait for a breakout (10 in the main run).

* **Rule A:** buy at the open of day 1, sell at the close of day H.
* **Rule B:** find the first day k (1 to W) whose close is above the day-0 high. Buy at the open of day k+1, sell at the close of day H. If there is no such day, do nothing (return 0).
* **Rule C (fixed delay):** buy at the open of day 3 no matter what, sell at the close of day H. Day 3 is the median breakout day, so C waits as long as B typically waits, but without looking at prices. If B beats C, the *breakout* matters; if not, only the *waiting* mattered.
* **Rules D1, D2, D3 (other levels):** like B, but the trigger is a close above the day-0 close (D1), above 1.03 times the day-0 high (D2), or above the day-1 high (D3). If these behave like B, the earnings-day high is not a special level.

All returns are **abnormal returns**: the stock's return minus SPY's return over the same span. Stocks that stop trading inside the window (17 cases) are sold at their last price.

**Toy example.** A stock closes day 0 at $100 with a day-0 high of $104. Rule A buys at $100 at the day-1 open. Suppose the stock closes at $105 on day 3, its first close above $104. Rule B buys at the day-4 open at $105. Both sell at $110 on day 40. Rule A made +10%. Rule B made +4.8%. Rule A's +10% is the run-up (+5%) *combined with* Rule B's +4.8%. This is always true: **whenever the stock breaks out, Rule A earns at least what Rule B earns.** Rule B can only come out ahead on average if the stocks that *never* break out lose a lot, because on those Rule B earns 0 while Rule A takes the loss. That is why "B beats A" cannot, on its own, tell us anything about timing.
""",
 "code": '''
# The identity in numbers: A = (1 + run-up) * (1 + B) - 1 on every breakout case.
p0_close, p0_high, p1_open, p3_close, p4_open, p40_close = 100, 104, 100, 105, 105, 110
ret_A = p40_close / p1_open - 1
ret_B = p40_close / p4_open - 1
run_up = p4_open / p1_open - 1
print(f"Rule A: {ret_A:+.2%}   Rule B: {ret_B:+.2%}   run-up A collected but B skipped: {run_up:+.2%}")
print(f"Check: (1 + run-up) * (1 + B) - 1 = {(1 + run_up) * (1 + ret_B) - 1:+.2%}  (equals Rule A)")
print("If the stock never closes above $104: Rule B = 0, Rule A = whatever happened (e.g. $92 -> -8%).")
'''},

{"md": """
## 8. How we measure and test

**Primary statistic (the timing test).** For each case that breaks out on day k, take its abnormal return per day from the entry (day k+1) to day H. Compare it with the abnormal return per day that *all* strong-report cases in the same quarter earned over those *same* days. The difference is the primary statistic. If drift really concentrates after breakouts, it is positive. Comparing with the same days and the same quarter removes the effect of "returns are higher early in the window" and of "that quarter was a good quarter". It also avoids the trap in the toy example: we never compare the post-breakout leg with the run-up that was conditioned on the breakout.

**Confidence intervals.** Earnings cluster in four seasons a year, so the 14,770 cases are far from independent. I treat each calendar quarter as one block (86 blocks) and resample blocks with replacement 5,000 times ("season-block bootstrap"). Every headline number comes with the resulting 95% interval, plus the share of quarters in which the number was positive.

**Calendar-time check.** I also form daily portfolios: on each trading day, average the abnormal return of every open Rule A position (and separately every Rule B position). This turns overlapping events into one daily series per rule; the difference series is tested with Newey-West standard errors, which correct for the fact that consecutive days are correlated.

**Parameters.** There are two tunable parameters: W (5, 10, 15, 20) and H (20, 40, 60). The default (10, 40) was fixed in advance. The 2005 to 2014 half chooses the best cell (largest lower confidence bound of the primary statistic); the 2015 to 2026 half is then reported for that cell. The whole grid is shown in section 10. All other choices ($5 price, $1M volume, 90th percentile, 60-day windows, 5 basis points commission per side) were set once, by convention, and not tuned. Optimising beyond this would only risk fitting noise.
"""},

{"md": """
## 9. Main results (default cell W = 10, H = 40)

### 9.1 Rule A: what happens after a strong report?

The average 40-day abnormal return of buying at the next open is **+0.55%** (95% CI -0.50% to +1.59%) over 2005 to 2026. It was **+1.43%** (+0.57% to +2.35%) in 2005 to 2014 and **+0.12%** (-1.29% to +1.55%) in 2015 to 2026. The daily calendar-time portfolio earns 2.9 basis points per day (Newey-West t = 2.5) overall, 5.2 (t = 3.8) before 2015 and 0.8 (t = 0.5) after. Drift after extreme positive reactions existed early in the sample and has faded, consistent with Martineau (2022).
""",
 "code": '''
cp = load("car_path_means.csv")
fig, ax = plt.subplots(figsize=(9, 4.5))
for per, c in (("all_2005_2026", "k"), ("selection_2005_2014", "tab:blue"), ("holdout_2015_2026", "tab:red")):
    d = cp[cp.period == per]; ax.plot(d.day, d.mean_car_pct, color=c, label=f"{per} (n={int(d.n_events.iloc[0])})"); ax.fill_between(d.day, d.ci_lo_pct, d.ci_hi_pct, color=c, alpha=0.12)
ax.axhline(0, color="gray", lw=0.8); ax.set_xlabel("trading days after day 0"); ax.set_ylabel("cumulative abnormal return, % (Rule A path)"); ax.legend(); ax.set_title("Figure 1. Average path after a top-decile reaction, with 95% season-bootstrap bands"); plt.show()
''',
 "figs": [("outputs/figures/fig1_car_paths.png", "Figure 1. Average cumulative abnormal return after a top-decile earnings reaction (Rule A path), with season-bootstrap 95% bands.")]},

{"md": """
### 9.2 Splitting the cases: breakout or not

60.8% of cases close above the day-0 high within 10 days, and 44.9% of those do it on day 1. The table below shows why the A-versus-B comparison is mechanical. Cases that break out earned +4.19% under Rule A but only +0.34% under Rule B, because the run-up before the entry was +3.79%. Cases that never break out lost 5.10% under Rule A, and Rule B sat them out.
""",
 "code": '''
dec = load("decomposition_W10_H40.csv")
cols = ["period", "group", "n", "share", "CAR_A", "CAR_B", "run_up_open1_to_entry", "post_entry_leg", "perday_A", "perday_post_entry"]
display(dec[cols].style.format({"share": "{:.1%}", "CAR_A": "{:+.2%}", "CAR_B": "{:+.2%}", "run_up_open1_to_entry": "{:+.2%}", "post_entry_leg": "{:+.2%}", "perday_A": "{:+.3%}", "perday_post_entry": "{:+.3%}"}, na_rep=""))
''',
 "tables": [{"csv_path": "outputs/tables/decomposition_W10_H40.csv", "cols": ["period", "group", "n", "share", "CAR_A", "CAR_B", "run_up_open1_to_entry", "post_entry_leg", "perday_post_entry"], "fmt": {"share": "{:.1%}", "CAR_A": PCT, "CAR_B": PCT, "run_up_open1_to_entry": PCT, "post_entry_leg": PCT, "perday_post_entry": "{:+.3%}"}}]},

{"md": """
### 9.3 The primary test: is there extra drift after the breakout?

**No.** After the entry, breakout cases earned +0.01% per day, and the matched normal path over the same days earned about the same. The primary statistic is **-0.7 basis points per day (95% CI -3.0 to +1.6)** for 2005 to 2026, -0.0 (-3 to +2) in 2005 to 2014 and -2 (-5 to +2) in 2015 to 2026. Figure 2 shows the daily abnormal returns lined up on the breakout day: a big spike on the breakout day itself (which is what *defines* a breakout), and from the entry open onwards a path that sits on top of the normal one.

**How to read Figure 2.** Day 0 on the x-axis is the breakout day k, not the earnings day. The red dot at 0 is huge because a breakout day is by definition a day the stock rose. Everything to the right of the green line is what a Rule B trader actually receives. It is indistinguishable from the grey squares, which show what all strong-report stocks earned on those same days in that same quarter.
""",
 "code": '''
ba = load("breakout_aligned_means.csv")
fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
axes[0].plot(ba.tau, ba.breakout_events_mean_ar_bp, "o-", color="tab:red", label="breakout cases"); axes[0].plot(ba.tau, ba.matched_unconditional_mean_ar_bp, "s--", color="gray", label="matched normal path")
axes[0].axvline(0, color="k", ls=":", lw=0.8); axes[0].axvline(1, color="tab:green", ls=":", lw=0.8); axes[0].set_xlabel("trading days relative to the breakout day"); axes[0].set_ylabel("mean daily abnormal return, bp"); axes[0].legend(); axes[0].set_title("Figure 2. Daily abnormal returns around the breakout")
post = ba[ba.tau >= 1]; axes[1].bar(post.tau - 0.2, post.breakout_events_mean_ar_bp, 0.4, color="tab:red", label="breakout cases"); axes[1].bar(post.tau + 0.2, post.matched_unconditional_mean_ar_bp, 0.4, color="gray", label="matched normal path")
axes[1].axhline(0, color="k", lw=0.8); axes[1].set_xlabel("days after the breakout"); axes[1].legend(); axes[1].set_title("Figure 3. After the entry only"); plt.tight_layout(); plt.show()
ms = load("main_summary_W10_H40.csv"); rows = ms[ms.statistic.str.contains("per-day|post-breakout")][["period", "statistic", "mean", "ci_lo", "ci_hi", "n_events"]]
display(rows.style.format({"mean": "{:+.4%}", "ci_lo": "{:+.4%}", "ci_hi": "{:+.4%}"}))
''',
 "figs": [("outputs/figures/fig2_breakout_aligned.png", "Figure 2. Daily abnormal returns aligned on the breakout day (red) against the matched normal path (grey)."), ("outputs/figures/fig3_post_breakout_bars.png", "Figure 3. The same comparison for the days after the entry only.")]},

{"md": """
### 9.4 Rule B versus Rule A, and the control rules

Rule B earned **+0.21%** against Rule A's +0.55%: a difference of **-0.34% (95% CI -0.87% to +0.20%)**. In 2005 to 2014 the difference was **-0.92% (-1.41% to -0.46%)** and Rule B beat Rule A in only 28% of quarters; in 2015 to 2026 it was -0.06% (-0.77% to +0.67%). In calendar time, the B-minus-A daily series averages -1.8 basis points per day (Newey-West t = -2.9). Waiting for the breakout forgoes the run-up and collects nothing extra.

The controls confirm that nothing about the *earnings-day high* is special. The fixed-delay Rule C earned +0.45% (C minus A: -0.09%, CI -0.25% to +0.06%). The other-level rules D1, D2 and D3 earned +0.40%, +0.08% and +0.12%; in 2005 to 2014 their shortfalls against A (-0.46%, -1.13%, -1.06%) bracket Rule B's (-0.92%). Any "wait for a higher close" rule behaves like Rule B.
""",
 "code": '''
ms = load("main_summary_W10_H40.csv")
want = ["CAR_A (open1->closeH)", "CAR_B (breakout entry, 0 if flat)", "B minus A", "CAR_C fixed delay m", "C minus A", "CAR_D1", "D1 minus A", "CAR_D2", "D2 minus A", "CAR_D3", "D3 minus A"]
t = ms[ms.statistic.isin(want)].pivot(index="statistic", columns="period", values="mean").reindex(want)[["all_2005_2026", "selection_2005_2014", "holdout_2015_2026"]]
display(t.style.format("{:+.2%}"))
ct = load("calendar_time_W10_H40.csv"); display(ct.round(3))
s = load("calendar_time_series_W10_H40.csv", index_col=0)
fig, ax = plt.subplots(figsize=(9, 4)); ax.plot(s.index, s.rA.cumsum() * 100, label="Rule A book"); ax.plot(s.index, s.rB.cumsum() * 100, label="Rule B book"); ax.plot(s.index, s.d.cumsum() * 100, color="k", label="B minus A")
ax.set_xlabel("trading-day index (2005 to 2026)"); ax.set_ylabel("cumulative daily abnormal return, %"); ax.legend(); ax.set_title("Figure 6. Calendar-time portfolios"); plt.show()
''',
 "tables": [{"csv_path": "outputs/tables/main_summary_W10_H40.csv", "query": "statistic in ['CAR_A (open1->closeH)', 'CAR_B (breakout entry, 0 if flat)', 'B minus A', 'CAR_C fixed delay m', 'C minus A', 'D1 minus A', 'D2 minus A', 'D3 minus A']", "cols": ["period", "statistic", "mean", "ci_lo", "ci_hi", "share_seasons_pos"], "fmt": {"mean": PCT, "ci_lo": PCT, "ci_hi": PCT, "share_seasons_pos": "{:.0%}"}}, {"csv_path": "outputs/tables/calendar_time_W10_H40.csv", "fmt": {"mean_daily_bp": BP, "nw_se_bp": "{:.2f}", "nw_t": "{:.2f}", "ann_sharpe": "{:.2f}"}}],
 "figs": [("outputs/figures/fig6_calendar_time.png", "Figure 6. Cumulative daily abnormal returns of the Rule A and Rule B books and their difference.")]},

{"md": """
## 10. Choosing the two parameters

The grid below covers every W and H combination for both halves of the sample. Rule B minus Rule A is negative in all 12 cells in 2005 to 2014 (the interval is entirely below zero in 11 of them) and its interval includes zero in all 12 cells in 2015 to 2026. The primary statistic stays within plus or minus 3 basis points per day of zero everywhere. The selection rule picked W = 15, H = 40 (primary statistic -0.0 bp, CI -2.4 to +2.5, in 2005 to 2014); in 2015 to 2026 that cell gives -1.6 bp (-5.2 to +2.0) and B minus A of +0.03% (-0.63% to +0.72%). **The conclusion does not depend on the parameters.**
""",
 "code": '''
g = load("grid_results.csv")
for per in ("selection_2005_2014", "holdout_2015_2026"):
    print(per, ": Rule B minus Rule A (%)"); display((g[g.label == per].pivot(index="W", columns="H", values="B_minus_A") * 100).round(2))
    print(per, ": primary statistic (bp per day)"); display((g[g.label == per].pivot(index="W", columns="H", values="PRIMARY_post_minus_matched") * 1e4).round(1))
display(Image(filename=str(F / "fig5_grid_B_minus_A.png")))
''',
 "figs": [("outputs/figures/fig5_grid_B_minus_A.png", "Figure 5. Rule B minus Rule A across the parameter grid, 2005 to 2014 (left) and 2015 to 2026 (right).")]},

{"md": """
## 11. Robustness checks and trading costs

Every variant below was run through the same engine and is logged in `logs/experiment_record.csv`, including the ones that made no difference.

* **Ignore day-1 breakouts** (trigger only from day 2): B minus A -0.37%; primary -0.8 bp/day.
* **Buy at the signal close instead of the next open:** -0.41%; -1.0 bp/day. Faster fills do not rescue Rule B.
* **Different "strong report" cut-offs:** a fixed +5% (26,611 cases) gives -0.18%; a reaction of at least two standard deviations (35,517 cases) gives -0.07%. Rule A's own return falls to +0.32% and +0.11% in these larger samples.
* **Include the ambiguous intraday filings:** -0.38%.
* **Placebo with no news:** run the same rules on the same stocks 60 sessions *before* the earnings day. B minus A is -0.40% and the primary statistic +0.4 bp/day. The B-below-A pattern appears without any news, which confirms it is mechanical.
* **Mirror image on the short side** (bottom-decile reactions, trigger = close below the day-0 low): -0.50%, primary +0.4 bp/day. A symmetry check only; borrowing costs and short-sale rules are ignored.
* **Friday announcements** (21.8% of cases): the primary statistic is -4.0 bp/day (-7.2 to -0.5), the opposite sign to the attention story. This is one of many splits, so I report it as a curiosity, not a finding.
* **By liquidity** (low / mid / high thirds): B minus A -0.48% / -0.05% / -0.49%. No concentration in illiquid names.
* **By where the day-0 close sits in its range** (low / mid / high thirds): -0.70% / -0.31% / -0.01%. Rule B's shortfall is largest exactly where the anchor actually binds.

**Costs.** The Corwin-Schultz estimate of the bid-ask spread has a median of 0.82% (0.73% for the most liquid third, 0.92% for the least liquid). Charging half the spread plus 5 basis points on each side turns Rule A's +0.55% into **-0.52%** (CI -1.55% to +0.52%) and Rule B's +0.21% into -0.45% (-1.01% to +0.14%). The 2005 to 2014 drift (+1.43% gross) would have been roughly break-even after costs; after 2015 there is nothing to trade.
""",
 "code": '''
rb = load("robustness_W10_H40.csv"); rb = rb[rb.period == "all"]
show = rb[["variant", "n_events", "share_entered_B", "CAR_A", "CAR_B", "B_minus_A", "B_minus_A_lo", "B_minus_A_hi", "PRIMARY_post_minus_matched", "PRIMARY_lo", "PRIMARY_hi"]].copy()
for c in ("PRIMARY_post_minus_matched", "PRIMARY_lo", "PRIMARY_hi"): show[c] = show[c] * 1e4
display(show.style.format({"share_entered_B": "{:.0%}", "CAR_A": "{:+.2%}", "CAR_B": "{:+.2%}", "B_minus_A": "{:+.2%}", "B_minus_A_lo": "{:+.2%}", "B_minus_A_hi": "{:+.2%}", "PRIMARY_post_minus_matched": "{:+.1f} bp", "PRIMARY_lo": "{:+.1f}", "PRIMARY_hi": "{:+.1f}"}))
costs = load("costs_W10_H40.csv"); display(costs[["group", "n", "median_spread", "gross_A", "net_A", "net_A_lo", "net_A_hi", "gross_B", "net_B", "net_B_lo", "net_B_hi"]].style.format({"median_spread": "{:.2%}", "gross_A": "{:+.2%}", "net_A": "{:+.2%}", "net_A_lo": "{:+.2%}", "net_A_hi": "{:+.2%}", "gross_B": "{:+.2%}", "net_B": "{:+.2%}", "net_B_lo": "{:+.2%}", "net_B_hi": "{:+.2%}"}))
''',
 "tables": [{"csv_path": "outputs/tables/robustness_W10_H40.csv", "query": "period == 'all'", "cols": ["variant", "n_events", "share_entered_B", "CAR_A", "B_minus_A", "B_minus_A_lo", "B_minus_A_hi", "PRIMARY_post_minus_matched", "PRIMARY_lo", "PRIMARY_hi"], "fmt": {"share_entered_B": "{:.0%}", "CAR_A": PCT, "B_minus_A": PCT, "B_minus_A_lo": PCT, "B_minus_A_hi": PCT, "PRIMARY_post_minus_matched": "{:+.4%}", "PRIMARY_lo": "{:+.4%}", "PRIMARY_hi": "{:+.4%}"}}, {"csv_path": "outputs/tables/costs_W10_H40.csv", "cols": ["group", "n", "median_spread", "gross_A", "net_A", "gross_B", "net_B"], "fmt": {"median_spread": "{:.2%}", "gross_A": PCT, "net_A": PCT, "gross_B": PCT, "net_B": PCT}}]},

{"md": """
## 12. Assumptions and limitations

* **Event dating.** The 8-K acceptance time can be hours after the press release, so roughly one case in five is dated a session late. This adds noise to both rules equally; it does not create a bias in favour of either.
* **Exchange membership** is taken from today's ticker master rather than as of the event date. Symbol reuse is handled with validity windows, but rare mismatches are possible.
* **Abnormal return = stock minus SPY.** Dividends are ignored (short windows) and there is no beta or size adjustment. The matched-path primary statistic and the placebo do not depend on the benchmark, which is why they are the main evidence.
* **Costs are estimated**, not observed. The spread proxy is coarse for the least liquid names.
* **The placebo's Rule A level** (+1.24%) is not meaningful on its own: those stocks were chosen because of a strong reaction that came later. Only the B-versus-A comparison inside the placebo is used.
* **Effective sample size.** Earnings arrive in four seasons a year, so 86 quarter blocks, not 14,770 cases, determine the width of the confidence intervals.
* **Ten design choices** are listed in the README's parameter table. Only W and H were tuned, on 2005 to 2014, and reported on 2015 to 2026.
"""},

{"md": """
## 13. Conclusion

**The hypothesis is rejected.** Abnormal returns after a close above the earnings-day high are indistinguishable from the normal post-announcement path in every period, every parameter cell and every robustness variant. The rule that waits for the breakout earns less than buying at the next open: clearly so in 2005 to 2014, and roughly zero after. The comparison the proposal put forward (Rule B beats Rule A) is biased against Rule B by construction, and its pattern is reproduced both by triggers that ignore the earnings-day high and by a placebo with no news at all, so even a positive result would not have supported a timing story.

In the language of the brief: for the *timing* claim, "the original result was caused by a methodological issue"; for the drift itself, "the result exists before costs but is not practically tradable", and only before 2015.
"""},

{"md": """
## 14. What I would investigate next

1. Date events by the press-release time (a newswire or earnings-calendar feed) and measure how much the 8-K lag matters.
2. Condition on a fundamental surprise (reported versus expected EPS and revenue) crossed with the price reaction; the strongest drift evidence in the literature is for surprise sorts.
3. Test the anchoring story where the literature places it: nearness to the 52-week high and the capital-gains position of holders measured *before* the announcement, with volume as the extra prediction.
4. Build a matched control from non-earnings days with equally large moves, to separate earnings-specific continuation from ordinary short-term momentum.
"""},

{"md": """
## Glossary

* **Abnormal return:** the stock's return minus SPY's return over the same span; what the stock did beyond the market.
* **Day 0:** the first trading session that could react to the earnings release.
* **CAR (cumulative abnormal return):** abnormal return added up over a window, here 40 trading days.
* **Breakout:** the first close above the high of day 0, within W days.
* **Basis point (bp):** one hundredth of one percent. 10 bp = 0.10%.
* **Look-ahead bias:** using information that was not available at the time a decision is made. Example: ranking a January event against the whole quarter's events.
* **Survivorship bias:** studying only companies that still exist today, which drops the failures.
* **Season-block bootstrap:** to get a confidence interval, resample whole quarters (with replacement) many times and recompute the statistic; this respects the fact that earnings cluster in quarters.
* **95% confidence interval (CI):** the range of values consistent with the data; if it includes zero, the effect is not distinguishable from zero.
* **Calendar-time portfolio:** on each day, the average return of all positions open that day; it turns overlapping events into one daily series.
* **Newey-West t-statistic:** a t-statistic whose standard error is corrected for correlation between consecutive days.
* **Corwin-Schultz spread:** an estimate of the bid-ask spread computed only from daily highs and lows.
"""},

{"md": """
## Questions an interviewer may ask, and short answers

1. **Why did Rule B lose to Rule A in 2005 to 2014?** Because on breakout cases A holds B's position plus a +3.3% run-up, and the non-breakout cases (40% of the sample) lost only 2.7% under A in that period; that is not enough for B's zeros to make up the difference. Table 9.2 shows both pieces.
2. **Is the result just because breakouts on day 1 are trivial?** No. Excluding day-1 breakouts gives -0.37% (versus -0.34%), and Rule B's shortfall is largest in the cases where the close was far below the high, where the anchor really binds.
3. **How do you know the primary statistic is not biased by the selection on breakouts?** The post-entry leg starts *after* the breakout day and is compared with what all strong-report stocks earned over the same days in the same quarter. The breakout-day spike itself (Figure 2, day 0) is excluded from both sides.
4. **What would have convinced you the hypothesis was true?** A primary statistic with a 95% interval above zero in both halves of the sample, plus Rules C and D failing to reproduce it, plus a flat placebo. None of the three happened.
5. **Where is the look-ahead in the original proposal?** The within-quarter decile ranking and the "buy at the signal close" rule. Both were replaced before any test was run, and both are logged.
6. **Could misdated events explain the null?** They add noise but no bias: misdating shifts the anchor and the entry for A and B alike, and the timing validation shows 64% correct dating with most of the rest one day late.
7. **Why SPY as benchmark and not a size-matched portfolio?** Simplicity and transparency. The primary statistic compares stocks with themselves over the same days, so the benchmark cancels out in the main test; the placebo provides a second benchmark-free check.
8. **Is anything here tradable?** No. Median round-trip spread costs of about 1% exceed the +0.55% gross return of Rule A; before 2015 the drift was roughly break-even after costs.
"""},

{"md": """
## References

Ball, R. and Brown, P. (1968). An empirical evaluation of accounting income numbers. *Journal of Accounting Research* 6, 159-178.
Bernard, V. and Thomas, J. (1989). Post-earnings-announcement drift: delayed price response or risk premium? *Journal of Accounting Research* 27 (Suppl.), 1-36.
Bernard, V. and Thomas, J. (1990). Evidence that stock prices do not fully reflect the implications of current earnings for future earnings. *Journal of Accounting and Economics* 13, 305-340.
Chan, L., Jegadeesh, N. and Lakonishok, J. (1996). Momentum strategies. *Journal of Finance* 51, 1681-1713.
Corwin, S. and Schultz, P. (2012). A simple way to estimate bid-ask spreads from daily high and low prices. *Journal of Finance* 67, 719-760.
DellaVigna, S. and Pollet, J. (2009). Investor inattention and Friday earnings announcements. *Journal of Finance* 64, 709-749.
Foster, G., Olsen, C. and Shevlin, T. (1984). Earnings releases, anomalies, and the behavior of security returns. *Accounting Review* 59, 574-603.
Frazzini, A. (2006). The disposition effect and underreaction to news. *Journal of Finance* 61, 2017-2046.
George, T. and Hwang, C.-Y. (2004). The 52-week high and momentum investing. *Journal of Finance* 59, 2145-2176.
Grinblatt, M. and Han, B. (2005). Prospect theory, mental accounting, and momentum. *Journal of Financial Economics* 78, 311-339.
Hirshleifer, D., Lim, S. and Teoh, S. H. (2009). Driven to distraction: extraneous events and underreaction to earnings news. *Journal of Finance* 64, 2289-2325.
Huddart, S., Lang, M. and Yetman, M. (2009). Volume and price patterns around a stock's 52-week highs and lows. *Management Science* 55, 16-31.
Martineau, C. (2022). Rest in peace post-earnings announcement drift. *Critical Finance Review* 11, 613-646.

## Appendix: reproducing this report

`scripts/run_all.py` runs every stage (downloads, panel, events, main run, grid, robustness, figures, aggregate export). `scripts/build_notebook.py` rebuilds this document, as `notebooks/report.ipynb` and `docs/report.md`, from the committed tables in `outputs/tables/` only; it needs no licensed data. Tests: `python -m pytest -q`.
"""},
]
