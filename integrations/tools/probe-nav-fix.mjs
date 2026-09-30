/**
 * Sweep viewport widths and test candidate CSS fixes for the eighth nav item.
 *
 * Injects each candidate rule into the live page, re-measures, and reports the
 * slack between the nav's content box and the sum of its items.  Nothing is
 * written here — the winning rule is baked into
 * integrations/municipal-site/assets/mock/strona-biznesu.css by hand.
 *
 * Usage: node integrations/tools/cdp.mjs integrations/tools/probe-nav-fix.mjs
 */
const BASE = process.env.SB_BASE || "http://127.0.0.1:8097/integrations/municipal-site/";

const CANDIDATES = [
  ["as-is", ""],
  ["C1 drop .main-menu side padding", "@media (min-width:992px) and (max-width:1399px){.main-menu{padding-left:0!important;padding-right:0!important}}"],
  ["C2 margin-right 8px", "@media (min-width:992px) and (max-width:1399px){.main-menu ul li{margin-right:8px}}"],
  ["C3 both", "@media (min-width:992px) and (max-width:1399px){.main-menu{padding-left:0!important;padding-right:0!important}.main-menu ul li{margin-right:12px}}"],
];

const MEASURE = () => {
  const ul = document.querySelector("header .main-menu nav#mobile-menu > ul");
  if (!ul) return { error: "nav ul not found" };
  const items = [...ul.children].filter((el) => el.tagName === "LI");
  let wraps = false;
  let wrapAt = null;
  let prevLeft = -Infinity;
  for (const li of items) {
    const r = li.getBoundingClientRect();
    if (r.left < prevLeft - 1) { wraps = true; wrapAt = wrapAt || li.id; }
    prevLeft = r.left;
  }
  const menu = ul.closest(".main-menu");
  const cs = getComputedStyle(menu);
  const avail = menu.getBoundingClientRect().width -
    parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
  const mr = parseFloat(getComputedStyle(items[0]).marginRight);
  const sum = items.reduce((a, li) => a + li.getBoundingClientRect().width, 0);
  return {
    items: items.length,
    wraps,
    wrapAt,
    avail: Math.round(avail * 100) / 100,
    need: Math.round((sum + mr * items.length) * 100) / 100,
    slack: Math.round((avail - (sum + mr * items.length)) * 100) / 100,
  };
};

const WIDTHS = [992, 1024, 1100, 1150, 1199, 1200, 1232, 1280, 1300, 1366, 1399, 1400, 1440, 1600, 1920];

export default async function (page) {
  const results = {};
  await page.setViewport(1280, 800);
  await page.goto(BASE, { waitMs: 2200 });
  await page.settle({ extraMs: 900 });

  for (const [name, css] of CANDIDATES) {
    results[name] = {};
    for (const w of WIDTHS) {
      await page.setViewport(w, 900);
      await page.evaluate((c) => {
        const old = document.getElementById("candidate");
        if (old) old.remove();
        if (c) {
          const s = document.createElement("style");
          s.id = "candidate";
          s.textContent = c;
          document.head.appendChild(s);
        }
        void document.body.offsetHeight;
      }, css);
      await new Promise((r) => setTimeout(r, 250));
      results[name][w] = await page.evaluate(MEASURE);
    }
  }

  const pad = (s, n) => String(s).padEnd(n);
  for (const [name] of CANDIDATES) {
    console.log(`\n=== ${name} ===`);
    console.log(pad("width", 8) + pad("items", 7) + pad("wraps", 7) + pad("avail", 10) + pad("need", 10) + "slack");
    for (const w of WIDTHS) {
      const r = results[name][w];
      if (r.error) { console.log(pad(w, 8) + r.error); continue; }
      console.log(
        pad(w, 8) + pad(r.items, 7) + pad(r.wraps ? "YES:" + r.wrapAt : "no", 7) +
        pad(r.avail, 10) + pad(r.need, 10) + r.slack,
      );
    }
  }
}
