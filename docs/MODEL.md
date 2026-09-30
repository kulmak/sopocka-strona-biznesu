# MODEL — what we estimate, what we assume, and where our own audit was wrong

The model answers one question for one restaurateur: *how far is today from normal for this street at this
hour, and which driver carries the signal?* It is deliberately three separable pieces — a weekday-matched
baseline, a driver regression that explains deviations, and a walk-forward forecast — and **no language
model is in the decision path**: the forecast is an explicit formula with published coefficients. The
identification assumptions come before the results, and §7 reports the places where the audit we inherited turned out to be wrong.

## 1. Reproduce

```sh
python3 -m pipeline.run --src /Users/kulma/Downloads --out artifacts   # writes backtest.json + drivers.json
python3 -c "import json;d=json.load(open('artifacts/drivers.json'));print(d['reading'])"
```

## 2. The estimands

Three distinct quantities, never mixed. A figure quoted from one is never presented as another.

| # | Estimand | Unit | Where it is used |
|---|---|---|---|
| E1 | The **weekday-matched baseline** `B(code, day, hour)` — what is normal *for this street, this weekday, this hour* | transactions per cell | the grey reference line and every „zwykle” readout |
| E2 | The **driver coefficients** `β` on the log of daily city transactions | log-points per unit | „główny czynnik” and the honest statement of what is robust |
| E3 | The **next-day forecast** and its interval | transactions per day, city-wide | the panel's headline number and band |

E2 is a *city-day* estimand: it says which covariate moves total trade, not which venue gained. We make no
per-venue causal claim, and the panel labels every area figure *„Dane dla obszaru {kod}, nie dla Twojego lokalu.”*

## 3. The baseline (E1)

For a target cell the baseline is the mean of the **same `purchase_weekday_iso`** over the trailing four weeks:

```
B(code, di, h) = mean( cnt[code, di - 7k, h] )      k = 1..4          #baseline_weeks
```

Not the mean of the last 30 days, which is what the prototype computed. Measured over all 378,212 rows in
local time, the index of each weekday against an average day is:

| | Pn | Wt | Śr | Cz | Pt | Sb | Nd |
|---|---:|---:|---:|---:|---:|---:|---:|
| index | **0.7214** | 0.7269 | 0.7370 | 0.8546 | 1.0721 | **1.5240** | 1.3640 |
| claim | `#weekday_index_monday` | `#weekday_index_tuesday` | `#weekday_index_wednesday` | `#weekday_index_thursday` | `#weekday_index_friday` | `#weekday_index_saturday` | `#weekday_index_sunday` |

So the weekday-blind mean is not a mild approximation: it reads a Saturday **−36.18%** and a Monday
**+30.12%** *before any real deviation exists*, with a worst cell of **+220.74%** at 81-777, day 543, hour 22
(`#d1_gap_saturday`, `#d1_gap_monday`, `#d1_gap_worst`). Both extremes are asserted against the contract's
expected index, and the index is derived two independent ways — from the stored `purchase_weekday_iso` and
from the local-day axis of the **exact city series** `cityCnt` — which still includes the cells the release
gate suppresses — with the two required to agree (`#weekday_index_population`).

## 4. The driver equation (E2)

```
log(y_t) = α + Σ_m γ_m · 1[month_t = m]  +  Σ_w δ_w · 1[dow_t = w]  +  β' x_t  +  ε_t       (1)
```

`y_t` is total MCC 5812 transactions on calendar day `t`; `x_t` = rainy fraction, mean temperature (°C),
mean wind (km/h) and `event_listings_count`. A second equation, used as a robustness row and as the closest
reconstruction of the inherited result, regresses the **log uplift ratio** instead of the level:

```
log( y_t / B_city(t) ) = α + β' x_t + ε_t                                                     (2)
```

with `B_city(t)` the mean-of-4 same-weekday city baseline. Four specifications are fitted and **all four are published**:

| id | equation | controls | n | k | R² |
|---|---|---|---:|---:|---:|
| `primary` | (1) | month (11) + weekday (6) | 546 | 22 | 0.8731 |
| `no_month` | (1) | weekday (6) only | 546 | 11 | 0.8078 |
| `audit_spec` | (2) | none | 490 | 5 | 0.176 |
| `nb2_glm` | (1) as an NB2 GLM | month + weekday | 546 | 22 | α = 0.034827 |

## 5. The full coefficient table

Every cell carries its standard error, t-statistic and 95% interval; the claim id lists all four. Standard
errors are classical (homoskedastic) OLS for the three OLS rows — no `scipy` here, so the t-quantile is a
Cornish–Fisher expansion in `pipeline/backtest.py` — and model-based for the NB2 row. The audit used
quasi-Poisson sandwich errors, so the two SEs are not expected to agree exactly.

**`primary` — log(count), month + weekday.** *Our headline specification.*

| driver | β | se | t | 95% CI | claim |
|---|---:|---:|---:|---|---|
| rain | −0.396329 | 0.040702 | **−9.74** | [−0.476289, −0.31637] | `#driver_primary_rain` |
| temperature | 0.030389 | 0.002668 | 11.39 | [0.025148, 0.03563] | `#driver_primary_temperature` |
| wind | −0.001923 | 0.001383 | −1.39 | [−0.004641, 0.000794] | `#driver_primary_wind` |
| events | 0.011194 | 0.002194 | **5.1** | [0.006883, 0.015505] | `#driver_primary_events` |

**`no_month` — the same without month dummies.** *How much season the month dummies absorb.*

| driver | β | se | t | 95% CI | claim |
|---|---:|---:|---:|---|---|
| rain | −0.366977 | 0.04791 | −7.66 | [−0.461092, −0.272862] | `#driver_no_month_rain` |
| temperature | 0.044284 | 0.001674 | 26.46 | [0.040996, 0.047572] | `#driver_no_month_temperature` |
| wind | −0.003988 | 0.001629 | −2.45 | [−0.007188, −0.000788] | `#driver_no_month_wind` |
| events | 0.017632 | 0.002365 | 7.45 | [0.012985, 0.022278] | `#driver_no_month_events` |

**`audit_spec` — equation (2), the log uplift ratio, 490 walk-forward days, no month dummies.**

| driver | β | se | t | 95% CI | claim |
|---|---:|---:|---:|---|---|
| rain | −0.483329 | 0.05685 | **−8.5** | [−0.595031, −0.371628] | `#driver_audit_spec_rain` |
| temperature | 0.005867 | 0.001876 | 3.13 | [0.002182, 0.009552] | `#driver_audit_spec_temperature` |
| wind | −0.003818 | 0.001928 | −1.98 | [−0.007607, −2.9e-05] | `#driver_audit_spec_wind` |
| events | 0.006071 | 0.002159 | **2.81** | [0.00183, 0.010313] | `#driver_audit_spec_events` |

**`nb2_glm` — negative binomial (NB2, `Var = μ + αμ²`), same design as `primary`.** No 95% interval is
published for this row: the fit returns model-based standard errors only, and we do not synthesise one.
rain **−0.394074** (se 0.039267, t **−10.04**) `#driver_nb2_glm_rain` · temperature **0.030641** (se 0.002581,
t 11.87) `#driver_nb2_glm_temperature` · wind **−0.001907** (se 0.001335, t −1.43) `#driver_nb2_glm_wind` ·
events **0.011973** (se 0.002109, t 5.68) `#driver_nb2_glm_events`.

**Reading it honestly.** Rain is the one robust driver: across all four specifications its coefficient lies
in **−0.483 … −0.367** with |t| ≥ **7.66** (`#driver_rain_range`) — the range, not the flattering end.
Temperature and events are **not** robust: a month dummy absorbs the seasonal mean *and* the seasonal
temperature trend together, so temperature reads 0.0304 (t = 11.39), 0.0443 (t = 26.46) without month dummies,
and 0.0059 (t = 3.13) in the ratio specification. **Wind is not significant anywhere** (|t| ≤ 2.45) and we
claim nothing about it. Fit statistics: `#driver_fit_primary`, `#driver_fit_no_month`,
`#driver_fit_audit_spec`, `#driver_fit_nb2_glm`.

## 6. Identification assumptions, before the results

**A1 — Weekday and hour profiles are stable within the sample.** *If violated:* a trend inside a month makes
"normal for this Saturday" wrong in a direction the panel cannot see. *Test:* the weekday index is re-derived
from the parquet independently of the cube and must agree — it does (`parquet_agreement=True`). A slow drift
is untested and flagged.

**A2 — Weather and events are known at the forecast origin.** *If violated:* the backtest is easier than the
future. *Test:* none — this is stated in the artifact as `protocol.weather_assumption`, and it is the single
most important caveat on §9's numbers.

**A3 — The weather join carries no spatial information, so only a city-level coefficient is identified.**
*Test:* **0** of the **10,483** observed local (date, hour) slots differ between postcodes. **We make no
per-district weather claim.**

**A4 — There is no event-free baseline.** `event_listings_count` has minimum **2** across all 546 dates
(`#event_listings_min`), so the event effect is identified off a *seasonal contrast*, not a control period.
*If violated:* the contrast absorbs whatever else co-moves with event density — which is exactly what §8 measures.

**A5 — A month dummy and a seasonal covariate are not separately identified.** *If violated:* temperature and
events absorb each other's trend. *Test:* §5's four-specification range — this assumption is why the table has
four columns of coefficients instead of one.

**A6 — Daily city counts are conditionally Poisson-overdispersed.** *If violated:* the NB2 standard errors
are wrong. *Test:* the dispersion estimate α = **0.034827** and agreement with the OLS row to within 0.002 on
rain (`#driver_fit_nb2_glm`). Flagged, not proven.

**A7 — The aggregation grain is the merchant's calendar day.** *Test:* the daily series is asserted to sum to
the artifact's `rows` exactly — **378,212** (`artifacts/backtest.json` → `protocol.reconciliation`).

## 7. Where our own audit was wrong

The audit we inherited (`research/presentation-assets.md` §3.5, quoted through
`pipeline/backtest.py::AUDITED`) published three results this pipeline re-measured. Two do not survive.

**7.1 The weather-and-events experiment is not reproducible, and we measure the opposite sign.** The audit
reported that adding weather and events to a seasonal-naive base made it **worse** — **29.2% / 206.9** and
**29.5% / 210.6**, against a **26.4% / 188.5** base (`#audited_snaive_weather`,
`#audited_snaive_weather_events`). On the same 490 days, with betas re-fitted on the expanding past, we
measure **24.66% / 177.7** and **25.39% / 181.9** (`#backtest_exp_drivers_on_snaive_weather`,
`#backtest_exp_drivers_on_snaive_weather_events`) — an **improvement**, not a degradation. The audit's design
is not recoverable from its text and we did not tune towards its numbers, so the claim *"weather and events
do not improve the forecast"* is **withdrawn**.

**7.2 The audited rain coefficient comes from an equation without month dummies.** The audit reports
**β_rain = −0.364 (t = −8.8)**, **β_temp = +0.0063 (t = +4.5)**, **β_events = +0.0031 (t = +1.9)**
(`#driver_audited_rain`, `#driver_audited_temperature`, `#driver_audited_events`) under the phrase *"a
multiple regression on the month-controlled uplift"* — where the month control sits in the **dependent
variable**, not among the regressors. `no_month` matches the rain coefficient at −0.3670 (t = −7.66);
`audit_spec` matches its t at −0.4833 (t = −8.5); **no single specification matches all three audited
coefficients**, and the event coefficient is matched by neither (0.0061 or 0.0176). The audited triple was
therefore not produced by one equation and must only be quoted with its specification attached.

**7.3 What the disagreement costs.** The deck's slide-5 numbers (rain −9.7 / −8.5, temperature +11.4 / +3.1,
events +5.1 / +2.8, wind −1.4 / −2.0) come from our two specifications, not the audit's; §8's control
reproduces the audit's raw leg to the decimal and differs on the controlled leg by 0.5 pp.

**7.4 A number we published and retracted.** A draft of our own deck quoted a **130.4 pp → 13.9 pp** event
spread, not reproducible under any split we tried (`#season_audit_unreproduced`): sweeping {matched-lag-4,
global same-weekday mean, log-uptake} × five quantile splits × two estimators tops out at 113.8 pp. It stays
in the ledger, so the retraction is on the record.

## 8. The season control: almost all of the "event effect" is the season

Days split by `event_listings_count` — the **bottom 140** and the **top 123** of 546 (`#season_split_days`),
which are *not* equal quartiles: equal quartiles (144/144) move the raw high side from +32.9 to +31.1 pp.
Uplift is measured against the **global same-weekday mean**; the control residualises on month + weekday dummies.

| | raw | after month × weekday control |
|---|---:|---:|
| top 123 event days | **+32.9 pp** | **+4.1 pp** |
| bottom 140 event days | **−26.9 pp** | **−4.8 pp** |
| **spread** | **59.8 pp** | **8.8 pp** |
| claim | `#event_spread_raw`, `#season_raw_hi`, `#season_raw_lo` | `#event_spread_controlled`, `#season_ctl_hi`, `#season_ctl_lo` |

The raw leg reproduces the audit's published 32.9 / −26.9 → 59.8 pp **exactly**
(`reproduced_exactly.raw_hi/raw_lo/spread_raw` are all `true` in `artifacts/drivers.json`). The collapse is
the finding: the events signal is real but an order of magnitude smaller than it first appears, and the
residual ±4 pp is not separable from the drivers §5 already reports.

## 9. The forecast (E3) and its intervals

`drivers_on_mean4sw_weather_events` — mean-of-4 same-weekday baseline × `exp(β'x)`, betas re-fitted on the
expanding past. Walk-forward, expanding window, past-only, **490** forecast days from **2025-02-26** to
2026-06-30 (`#backtest_forecast_days`, `#backtest_first_day`).

| metric | value | claim |
|---|---:|---|
| MAPE | **20.51%** | `#forecast_mape_full` |
| MAE | **145.2** transactions/day | `#forecast_mae_full` |
| WAPE | **20.18%** | `#forecast_wape_full` |
| MASE (seasonal naive, m = **7**) | **0.759** | `#forecast_mase_full`, `#backtest_seasonal_period` |
| PICP80 | **80.61%** | `#forecast_picp80` |
| bias | **−0.0344** | `#forecast_bias_full` |

The 80% interval is built from the **expanding past** distribution of realised `y/f` ratios — the 10th and
90th percentiles of everything seen so far, never the future. It covers **80.61%** of days against a nominal
80%, which is calibration and not merely narrowness: an interval that covered 60% would be a narrower number
and a worse product. Full comparison against the baselines, and the interval's failure modes, are `docs/EVALUATION.md`.

## 10. The recommendation layer — four sentences

The product is not a dashboard; it is four sentences, each with a computed source and an explicit state when
it cannot be computed. The panel implements sentences 1–3; sentence 4 is a threshold layer that is
**DESIGN ONLY** and is labelled as such.

| # | Sentence | Computed from | Status |
|---|---|---|---|
| 1 | *Dziś spodziewaj się ~X transakcji (± band).* | `M.winStats` → `s.a / 3` (3-hour window around the hour) | **runs** |
| 2 | *To o N% więcej niż typowa sobota w czerwcu.* | `s.rel = s.a/s.v − 1` against the weekday-matched baseline | **runs** |
| 3 | *Główny czynnik: deszcz — wkład ±N pp.* | `β_rain` from §5 and the day's rain; the panel prints the driver, not a re-forecast | **runs** |
| 4 | *Obsada: zmiana wzmocniona. Promocja: tak.* | a staffing/promotion threshold on sentences 1–2 | **DESIGN ONLY** |

Two honest corrections to the deck's rendering of these sentences. First, sentence 1's band in the deck is
labelled **P10–P90**, but the panel prints a **95% Poisson band** — `rel ± 1.96/√base`, capped at ±150%
(`#band_z`). Both are legitimate; they are not the same interval, and the document wins over the slide.
Second, **`THIN = 12`** (`#thin_base_transactions`): when the 3-hour window's baseline falls below 12
transactions the reading **escalates** code → parent → city and, at the city, is printed *with* its band
rather than withheld — defect D4's fix. A number is never hidden behind a drawn curve.

## 11. The non-obvious steps, in full

**The UTC binding** — skipping it costs an hour all summer, silently:

```sql
timezone('Europe/Warsaw', TIMESTAMP '2025-07-01 12:00:00')          -- WRONG: no-ops, returns 12:00
timezone('Europe/Warsaw', (<naive ts>) AT TIME ZONE 'UTC')          -- RIGHT: 12:00 -> 14:00
```

**The four-same-weekday slice, built from explicit indices** — `y[i-7:i-29:-7]` returns an empty array when
`i-29 < 0`, and `y[i-7:i-27:-7]` returns **three** values where four are meant, which is the difference
between MAPE 23.55 and the audited 24.07:

```python
def _same_weekday(y, i, k=4):        # None ⇒ the panel says "brak historii"
    idx = [i - 7 * j for j in range(1, k + 1)]; return None if idx[-1] < 0 else y[idx]
```

**The season control**, in three lines of numpy — the uplift, then the residual on month + weekday dummies:

```python
u_season = y / dow_mean[dow] - 1.0            # uplift vs the global same-weekday mean
Xc = np.column_stack([np.ones(len(y))] + [(month == m) for m in range(2, 13)] + [(dow == w) for w in range(2, 8)])
resid = u_season - Xc @ np.linalg.lstsq(Xc, u_season, rcond=None)[0]     # residual, month x weekday
```

**The interval**, from the expanding past and never from the future:

```python
r = y[35:i] / np.maximum(f[35:i], 1e-9)      # realised ratios seen SO FAR
lo[i], hi[i] = f[i] * np.percentile(r, 10), f[i] * np.percentile(r, 90)
```

## 12. What would falsify this

- **The weekend index.** Re-derive `weekday_index` from the parquet and compare with `baseline.json`; if
  Saturday is not 1.5240 ± 0.01, the local-hour axis is wrong and every curve in the panel is wrong.
- **Rain under a fifth specification.** Add a day-of-year harmonic (the audit's own §3b design) instead of
  month dummies. If rain's t falls inside ±2, the "robust driver" claim dies.
- **The season control.** Re-run it against the trailing matched baseline instead of the global same-weekday
  mean: the raw spread collapses to ~9.9 pp and the 59.8 → 8.8 story is an artefact of the reference chosen.
- **The interval.** Rebuild it as a Gaussian band around the forecast. PICP80 should move well below 0.80,
  which would show the empirical-ratio interval is doing work rather than tracking the point forecast.

## 13. Known limitations

- **The forecast sees its own covariates.** Assumption A2 is load-bearing for every §9 number: weather and
  events are known at the origin, so the backtest is a *hindcast with known covariates*, not a live forecast.
  A real forward forecast needs a weather feed and an event schedule, and the panel says so.
- **Everything is one city and one category.** MCC 5812 only, and `81-777` alone holds 51.1% of volume, so
  the city series is largely one street and the driver coefficients describe Sopot's restaurant trade, not a market.
- **The driver layer is explanatory, not prescriptive.** No specification identifies a *causal* effect of
  rain or events: both are correlated with season and with each other, and A5 says the data cannot separate
  them. The panel therefore reports the driver as an explanation and never multiplies it into a claim about
  a specific venue's revenue.
- **`nb2_glm` has no published interval** and its errors are model-based, so it is a robustness row, not a
  headline source. **Sentence 4 of the recommendation layer is `DESIGN ONLY`**: its thresholds exist in the
  deck, not in the code.
