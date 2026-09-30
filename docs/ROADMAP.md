# ROADMAP — what we tried, what we found, what we concluded

*Sopocka Strona Biznesu · Visa Data Sprint · 29–30 September 2026.*
Read this if you want to judge the work rather than the result. The deck shows what survived; this
document shows what did not, and why the surviving version is different from the one we started with.

**Number provenance — the rule this file obeys.** Two citation kinds appear below, and no third exists.
`cmd:` is a command in this repository that prints the number — today `make data` (which prints a counter
for every row it keeps or excludes), `make check`, `make verify`, `make sample`. `audit:` is a reading from
`../research/*.md`, marked **MEASURED-AUDIT**: the audit captured the command and its literal output, but
the matching row in `docs/claims.json` is not written yet, so a MEASURED-AUDIT number is traceable to a
section rather than to a `make` target. A number with neither citation is not in this document. Where two
audits disagree, both readings appear with their sources and we say which denominator each uses.

**How to read an entry.** `TRIED` names what we ran; `FOUND` reports what the machine printed;
`CONCLUDED` is what we changed; `NOT PROVEN` names the falsifier — the measurement that would overturn
the conclusion, and whether we ran it. A phase that ended `0 completed` on its own todo list is reported
as a phase that failed.

---

## The eight phases

| # | Phase | Window (CEST) | Verdict |
| --- | --- | --- | --- |
| P0 | Archive access and the encrypted dataset | 28 Sep 18:01 → 29 Sep 12:01 | **Failed by this route** — the archive was never opened here |
| P1 | Municipal site replica (`karta.sopot.pl`) | 29 Sep 13:02 → 14:28, re-render 30 Sep 03:29 | **Shipped, verified** — 0-diff on Aktualności |
| P2 | Geo-spatial and weather enrichment | 28 Sep 23:27 → 29 Sep 20:12 | **Shipped, documented** — accuracy caveats explicit |
| P3 | Merchant panel, model and module docs | 29 Sep ≈03:00 → 18:37 | **Prototype complete**, demo-selection defect open |
| P4 | Data cleaning → analytics cube | 30 Sep 01:44 → 02:09 | **Shipped** — pipeline itself unreproducible |
| P5 | Export and packaging | 30 Sep 02:59 → 03:38 | **Partial** — two directories left empty |
| P6 | Film *Rytm miasta* and the card-payment clip | 29 Sep 22:23 → 30 Sep 01:14 | **One clip delivered**; the main film not copied in |
| P7 | Finalisation and the ten-agent audit fleet | 30 Sep 03:29 → 04:12+ | In progress at time of writing |

Total measured agent time in the product phases is **≈ 1 h 53 m** across 15 logged sessions, inside a 34-hour artifact-to-artifact span. Phases P2, P3, P4 and P6 left no local transcript and are estimated, not measured. `audit: work-timeline.md §4` (MEASURED-AUDIT)

---

## Phase P0 — archive access and the encrypted dataset

The official dataset arrived as two password-protected archives. We spent one whole session trying to
open one of them by cryptanalysis. We failed. Everything below is kept because the failures are the
most transferable thing in this repository.

| Decision | Rejected alternative | Reason (as recorded) |
| --- | --- | --- |
| Identify the encryption scheme before attacking it | Start with a wordlist against both archives | Two archives, two schemes; AES is not worth a dictionary attack |
| Build John from source into the workspace | Keep retrying Homebrew | `/opt/homebrew` was root-owned and `sudo` was unavailable all night — and a source build is reproducible for a judge |

### R01 — Two archives, two crypto schemes, one of them weak
TRIED: `unzip -l` plus Python `zipfile` on both official archives before writing any attack code.
FOUND: sample = `flag_bits 0x1`, `compress_type 99` → **WinZip AES**; full = `flag_bits 0x9`, `compress_type 8` → **ZipCrypto with bit 3 (data descriptor) set**. Member sizes 17,525,766,131 B and 87,186,941,001 B.
CONCLUDED: scope the attack to the 84.2 GB ZipCrypto archive and never spend AES-level effort on the sample. Bit 3 was the detail that later broke everything.
NOT PROVEN: that the two archives had independent passwords. **Falsifier:** obtain the organiser's key and try it against both. We never had the key, so we could not run it.
Evidence: `../research/findings-ledger.md` §A1 · session `025fda05` @ 2026-09-28 22:32:46, 22:35:19

### R02 — Look for the legitimate key before spending compute — and it was on page 1 all along
TRIED: web search plus five fetches of the event site, including the WordPress REST API (`/wp-json/wp/v2/pages?per_page=100`), and download of four official instruction PDFs into `guides/`.
FOUND: the REST dump exposed an undocumented slug `danedatasprint` ("POBIERZ DANE") holding the download links; the PDFs state the password is *"provided by the organiser"*. **The password is printed in plain sight on page 1 of the organiser's own challenge PDF.**
CONCLUDED: the key was never a secret to be broken — it was a distribution step we had not read. Every hour of cryptanalysis was an hour spent working around a process. The lesson we submit: *a password you are not supposed to have is not a data-access plan.*
NOT PROVEN: that we would have found it sooner with a full read of the challenge document. **Falsifier:** time the read. We cannot re-run a night we already spent.
Evidence: `../research/findings-ledger.md` §A2 · `../research/submission-requirements.md` §1.1 · session `025fda05` @ 22:33:08–22:34:47

### R03 — The check byte depends on a flag bit nobody mentions: twelve lines beat an hour of guessing
TRIED: a 1,940-candidate targeted wordlist (event names, organiser names, Kraków/Sopot, date strings) against the ZipCrypto archive, checking the 12th decrypted byte.
FOUND: **7 candidates "matched"** on the first pass and **9 on the second**; every one failed on real decryption with `RuntimeError: Bad password`. 1,940 / 256 ≈ **7.6** expected by chance. Reading CPython's `zipfile.py` gave the reason: `if flag_bits & 0x8: check_byte = (_raw_time >> 8) & 0xff else: check_byte = (CRC >> 24) & 0xff`. The target has bit 3 set, so the check byte is the **DOS-time high byte**, not the CRC MSB — `zip2john` independently reported `ts=A764 cs=a764` → `0xA7`.
CONCLUDED: a 1-byte header check is a *filter*, never a *result*; validate by inflating real plaintext (we looked for the Parquet magic `PAR1`). **Factor 12 separates our first guess from the correct answer, and the reference implementation was on disk the whole time.**
NOT PROVEN: that no password in rockyou opens the archive. The sweep was killed at 60 s; see R05.
Evidence: `../research/findings-ledger.md` §A5–A6 · `~/Downloads/temp/full.zip2john.log` · session `025fda05` @ 22:35:46, 22:36:11, 22:37:28, 22:38:41

### R04 — The self-test that could not fail, because Python cannot write an encrypted zip
TRIED: build a `test.zip` with a known password (`tajneHaslo2026`) and assert the cracker finds exactly that one password.
FOUND: the test reported `worker found: [] (expected: tajneHaslo2026 only)`. Diagnosis: `flag_bits: 0x0` — `zipfile.writestr` after `setpassword` produces an **unencrypted** entry, so the fixture was plaintext from the start and the test could never fail for the right reason.
CONCLUDED: **a self-test that cannot fail is worse than no test: it hid a real bug, and it was the reason 16 convincing false positives had to be disproved one by one.** Validate tooling against a positively verified fixture, and check the fixture's own properties before trusting its verdict.
NOT PROVEN: that the corrected cracker would have found the key given time. **Falsifier:** run it to completion against a fixture we can actually verify as encrypted. Not run — the session was interrupted first.
Evidence: `../research/findings-ledger.md` §A7 · `~/Downloads/temp/test.zip` (1,004 B `test.parquet`, still on disk and still misleading) · session `025fda05` @ 22:37:01, 22:39:09, 22:39:30

### R05 — An 84 GB archive member does not fit inside a 60-second tool budget
TRIED: `./zip2john …/datasprint_full_data.zip > full.hash`, then a corrected `zc_crack.py` across all 14,344,391 rockyou entries at a measured **76,585 candidates/s** single-process.
FOUND: `zip2john` timed out twice (`[timed out after 60000ms] [killed by signal: SIGTERM]`) and left **`full.hash` at 0 bytes**; the rockyou sweep was killed by the same timeout. At the measured rate, 14.3 M candidates is ≈ **190 s** multi-process — the tool could have done it; the wrapper could not. `turn/end reason=interrupted`, never resumed.
CONCLUDED: budget the harness, not just the algorithm. Long jobs belong in managed background jobs — the same session had already used that pattern successfully for `brew install` and the john build. **Tool timeouts are a design constraint of agent work and they silently truncate evidence.** The archive is still on disk, still encrypted, still unopened.
NOT PROVEN: that rockyou contains the key at all. **Falsifier:** complete the sweep in a background job and report the miss as a miss. Not run; we obtained the data by the legitimate route instead.
Evidence: `../research/findings-ledger.md` §A8, §E42 · session `025fda05` @ 22:37:34, 22:38:41, 22:40:35 · `turn/end` record

---

## Phase P1 — municipal site replica (`karta.sopot.pl`)

The brief was twenty words: *"Create a locally-hostable static replica of karta.sopot.pl … I'm prototyping a new navigation tab."* The rest of the specification lives in `NOTES.md` and two module documents. This was the most thoroughly engineering-managed phase of the project: 325 tool calls, 318 steps, one session, two sittings.

| Decision | Rejected alternative | Reason (as recorded) |
| --- | --- | --- |
| D1 Mirror every asset locally; `site/` self-contained | Hot-link the live CDN/theme assets | A mockup that needs the live server is not a base for prototyping |
| D2 Generate pages from captured HTML (`build_site.py`) | Hand-edit 161 pages | The nav shell appears **three times per page**; hand-editing cannot stay faithful |
| D3 Keep the CMS nav markup verbatim, one marked insertion point | Refactor the nav into a clean component | The replica must still be the same site; the layout needs no CSS change to accept an eighth item |
| D4 Stub uncaptured routes with the site's own containers | Invent plausible page content | Never fabricate municipal content |
| D5 Rewrite `action` to `#` + `data-mock-action` | Let forms POST to the real CMS | No network request, but the integration contract is preserved verbatim |
| D6 Cookie banner non-blocking (`display:none`, no overlay) | Reproduce the blocking modal | Brief-specified; a documented deviation is engineering, an undocumented one is a bug |
| D8 Self-host Montserrat latin + latin-ext, delete the dead Poppins `@import` | Mirror the full Google Fonts bundle | Poppins is declared but never applied; `ą ć ę ł ń ó ś ź ż` must render |

### R06 — The nav exists three times per page, and only one copy is editable
TRIED: locate the primary menu in captured HTML and rewrite its links for a local replica.
FOUND: every page carries the real menu in `header … .main-menu nav#mobile-menu > ul`, plus **two more copies** under `.offcanvas__area` — one an empty container that `meanmenu.js` fills by *cloning the menu at runtime*, one a static offcanvas copy.
CONCLUDED: edit only the first; document the other two as read-only in `NOTES.md` §2, or the next person edits a copy that is overwritten at runtime. The `<ul>` is centred by a flex parent, so an eighth `<li>` reflows and re-centres on its own: **one `<li>` plus one page is the entire cost of adding the merchant-panel tab.**
NOT PROVEN: that the insertion survives a theme update. **Falsifier:** re-capture after the CMS theme changes and re-run the comparator. The site did change once (R07); the nav structure did not.
Evidence: `karta-mockup/NOTES.md` §2 · `../research/findings-ledger.md` §B9–B10 · session `41f86e90` @ 2026-09-29 13:07:16, 13:29:03, 13:43:11

### R07 — Ten probes chasing a nav-font mismatch that was the live site changing under us
TRIED: chase a residual nav discrepancy with ten purpose-built CDP probes (`shell`, `menuorigin`, `navchain`, `navtext`, `fontnet`, `fontsdiag`, `footer`, `compare`, `interact`, `offcanvas`, `mobilenav`).
FOUND: the nav did not match because (a) the live site fetches its own webfonts, so the local render used fallback metrics, and (b) **between two re-renders a day apart the live nav font changed 16 px → 14 px and the article count moved 131 → 135.** Nothing in the local build had changed.
CONCLUDED: against a live target, measure the target's drift before debugging your own renderer — *"our replica regressed"* is the second hypothesis, not the first. Only a re-capture from live resolved it. The build pipeline was re-run rather than patched, so it absorbs upstream drift by construction.
NOT PROVEN: that the two captures were on the same CMS build. **Falsifier:** diff the live CSS between two captures with an HTTP `ETag`/`Last-Modified` check. We diffed rendered geometry, not stylesheets.
Evidence: `karta-mockup/NOTES.md` §3 · `../research/findings-ledger.md` §B14 · session `41f86e90` @ 13:19:26–13:34:53 and 30 Sep 03:29–03:34

### R08 — Google's Maps API and reCAPTCHA cannot be self-hosted; Leaflet's basemap cannot either
TRIED: mirror `maps.googleapis.com/maps/api/js`, the partner-page Google map, its Google-hosted marker image, and `recaptcha/enterprise.js`, then make the "Punkt obsługi" Leaflet map work offline.
FOUND: the three Google resources require a live, keyed, origin-bound service — a hard boundary, not a missing asset. `leaflet.js`/`leaflet.css` mirror cleanly into `site/vendor/`, but markers and controls render over a **blank frame** without `tile.openstreetmap.org`.
CONCLUDED: stop trying. `src/mock/google-stubs.js` paints a labelled placeholder and defines a no-op `grecaptcha`; the YouTube embed gets a same-size placeholder linking to the original. **"Offline" is a bounded claim, not a slogan** — the styled map frame and all markers work offline, imagery does not, and the README says so.
NOT PROVEN: that no self-hostable reCAPTCHA replacement exists. **Falsifier:** install a local CAPTCHA and re-run the form test. Not run — the brief explicitly asked for a labelled placeholder in that case.
Evidence: `karta-mockup/NOTES.md` §5, §8 · `../research/findings-ledger.md` §B11–B12 · session `41f86e90` @ 13:11:41–13:14:31, 13:40:30–13:40:57

### R09 — A fidelity claim needs a measuring instrument, not an opinion
TRIED: prove the replica matches the live site. No suitable tool was installed, so we wrote `tools/cdp.mjs` — a dependency-free Chrome DevTools Protocol driver — and rendered live and local side by side at 1440×900 and 390×844, diffing computed geometry and typography of the shared shell.
FOUND: **5 page-types byte-for-byte identical, footer within 0.15 px, 0 console errors**; the latest re-render gave **7 of 12 page × viewport combinations identical, including a 0-difference on Aktualności**, with residual diffs only in `footer.y`/`docHeight` on the three pages the live CMS mutates between requests.
CONCLUDED: a number beats an adjective, and the comparator is reusable. `.stage/url_map.txt` (**903 mirrored URLs**) and `.stage/stub_manifest.txt` (**14 route stubs**) make the mirror auditable byte by byte.
NOT PROVEN: that the residual `footer.y` delta is entirely upstream. **Falsifier:** capture the same page twice from live with no local build in the loop and measure the live-to-live delta. We measured live-to-local only.
Evidence: `karta-mockup/NOTES.md` §3 · `karta-mockup/tools/cdp.mjs` · `../research/findings-ledger.md` §B16–B17 · session `41f86e90` @ 13:19:26

### R10 — The live site is itself broken, and that is a design decision
TRIED: faithfully reproduce the Partnerzy directory and its galleries.
FOUND: the CMS emits **671 partner gallery `<img>` tags with an empty `src`** and the real URL parked in `data-url-grafiki`; the handler that should copy it across is missing from the deployed site, so **the images never load on the live site either (671 tags, 0 loaded)**. Our own probe proved it.
CONCLUDED: mirror the images and hydrate them in `mock.js`, but label it an **enhancement, not a regression**, removable with one `<script>` tag — do not copy someone else's bug into a stakeholder demo silently. The same rule produced 14 `STRONA ZASTĘPCZA` stubs built from the site's own containers rather than invented content.
NOT PROVEN: that the upstream handler is permanently missing rather than cached-out. **Falsifier:** re-probe the live gallery after a cache purge. Not run.
Evidence: `karta-mockup/NOTES.md` §4, §5 · `../research/findings-ledger.md` §B13, §B18 · session `41f86e90` @ 14:15:50–14:17:52

---

## Phase P2 — geo-spatial and weather enrichment

Independently of the transactions, the product needed a spatial key and a weather covariate. This phase ran in a Claude artifact thread whose transcript is **not on this machine**; timing is inferred from file mtimes and from the `source_data_field` timestamps embedded in the GIS package. The artifacts are the evidence, and we do not pretend the deliberation is recoverable.

| Decision | Rejected alternative | Reason (as recorded) |
| --- | --- | --- |
| Model postcode sectors from parcels, addresses and the Poczta Polska reference | Invent plausible boundaries, or draw convex hulls by hand | No official geometry exists; a *model* can be labelled and validated, an invention cannot |
| Ship the uncertainty as data layers, not as a caveat paragraph | One reassuring sentence in the README | A reviewer can then recompute the conservative version of every map |
| Carry three boundary layers explicitly | Pick "the" Sopot polygon | The cadastral city, the terrestrial districts and the topographic land footprint disagree by 10.38 km² |

### R11 — Postcode boundaries are not published, so we modelled them and said so
TRIED: get Sopot postal-code polygons to join transactions to places.
FOUND: Poczta Polska publishes no postal boundary geometry. What exists: 278 street/range/premises records covering 155 distinct codes, **3,767 municipal address points**, **5,440 building footprints** and **8,289 parcels** from `mapa.um.sopot.pl/iip/ows`, plus the official PRG boundary (1 polygon, 515 vertices, version 2026-04-13). We built **151 inferred sectors**; the 100 m evidence-proximity mask covers 149 of them. Confidence classes: **105 observed, 12 extrapolated**, the rest intermediate (`observed` = dual-source agreement ≥ 3 **and** 100 m support ≥ 75 % **and** extrapolated share < 10 %).
CONCLUDED: label it loudly — *"not official boundaries published by Poczta Polska… Neither detailed contours nor many decimal places establish the accuracy of an inferred postal boundary"* — and keep conflicting address assignments and 362 review flags visible instead of silently snapping them. **The 12 extrapolated polygons are flagged in the panel, not smoothed away.**
NOT PROVEN: that our sectors match the real delivery rounds. **Falsifier:** obtain the operator's internal PNA geometry and compute the symmetric difference per sector. Not available to us.
Evidence: `../research/geo-enrichment.md` §3.3, §2.1–2.2, §0 · `…/Sopot_GIS_2026-09-29/README_ACCURACY.md`, `validation_report.json` · MEASURED-AUDIT

### R12 — Weather does not vary by postcode at all; we measured it before claiming anything
TRIED: join weather to transaction hours to explain variance, treating it as a per-postcode covariate.
FOUND: `sopot_weather_by_postal_code_2025-01-01_2026-06-30.csv` is **88,049,846 B** and had to be cut into six ~14 MB chunks to move. Across **13,102 hourly timestamps**, the number on which the `is it sunny` flag takes more than one distinct value across the 155 postcodes is **0**; mean cross-postcode SD of temperature is **8 × 10⁻⁶ °C**; exactly one timestamp shows any temperature spread at all (≤ 0.1 °C, float-format noise).
CONCLUDED: **the series is city-level and has been duplicated across 155 postcodes.** We say so on screen. The defensible heterogeneity claim is the other way round: the weather varies by *time*, the *sensitivity* varies by place — "rain costs the beach strip more than the upper town" survives, "it rained harder in Karlikowo" does not.
NOT PROVEN: that the duplication is in the source rather than in our export. **Falsifier:** re-pull from the weather API for two coastal and two inland points and compare. Not run — the join-quality question (`weather_match_status`) stayed open to submission.
Evidence: `../research/geo-enrichment.md` §6.2–6.3 · `../research/findings-ledger.md` §C26 · `~/Downloads/sopot_weather_by_postal_code_*` @ 2026-09-29 20:05, 20:12 · MEASURED-AUDIT

### R13 — "Sopot" is three different polygons depending on who asks
TRIED: clip the model domain to "the city".
FOUND: municipality TERYT `2264011`, official boundary version 2026-04-13. Three areas, all documented: official municipality incl. marine territory **27.717276 km²**; terrestrial cadastral area (districts 1–51) **17.333025 km²**; marine cadastral area (district 52, `226401_1.0052`) **10.384251 km²**. A topographic land footprint from BDOT10k (838 vertices) is a fourth thing and is not a legal boundary.
CONCLUDED: carry all three layers explicitly (`terrestrial_boundary_prg`, `land_footprint_topographic`, marine district) and document the ordering, so no map silently mixes a sea area into a per-capita denominator.
NOT PROVEN: which polygon a municipal procurement would specify. **Falsifier:** ask the city. We did not, and this is a question for the deployment phase.
Evidence: `../research/geo-enrichment.md` §1.1 · `../research/findings-ledger.md` §C24 · `validation_report.json` → `metrics.*` · MEASURED-AUDIT

### R14 — `postcode_premises` is not a commercial-POI layer, so we cannot claim restaurant coverage
TRIED: quantify "premises per postcode" from `postcode_premises.geojson`, as the brief suggested.
FOUND: that layer has **5 features** and its `recipient_type` is `Placówka Pocztowa` — five Poczta Polska post-office records, one of them a compound multipoint; the foreign-postcode leak it failed to catch is `nonSopotPostcode=2527` across 8 codes (`cmd: make data`, stage 4/8). The package contains **no commercial-premises, POI, retail or business-register layer at all**, and `source_manifest.json` confirms the building layer carries "no owners or occupiers".
CONCLUDED: use buildings and address points as the honest commercial-surface proxies, and **never state "X % of restaurants in this area"** — we cannot count restaurants, only card-accepting merchant descriptors. The defensible ratio is the one the data supports: the 18 gate-passing codes contain **717 of 3,767 address points (19.0 %)**, **954 of 5,439 buildings (17.5 %)**, and **337,172 of 378,212 transactions (89.1 %)**. `audit: geo-enrichment.md §4.3`
NOT PROVEN: that 19 % of the addressable surface carries 89 % of *restaurant* volume, as opposed to card volume from MCC 5812 merchants. **Falsifier:** an independent POI register (CEIDG/GUS) joined to the same sectors. Not obtained.
Evidence: `../research/geo-enrichment.md` §4.1–4.3 · `README_ACCURACY.md:109` · MEASURED-AUDIT

---

## Phase P3 — merchant panel, model and module documentation

The product itself was designed here, and this is the only phase whose full transcript is missing. What survives is unusually good evidence of *intent*: two module specifications written in Polish for a business audience, one of which keeps a numbered "requirement evolution" log, plus four generations of prototype and two of map. Every root cause below was found later, by a forensic pass that re-ran the model unmodified against the real data.

| Decision | Rejected alternative | Reason (as recorded) |
| --- | --- | --- |
| D11 Never read card numbers; aggregate to postcode × hour × day | Row-level browsing in the page | Privacy by construction; the loader's column list is explicit |
| D12 Four-level privacy cascade with a reason string per level | Show every postcode, or show nothing | Re-identification risk in a 38,000-person city; suppression must be legible, not silent |
| D13 Inherit to the parent area (code → `81-70x` → `81-7xx`) and hatch what still fails | Show "no data" everywhere | Keeps the map useful while naming the source area in the tooltip |
| D14 Include an event only if the merchant's MCC rose ≥ 15 % vs the trailing 30-day mean (tunable 0–60 %) | Show all city events | The panel must answer "does this event matter *to me*" |
| D15 No distance or event-scale filtering | Filter events by distance from the shop | Documented as an assumption removed from scope, not an oversight |
| D16 Continuous "seismic" magnitude gradient | v3's vector-arrow field showing flow direction | Arrows over-claimed direction the data cannot support |
| D17 Two map modes: global (codes vs each other) and local (one code vs its own 30-day mean) | One mode only | A code can be quiet in absolute terms yet 40 % up on its own baseline |
| D18 The dashboard explains itself with numbers, not written recommendations | Advice text ("hire more staff Friday") | A stated design principle in both module documents |
| D20 Convert GMT → Europe/Warsaw with a per-day DST offset computed at load | Treat the column as local time | The source stores `tran_id_gmt_tm` in GMT; a naive read shifts every bucket |

### R15 — The demo default landed on two of the city's thinnest postcodes
TRIED: render the panel's default state — `Restauracja przy Molo` + `Bistro przy dworcu`, Saturday **2026-06-20 at 19:00**, with the fictional `Koncert letni na Molo` — and measure every number it prints.
FOUND: the two preset coordinates resolve to `81-720` (**16 merchants, 9,711 rows / 546 days**) and `81-805` (**12 merchants, 7,245 rows**), while **51.1 % of all 378,212 transactions sit in one sector, `81-777` (241 merchants, 193,234 rows)**. Against `THIN = 12`, **71 of 72** hours are unreadable for the first venue and **72 of 72** for the second: both read `—`, both lane charts are literal zeros with an axis top of `2e-9`. On the map at that hour, **18 of 151 areas carry a readable number** — 107 read `za mało transakcji`, 26 `dane ukryte`, 16 a parent value, 2 a genuine own value.
CONCLUDED: **the demo was selecting for the data shape, not for the business.** Replace the hand-picked presets with a data-driven feasibility table that scores every candidate venue against the three gates and the baseline base, and make an empty lane a hard failure of `make demo-ready` rather than something a human notices on stage. See `docs/adr/0005`.
NOT PROVEN: that a "good-looking" preset is a *representative* one. **Falsifier:** show the same panel for a median sector and check whether the owner still finds it actionable. Not run — it is a user study, and we ran out of event.
Evidence: `../research/app-forensics.md` §4.0–4.1, §4.8, §7 · `../research/live-repro.md` §4 · `../research/demo-feasibility-table.csv` · re-run of `sopot-model.js` unmodified

### R16 — The baseline averaged every weekday, so a no-event Saturday read +75 %
TRIED: compare "today" against the trailing 30-day mean, as the model did on real data.
FOUND: the real-data path flattened all weekdays: measured day-of-week indices run **1.514 (Saturday) to 0.724 (Monday)**, and **a Saturday with no event at all (2026-06-06) still reads +75 %**. The simulation *had* the correction; the real-data override silently dropped it. The preset day is a Saturday.
CONCLUDED: the baseline is the mean of the last four **same-weekday** observations, computed client-side from the count cube. This is defect D1, and the fix is asserted by the pipeline rather than left to the renderer.
NOT PROVEN: that four weeks is the right window. **Falsifier:** sweep the window length in the backtest and compare MAPE. The 4-week mean is the best of the four candidates we did test (R27), but the window length itself was not swept.
Evidence: `../research/app-forensics.md` §4.4.1, §7 (defect 2) · `contracts/AGGREGATE.md` "What the app must do" · `sopot-model.js:206`

### R17 — We built the privacy gate after the UI, and measured what that cost
TRIED: let a merchant see competitor volume by area, then add k-anonymity afterwards.
FOUND: on real data the **≥30-card gate (G1) and the ≤75 % top-1-share gate (G3) never fired at all** — `pymt_crd_acct_num_raw` is not in the loader's column list, so no card count existed anywhere, and the only implementation of the share rule sat on an invented `STATS` table. Of the **67,204 cells the map paints**, **2,006 (3.0 %) pass all three gates**; **48,404 (72.0 %) have fewer than 3 merchants active in that hour**; 65,197 have fewer than 30 cards; 38,992 have a top-1 share above 75 %. At the pooled postcode grain, **18 of 54 Sopot codes pass** — and the dominant reason is G2, not G1: **21 codes contain exactly one merchant and 8 contain exactly two**, so 29 of 54 fail the 3-entity floor before any share test is applied.
CONCLUDED: **the gate moves in front of the render, not behind it.** The card count becomes a first-class pipeline output (`nCards` per code), the three gates are asserted once in `contracts/privacy.py` and mirrored in the app, the area value escalates to a parent unit only after the *parent* is re-tested on all three gates, and the raster is never painted where the readout is withheld. Ordering was the defect; the arithmetic was fine.
NOT PROVEN: that a 3-gate cell is safe. **Falsifier:** the differencing test G4 — subtract a known own-merchant volume from a released area total and see whether a competitor's volume falls out. G4 is implemented in `contracts/privacy.py`, but the artifact's gate block carries only G1–G3, so it is not yet a release condition.
Evidence: `../research/privacy-compliance.md` §3.2–3.4, §4.2 · `../research/app-forensics.md` §4.2, §7 (defect 5) · MEASURED-AUDIT

### R18 — PKD is what the merchant knows; MCC is what the data has
TRIED: let a restaurant owner identify herself without knowing card-network codes.
FOUND: **no shared key exists between PKD 2007 and MCC.** A merchant knows "56.10.A — Restauracje"; the data has `5812`. The real dataset contains **exactly one MCC value, `5812`, across all 378,212 rows** — five of the six category chips in our own film name MCCs that are absent from the data.
CONCLUDED: ship an explicit curated bridge (`'56.10.A' → {name:'Restauracje', mcc:'5812'}`, 7 entries) plus MCC **groups** so small MCCs can be pooled to satisfy the privacy gate without exposing anyone. The mapping table *is* the onboarding UX, and its honesty limit is that it is curated by hand, not derived.
NOT PROVEN: that the 7-entry bridge is what a Sopot owner would choose. **Falsifier:** card-sort the PKD list with five owners. Not run.
Evidence: `../research/findings-ledger.md` §D38 · `../research/privacy-compliance.md` §3.4 · `sopot-model.js` (`M.PKD`, `M.GROUPS`)

### R19 — The map's visual grammar changed four times, and version 3 was a lie we caught
TRIED: represent transaction intensity spatially, across four generations of map.
FOUND: v1 = per-sector percentage fills like a weather radar; v2 = every postcode shown separately, OSM streets dropped for a stylised outline; v3 = a **vector-arrow field** showing flow direction; v4 = a continuous "seismic" magnitude gradient with click-to-zoom, split into a global and a local mode.
CONCLUDED: arrows over-claimed a direction the data cannot support — a per-sector aggregate has magnitude, not flow. Magnitude reads at a glance and survives a screenshot. **The rejected versions are preserved in the module document's numbered decision log**, which is why we can show the reversal instead of only the survivor.
NOT PROVEN: that a magnitude gradient is the final form. **Falsifier:** a reader study at projection size. Not run.
Evidence: `Dokumentacja — 02 Mapa.md` §1.1 · `../research/findings-ledger.md` §D37, §6.2 · `Mapa v1 (OSM).html` vs `Mapa.html`

### R20 — The event list was fiction while the real city calendar sat unused in the data
TRIED: surface city events on the merchant calendar from an 11-entry hand-written catalogue, with a per-MCC uplift map and an attendance figure.
FOUND: the parquet carries `event_titles_json` with **544 distinct values**, every row marked `event_calendar_match_date`-matched, and **21 real titled city events on the preset day 2026-06-20** (e.g. `Dwa Teatry 2026`, `Soboty z DJ-em w Sopockiej Meduzie`). The app reduced all of it to one hover tooltip while the headline strip ran on invented events. The panel's own footnote admitted it: *"Wydarzenia z godzinami i miejscem: lista przykładowa (kalendarz miasta w danych nie ma godzin ani lokalizacji)."*
CONCLUDED: drive the month strip from `eventsByDay` (real titles) and keep the hand-written catalogue only for the hour/place overlay, clearly marked as enrichment. Two of the eleven hand-placed event pins were also found **offshore, in Gdańsk Bay**, and were corrected.
NOT PROVEN: that the real calendar improves the merchant's decision. **Falsifier:** see R27 — the event effect is mostly season, so a better event *list* does not by itself make events a better *driver*.
Evidence: `../research/app-forensics.md` §4.7.2, §7 (defect 9) · `../research/geo-enrichment.md` §5.2–5.3 · `sopot-model.js:10-22`

---

## Phase P4 — data cleaning and the analytics cube

The single most important transformation in the project — 87 GB of archive down to a 189 k-row, 26 MB analytics cube — is also the least documented. Two `.csv.xz` files appear at 01:44 and two `.parquet` files at 02:09, and the Parquet writer is DuckDB v1.5.6, so the final serialisation at least ran locally.

| Decision | Rejected alternative | Reason (as recorded) |
| --- | --- | --- |
| Column pruning + predicate pushdown on the raw Parquet, export only MCC 5812 Sopot rows | Load the whole archive into a warehouse | This is what makes the project possible on a laptop with no cluster |
| Keep the sentinel rows in the cube and flag them | Delete them silently at ingest | A row that vanishes cannot be counted and reported |

### R21 — The 87 GB → 26 MB reduction was never saved as a script, so it could not regenerate its own dataset
TRIED: find the program that produced `mcc5812_transactions.part0{1,2}.parquet`.
FOUND: a disk-wide ripgrep for the output column names (`sopot_match_basis`, `merchant_postal_code_normalized`, `weather_match_status`) finds the *outputs* and **no producer** — no script, no SQL file, no notebook, no session, no rollout. `~/.zsh_history` holds 749 untimestamped lines with **zero** project keywords, so a human-typed one-liner would have left no trace at all. The only surviving metadata is the writer stamp `created_by = "DuckDB version v1.5.6"`, part01 = **189,106 rows, 2 row groups** — and the reconstruction's first stage reproduces the population exactly: `rows=378212 · overlap_tran_id=0 · parts=189106+189106` (`cmd: make data`, stage 1/8).
CONCLUDED: **this is the reason `pipeline/` exists.** The submission must be able to regenerate its own dataset from the raw archive, or it is an exhibit rather than a project. The pipeline is written so that `make data` reproduces `artifacts/aggregate.json` from source and fails loudly if the row counts move.
NOT PROVEN: that the reconstructed pipeline reproduces the original subset row for row. **Falsifier:** `make data` and compare the row count and the exclusion counters against 378,212 / 38,443 / 2,527 / 6,431. Not yet run — the pipeline is being written now.
Evidence: `../research/work-timeline.md` §P4, §6.3 U4, §7 G3 · `../research/findings-ledger.md` §D31, §E39 · Parquet footer metadata

### R22 — 10.2 % of rows carry a sentinel time that fabricates a 02:00 rush
TRIED: bucket transactions by local hour of day.
FOUND: **38,443 rows (10.2 %) carry `tran_id_gmt_tm = '000000'` and are marked `valid`** — printed by `cmd: make data` stage 4/8 as `zeroTimecode=38443 · share=0.101644`. The loader converted them as `tm.slice(0,2) + offset`, landing every one in hour 00/01: raw 02:00 counts of 105/141/122 against neighbours of 0–5, still a 40-unit hump after the 5-hour smoothing kernel. The concentration varies by postcode — **20.3 % of `81-769`, 18.9 % of `81-861`, 14.8 % of the dominant `81-777`**. The true hourly profile peaks at 13:00–14:00 with 48.7 % of traffic in 11:00–15:00; the panel's placeholder curve overstated 18:00–22:00 by 28–33 %.
CONCLUDED: this is defect D2. Flag the sentinel, keep the rows in the total count, exclude them from hourly views, and surface the count and the rule on screen. A restaurant dataset with a nightly 02:00 spike is not a rounding error; it is a wrong product.
NOT PROVEN: that the sentinel means "time unknown" rather than "midnight". **Falsifier:** check the sentinel's share against the merchant's own open hours. Not run; we treat it as unknown, which is the conservative reading.
Evidence: `../research/presentation-assets.md` §3.7, §3.5 · `../research/app-forensics.md` §4.4.2, §7 (defect 3) · `contracts/AGGREGATE.md` (`excluded.zeroTimecode`) · MEASURED-AUDIT

### R23 — GMT is not local time, and the offset is not a constant
TRIED: bucket transactions by local hour using a fixed offset from the column named `tran_id_gmt_tm`.
FOUND: the source stores UTC `HHMMSS` under a name that invites a naive read, and a single fixed offset is wrong twice a year. The loader resolved the real offset **per day** with `Intl.DateTimeFormat('en-GB', {timeZone:'Europe/Warsaw', hour12:false})` evaluated at local noon, then rolled hours past 24 into the next day.
CONCLUDED: for a hospitality product an hour bucket off by one invalidates the entire pitch, so the conversion is a pipeline responsibility with a test, not a rendering detail. The cube's hour axis is defined as local Europe/Warsaw and the contract says so.
NOT PROVEN: that the DST transition days themselves are clean. **Falsifier:** count rows in the two transition hours each year and compare against the neighbouring days. Not run.
Evidence: `../research/findings-ledger.md` §D34 · `contracts/AGGREGATE.md` "Cell indexing" · `sopot-model.js` (`offsetAt`, the `h >= 24` roll-over)

---

## Phase P5 — export and packaging

| Decision | Rejected alternative | Reason (as recorded) |
| --- | --- | --- |
| Precompute a privacy-gated `aggregate.json` and ship only that | Ship the 26 MB parquet for the browser to aggregate | 26 MB in the browser cost 8–14 s cold and showed fabricated numbers in the meantime. See `docs/adr/0001` |
| Publish the aggregate, never the parquet | Publish the cube "for reproducibility" | Organiser Data is confidential (challenge §7.2–7.4); a column that does not exist cannot leak |

### R24 — 26 MB of Parquet in the browser cost 8–14 seconds, and lied for the first 1.4–2.7 of them
TRIED: avoid a backend by reading the analytics subset directly in the page with `hyparquet` + ZSTD, caching the cube in IndexedDB behind `CACHE_VER = 3`.
FOUND: `hyparquet` parses Parquet in JS but the files are ZSTD-compressed, so the reader needs an explicit compressor and the whole file is fetched into an `ArrayBuffer` first. Measured cold cost **2.9–5.6 s on a fast link and 8–14 s on a 50 Mbps link for 26,071,536 B**, and for the first **1.4–2.7 s** the panel displayed **fabricated** numbers under the label `Dane przykładowe`. The deployment unit was the whole folder plus **six external CDN origins**, any one of which failing re-triggered the fake-data path.
CONCLUDED: the browser keeps the analysis, not the data. The pipeline writes a precomputed, privacy-gated `aggregate.json` (**26.84 MiB → 1.98 MiB**), the app refuses any other contract version rather than falling back, and there is no silent substitute for a failed load — a degraded path renders an explicit state or nothing.
NOT PROVEN: that 1.98 MiB is small enough for a municipal CMS budget. **Falsifier:** measure over the city's actual CDN and on a mid-range phone. Not run.
Evidence: `contracts/AGGREGATE.md` "Why this contract exists" · `../research/karta-integration.md` §0 · `../research/app-forensics.md` §7 (defect 10) · MEASURED-AUDIT

### R25 — Two directories were created for the submission and left empty
TRIED: package the audit reports and the finished film into the submission workspace.
FOUND: `mkdir -p …/Hackathon/research …/Hackathon/rytm-miasta` ran at 2026-09-30 04:02:59 and **both stayed empty**; the film itself lives in `~/Documents/ChatGPT/Hackathon/rytm-miasta/`. Separately, `karta-mockup.zip` (100,258,924 B) was written at 03:35 while `tools/` and `NOTES.md` were still being modified at 03:34–03:37, so the archive does not contain the final toolchain.
CONCLUDED: **packaging is a build step, not a folder action.** Every published artifact is produced by a `make` target from the sources in this repository, and a human copying files between directories is not a release process.
NOT PROVEN: that no other stale copy is in circulation. **Falsifier:** hash every distributed artifact against its `make` output. The manifest in `data/MANIFEST.sha256` is the mechanism; it does not yet cover the zip.
Evidence: `../research/work-timeline.md` §P5, §6.3 U2, U13 · `../research/findings-ledger.md` §E40 · `data/MANIFEST.sha256`

---

## Phase P6 — the film *Rytm miasta* and the card-payment clip

The film is **not a required deliverable** — the words *film* and *video* appear exactly once in the challenge document and nowhere in the Regulamin's deliverable list. We built it anyway, and it taught us the most expensive lesson in the project. `audit: submission-requirements.md §5` (MEASURED-AUDIT)

| Decision | Rejected alternative | Reason (as recorded) |
| --- | --- | --- |
| Publish the negative result: the event effect is mostly season | Keep the raw 59.8 pp headline because it is the better story | See `docs/adr/0003`. A number a juror can overturn in five minutes is a liability, not an asset |
| Re-render no frames; correct in the spoken line and the deck | Re-encode 300 s of finished 1080p to change four numbers | The deck was not yet built, so the correction cost nothing there |

### R26 — The film baked unverified numbers into the picture, and a juror can check them
TRIED: build a 300 s presentation film from a brief, with data overlays.
FOUND: the rendered film shows `475 000 transakcji` where the parquet has **378,212 rows** (overstated by 25.6 %) and five of six category chips name MCCs (**5813, 5814, 5912, 7523, 5462**) that **do not exist in the dataset**, which contains one value, `5812`. Its `+38 %` forecast and its `0.29–0.47` interval are self-declared placeholders in the storyboard. The stated baseline, "mediana ostatnich piątków", is the **worst of the four methods we backtested** (35.4 % MAPE vs 24.1 %). Two things in it are true: the 181-day test window, and the privacy thresholds 30 cards / 3 entities / 75 %.
CONCLUDED: **a silent film shows placeholder numbers with none of the author's hedging.** Every number that ships in any artifact — film frame, slide, panel, README — now has to survive the question "where did this come from?", and `make verify` fails the release if it does not. The correction goes in the deck and in the spoken line; volunteering it is stronger than being caught by it.
NOT PROVEN: that the film's remaining overlays are clean. **Falsifier:** OCR every frame and diff the strings against `artifacts/`. Not run — the film was not re-rendered.
Evidence: `../research/presentation-assets.md` §3.4–3.6, §8 R1 · `../research/submission-requirements.md` §5 · `rytm-miasta/final/rytm-miasta-1080p.mp4` (780,556,064 B, 300.000 s, 9,000 frames)

### R27 — The event effect is mostly season; rain is the robust driver
TRIED: measure whether city events move restaurant card payments, as the whole narrative claims — first raw, then with month × weekday control.
FOUND: grouping days by mean `event_listings_count`, the raw spread between the most-event and least-event quartiles is **59.8 pp** (Q4 +32.9 % vs Q1 −26.9 % against a same-weekday mean). After month × weekday control it collapses to **9.0 pp** (Q4 +4.7 % vs Q1 −4.3 %). In a multiple regression on the month-controlled uplift: **event listings β = +0.0031 (t = +1.9)** — marginal; **rain fraction β = −0.364 (t = −8.8)** — overwhelming; temperature β = +0.0063 (t = +4.5) — clear but small. The backtest over 490 walk-forward days (2025-02-26 → 2026-06-30, expanding window, past-only) puts the mean of the last four same-weekday observations at **MAPE 24.1 % / MAE 169.9** — best of five candidates — while adding weather and events makes the forecast *worse* (29.2 % / 29.5 %).
CONCLUDED: **two claims die and one survives.** We do not claim "our model beats naive" — once you have a recent same-weekday baseline, the weather and event signal is already inside it. The honest product claim is *we hand the owner the baseline she cannot compute herself, plus the drivers that explain the deviation*, and the driver we lead with is rain, not events. The product changed to match: events remain as context, and the deviation is explained by weather first.
NOT PROVEN: that the residual 9.0 pp is causal rather than a better-specified seasonal control. **Falsifier:** a difference-in-differences on event venues against matched non-event venues in the same week. Specified in `docs/ROADMAP.md` §"What we would do with another 24 hours", not yet run.
Evidence: `../research/presentation-assets.md` §3.4 (claim 19), §3.5 · `../research/deck-outline.md` §4 · MEASURED-AUDIT

---

## Phase P7 — finalisation and the audit fleet

| Decision | Rejected alternative | Reason (as recorded) |
| --- | --- | --- |
| One privacy module, every release passes through it | Re-implement the gates in the UI as well | Two implementations drift; the thresholds already drifted once (R30). See `docs/adr/0004` |
| No LLM anywhere in the decision path | Use a model to produce or adjust a number | AI built and analysed the project; it does not manufacture a figure. See `docs/adr/0006` |

### R28 — A repository was initialised, files were staged, and nothing was ever committed
TRIED: put the work under version control.
FOUND: `~/Documents/ChatGPT/Hackathon/.git` was created 2026-09-29 21:31 with `HEAD → refs/heads/main`. `git rev-list --all --count` = **0**; no refs, no `packed-refs`, no index. `git fsck` reports 6 dangling trees while `git cat-file --batch-all-objects` finds **408 blobs and 63 trees** — files were `git add`-ed at least twice and never committed. The product itself (`…/Projects/Hackathon/`) had **no repository at all**, and the panel, model, GIS and cleaning sources lived in `~/Downloads/`.
CONCLUDED: the entry promised "an end-to-end clean programming project" and shipped loose files across three unrelated directories. **A repository with the reconstructed phase history as its commit sequence is the single highest-value remaining action**, and `work-timeline.md` is its commit-message log. This repository is that action.
NOT PROVEN: that the reconstruction is complete. **Falsifier:** a file in the tree with no producer, no mtime and no session. We know of several — `../research/work-timeline.md` §7 lists five evidence gaps, including the entire P2/P3 transcript.
Evidence: `../research/work-timeline.md` §9, §7 · `../research/findings-ledger.md` §E40, cross-reference table · `git fsck --lost-found`

### R29 — The interactive shell recorded none of the work, so the transcript has to be the artifact
TRIED: reconstruct the command chronology from `~/.zsh_history`.
FOUND: 749 lines, **no timestamps**, and **zero** matches for `datasprint|sopot|visa|mcc5812|karta|parquet|duckdb|unzip|john|hashcat|xz|zstd`. No `~/.bash_history` exists. All project shell work ran through agent bash tools.
CONCLUDED: session logs are the **only** command-level record, and any human-typed one-liner is permanently lost — which is almost certainly where the cleaning pipeline went (R21). So the repository keeps its own evidence: every number in these docs cites a command or an audit section, and `make verify` recomputes the ones that have commands.
NOT PROVEN: that no human command mattered. **Falsifier:** we cannot run one — the file has no timestamps and the shell was not recorded. Reported as an unrecoverable gap rather than a clean result.
Evidence: `../research/findings-ledger.md` §E39 · `../research/work-timeline.md` §7 G3 · `~/.zsh_history` @ 2026-09-30 02:59

### R30 — The privacy thresholds were stated two ways, found twice by two agents, and stayed unresolved
TRIED: keep the privacy numbers consistent between the model, the two Polish module documents and the film script.
FOUND: the model and both module documents say **3 merchants / 30 cards / 75 %** — which matches the challenge §3 verbatim. The finalisation brief instructed an audit to *"find internal materials quoting wrong thresholds (30 cardholders / 25 / 50)"*. Independently, on 29 Sep at ~22:30, the Codex film agent **stopped and asked the user to adjudicate** because *"their privacy thresholds differ from the script"*.
CONCLUDED: the same conflict was found **twice, by two different agents, in two different tools, and was still unresolved at submission time.** The fix is structural, not editorial: the thresholds live in exactly one machine-readable place (`contracts/privacy.py`), and every mention in the UI, the deck and these documents is checked against it by `make verify` rather than retyped. This is the concrete reason for `docs/adr/0004`.
NOT PROVEN: that no other conflicting copy exists. **Falsifier:** grep every tracked file for `30`, `75` and `25` near the word *próg*/*threshold* and confirm a single source. Partially run — `make verify-docs` reports the remaining hits; the docx and the film are outside its reach.
Evidence: `../research/findings-ledger.md` §C29, §E29 · `../research/work-timeline.md` §6.3 U6 · `Dokumentacja — 01 Kalendarz.md` §3.1 · Codex rollout `01a0eed5`

---

## What we would do with another 24 hours

Ranked by how much it would change what a juror can verify, not by how interesting it is.

1. **A difference-in-differences on the event effect.** The one headline claim we still cannot defend (R27, residual 9.0 pp at t = +1.9): treated venues named in `event_titles_json`, matched non-event sectors as controls, same week, hour × weekday fixed effects. Needs only the data we have.
2. **Wire gate G4 into the release path.** R17's fix stops the *display* of thin cells; it does not stop a merchant subtracting her own settlement volume from a released area total. G4 is implemented in `contracts/privacy.py`; the artifact's `codeMeta[].gates` block must carry it before it is a release condition.
3. **A URL state on the panel.** `?day=&event=&t=&focus=&lat=&lng=`. A judge cannot currently be handed a link to the good view, and the whole demo depends on someone clicking to the right place.
4. **Restore the 84 GB route properly.** In a background job, with a real hash extraction, so the entry can state what the full dataset contains rather than what our subset contains (R05).
5. **A user test with three Sopot owners.** Every preset, every threshold and the entire PKD→MCC bridge are our inferences about what a restaurateur wants to see (R15, R18). Cheapest way to be wrong at scale.

---

## Known limitations

Each item names the mechanism that produces it. These are the fences a reader should hold us to.

- **No commercial-POI layer, so we cannot claim restaurant coverage.** The GIS package has 5 premises
  records and all of them are Poczta Polska post offices; it contains no retail, POI or business-register
  layer (R14). Consequence: we can say "N % of card volume", never "X % of restaurants in this area" —
  we do not know how many restaurants there are, only how many merchant descriptors took cards.
- **12 of 151 postcode sectors are extrapolated.** Postal boundaries are not published, so the sectors
  are a parcel-informed spatial model; 105 are `observed`, **12 are `extrapolated`** (no dual-source
  agreement, or 100 m support < 40 %) and the rest intermediate (R11). Consequence: a value shown for
  those 12 is a model output, and the panel flags the class rather than hiding it.
- **The GIS sectors are inferred, not official, and Sopot has no official district names.** The PRG
  cadastral districts are exposed as **numbers only** — `district_name` is `"1"`…`"52"` — and the package
  contains **no toponymy at all** (R11, R13). Consequence: every label of the form "Dolny Sopot /
  Karlikowo" in our UI is a non-official toponym supplied by us, and the map's own attribution says
  `Granice obszarów modelowane z adresów (nieoficjalne)`.
- **Weather is city-level, duplicated across 155 postcodes.** 0 of 13,102 hourly timestamps differ across
  postcodes (R12). Consequence: no per-area weather statement is derivable from this series; only the
  per-area *sensitivity* to city weather is, and the UI must be worded that way.
- **MCC 5812 only, and 7 of 72 columns.** The dataset contains exactly one merchant-category value
  across all 378,212 rows (R18), and the analysis consumes 7 of the 72 available columns. Consequence:
  every cross-category comparison is impossible, and our own film's five non-5812 category figures are
  unsupportable (R26).
- **10.2 % of rows (38,443) carry the sentinel time `'000000'` and are marked `valid`.** They cannot be
  placed on the hour axis and are excluded from hourly views while remaining in totals (R22).
  Consequence: every hourly figure and every baseline is computed on 89.8 % of the rows, and the panel
  states the count rather than silently absorbing it.
- **The cleaning pipeline has been rewritten, not recovered.** No script produced the original subset
  (R21). Consequence: `make data` is our reconstruction; if a juror compares its exclusion counters with
  the original artifacts and they differ, the reconstruction is wrong and this line is where to say so.
- **The privacy gate is k-anonymity, not differential privacy.** It bounds what a single released cell
  reveals; it does not bound what a sequence of queries reveals, and it does not protect against an
  attacker who already holds the raw feed. Consequence: G4 (the differencing test) exists in
  `contracts/privacy.py` but is not yet a release condition, and we say so rather than implying the
  ladder is complete.
