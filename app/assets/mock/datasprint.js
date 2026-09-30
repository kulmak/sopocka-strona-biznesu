/* ==========================================================================
   DataSprint — fajerwerki nad wyróżnioną zakładką (dodatek do makiety)

   Rysuje krótkie serie iskier na <canvas> umieszczonym nad pozycją menu.
   Efekt jest wyłączony przy prefers-reduced-motion.
   ========================================================================== */
(function () {
    "use strict";

    var PALETTE = ["#ffd166", "#ff8a2b", "#ff4d2e", "#ff2d55", "#ffe08a", "#4fd1a5"];
    var canvas = null;
    var ctx = null;
    var raf = 0;
    var last = 0;
    var nextBurst = 0;
    var particles = [];

    function reducedMotion() {
        return (
            typeof window.matchMedia === "function" &&
            window.matchMedia("(prefers-reduced-motion: reduce)").matches
        );
    }

    function resize() {
        if (!canvas) return;
        var box = canvas.getBoundingClientRect();
        var dpr = window.devicePixelRatio || 1;
        canvas.width = Math.max(1, Math.round(box.width * dpr));
        canvas.height = Math.max(1, Math.round(box.height * dpr));
        if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function burst(w, h) {
        var fromLeft = Math.random() < 0.5;
        var ox = fromLeft ? 2 : w - 2;
        var oy = h - 2;
        var tx = w * (0.18 + Math.random() * 0.64);
        var ty = h * (0.05 + Math.random() * 0.34);
        var count = 24 + Math.floor(Math.random() * 14);
        var color = PALETTE[Math.floor(Math.random() * PALETTE.length)];
        for (var i = 0; i < count; i++) {
            var life = 0.9 + Math.random() * 0.6;
            particles.push({
                x: ox,
                y: oy,
                vx: (tx - ox) / (life * 60) + (Math.random() - 0.5) * 52,
                vy: (ty - oy) / (life * 60) + (Math.random() - 0.5) * 42,
                life: life,
                age: 0,
                color: Math.random() < 0.72 ? color : "#fff6e0",
                size: 1.4 + Math.random() * 2,
            });
        }
    }

    function frame(now) {
        raf = window.requestAnimationFrame(frame);
        if (!ctx || !canvas) return;
        var dt = Math.min(48, now - (last || now)) / 1000;
        last = now;
        var w = canvas.clientWidth || 1;
        var h = canvas.clientHeight || 1;

        if (now >= nextBurst) {
            burst(w, h);
            nextBurst = now + 240 + Math.random() * 380;
        }

        ctx.clearRect(0, 0, w, h);
        var keep = [];
        for (var i = 0; i < particles.length; i++) {
            var p = particles[i];
            p.age += dt;
            if (p.age >= p.life) continue;
            p.vy += 165 * dt;
            p.vx *= 0.988;
            p.vy *= 0.988;
            p.x += p.vx * dt;
            p.y += p.vy * dt;
            var t = 1 - p.age / p.life;
            ctx.globalAlpha = Math.max(0, t * t);
            ctx.fillStyle = p.color;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size * (0.5 + t * 0.7), 0, Math.PI * 2);
            ctx.fill();
            keep.push(p);
        }
        ctx.globalAlpha = 1;
        particles = keep;
    }

    function start() {
        if (reducedMotion()) return;
        var li = document.querySelector("li.menu-datasprint");
        if (!li || li.querySelector("canvas.ds-fx")) return;

        // The header menu is hidden on narrow screens; a zero-size host would
        // just burn CPU on an invisible canvas.
        var host = li.getBoundingClientRect();
        if (host.width < 40 || host.height < 10) return;

        canvas = document.createElement("canvas");
        canvas.className = "ds-fx";
        canvas.setAttribute("aria-hidden", "true");
        li.insertBefore(canvas, li.firstChild);
        ctx = canvas.getContext("2d");
        if (!ctx) return;

        resize();
        window.addEventListener("resize", resize);
        last = 0;
        nextBurst = 0;
        burst(canvas.clientWidth || 200, canvas.clientHeight || 44);
        burst(canvas.clientWidth || 200, canvas.clientHeight || 44);
        raf = window.requestAnimationFrame(frame);
    }

    /* Podświetlenie zakładki na jej własnej stronie (bez ingerencji w build). */
    function markActive() {
        var path = window.location.pathname.replace(/\/+$/, "");
        if (!/\/pl\/datasprint$/.test(path)) return;
        var li = document.querySelector("li.menu-datasprint");
        if (!li) return;
        li.classList.add("is-active");
        var a = li.querySelector("a");
        if (a) a.setAttribute("aria-current", "page");
    }

    function init() {
        markActive();
        start();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
