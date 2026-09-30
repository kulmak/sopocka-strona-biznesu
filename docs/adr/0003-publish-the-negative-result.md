# 0003 — Publish the negative result: the event effect is mostly season

**Status:** accepted · **Date:** 2026-09-30 · **Supersedes:** the film's causal claim

**Context.** The product's narrative — and the finished film — claims that city events move restaurant
card payments. Measured on the real parquet, grouping days by mean `event_listings_count`: the raw spread
between the most-event and least-event quartiles is **59.8 pp** (Q4 +32.9 %, Q1 −26.9 %, against a
same-weekday mean). After month × weekday control it collapses to **9.0 pp** (Q4 +4.7 %, Q1 −4.3 %). In a
multiple regression on the month-controlled uplift: event listings **β = +0.0031 (t = +1.9)** — marginal;
rain fraction **β = −0.364 (t = −8.8)** — overwhelming; temperature β = +0.0063 (t = +4.5). The walk-forward
backtest (490 days, expanding window, past-only) puts the mean of the last four same-weekday observations
at **MAPE 24.1 %**, best of five candidates, while *adding* weather and events makes the forecast worse
(29.2 % / 29.5 %).

**Decision.** Publish the collapse, lead the product with weather rather than events, keep events as
context and calendar, and drop the claim that our model beats a naive baseline. The deck states the raw
number, the controlled number and the reason they differ, on one slide.

**Consequences.** The film's headline causal claim becomes the deck's worked counter-example instead of its
conclusion, and the value proposition narrows to something defensible: *we hand the owner the baseline she
cannot compute for herself, plus the drivers that explain the deviation.* A juror can overturn the retained
claim in five minutes with the same parquet — which is the point of publishing it rather than being caught
by it. The event-strip feature survives, demoted from explanation to context.

**Alternatives rejected.**
- **Keep the 59.8 pp headline.** Rejected: any juror who reruns the control on the same data reproduces the
  seasonal explanation in minutes; a number that collapses under one control is a liability, not a result.
- **Remove the event feature entirely.** Rejected: the merchant's own city calendar already shows events;
  deleting them makes the panel less useful than the calendar, not more honest.
- **Report both numbers without choosing.** Rejected: two live versions of one claim is exactly the defect
  class our own documentation standard forbids, and it leaves the reader to decide what we believe.
- **Add a stronger seasonality model until the event effect reappears.** Rejected: that is fitting the
  control to the desired answer; the honest sequence is to report the specification we pre-committed to.
