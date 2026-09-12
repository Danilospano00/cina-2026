/* Deck del talk: navigazione, schermo intero, cronometro di prova.
   Lo scorrimento orizzontale è dello scroll-snap del CSS: qui si sincronizzano
   soltanto i pallini, i tasti e il tempo. Senza JS il deck si scorre a swipe. */
(function () {
  var deck = document.getElementById("deck");
  if (!deck) return;
  var slide = [].slice.call(deck.querySelectorAll(".slide"));
  var wrap = document.getElementById("deckwrap");
  var dots = [].slice.call(document.querySelectorAll("#dots button"));
  var eti = document.getElementById("etichetta");
  var crono = document.getElementById("crono");
  var budget = slide.map(function (s) { return +s.dataset.secondi || 0; });
  var tot = budget.reduce(function (a, b) { return a + b; }, 0);
  var i = 0;
  var t0 = null;
  var tick = null;

  // offsetLeft è relativo al body, non al contenitore di scroll: la differenza
  // dalla prima slide è l'unica misura che vale come coordinata di scorrimento.
  function pos(k) {
    return slide[k].offsetLeft - slide[0].offsetLeft;
  }

  function mmss(s) {
    s = Math.max(0, Math.round(s));
    return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2);
  }

  // Secondi previsti dall'inizio fino alla fine della slide n.
  function fino(n) {
    var s = 0;
    for (var k = 0; k <= n; k++) s += budget[k];
    return s;
  }

  function aggiorna() {
    dots.forEach(function (d, k) {
      d.classList.toggle("on", k === i);
      d.setAttribute("aria-current", k === i ? "true" : "false");
    });
    if (eti) eti.textContent = (i + 1) + " / " + slide.length + " · " + budget[i] + "s";
  }

  // Sempre istantaneo: su un contenitore con scroll-snap e scrollbar nascosta
  // Chrome ignora behavior:"smooth", e per un deck il taglio secco è il gesto
  // giusto comunque. Lo swipe resta fluido, quello lo anima il browser.
  function vai(n) {
    i = Math.max(0, Math.min(slide.length - 1, n));
    deck.scrollLeft = pos(i);
    aggiorna();
  }

  // Chi comanda è lo scroll: swipe e tasti finiscono entrambi qui.
  var attesa;
  deck.addEventListener("scroll", function () {
    clearTimeout(attesa);
    attesa = setTimeout(function () {
      var c = deck.scrollLeft + deck.clientWidth / 2;
      var vicino = 0;
      var min = Infinity;
      slide.forEach(function (s, k) {
        var d = Math.abs(pos(k) + s.offsetWidth / 2 - c);
        if (d < min) { min = d; vicino = k; }
      });
      if (vicino !== i) { i = vicino; aggiorna(); }
    }, 90);
  }, { passive: true });

  dots.forEach(function (d, k) {
    d.addEventListener("click", function () { vai(k); });
  });

  var prev = document.getElementById("prev");
  var next = document.getElementById("next");
  if (prev) prev.addEventListener("click", function () { vai(i - 1); });
  if (next) next.addEventListener("click", function () { vai(i + 1); });

  // --- cronometro: parte al primo avanzamento, confronta col budget --------
  function disegna() {
    if (!crono) return;
    var el = t0 ? (Date.now() - t0) / 1000 : 0;
    var atteso = fino(i);
    var scarto = el - atteso;
    crono.textContent = mmss(el) + " / " + mmss(tot);
    crono.className = "crono" + (!t0 ? "" : scarto > 12 ? " tardi" : scarto < -12 ? " avanti" : " ok");
    crono.title = t0
      ? (scarto >= 0 ? "+" : "−") + mmss(Math.abs(scarto)) + " rispetto alla fine della slide " + (i + 1)
      : "Il cronometro parte al primo avanzamento";
  }

  function parti() {
    if (t0) return;
    t0 = Date.now();
    tick = setInterval(disegna, 250);
    disegna();
  }

  var azzera = document.getElementById("azzera");
  if (azzera) azzera.addEventListener("click", function () {
    clearInterval(tick);
    t0 = null;
    tick = null;
    vai(0);
    disegna();
  });

  // --- schermo intero -----------------------------------------------------
  var pieno = document.getElementById("pieno");
  function schermo() {
    var t = wrap || deck;
    if (document.fullscreenElement) document.exitFullscreen();
    else if (t.requestFullscreen) t.requestFullscreen();
    else if (t.webkitRequestFullscreen) t.webkitRequestFullscreen();
  }
  if (pieno) pieno.addEventListener("click", schermo);
  document.addEventListener("fullscreenchange", function () {
    document.body.classList.toggle("proiezione", !!document.fullscreenElement);
    // Il riquadro cambia dimensione: la slide corrente va riallineata.
    setTimeout(function () { vai(i); }, 60);
  });

  // --- note per chi parla -------------------------------------------------
  var bnote = document.getElementById("bnote");
  if (bnote) bnote.addEventListener("click", function () {
    var on = document.body.classList.toggle("con-note");
    bnote.setAttribute("aria-pressed", on ? "true" : "false");
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    var k = ev.key;
    if (k === "ArrowRight" || k === "PageDown" || k === " ") { parti(); vai(i + 1); }
    else if (k === "ArrowLeft" || k === "PageUp") { vai(i - 1); }
    else if (k === "Home") { vai(0); }
    else if (k === "End") { vai(slide.length - 1); }
    else if (k === "f" || k === "F") { schermo(); }
    else if (k === "n" || k === "N") { if (bnote) bnote.click(); }
    else return;
    ev.preventDefault();
  });

  if (next) next.addEventListener("click", parti);
  aggiorna();
  disegna();
})();
