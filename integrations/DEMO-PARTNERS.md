# DEMO-PARTNERS — the real Sopot businesses the demo names

**Owner:** municipal integrator · **Source:** `research/sopot-partners.csv` (117
parsed partner profiles) · **Consumers:** the panel's venue selector, the tab
page's partner list, the pitch script.

> ### „Dane dla obszaru **{kod}**, nie dla Twojego lokalu.”
>
> *("Data for area **{code}**, not for your venue.")*
>
> This label is mandatory on every surface that shows an area number next to a
> business name — `contracts/PRIVACY-COPY.md` §4, "The mandatory area label":
> *"in the same visual block as the number. It is not a footnote and it is not
> optional."* The `{kod}` slot is filled with the real postcode and never
> hand-typed as a placeholder. On the tab page it is rendered once per area,
> reading **„Dane dla obszaru 81-777, nie dla Twojego lokalu.”** and
> **„Dane dla obszaru 81-759, nie dla Twojego lokalu.”

---

## 1. The short list — four food-service partners of the Sopot Card

The two demo postcodes are **81-777** and **81-759** (`AGENTS.md`, "the working
demo presets are 81-777 and 81-759"; `contracts/AGGREGATE.md:59-66`). The
business directory holds exactly **four** food-service partners in those two
areas. All four are in the list; the demo walks through the first three.

| # | Venue | Street | Area | Phone | Profile (in this repo) | Logo | Gallery |
|---|---|---|---|---|---|---|---|
| 1 | **Restauracja Falo Sopot** | ul. Na Wydmach 10 | **81-777** | 692 560 892 | `pl/partnerzy/restauracja-falo-sopot-12816437/` | ✔ | 19 photos |
| 2 | **Restauracja Pomarańczowa Plaża** | Emilii Plater 19 | **81-777** | +48 515 263 115 | `pl/partnerzy/restauracja-pomaranczowa-plaza-10565615/` | ✔ | 5 photos |
| 3 | **Dwie Zmiany** | Bohaterów Monte Cassino 31 | **81-759** | +48 58 380 21 27 | `pl/partnerzy/dwie-zmiany-12257/` | ✔ | 2 photos |
| 4 | **Tuż za Rogiem** | ul. Grunwaldzka 4/6 | **81-759** | 730 108 107 | `pl/partnerzy/tuz-za-rogiem-268320/` | ✔ | 11 photos |

All four profile pages ship in `integrations/municipal-site/`, so the tab page
links a juror straight from the panel to the venue's real page — logo, gallery,
description, amenities and discount badge — inside the same municipal site, with
no network access.

**Why these three for the walkthrough.** Falo and Pomarańczowa Plaża sit in
**81-777**, the area that carries **51.1 %** of all transactions (241 of 347
merchants); Dwie Zmiany sits on **Monciak** in **81-759** (39 merchants,
9.4 % of rows, full 18 months). That pairing lets the same three-beat story be
told twice — once for the busiest area in the dataset, once for the most
recognisable street in Sopot — without either of them being a thin cell.

**Recognisability.** Dwie Zmiany is on Bohaterów Monte Cassino, the street every
juror who has been to Sopot has walked. Falo and Pomarańczowa Plaża are beach
venues in the 81-777 area the panel already defaults to.

---

## 2. How this list was produced

```sh
cd /Users/kulma/Documents/Projects/Hackathon/research
python3 - <<'EOF'
import csv
rows = [r for r in csv.DictReader(open('sopot-partners.csv'))
        if r['is_food_service'].strip().lower() == 'true'
        and r['postcode'].strip() in ('81-777', '81-759')]
for r in rows:
    print(r['name'], '|', r['address'], '|', r['postcode'], '|', r['profile_url'])
EOF
```

Output — four rows, reproduced above:

```
Restauracja Falo Sopot | ul. Na Wydmach 10, 81-777 Sopot | 81-777 | /pl/partnerzy/restauracja-falo-sopot-12816437/
Restauracja Pomarańczowa Plaża | Emilii Plater 19 81-777 Sopot | 81-777 | /pl/partnerzy/restauracja-pomaranczowa-plaza-10565615/
Dwie Zmiany | Bohaterów Monte Cassino 31, 81-759 Sopot | 81-759 | /pl/partnerzy/dwie-zmiany-12257/
Tuż za Rogiem | ul. Grunwaldzka 4/6, Sopot 81-759 | 81-759 | /pl/partnerzy/tuz-za-rogiem-268320/
```

Rejected candidate: **81-718** carries eight food-service partners and is the
audit's own §7 suggestion (it names `Restauracja Bulaj` and `Restauracja Małe
Molo`). It is **not** a demo preset in this submission — `AGENTS.md` and
`contracts/AGGREGATE.md` fix the presets at 81-777 and 81-759 — so those venues
are not wired. They remain available as a fallback if a preset changes.

---

## 3. What the partners are, and what they are not

**The partners are the ACTORS. The postcodes are their NEIGHBOURHOODS.**

- The merchant in the demo story is one of these four businesses. It is a real
  Sopot Card partner with a real, browsable page on the municipal site.
- Every number the panel shows is a **sum for the postcode area**, never for the
  venue. The panel defaults to 81-777 and 81-759 because those are the presets.
- **No name-join was attempted, and none should be.** The audit's §5 measured the
  join between partner names and the transaction merchant descriptors at **21 %
  reliable** — it is a coincidence generator, not a key. Chaining a venue name to
  a transaction row would put a fabricated per-venue number in front of a
  restaurateur, which is exactly the failure the project's "no silent fallbacks"
  rule exists to prevent.

### Why 81-777 and 81-759 can carry the story

| area | rows | merchants | share of all rows | source |
|---|---|---|---|---|
| 81-777 | 193,234 | 241 | **51.1 %** | `AGENTS.md`; `research/dataset-profile.md:265` |
| 81-759 | 35,480 | 39 | 9.4 % | `research/dataset-profile.md:421`, `:265` |

Only 18 of 62 postcodes pass all three privacy gates, and they carry 90.7 % of
volume. Both demo areas are among them — `contracts/AGGREGATE.md:59-66` requires
every preset to pass all gates, and lists `81-777` (`Molo i Plac Zdrojowy`,
241 merchants, 51.1 % of volume) and `81-759` (39 merchants, full 18 months).

---

## 4. What the panel agent still needs from this file

The panel's venue-selection screen (audit §7.1 #11–#15) should list these four
names, each mapped to its area:

| venue | area to scope the panel to |
|---|---|
| Restauracja Falo Sopot | `81-777` |
| Restauracja Pomarańczowa Plaża | `81-777` |
| Dwie Zmiany | `81-759` |
| Tuż za Rogiem | `81-759` |

Every one of them must render with the mandatory label from the top of this
file, because the number beside a venue name is an area number.
