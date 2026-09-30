/**
 * Measure whether the eighth navigation item wraps or clips.
 *
 * The audit (karta-integration.md §1.5) predicts the nav is already near
 * capacity at 1200–1400 px and that an eighth item will wrap.  This probe
 * answers that with measurements instead of an estimate, at the two viewports
 * the brief names.
 *
 * Usage: node integrations/tools/cdp.mjs integrations/tools/probe-nav.mjs
 */
const BASE = process.env.SB_BASE || "http://127.0.0.1:8097/integrations/municipal-site/";

const MEASURE = () => {
  const nav = document.querySelector("header .main-menu nav#mobile-menu");
  const ul = nav && nav.querySelector(":scope > ul");
  if (!ul) return { error: "header nav ul not found" };

  const items = [...ul.children].filter((el) => el.tagName === "LI");
  const boxes = items.map((li) => {
    const a = li.querySelector("a");
    const r = li.getBoundingClientRect();
    const ar = a ? a.getBoundingClientRect() : null;
    return {
      id: li.id,
      label: a ? a.textContent.trim() : "",
      cls: li.className,
      top: Math.round(r.top * 100) / 100,
      left: Math.round(r.left * 100) / 100,
      right: Math.round(r.right * 100) / 100,
      width: Math.round(r.width * 100) / 100,
      height: Math.round(r.height * 100) / 100,
      linkWidth: ar ? Math.round(ar.width * 100) / 100 : null,
      linkFont: a ? getComputedStyle(a).font : null,
      marginRight: getComputedStyle(li).marginRight,
    };
  });

  // Wrapping is "some item starts further left than an earlier one" — the
  // per-item `top` also moves for the taller CTA-style item, so distinct top
  // values alone would report a false wrap.
  let wraps = false;
  let wrapAt = null;
  for (let i = 1; i < boxes.length; i++) {
    if (boxes[i].left < boxes[i - 1].left - 1) {
      wraps = true;
      wrapAt = boxes[i].id;
      break;
    }
  }
  const rows = [...new Set(boxes.map((b) => b.top))].sort((a, b) => a - b);
  const ulRect = ul.getBoundingClientRect();
  const colRect = ul.closest(".main-menu").getBoundingClientRect();
  const last = boxes[boxes.length - 1];
  const navRect = nav.getBoundingClientRect();
  const headerInner = document.querySelector("#mainMenu");
  const innerRect = headerInner ? headerInner.getBoundingClientRect() : null;

  // Does the last item's box overflow its column, the nav or the header bar?
  const overflow = {
    pastNavRight: Math.round((last.right - navRect.right) * 100) / 100,
    pastHeaderRight: innerRect ? Math.round((last.right - innerRect.right) * 100) / 100 : null,
    pastMenuColumn: Math.round((last.right - colRect.right) * 100) / 100,
    pastViewport: Math.round((last.right - window.innerWidth) * 100) / 100,
  };

  // Clipping: is any ancestor hiding the overflow?
  const clipped = [];
  let el = ul.parentElement;
  while (el && el !== document.documentElement) {
    const cs = getComputedStyle(el);
    if (cs.overflowX !== "visible" || cs.overflow !== "visible") {
      const r = el.getBoundingClientRect();
      if (last.right > r.right + 0.5) {
        clipped.push({
          selector: el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") +
            (el.className && typeof el.className === "string"
              ? "." + el.className.trim().split(/\s+/).join(".") : ""),
          overflow: cs.overflow,
          right: Math.round(r.right * 100) / 100,
        });
      }
    }
    el = el.parentElement;
  }

  return {
    viewport: { width: window.innerWidth, height: window.innerHeight, dpr: window.devicePixelRatio },
    itemCount: boxes.length,
    tabItem: boxes.find((b) => b.id === "menuItem_900") || null,
    distinctRows: rows.length,
    wraps,
    wrapAt,
    ulWidth: Math.round(ulRect.width * 100) / 100,
    navWidth: Math.round(navRect.width * 100) / 100,
    menuColumnWidth: Math.round(colRect.width * 100) / 100,
    ulHeight: Math.round(ulRect.height * 100) / 100,
    rowTops: rows,
    items: boxes,
    overflow,
    clipped,
    stylesheetRule: (() => {
      const a = document.querySelector("#menuItem_900 a");
      const cs = a ? getComputedStyle(a) : null;
      return cs ? { fontSize: cs.fontSize, fontWeight: cs.fontWeight, fontFamily: cs.fontFamily } : null;
    })(),
  };
};

function summarise(m) {
  if (m.error) return m;
  const tab = m.tabItem;
  return {
    items: m.itemCount,
    wraps: m.wraps,
    wrapAt: m.wrapAt,
    tab: tab && {
      label: tab.label, left: tab.left, right: tab.right,
      width: tab.width, height: tab.height, top: tab.top, class: tab.cls,
    },
    ulWidth: m.ulWidth,
    menuColumnWidth: m.menuColumnWidth,
    slackInColumn: Math.round((m.menuColumnWidth - m.ulWidth) * 100) / 100,
    overflow: m.overflow,
    clippedBy: m.clipped,
    lastItemRight: m.items[m.items.length - 1].right,
    firstItemLeft: m.items[0].left,
    font: m.stylesheetRule,
  };
}

export default async function (page) {
  const out = {};
  for (const [w, h] of [[1280, 800], [1366, 768], [1440, 900], [1920, 1080]]) {
    await page.setViewport(w, h);
    await page.goto(BASE, { waitMs: 2200 });
    await page.settle({ extraMs: 1200 });
    out[`${w}x${h}`] = summarise(await page.evaluate(MEASURE));
  }
  console.log(JSON.stringify(out, null, 2));
}
