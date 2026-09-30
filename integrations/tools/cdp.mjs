/**
 * Minimal Chrome DevTools Protocol driver (no npm dependencies).
 *
 * Adapted from karta-mockup/tools/cdp.mjs (read-only source, never modified) so
 * the integration can be verified inside this repository.  The additions are a
 * network recorder — needed to prove that no request leaves 127.0.0.1 — and a
 * `click` helper that waits for navigation.
 *
 * Usage: node integrations/tools/cdp.mjs <script.mjs>
 * The target script exports `default async (page, ctx) => {...}` and receives a
 * `page` object with goto / evaluate / screenshot / setViewport / click /
 * requests helpers.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

async function launch() {
  const profile = mkdtempSync(join(tmpdir(), "cdp-"));
  const child = spawn(
    CHROME,
    [
      "--headless=new",
      "--window-size=1440,900",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      "--hide-scrollbars",
      "--remote-debugging-port=0",
      `--user-data-dir=${profile}`,
      "about:blank",
    ],
    { stdio: ["ignore", "pipe", "pipe"] },
  );

  const wsUrl = await new Promise((res, rej) => {
    let buf = "";
    const onData = (d) => {
      buf += d.toString();
      const m = buf.match(/ws:\/\/[^\s]+/);
      if (m) res(m[0]);
    };
    child.stderr.on("data", onData);
    child.stdout.on("data", onData);
    child.on("exit", (c) => rej(new Error(`chrome exited ${c}`)));
    setTimeout(() => rej(new Error("chrome did not report a ws endpoint")), 25000);
  });

  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => {
    ws.onopen = res;
    ws.onerror = rej;
  });

  let id = 0;
  const pending = new Map();
  const events = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { res, rej } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
    } else if (msg.method) {
      events.push(msg);
    }
  };

  const send = (method, params = {}, sessionId) =>
    new Promise((res, rej) => {
      const mid = ++id;
      pending.set(mid, { res, rej });
      ws.send(JSON.stringify({ id: mid, method, params, sessionId }));
    });

  return { child, ws, send, events, close: () => { try { ws.close(); } catch {} child.kill(); } };
}

function makePage(send, sessionId, events) {
  return {
    /** Console + page errors observed since the last reset. */
    logs() {
      return events
        .filter((e) => e.method === "Runtime.consoleAPICalled" || e.method === "Runtime.exceptionThrown")
        .map((e) => {
          if (e.method === "Runtime.exceptionThrown") {
            const d = e.params.exceptionDetails;
            return `EXCEPTION ${d.text} ${d.exception?.description ?? ""}`.trim();
          }
          const p = e.params;
          return `${p.type.toUpperCase()} ${(p.args || [])
            .map((a) => a.value ?? a.description ?? a.type)
            .join(" ")}`;
        });
    },
    resetLogs() {
      events.length = 0;
    },

    /** Every URL the page actually requested since the last reset, with status. */
    requests() {
      const out = new Map();
      for (const e of events) {
        if (e.method === "Network.requestWillBeSent") {
          const u = e.params.request.url;
          if (!out.has(u)) out.set(u, { url: u, status: null, type: e.params.type });
        }
        if (e.method === "Network.responseReceived") {
          const u = e.params.response.url;
          if (out.has(u)) out.get(u).status = e.params.response.status;
          else out.set(u, { url: u, status: e.params.response.status, type: e.params.type });
        }
        if (e.method === "Network.loadingFailed") {
          const u = e.params.requestId;
          for (const v of out.values()) if (v.requestId === u) v.failed = e.params.errorText;
        }
      }
      return [...out.values()];
    },
    /**
     * Genuine network requests to anything other than the local origin.
     * data: and blob: URLs are inline payloads, not requests, so they are not
     * reported here.
     */
    offOrigin() {
      return this.requests().filter((r) =>
        /^[a-z][a-z0-9+.-]*:/i.test(r.url) &&
        !/^(data|blob|about|javascript):/i.test(r.url) &&
        !/^https?:\/\/(127\.0\.0\.1|localhost)(:|\/)/.test(r.url));
    },

    async goto(url, { waitMs = 1200 } = {}) {
      this.resetLogs();
      await send("Page.navigate", { url }, sessionId);
      await new Promise((r) => setTimeout(r, waitMs));
    },

    /** Click a selector and wait for the resulting navigation to settle. */
    async click(selector, { waitMs = 1500 } = {}) {
      const ok = await this.evaluate((sel) => {
        const el = document.querySelector(sel);
        if (!el) return false;
        el.scrollIntoView({ block: "center" });
        el.click();
        return true;
      }, selector);
      if (!ok) throw new Error(`click: no element for ${selector}`);
      await new Promise((r) => setTimeout(r, waitMs));
      return this.evaluate(() => location.href);
    },

    async setViewport(width, height, deviceScaleFactor = 1) {
      await send(
        "Emulation.setDeviceMetricsOverride",
        { width, height, deviceScaleFactor, mobile: width < 768 },
        sessionId,
      );
    },

    /** Block requests whose URL matches any of the glob patterns. */
    async blockUrls(patterns) {
      await send("Network.enable", {}, sessionId);
      await send("Network.setBlockedURLs", { urls: patterns }, sessionId);
    },

    /**
     * Block until layout is deterministic: load event, every declared webfont
     * actually rasterised, then animations frozen so nothing shifts mid-capture.
     */
    async settle({ extraMs = 2500 } = {}) {
      await this.evaluate(async () => {
        if (document.readyState !== "complete") {
          await new Promise((r) => window.addEventListener("load", r, { once: true }));
        }
        if (document.fonts) {
          const faces = [...document.fonts].filter((f) => f.family.includes("Montserrat"));
          await Promise.all(faces.map((f) => f.load().catch(() => null)));
          await document.fonts.ready;
          void document.body.offsetHeight;
        }
      });
      await new Promise((r) => setTimeout(r, extraMs));
      await this.evaluate(() => {
        const kill = document.createElement("style");
        kill.textContent =
          "*,*::before,*::after{animation-duration:0s!important;animation-delay:0s!important;transition-duration:0s!important;transition-delay:0s!important;}";
        document.head.appendChild(kill);
        void document.body.offsetHeight;
      });
    },

    async evaluate(fnSource, ...args) {
      const expression = `(${fnSource})(${args.map((a) => JSON.stringify(a)).join(",")})`;
      const r = await send(
        "Runtime.evaluate",
        { expression, returnByValue: true, awaitPromise: true },
        sessionId,
      );
      if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
      return r.result.value;
    },

    /** Evaluate inside the embedded panel's document (same-origin only). */
    async evaluateInFrame(selector, fnSource, ...args) {
      const expression = `(function(){
        var f = document.querySelector(${JSON.stringify(selector)});
        if (!f || !f.contentDocument) return null;
        return (${fnSource}).apply(f.contentWindow, ${JSON.stringify(args)});
      })()`;
      const r = await send(
        "Runtime.evaluate",
        { expression, returnByValue: true, awaitPromise: true },
        sessionId,
      );
      if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
      return r.result.value;
    },

    async screenshot(path, { fullPage = true } = {}) {
      const params = { format: "png", captureBeyondViewport: fullPage };
      if (fullPage) {
        const m = await send("Page.getLayoutMetrics", {}, sessionId);
        const h = Math.min(Math.ceil(m.cssContentSize.height), 16000);
        params.clip = { x: 0, y: 0, width: Math.ceil(m.cssContentSize.width), height: h, scale: 1 };
      }
      const { data } = await send("Page.captureScreenshot", params, sessionId);
      writeFileSync(path, Buffer.from(data, "base64"));
      return path;
    },

    /**
     * Capture a page-coordinate rectangle, whatever the scroll position.
     * Defaults to JPEG q92: these are evidence photographs, and PNG screenshots
     * of a photo-heavy page cost ~8x the bytes for no visible gain.
     */
    async screenshotClip(path, rect, { format = "jpeg", quality = 92 } = {}) {
      const params = {
        format,
        clip: { x: rect.x, y: rect.y, width: rect.width, height: rect.height, scale: 1 },
      };
      if (format === "jpeg") params.quality = quality;
      const { data } = await send("Page.captureScreenshot", params, sessionId);
      writeFileSync(path, Buffer.from(data, "base64"));
      return path;
    },

    /** Viewport-only capture, for evidence that matches what a juror sees. */
    async screenshotViewport(path, { format = "jpeg", quality = 92 } = {}) {
      const params = { format };
      if (format === "jpeg") params.quality = quality;
      const { data } = await send("Page.captureScreenshot", params, sessionId);
      writeFileSync(path, Buffer.from(data, "base64"));
      return path;
    },
  };
}

const scriptPath = process.argv[2];
if (!scriptPath) {
  console.error("usage: node integrations/tools/cdp.mjs <script.mjs>");
  process.exit(2);
}

const { child, send, close, events } = await launch();
const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
await send("Page.enable", {}, sessionId);
await send("Runtime.enable", {}, sessionId);
await send("Network.enable", {}, sessionId);

const mod = await import(pathToFileURL(resolve(scriptPath)).href);
try {
  await mod.default(makePage(send, sessionId, events), { send, sessionId });
} finally {
  close();
}
void child;
