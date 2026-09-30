# PRIVACY-COPY.md — ready-to-paste UI strings

**Owner:** the privacy gate (`contracts/privacy.py`, mirrored by `contracts/privacy.ts`).
**Audience:** whoever writes the panel's HTML. Every block below is final copy: paste it, do not paraphrase
it. Where a block contains `{…}`, the value is filled at runtime from the gate result — never hand-typed.

**Why this file exists.** The current tree contains one artifact that *denies* enforcement
(`Dokumentacja - 03 Panel.md:202`), two that *claim* it falsely (`Panel.dc.html:332`,
`Dashboard.dc.html:290`), and a video that states the rule on screen. Only one of those can survive.
The cheap, honest resolution is: the code now enforces the rule, the false claims are deleted, and the
copy below — which is generated from the same rule constants the gate uses — replaces them.

**The rule this copy describes** (challenge document §3, „Oczekiwany rezultat”, verbatim):

> „analizy i prezentacje wyników powinny być prowadzone wyłącznie na grupach obejmujących co najmniej 30 kart”
> „każda grupa porównawcza powinna obejmować co najmniej 3 podmioty/graczy, przy czym udział żadnego z nich
> nie może przekraczać 75% analizowanej grupy”
> „Rozwiązanie nie powinno umożliwiać identyfikacji pojedynczych użytkowników, kart, transakcji ani podmiotów”

30 means **30 distinct cards** (`pymt_crd_acct_num_raw`), never 30 cardholders, never 30 transactions.
`≥` and `≤` are inclusive: exactly 30 cards pass, exactly 3 entities pass, exactly 75.000000% passes and
75.000025% fails. All three are evaluated on integers — `100 × top-1 transactions ≤ 75 × group transactions`
— never on a rounded or floating-point share.

---

## 1. Methodology footnote

**Where:** the panel footer, and next to every chart that shows more than one number. Replaces
`Panel v4.dc.html:476`. Generated from `contracts/privacy.py` constants; if a threshold ever changes, this
block must change with it in the same commit.

### PL

> **Metodologia.** Liczby pochodzą z panelu transakcji kartą, kategoria MCC 5812 (restauracje), Sopot,
> 01.01.2025–30.06.2026: 378 212 transakcji, 54 sopockie kody pocztowe z transakcjami, 347 podmiotów.
> Czas GMT przeliczony na czas polski (Europe/Warsaw, z uwzględnieniem zmiany czasu). „Zwykle” = średnia
> z 30 poprzednich dni dla tej samej godziny. **Wszystkie prezentowane liczby są agregatami i przechodzą
> trzy progi anonimizacji: ≥ 30 unikalnych kart, ≥ 3 podmioty w grupie porównawczej oraz udział żadnego
> podmiotu ≤ 75% grupy.** Dodatkowo stosujemy **test różnicowy**: publikujemy tylko takie grupy, które
> spełniają te progi także po odjęciu dowolnego jednego podmiotu z grupy. Grupy, które nie spełniają
> progów, nie są publikowane — pokazujemy wtedy wartość większego obszaru, który progi spełnia, i wyraźnie
> to oznaczamy („wartość większego obszaru: …”), albo nie pokazujemy nic. Liczby kart i podmiotów liczymy
> na zbiorze transakcji, nigdy przez sumowanie podzbiorów (jedna karta może płacić w więcej niż jednym
> obszarze). Wpływ wydarzenia = zmiana obszaru względem jego własnej zwykłej, pomniejszona o zmianę całego
> miasta (punkty procentowe). Kalendarz wydarzeń pochodzi ze źródeł publicznych i jest przykładowy — dane
> transakcyjne nie zawierają godzin ani lokalizacji wydarzeń.

### EN

> **Methodology.** Figures come from the card-transaction panel, MCC 5812 (restaurants), Sopot,
> 2025-01-01–2026-06-30: 378,212 transactions, 54 Sopot postcodes with transactions, 347 entities. GMT
> converted to Polish time (Europe/Warsaw, DST-aware). "Usually" = the mean of the 30 preceding days for the
> same hour. **All published figures are aggregates and pass three anonymisation thresholds: ≥ 30 unique
> cards, ≥ 3 entities in the comparison group, and no entity exceeding a 75% share of the group.** We
> additionally apply a **differencing test**: we publish only groups that still meet those thresholds after
> removing any single entity from the group. Groups that fail are never published; instead we show the value
> of a larger area that does pass, clearly attributed ("value of a larger area: …"), or nothing at all. Card
> and entity counts are computed over the transaction set, never by summing subsets (a single card may pay
> in more than one area). Event impact = the area's change versus its own usual, net of the city's change
> (percentage points). The event calendar comes from public sources and is illustrative — the transaction
> data carries no event times or locations.

---

## 2. Suppression explanation — „why is this area dark?”

**Where:** the map's hatched area tooltip, the panel's empty state, and the series' dash marker. The
`{reason}` slot is filled with the gate's own machine code mapped to the sentence below — **never** a bare
„ukryte” and **never** a generic „za mało danych” when the real cause was a dominated share.

| gate code | what it means | PL sentence | EN sentence |
|---|---|---|---|
| `lt_30_cards` | fewer than 30 distinct cards | „Ukryte: w tym obszarze i o tej porze jest mniej niż 30 unikalnych kart (wymagane ≥ 30).” | "Hidden: fewer than 30 unique cards in this area and time window (≥ 30 required)." |
| `lt_3_merchants` | fewer than 3 merchants | „Ukryte: w tym obszarze i o tej porze działa mniej niż 3 podmioty (wymagane ≥ 3) — grupa porównawcza jest zbyt mała.” | "Hidden: fewer than 3 entities active in this area and time window (≥ 3 required) — the comparison group is too small." |
| `top1_gt_75` | one merchant dominates | „Ukryte: udział jednego podmiotu w tej grupie przekracza 75% — nie pokazujemy grupy zdominowanej przez jednego gracza.” | "Hidden: one entity holds more than 75% of this group — we do not publish a group dominated by a single player." |
| `multi` | several gates fail at once | „Ukryte: grupa nie spełnia kilku progów jednocześnie ({failures}).” | "Hidden: the group fails several thresholds at once ({failures})." |
| `g4_differencing` | the group collapses when one member is removed | „Ukryte: po odjęciu jednego podmiotu grupa przestaje spełniać progi anonimizacji (test różnicowy).” | "Hidden: once a single entity is removed the group no longer meets the anonymisation thresholds (differencing test)." |
| `all_levels_failed` | no level passes | „Analiza zablokowana — żadna grupa (ten obszar, obszar nadrzędny, całe miasto) nie spełnia progów anonimizacji.” | "Analysis blocked — no group (this area, its parent area, the whole city) meets the anonymisation thresholds." |
| `thin_base` | too few transactions in the window (display floor, **not** a privacy gate) | „Za mało danych w tym oknie czasowym, aby porównać — to nie jest ukrycie ze względów prywatności.” | "Too little data in this time window to compare — this is not a privacy suppression." |
| `no_data` | no transactions at all | „Brak danych dla tego obszaru i okresu.” | "No data for this area and period." |

### The standing explanation (PL)

> **Dlaczego czasem nie ma liczby.** Nie pokazujemy wartości dla grup, które byłyby zbyt małe, żeby
> zagwarantować anonimowość. Progi to **30 unikalnych kart** i **3 podmioty**, a udział żadnego pojedynczego
> podmiotu nie może przekraczać **75%** grupy. Gdy obszar lub godzina tego nie spełnia, pokazujemy wartość
> większego obszaru, który próg spełnia — z podpisem, którego obszaru to wartość — albo oznaczamy miejsce
> jako niedostępne. Nie pokazujemy nigdy pojedynczego podmiotu ani pojedynczej karty. W tym widoku ukrytych
> jest obecnie **{pct_hidden}%** odczytów obszarów.

### The standing explanation (EN)

> **Why a figure is sometimes missing.** We do not show values for groups too small to guarantee anonymity.
> The thresholds are **30 unique cards** and **3 entities**, and no single entity may exceed **75%** of the
> group. Where an area or hour fails, we show the value of a larger area that passes — labelled with which
> area it is — or we mark the spot as unavailable. We never show a single entity or a single card. In this
> view, **{pct_hidden}%** of area readings are currently suppressed.

`{pct_hidden}` is computed from `artifacts/privacy-report.json` (`grain_postcode_month_daypart.summary`:
`100 × (cells − all_three_pass) / cells`), not hand-written. Measured floor today: **19.6%** of the
postcode × month × daypart cells pass all three gates, i.e. roughly 80% of that view is suppressed — say so
in the UI, and do not round it in our favour.

---

## 3. Small-numbers policy

**Where:** the methodology page, and the tooltip of any percentage.

### PL

> **Polityka małych liczb.** Progi: **≥ 30 unikalnych kart**, **≥ 3 podmioty**, **≤ 75% udziału**
> największego podmiotu. Progi sprawdzamy na liczbach całkowitych, bez zaokrągleń: warunek udziału jest
> spełniony wtedy i tylko wtedy, gdy `100 × transakcje największego podmiotu ≤ 75 × transakcje w grupie`.
> Wartość 75,0% jest dopuszczalna, 75,1% nie. Dokładnie 29 kart nie przechodzi, 30 przechodzi; 2 podmioty
> nie przechodzą, 3 przechodzą. Udziały pokazujemy po zaokrągleniu do jednego miejsca po przecinku, ale
> porównanie zawsze wykonujemy na wartościach dokładnych — zaokrąglenie nigdy nie przenosi grupy przez próg.
> Sprawdzamy **obie** miary udziału: transakcje i unikalne karty; grupa przechodzi tylko wtedy, gdy żadna
> z nich nie przekracza 75%. Każdy publikowany procent ma mianownik, który sam spełnia próg 30 kart;
> dotyczy to również udziałów kart zagranicznych i udziału pasa nadmorskiego.

### EN

> **Small-numbers policy.** Thresholds: **≥ 30 unique cards**, **≥ 3 entities**, **≤ 75% share** for the
> largest entity. Gates are evaluated on integers, without rounding: the share condition holds if and only
> if `100 × the largest entity's transactions ≤ 75 × the group's transactions`. Exactly 75.0% passes; 75.1%
> does not. Exactly 29 cards fails, 30 passes; 2 entities fail, 3 pass. Shares are displayed rounded to one
> decimal, but the comparison always uses exact values — rounding never moves a group across a threshold.
> **Both** share metrics are checked — transactions and unique cards; a group passes only when neither
> exceeds 75%. Every published percentage has a denominator that itself meets the 30-card threshold; this
> applies to foreign-card shares and the seafront-strip share as well.

---

## 4. The two planes — own data vs gated comparison

**Where:** the split screen. Plane A on the left, Plane B on the right. **Never blend the two into one
number**, and never derive a Plane A figure from the pooled panel: finding "the merchant's own volume in
the panel" is exactly the re-identification attempt the challenge forbids (§1.5(a)).

| | **Plane A — your own data** | **Plane B — the comparison panel** |
|---|---|---|
| Source | the merchant's own acquirer/POS feed, with consent | the anonymised card-transaction panel |
| Subjects | one (the merchant itself) | many |
| Rule | not a k-anonymity group — it is your own till | **gated: ≥ 30 cards, ≥ 3 entities, ≤ 75%, plus the differencing test** |
| If it cannot be shown | show the gap, ask for the feed | escalate to the smallest passing ancestor, or suppress |

### Plane A disclosure

PL:

> **Twoje dane.** Te liczby pochodzą wyłącznie z Twoich własnych transakcji przekazanych przez Twojego
> operatora płatności, za Twoją zgodą. Nie pochodzą z panelu porównawczego i nie zawierają danych innych
> podmiotów. Możesz je w każdej chwili wyłączyć.

EN:

> **Your data.** These figures come only from your own transactions supplied by your payment provider, with
> your consent. They are not drawn from the comparison panel and contain no other entity's data. You can
> switch this off at any time.

### Plane B disclosure

PL:

> **Porównanie branżowe.** Te liczby to agregat wszystkich restauracji w wybranym obszarze i okresie,
> liczony z panelu transakcji kartą. Publikujemy je tylko wtedy, gdy grupa obejmuje co najmniej 30
> unikalnych kart i co najmniej 3 podmioty, a udział żadnego podmiotu nie przekracza 75%. Stosujemy
> dodatkowo test różnicowy: grupa musi spełniać progi także po odjęciu dowolnego jednego podmiotu. Twoja
> własna sprzedaż nie jest odejmowana ani dodawana do tej liczby.

EN:

> **Sector comparison.** These figures aggregate all restaurants in the selected area and period, computed
> from the card-transaction panel. We publish them only when the group covers at least 30 unique cards and
> at least 3 entities, and no single entity exceeds a 75% share. We additionally apply a differencing test:
> the group must still meet the thresholds after any single entity is removed. Your own sales are neither
> added to nor subtracted from this figure.

### The mandatory area label

**Every** Plane B number carries this line, in the same visual block as the number. It is not a footnote and
it is not optional: the panel's own documentation used to present an area aggregate as "the venue's values",
which is the confusion this label exists to end.

> **PL:** „Dane dla obszaru **{kod}**, nie dla Twojego lokalu.”

> **EN:** “Data for area **{code}**, not for your venue.”

When the value was escalated to an ancestor, the label names the **ancestor**, and the badge says so:

> **PL:** „Wartość większego obszaru: **{nazwa_obszaru}** ({poziom}) — dla Twojego obszaru grupa nie spełnia
> progów anonimizacji ({powód}).”

> **EN:** “Value of a larger area: **{area_label}** ({level}) — your own area's group does not meet the
> anonymisation thresholds ({reason}).”

### Level badges (replaces the false claim in `Panel.dc.html:332`)

| level | PL | EN |
|---|---|---|
| `cell` | „Twój obszar · grupa spełnia progi anonimizacji” | “Your area · the group meets the anonymisation thresholds” |
| `parent` | „Obszar nadrzędny · Twój obszar ma zbyt małą grupę lub zdominowany udział” | “Parent area · your area's group is too small or too dominated” |
| `city` | „Całe miasto · mniejsze obszary nie spełniają progów” | “Whole city · smaller areas do not meet the thresholds” |
| `locked` | „Analiza zablokowana · żadna grupa nie spełnia progów: {reason}” | “Analysis blocked · no group meets the thresholds: {reason}” |

`{reason}` is one of the codes in §2 — spelled out in words, never shown raw and never replaced by a
generic „ukryte”.

---

## 5. Data-provenance statement

**Where:** the methodology page, and the deck. Satisfies challenge §1.5(b) and §1.5(d) (p32/p199, p152/p323).

### PL

> **Wykorzystane dane.** (1) **Transakcje:** zanonimizowany, syntetyczny panel transakcji kartą
> udostępniony przez organizatora wyzwania, kategoria MCC 5812 (restauracje), Sopot, 01.01.2025–30.06.2026.
> Identyfikatory kart i transakcji są pseudonimowe; nie są prezentowane, nie są łączone z żadnym innym
> źródłem i służą wyłącznie do zliczania unikalnych kart w agregatach. Nie odczytujemy atrybutów
> przypisanych do karty (`lau_enr`, `fua_enr`, `pstl_cd_enr`) ani nie publikujemy żadnej wartości kluczowanej
> tymi kolumnami. (2) **Dane publiczne:** granice i punkty adresowe — UM Sopot oraz PRG (GUGiK) i BDOT10k;
> wykaz kodów pocztowych — Poczty Polskiej; podkład mapowy — OpenStreetMap; kalendarz wydarzeń i pogoda —
> serwisy publiczne. Wykorzystano je wyłącznie do osadzenia analizy w kontekście przestrzennym i czasowym —
> **nie zawierają danych osobowych i nie wpływają na liczby transakcyjne**. (3) **Ograniczenie celu:** dane
> wykorzystujemy wyłącznie na potrzeby tego wyzwania; nie podejmujemy prób identyfikacji pojedynczych osób,
> podmiotów ani rzeczywistych transakcji i nie łączymy danych z żadnym rejestrem zewnętrznym.

### EN

> **Data used.** (1) **Transactions:** the anonymised, synthetic card-transaction panel provided by the
> challenge organiser, MCC 5812 (restaurants), Sopot, 2025-01-01–2026-06-30. Card and transaction
> identifiers are pseudonymous; they are never displayed, never joined to any other source, and are used only
> to count unique cards within aggregates. We do not read the card-level attributes `lau_enr`, `fua_enr`,
> `pstl_cd_enr`, and we publish no value keyed by them. (2) **Public data:** boundaries and address points —
> the City of Sopot, plus PRG (GUGiK) and BDOT10k; postcode register — Poczta Polska; map base layer —
> OpenStreetMap; event calendar and weather — public services. They are used only to situate the analysis in
> space and time — they contain **no personal data** and do not affect any transaction figure. (3) **Purpose
> limitation:** the data is used solely for this challenge; we do not attempt to identify individual persons,
> entities or actual transactions, and we join the data to no external register.

---

## 6. Integrator note — how the app must call the gate

Not UI copy: this is the one sanctioned way a number reaches the screen. It is stated here because the copy
above makes claims that are only true if this path is the only path.

```python
from contracts import privacy as P

cells = {"cell": cell, "parent": parent_cell, "city": city_cell}   # precomputed, gated aggregates
result = P.cascade(cells, rules=P.PRODUCT_RULES)                    # G1+G2+G3+G4, cell → parent → city
value = P.release(result, rules=P.PRODUCT_RULES)                    # asserts, then returns value or None
if value is None:
    render_suppression(result.reason, result.detail)                # NEVER a placeholder number
else:
    render_value(value, level_label=value.level, reason=result.reason)
```

In the browser, the same three calls exist in `contracts/privacy.ts` (`cascade`, `assertReleased`,
`releaseValue`). `assertReleased` throws — it never warns — on `ungated_path`, `orphan_release`, `leak`,
`no_trace` or `stale_rules`. A record that did not come from `gate()`/`cascade()` cannot be rendered, and a
suppressed record cannot carry a value: the type makes it unrepresentable, and the guard re-checks it.

**The rule:** any aggregate the app can display must have been produced by `gate()`. The prototype broke
exactly this rule — it aggregated the whole cube in the browser and suppressed at *render* time, so every
"hidden" number was already in the client and readable from DevTools.

---

## 7. Provenance of the numbers in this file

| Number | Where it comes from |
|---|---|
| 378,212 transactions · 347 entities · 160,127 cards · 2025-01-01–2026-06-30 | `artifacts/privacy-report.json` → `source` |
| 54 Sopot postcodes with transactions · 62 postcode cells in the audited universe | `artifacts/privacy-report.json` → `method.postcode_universe`, `grain_postcode.summary` |
| 18 of 62 postcode cells pass all three gates and carry **90.69%** of volume | `grain_postcode.summary.all_three_pass_volume_only`, `.share_all_three_volume_only_pct` |
| ~80% of the postcode × month × daypart view is suppressed | `grain_postcode_month_daypart.summary` |
| the three thresholds and their exact boundary behaviour | `contracts/privacy.py` constants; `tests/privacy/test_gates.py::test_boundary_thresholds` |

Command: `python3 scripts/privacy_report.py --src /Users/kulma/Downloads --out artifacts/privacy-report.json`
