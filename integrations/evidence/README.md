# Evidence — what each file is, and how to regenerate it

**Owner:** municipal integrator.
Everything here is produced by a command in this repository. Nothing is a
transcript of a claim.

Regenerate all of it:

```sh
# 1. serve the demo (repository root, so both the site and /app/ resolve)
python3 -m http.server 8097 --bind 127.0.0.1

# 2. in another shell
cd /Users/kulma/Documents/Projects/Hackathon/sopocka-strona-biznesu
node integrations/tools/cdp.mjs integrations/tools/probe-nav.mjs          > integrations/evidence/nav-measurement.json
node integrations/tools/cdp.mjs integrations/tools/probe-nav-baseline.mjs  > integrations/evidence/nav-baseline-vs-integrated.txt
node integrations/tools/cdp.mjs integrations/tools/probe-demo-flow.mjs     # writes the screenshots + demo-flow.json
node integrations/tools/cdp.mjs integrations/tools/probe-isolation.mjs     > integrations/evidence/isolation-table.txt
bash integrations/tools/offline-audit.sh                                   > integrations/evidence/offline-audit.txt
```

> The screenshots are JPEG at quality 92, not PNG. They are photographs of a
> photo-heavy page; PNG cost 13 MB for the same set, JPEG costs 2.4 MB with no
> visible difference at these dimensions.

---

## The three demo steps

The mission's three steps, captured through a real Chrome over CDP at
`http://127.0.0.1:8097/integrations/municipal-site/`.

| file | step | what it shows |
|---|---|---|
| `01-homepage-1280x800.jpg` | **1. the municipal homepage** | the real portal: hero slider, seven familiar tabs plus the new eighth, footer |
| `01-homepage-1920x1080.jpg` | 1, wide | same, at 1920 |
| `02-tab-page-1280x800.jpg` | **2. click `Strona Biznesu`** | the tab page: real header with the tab highlighted `#178fd3`, breadcrumb hero over the city's own Skwer Kuracyjny photograph, the `Home › Sopocka Strona Biznesu` breadcrumb, the strap, and the top of the embedded panel |
| `02-tab-page-1920x1080.jpg` | 2, wide | same, at 1920 |
| `03-panel-1280x800.jpg` | **3. the panel** | viewport scrolled to the panel (`window.scrollY = 553`) |
| `03-panel-1920x1080.jpg` | 3, wide | same at 1920 (`scrollY = 527`) |
| `03-panel-frame-1280x800.jpg` | 3, isolated | the iframe's own rectangle in page coordinates — the panel alone, 1116 × 1100 |
| `03-panel-frame-1920x1080.jpg` | 3, isolated | the same at 1296 × 1100 |

Step 4 of the route — the way back — is recorded in `demo-flow.json` rather than
photographed: clicking the header logo returns to `pl/home/`, which is the
homepage (`isHomepage: true`) and still carries the new tab (`hasNewTab: true`).

### Content checks on the screenshots

Because "the file exists" is not evidence that it shows the right thing, the
pixels were checked for the colours each step must contain:

| file | expected | measured |
|---|---|---|
| `01-homepage-1280x800.jpg` | municipality orange + blue on white | `#fe5d0c` orange, `#1690d3` blue, white dominant; accent `#178fd3` in 2.09 % of pixels (the new tab) |
| `02-tab-page-1280x800.jpg` | the accent `#178fd3` of the highlighted tab, plus the black hero title box | accent in **2.09 %** of pixels; near-black **6.40 %** (the hero title box); panel cream **9.75 %** |
| `03-panel-1280x800.jpg` | the panel filling the viewport after the scroll | panel cream **61.66 %** of pixels |
| `03-panel-frame-1280x800.jpg` | the panel's own palette | panel cream `rgb(242,240,231)` in **51.37 %** of pixels |
| `03-panel-frame-1920x1080.jpg` | the same at 1296 px wide | panel cream **50.90 %** |

## The measurements

| file | what it proves |
|---|---|
| `nav-measurement.json` | the eighth item does **not** wrap and is **not** clipped at 1280×800, 1366×768, 1440×900, 1920×1080. Per-viewport: item count, wrap detection, the tab item's box, its distance past the nav's right edge, and every ancestor with a non-visible `overflow` that could clip it. |
| `nav-baseline-vs-integrated.txt` | the same nav in the **pristine replica at `:8099`** (7 items) against the integrated copy (8 items), at four widths, with the font size and margin in force at each. Shows the theme's own spacing is preserved (`14px` / `12px` in both at 1280). |
| `demo-flow.json` | the full three-step route at 1280 and 1920: the URL at each step, the nav state (item count, wrap, `menu-wybrane`, `rgb(23,143,211)`, the 20 px underline), the frame's `src`/height/`min-height`, the panel's own title and rendered text, the host page's untouched `--bd-theme-primary` and `Montserrat` body font, the console output, and **the complete request log** — `offOrigin: []` at both viewports. |
| `isolation-table.txt` | both documents read at once: the host's intact `--bd-theme-primary` / font / focus ring next to the panel's own font, background and 45 `:root` tokens, plus the frame's page-coordinate rectangle. |
| `offline-audit.txt` | the offline grep: zero off-origin *request* patterns, the one non-request `data-mock-embed-src` marker, and the informational counts of links, body-text URLs, JS string literals and `xmlns` values. |

## Isolation

`probe-isolation.mjs` prints (rather than writing a file) the table that shows
the iframe does the job the audit's §5 collision list demands:

```
host   --bd-theme-primary  #178fd3        (intact; the panel injects ~48 :root tokens LAST)
host   body font           Montserrat, sans-serif
host   focus ring          solid 3px      (the panel sets :focus{outline:none} site-wide)
panel  body font           Barlow, system-ui, sans-serif
panel  body background     rgb(242, 240, 231)
panel  :root tokens        45 declared, 0 reachable from the host document
```

and `04-panel-direct.jpg` is `/app/` visited directly at the frame's own width,
for comparison with `03-panel-frame-*.jpg`.

## What is *not* here

No evidence file is a hand-written summary. If a number appears in
`../NAV-DIFF.md`, `../COPY.md` or `../DEMO-PARTNERS.md`, its command is named in
that document. Numbers with no row here or there should be treated as unproven.
