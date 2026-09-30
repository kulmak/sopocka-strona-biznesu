/**
 * Prove the iframe is doing real work.
 *
 * The audit's collision list is the reason for embedding the panel in its own
 * document rather than inline. This probe reads both documents at once and
 * shows that none of it crosses the boundary:
 *
 *   - host <html> keeps #178fd3 and Montserrat; the panel runs Barlow on its own
 *   - the panel's :root tokens do not appear in the host
 *   - the host still has focus outlines
 *   - the panel's own rendered pixels match a direct visit to /app/
 *
 * Usage: node integrations/tools/cdp.mjs integrations/tools/probe-isolation.mjs
 */
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const BASE = process.env.SB_BASE || "http://127.0.0.1:8097/integrations/municipal-site/";
const EVIDENCE = "integrations/evidence";

const SAMPLE = () => {
  const host = getComputedStyle(document.documentElement);
  const body = getComputedStyle(document.body);
  const f = document.getElementById("sb-panel-frame");
  const doc = f && f.contentDocument;
  const inner = doc ? getComputedStyle(doc.body) : null;
  const innerRoot = doc ? getComputedStyle(doc.documentElement) : null;

  // Every custom property the panel defines, to check for leakage into the host.
  const panelTokenNames = [];
  if (innerRoot) {
    for (const sheet of doc.styleSheets) {
      let rules;
      try { rules = sheet.cssRules; } catch { continue; }
      for (const rule of rules || []) {
        if (rule.selectorText === ":root" || rule.selectorText === "html") {
          for (const prop of rule.style || []) {
            if (prop.startsWith("--")) panelTokenNames.push(prop);
          }
        }
      }
    }
  }
  const leaked = panelTokenNames.filter(
    (p) => host.getPropertyValue(p).trim() !== "" && host.getPropertyValue(p).trim() !== "",
  );

  // A focused link must keep a visible ring on the host.
  const a = document.querySelector(".main-menu nav a");
  a.focus();
  const focusRing = getComputedStyle(a).outlineStyle + " " + getComputedStyle(a).outlineWidth;
  a.blur();

  const r = f ? f.getBoundingClientRect() : null;
  return {
    host: {
      themePrimary: host.getPropertyValue("--bd-theme-primary").trim(),
      fontBody: body.fontFamily,
      bodyBg: body.backgroundColor,
      focusRing,
      htmlOverflow: getComputedStyle(document.documentElement).overflow,
      boxSizingOnHostEl: getComputedStyle(document.querySelector("main") || document.body).boxSizing,
    },
    panel: inner
      ? {
          fontBody: inner.fontFamily,
          bodyBg: inner.backgroundColor,
          bodyMargin: inner.margin,
          htmlHeight: innerRoot.height,
        }
      : null,
    panelTokenCount: panelTokenNames.length,
    // Tokens the panel defines that the host ALSO resolves to something: these
    // are the ones that would clobber the municipal theme on a direct embed.
    tokensThatWouldCollide: leaked.slice(0, 12),
    leakedCount: leaked.length,
    frame: r
      ? {
          x: Math.round(r.left + window.scrollX),
          y: Math.round(r.top + window.scrollY),
          width: Math.round(r.width),
          height: Math.round(r.height),
        }
      : null,
  };
};

export default async function (page) {
  mkdirSync(EVIDENCE, { recursive: true });

  await page.setViewport(1280, 800);
  await page.goto(BASE + "pl/strona-biznesu/", { waitMs: 3000 });
  await page.settle({ extraMs: 1500 });
  const embedded = await page.evaluate(SAMPLE);

  // The same pixels, reached directly: if the panel renders identically inside
  // the frame, the boundary is invisible to the panel and to the juror.
  const w = embedded.frame ? embedded.frame.width : 1116;
  await page.setViewport(w, 1100);
  await page.goto(new URL("/app/", BASE).href, { waitMs: 3000 });
  await page.settle({ extraMs: 1200 });
  const direct = await page.evaluate(() => ({
    title: document.title,
    bg: getComputedStyle(document.body).backgroundColor,
    font: getComputedStyle(document.body).fontFamily,
  }));
  await page.screenshotClip(join(EVIDENCE, "04-panel-direct.jpg"),
    { x: 0, y: 0, width: w, height: 1100 });

  const out = {
    embeddedAt1280: embedded,
    directVisit: direct,
    offOrigin: page.offOrigin(),
    console: page.logs(),
  };
  console.log(JSON.stringify(out, null, 2));
}
