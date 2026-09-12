# Research Proposal (Woody Lei, submitted draft, Google Doc last edited 2026-09-09)

Title: Does post-earnings drift happen mostly after the stock clears its earnings-day high?

## Research question
After a strong earnings report, does the stock drift upward steadily from the next day, or does most of the move happen only after it first closes above its report-day high? This is a question about timing rather than size.

## Hypothesis
Drift is concentrated after the stock clears its earnings-day high. I compare two rules on the same events over the same window. Rule A buys the day after the report. Rule B waits and buys only once the stock closes above its earnings-day high. If the hypothesis holds, Rule B earns more despite holding for fewer days.

## Motivation
Buying a breakout from post-earnings consolidation is a widely taught setup, rarely tested against a passive benchmark. Ball and Brown (1968) and Bernard and Thomas (1989) documented post-earnings drift, but Martineau (2022) shows it has since disappeared, absent in large stocks since 2006. I therefore expect average drift near zero, which is what makes the timing question worth asking: a zero average can hide continuation offset by reversal.

## Asset class and universe
US common stocks. Filters use only pre-event data: minimum prior close and trailing dollar volume. Delisted stocks are retained, so the sample is not biased toward survivors.

## Massive datasets and endpoints
Daily Market Summary for daily prices, one call per date for the whole market; 8-K Disclosures and Disclosure Categories for Item 2.02 releases and timestamps; All Tickers and Ticker Events for security type and delistings; Splits and Dividends for adjustment; NBBO Quotes for spreads; Income Statements for an alternative surprise measure; SPY as benchmark.

## External data
None expected. If 8-K coverage or timestamps prove insufficient, I will fall back to SEC EDGAR and document the change.

## Variable studied
Cumulative abnormal return: stock return minus SPY return, accumulated over the days after the report.

## Why the relationship may exist
If holders take profits after good news, their selling absorbs buying pressure and holds the price flat until that supply clears; Frazzini (2006) finds drift is largest when the news and holders' unrealised gains share a sign. A close above the earnings-day high also removes a reference level investors were anchored to. Both imply a late move.

## Methodology and evaluation plan
Assign day 0 by comparing each Item 2.02 timestamp to 16:00 ET, separating before-open from after-close reports. Rank events by day-0 abnormal return within each quarter and take the top decile. Run both rules over an identical window, counting days before Rule B enters as zero return, so Rule B is handicapped by construction and must win anyway. Aggregate to a daily cross-sectional mean before testing, since clustered earnings dates would inflate pooled test statistics. Two parameters only, the maximum wait and the holding length, chosen on an early sub-period and reported on a later one, with the full grid disclosed including failures. Costs are applied separately, reported gross and net. Robustness: a mirrored short-side run, a split by day-0 range placement, and a placebo test in a pre-earnings window.

## Limitations and research risks
The 8-K timestamp may lag the press release and some issuers report without an Item 2.02, so measuring coverage is my first task. Breakout status depends on what happened after the report, which is why both rules share a window, and why separating genuine timing from the mechanical exclusion of stocks that fell is the main analytical risk. Earnings cluster into four seasons a year, so my effective sample is far smaller than the event count suggests, and I will report confidence intervals rather than significance alone. Drift is reported to have weakened and to concentrate in illiquid names, so the effect may be absent, or present before costs and untradable after. Any of these would be reported as the conclusion.
