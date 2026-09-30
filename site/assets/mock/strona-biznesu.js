/* ==========================================================================
   Strona Biznesu — podłączenie panelu przedsiębiorcy.

   Panel jest osobną aplikacją pod adresem /app/. Ten skrypt:

     1. sprawdza, czy aplikacja jest dostępna (nagłówek HEAD na plik wejściowy),
     2. wstawia ją do ramki,
     3. dopasowuje wysokość ramki do treści panelu.

   Punkt 3 jest ważny dla odbioru: panel ma około 3000 px wysokości i bez tego
   powstałoby drugie, wewnętrzne okno przewijania — strona wyglądałaby wtedy
   jak obcy widget wklejony w środek serwisu, a nie jak jego własna treść.

   Gdy aplikacji nie ma, w ramce pojawia się strona "panel-w-przygotowaniu.html",
   która mówi wprost, na co strona czeka. Nigdy nie pokazujemy fałszywego panelu
   ani danych przykładowych.

   Brak tutaj jakiejkolwiek zależności sieciowej poza tym samym hostem.
   ========================================================================== */
(function () {
    "use strict";

    var PANEL_URL = "../../../app/panel.html";
    var PANEL_PROBE = "../../../app/index.html";
    var PENDING = "panel-w-przygotowaniu.html";

    // The panel is a full dashboard; these bound the frame so a runaway
    // document cannot stretch the municipal page without limit.
    var MIN_HEIGHT = 820;
    var MAX_HEIGHT = 6000;

    function showStatus(box, visible) {
        if (visible) {
            box.classList.remove("is-ready");
        } else {
            box.classList.add("is-ready");
        }
    }

    function sizeToContent(frame) {
        var doc = frame.contentDocument;
        if (!doc || !doc.documentElement) {
            return;
        }
        var h = Math.max(
            doc.documentElement.scrollHeight,
            doc.body ? doc.body.scrollHeight : 0
        );
        if (!h) {
            return;
        }
        var bounded = Math.min(Math.max(h + 8, MIN_HEIGHT), MAX_HEIGHT);
        frame.style.height = bounded + "px";
    }

    function watch(frame) {
        // The panel fills in after its aggregate loads, so re-measure for a
        // while rather than trusting the first load event alone.
        var ticks = 0;
        var timer = window.setInterval(function () {
            sizeToContent(frame);
            if (++ticks > 24) {
                window.clearInterval(timer);
            }
        }, 500);

        var doc = frame.contentDocument;
        if (doc && window.ResizeObserver) {
            try {
                new window.ResizeObserver(function () {
                    sizeToContent(frame);
                }).observe(doc.documentElement);
            } catch (err) {
                /* older engines: the interval above already covers this */
            }
        }
    }

    function boot() {
        var box = document.getElementById("sb-panel");
        var frame = document.getElementById("sb-panel-frame");
        if (!box || !frame) {
            return;
        }

        function show(src, isPanel) {
            if (isPanel) {
                frame.addEventListener("load", function () {
                    showStatus(box, false);
                    sizeToContent(frame);
                    watch(frame);
                });
            }
            frame.src = src;
            if (!isPanel) {
                showStatus(box, false);
                frame.style.height = "auto";
                frame.style.minHeight = "320px";
            }
        }

        try {
            var xhr = new XMLHttpRequest();
            xhr.open("HEAD", PANEL_PROBE, true);
            xhr.onreadystatechange = function () {
                if (xhr.readyState !== 4) {
                    return;
                }
                var ok = xhr.status >= 200 && xhr.status < 400;
                show(ok ? PANEL_URL : PENDING, ok);
            };
            xhr.onerror = function () {
                show(PENDING, false);
            };
            xhr.send();
            // A server that never answers the HEAD must not leave the juror
            // staring at "Wczytywanie…" forever.
            window.setTimeout(function () {
                if (!frame.getAttribute("src")) {
                    show(PENDING, false);
                }
            }, 4000);
        } catch (err) {
            show(PENDING, false);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
