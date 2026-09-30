/* aggregate-loader.js — the ONLY data source of the panel. Replaces sopot-data.js.
 *
 * Reads ../artifacts/aggregate.json (contracts/AGGREGATE.md, v4), validates it inline against
 * contracts/aggregate.schema.json (no npm dependencies), decodes the three base64 payloads into
 * typed arrays with the contract's exact indexing, and exposes a window.SopotData surface that
 * app/sopot-model.js already knows how to consume.
 *
 * Hard rules this file exists to enforce:
 *   - ver must be 5. Any other version is refused.
 *   - Any validation or decode failure sets status='error' and publishes the reason.
 *   - There is NO simulated fallback: no parquet fetch, no browser-side decompression, no
 *     IndexedDB cache. If the file is missing or wrong the panel shows an error, never a number.
 */
(function () {
  if (window.SopotData && window.SopotData.ver === 5) return;   // helmet scripts may run twice
  const ENDPOINT = '../artifacts/aggregate.json';
  // The pipeline agent owns artifacts/aggregate.json. Until it lands, tools/make_fixture_aggregate.py
  // writes artifacts/aggregate.fixture.json with the same contract and obviously invented numbers.
  // Falling back to it is LOUD, never silent: SD.usingFixture is set, the panel prints
  // "Dane testowe (fixture)" instead of "Dane rzeczywiste", and a banner explains why.
  const FIXTURE = '../artifacts/aggregate.fixture.json';
  const OVERRIDE = new URLSearchParams(location.search).get('agg');   // ?agg=… for the gate
  const CONTRACT = 5;

  const SD = (window.SopotData = {
    ver: CONTRACT,
    endpoint: ENDPOINT,
    status: 'idle',          // idle | loading | ready | error
    progress: '',
    agg: null,
    error: null,
    notes: [],
    presets: [],
    listeners: new Set(),
    onChange(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); },
  });
  const emit = () => SD.listeners.forEach((fn) => { try { fn(SD); } catch (e) { /* a listener must not break the load */ } });
  const set = (status, progress) => { SD.status = status; SD.progress = progress || ''; emit(); };
  SD.timing = { start: performance.now(), fetched: null, parsed: null, decoded: null };

  // ---------------------------------------------------------------- validation
  const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
  const isStr = (v) => typeof v === 'string';
  const isInt = (v) => Number.isInteger(v);
  const isNum = (v) => typeof v === 'number' && isFinite(v);
  const isBool = (v) => typeof v === 'boolean';
  const DATE = /^\d{4}-\d{2}-\d{2}$/;
  const CONFIDENCE = ['observed', 'inferred', 'extrapolated', 'none'];

  const TOP_KEYS = ['ver', 'generated', 'source', 'start', 'days', 'hours', 'codes', 'codeMeta',
                    'cityCnt', 'cityAmt', 'cityAmtScale', 'released',
    'cnt', 'amt', 'amtScale', 'nat', 'eventsByDay', 'rows', 'excluded', 'presets'];

  /* Mirrors contracts/aggregate.schema.json. Returns a list of human-readable violations. */
  function validate(o) {
    const bad = [];
    if (!isObj(o)) return ['root is not a JSON object'];
    for (const k of TOP_KEYS) if (!(k in o)) bad.push(`missing required key "${k}"`);
    for (const k of Object.keys(o)) if (!TOP_KEYS.includes(k)) bad.push(`unexpected key "${k}" (schema sets additionalProperties:false)`);
    if (o.ver !== CONTRACT) bad.push(`ver is ${JSON.stringify(o.ver)}, the app only reads ver ${CONTRACT}`);
    if (!isStr(o.generated)) bad.push('generated must be a string');
    if (!isObj(o.source)) bad.push('source must be an object');
    else {
      for (const k of ['files', 'sha256', 'rule_version']) if (!(k in o.source)) bad.push(`source.${k} is missing`);
      if (o.source.files && (!Array.isArray(o.source.files) || !o.source.files.length || !o.source.files.every(isStr))) bad.push('source.files must be a non-empty array of strings');
      if (o.source.sha256 && !(Array.isArray(o.source.sha256) && o.source.sha256.every(isStr))) bad.push('source.sha256 must be an array of strings');
      if (o.source.rule_version != null && !isStr(o.source.rule_version)) bad.push('source.rule_version must be a string');
    }
    if (!isStr(o.start) || !DATE.test(o.start)) bad.push('start must be YYYY-MM-DD');
    if (!isInt(o.days) || o.days < 1) bad.push('days must be an integer >= 1');
    if (o.hours !== 24) bad.push(`hours is ${JSON.stringify(o.hours)}, the contract fixes it at 24`);
    if (!Array.isArray(o.codes) || !o.codes.length || !o.codes.every(isStr)) bad.push('codes must be a non-empty array of strings');
    if (!isObj(o.codeMeta)) bad.push('codeMeta must be an object');
    if (!isStr(o.cnt) || !isStr(o.amt) || !isStr(o.nat)) bad.push('cnt, amt and nat must be base64 strings');
    if (!isStr(o.cityCnt) || !isStr(o.cityAmt)) bad.push('cityCnt and cityAmt must be base64 strings');
    if (!isNum(o.cityAmtScale) || o.cityAmtScale <= 0) bad.push('cityAmtScale must be a number > 0');
    if (!isObj(o.released) || !isInt(o.released.codes) || !isInt(o.released.suppressed)
        || !isInt(o.released.suppressedVolume)) {
      bad.push('released must carry integer codes, suppressed and suppressedVolume');
    }
    if (!isNum(o.amtScale) || o.amtScale <= 0) bad.push('amtScale must be a number > 0');
    if (!isInt(o.rows) || o.rows < 0) bad.push('rows must be an integer >= 0');
    if (!isObj(o.eventsByDay)) bad.push('eventsByDay must be an object');
    else for (const [k, v] of Object.entries(o.eventsByDay)) {
      if (!Array.isArray(v) || !v.every(isStr)) { bad.push(`eventsByDay["${k}"] must be an array of strings`); break; }
    }
    if (!isObj(o.excluded)) bad.push('excluded must be an object');
    else for (const k of ['zeroTimecode', 'nonSopotPostcode', 'noPostcode']) {
      if (!isInt(o.excluded[k]) || o.excluded[k] < 0) bad.push(`excluded.${k} must be an integer >= 0`);
    }
    if (!Array.isArray(o.presets) || !o.presets.length) bad.push('presets must be a non-empty array');
    if (bad.length) return bad;

    // codeMeta — every code except index 0 must have an entry (contract invariant 7)
    for (let i = 1; i < o.codes.length; i++) {
      const c = o.codes[i], m = o.codeMeta[c];
      if (!m) { bad.push(`codeMeta["${c}"] is missing (contract invariant 7)`); continue; }
      if (!isStr(m.name)) bad.push(`codeMeta["${c}"].name must be a string`);
      // A SUPPRESSED cell carries no counts by design — the release gate strips them, because
      // "81-814: 1 transakcja, 1 karta, 1 podmiot" is the identification the rule forbids. The
      // contract therefore requires the stats only when gates.all is true, and requires their
      // ABSENCE when it is false: counts appearing on a suppressed cell is a contract violation,
      // not a nicety, and the loader refuses the whole file if it sees one.
      const suppressed = m.gates && m.gates.all === false;
      const statKeys = ['merchants', 'transactions', 'nCards', 'top1Share'];
      const present = statKeys.filter((k) => m[k] != null);
      if (suppressed && present.length) {
        bad.push(`codeMeta["${c}"] is suppressed but still carries ${present.join(', ')} — the release gate must strip these`);
      }
      if (!suppressed) {
        if (!isInt(m.merchants) || m.merchants < 0) bad.push(`codeMeta["${c}"].merchants must be an integer >= 0`);
        if (!isInt(m.transactions) || m.transactions < 0) bad.push(`codeMeta["${c}"].transactions must be an integer >= 0`);
      }
      if (!CONFIDENCE.includes(m.polygonConfidence)) bad.push(`codeMeta["${c}"].polygonConfidence must be one of ${CONFIDENCE.join('|')}`);
      if (m.centroid != null && !(Array.isArray(m.centroid) && m.centroid.length === 2 && m.centroid.every(isNum))) bad.push(`codeMeta["${c}"].centroid must be [lat, lng]`);
      if (m.nCards != null && (!isInt(m.nCards) || m.nCards < 0)) bad.push(`codeMeta["${c}"].nCards must be an integer >= 0`);
      if (m.top1Share != null && !(isNum(m.top1Share) && m.top1Share >= 0 && m.top1Share <= 1)) bad.push(`codeMeta["${c}"].top1Share must be within [0,1]`);
      const g = m.gates;
      if (!isObj(g)) bad.push(`codeMeta["${c}"].gates is missing`);
      else for (const k of ['g1_cards', 'g2_merchants', 'g3_share', 'all']) if (!isBool(g[k])) bad.push(`codeMeta["${c}"].gates.${k} must be a boolean`);
    }
    for (const p of o.presets) {
      if (!isObj(p)) { bad.push('every preset must be an object'); continue; }
      for (const k of ['id', 'code', 'name']) if (!isStr(p[k])) bad.push(`preset.${k} must be a string`);
      if (!isNum(p.lat) || !isNum(p.lng)) bad.push(`preset "${p.id}" needs numeric lat/lng`);
      if (isStr(p.code) && !o.codes.includes(p.code)) bad.push(`preset "${p.id}" points at code ${p.code}, which is not in codes[]`);
      if (isStr(p.code) && o.codeMeta[p.code] && o.codeMeta[p.code].gates && o.codeMeta[p.code].gates.all !== true) {
        bad.push(`preset "${p.id}" (${p.code}) does not pass all privacy gates (contract invariant 8)`);
      }
    }
    return bad;
  }

  // ---------------------------------------------------------------- decoding
  function b64ToBytes(s) {
    const bin = atob(s);
    const n = bin.length, out = new Uint8Array(n);
    for (let i = 0; i < n; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  const view16 = (bytes) => new Uint16Array(bytes.slice().buffer);   // slice() → offset 0, aligned
  const view32 = (bytes) => new Uint32Array(bytes.slice().buffer);
  const sum = (a) => { let s = 0; for (let i = 0; i < a.length; i++) s += a[i]; return s; };
  function swap16(a) { const out = new Uint16Array(a.length); for (let i = 0; i < a.length; i++) { const v = a[i]; out[i] = ((v & 255) << 8) | (v >> 8); } return out; }
  function swap32(a) { const out = new Uint32Array(a.length); for (let i = 0; i < a.length; i++) { const v = a[i]; out[i] = ((v & 255) << 24) | (((v >> 8) & 255) << 16) | (((v >> 16) & 255) << 8) | ((v >>> 24) & 255); } return out; }

  const iso = (d) => `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
  function addDaysUTC(k, n) { const d = new Date(k + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return iso(d); }

  // ---------------------------------------------------------------- load
  SD.load = function () {
    if (SD.agg) return Promise.resolve(SD.agg);
    if (SD._p) return SD._p;
    SD._p = (async () => {
      try {
        set('loading', 'Wczytywanie danych kartowych…');
        const tried = [];
        let res = null, url = OVERRIDE || ENDPOINT;
        res = await fetch(url, { cache: 'no-cache' });
        tried.push(`${url} → HTTP ${res.status}`);
        // NO FIXTURE FALLBACK ON THE SHIPPED PATH.
        //
        // This used to fall back to artifacts/aggregate.fixture.json, which paints invented
        // numbers under a loud "Dane testowe (fixture)" banner. The banner was honest and the
        // decision was still wrong: the panel is a municipal service, and a service that shows a
        // restaurateur a number it made up — even labelled — has done the thing this whole
        // artifact exists to prevent. An adversarial pass demonstrated it by renaming the real
        // aggregate and watching the panel render a full, confident, fabricated dashboard.
        //
        // The fixture remains available for development, but only by asking for it explicitly
        // with ?agg=…, which is a developer action, not a silent fallback.
        if (!res.ok) throw new Error(`nie można wczytać danych (${tried.join('; ')})`);
        SD.endpoint = url;
        const text = await res.text();
        SD.timing.fetched = performance.now();
        SD.bytes = text.length;
        set('loading', 'Sprawdzanie zgodności z kontraktem aggregate.json v4…');
        let raw;
        try { raw = JSON.parse(text); }
        catch (e) { throw new Error(`${SD.endpoint} nie jest poprawnym JSON-em: ${e.message}`); }
        SD.timing.parsed = performance.now();

        const bad = validate(raw);
        if (bad.length) {
          SD.violations = bad;
          throw new Error(`aggregate.json v${CONTRACT} odrzucony — ${bad.length} ${bad.length === 1 ? 'naruszenie' : 'naruszeń'} kontraktu: ${bad.slice(0, 4).join('; ')}${bad.length > 4 ? ' …' : ''}`);
        }

        set('loading', 'Kodowanie godzin i obszarów…');
        const codes = raw.codes.slice();
        const days = raw.days, hours = 24;
        const nCells = codes.length * days * hours;

        const cntBytes = b64ToBytes(raw.cnt), amtBytes = b64ToBytes(raw.amt), natBytes = b64ToBytes(raw.nat);
        if (cntBytes.byteLength !== nCells * 2) throw new Error(`cnt ma ${cntBytes.byteLength} B, kontrakt wymaga ${nCells * 2} B (codes ${codes.length} × days ${days} × 24 × 2)`);
        if (amtBytes.byteLength !== nCells * 2) throw new Error(`amt ma ${amtBytes.byteLength} B, kontrakt wymaga ${nCells * 2} B`);
        if (natBytes.byteLength !== days * hours * 6 * 4) throw new Error(`nat ma ${natBytes.byteLength} B, kontrakt wymaga ${days * hours * 6 * 4} B`);

        let cnt = view16(cntBytes), amt = view16(amtBytes), nat = view32(natBytes);
        // Endianness is not in the contract; pick the byte order under which the counts are plausible.
        // Invariant 1 (sum(cnt) == rows) is asserted by the pipeline, so a wrong byte order is obvious.
        const sumLE = sum(cnt);
        let order = 'LE';
        if (Math.abs(sumLE - raw.rows) > raw.rows * 0.35) {
          const sumBE = sum(swap16(cnt));
          if (Math.abs(sumBE - raw.rows) < Math.abs(sumLE - raw.rows)) { cnt = swap16(cnt); amt = swap16(amt); nat = swap32(nat); order = 'BE'; }
        }
        const sumCnt = sum(cnt);
        SD.timing.decoded = performance.now();

        if (sumCnt !== raw.rows) {
          const gap = raw.rows - sumCnt;
          if (Math.abs(gap) > raw.rows * 0.35) {
            throw new Error(`suma cnt (${sumCnt.toLocaleString('pl-PL')}) nie zgadza się z rows (${raw.rows.toLocaleString('pl-PL')}) — odczyt binarny jest błędny, panel nie pokaże liczb`);
          }
          SD.notes.push(`sum(cnt) = ${sumCnt.toLocaleString('pl-PL')}, rows = ${raw.rows.toLocaleString('pl-PL')} (${gap > 0 ? '−' : '+'}${Math.abs(gap).toLocaleString('pl-PL')}): wiersze wyłączone z sześcianu godzinowego (contracts/AGGREGATE.md §„What the app must do”).`);
        }

        // merchants per code, parallel to codes[]; index 0 is the EXCLUDED bucket and has no codeMeta
        const merchants = codes.map((c, i) => (i === 0 ? 0 : (raw.codeMeta[c] ? raw.codeMeta[c].merchants : 0)));
        const gates = codes.map((c, i) => (i === 0 ? { g1_cards: false, g2_merchants: false, g3_share: false, all: false } : (raw.codeMeta[c] || {}).gates || null));

        const agg = {
          ver: raw.ver, generated: raw.generated, source: raw.source,
          start: raw.start, days, hours, codes, codeMeta: raw.codeMeta,
          codeIdx: new Map(codes.map((c, i) => [c, i])),
          cnt, amt, amtScale: raw.amtScale, nat,
          merchants, gates,
          rows: raw.rows, sumCnt, byteOrder: order,
          excluded: raw.excluded,
          eventsByDay: raw.eventsByDay,
          presets: raw.presets,
          range: [raw.start, addDaysUTC(raw.start, days - 1)],
          isFixture: /fixture|synthetic|test/i.test((raw.source && raw.source.rule_version) || '') ||
                     /fixture/i.test(((raw.source && raw.source.files) || []).join(' ')),
          // LIMIT: the v4 contract has no city-wide distinct-merchant count (additionalProperties:false
          // forbids adding one). The panel therefore never prints a city merchant total; it prints the
          // largest gated area's count instead. See app/sopot-model.js M.useData.
          cityMerchants: null,
        };
        agg.maxMerchants = merchants.reduce((a, b) => Math.max(a, b), 0);
        agg.gatedCodes = gates.filter((g) => g && g.all).length;
        agg.zeroTimecodeShare = raw.rows ? raw.excluded.zeroTimecode / raw.rows : 0;

        SD.agg = agg;
        SD.presets = agg.presets.slice();
        SD.usingFixture = !!agg.isFixture;
        SD.notes.push(...(agg.isFixture
          ? ['FIXTURE: te liczby pochodzą z tools/make_fixture_aggregate.py, nie z parquetu. Kontrakt i ścieżka kodu są prawdziwe, dane nie.']
          : []));
        console.info(`[SopotData] ${agg.isFixture ? 'FIXTURE' : 'aggregate'} v${agg.ver}: ${agg.rows.toLocaleString('pl-PL')} wierszy, ${agg.codes.length - 1} kodów, ${agg.gatedCodes} obszarów po wszystkich bramkach, ${(SD.bytes / 1048576).toFixed(2)} MB, ${Math.round(SD.timing.decoded)} ms`);
        set('ready', `${agg.rows.toLocaleString('pl-PL')} transakcji`);
        return agg;
      } catch (err) {
        SD.error = err;
        SD.agg = null;
        console.error('[SopotData]', err);
        set('error', err && err.message ? err.message : String(err));
        throw err;
      }
    })();
    return SD._p;
  };

  // Programmatic re-check used by tools/demo_ready.mjs
  SD.validateOnly = async function (url) {
    const res = await fetch(url || SD.endpoint, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const bad = validate(await res.json());
    return bad;
  };
})();
