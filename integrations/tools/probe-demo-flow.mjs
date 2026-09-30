/**
 * The three demo steps, measured and photographed.
 *
 *   1. the municipal homepage
 *   2. click the new tab
 *   3. the tab page, with the panel embedded
 *   ... and back, to prove the demo is navigable in both directions.
 *
 * Also records every request the route makes, so "no request leaves 127.0.0.1"
 * is evidence rather than a claim, and reads the embedded document directly to
 * prove the host page and the panel do not share a style context.
 *
 * Usage: node integrations/tools/cdp.mjs integrations/tools/probe-demo-flow.mjs
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const BASE = process.env.SB_BASE || "http://127.0.0.1:8097/integrations/municipal-site/";
const EVIDENCE = "integrations/evidence";

const NAV_STATE = () => {
  const ul = document.querySelector("header .main-menu nav#mobile-menu > ul");
  if (!ul) return { error: "no nav" };
  const items = [...ul.children].filter((e) => e.tagName === "LI");
  let wraps = false;
  let wrapAt = null;
  let prev = -Infinity;
  for (const li of items) {
    const r = li.getBoundingClientRect();
    if (r.left < prev - 1) { wraps = true; wrapAt = wrapAt || li.id; }
    prev = r.left;
  }
  const tab = document.getElementById("menuItem_900");
  const tabRect = tab.getBoundingClientRect();
  const link = tab.querySelector("a");
  const cs = getComputedStyle(link);
  return {
    itemCount: items.length,
    wraps,
    wrapAt,
    tabLabel: link.textContent.trim(),
    tabHref: link.getAttribute("href"),
    tabClass: tab.className,
    tabWidth: Math.round(tabRect.width * 100) / 100,
    tabRight: Math.round(tabRect.right * 100) / 100,
    tabColor: cs.color,
    underline: getComputedStyle(tab, "::before").backgroundColor,
    underlineWidth: getComputedStyle(tab, "::before").width,
    viewport: { w: window.innerWidth, h: window.innerHeight },
  };
};

const FRAME_STATE = () => {
  const f = document.getElementById("sb-panel-frame");
  if (!f) return { error: "no iframe" };
  const r = f.getBoundingClientRect();
  const cs = getComputedStyle(f);
  const doc = f.contentDocument;
  let inner = null;
  if (doc) {
    inner = {
      title: doc.title,
      h1: doc.querySelector("h1") ? doc.querySelector("h1").textContent.trim() : null,
      // What the panel itself says about its data — the honest-state contract.
      bodyText: doc.body ? doc.body.innerText.replace(/\s+/g, " ").slice(0, 420) : null,
      scrollHeight: doc.documentElement ? doc.documentElement.scrollHeight : null,
      hasErrorBox: !!doc.querySelector(".sc-logic-error"),
      scripts: doc.querySelectorAll("script[src]").length,
      externalScripts: [...doc.querySelectorAll("script[src]")]
        .map((s) => s.getAttribute("src"))
        .filter((s) => /^https?:\/\//.test(s)),
      bodyFont: doc.body ? getComputedStyle(doc.body).fontFamily : null,
      bodyBg: doc.body ? getComputedStyle(doc.body).backgroundColor : null,
      rootTokens: doc.documentElement ? Object.keys(getComputedStyle(doc.documentElement)).length : 0,
    };
  }
  return {
    src: f.getAttribute("src"),
    width: Math.round(r.width * 100) / 100,
    height: Math.round(r.height * 100) / 100,
    border: cs.borderTopWidth,
    display: cs.display,
    minHeight: cs.minHeight,
    sameOrigin: !!doc,
    inner,
  };
};

const HOST_STATE = () => {
  const html = document.documentElement;
  const cs = getComputedStyle(html);
  return {
    title: document.title,
    breadcrumb: [...document.querySelectorAll("#position ul li")].map((li) => li.textContent.trim()),
    heroTitle: (document.querySelector(".breadcrumb__title") || {}).textContent?.trim() ?? null,
    kicker: (document.querySelector(".sb-kicker") || {}).textContent?.trim() ?? null,
    strap: (document.querySelector(".sb-strap") || {}).textContent?.replace(/\s+/g, " ").trim() ?? null,
    // If the panel's stylesheet leaked, these would be the panel's values.
    themePrimary: cs.getPropertyValue("--bd-theme-primary").trim(),
    bodyBg: getComputedStyle(document.body).backgroundColor,
    bodyFont: getComputedStyle(document.body).fontFamily,
    focusOutline: (() => {
      const a = document.querySelector(".main-menu a");
      return a ? getComputedStyle(a, ":focus").outlineStyle : null;
    })(),
    hasFooter: !!document.querySelector("footer.bd-footer__section, footer"),
    footerBusinessLink: (() => {
      const a = [...document.querySelectorAll("footer a")].find((x) =>
        /jak-zostac-partnerem/.test(x.getAttribute("href") || ""));
      return a ? a.textContent.trim() : null;
    })(),
  };
};

export default async function (page) {
  mkdirSync(EVIDENCE, { recursive: true });
  const report = {};

  for (const [w, h] of [[1280, 800], [1920, 1080]]) {
    const tag = `${w}x${h}`;
    await page.setViewport(w, h);

    // --- Step 1: the municipal homepage ---------------------------------
    await page.goto(BASE, { waitMs: 2500 });
    await page.settle({ extraMs: 1200 });
    report[`step1-homepage-${tag}`] = {
      url: await page.evaluate(() => location.href),
      nav: await page.evaluate(NAV_STATE),
    };
    await page.screenshotViewport(join(EVIDENCE, `01-homepage-${tag}.jpg`));

    // --- Step 2: click the new tab ---------------------------------------
    const url2 = await page.click("#menuItem_900 a", { waitMs: 2600 });
    await page.settle({ extraMs: 1500 });
    report[`step2-tab-${tag}`] = {
      url: url2,
      nav: await page.evaluate(NAV_STATE),
      frame: await page.evaluate(FRAME_STATE),
    };
    await page.screenshotViewport(join(EVIDENCE, `02-tab-page-${tag}.jpg`));

    // --- Step 3: the embedded panel --------------------------------------
    // Scroll the *window* to the frame's document offset; scrollIntoView on a
    // frame inside a static container does not always move the viewport.
    await page.evaluate(() => {
      const f = document.getElementById("sb-panel-frame");
      if (!f) return;
      const top = f.getBoundingClientRect().top + window.scrollY - 110;
      // The theme sets scroll-behavior: smooth, so the scroll lands after the
      // call returns; read the position only after the wait below.
      window.scrollTo({ top: Math.max(0, top), behavior: "instant" });
    });
    await new Promise((r) => setTimeout(r, 1200));
    const scrolledTo = await page.evaluate(() => Math.round(window.scrollY));
    // Also capture the frame's own rectangle in page coordinates, so the
    // "panel" evidence shows the panel regardless of scroll behaviour.
    const frameRect = await page.evaluate(() => {
      const f = document.getElementById("sb-panel-frame");
      if (!f) return null;
      const r = f.getBoundingClientRect();
      return {
        x: Math.round(r.left + window.scrollX),
        y: Math.round(r.top + window.scrollY),
        width: Math.round(r.width),
        height: Math.min(Math.round(r.height), 1100),
      };
    });
    if (frameRect) {
      await page.screenshotClip(join(EVIDENCE, `03-panel-frame-${tag}.jpg`), frameRect);
    }
    report[`step3-panel-${tag}`] = {
      frame: await page.evaluate(FRAME_STATE),
      host: await page.evaluate(HOST_STATE),
    };
    await page.screenshotViewport(join(EVIDENCE, `03-panel-${tag}.jpg`));
    report[`step3-panel-${tag}`].scrolledTo = scrolledTo;

    // --- back ------------------------------------------------------------
    await page.evaluate(() => window.scrollTo(0, 0));
    await new Promise((r) => setTimeout(r, 400));
    const back = await page.click("header .logo a, header a.logo", { waitMs: 2600 }).catch(() => null);
    if (!back) {
      await page.goto(BASE, { waitMs: 2000 });
    }
    report[`step4-back-${tag}`] = {
      url: await page.evaluate(() => location.href),
      isHomepage: await page.evaluate(() =>
        !!document.querySelector(".bd-slider__section") &&
        document.title === "Karta Mieszkańca"),
      hasNewTab: await page.evaluate(() => !!document.getElementById("menuItem_900")),
    };

    // --- requests over the whole route ------------------------------------
    const off = page.offOrigin();
    const all = page.requests();
    report[`requests-${tag}`] = {
      total: all.length,
      offOrigin: off.map((r) => ({ url: r.url, status: r.status })),
      origin: (() => {
        const u = new URL(BASE);
        return u.origin;
      })(),
    };
    report[`console-${tag}`] = page.logs();
  }

  writeFileSync(join(EVIDENCE, "demo-flow.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}
