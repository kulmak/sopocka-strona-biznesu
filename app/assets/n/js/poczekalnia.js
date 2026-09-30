/**
 * Heartbeat poczekalni — dołączany na stronach koszyka/zakupu biletów.
 * Ten sam skrypt działa w przeglądarce i w webview aplikacji (MagicznyWebWidok),
 * bo webview wykonuje JS strony tak samo jak przeglądarka.
 *
 * Użycie w QCards (wspólny layout, np. n-head.ftl na stronach zakupu):
 *   <script src="/poczekalnia/js/poczekalnia.js"></script>
 * Przed redirectem do P24 wywołać: Poczekalnia.idePlacic(function(){ ...redirect... });
 * Po udanym zakupie (strona podziękowania): Poczekalnia.zwolnij();
 */
(function (okno) {
  "use strict";

  var INTERWAL_MS = 10000; // co ile ping (TTL slotu na serwerze ~3x ta wartosc)
  var stoper = null;

  // Sciezki objete bramka — MUSZA odpowiadac temu, co bramkuje nginx
  // (integracja/poczekalnia-vhost.conf) i regulom KOLEJKA_REGULY.
  // Ta lista rzadzi WYLACZNIE przekierowaniem do poczekalni: odsylamy tylko
  // stamtad, gdzie faktycznie jest czego bronic.
  //
  // Przy bramkowaniu CALEGO serwisu (web w kolejce od pierwszego kliku) jest
  // to po prostu kazda sciezka. Gdybys wrocil do bramkowania samych sciezek
  // zakupu, wpisz tu ich liste — inaczej wygasly slot wyrzucalby do kolejki
  // z dowolnej podstrony, takze takiej, ktora wcale nie jest bramkowana.
  //
  // Ping NIE jest tym filtrem objety: dopoki mamy token, slot trzeba
  // podtrzymywac wszedzie. Zajrzenie do profilu na minute w trakcie zakupow
  // nie moze kosztowac miejsca w kolejce — TTL slotu to ~30 s, wiec przerwa
  // w pingu szybko konczy sie powrotem na koniec.
  //
  // W WebView aplikacji ten skrypt nic nie robi: apka jest wykluczona z bramki
  // po User-Agencie (pomin_ua), wiec nie ma ciastka z tokenem i start() konczy
  // sie od razu.
  var BRAMKOWANE = /^\/(n-kup-bilet|n-dodaj-bilet-zewnetrzny|n-bilety-zewnetrzne-formularz)/;

  function bramkowana() {
    return BRAMKOWANE.test(location.pathname);
  }

  function cookie(nazwa) {
    var m = document.cookie.match("(?:^|;\\s*)" + nazwa + "=([^;]*)");
    return m ? decodeURIComponent(m[1]) : null;
  }

  function token() { return cookie("kolejka_token"); }

  // wydarzenie zakodowane w tokenie: id|wydarzenie|exp|podpis
  function wydarzenieZTokenu() {
    var t = token();
    if (!t) { return "glowna"; }
    var czesci = t.split("|");
    return czesci.length === 4 ? czesci[1] : "glowna";
  }

  function doPoczekalni() {
    location.href = "/poczekalnia/?wydarzenie=" + encodeURIComponent(wydarzenieZTokenu())
      + "&powrot=" + encodeURIComponent(location.pathname + location.search);
  }

  function ping() {
    var t = token();
    if (!t) { return; } // brak tokenu = nie mamy slotu, nie ma czego podtrzymywac
    fetch("/poczekalnia/api/heartbeat", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Kolejka-Token": t },
      keepalive: true
    })
    .then(function (r) {
      if (r.status === 410 || r.status === 401) {
        // slot przepadl albo token wygasl — wracamy do kolejki
        zatrzymaj();
        if (bramkowana()) { doPoczekalni(); }
      }
      // odswiezony token przychodzi w Set-Cookie — nic do roboty
    })
    .catch(function () { /* chwilowy brak sieci — kolejny ping za INTERWAL_MS */ });
  }

  function start() {
    if (stoper || !token()) { return; }
    ping();
    stoper = setInterval(ping, INTERWAL_MS);
  }

  function zatrzymaj() {
    if (stoper) { clearInterval(stoper); stoper = null; }
  }

  var Poczekalnia = {
    /**
     * Wywołać tuż przed redirectem do P24 — przedłuża TTL slotu na czas
     * płatności (KOLEJKA_PLATNOSC_TTL, zgrany z czasNaPotwierdzenieZakupu).
     */
    idePlacic: function (poZapisie) {
      var t = token();
      if (!t) { if (poZapisie) { poZapisie(); } return; }
      zatrzymaj(); // po redirekcie i tak nie ma juz naszej strony
      fetch("/poczekalnia/api/platnosc", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-Kolejka-Token": t },
        keepalive: true
      }).catch(function () {}).finally(function () {
        if (poZapisie) { poZapisie(); }
      });
    },

    /** Zwolnienie slotu — po zakupie albo przy świadomej rezygnacji. */
    zwolnij: function () {
      zatrzymaj();
      var t = token();
      if (!t) { return; }
      navigator.sendBeacon("/poczekalnia/api/zwolnij?token=" + encodeURIComponent(t));
    },

    start: start,
    zatrzymaj: zatrzymaj
  };

  // UWAGA: celowo NIE zwalniamy slotu na pagehide/beforeunload — te zdarzenia
  // odpalaja sie takze przy zwyklej nawigacji miedzy krokami koszyka i przy
  // redirekcie do P24. Porzucona sesje (zamknieta karta) sprzata krotki TTL
  // heartbeatu (~30 s). Jawne zwolnienie: Poczekalnia.zwolnij() na stronie
  // podziekowania albo przy przycisku rezygnacji.

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

  okno.Poczekalnia = Poczekalnia;
})(window);
