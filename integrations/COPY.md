# COPY — every new Polish string, with an English gloss

**Owner:** municipal integrator · **Scope:** strings this integration introduces
into `karta.sopot.pl`. The panel's own interior copy belongs to the panel agent
and is out of scope here.

**Register check.** Every line below is second-person formal (*Twojej*, *znajdziesz*,
*Chcesz*), sentence case, no first person, Polish diacritics intact, and no
exclamation mark except the call to action, which mirrors the site's own
`Zostań Partnerem Karty Sopockiej!`. Numbers `#n` refer to the audit's §7.1
microcopy table where a string is reused verbatim.

---

## 1. The navigation tab

| # | Where | Polish | English |
|---|---|---|---|
| 1 | `<li id="menuItem_900">` label | **Strona Biznesu** | Business Page |
| 1a | full nav markup | `<li class=" " id="menuItem_900"><a class="wyroznione2" href="pl/strona-biznesu">Strona Biznesu</a></li>` | the new tab, `menu-wybrane` on its own page |

## 2. Document head — `pl/strona-biznesu/index.html`

| # | Where | Polish | English |
|---|---|---|---|
| 2 | `<title>` | **Sopocka Strona Biznesu — Karta Sopocka** | Sopot Business Page — Sopot Card |
| 3 | `<meta name="description">` | **Sopocka Strona Biznesu — panel przedsiębiorcy Karty Sopockiej. Płatności kartą w Twojej okolicy: wydarzenia, pogoda i pory dnia.** | Sopot Business Page — the Sopot Card's business panel. Card payments in your area: events, weather and time of day. |

## 3. Breadcrumb hero (audit #3–#6)

| # | Where | Polish | English |
|---|---|---|---|
| 4 | `.sb-kicker` over the title | **Panel przedsiębiorcy** | Entrepreneur's panel |
| 5 | `.breadcrumb__title` | **Sopocka Strona Biznesu** | Sopot Business Page |
| 6 | `.sb-lead` under the title | **Jak wydarzenia, pogoda i pora dnia wpływają na płatności kartą w Twojej branży i Twojej okolicy.** | How events, weather and time of day affect card payments in your industry and your neighbourhood. |
| 7 | `#position` breadcrumb | **Home › Sopocka Strona Biznesu** | Home › Sopot Business Page |

The hero photograph is the city's own *Skwer Kuracyjny* by Marcin Czechowicz,
already mirrored in the replica and served locally; it carries no caption.

## 4. What this is — the strap above the panel

| # | Where | Polish | English |
|---|---|---|---|
| 8 | `.sb-strap`, one line | **Strona Biznesu jest częścią programu Karty Sopockiej: pokazujemy sopockim przedsiębiorcom, jak kształtują się płatności kartą w ich okolicy.** | The Business Page is part of the Sopot Card programme: we show Sopot businesses how card payments in their area take shape. |

## 5. The embedded panel's frame

| # | Where | Polish | English |
|---|---|---|---|
| 9 | iframe `title=` attribute | **Panel przedsiębiorcy — dane o płatnościach kartą** | Entrepreneur's panel — card payment data |
| 10 | status shown while the frame resolves (audit #29) | **Wczytywanie panelu przedsiębiorcy…** | Loading the entrepreneur's panel… |

## 6. Privacy disclosure

**`contracts/PRIVACY-COPY.md` now exists** (it landed while this integration was
being built), and this page **pastes its copy rather than paraphrasing it**, as
that contract requires. The only edit is that the `{kod}` slot is filled with the
real postcode, because the page is static and the contract forbids hand-typing a
placeholder where a value belongs.

| # | Where | Polish | English |
|---|---|---|---|
| 11 | `.sb-note--privacy` | **Porównanie branżowe.** Te liczby to agregat wszystkich restauracji w wybranym obszarze i okresie, liczony z panelu transakcji kartą. Publikujemy je tylko wtedy, gdy grupa obejmuje co najmniej 30 unikalnych kart i co najmniej 3 podmioty, a udział żadnego podmiotu nie przekracza 75%. Stosujemy dodatkowo test różnicowy: grupa musi spełniać progi także po odjęciu dowolnego jednego podmiotu. Twoja własna sprzedaż nie jest odejmowana ani dodawana do tej liczby. Nie pokazujemy nigdy pojedynczego podmiotu ani pojedynczej karty. | **Sector comparison.** These figures aggregate all restaurants in the selected area and period, computed from the card-transaction panel. We publish them only when the group covers at least 30 unique cards and at least 3 entities, and no single entity exceeds a 75% share. We additionally apply a differencing test: the group must still meet the thresholds after any single entity is removed. Your own sales are neither added to nor subtracted from this figure. We never show a single entity or a single card. |
| 12 | `.sb-note--label`, once per area (2 ×) | **Dane dla obszaru &lt;81-759&gt;, nie dla Twojego lokalu.**<br>**Dane dla obszaru &lt;81-777&gt;, nie dla Twojego lokalu.** | Data for area &lt;81-759&gt;, not for your venue.<br>Data for area &lt;81-777&gt;, not for your venue. |

Provenance of #11: `contracts/PRIVACY-COPY.md` §4 "Plane B disclosure" (PL),
verbatim, plus the closing sentence of §2's standing explanation
(*"Nie pokazujemy nigdy pojedynczego podmiotu ani pojedynczej karty."*).
Provenance of #12: §4 "The mandatory area label", **PL:** „Dane dla obszaru
**{kod}**, nie dla Twojego lokalu." with `{kod}` resolved.

#12 is emitted **once per postcode area**, not once per venue, and sits in the
same visual block as that area's venue list — which is what §4 requires
(*"in the same visual block as the number. It is not a footnote and it is not
optional"*).

## 7. Where the venue names come from

| # | Where | Polish | English |
|---|---|---|---|
| 16 | `<h4>` | **Skąd biorą się nazwy lokali w panelu** | Where the venue names in the panel come from |
| 17 | body (audit #12) | **Lista lokali pochodzi z Bazy Przedsiębiorców Karty Sopockiej — tej samej, którą znajdziesz w zakładce Partnerzy. Poniżej cztery lokale gastronomiczne z obszarów demonstracyjnych. Dane w panelu opisują obszar, w którym działa lokal, a nie sam lokal.** | The list of venues comes from the Sopot Card business directory — the same one you will find under Partners. Below are four food-service venues from the demo areas. The data in the panel describes the area the venue operates in, not the venue itself. |
| 18 | link text inside #17, target `../../pl/partnerzy` | **Partnerzy** | Partners — the site's own nav label, verbatim |
| 19 | four list items | **Restauracja Falo Sopot** · ul. Na Wydmach 10 · 81-777<br>**Restauracja Pomarańczowa Plaża** · Emilii Plater 19 · 81-777<br>**Dwie Zmiany** · Bohaterów Monte Cassino 31 · 81-759<br>**Tuż za Rogiem** · ul. Grunwaldzka 4/6 · 81-759 | real Sopot Card partners, taken verbatim from `research/sopot-partners.csv`; see `DEMO-PARTNERS.md` |

Names, streets and postcodes are data, not copy: they are reproduced from the
CSV without editing, including `ul.` and the postcode spacing.

## 8. Business-facing call to action and footnotes

| # | Where | Polish | English |
|---|---|---|---|
| 20 | CTA `<h4>` (audit #39) | **Chcesz zostać Partnerem Karty Sopockiej?** | Want to become a Sopot Card Partner? |
| 21 | CTA body | **Partnerstwo obejmuje prezentację firmy w Bazie Przedsiębiorców, udział w Konkursie punktowym oraz dostęp do systemu statystyk sprzedażowych.** | Partnership covers presenting your business in the business directory, taking part in the points competition, and access to the sales-statistics system. |
| 22 | CTA primary link, target `../../pl/jak-zostac-partnerem` (audit #40) | **Jak zostać partnerem karty** | How to become a card partner — the site's own footer wording, verbatim |
| 23 | CTA secondary link, target `../../pl/partnerzy` | **Baza Przedsiębiorców** | Business directory |
| 24 | data-provenance footnote, paragraphs (1) and (2) | **Wykorzystane dane.** (1) Transakcje: zanonimizowany, syntetyczny panel transakcji kartą udostępniony przez organizatora wyzwania, kategoria MCC 5812 (restauracje), Sopot, 01.01.2025–30.06.2026. Identyfikatory kart i transakcji są pseudonimowe; nie są prezentowane, nie są łączone z żadnym innym źródłem i służą wyłącznie do zliczania unikalnych kart w agregatach. (2) Dane publiczne: granice i punkty adresowe — UM Sopot oraz PRG (GUGiK) i BDOT10k; wykaz kodów pocztowych — Poczty Polskiej; podkład mapowy — OpenStreetMap; kalendarz wydarzeń i pogoda — serwisy publiczne. Wykorzystano je wyłącznie do osadzenia analizy w kontekście przestrzennym i czasowym — nie zawierają danych osobowych i nie wpływają na liczby transakcyjne. | **Data used.** (1) Transactions: the anonymised, synthetic card-transaction panel provided by the challenge organiser, MCC 5812 (restaurants), Sopot, 2025-01-01–2026-06-30. Card and transaction identifiers are pseudonymous; they are never displayed, never joined to any other source, and are used only to count unique cards within aggregates. (2) Public data: boundaries and address points — the City of Sopot, plus PRG (GUGiK) and BDOT10k; postcode register — Poczta Polska; map base layer — OpenStreetMap; event calendar and weather — public services. They are used only to situate the analysis in space and time — they contain no personal data and do not affect any transaction figure. |
| 25 | help footnote (audit #38) | **Potrzebujesz pomocy? kartasopocka@visit.sopot.pl · +48 791 778 477** | Need help? — the site's own contact line, verbatim from `konkurs-punktowy` |

#24 is `contracts/PRIVACY-COPY.md` §5 paragraphs (1) and (2), verbatim. It
**replaces** an earlier draft line reading *"Źródło: zanonimizowane transakcje
kartowe Visa, MCC 5812 (gastronomia), lata 2025–2026"*: that said "Visa
transactions" without saying the panel is **synthetic**, which a municipal page
must not imply. The contract's wording is the accurate one.

#21 is written from the site's own promise: `pl/jak-zostac-partnerem` states
*"Zostając Partnerem Karty, zyskujesz: … ✅ dostęp do systemu statystyk
sprzedażowych"*, and `konkurs-punktowy` justifies the competition as
*"korzyści zarówno dla mieszkańców, jak i lokalnych przedsiębiorców"*. The CTA
therefore names only benefits the portal already advertises.

## 9. The waiting state — `pl/strona-biznesu/panel-w-przygotowaniu.html`

Rendered inside the iframe only when `/app/index.html` is absent. It exists so
the page is never a fake panel and never blank.

| # | Where | Polish | English |
|---|---|---|---|
| 26 | `.sb-kicker` | **Panel przedsiębiorcy** | Entrepreneur's panel |
| 27 | `<h1>` | **Panel jest w przygotowaniu** | The panel is being prepared |
| 28 | body 1 | **Ta strona jest miejscem na panel przedsiębiorcy. Aplikacja panelu nie została jeszcze podłączona, więc nie pokazujemy tu żadnych danych — ani prawdziwych, ani przykładowych.** | This page is the place for the entrepreneur's panel. The panel application is not connected yet, so we show no data here — neither real nor sample. |
| 29 | body 2 | **Strona czeka na aplikację panelu pod adresem `/app/` (plik wejściowy `app/index.html`). Gdy tylko będzie dostępna, ta strona wczyta ją automatycznie i to zastrzeżenie zniknie.** | The page is waiting for the panel application at `/app/` (entry file `app/index.html`). As soon as it is available, this page will load it automatically and this notice will disappear. |
| 30 | body 3 | **Jeśli widzisz tę stronę podczas prezentacji, panel nie został zbudowany lub nie jest serwowany z katalogu głównego repozytorium.** | If you see this page during a presentation, the panel was not built or is not being served from the repository root. |

## 10. Accessibility labels on the offline placeholders

| # | Where | Polish | English |
|---|---|---|---|
| 31 | `assets/mock/offline/pin-red.svg`, `aria-label` | **Punkt na mapie** | Point on the map |
| 32 | `assets/mock/offline/photo-placeholder.svg`, `aria-label` | **Zdjęcie niedostępne w wersji offline** | Photograph unavailable in the offline version |

These two SVGs replace the 154 off-origin `<img src>` values the replica carried
(see `NAV-DIFF.md` §6). Both carry a label so screen readers announce something
truthful rather than a filename.

## 11. Reconciliation

| Item | Status |
|---|---|
| `contracts/PRIVACY-COPY.md` | **landed during this build and is now the source of truth.** §6 (#11–#12) and #24 are pasted from it verbatim; the earlier hand-written disclosure and the "Visa transactions" source line were replaced. Nothing in §6 or #24 is now this document's invention. |
| Panel interior copy | owned by the panel agent; the audit's §7.1 #7–#32, #41 describe it. Not duplicated here. |
| `Dane dla obszaru <kod>, nie dla Twojego lokalu.` | the one string that must match character-for-character across the contract, this page and the panel. Rendered here as `Dane dla obszaru &lt;kod&gt;, nie dla Twojego lokalu.` |
