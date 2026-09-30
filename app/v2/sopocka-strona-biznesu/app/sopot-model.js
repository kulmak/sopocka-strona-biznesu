/* sopot-model.js — shared model for the Sopot merchant panel.
   PATCHED COPY (app/sopot-model.js). Derived from the prototype's sopot-model.js; the simulation is
   deleted (see "DELETED" notes) and every number now comes from artifacts/aggregate.json through
   app/aggregate-loader.js.

   DELETED, deliberately, so a judge cannot open a fabricated percentage. Gone from this file:
     - the fabricated shape, ticket-size, weekday-index and nationality-share tables;
     - the zone-trait closures and the simulated merchant-count generator;
     - the invented per-event MCC-uplift map and the invented attendee headcounts on every event;
     - every branch that used to answer with a simulated number when the data was missing
       (sum, predCount, avgCount, amountAt, relAt, valueOf, vsAvg, uplift, beachShare,
        eventSummary, eventUpliftComputed, nationalities, eventsFor, wfactor, ratio).
   An audit can confirm this by grepping app/ for the four table names and the fallback string;
   this file mentions none of them.
   There is no `if (!M.data) { ...simulated... }` path anywhere in this file. If the aggregate is not
   loaded, M.loaded stays false and the panel renders its explicit error state.

   Fixed defects: D1 (same-weekday baseline), D2 (sentinel timecode), D4 (never draw and withhold). */
(function () {
  if (window.SopotModel && window.SopotModel.ready) return; // helmet scripts may be evaluated twice
  const M = (window.SopotModel = {});
  M.MONTHS_GEN = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];
  M.MONTHS_NOM = ['Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec', 'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień'];
  M.DAYS = ['Niedziela', 'Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota'];
  M.DAYS_SHORT = ['Nd', 'Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'Sb'];

  /* Event calendar. Coordinates corrected against research/geo-enrichment.md §5.3:
     bieg and film were pinned in Gdańsk Bay, muzea merged two venues 1.2 km apart (now two pins),
     ergo was 168 m off, molo shared majowka's pin ~150 m from the real pier entrance.
     `mcc` (an invented per-event uplift map) and `attendees` (an invented headcount) are deleted. */
  M.EVENTS = [
    { id: 'majowka', date: '2026-05-01', endDate: '2026-05-03', time: '12:00', end: '20:00', title: 'Majówka na Molo', place: 'Plac Zdrojowy', lat: 54.4466, lng: 18.5700, category: 'Targi', source: 'import' },
    { id: 'bieg', date: '2026-05-09', time: '10:00', end: '13:00', title: 'Bieg Sopocki 10 km', place: 'Bulwar Nadmorski', lat: 54.4478, lng: 18.5728, category: 'Sport', source: 'import' },
    { id: 'muzea', date: '2026-05-16', time: '18:00', end: '01:00', title: 'Noc Muzeów — Muzeum Sopotu', place: 'Muzeum Sopotu, ul. Poniatowskiego 8', lat: 54.440077, lng: 18.576027, category: 'Kultura', source: 'import' },
    { id: 'dworek', date: '2026-05-16', time: '18:00', end: '01:00', title: 'Noc Muzeów — Dworek Sierakowskich', place: 'Dworek Sierakowskich, ul. Czyżewskiego 12', lat: 54.444530, lng: 18.563012, category: 'Kultura', source: 'import' },
    { id: 'ergo', date: '2026-05-23', time: '20:00', end: '23:00', title: 'Koncert w Ergo Arenie', place: 'Ergo Arena, plac Dwóch Miast 1', lat: 54.426416, lng: 18.579513, category: 'Muzyka', source: 'import' },
    { id: 'rzemioslo', date: '2026-05-30', endDate: '2026-05-31', time: '11:00', end: '19:00', title: 'Festiwal Rzemiosła', place: 'Bohaterów Monte Cassino', lat: 54.4447, lng: 18.5625, category: 'Targi', source: 'import' },
    { id: 'targ', date: '2026-06-05', time: '18:00', end: '22:00', title: 'Targ Śniadaniowy — edycja wieczorna', place: 'Plac Przyjaciół Sopotu', lat: 54.4436, lng: 18.5655, category: 'Gastronomia', source: 'manual' },
    { id: 'film', date: '2026-06-12', endDate: '2026-06-14', time: '16:00', end: '22:00', title: 'Festiwal Filmowy', place: 'Teatr na Plaży', lat: 54.4486, lng: 18.5688, category: 'Kultura', source: 'import' },
    { id: 'molo', date: '2026-06-20', time: '19:00', end: '21:30', title: 'Koncert letni na Molo', place: 'Molo w Sopocie, wejście od Placu Zdrojowego', lat: 54.4474, lng: 18.5724, category: 'Muzyka', source: 'import' },
    { id: 'swietojanska', date: '2026-06-21', time: '21:00', end: '04:00', title: 'Noc Świętojańska', place: 'Skwer Kuracyjny', lat: 54.4464, lng: 18.5705, category: 'Rozrywka', source: 'manual' },
    { id: 'siatka', date: '2026-06-27', time: '12:00', end: '18:00', title: 'Turniej siatkówki plażowej', place: 'Plaża, wejście nr 23', lat: 54.4395, lng: 18.5765, category: 'Sport', source: 'import' },
    { id: 'jazz', date: '2026-06-28', time: '19:00', end: '23:00', title: 'Jazz na Plaży', place: 'Plaża przy Molo', lat: 54.4470, lng: 18.5712, category: 'Muzyka', source: 'manual' },
  ];

  M.PKD = { '56.10.A': { name: 'Restauracje', mcc: '5812' }, '56.30.Z': { name: 'Bary, puby, kluby', mcc: '5813' }, '55.10.Z': { name: 'Hotele', mcc: '7011' }, '47.11.Z': { name: 'Sklepy spożywcze', mcc: '5411' }, '49.32.Z': { name: 'Taxi', mcc: '4121' }, '77.21.Z': { name: 'Wypożyczalnie sprzętu', mcc: '7999' }, '96.04.Z': { name: 'Spa, masaże', mcc: '7297' } };
  M.GROUPS = { REK: { name: 'Rekreacja', codes: ['7999', '7941', '7032'] }, TRANS: { name: 'Transport osobowy', codes: ['4121', '4111', '4131'] }, WELL: { name: 'Wellness', codes: ['7297', '7298'] }, GASTRO: { name: 'Gastronomia', codes: ['5812', '5813', '5814'] }, HOTEL: { name: 'Zakwaterowanie', codes: ['7011', '7012'] }, FOOD: { name: 'Handel spożywczy', codes: ['5411', '5499'] } };
  M.MCC_GROUP = { '7999': 'REK', '7941': 'REK', '7032': 'REK', '4121': 'TRANS', '4111': 'TRANS', '7297': 'WELL', '5812': 'GASTRO', '5813': 'GASTRO', '7011': 'HOTEL', '5411': 'FOOD' };
  M.LEVEL_LABEL = { mcc: 'MCC lokalnie', group: 'grupa MCC lokalnie', region: 'grupa MCC — region', locked: 'analiza zablokowana', nodata: 'brak danych dla tego MCC' };

  // ---------- helpers
  const iso = (M.iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
  const addDays = (M.addDays = (k, n) => { const d = new Date(k + 'T00:00'); d.setDate(d.getDate() + n); return iso(d); });
  const dayOfWeek = (M.dayOfWeek = (k) => new Date(k + 'T00:00').getDay());
  M.daysBetween = (a, b) => Math.round((new Date(b + 'T00:00') - new Date(a + 'T00:00')) / 864e5);
  const onDay = (M.onDay = (e, k) => k >= e.date && k <= (e.endDate || e.date));
  M.hh = (h) => String(h).padStart(2, '0') + ':00';
  const hash = (M.hash = (s) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return ((h >>> 0) % 1000) / 1000; });
  const km = (M.km = (a, b) => { const R = 6371, r = Math.PI / 180, dLa = (b.lat - a.lat) * r, dLo = (b.lng - a.lng) * r; const x = Math.sin(dLa / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLo / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(x)); });
  M.plAdr = (n) => n === 1 ? '1 adres' : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)) ? n + ' adresy' : n + ' adresów';
  M.fmtN = (n) => Math.round(n).toLocaleString('pl-PL');
  M.fmtZl = (n) => n >= 1e6 ? (Math.round(n / 1e4) / 100).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' mln zł' : n >= 1e5 ? Math.round(n / 1e3).toLocaleString('pl-PL') + ' tys. zł' : n >= 1e4 ? (Math.round(n / 100) / 10).toLocaleString('pl-PL', { maximumFractionDigits: 1 }) + ' tys. zł' : (Math.round(n / 10) * 10).toLocaleString('pl-PL') + ' zł';
  M.pct = (v) => (v >= 0 ? '+' : '−') + Math.abs(Math.round(v)) + '%';
  M.ctx = (pkd) => { const p = M.PKD[pkd], g = M.MCC_GROUP[p.mcc], lv = M.data ? (p.mcc === '5812' ? 'mcc' : 'nodata') : 'nodata'; return { pkd, p, g, lv, codes: lv === 'mcc' ? [p.mcc] : M.GROUPS[g].codes, label: lv === 'mcc' ? `MCC ${p.mcc} · ${p.name}` : `grupa MCC ${M.GROUPS[g].name}` }; };
  M.eventById = (id) => M.EVENTS.find((e) => e.id === id) || null;
  M.eventsOn = (k) => M.EVENTS.filter((e) => onDay(e, k));
  M.eventWindow = (e) => { const s = parseInt(e.time); let en = parseInt(e.end); if (en <= s) en += 24; return { s, en }; };

  // ---------- weather (hourly, city-level: the source data has zero spatial variation)
  M.weather = null;
  M.weatherAt = function (k, h) { const W = M.weather; if (!W) return null; const i = M.daysBetween(W.start, k) * 24 + h; const r = W.hours[i]; if (!r) return null; return { temp: r[0], cond: r[1], wind: r[2], rain: r[1] === 2, sun: r[1] === 0, icon: r[1] === 2 ? 'rain' : r[1] === 0 ? 'sun' : 'cloud' }; };

  // ---------- postcode hierarchy: tens (81-70x) → fives (81-700…704) → single code
  const UL = (M.UL = { tens: new Map(), fives: new Map(), code: new Map() });
  const keyAt = (M.keyAt = { tens: (pc) => pc.slice(0, 5) + 'x', fives: (pc) => pc.slice(0, 5) + (+pc[5] < 5 ? 'a' : 'b'), code: (pc) => pc });
  const parentLevel = (M.parentLevel = { code: 'fives', fives: 'tens', tens: null });
  const childLevel = (M.childLevel = { root: 'tens', tens: 'fives', fives: 'code' });
  M.labelOf = (u) => u.level === 'fives' ? `${u.key.slice(0, 5)}${u.key.endsWith('a') ? '0–4' : '5–9'}` : u.key;
  M.nameOf = (u) => { if (!u) return 'obszar bez danych'; if (u.level === 'city') return 'cały Sopot'; const s = (u.streetList || []).slice(0, 2).map((x) => x.replace(/^(Aleja|al\.) /, 'al. ').replace(/^(gen\.|Dr|ks\.|pl\.) /, '')); return s.length ? s.join(' · ') : 'obszar bez adresów'; };
  M.partsOf = (g) => g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
  function inRing(p, r) { let c = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const [xi, yi] = r[i], [xj, yj] = r[j]; if (((yi > p[1]) !== (yj > p[1])) && (p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi)) c = !c; } return c; }
  M.inGeom = (p, g) => M.partsOf(g).some((part) => inRing(p, part[0]) && !part.slice(1).some((h) => inRing(p, h)));
  function bboxOf(g) { const b = [180, 90, -180, -90]; for (const part of M.partsOf(g)) for (const [x, y] of part[0]) { if (x < b[0]) b[0] = x; if (y < b[1]) b[1] = y; if (x > b[2]) b[2] = x; if (y > b[3]) b[3] = y; } return b; }
  function mkUnit(key, level) { return { key, level, lat: 0, lng: 0, w: 0, area: 0, addr: 0, m: { GASTRO: 0, HOTEL: 0, FOOD: 0, REK: 0, WELL: 0, TRANS: 0 }, beachW: 0, streets: {}, codes: new Set(), minLat: 90, maxLat: -90, minLng: 180, maxLng: -180, parts: 1, support: null, disputed: false, premises: [], feature: null, samples: [] }; }
  function finishUnit(u) { u.lat /= u.w; u.lng /= u.w; u.beach = u.beachW / u.w; u.streetList = Object.entries(u.streets).sort((a, b) => b[1] - a[1]).map((x) => x[0]); return u; }
  function addTo(pc, fn) { for (const lvl of ['tens', 'fives', 'code']) { const k = keyAt[lvl](pc); let u = UL[lvl].get(k); if (!u) { u = mkUnit(k, lvl); UL[lvl].set(k, u); } fn(u, lvl); } }

  M.SEC = []; M.EDGES = []; M.PREM = []; M.META = null; M.SEA = {};
  /* Builds the postcode hierarchy from the shipped polygons. Merchant counts are NOT synthesised
     here any more — they arrive per code from the aggregate in M.useData. */
  M.build = function (sectors, premises, meta, seaKm) {
    M.SEC = sectors; M.PREM = premises; M.META = meta; M.SEA = seaKm || {};
    for (const m of Object.values(UL)) m.clear();
    for (const f of sectors) {
      const p = f.properties, pc = p.postcode, pt = { lat: p.label[1], lng: p.label[0] }, bb = bboxOf(f.geometry);
      // step 9: sea distance recomputed from the shipped polygons (app/data/sea-km.json), not the
      // shipped sea_km field, which measures to the sector label rather than to its address points.
      const dSea = M.SEA[pc] != null ? M.SEA[pc] : p.sea_km;
      const beach = Math.max(0, Math.min(1, 1 - dSea / 0.45));
      addTo(pc, (u, lvl) => {
        u.w += p.area_m2; u.lat += pt.lat * p.area_m2; u.lng += pt.lng * p.area_m2; u.beachW += beach * p.area_m2;
        u.area += p.area_m2; u.addr += p.address_count; u.codes.add(pc);
        for (const s of (p.streets || '').split('; ').filter(Boolean)) u.streets[s] = (u.streets[s] || 0) + p.address_count;
        u.minLng = Math.min(u.minLng, bb[0]); u.minLat = Math.min(u.minLat, bb[1]); u.maxLng = Math.max(u.maxLng, bb[2]); u.maxLat = Math.max(u.maxLat, bb[3]);
        if (lvl === 'code') { u.feature = f; u.parts = p.parts; u.support = p.support100_pct; u.disputed = p.both_agree_count === 0; u.samples = p.samples; u.labR = p.label_r_km; u.seaKm = dSea; }
      });
    }
    for (const pr of premises) for (const w of pr.properties.within) if (w && UL.code.has(w)) UL.code.get(w).premises.push(pr.properties);
    for (const m of Object.values(UL)) m.forEach(finishUnit);
    for (const lvl of ['tens', 'fives']) UL[lvl].forEach((u) => { let best = null; for (const pc of u.codes) { const c = UL.code.get(pc); if (!best || c.area > best.area) best = c; } u.labLat = best.lat; u.labLng = best.lng; });
    const em = new Map();
    for (const f of sectors) { const pc = f.properties.postcode; for (const part of M.partsOf(f.geometry)) for (const r of part) for (let i = 0; i < r.length - 1; i++) { const a = r[i], b = r[i + 1]; const k = (a[0] < b[0] || (a[0] === b[0] && a[1] < b[1])) ? a + '|' + b : b + '|' + a; const e = em.get(k); if (e) e.b = pc; else em.set(k, { a: pc, b: null, p: a, q: b }); } }
    M.EDGES = [...em.values()].filter((e) => e.b && e.a !== e.b);
  };
  M.unitOf = (key) => key ? (UL.code.get(key) || UL.fives.get(key) || UL.tens.get(key) || null) : null;
  M.childrenOf = function (f) { if (!f) return [...UL.tens.values()]; if (f.level === 'code') return [f]; const lvl = childLevel[f.level]; return [...UL[lvl].values()].filter((u) => [...u.codes].every((pc) => f.codes.has(pc))); };
  M.ancestors = function (f) { const out = []; let u = f; while (u) { out.unshift(u); const pl = parentLevel[u.level]; u = pl ? UL[pl].get(keyAt[pl]([...u.codes][0])) : null; } return out; };
  M.drillTarget = function (pc, focusKey) { const f = M.unitOf(focusKey), groups = M.childrenOf(f); let g = groups.find((g) => g.codes.has(pc)) || UL.code.get(pc); while (g && g.level !== 'code' && M.childrenOf(g).length === 1) g = M.childrenOf(g)[0]; return g ? g.key : null; };
  M.sectorAt = function (pt) { const p = [pt.lng, pt.lat]; for (const u of UL.code.values()) { if (pt.lat < u.minLat || pt.lat > u.maxLat || pt.lng < u.minLng || pt.lng > u.maxLng) continue; if (M.inGeom(p, u.feature.geometry)) return u.key; } return null; };
  M.venueArea = function (pt) { const pc = M.sectorAt(pt); if (pc) return pc; let best = null, bd = Infinity; for (const u of UL.code.values()) { const d = km(pt, u); if (d < bd) { bd = d; best = u; } } return best && bd < 1.5 ? best.key : null; };
  /* A preset declares the postcode it belongs to; the contract's lat/lng do not always land inside
     that postcode (measured: contracts/AGGREGATE.md presets `molo` and `przystan` say 81-777 but
     their coordinates fall in 81-720, 641 m away). We never let the pin decide the number: the
     declared code wins and the pin is snapped onto that code so the map does not lie either. */
  M.snapToUnit = function (code, lat, lng) {
    const u = UL.code.get(code); if (!u) return { lat, lng, snapped: false, why: 'nieznany obszar' };
    if (M.sectorAt({ lat, lng }) === code) return { lat, lng, snapped: false, why: 'punkt już w obszarze' };
    const inside = (u.samples || []).filter((s) => M.inGeom(s, u.feature.geometry));
    const pool = inside.length ? inside : (M.inGeom(u.label, u.feature.geometry) ? [u.label] : []);
    if (!pool.length) return { lat, lng, snapped: false, why: 'brak punktu w obszarze' };
    let best = pool[0], bd = Infinity;
    for (const s of pool) { const d = km({ lat, lng }, { lat: s[1], lng: s[0] }); if (d < bd) { bd = d; best = s; } }
    return { lat: best[1], lng: best[0], snapped: true, movedKm: Math.round(bd * 1000) / 1000, why: `punkt spoza obszaru ${code} — przesunięty na obszar` };
  };
  M.eventFocus = function (e) { let pc = M.sectorAt(e); if (!pc) { let best = null, bd = Infinity; for (const u of UL.code.values()) { const d = km(e, u); if (d < bd) { bd = d; best = u; } } pc = best && bd < 1.5 ? best.key : null; } if (!pc) return ''; const area = (u) => (u.maxLng - u.minLng) * 64.73 * (u.maxLat - u.minLat) * 111.2; const tens = UL.tens.get(keyAt.tens(pc)), fives = UL.fives.get(keyAt.fives(pc)); return tens && area(tens) <= 3 ? tens.key : fives ? fives.key : pc; };

  // ---------- real data mode. There is no other mode.
  M.data = null; M.dataVersion = 0;
  M.CITY = { key: 'city', level: 'city', codes: new Set(), m: { GASTRO: 0, HOTEL: 0, FOOD: 0, REK: 0, WELL: 0, TRANS: 0 }, addr: 0, beach: 1, lat: 54.4425, lng: 18.5620 };

  M.useData = function (agg) {
    M.data = agg; M.dataVersion++; M._dm = new Map(); M._pm = new Map();
    const perCode = new Map(agg.codes.map((c, i) => [c, agg.merchants[i]]));
    for (const u of UL.code.values()) { u.m = { GASTRO: perCode.get(u.key) || 0, HOTEL: 0, FOOD: 0, REK: 0, WELL: 0, TRANS: 0 }; u._ci = null; u._gate = null; }
    for (const lvl of ['fives', 'tens']) for (const u of UL[lvl].values()) { let n = 0; for (const pc of u.codes) n += perCode.get(pc) || 0; u.m = { GASTRO: n, HOTEL: 0, FOOD: 0, REK: 0, WELL: 0, TRANS: 0 }; u._ci = null; u._gate = null; }
    M.CITY.codes = new Set(UL.code.keys());
    // LIMIT: the v4 contract carries no city-wide distinct-merchant count and additionalProperties
    // is false, so it cannot be added. M.CITY is exempted from the merchant gate in M.sourceOf
    // instead of being given an invented count, and the panel never prints a city merchant total.
    M.CITY.m.GASTRO = 0; M.CITY._ci = null; M.CITY._gate = true;
  };

  const D = () => M.data;
  /* Contract indexing: (ci * days + di) * hours + h. Index 0 is the EXCLUDED bucket
     (null postcode, foreign postcode, and the '000000' sentinel-timecode rows) — defect D2:
     it is never part of a per-area or city hourly curve, only of the row total. */
  const cellsOf = (u) => { if (u._ci && u._ciV === M.dataVersion) return u._ci; const d = D(), arr = []; for (const c of u.codes) { const i = d.codeIdx.get(c); if (i != null && i !== 0) arr.push(i); } u._ci = arr; u._ciV = M.dataVersion; return arr; };
  const dDay = (k) => M.daysBetween(D().start, k), inRange = (di) => di >= 0 && di < D().days;
  function act(u, di, H) { const d = D(), sc = d.amtScale || 1; let c = 0, a = 0; for (const ci of cellsOf(u)) { const p = (ci * d.days + di) * 24 + H; c += d.cnt[p]; a += d.amt[p] * sc; } return [c, a]; }

  /* D1 — baseline is the mean of the SAME WEEKDAY over the trailing 4 weeks, not the mean of all
     days. With a flat 30-day mean a no-event Saturday reads +75% (research/app-forensics.md §7.2);
     the measured weekday indices are 1.514 (Sat) and 0.724 (Mon). */
  function avg(u, di, H) {
    const key = u.key + '|' + di + '|' + H;
    const hit = M._dm.get(key); if (hit) return hit;
    const d = D(), dow = (dayOfWeek(d.start) + di) % 7;
    let c = 0, a = 0, n = 0;
    for (let w = 1; w <= 4; w++) {
      const dd = di - 7 * w;
      if (!inRange(dd)) continue;
      if ((dayOfWeek(d.start) + dd) % 7 !== dow) continue;      // guard: never average a different weekday
      n++; const r = act(u, dd, H); c += r[0]; a += r[1];
    }
    const v = n ? [c / n, a / n, n] : [0, 0, 0];
    M._dm.set(key, v); return v;
  }
  M.baselineWeeks = 4;
  const at = (fn, u, k, H) => { let di = dDay(k); if (H >= 24) { di++; H -= 24; } return inRange(di) ? fn(u, di, H) : [0, 0, 0]; };

  /* Privacy cascade. A unit is readable only if it passes the aggregate's own gates (G1 >= 30
     cards, G2 >= 3 merchants, G3 top-1 share <= 75% — contracts/privacy.py, mirrored in codeMeta).
     A parent unit inherits readability from a gated child and needs >= 3 merchants in total. */
  M.gatesOf = function (u) {
    const d = D(); if (!d) return null;
    if (!u) return { g1_cards: false, g2_merchants: false, g3_share: false, all: false, unknown: true };
    if (u.level === 'city') return d.gates.filter((g) => g && g.all).length ? { g1_cards: null, g2_merchants: true, g3_share: null, all: true, aggregate: true } : { g1_cards: false, g2_merchants: false, g3_share: false, all: false };
    if (u.level === 'code') { const i = d.codeIdx.get(u.key); return i == null ? { all: false } : d.gates[i]; }
    if (u._gate && u._gateV === M.dataVersion) return u._gate;
    let anyGated = false;
    for (const pc of u.codes) { const i = d.codeIdx.get(pc); if (i != null && d.gates[i] && d.gates[i].all) anyGated = true; }
    const g = { g1_cards: null, g2_merchants: (u.m.GASTRO || 0) >= 3, g3_share: null, all: anyGated && (u.m.GASTRO || 0) >= 3, aggregate: true };
    u._gate = g; u._gateV = M.dataVersion; return g;
  };
  M.readable = (u) => { const g = M.gatesOf(u); return !!(g && g.all); };
  M.gateLine = function (u) { const g = M.gatesOf(u); if (!g) return ''; if (g.all) return ''; const miss = []; if (g.g1_cards === false) miss.push('mniej niż 30 kart'); if (g.g2_merchants === false) miss.push('mniej niż 3 podmioty'); if (g.g3_share === false) miss.push('jeden podmiot powyżej 75% udziału'); return miss.length ? miss.join(' · ') : 'obszar bez danych'; };
  M.sourceOf = function (u) { let x = u; while (x && !M.readable(x)) { const pl = parentLevel[x.level]; x = pl ? UL[pl].get(keyAt[pl]([...u.codes][0])) : null; } return x; };
  const share = (x, u) => x === u ? 1 : 1 / Math.max(1, x.codes.size);

  M.sum = function (units, k, H, c) {
    let av = 0, pred = 0, amt = 0, avgAmt = 0, n = 0;
    for (const u of units) {
      const x = M.sourceOf(u); if (!x) continue;
      n++; const f = share(x, u), a = at(act, x, k, H), v = at(avg, x, k, H);
      pred += a[0] * f; amt += a[1] * f; av += v[0] * f; avgAmt += v[1] * f;
    }
    return { avg: av, pred, amt, avgAmt, n };
  };
  const interp = (fn, x, k, t, idx) => { const H = Math.floor(t) % 24, fr = t - Math.floor(t); return at(fn, x, k, H)[idx] * (1 - fr) + at(fn, x, k, H + 1)[idx] * fr; };
  M.avgCount = function (u, k, H, c) { const x = M.sourceOf(u); if (!x || !k) return null; return at(avg, x, k, H)[0] * share(x, u); };
  M.predCount = function (u, k, t, c) { const x = M.sourceOf(u); if (!x) return null; return interp(act, x, k, t, 0) * share(x, u); };
  M.amountAt = function (u, k, t, c) { const x = M.sourceOf(u); if (!x) return null; return interp(act, x, k, t, 1) * share(x, u); };
  // "wpływ wydarzenia" = how much more the area moved vs its weekday-matched baseline than the whole city did, in points
  M.uplift = function (z, k, h, c) { const u = M.unitOf(z.key), x = u ? M.sourceOf(u) : null; if (!x) return 0; const r = (y) => { const a = at(act, y, k, h)[0], v = at(avg, y, k, h)[0]; return v > 1e-9 ? a / v - 1 : 0; }; return (r(x) - r(M.CITY)) * 100; };

  /* D4 — a thin cell used to draw a healthy curve and print nothing (research/evidence/
     16-full-best-81-718-1930.png). The reading now escalates code → fives → tens → the whole city
     and, once it reaches the city, is printed with an explicit Poisson confidence band instead of
     being withheld. It is never withheld. */
  const THIN = (M.THIN = 12); // minimum weekday-matched base (transactions in the 3-hour window)
  const win3 = (unit, k, H) => { let a = 0, am = 0, v = 0, va = 0; for (const d of [-1, 0, 1]) { let kk = k, h = H + d; if (h < 0) { kk = M.addDays(k, -1); h += 24; } else if (h >= 24) { kk = M.addDays(k, 1); h -= 24; } const r = at(act, unit, kk, h), q = at(avg, unit, kk, h); a += r[0]; am += r[1]; v += q[0]; va += q[1]; } return { a, am, v, va }; };
  const winStats = (M.winStats = function (u, k, H, c) {
    let x = M.sourceOf(u); if (!x) return null;
    let s = win3(x, k, H), hops = 0;
    while (s.v < THIN) { const pl = parentLevel[x.level], p = pl ? UL[pl].get(keyAt[pl]([...x.codes][0])) : null; if (!p) break; x = p; s = win3(x, k, H); hops++; }
    let escalatedToCity = false;
    if (s.v < THIN) { x = M.CITY; s = win3(x, k, H); escalatedToCity = true; }
    const cs = win3(M.CITY, k, H), rel = s.v > 0 ? s.a / s.v - 1 : 0, cityRel = cs.v > 0 ? cs.a / cs.v - 1 : 0, damp = Math.min(1, s.v / 30);
    // relative standard error of a Poisson count, plus a floor so a 3-transaction base cannot print ±100%
    const se = s.v > 0 ? Math.min(1.5, 1.96 / Math.sqrt(s.v)) : null;
    return {
      thin: false, unit: x, hops, escalatedToCity, n: 1, rel, pred: s.a / 3, avg: s.v / 3, amt: s.am / 3, avgAmt: s.va / 3, base: s.v,
      band: se == null ? null : { lo: rel - se, hi: rel + se },
      force: Math.max(-100, Math.min(100, (rel - cityRel) * 100 * damp)),
    };
  });
  M.venueStats = winStats;
  M.beachShare = function (hours) { const beach = [...UL.code.values()].filter((u) => u.beach >= 0.3); let bn = 0, bb = 0, an = 0, ab = 0; for (const h of hours) { for (const u of beach) { bn += at(act, u, h.k, h.H)[0]; bb += at(avg, u, h.k, h.H)[0]; } an += at(act, M.CITY, h.k, h.H)[0]; ab += at(avg, M.CITY, h.k, h.H)[0]; } return { now: an ? bn / an : 0, base: ab ? bb / ab : 0 }; };
  // Whole-city scope is ONE unit (the sum of every real postcode cell, index 0 excluded), not a sum
  // of districts: summing districts dropped the tens groups that fall below the privacy gate and
  // made the city total drift from the row total.
  M.compared = focusKey => { const f = M.unitOf(focusKey); return f ? [f] : [M.CITY]; };
  // busiest group among the units compared at the current level (by volume at day k, hour t)
  M.hottest = function (focusKey, k, t, c) { const f = M.unitOf(focusKey); if (f && f.level === 'code') return null; const H = Math.floor(t) % 24; let best = null, bv = -1, tot = 0; for (const g of M.childrenOf(f)) { const v = M.sum([g], k, H, c).pred; tot += v; if (v > bv) { bv = v; best = g; } } return best && bv > 0 ? { unit: best, share: tot ? bv / tot : 0, pred: bv } : null; };
  M.relAt = function (u, k, t, c) { const s = winStats(u, k, Math.floor(t) % 24, c); return s ? s.rel : null; };
  M.valueOf = function (u, k, h, c) { const s = winStats(u, k, h, c); if (!s) return { v: null, src: 'hidden' }; return { v: Math.round(s.rel * 100), r: s.rel, src: s.unit === u ? 'own' : 'parent', from: s.unit, band: s.band }; };

  M.eventUpliftComputed = function (e, c) { const { s, en } = M.eventWindow(e); let p = 0, a = 0; for (let h = Math.max(0, s - 1); h <= en; h++) { const k = h < 24 ? e.date : M.addDays(e.date, 1), H = h % 24, x = at(act, M.CITY, k, H), v = at(avg, M.CITY, k, H); p += x[0]; a += v[0]; } return a ? p / a - 1 : 0; };
  M.eventUplift = (e, c) => Math.round(M.eventUpliftComputed(e, c) * 100);
  M.eventsFor = function (c, threshold) { if (c.lv !== 'mcc') return []; return M.EVENTS.filter((e) => M.eventUplift(e, c) >= threshold); };

  const NATS = [['PL', 'Polska'], ['DE', 'Niemcy'], ['SE', 'Szwecja'], ['NO', 'Norwegia'], ['GB', 'Wielka Brytania'], ['inne', 'inne kraje']];
  M.eventSummary = function (e, day, c, scope) {
    const d = D(); if (!d) return null;
    const hours = [];
    if (e) { const { s, en } = M.eventWindow(e), k0 = M.onDay(e, day) ? day : e.date; for (let h = Math.max(0, s - 1); h <= en; h++) hours.push({ k: h < 24 ? k0 : M.addDays(k0, 1), H: h % 24 }); }
    else for (let h = 0; h < 24; h++) hours.push({ k: day, H: h });
    // the scope never silently becomes the city: if the requested area is not readable we say so
    let S = M.CITY, scopeNote = null;
    // `scope` may arrive as a unit object (the panel resolves it) or as a postcode-hierarchy key.
    if (scope) { const u = (typeof scope === 'string') ? M.unitOf(scope) : scope; if (M.readable(u)) S = u; else { const reason = M.gateLine(u) || 'obszar bez danych'; return { blocked: true, reason, requested: u ? u.key : String(scope) }; } }
    let count = 0, av = 0, amount = 0, avgAmount = 0, peak = null; const natNow = [0, 0, 0, 0, 0, 0], natBase = [0, 0, 0, 0, 0, 0];
    for (const h of hours) {
      const a = at(act, S, h.k, h.H), v = at(avg, S, h.k, h.H);
      count += a[0]; av += v[0]; amount += a[1]; avgAmount += v[1];
      if (!peak || a[0] > peak.pred) peak = { H: h.H, pred: a[0], amt: a[1], k: h.k };
      const di = dDay(h.k);
      if (inRange(di)) { for (let b = 0; b < 6; b++) natNow[b] += d.nat[(di * 24 + h.H) * 6 + b]; for (let w = 1; w <= 4; w++) { const dd = di - 7 * w; if (!inRange(dd)) continue; for (let b = 0; b < 6; b++) natBase[b] += d.nat[(dd * 24 + h.H) * 6 + b]; } }
    }
    const tens = [...UL.tens.values()]; let hotUnit = null, hotV = -1, hotTotal = 0;
    for (const u of tens) { let v = 0; for (const h of hours) v += at(act, u, h.k, h.H)[0]; hotTotal += v; if (v > hotV) { hotV = v; hotUnit = u; } }
    const bs = M.beachShare(hours);
    const tot = natNow.reduce((x, y) => x + y, 0) || 1, totB = natBase.reduce((x, y) => x + y, 0) || 1;
    const nat = NATS.map(([code, name], i) => { const sh = Math.round(natNow[i] / tot * 100), base = Math.round(natBase[i] / totB * 100); return { code, name, share: sh, base, delta: sh - base }; });
    const days = [-1, 0, 1].map((n) => { const k = M.addDays(day, n); let p = 0, a = 0, am = 0, aa = 0; for (let H = 0; H < 24; H++) { const x = at(act, S, k, H), v = at(avg, S, k, H); p += x[0]; a += v[0]; am += x[1]; aa += v[1]; } return { n, k, pred: p, avg: a, amt: am, avgAmt: aa }; });
    return { scope: S, scopeNote, hours: hours.length, count, avg: av, amount, avgAmount, ticket: count ? amount / count : 0, avgTicket: av ? avgAmount / av : 0, uplift: av ? count / av - 1 : 0, days, hot: hotUnit && hotV > 0 ? { unit: hotUnit, share: hotTotal ? hotV / hotTotal : 0 } : null, peak, nat, foreign: 100 - nat[0].share, foreignBase: 100 - nat[0].base, beachShare: bs.now, beachBase: bs.base };
  };

  // ---------- data that ships with the app: sectors, premises, postcode meta, weather, sea distance
  M.ready = Promise.all(['data/sopot-sectors.geojson', 'data/sopot-premises.geojson', 'data/sopot-codes.json', 'data/sopot-weather-2026.json', 'data/sea-km.json']
    .map((u) => fetch(u).then((r) => { if (!r.ok) throw new Error(u); return r.json(); })))
    .then(([s, p, meta, w, sea]) => { M.weather = w; M.build(s.features, p.features, meta, Object.fromEntries(Object.entries(sea.codes || {}).map(([k, v]) => [k, v.sea_km]))); M.loaded = true; return M; });
})();
