# RUN — one command to run everything

*Sopocka Strona Biznesu* runs from this directory with Python 3 and `make`. `make data` rebuilds every
published artifact from the Organiser Data, `make check` runs the tests, `make verify` re-derives every
number in the submission, and `make demo-ready` proves the panel renders real data. **Serve the panel
over HTTP**: it fetches `artifacts/aggregate.json`, and a browser refuses that fetch from `file://`.

## 1. Run it locally

```sh
make run PORT=8098    # serves this repo at http://127.0.0.1:8098/app/  → HTTP 200, 6,202 bytes
```

## 2. Prerequisites and data

Python 3.11+ with `duckdb` and `numpy` — nothing else, and `scipy` and `jsonschema` are deliberately
absent (`docs/claims.json#deps_stdlib_only`). GNU `make`; Node 18+ for `make demo-ready`. The parquet is
Organiser Data, never redistributed (challenge §7.2–7.4): `data/MANIFEST.sha256` pins it and
`data/samples/` holds the k-anonymised extract a reader may open. Only `SRC=/Users/kulma/Downloads Only `SRC=/Users/kulma/Downloads make data` needs the parquet itself.

## 3. The targets

| Command | Produces | Measured |
|---|---|---|
| `make data` | `artifacts/{aggregate,baseline,backtest,drivers}.json` + `data/samples/` | ≈10 s |
| `make check` | `62 passed` — pipeline, contract, models, privacy | 11 s |
| `make verify` | `186/186 claims verified` — re-runs every row of `docs/claims.json` | 31 s |
| `make demo-ready` | `3 presets · 39/39 assertions passed`; screenshots into `research/evidence/demo-ready/` | 6 s |

`make demo-ready` needs the server already up (`make run PORT=8098`, then `make demo-ready PORT=8098`).
`make deck` rebuilds `docs/deck/deck.pdf` (Chromium print-to-PDF). We do not run it, because it rewrites
a file another owner holds; `python3 tools/make_deck.py --check` reads it instead — `ok: %PDF header,
page count within limit, size within limit`, 0.81 MB.

## 4. What a juror opens

**<http://127.0.0.1:8098/app/>** — a three-venue chooser over the full panel, load status in the header.
Venue deep-links are in `app/states/index.json`, e.g.
`http://127.0.0.1:8098/app/panel.html?stan=molo&data=2026-06-20&g=19`.

**Never open `app/panel.html` over `file://`.** The loader's `fetch()` of `../artifacts/aggregate.json`
is blocked for a `file://` origin, so the panel prints *„Brak danych — nie udało się wczytać
aggregate.json"* and the splash *„Panel nie pokazuje żadnej liczby"*. There is no fallback mode —
`Dane przykładowe` was deleted — so a `file://` page shows **no numbers**, not wrong ones; but an empty
panel reads as broken, so use the server.

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `127.0.0.1:8099/app/` returns **404** for every path | A second static server already owns `127.0.0.1:8099`. The bind does not fail: yours takes `*:8099` and the more specific socket answers first | `make run PORT=8098` |
| Panel shows *„Nie udało się wczytać danych"* | Opened over `file://`, or no `aggregate.json` | Serve over HTTP; `make data` |
| `make demo-ready` reports 0 presets | No server on `$(PORT)` | Start `make run PORT=8098` |

## 6. Known limitations

- **`make data` needs data we may not ship**: a clean clone runs the panel but cannot rebuild the
  aggregate; committing `artifacts/*.json` is what closes that gap for a reader.
- **Verified on one machine**, where `127.0.0.1:8099` is already taken — hence the §5 trap. `make
  deck`'s runtime is unquoted because we measured its artifact, not the rebuild.
