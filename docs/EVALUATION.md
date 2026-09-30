# EVALUATION — the backtest, the ablation, and every number we ship

This document owns every figure in the submission. It states the protocol before the results, reports the
baselines beside our model rather than instead of them, and ends with a table that binds each published
number to the command that re-derives it. **§5 is generated from `docs/claims.json`** — the ledger is the
single source of truth, and a number that is not in it is not published.

## 1. Reproduce

```sh
python3 tools/verify_claims.py    # 197/197 claims verified, ~30 s
python3 -m pipeline.run --src /Users/kulma/Downloads --out artifacts   # rebuilds backtest.json/drivers.json
```

## 2. Protocol

| | Value | Claim |
|---|---|---|
| Design | walk-forward, **expanding window**, **past-only** | — |
| Forecast days | **490** (day indices 56…545) | `#backtest_forecast_days` |
| First / last day | **2025-02-26** / 2026-06-30 | `#backtest_first_day` |
| Target | total MCC 5812 transactions per calendar day, all postcodes | — |
| Seasonal period for MASE | **7** | `#backtest_seasonal_period` |
| Interval | 10th–90th percentile of the **expanding past** distribution of `y/f` ratios | — |
| Weather/events | known at the origin, as a forecast would be | `protocol.weather_assumption` |

At every origin the model is re-fitted on days `0 … i-1` and predicts day `i`; nothing from day `i` or
later enters any parameter or interval. The daily series is asserted to sum to the artifact's `rows`
exactly — **378,212** — so an axis drift between the parquet and the cube is loud.

**Where we deviate from the inherited audit, and why.** The audit's §5.1 specifies **26 weekly origins with
a 7-day horizon** in 2026 (`#audit_protocol_origins`) and a PICP acceptance band of **0.80 ± 0.05**
(`#audit_protocol_picp`). We use **daily origins over 490 days with a 1-day horizon**, because the panel's
unit is a day: a 7-day aggregate would be a quantity no restaurateur asks for. The hourly MASE period
(m = 168) is likewise replaced by m = 7. Both are deviations, not improvements, and the acceptance band is
met either way. The audit also splits a 2025 validation block from a 2026 test block; we do not, because
490 past-only origins leave nothing to tune on.

## 3. Results

Six metrics per candidate. **Bold is ours; the reference sits in an adjacent column.** Every cell is a claim
(§5); the four baselines are the audit's candidate set, and the seven driver-augmented rows are ours.

### 3.1 The four baselines

| Candidate | MAPE | MAE | WAPE | MASE | PICP80 | bias | claim |
|---|---:|---:|---:|---:|---:|---:|---|
| `a_mean4sw` mean of last 4 same weekdays | **24.07** | 169.9 | 23.61 | 0.888 | 0.7816 | −0.0291 | `#backtest_candidate_a_mean4sw` |
| `b_median4sw` median of last 4 same weekdays | **22.8** | **166.3** | **23.11** | **0.869** | **0.7857** | −0.0552 | `#backtest_candidate_b_median4sw` |
| `c_mean7` mean of the last 7 days | 36.91 | 232.9 | 32.36 | 1.218 | 0.7959 | −0.0086 | `#backtest_candidate_c_mean7` |
| `d_snaive` same weekday one week earlier | 26.4 | 188.5 | 26.2 | 0.986 | 0.7959 | −0.015 | `#backtest_candidate_d_snaive` |

**The best baseline is the median of the last four same weekdays, at MAPE 22.8%** — not the mean, and not
the seasonal naive. Note the audit's own `b_median4sw` row is a *different estimator* — **median of recent
Fridays**, **35.4 / 270.0** (`#audited_b_median4sw`) — so the two must never be compared as one method; that
is why our `b_median4sw` row carries no "audited" value in `artifacts/backtest.json`.

### 3.2 The driver-augmented variants

| Variant | MAPE | MAE | WAPE | MASE | PICP80 | bias | claim |
|---|---:|---:|---:|---:|---:|---:|---|
| mean-of-4 × exp(β·weather + events) — **shipped** | **20.51** | **145.2** | **20.18** | **0.759** | **0.8061** | −0.0344 | `#backtest_exp_drivers_on_mean4sw_weather_events` |
| mean-of-4 × exp(β·weather) | 20.86 | 151.1 | 21.0 | 0.79 | 0.7918 | −0.0817 | `#backtest_exp_drivers_on_mean4sw_weather` |
| seasonal naive × exp(β·weather + events) | 25.39 | 181.9 | 25.28 | 0.951 | 0.8082 | 0.0211 | `#backtest_exp_drivers_on_snaive_weather_events` |
| seasonal naive × exp(β·weather) | 24.66 | 177.7 | 24.7 | 0.929 | 0.8041 | −0.025 | `#backtest_exp_drivers_on_snaive_weather` |
| expanding OLS on log(count) + weather + events | 16.13 | 115.7 | 16.08 | 0.605 | 0.8204 | −0.0028 | `#backtest_exp_ols_logcount_weather_events` |
| expanding OLS on log(count) + weather | 16.44 | 119.9 | 16.66 | 0.627 | 0.8327 | −0.0106 | `#backtest_exp_ols_logcount_weather` |
| expanding OLS on log(count), no weather | 21.46 | 156.0 | 21.68 | 0.816 | — | −0.0221 | `#backtest_exp_ols_logcount_no_weather` |

### 3.3 The honest reading of what improves what

- **Adding weather and events improves every base it is added to.** On the mean-of-4 base, **24.07% →
  20.86% → 20.51%**; on the seasonal-naive base, **26.4% → 24.66% → 25.39%**. This is the opposite of the
  inherited audit's finding, and §7 of `docs/MODEL.md` reports the disagreement rather than burying it.
- **The shipped row is not the best number in this document.** The expanding-window OLS on log(count) scores
  **16.13%**, better than the 20.51% we ship, and we do not ship it. Reason: it is an *estimator whose
  coefficients move every day*, so the panel cannot tell a merchant what drives her deviation — and the
  product's second sentence is exactly that. The 20.51% row keeps an explicit, auditable decomposition into
  baseline × drivers. **We ship the explainable model and publish the better one.**
- **MASE below 1 for everything we ship.** 0.759 against the seasonal-naive benchmark, i.e. the shipped
  model has a quarter less absolute error than "the same weekday last week".
- **Bias is small and negative** (−0.0344): a forecast can be accurate and still useless, so we publish it.

## 4. Interval calibration

The 80% interval is built from the **expanding past** distribution of realised `y/f` ratios — the 10th and
90th percentiles of everything seen so far, never the future — which is the audit's own recommendation for a
heavy-tailed count series. Result: **PICP80 = 0.8061** (`#forecast_picp80`) against a nominal 0.80, inside
the audit's 0.80 ± 0.05 band (`#audit_protocol_picp`). That is calibration, not merely narrowness: an
interval tuned to look tight would report 0.60 and would be a worse product. The variants' coverage ranges
**0.7816 … 0.8327** across the table above, all inside the band, so the interval is not an artefact of one
lucky configuration.

## 5. Claim → command

**Generated from `docs/claims.json`; do not edit by hand.** Regenerate with the command in §5.0, edit the
ledger instead, and re-run `python3 tools/verify_claims.py`. §5.1 lists every claim that any of the deck,
the README, the poster or the panel uses. §5.2 lists the numbers those artefacts use that have **no**
verifiable command — a defect, kept visible on purpose.

### 5.0 How this table is produced

```sh
python3 -c "import json,re;rows=json.load(open('docs/claims.json'));print('\n'.join('| %s | %s | %s |' % (r['id'], r['value'], ','.join(map(str,r['used_in']))) for r in rows if any(str(u).startswith(('deck','README','poster','panel')) for u in r['used_in'])))"
```

The `re-run it` column is the ledger's own entry point: `--only <id>` executes exactly the command stored on
that row and prints its value, so a reader can verify one number in about a second. The full command lives in
`docs/claims.json` beside its `statement`.

### 5.1 Numbers that appear in the deck, the README, the poster or the panel

| claim id | value | where it is used | re-run it |
|---|---|---|---|
| `rows` | 378212 | deck s1, deck s3 | `python3 tools/verify_claims.py --only rows` |
| `postcodes` | 62 | deck s1, deck s8 | `python3 tools/verify_claims.py --only postcodes` |
| `merchants` | 347 | deck s1, deck s2 | `python3 tools/verify_claims.py --only merchants` |
| `cards` | 160127 | deck s3 | `python3 tools/verify_claims.py --only cards` |
| `days` | 546 | deck s1 | `python3 tools/verify_claims.py --only days` |
| `median_ticket` | 81.33 | deck s2 | `python3 tools/verify_claims.py --only median_ticket` |
| `peak_hour` | 14 | deck s4 | `python3 tools/verify_claims.py --only peak_hour` |
| `lunch_share` | 45.8 | deck s4 | `python3 tools/verify_claims.py --only lunch_share` |
| `zero_timecode` | 38443 | deck s4 | `python3 tools/verify_claims.py --only zero_timecode` |
| `gate_g1_cards` | 54 | deck s8 | `python3 tools/verify_claims.py --only gate_g1_cards` |
| `gate_g2_merchants` | 25 | deck s8 | `python3 tools/verify_claims.py --only gate_g2_merchants` |
| `gate_all_three` | 17 | deck s8 | `python3 tools/verify_claims.py --only gate_all_three` |
| `gate_volume_share` | 89.95 | deck s8 | `python3 tools/verify_claims.py --only gate_volume_share` |
| `top_postcode_share` | 51.1 | deck s8 | `python3 tools/verify_claims.py --only top_postcode_share` |
| `aggregate_rows` | 378212 | deck s9 | `python3 tools/verify_claims.py --only aggregate_rows` |
| `forecast_mape_full` | 20.51 | deck s6 | `python3 tools/verify_claims.py --only forecast_mape_full` |
| `forecast_mape_baseline_only` | 22.8 | deck s6 | `python3 tools/verify_claims.py --only forecast_mape_baseline_only` |
| `forecast_mape_mean4` | 24.07 | deck s6 | `python3 tools/verify_claims.py --only forecast_mape_mean4` |
| `forecast_mape_snaive` | 26.4 | deck s6 | `python3 tools/verify_claims.py --only forecast_mape_snaive` |
| `forecast_picp80` | 0.8061 | deck s6 | `python3 tools/verify_claims.py --only forecast_picp80` |
| `driver_rain_t_primary` | -9.74 | deck s5 | `python3 tools/verify_claims.py --only driver_rain_t_primary` |
| `driver_rain_t_auditspec` | -8.5 | deck s5 | `python3 tools/verify_claims.py --only driver_rain_t_auditspec` |
| `driver_events_t_primary` | 5.1 | deck s5 | `python3 tools/verify_claims.py --only driver_events_t_primary` |
| `driver_events_t_auditspec` | 2.81 | deck s5 | `python3 tools/verify_claims.py --only driver_events_t_auditspec` |
| `aggregate_size_mb` | 4.55 | deck s9 | `python3 tools/verify_claims.py --only aggregate_size_mb` |
| `event_spread_raw` | 59.8 | deck s5 | `python3 tools/verify_claims.py --only event_spread_raw` |
| `event_spread_controlled` | 8.8 | deck s5 | `python3 tools/verify_claims.py --only event_spread_controlled` |
| `raw_schema_columns` | 72 | deck s3 | `python3 tools/verify_claims.py --only raw_schema_columns` |
| `weather_source_rows` | 2030965 | deck s3 | `python3 tools/verify_claims.py --only weather_source_rows` |
| `event_ids_distinct` | 2819 | deck s3 | `python3 tools/verify_claims.py --only event_ids_distinct` |
| `gis_addresses` | 3767 | deck s3 | `python3 tools/verify_claims.py --only gis_addresses` |
| `gis_sectors` | 151 | deck s3 | `python3 tools/verify_claims.py --only gis_sectors` |
| `address_share_passing18` | 19.0 | deck s3, deck s8 | `python3 tools/verify_claims.py --only address_share_passing18` |
| `zero_timecode_pct` | 10.2 | deck s3, deck s4 | `python3 tools/verify_claims.py --only zero_timecode_pct` |
| `driver_primary_rain` | beta=-0.396329; se=0.040702; t=-9.74 ci95=[-0.476289, -0.31637] | deck s5 | `python3 tools/verify_claims.py --only driver_primary_rain` |
| `driver_primary_temperature` | beta=0.030389; se=0.002668; t=11.39 ci95=[0.025148, 0.03563] | deck s5 | `python3 tools/verify_claims.py --only driver_primary_temperature` |
| `driver_primary_wind` | beta=-0.001923; se=0.001383; t=-1.39 ci95=[-0.004641, 0.000794] | deck s5 | `python3 tools/verify_claims.py --only driver_primary_wind` |
| `driver_primary_events` | beta=0.011194; se=0.002194; t=5.1 ci95=[0.006883, 0.015505] | deck s5 | `python3 tools/verify_claims.py --only driver_primary_events` |
| `driver_audit_spec_rain` | beta=-0.483329; se=0.05685; t=-8.5 ci95=[-0.595031, -0.371628] | deck s5 | `python3 tools/verify_claims.py --only driver_audit_spec_rain` |
| `driver_audit_spec_temperature` | beta=0.005867; se=0.001876; t=3.13 ci95=[0.002182, 0.009552] | deck s5 | `python3 tools/verify_claims.py --only driver_audit_spec_temperature` |
| `driver_audit_spec_wind` | beta=-0.003818; se=0.001928; t=-1.98 ci95=[-0.007607, -2.9e-05] | deck s5 | `python3 tools/verify_claims.py --only driver_audit_spec_wind` |
| `driver_audit_spec_events` | beta=0.006071; se=0.002159; t=2.81 ci95=[0.00183, 0.010313] | deck s5 | `python3 tools/verify_claims.py --only driver_audit_spec_events` |
| `season_raw_hi` | 32.9 | deck s5 | `python3 tools/verify_claims.py --only season_raw_hi` |
| `season_raw_lo` | -26.9 | deck s5 | `python3 tools/verify_claims.py --only season_raw_lo` |
| `backtest_candidate_a_mean4sw` | MAPE=24.07; MAE=169.9; WAPE=23.61; MASE=0.888; PICP80=0.7816; bias=-0.0291 | deck s6 | `python3 tools/verify_claims.py --only backtest_candidate_a_mean4sw` |
| `backtest_candidate_b_median4sw` | MAPE=22.8; MAE=166.3; WAPE=23.11; MASE=0.869; PICP80=0.7857; bias=-0.0552 | deck s6 | `python3 tools/verify_claims.py --only backtest_candidate_b_median4sw` |
| `backtest_candidate_c_mean7` | MAPE=36.91; MAE=232.9; WAPE=32.36; MASE=1.218; PICP80=0.7959; bias=-0.0086 | deck s6 | `python3 tools/verify_claims.py --only backtest_candidate_c_mean7` |
| `backtest_candidate_d_snaive` | MAPE=26.4; MAE=188.5; WAPE=26.2; MASE=0.986; PICP80=0.7959; bias=-0.015 | deck s6 | `python3 tools/verify_claims.py --only backtest_candidate_d_snaive` |
| `backtest_exp_drivers_on_mean4sw_weather_events` | MAPE=20.51 MAE=145.2 WAPE=20.18 MASE=0.759 PICP80=0.8061 bias=-0.0344 | deck s6 | `python3 tools/verify_claims.py --only backtest_exp_drivers_on_mean4sw_weather_events` |
| `forecast_mae_full` | 145.2 | deck s6 | `python3 tools/verify_claims.py --only forecast_mae_full` |
| `forecast_wape_full` | 20.18 | deck s6 | `python3 tools/verify_claims.py --only forecast_wape_full` |
| `forecast_mase_full` | 0.759 | deck s6 | `python3 tools/verify_claims.py --only forecast_mase_full` |
| `forecast_bias_full` | -0.0344 | deck s6 | `python3 tools/verify_claims.py --only forecast_bias_full` |
| `privacy_thresholds` | minCards=30; minMerchants=3; maxShare=3/4 | deck s8, panel | `python3 tools/verify_claims.py --only privacy_thresholds` |
| `privacy_fixtures` | fixtures=18 | deck s9 | `python3 tools/verify_claims.py --only privacy_fixtures` |
| `privacy_suite_passed` | 31 passed | deck s9 | `python3 tools/verify_claims.py --only privacy_suite_passed` |
| `deps_stdlib_only` | duckdb=ok numpy=ok jsonschema=absent scipy=absent | README | `python3 tools/verify_claims.py --only deps_stdlib_only` |
| `band_z` | 1.96 | deck s7, panel | `python3 tools/verify_claims.py --only band_z` |
| `released_codes` | 17 | deck s8 | `python3 tools/verify_claims.py --only released_codes` |
| `suppressed_codes` | 37 | deck s8 | `python3 tools/verify_claims.py --only suppressed_codes` |
| `suppressed_volume` | 33197 | deck s8 | `python3 tools/verify_claims.py --only suppressed_volume` |


### 5.2 Numbers in those artefacts that have NO command — defects, not details

| Where | Number | Why it has no command |
|---|---|---|
| deck slide 3 | `151 sektorów (105 obserwowanych, 34 wnioskowane, 12 ekstrapolowanych)` | The repo's own rule (`pipeline/enrich.py::polygon_confidence`) grades the same 151 sectors **116 / 24 / 11** (`#sectors_observed`). The audit's 105/34/12 applies a third criterion (`extrapolated_pct < 10`) that the shipped sector model does not carry, so it is **MEASURED-AUDIT** and not reproducible here. **The deck's split is wrong for this repository.** |
| deck slide 9 | `Seven stages, one command` | `pipeline/run.py` prints **eight** stages (`[1/8]`…`[8/8]`). The diagram on that slide draws seven arrows. |
| deck slide 8 | `Bramka prywatności: 6 testów, 18 przypadków` | Stale. The privacy suite runs **31** tests (`#privacy_suite_passed`) against **18** reference fixtures (`#privacy_fixtures`). |
| deck slide 5 | `the film's draft claimed +38%` | The film's own reconciliation file calls it a self-declared placeholder with no model behind it. |
| README | `MAPE 24.1 %, the best of five candidate methods` | The best candidate in `artifacts/backtest.json` is **22.8%** (`b_median4sw`); **24.07%** is `a_mean4sw`. The README's claim id `#backtest_mape_base` does not exist in the ledger. |
| README | `Efekt wydarzeń 59,8 pp → 9,0 pp` | The artifact says **8.8 pp** (`#event_spread_controlled`). |
| README | `β = −0,364 (t = −8,8)` under `#driver_rain_t` | That id does not exist. −0.364 / −8.8 is the **audited** pair (`#driver_audited_rain`, `docs/MODEL.md` §7.2); our primary specification reports **−9.74** (`#driver_rain_t_primary`). |
| README | `docs/claims.json — 21 rows` | The ledger holds **197** rows. |
| README §1 | `make data … stops on its own assertion — 2025-10-26 should hold 1500 distinct local minutes, got 301` | Stale. `python3 -m pipeline.run` currently runs all eight stages to completion and exits **0**. |
| README §1 | `app/index.html is not in the tree yet` | It is in the tree and serves at `http://127.0.0.1:8098/app/` (`docs/RUN.md` §4). |

**An unexplained number is a defect even when it is right.** Every row above is either stale, misattributed,
or measured by a rule this repository does not implement; none of them should survive into the next build.

## 6. How to falsify this

Three concrete perturbations a sceptic can run in a minute each. Each one is designed to break a specific
claim, not to confirm it.

1. **Break the metric layer.** `y=[10,20]`, `f=[12,18]` must give MAPE **15.0%**, WAPE **13.33%**, MAE 2.0
   (`#metric_selftest`). If the harness's own arithmetic is wrong, every number in §3 is wrong — this is the
   cheapest test of the whole evaluation.
2. **Take the fourth same-weekday value away.** `pipeline/backtest.py::_same_weekday` builds its indices
   explicitly because the natural slice `y[i-7:i-27:-7]` returns **three** values where four are meant:
   MAPE becomes **23.55** instead of the audited **24.07**, and `a_mean4sw` stops reproducing. Change the
   slice and watch `#backtest_candidate_a_mean4sw` fail — that is the reproduction test, not a coincidence.
3. **Replace the interval with a Gaussian band.** `interval_from_history` uses the empirical 10th/90th
   percentiles of past `y/f` ratios. Swap in `f ± 1.28·σ` and PICP80 moves away from **0.8061**
   (`#forecast_picp80`); if it did not, the empirical interval would be decorative.
4. **Re-run the pipeline from scratch.** `python3 -m pipeline.run --src /Users/kulma/Downloads --out /tmp/x`
   must reproduce `artifacts/aggregate.json` **byte for byte** (`#aggregate_sha256`). We verified this: a
   fresh run into a scratch directory produced an identical SHA-256. If it ever differs, `generated` or the
   sort order has picked up wall-clock state.
5. **Delete a row from the ledger and watch `make verify` fail.** The harness matches whole tokens, so a
   doctored `1378212` no longer satisfies `378212`. If you can make a row pass with a wrong value, the
   harness is broken and you should say so.

## 7. Known limitations

- **The forecast sees its own covariates.** Weather and event listings are known at the origin, so §3 is a
  backtest with known future covariates — the honest description of how the panel would be used with a
  weather feed, and not a live forecast.
- **The target is the city, not the venue.** Everything here scores daily *city* totals. The panel applies
  the seasonal shape and the drivers to a single postcode; no per-venue accuracy is measured anywhere, and
  none should be inferred from §3.
- **490 origins are not independent.** Expanding-window origins share almost all their training data, so the
  metric differences between adjacent candidates (20.51 vs 20.86) are inside the noise of the comparison —
  we report them because they are measured, not because the ordering is significant.
- **The better model is not the shipped model.** §3.3 explains why; a reader who wants the most accurate
  number in this document should read the `ols_logcount_*` rows, and a reader who wants the product should
  read the shipped row.
- **MASE's two conventions disagree by 1.45%.** `MASE = 0.759` uses the audit's literal formula with its
  `N/(N−m)` inflation; the standard form is **0.770** (`MASE_std`). Both are in the artifact and neither is
  silently preferred.
