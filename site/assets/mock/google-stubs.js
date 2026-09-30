/* ==========================================================================
   Local shim for third-party scripts that cannot be self-hosted.

   Replaces, in the design-mockup replica:
     * https://www.google.com/recaptcha/enterprise.js   (/pl/jak-zostac-partnerem/)
     * https://maps.googleapis.com/maps/api/js          (/pl/partnerzy/)

   Nothing here talks to the network. The widgets those scripts would power are
   rendered as clearly labelled placeholders instead.
   ========================================================================== */
(function () {
    "use strict";

    function placeholder(container, title, detail, source) {
        if (!container || container.dataset.mockPlaceholder) {
            return;
        }
        container.dataset.mockPlaceholder = "1";
        container.innerHTML =
            '<div class="embed-placeholder">' +
            "<strong>" + title + "</strong>" +
            "<span>" + detail + "</span>" +
            (source ? "<code>" + source + "</code>" : "") +
            "</div>";
    }

    /* --- reCAPTCHA ------------------------------------------------------- */
    window.grecaptcha = window.grecaptcha || {
        ready: function (cb) {
            if (typeof cb === "function") {
                cb();
            }
        },
        execute: function () {
            return Promise.resolve("mock-recaptcha-token");
        },
        render: function () {
            return 0;
        },
        reset: function () {},
        getResponse: function () {
            return "mock-recaptcha-token";
        },
    };
    window.___grecaptcha_cfg = window.___grecaptcha_cfg || { clients: {} };

    /* --- Google Maps ----------------------------------------------------- */
    var noop = function () {
        return undefined;
    };

    function chainable() {
        return new Proxy(function () {}, {
            get: function () {
                return chainable();
            },
            apply: function () {
                return chainable();
            },
        });
    }

    if (!window.google) {
        window.google = {
            maps: {
                Map: function (container) {
                    placeholder(
                        container,
                        "Mapa Google — placeholder",
                        "Interaktywna mapa Google Maps nie jest hostowana lokalnie w tej makiecie." +
                            " W oryginale zastępuje ten obszar widget Google Maps API.",
                        "maps.googleapis.com/maps/api/js",
                    );
                    this.setCenter = noop;
                    this.setZoom = noop;
                    this.addListener = noop;
                    this.fitBounds = noop;
                    this.panTo = noop;
                    this.getBounds = noop;
                },
                Marker: function () {
                    this.setMap = noop;
                    this.addListener = noop;
                },
                LatLng: function (lat, lng) {
                    this.lat = function () {
                        return lat;
                    };
                    this.lng = function () {
                        return lng;
                    };
                },
                LatLngBounds: function () {
                    this.extend = noop;
                    this.getCenter = noop;
                },
                DirectionsService: function () {
                    this.route = noop;
                },
                DirectionsRenderer: function () {
                    this.setDirections = noop;
                    this.setMap = noop;
                },
                InfoWindow: function () {
                    this.open = noop;
                    this.close = noop;
                },
                Size: function () {},
                Point: function () {},
                MapTypeId: { ROADMAP: "roadmap" },
                SymbolPath: { CIRCLE: 0 },
                event: { addListener: noop, removeListener: noop, trigger: noop },
                geometry: { spherical: chainable() },
            },
        };
    }

    /* --- generic labelled placeholders ----------------------------------- */
    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-mock-embed]").forEach(function (el) {
            placeholder(
                el,
                "Osadzona treść — placeholder",
                "Ta treść pochodzi z serwisu zewnętrznego i nie jest hostowana lokalnie w tej makiecie.",
                el.getAttribute("data-mock-embed"),
            );
        });
    });
})();
