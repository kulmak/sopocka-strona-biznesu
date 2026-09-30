/**
 * Compare the primary nav of the pristine replica against the integrated copy,
 * with and without the eighth item, across the breakpoints that matter.
 *
 * Usage: node integrations/tools/cdp.mjs integrations/tools/probe-nav-baseline.mjs
 */
const SOURCE = process.env.SB_SOURCE || "http://127.0.0.1:8099/";
const INTEG = process.env.SB_BASE || "http://127.0.0.1:8097/integrations/municipal-site/";

const MEASURE = () => {
  const ul = document.querySelector("header .main-menu nav#mobile-menu > ul");
  if (!ul) return { error: "nav ul not found" };
  const items = [...ul.children].filter((el) => el.tagName === "LI");
  let wraps = false;
  let wrapAt = null;
  let prevLeft = -Infinity;
  const rows = [];
  for (const li of items) {
    const r = li.getBoundingClientRect();
    if (r.left < prevLeft - 1) {
      wraps = true;
      if (!wrapAt) wrapAt = li.id;
    }
    prevLeft = r.left;
    rows.push({
      id: li.id,
      label: (li.querySelector("a") || {}).textContent?.trim() ?? "",
      w: Math.round(r.width * 10) / 10,
      left: Math.round(r.left * 10) / 10,
      top: Math.round(r.top * 10) / 10,
      mr: getComputedStyle(li).marginRight,
      ml: getComputedStyle(li).marginLeft,
    });
  }
  const menu = ul.closest(".main-menu");
  const menuRect = menu.getBoundingClientRect();
  const padding = getComputedStyle(menu);
  const last = items[items.length - 1].getBoundingClientRect();
  return {
    items: items.length,
    wraps,
    wrapAt,
    font: getComputedStyle(ul.querySelector("a")).fontSize,
    itemMarginRight: getComputedStyle(items[0]).marginRight,
    menuPadding: `${padding.paddingLeft}/${padding.paddingRight}`,
    menuWidth: Math.round(menuRect.width * 10) / 10,
    navWidth: Math.round(ul.parentElement.getBoundingClientRect().width * 10) / 10,
    sumWidths: Math.round(items.reduce((a, li) => a + li.getBoundingClientRect().width, 0) * 10) / 10,
    lastRight: Math.round(last.right * 10) / 10,
    rows,
  };
};

export default async function (page) {
  const out = {};
  for (const [name, base] of [["source-7-items", SOURCE], ["integrated-8-items", INTEG]]) {
    for (const [w, h] of [[1280, 800], [1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewport(w, h);
      await page.goto(base, { waitMs: 2000 });
      await page.settle({ extraMs: 900 });
      out[`${name} @${w}`] = await page.evaluate(MEASURE);
    }
  }

  // Compact table.
  const pad = (s, n) => String(s).padEnd(n);
  console.log(
    pad("case", 26) + pad("items", 7) + pad("wraps", 7) + pad("font", 7) +
    pad("marginR", 9) + pad("sumW", 9) + pad("lastRight", 11) + "wrapAt",
  );
  for (const [k, v] of Object.entries(out)) {
    if (v.error) { console.log(pad(k, 26) + v.error); continue; }
    console.log(
      pad(k, 26) + pad(v.items, 7) + pad(v.wraps, 7) + pad(v.font, 7) +
      pad(v.itemMarginRight, 9) + pad(v.sumWidths, 9) + pad(v.lastRight, 11) + (v.wrapAt || "-"),
    );
  }
  console.log("\nfull metrics:\n" + JSON.stringify(out, null, 1));
}
