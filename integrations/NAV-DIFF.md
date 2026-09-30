# NAV-DIFF — welding `Strona Biznesu` into karta.sopot.pl

**Owner:** municipal integrator · **Artifact:** `integrations/municipal-site/`
**Source (read-only, never modified):** `../karta-mockup/site/`
**Rebuild:** `bash integrations/tools/build-all.sh`

---

## 1. The navigation change, verbatim

One line, inserted immediately after the `menuItem_392` item inside
`header … .main-menu nav#mobile-menu > ul` — the only one of the three menu
copies that is editable (the offcanvas copies are cloned at runtime by
`meanmenu.js`; `NOTES.md` §2).

```html
<li class=" " id="menuItem_900"><a class="wyroznione2" href="pl/strona-biznesu">Strona Biznesu</a></li>
```

Applied to `integrations/municipal-site/index.html`, the result is:

```diff
                             <li  class=" " id="menuItem_392">
                                 <a
                                    href="pl/rejestracja">Załóż konto
                                 </a>


                                         </li>
+                            <li class=" " id="menuItem_900"><a class="wyroznione2" href="pl/strona-biznesu">Strona Biznesu</a></li>










                             </li>
                         </ul>
```

The stray `</li>` before `</ul>` is a real CMS artefact of the replica and is
left exactly where it was.

### 1.1 Two deliberate deviations from the audit's §1.5 snippet

Both are corrections, not preferences; the measurements that force them are in §3.

1. **The `href` is document-relative and depth-correct.** The audit's snippet
   shows `href="pl/strona-biznesu"`, which is right for `index.html` at the site
   root. But the replica's nav hrefs are *not* root-relative: on
   `pl/partnerzy/index.html` the same item reads `href="../../pl/rejestracja"`.
   `tools/build_site.py` rewrites them per depth when it generates a page. The
   patcher therefore emits:

   | page | emitted `href` |
   |---|---|
   | `index.html` | `pl/strona-biznesu` |
   | `pl/partnerzy/index.html` | `../../pl/strona-biznesu` |
   | `pl/partnerzy/dwie-zmiany-12257/index.html` | `../../../pl/strona-biznesu` |

   A literal copy of the audit's snippet onto all 166 pages would have produced
   166 dead links.

2. **One-line markup instead of the CMS's five-line form.** The audit's §1.5
   diff shows the multi-line CMS whitespace; the audit itself notes the two
   render identically. The one-line form is the brief's exact string.

### 1.2 The active-tab highlight

`class="menu-wybrane"` is set by hand on the tab's own page — the same class the
CMS puts on the current section. `apply-nav.py` owns this and keeps it in sync,
so it cannot drift:

- `pl/strona-biznesu/index.html` → `<li class="menu-wybrane" id="menuItem_900">`
- every other page → `<li class=" " id="menuItem_900">`

It renders as `#178fd3` text plus the CMS's own 20 × 2 px underline bar
(`cmsCSS/v-custom.css:2064-2086`). Measured on the live page, not assumed —
`integrations/evidence/demo-flow.json`:

```
"tabClass":  "menu-wybrane"
"tabColor":  "rgb(23, 143, 211)"     ← #178fd3
"underline": "rgb(23, 143, 211)"  width "20px"
```

**`build_site.py` was not re-run** (and must not be — `tools/build.sh` wipes
`site/`). The audit's Diff 3 registers `("pl/strona-biznesu", "menuItem_900")`
in `MENU_SECTIONS`; that is the equivalent change for a regeneration, and it is
recorded here so a future rebuild reproduces the highlight instead of losing it.

### 1.3 What `.wyroznione2` does

Nothing. `grep -rn wyroznione2` over the entire replica returns no match: the
class is inert. The CMS pairs `menu-wybrane` with `a.wyroznione` (a white-text
rule) for menu items that sit on a coloured background; our item is on white, so
it correctly carries neither. It is kept because the brief specifies it.

### 1.4 Coverage

```
$ python3 integrations/tools/apply-nav.py --check
checked 167 pages in …/integrations/municipal-site
  already present  166
  skipped (no header nav) 1
```

- **166 pages carry the item** — all 165 pages of the replica **plus** the new
  tab page. Every nav, footer and breadcrumb link in the demo resolves; nothing
  404s in front of a juror.
- The 1 skipped file is `pl/strona-biznesu/panel-w-przygotowaniu.html`, the
  frameless document rendered inside the iframe when the panel app is absent. It
  has no municipal chrome and therefore no nav to patch.

---

## 2. Applying this to the live CMS

The replica is static HTML; the live site is a CMS that emits it. The change is
the same idea in three places:

| # | Where | Change |
|---|---|---|
| 1 | **Menu module `module_865`** → the `nav#mobile-menu > ul` | Append one `<li>` with `id="menuItem_900"` and the label `Strona Biznesu`, positioned after `menuItem_392` (`Załóż konto`). The CMS writes the `href` itself; supply `pl/strona-biznesu`. |
| 2 | **`MENU_SECTIONS`** in the site generator | Register `("pl/strona-biznesu", "menuItem_900")` so the item receives `menu-wybrane` on its own page. Without this, set the class manually on that one page. |
| 3 | **The page** | Create the `pl/strona-biznesu` node with the content in §4, whose only dynamic element is the iframe. |

Do **not** touch the offcanvas menu modules: they are filled by `meanmenu.js`
from the header list.

---

## 3. Does the eighth item wrap? — measured, and the one CSS rule it needs

The audit predicted a wrap and suggested *"keep the label short"* plus a
margin tweak. Measurement confirms the wrap and shows the audit's suggested
margin value would not have fixed it.

`integrations/tools/probe-nav-fix.mjs`, `integrations/tools/probe-nav.mjs`,
`integrations/tools/probe-nav-baseline.mjs`; raw output in
`integrations/evidence/nav-measurement.json` and
`integrations/evidence/nav-baseline-vs-integrated.txt`.

### 3.1 Before the fix — it wraps at 1280, and at 1500–1559

| viewport | pristine replica (7 items) | integrated (8 items), no fix |
|---|---|---|
| 1280×800 | no wrap | **WRAPS** — `menuItem_900` drops to a second row |
| 1366×768 | no wrap | no wrap |
| 1440×900 | no wrap | no wrap |
| 1500×900 | no wrap | **WRAPS** |
| 1512×900 | — | **WRAPS** |
| 1550×900 | — | **WRAPS** |
| 1600×900 | no wrap | no wrap |
| 1920×1080 | no wrap | no wrap |

At 1280 the nav's content box is **805.33 px** and the eight items need
**817.44 px** — 12.11 px short. The 1500–1559 window matters more than it looks:
**1512 px is the default scaled width of a 14-inch MacBook Pro.**

### 3.2 The cause, and the fix

`css/site-inline.css:1118-1127` already tunes the live nav for seven items
(`white-space: nowrap`, a 12 px gap and 14 px type below 1500 px; the comment in
the source says *"zeby wszystkie punkty … miescily sie w jednej linii"*). Two
things eat the remaining budget:

1. `.main-menu { padding: 0 20px }` (`cmsCSS/v-custom.css:499`) spends 40 px on
   padding a centred nav does not use.
2. The items are `inline-block`, so the newlines between the `<li>` tags render
   as word spaces — seven of them, about 27 px, on top of the margins the theme
   already set.

One rule, in the replica-only augmentation file (never the mirrored theme CSS):

```css
@media (min-width: 1200px) {
    .main-menu { padding-left: 0; padding-right: 0; }
    .main-menu nav > ul { display: flex; flex-wrap: nowrap; justify-content: center; }
}
```

`display: flex` removes the phantom whitespace, so the theme's own margins
(12 px / 20 px) apply exactly as written — **the visible gaps stay identical to
the seven-item site**, and no type size changes.

### 3.3 After the fix — verified at both mandated viewports

```
$ node integrations/tools/cdp.mjs integrations/tools/probe-nav.mjs
1280x800   items=8 wraps=False tab.width=107.02 tab.right=1048.72 pastNavRight=0 pastViewport=-231.28 clipped=[]
1366x768   items=8 wraps=False tab.width=107.02 tab.right=1091.70 pastNavRight=0 pastViewport=-274.30 clipped=[]
1440x900   items=8 wraps=False tab.width=107.02 tab.right=1128.72 pastNavRight=0 pastViewport=-311.28 clipped=[]
1920x1080  items=8 wraps=False tab.width=122.30 tab.right=1447.64 pastNavRight=0 pastViewport=-472.36 clipped=[]
```

- **1280×800: one row.** Item 8 is 107.02 px wide, its right edge is 1048.72,
  `pastNavRight = 0` (flush with the nav's own right edge) and
  `pastViewport = -231.28` — 231 px of headroom.
- **1920×1080: one row.** 122.30 px wide, right edge 1447.64,
  `pastNavRight = 0`, 472 px of headroom.
- `clippedBy: []` at every width: no ancestor has a non-visible `overflow`, so
  nothing is clipped either. The probe walks the whole ancestor chain and
  reports every box that would cut the item off; it reports none.
- Between 1200 and 1920 the nav is one row at **every** width tested
  (1200, 1232, 1280, 1366, 1440, 1499, 1500, 1512, 1550, 1600, 1920).

Below 1200 px the theme's own layout holds and the nav wraps — **the pristine
replica wraps there too** with only seven items (at 992 px, 613.33 px of space
against 698.40 px of items), so this is the site's existing behaviour, not a
regression introduced here. Below 992 px the nav column is `d-none` and
`meanmenu.js` takes over.

**No route in the demo needs a viewport below 1280.**

---

## 4. The tab page, and why the panel is an iframe

`integrations/municipal-site/pl/strona-biznesu/index.html` is a real page of the
replica: it is the replica's own section-page shell
(`pl/jak-zostac-partnerem/index.html`, chosen because it already sits at the same
document depth, so every mirrored `../../assets/…` href is correct) with exactly
three edits — `<title>`, `<meta name="description">`, and the contents of
`<main>`. Header, nav (with the new item), offcanvas, footer, theme CSS/JS load
order and the accessibility widget are inherited byte-for-byte.

`<main>` contains: the breadcrumb hero (`.breadcrumb__section` over the city's
own Skwer Kuracyjny photograph, `data-background` wired by `cmsJS/main.js:76`),
the real `#position` breadcrumb `Home › Sopocka Strona Biznesu`, the one-line
"what this is" strap, **one borderless full-width `<iframe>`**, the privacy
disclosure, the business-facing call to action and the partner list.

### Why an iframe — and the evidence it works

The embedding audit (§5) rejected a direct embed because the panel's stylesheet
is not isolated in any way: it styles `body`, bare `h1–h6/p/a/img/figure`, sets
`:focus { outline: none }` site-wide, injects ~48 generic `:root` tokens **last**,
and captures `Escape` at the document level. A direct embed visibly breaks the
host page.

`integrations/tools/probe-isolation.mjs` reads both documents at once and shows
none of it crosses the boundary:

| the audit's collision | host page, panel embedded | would be, on a direct embed |
|---|---|---|
| `:root` tokens clobbered | `--bd-theme-primary: #178fd3` — intact | panel's accent wins (injected last) |
| `body` repainted | `Montserrat` on `rgb(255,255,255)` | `Barlow` on `rgb(242,240,231)` |
| `:focus{outline:none}` | focus ring `solid 3px` | no ring (WCAG 2.4.7 failure) |
| `box-sizing` | host elements `border-box` | panel's rule applies |
| tokens leaking | **0** of the panel's 45 `:root` tokens resolve in the host | — |

The panel itself runs `Barlow` on `rgb(242,240,231)` inside the frame, and a
direct visit to `/app/` renders the same title, background and font — so the
boundary is invisible in both directions.

### The frame's geometry

- `width: 100%`, `border: 0`, `display: block`, `background: #fff`,
  `min-height: 820px`.
- **Height is measured from the panel, not fixed.** The panel is ~3000 px tall;
  a fixed-height frame would give the juror a second, nested scrollbar and the
  page would read as a foreign widget. `assets/mock/strona-biznesu.js` sizes the
  frame to the panel's `scrollHeight` (bounded to 820–6000 px) on load and
  re-measures for 12 s while the aggregate loads. Measured: 2978 px at 1280,
  2639 px at 1920 — exactly the panel's own content height.
- **Panel availability is probed at `/app/index.html`, never `/app/`.** A
  directory request answered by `python -m http.server` returns a 200 *directory
  listing*, which would have been embedded as if it were the panel.
- If the panel is absent the frame loads
  `pl/strona-biznesu/panel-w-przygotowaniu.html`, which says in Polish what the
  page is waiting for. **There is no fake panel and no sample data anywhere in
  this integration.**

---

## 5. The reduction, and why the copy is 48.7 MB and not 111.4 MB

`tools/build.sh` wipes `site/`; this copy is independent and is rebuilt from the
read-only source by `bundle-replica.py`. **No page of the replica was dropped** —
all 165 pages are present, so the nav diff above is a genuine whole-site diff and
no link in the demo dead-ends. The saving comes from assets:

| step | effect | bytes |
|---|---|---|
| source tree | | 111.4 MB |
| `snapshots/` dropped | 22 MB of build-time verification captures, referenced by no page (`grep -rl snapshots/ --include=*.html` → 0) | −22 MB |
| `assets/visit/fonts/*.ttf` dropped | every `@font-face` offers `woff2` first; Chrome never requests the `.ttf` fallbacks | −3.7 MB |
| images re-encoded | CMYK JPEGs converted to sRGB with the embedded ICC profile dropped (the replica carries print-ready uploads whose ~590 KB FOGRA39 profile dwarfs 81 KB of actual image data); >640 px JPEG downsampled and re-encoded progressive; PNG kept as PNG at ≤420 px because references are never rewritten | −36.1 MB |
| homepage hero art kept | 5 images the homepage paints full-bleed stay at up to 1920 px | +0.8 MB |
| navigation + hardening + new page | | ±0.3 MB |
| **bundle** | **48.7 MB in 1093 files** | |

Verified visually inert where it matters: at 1280 and 1920 the hero, the nav and
the partner grid render from the same assets as the pristine replica at
`:8099`. Re-run `python3 integrations/tools/bundle-replica.py --force` to
reproduce the exact tree.

---

## 6. Offline

`bash integrations/tools/offline-audit.sh` → `integrations/evidence/offline-audit.txt`.

```
== off-origin REQUESTS (must be 0) ==
  (^|[^-a-zA-Z0-9_])src="https?://    0
  (^|[^-a-zA-Z0-9_])src='https?://    0
  url\((https?:)?//                   0
  @import[^;]*https?://               0
  data-background="https?://          0
  TOTAL REQUESTS: 0
PASS: no request in integrations/municipal-site can leave 127.0.0.1
```

The replica arrived with 154 off-origin `<img src>` values in 127 pages, in four
hosts — `maps.gstatic.com` (118, the red "you are here" map pin),
`kalendarz.sopot.pl` (35, event photographs), `sopot.bifrost.lepsze.it` (1, the
CMS's own upload host, absent from the mirror) and one YouTube embed. The first
three are repointed at two local placeholders in the replica's own palette
(`assets/mock/offline/pin-red.svg`, `photo-placeholder.svg`) by
`integrations/tools/offline-hardening.py`. The YouTube embed had **already** been
replaced by the replica's own `google-stubs.js` with a local `.embed-placeholder`
notice; the surviving `data-mock-embed-src="https://…"` is a `data-` attribute on
that local div and fetches nothing.

What remains and why it is not a request:

| category | count | comment |
|---|---|---|
| `href="http(s)://…"` | 817 | links, not fetches. 165 of them are the footer's `qb.com.pl` credit on every page; the rest are the site's authentic outbound links (Facebook, Instagram, Google Maps directions, partner websites). |
| bare URLs in body text | 80 | e.g. `https://ecosopot.pl/…` printed as link text |
| URLs in JS string literals | 52 | pdfmake font config and a YouTube URL builder pasted into article bodies by the CMS; inert unless that widget is used |
| `xmlns` / schema | 8 | XML namespace identifiers, never fetched |
| OpenStreetMap tiles | 1 page | `pl/punkty-obslugi/index.html` — the mandated exception. **The demo does not route through this page.** |

Confirmed in the browser, not only by grep: over the whole three-step route
(homepage → tab → panel → back) at 1280 and 1920, `offOrigin()` is `[]` — every
network request went to `127.0.0.1:8097`. See
`integrations/evidence/demo-flow.json`.

---

## 7. Reproducing all of it

```sh
bash integrations/tools/build-all.sh          # bundle → harden → page → links → nav
python3 integrations/tools/bundle-replica.py --force
python3 integrations/tools/offline-hardening.py
python3 integrations/tools/build-tab-page.py
python3 integrations/tools/apply-augmentation.py
python3 integrations/tools/apply-nav.py

# verify (each must be a no-op)
python3 integrations/tools/apply-augmentation.py --check
python3 integrations/tools/apply-nav.py --check
python3 integrations/tools/offline-hardening.py --check

# measure
node integrations/tools/cdp.mjs integrations/tools/probe-nav.mjs
node integrations/tools/cdp.mjs integrations/tools/probe-demo-flow.mjs
node integrations/tools/cdp.mjs integrations/tools/probe-isolation.mjs
bash integrations/tools/offline-audit.sh

# serve the demo (repository root, so that both /app/ and the site resolve)
python3 -m http.server 8097 --bind 127.0.0.1
# → http://127.0.0.1:8097/integrations/municipal-site/
```

Order matters: `build-tab-page.py` regenerates the tab page from its donor, so
the augmentation and navigation passes must run after it.
