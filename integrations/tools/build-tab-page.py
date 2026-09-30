#!/usr/bin/env python3
"""Build the `Strona Biznesu` tab page from a real page of the replica.

This is NOT a hand-edited blob.  It takes the replica's own section-page shell
(`pl/jak-zostac-partnerem/index.html` — same document depth, so every mirrored
`../../assets/…` href is already correct) and replaces exactly three things:

    <title> + <meta name="description">
    the two new <link>/<script> tags for the replica-only augmentation
    everything between <main> and </main>

Header, nav (including the new `menuItem_900` item), offcanvas, footer, theme
CSS/JS load order and the accessibility widget are all inherited byte-for-byte.

The panel is embedded in ONE borderless iframe.  See integrations/NAV-DIFF.md
§"Why an iframe" for the collision list that makes a direct embed impossible.

Usage:
    python3 integrations/tools/build-tab-page.py
    python3 integrations/tools/build-tab-page.py --check
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SITE = os.path.abspath(os.path.join(REPO, "integrations", "municipal-site"))

DONOR = os.path.join("pl", "jak-zostac-partnerem", "index.html")
OUTDIR = os.path.join("pl", "strona-biznesu")
PAGE = os.path.join(OUTDIR, "index.html")
PLACEHOLDER = os.path.join(OUTDIR, "panel-w-przygotowaniu.html")
CSS = os.path.join("assets", "mock", "strona-biznesu.css")
JS = os.path.join("assets", "mock", "strona-biznesu.js")

# /app/ is the panel, owned by the panel agent.  It is addressed absolutely
# because the demo is served from the repository root, so the tab page works
# from any mount prefix the municipal site happens to sit under.
PANEL_URL = "/app/"
# Probe the entry FILE, never the directory: python's http.server answers a
# directory request with a 200 directory listing, which would embed a file index
# as if it were the panel.
PANEL_PROBE = "/app/index.html"

TITLE = "Sopocka Strona Biznesu — Karta Sopocka"
DESCRIPTION = ("Sopocka Strona Biznesu — panel przedsiębiorcy Karty Sopockiej. "
               "Płatności kartą w Twojej okolicy: wydarzenia, pogoda i pory dnia.")

# The four food-service partners of the Sopot Card business directory that sit in
# the two demo postcode areas.  Source: research/sopot-partners.csv (see
# integrations/DEMO-PARTNERS.md for the extraction command).
PARTNERS = [
    ("Restauracja Falo Sopot", "ul. Na Wydmach 10", "81-777",
     "restauracja-falo-sopot-12816437"),
    ("Restauracja Pomarańczowa Plaża", "Emilii Plater 19", "81-777",
     "restauracja-pomaranczowa-plaza-10565615"),
    ("Dwie Zmiany", "Bohaterów Monte Cassino 31", "81-759", "dwie-zmiany-12257"),
    ("Tuż za Rogiem", "ul. Grunwaldzka 4/6", "81-759", "tuz-za-rogiem-268320"),
]

# Full-bleed hero photograph.  The city's own asset, already mirrored into the
# replica and served from 127.0.0.1: the Skwer Kuracyjny photograph by Marcin
# Czechowicz that the homepage uses.
HERO_IMAGE = ("../../res/688/13302283/"
              "Sopot_skwer_kuracyjny_poziom_Fot._Marcin_Czechowicz__9b81b38e.jpg")


def partner_rows():
    """The demo partners, grouped by postcode area.

    `contracts/PRIVACY-COPY.md` §4 makes the area label mandatory on every
    Plane B number, in the same visual block as the number, and requires the
    real code in it — so the label is emitted once per area, not once per venue.
    """
    by_area = {}
    for name, street, code, slug in PARTNERS:
        by_area.setdefault(code, []).append((name, street, slug))

    out = []
    for code in sorted(by_area):
        venues = "\n".join(
            f'                        <li class="sb-partner">\n'
            f'                            <a href="../partnerzy/{slug}">{name}</a>\n'
            f'                            <span class="sb-partner__meta">{street}</span>\n'
            f'                        </li>'
            for name, street, slug in by_area[code]
        )
        out.append(
            f'                    <div class="sb-area">\n'
            f'                        <h5 class="sb-area__title">Obszar '
            f'<span class="sb-partner__code">{code}</span></h5>\n'
            f'                        <ul class="sb-partners">\n{venues}\n'
            f'                        </ul>\n'
            f'                        <p class="sb-note sb-note--label">'
            f'Dane dla obszaru <strong>{code}</strong>, nie dla Twojego lokalu.</p>\n'
            f'                    </div>'
        )
    return "\n".join(out)


MAIN = f'''<main>
    <!-- breadcrumb area start -->
    <div class="breadcrumb__section include-bg mt-10"
         style="height: 340px !important; padding-top: 130px;"
         data-background="{HERO_IMAGE}">
        <div class="container">
            <div class="breadcrumb__content">
                <p class="sb-kicker">Panel przedsiębiorcy</p>
                <h3 class="breadcrumb__title">Sopocka Strona Biznesu</h3>
                <p class="sb-lead">Jak wydarzenia, pogoda i pora dnia wpływają na
                    płatności kartą w Twojej branży i Twojej okolicy.</p>
            </div>
        </div>
    </div>
    <!-- breadcrumb area end -->

    <div id="position">
        <div class="container">
            <ul>
                <li><a href="../../pl/home">Home</a></li>
                <li>Sopocka Strona Biznesu</li>
            </ul>
        </div>
    </div>
    <!-- End Position -->

    <div class="container mt-30">
        <div class="row">
            <div class="col-12">
                <p class="sb-strap">Strona Biznesu jest częścią programu Karty
                    Sopockiej: pokazujemy sopockim przedsiębiorcom, jak kształtują
                    się płatności kartą w ich okolicy.</p>
            </div>
        </div>
    </div>

    <!-- ===== PANEL PRZEDSIĘBIORCY (osadzony) ==============================
         Panel działa we własnym dokumencie (iframe), dzięki czemu jego arkusze
         stylów nie zmieniają wyglądu serwisu Karty Sopockiej. Osadzenie jest
         jednym elemencie — panel nie wymaga żadnych zmian po swojej stronie.
         ==================================================================== -->
    <div class="postbox__area mt-30">
        <div class="container">
            <div class="sb-panel" id="sb-panel">
                <p class="sb-panel__status" id="sb-panel-status">
                    Wczytywanie panelu przedsiębiorcy…
                </p>
                <iframe id="sb-panel-frame"
                        title="Panel przedsiębiorcy — dane o płatnościach kartą"
                        loading="eager"></iframe>
            </div>

            <!-- Copy is pasted verbatim from contracts/PRIVACY-COPY.md:
                 §4 "Plane B disclosure" and the standing explanation in §2.
                 Do not paraphrase it. -->
            <p class="sb-note sb-note--privacy">
                <strong>Porównanie branżowe.</strong> Te liczby to agregat wszystkich
                restauracji w wybranym obszarze i okresie, liczony z panelu transakcji
                kartą. Publikujemy je tylko wtedy, gdy grupa obejmuje co najmniej
                30 unikalnych kart i co najmniej 3 podmioty, a udział żadnego podmiotu
                nie przekracza 75%. Stosujemy dodatkowo test różnicowy: grupa musi
                spełniać progi także po odjęciu dowolnego jednego podmiotu. Twoja
                własna sprzedaż nie jest odejmowana ani dodawana do tej liczby.
                Nie pokazujemy nigdy pojedynczego podmiotu ani pojedynczej karty.
            </p>
        </div>
    </div>

    <div class="container mt-30">
        <div class="row">
            <div class="col-lg-8">
                <h4 class="sb-h">Skąd biorą się nazwy lokali w panelu</h4>
                <p class="sb-p">
                    Lista lokali pochodzi z Bazy Przedsiębiorców Karty Sopockiej —
                    tej samej, którą znajdziesz w zakładce
                    <a href="../../pl/partnerzy">Partnerzy</a>. Poniżej cztery lokale
                    gastronomiczne z dwóch obszarów demonstracyjnych. Dane w panelu
                    opisują obszar, w którym działa lokal, a nie sam lokal.
                </p>
{partner_rows()}
            </div>
            <div class="col-lg-4">
                <div class="sb-cta">
                    <h4 class="sb-h">Chcesz zostać Partnerem Karty Sopockiej?</h4>
                    <p class="sb-p">
                        Partnerstwo obejmuje prezentację firmy w Bazie Przedsiębiorców,
                        udział w Konkursie punktowym oraz dostęp do systemu statystyk
                        sprzedażowych.
                    </p>
                    <p class="sb-cta__links">
                        <a class="sb-btn" href="../../pl/jak-zostac-partnerem">Jak zostać partnerem karty</a>
                        <a href="../../pl/partnerzy">Baza Przedsiębiorców</a>
                    </p>
                </div>
            </div>
        </div>
    </div>

    <div class="container mt-30">
        <div class="row">
            <div class="col-12">
                <!-- contracts/PRIVACY-COPY.md §5 "Data-provenance statement",
                     paragraphs (1) and (2), pasted verbatim. This replaces an
                     earlier line that called the data "transakcje kartowe Visa"
                     without saying it is synthetic — the panel is built on the
                     organiser's anonymised SYNTHETIC panel, and a municipal page
                     must not imply otherwise. -->
                <p class="sb-note">
                    <strong>Wykorzystane dane.</strong> (1) Transakcje: zanonimizowany,
                    syntetyczny panel transakcji kartą udostępniony przez organizatora
                    wyzwania, kategoria MCC 5812 (restauracje), Sopot,
                    01.01.2025–30.06.2026. Identyfikatory kart i transakcji są
                    pseudonimowe; nie są prezentowane, nie są łączone z żadnym innym
                    źródłem i służą wyłącznie do zliczania unikalnych kart w agregatach.
                    (2) Dane publiczne: granice i punkty adresowe — UM Sopot oraz PRG
                    (GUGiK) i BDOT10k; wykaz kodów pocztowych — Poczty Polskiej;
                    podkład mapowy — OpenStreetMap; kalendarz wydarzeń i pogoda —
                    serwisy publiczne. Wykorzystano je wyłącznie do osadzenia analizy
                    w kontekście przestrzennym i czasowym — nie zawierają danych
                    osobowych i nie wpływają na liczby transakcyjne.
                </p>
            </div>
        </div>
    </div>
</main>'''

PLACEHOLDER_HTML = """<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Panel przedsiębiorcy — w przygotowaniu</title>
    <link href="../../assets/mock/montserrat.css" rel="stylesheet">
    <link rel="stylesheet" href="../../css/site-inline.css">
    <link rel="stylesheet" href="../../assets/mock/strona-biznesu.css">
</head>
<body class="sb-standalone">
    <div class="sb-pending">
        <p class="sb-kicker">Panel przedsiębiorcy</p>
        <h1 class="sb-pending__title">Panel jest w przygotowaniu</h1>
        <p class="sb-p">
            Ta strona jest miejscem na panel przedsiębiorcy. Aplikacja panelu nie
            została jeszcze podłączona, więc nie pokazujemy tu żadnych danych —
            ani prawdziwych, ani przykładowych.
        </p>
        <p class="sb-p">
            Strona czeka na aplikację panelu pod adresem <code>/app/</code>
            (plik wejściowy <code>app/index.html</code>). Gdy tylko będzie
            dostępna, ta strona wczyta ją automatycznie i to zastrzeżenie zniknie.
        </p>
        <p class="sb-note">
            Jeśli widzisz tę stronę podczas prezentacji, panel nie został
            zbudowany lub nie jest serwowany z katalogu głównego repozytorium.
        </p>
    </div>
</body>
</html>
"""

CSS_BODY = """/* ==========================================================================
   Strona Biznesu — augmentacja repliki (replica-only augmentation).

   Wyłącznie klasy z przedrostkiem .sb- . Plik nie zmienia ani jednej reguły
   motywu: panel działa we własnym dokumencie (iframe), więc nie ma czego
   izolować w tym arkuszu.

   Wzorzec i miejsce są zgodne z NOTES.md: nowe style piszemy tylko
   w site/assets/mock/.
   ========================================================================== */


/* --- dopasowanie menu głównego do ósmej pozycji -------------------------
   MEASURED, not estimated (integrations/tools/probe-nav-fix.mjs).

   The replica already tunes its own nav to fit seven items on one line:
   css/site-inline.css:1118-1127 sets `white-space: nowrap`, a 12 px gap and
   14 px type below 1500 px, with the comment "zeby wszystkie punkty ...
   miescily sie w jednej linii".  An eighth item overflows that budget in two
   windows: 992-1231 px, and 1500-1559 px.  The second one matters: 1512 px is
   the default scaled width of a 14-inch MacBook Pro.

   Two causes, both removed here without touching type or spacing:

     1. `.main-menu { padding: 0 20px }` (cmsCSS/v-custom.css:499) spends 40 px
        of the column on padding that a centred nav does not use.
     2. The items are `inline-block`, so the newlines between the `<li>` tags
        render as word spaces.  Seven of them cost roughly 27 px on top of the
        margins the theme already set.  `display: flex` removes that phantom
        gap, and the theme's own margins (12 px / 20 px) then apply exactly as
        written -- so the visible gaps stay identical to the seven-item site.

   Verified: one row, exactly centred, no clipping, at every width from 1200 px
   to 1920 px.  Type sizes untouched (14 px below 1500, 16 px above). */
@media (min-width: 1200px) {
    .main-menu {
        padding-left: 0;
        padding-right: 0;
    }
    .main-menu nav > ul {
        display: flex;
        flex-wrap: nowrap;
        justify-content: center;
    }
}

.sb-kicker {
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--bd-theme-primary);
    margin: 0 0 8px;
}

.breadcrumb__section .sb-lead {
    max-width: 760px;
    margin: 14px 0 0;
    font-size: 16px;
    line-height: 24px;
    color: #1b1b1b;
}

/* The hero carries a black label box over a photograph; without a scrim the
   white-on-black title is unreadable against a light sky. */
.breadcrumb__section[data-background] {
    position: relative;
}
.breadcrumb__section[data-background]::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(0, 0, 0, .45) 0%, rgba(0, 0, 0, .25) 100%);
}
.breadcrumb__section[data-background] .container {
    position: relative;
    z-index: 1;
}
.breadcrumb__section[data-background] .sb-lead {
    color: #fff;
    text-shadow: 0 1px 3px rgba(0, 0, 0, .55);
}

.sb-strap {
    font-size: 17px;
    line-height: 26px;
    color: #333;
    border-left: 3px solid var(--bd-theme-primary);
    padding-left: 16px;
    margin: 0;
}

/* --- the embedded panel ------------------------------------------------- */

.sb-panel {
    position: relative;
}
.sb-panel__status {
    margin: 0;
    padding: 28px 0;
    text-align: center;
    color: #878787;
    font-size: 14px;
}
.sb-panel.is-ready .sb-panel__status {
    display: none;
}
.sb-panel iframe {
    width: 100%;
    height: 1180px;
    min-height: 820px;
    border: 0;
    display: block;
    background: #fff;
}

@media (max-width: 991.98px) {
    .sb-panel iframe {
        height: 1500px;
    }
}
@media (max-width: 575.98px) {
    .sb-panel iframe {
        height: 1700px;
        min-height: 640px;
    }
}

/* --- footnotes, call to action, partner list ---------------------------- */

.sb-note {
    font-size: 12px;
    line-height: 19px;
    color: #6d6d6d;
    max-width: 900px;
    margin: 18px 0 0;
}
.sb-note--privacy {
    border-top: 1px solid #ededed;
    padding-top: 16px;
}
.sb-note a {
    color: #333;
    text-decoration: underline;
}
.sb-note--label {
    font-style: italic;
    color: #555;
}

.sb-h {
    font-size: 18px;
    font-weight: 700;
    margin: 0 0 10px;
    color: #1b1b1b;
}
.sb-p {
    font-size: 14px;
    line-height: 22px;
    color: #444;
    margin: 0 0 12px;
}
.sb-p a {
    color: var(--bd-theme-primary);
    text-decoration: underline;
}

.sb-area {
    margin-bottom: 22px;
}
.sb-area__title {
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #878787;
    margin: 0 0 4px;
}
.sb-partners {
    list-style: none;
    margin: 0;
    padding: 0;
}
.sb-partner {
    padding: 10px 0;
    border-bottom: 1px solid #ededed;
}
.sb-partner a {
    font-size: 15px;
    font-weight: 600;
    color: #1b1b1b;
}
.sb-partner a:hover {
    color: var(--bd-theme-primary);
}
.sb-partner__meta {
    display: block;
    font-size: 12px;
    color: #878787;
}
.sb-partner__code {
    color: var(--bd-theme-primary);
    font-weight: 600;
}

.sb-cta {
    background: #f6f8fa;
    border-left: 3px solid var(--bd-theme-primary);
    padding: 22px 22px 6px;
}
.sb-cta__links a {
    font-size: 14px;
    font-weight: 600;
    color: var(--bd-theme-primary);
    text-decoration: underline;
    display: block;
    margin-bottom: 8px;
}
.sb-btn {
    display: inline-block !important;
    background: var(--bd-theme-primary);
    color: #fff !important;
    padding: 10px 18px !important;
    text-decoration: none !important;
}

/* --- the placeholder document (rendered inside the iframe) -------------- */

.sb-standalone {
    margin: 0;
    background: #fff;
    font-family: 'Montserrat', sans-serif;
}
.sb-pending {
    max-width: 640px;
    margin: 0 auto;
    padding: 48px 24px;
}
.sb-pending__title {
    font-size: 24px;
    font-weight: 700;
    margin: 0 0 16px;
    color: #1b1b1b;
}
.sb-pending .sb-p {
    font-size: 14px;
    line-height: 22px;
}
.sb-pending code {
    background: #f2f2f3;
    padding: 1px 5px;
    font-size: 13px;
}
"""

JS_BODY = f"""/* ==========================================================================
   Strona Biznesu — podłączenie panelu przedsiębiorcy.

   Panel jest osobną aplikacją pod adresem {PANEL_URL}. Ten skrypt:

     1. sprawdza, czy aplikacja jest dostępna (nagłówek HEAD na plik wejściowy),
     2. wstawia ją do ramki,
     3. dopasowuje wysokość ramki do treści panelu.

   Punkt 3 jest ważny dla odbioru: panel ma około 3000 px wysokości i bez tego
   powstałoby drugie, wewnętrzne okno przewijania — strona wyglądałaby wtedy
   jak obcy widget wklejony w środek serwisu, a nie jak jego własna treść.

   Gdy aplikacji nie ma, w ramce pojawia się strona "panel-w-przygotowaniu.html",
   która mówi wprost, na co strona czeka. Nigdy nie pokazujemy fałszywego panelu
   ani danych przykładowych.

   Brak tutaj jakiejkolwiek zależności sieciowej poza tym samym hostem.
   ========================================================================== */
(function () {{
    "use strict";

    var PANEL_URL = "{PANEL_URL}";
    var PANEL_PROBE = "{PANEL_PROBE}";
    var PENDING = "panel-w-przygotowaniu.html";

    // The panel is a full dashboard; these bound the frame so a runaway
    // document cannot stretch the municipal page without limit.
    var MIN_HEIGHT = 820;
    var MAX_HEIGHT = 6000;

    function showStatus(box, visible) {{
        if (visible) {{
            box.classList.remove("is-ready");
        }} else {{
            box.classList.add("is-ready");
        }}
    }}

    function sizeToContent(frame) {{
        var doc = frame.contentDocument;
        if (!doc || !doc.documentElement) {{
            return;
        }}
        var h = Math.max(
            doc.documentElement.scrollHeight,
            doc.body ? doc.body.scrollHeight : 0
        );
        if (!h) {{
            return;
        }}
        var bounded = Math.min(Math.max(h + 8, MIN_HEIGHT), MAX_HEIGHT);
        frame.style.height = bounded + "px";
    }}

    function watch(frame) {{
        // The panel fills in after its aggregate loads, so re-measure for a
        // while rather than trusting the first load event alone.
        var ticks = 0;
        var timer = window.setInterval(function () {{
            sizeToContent(frame);
            if (++ticks > 24) {{
                window.clearInterval(timer);
            }}
        }}, 500);

        var doc = frame.contentDocument;
        if (doc && window.ResizeObserver) {{
            try {{
                new window.ResizeObserver(function () {{
                    sizeToContent(frame);
                }}).observe(doc.documentElement);
            }} catch (err) {{
                /* older engines: the interval above already covers this */
            }}
        }}
    }}

    function boot() {{
        var box = document.getElementById("sb-panel");
        var frame = document.getElementById("sb-panel-frame");
        if (!box || !frame) {{
            return;
        }}

        function show(src, isPanel) {{
            if (isPanel) {{
                frame.addEventListener("load", function () {{
                    showStatus(box, false);
                    sizeToContent(frame);
                    watch(frame);
                }});
            }}
            frame.src = src;
            if (!isPanel) {{
                showStatus(box, false);
                frame.style.height = "auto";
                frame.style.minHeight = "320px";
            }}
        }}

        try {{
            var xhr = new XMLHttpRequest();
            xhr.open("HEAD", PANEL_PROBE, true);
            xhr.onreadystatechange = function () {{
                if (xhr.readyState !== 4) {{
                    return;
                }}
                var ok = xhr.status >= 200 && xhr.status < 400;
                show(ok ? PANEL_URL : PENDING, ok);
            }};
            xhr.onerror = function () {{
                show(PENDING, false);
            }};
            xhr.send();
            // A server that never answers the HEAD must not leave the juror
            // staring at "Wczytywanie…" forever.
            window.setTimeout(function () {{
                if (!frame.getAttribute("src")) {{
                    show(PENDING, false);
                }}
            }}, 4000);
        }} catch (err) {{
            show(PENDING, false);
        }}
    }}

    if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", boot);
    }} else {{
        boot();
    }}
}})();
"""


def build_main():
    return MAIN


def build_page():
    donor = os.path.join(SITE, DONOR)
    if not os.path.isfile(donor):
        sys.exit(f"donor page missing: {donor}")
    with open(donor, encoding="utf-8") as fh:
        html = fh.read()

    html = re.sub(r"<title>.*?</title>", f"<title>{TITLE}</title>", html, count=1, flags=re.S)
    html = re.sub(r'<meta name="description" content="[^"]*">',
                  f'<meta name="description" content="{DESCRIPTION}">', html, count=1)

    # Link injection belongs to apply-augmentation.py, which does it for every
    # page (the nav fit rule has to reach all 165 headers, not just this one).

    start = html.index("<main>")
    end = html.index("</main>") + len("</main>")
    html = html[:start] + build_main() + html[end:]
    return html


def write(rel, body, check):
    path = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    old = open(path, encoding="utf-8").read() if os.path.isfile(path) else None
    if old == body:
        return False
    if not check:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(SITE):
        sys.exit(f"bundle not found: {SITE}")

    written = []
    if write(PAGE, build_page(), args.check):
        written.append(PAGE)
    if write(PLACEHOLDER, PLACEHOLDER_HTML, args.check):
        written.append(PLACEHOLDER)
    if write(CSS, CSS_BODY, args.check):
        written.append(CSS)
    if write(JS, JS_BODY, args.check):
        written.append(JS)

    verb = "checked" if args.check else "built"
    print(f"{verb} {len(written)} files")
    for w in written:
        print(f"  {w}")


if __name__ == "__main__":
    main()
