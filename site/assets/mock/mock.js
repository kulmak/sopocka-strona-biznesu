/* ==========================================================================
   Enhancement over the original: partner gallery thumbnails.

   The live CMS emits partner gallery <img> tags with an empty src and the real
   URL parked in data-url-grafiki:

       <img src='' data-url-grafiki="https://.../res/.../foto.jpg"
            class="grafika-galerii-lazy-load" alt=""/>

   The scroll handler that was supposed to copy that value into src is missing
   from the deployed site, so those images never load there either. In the
   replica the URLs are mirrored locally (see tools/fetch_details.py), so this
   wires them up and the Partnerzy grid shows real thumbnails.

   Remove this file's <script> tag if you would rather see the original,
   image-less behaviour.
   ========================================================================== */
(function () {
    "use strict";

    function hydrateImage(img) {
        var url = img.getAttribute("data-url-grafiki");
        if (!url || img.getAttribute("src")) {
            return;
        }
        img.setAttribute("src", url);
    }

    function hydrateAll(scope) {
        (scope || document).querySelectorAll("img[data-url-grafiki]").forEach(hydrateImage);
    }

    document.addEventListener("DOMContentLoaded", function () {
        hydrateAll(document);
    });

    // Partner cards are appended/filtered client-side, so keep watching.
    if (window.MutationObserver) {
        new MutationObserver(function (records) {
            records.forEach(function (record) {
                record.addedNodes.forEach(function (node) {
                    if (node.nodeType !== 1) {
                        return;
                    }
                    if (node.matches && node.matches("img[data-url-grafiki]")) {
                        hydrateImage(node);
                    }
                    hydrateAll(node);
                });
            });
        }).observe(document.documentElement, { childList: true, subtree: true });
    }
})();
