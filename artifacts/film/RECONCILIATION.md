# Film reconciliation — Rytm Miasta → Sopocka Strona Biznesu

**Owner:** film reconciler · Written 2026-09-30 · Executed option **1** (90-second re-cut, false strings corrected in place).
Source of truth for the four claims: `research/presentation-assets.md` §3.
Source film treated as strictly read-only; every write went to `artifacts/film/` and `/tmp/recon/`.

---

## 1. What was false, and what changed

| # | Claim on screen | Where | Verified status | Action in the delivered cut |
|---|---|---|---|---|
| 1 | „**475 000** transakcji" | `compositions/b04.html` `#b04-num` | **FALSE** — parquet holds **378 212** rows (−25.6 %) | Replaced in place by an opaque plate reading **378 212 transakcji** |
| 2 | Six category chips: „Bary +29 %", „Fast food +22 %", „Apteki −47 %", „Parkingi −57 %", „Piekarnie −81 %" | `b04.html` `#b04-chip1…5` | **UNSUPPORTABLE** — `mrch_catg_cd` has exactly one distinct value, **5812**. MCC 5813/5814/5912/7523/5462 are absent from the dataset | **Not on screen in this cut** (chips enter at master 97.5 s; the b04 segment ends at 97.0 s). The plate states the single-MCC constraint explicitly |
| 3 | Error bars **66 % / 17 %** | `b05.html` `#b05-bar66/#b05-bar17`; `b07.html` `#b07-window-bars` | **MISATTRIBUTED + MISCALIBRATED** — `sources/resource-audit.md:70` records the source pair as the **cosmetics** category; measured walk-forward MAPE is **24.1 %** (best of four candidates), not 17 % (`research/presentation-assets.md` §3.5b) | b05's bars (master 169 s) are outside the cut. b07's ghost pair (master 212.0–213.6 s) is covered by a plate reading **MAPE 24,1 %** with the misattribution stated. The b05 segment carries the same measured figure in a second plate |
| 4 | „**PT 9 LIP**" / „Piątek, 9 lipca" | `index.html` `#locked-day` + `#date-chip`; `b05.html` `#b05-forecast`; `b07.html` `#b07-sentence` | **FALSE** — 2026-07-09 is a **Thursday** (verified: `python3 -c "import datetime;print(datetime.date(2026,7,9).strftime('%A'))"` → `Thursday`). STORYBOARD.md notes it too | All four on-screen occurrences inside the cut re-lettered to **CZ / czwartek, 9 lipca** |

**Standing caveat plate.** A plate in the b04 segment carries the film's own disclaimer, replacing the honesty that previously lived only in the repo:

> Zastrzeżenia: Część zdjęć — prawa niepotwierdzone. Źródłowe 66 %/17 % dotyczy kosmetyków.
> Prognoza +38 % to wartość ilustracyjna, nie końcowy wynik modelu.
> Żadna liczba nie została zawyżona; wszystkie są zmierzone albo oznaczone.

All seven correction surfaces (the caveat plate is part of C1) were verified by comparing the covered rectangle in the output against the same rectangle in the original: every one differs materially.

| Patch | New-timeline window | Source window | mean&#124;out−src&#124; in the covered rect |
|---|---|---|---|
| C1 b04 count + standing caveat | 27.0 – 38.0 s | 86.0 – 97.0 s | 39.8 |
| C2 b05 `#locked-day` | 42.6 – 56.0 s | 124.6 – 140.0 s | 19.0 |
| C3 b05 forecast date line | 49.75 – 56.0 s | 133.75 – 140.0 s | 21.4 |
| C4 b05 measured-MAPE band | 49.75 – 56.0 s | 133.75 – 140.0 s | 210.6 |
| C5 b07 `#date-chip` | 64.0 – 71.0 s | 211.0 – 218.0 s | 29.8 |
| C6 b07 ghost bars | 64.9 – 66.8 s | 211.9 – 213.8 s | 140.8 |
| C7 b07 sentence-card date | 66.9 – 71.0 s | 214.9 – 218.0 s | 15.7 |

---

## 2. Measured block boundaries

`STORYBOARD.md` and `index.html` agree on the mount grid: **b01 0 · b02 30 · b03 52 · b04 80 · b05 122 · b06 182 · b07 211 · b08 237 · b09 259**.

I tried to confirm those boundaries independently:

```
ffmpeg -i rytm-miasta-1080p.mp4 -vf "select='gt(scene,0.25)',metadata=print:file=scenes.txt" -an -f null -
```

**Result: only two hard cuts exist in the entire 300 s film** — `pts_time:52` (`scene_score=1.000000`, b03) and `pts_time:211` (`scene_score=0.544876`, b07). Every other block join is a **dissolve**, so scene-change detection cannot confirm those boundaries. The two cuts it did find land **exactly** on the storyboard's 52 and 211, which is the only independent confirmation available; the remaining boundaries are taken from the storyboard and the composition mount times.

I then measured the *intra-block* geometry of every element I patch, **against the original mp4 pixels, not against the HTML**, by cropping the frame and profiling dark/bright row runs and colour clusters. Every measurement matched the CSS box, with one exception: the `#locked-day` chip in `index.html` renders **offset by (+96, +56) px** from its CSS box (`left:748;top:12`) because of its reveal animation. I used the measured box (x 844–1063, y 68–177).

### The nine segments actually used

| # | Block | Source in–out (s) | Frames | New timeline |
|---|---|---|---|---|
| 1 | b01 Miasto oddycha | 0 – 10 | 300 | 0.000 – 10.000 |
| 2 | b02 Krwiobieg | 30 – 38 | 240 | 10.000 – 18.000 |
| 3 | b03 Dostęp | 52 – 60 | 240 | 18.000 – 26.000 |
| 4 | b04 Ulica | 85 – 97 | 360 | 26.000 – 38.000 |
| 5 | b05 Kalendarz | 122 – 140 | 540 | 38.000 – 56.000 |
| 6 | b06 Rozrusznik | 182 – 190 | 240 | 56.000 – 64.000 |
| 7 | b07 Dzień koncertu | 211 – 218 | 210 | 64.000 – 71.000 |
| 8 | b08 Organizm | 245 – 251 | 180 | 71.000 – 77.000 |
| 9 | b09 Zamknięcie | 287 – 300 | 390 | 77.000 – 90.000 |

**Total: 2 700 frames = 90.000 s exactly.** Every in/out is an integer second, i.e. an exact multiple of 1/30 s, so no frame is half-selected.

### Where this deviates from `research/presentation-assets.md` §2.4, and why

- **b04 at 85–97 (block-local 5–17), not 80–92.** Master 80.0 lands inside the block's own fade-in (`#b04-world` starts `hidden`). Master 85 is settled. Ending at 97.0 rather than 98.0 keeps the six category chips — which enter at block-local 17.5 s (master 97.5) — off screen entirely. Claim 2 is therefore resolved by omission *and* stated on the plate.
- **b08 at 245–251, not the block head 237–243.** The three privacy labels (`min. 30 kart`, `min. 3 podmioty`, `żaden > 75 % grupy`) only become visible from block-local 8.5 s (master 245.5). The head of b08 shows **no labels at all** — the audit's 6 s allocation would have kept none of them. Block-local 8–14 (master 245–251) holds labels 1 and 2 in full; label 3 starts at 253.9, outside the 6 s budget.
- **b09 at 287–300 (the block's last 13 s), not its head.** `#b09-end-card` only enters at block-local 31.05 s (master 290.05). The block head contains no product name and no tagline, so a head-cut would have removed the film's identity.
- **b05 at 122–140** kept exactly as proposed.
- **b02 kept.** The audit calls it the most droppable, but the arc survives at 8 s and removing it would have cost the "value drains away" setup for no gain in the cut's length.

### Cut-point screening — I could not look at the frames

The model executing this work has **no image-input capability**, so I could not eyeball the join frames or the overlays. Every cut point was screened **numerically** instead (mean luminance and standard deviation of the grey frame at each in/out, on a 192×108 px downscale):

| t (s) | 0 | 10 | 30 | 38 | 52 | 60 | 85 | 97 | 122 | 140 | 182 | 190 | 211 | 218 | 245 | 251 | 287 | 300 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean | 94.9 | 95.5 | 19.9 | 15.6 | 170.0 | 169.2 | 96.2 | 97.3 | 99.4 | 197.5 | 143.6 | 78.4 | 120.0 | 144.5 | — | — | 51.8 | — |
| sd | 17.9 | 18.5 | 15.1 | 13.5 | 70.3 | 71.5 | 53.0 | 53.6 | 55.0 | 73.9 | 77.6 | 35.0 | 60.6 | 70.9 | — | — | 22.4 | — |

No join frame is near-black (min mean 15.6, a deliberate night plate) or blown out (max mean 197.5, the light forecast card). Seven of the nine block boundaries are mid-dissolve **by design** — the film has no hard cut there — so those join frames are blended rather than clean. That is a property of the source, not of the cut.

---

## 3. The exact commands

### 3.1 The final encode

```sh
/Users/kulma/.local/bin/ffmpeg -hide_banner -stats -y \
  -i /Users/kulma/Documents/ChatGPT/Hackathon/rytm-miasta/final/rytm-miasta-1080p.mp4 \
  -filter_complex_script /tmp/recon/filter.txt \
  -map "[out]" -an -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p \
  -profile:v high -level 4.0 -r 30 -movflags +faststart \
  artifacts/film/sopocka-strona-biznesu-90s.mp4
```

One decode, one encode. The filter script is generated by `/tmp/recon/build.py` and has this shape:

```
[0:v]select='gte(t,0)*lt(t,10)+gte(t,30)*lt(t,38)+gte(t,52)*lt(t,60)+gte(t,85)*lt(t,97)
            +gte(t,122)*lt(t,140)+gte(t,182)*lt(t,190)+gte(t,211)*lt(t,218)
            +gte(t,245)*lt(t,251)+gte(t,287)*lt(t,300)',setpts=N/30/TB[s0];
[s0]drawbox=…,drawtext=…,…[out]
```

`select` + `setpts=N/30/TB` is used rather than nine `trim` branches because `trim` decodes the source nine times; `select` decodes it once and the ascending time bounds guarantee frame order. `drawtext` uses `expansion=none` so the `%` signs in „MAPE 24,1 %" and „+38 %" stay literal.

### 3.2 Verification

```sh
ffprobe -v error -show_entries format=duration,size,bit_rate \
        -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate,nb_frames \
        -of default=noprint_wrappers=0 artifacts/film/sopocka-strona-biznesu-90s.mp4
ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 artifacts/film/sopocka-strona-biznesu-90s.mp4   # -> empty
ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 artifacts/film/sopocka-strona-biznesu-90s.mp4
shasum -a 256 artifacts/film/sopocka-strona-biznesu-90s.mp4
```

### 3.3 Frames extracted as evidence (in `artifacts/film/frames/`)

```sh
ffmpeg -y -ss 30.0 -i sopocka-strona-biznesu-90s.mp4 -frames:v 1 frames/C1_t30.0.png   # 378 212 + caveat plate
ffmpeg -y -ss 52.0 -i sopocka-strona-biznesu-90s.mp4 -frames:v 1 frames/C4_t52.0.png   # MAPE 24,1 % plate + corrected date
ffmpeg -y -ss 69.0 -i sopocka-strona-biznesu-90s.mp4 -frames:v 1 frames/C7_t69.0.png   # czwartek, 9 lipca in the sentence card
```

`POSTER.jpg` is frame 86.0 s of the delivered file — the b09 end card, carrying the product name, the tagline and the credits.

---

## 4. Fonts, and how glyph coverage was verified

Three fonts, all taken read-only from the source project:

| Role | File |
|---|---|
| Figures, labels, chips | `rytm-miasta/assets/fonts/jetbrains-mono-0.ttf` |
| Body copy | `rytm-miasta/assets/fonts/inter-0.ttf` |
| (available, unused) | `inter-tight-0.ttf` |

`fc-list` on this machine has **no** Inter, Inter Tight, JetBrains Mono or Montserrat installed, so every `drawtext` passes an explicit `fontfile=`; the film never depends on system font resolution. (ffmpeg prints `Fontconfig error: Cannot load default config file` — harmless, and it is exactly why the explicit `fontfile` is there.)

I cannot see images, so coverage was proven quantitatively, through the **same ffmpeg/libfreetype path the encoder used**:

**(a) Per-glyph matrix.** Each of `ą ć ę ł ń ó ś ź ż Ą Ć Ę Ł Ń Ó Ś Ź Ż` was rendered alone at 80 px and its ink-pixel count and bounding box recorded. A missing codepoint renders `.notdef`, which in these fonts is a solid box (`Inter`: 1 789 ink px; `Inter Tight`: 936; `JetBrains Mono`: 865 — all with a small, distinctive bbox).

```
Inter           distinct=18/18  tofu-or-blank=NONE
Inter Tight     distinct=18/18  tofu-or-blank=NONE
JetBrains Mono  distinct=18/18  tofu-or-blank=NONE
```

All 18 renderings are pairwise distinct and none matches the `.notdef` signature.

**(b) Control on the delivered string.** The heading actually used in the film, `Zastrzeżenia:`, was rendered three ways through the identical chain:

| String | ink px | bbox x |
|---|---|---|
| `Zastrzeżenia:` (as delivered) | **4 669** | 24–381 |
| diacritics replaced by spaces | 4 242 | 24–365 |
| `Zastrzezenia:` (no diacritics) | 4 629 | 24–381 |

The diacritics add ink and width over the space-replaced control instead of collapsing to a wide `.notdef` box (which would have added roughly 3 × the 865–1 789 px tofu signature above and blown the bbox out) — **ę, ń and ż rendered as real glyphs, not fallback boxes.**

The same control was run for **every Polish word that appears in the delivered overlays** — the diacritic mark adds ink in every single case, which is what a real glyph does and what a `.notdef` box does not:

| word (as delivered) | ink px | same word, diacritics stripped | ink px | Δ |
|---|---|---|---|---|
| Zastrzeżenia: | 5 169 | Zastrzezenia: | 5 120 | +49 |
| Błąd | 2 050 | Blad | 1 922 | +128 |
| Źródłowe | 3 539 | Zrodlowe | 3 403 | +136 |
| część | 2 143 | czesc | 1 960 | +183 |
| zdjęć | 2 165 | zdjec | 2 025 | +140 |
| kategorię | 3 703 | kategorie | 3 609 | +94 |
| kosmetyków | 4 562 | kosmetykow | 4 516 | +46 |
| Żadna | 2 394 | Zadna | 2 354 | +40 |
| została | 2 692 | zostala | 2 646 | +46 |
| końcowy | 3 123 | koncowy | 3 079 | +44 |
| są | 937 | sa | 855 | +82 |

**(c) Coverage of the delivered overlays.** The text placed on screen uses **all nine lower-case Polish diacritics**: `ą` (są), `ć` (część, zdjęć, wartość), `ę` (część, zdjęć, kategorię), `ł` (została), `ń` (końcowy), `ó` (Źródłowe, kosmetyków, końcowy), `ś` (część), `ź` (Źródłowe), `ż` (Zastrzeżenia, Żadna, zawyżona).

---

## 5. The output, ffprobe

```
[STREAM]
index=0
codec_name=h264
profile=High
codec_type=video
width=1920
height=1080
pix_fmt=yuv420p
r_frame_rate=30/1
avg_frame_rate=30/1
nb_frames=2700
[/STREAM]
[FORMAT]
format_name=mov,mp4,m4a,3gp,3g2,mj2
duration=90.000000
size=36221114
bit_rate=3219654
[/FORMAT]
```

- **Duration 90.000 s**, 2 700 decoded frames, 1920×1080, 30 fps, H.264 High, `+faststart`, **zero audio streams** (verified by `-select_streams a`, which returns an empty list).
- **36 221 114 bytes (36.2 MB)** — under the 120 MB target by 3.3×, and 21.5× smaller than the 780 556 064-byte source.
- **SHA-256 `1b1839495338576b00e67b156e56a3926ecc4f7f5ccde6df42c1e8537d623ce9`**

---

## 6. The honest residual — still on screen, still not supportable

These are **not** fixed. They are named here so nobody discovers them from a juror.

1. **„+38 %"** (`#b05-pct`, and „Spodziewaj się ok. +38 % gości." in b07). Self-declared placeholder; no model in this project produces it and `resource-audit.md:47–53` says no evidenced replacement exists. **Not corrected** — there is no better number to put in its place. It is disclosed in the standing caveat plate as *wartość ilustracyjna*.
2. **The forecast interval 0,29–0,47** (`#b05-interval-band`). Same status: placeholder, uncorrected, disclosed.
3. **The calendar grid is systematically one day ahead of the real 2026 week.** `#calendar-cells` labels 18 June 2026 as `PT`, but 18 June 2026 is a Thursday (as are 11, 18 and 25 June and 2 July); the film's Fridays are 11/18/25 CZE + 2 LIP, the real ones are 12/19/26 CZE + 3/10 LIP. **Only the four 9-July statements were corrected**; the scrolling grid itself is not fixable with static overlays and remains wrong. A juror who checks any other cell will still find the shift.
4. **„Koncert · Opera Leśna"** (`#event-label`, `#b05-forecast`). Generic placeholder. Real Sopot event titles and dates exist unused in `event_titles_json` (e.g. 22 titles on 2026-06-13). Not joined.
5. **Photo rights unconfirmed.** The end card credits seven photographers by name; no rights document exists anywhere in the archive (`resource-audit.md:35`). **This is the highest legal risk on the submission** and it is on screen in the delivered cut. Disclosed in the caveat plate; not resolvable by me.
6. **The b06 causal claim.** The cut keeps b06 (182–190 s). Its claim — that city events move restaurant payments — is confounded with season: 59.8 pp raw, **9.0 pp after month × weekday control** (t = +1.9 for events; rain is the robust driver at t = −8.8).
7. **The event date sits outside the data.** The data ends 2026-06-30; the film's event is 9 July. Even corrected, it is not a date the dataset covers.
8. **The heroine stills are soft.** `assets/gen/stills/g01…g09` are 1672×941 upscaled into 1920×1080, so b03, b04 and b07 — the emotional spine — are the softest material on a large screen.
9. **Cut-point quality is unverified by eye.** I have no image input. Every join was screened numerically (luminance mean/sd, §2) but **nobody has looked at the delivered film.** Before it is played to a jury, a human must watch it once end to end.
10. **The b04 chip „Restauracje +42 %"** is supportable (measured +41.6 % like-for-like) but is not in this cut, so the film no longer shows any category movement at all. That is a loss of story, accepted deliberately in exchange for showing no unsupportable category.
