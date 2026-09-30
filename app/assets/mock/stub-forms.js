/* ==========================================================================
   Form stub for the karta.sopot.pl design-mockup replica.

   Every <form> in this replica keeps its original markup, field names and
   validation attributes, but its action was rewritten to "#" and annotated
   with data-mock-action="<original action>" plus data-mock-form="1".

   This script intercepts submission, shows the same SweetAlert2 dialog style
   the site itself uses, and never performs a network request.
   ========================================================================== */
(function () {
    "use strict";

    var MESSAGE = {
        title: "Makieta",
        html:
            "Wysyłka formularza jest wyłączona w tej makiecie.<br>" +
            "Oryginalny adres docelowy: <code>%ACTION%</code>",
        icon: "info",
        confirmButtonText: "Rozumiem",
        confirmButtonColor: "#178fd3",
    };

    function note(form) {
        if (!form || form.querySelector(".mock-form-note")) {
            return;
        }
        var box = document.createElement("p");
        box.className = "mock-form-note";
        box.innerHTML =
            "<strong>Makieta:</strong> formularz odtworzony wizualnie, wysyłka wyłączona.";
        if (form.parentNode) {
            form.parentNode.insertBefore(box, form.nextSibling);
        }
    }

    function announce(form) {
        var action = (form && form.getAttribute("data-mock-action")) || "(brak)";
        var payload = MESSAGE.html.replace("%ACTION%", action);
        note(form);
        if (window.Swal && typeof window.Swal.fire === "function") {
            window.Swal.fire({
                title: MESSAGE.title,
                html: payload,
                icon: MESSAGE.icon,
                confirmButtonText: MESSAGE.confirmButtonText,
                confirmButtonColor: MESSAGE.confirmButtonColor,
            });
        } else {
            window.alert("Makieta: wysyłka formularza jest wyłączona.\n" + action);
        }
    }

    document.addEventListener(
        "submit",
        function (event) {
            if (event.target && event.target.matches("[data-mock-form]")) {
                event.preventDefault();
                event.stopPropagation();
                announce(event.target);
            }
        },
        true,
    );

    // A few CMS buttons live outside a <form> and would otherwise navigate to a
    // backend route that does not exist in a static replica.
    document.addEventListener(
        "click",
        function (event) {
            var el = event.target;
            if (!el || !el.closest) {
                return;
            }
            var trigger = el.closest("[data-mock-action]:not(form)");
            if (!trigger) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            announce(trigger.form || trigger.closest("form") || trigger);
        },
        true,
    );
})();
