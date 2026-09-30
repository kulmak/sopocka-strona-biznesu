/* Dashboard shell — left sidebar navigation between the three sections:
   · "Wydarzenia i biznes"  (calendar) → Panel przedsiębiorcy (iframe)
   · "Mój rynek"            (market)   → Sopot Signal (iframe, demo mode)
   · "Moje Sprawy"          (sprawy)   → inline municipal case list (kept from the layout)
   Only the active section is shown; iframes keep their own state across switches. */

const SECTIONS = {
  calendar: { eyebrow: "Wydarzenia i biznes", title: "Wydarzenia i biznes" },
  market: { eyebrow: "Mój rynek", title: "Mój rynek" },
  sprawy: { eyebrow: "Moje Sprawy", title: "Moje Sprawy" },
};

const VALID = Object.keys(SECTIONS);
const NAV_SELECTOR = ".side-nav-item[data-section]";

function setSection(id) {
  const section = VALID.includes(id) ? id : "calendar";

  document.querySelectorAll(NAV_SELECTOR).forEach((el) => {
    const active = el.dataset.section === section;
    el.classList.toggle("is-active", active);
    el.setAttribute("aria-selected", active ? "true" : "false");
  });

  document.querySelectorAll(".view").forEach((view) => {
    const active = view.id === `view-${section}`;
    view.classList.toggle("is-active", active);
    view.hidden = !active;
  });

  const meta = SECTIONS[section];
  document.getElementById("section-eyebrow").textContent = meta.eyebrow;
  document.getElementById("section-title").textContent = meta.title;

  const url = new URL(window.location.href);
  url.searchParams.set("section", section);
  window.history.replaceState({}, "", url);
}

function init() {
  document.querySelectorAll(NAV_SELECTOR).forEach((nav) => {
    nav.addEventListener("click", () => setSection(nav.dataset.section));
  });

  setSection(new URLSearchParams(window.location.search).get("section") || "calendar");
}

document.addEventListener("DOMContentLoaded", init);
