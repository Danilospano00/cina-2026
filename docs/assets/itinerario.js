// Accordion dell'itinerario: apertura da hash e toggle «apri tutto».
(function () {
  var schede = Array.prototype.slice.call(document.querySelectorAll("details.stop"));
  if (!schede.length) return;

  // I link in arrivo da altre pagine (index, hotel) puntano a #shenzhen, #guangzhou…
  // Senza questo la scheda resta chiusa e l'ancora sembra rotta.
  function apriDaHash() {
    var id = decodeURIComponent(location.hash.slice(1));
    if (!id) return;
    var el = document.getElementById(id);
    if (el && el.tagName === "DETAILS") {
      el.open = true;
      el.scrollIntoView();
    }
  }

  var bottone = document.getElementById("apri-tutto");

  function aggiornaBottone() {
    if (!bottone) return;
    var tutteAperte = schede.every(function (d) { return d.open; });
    bottone.textContent = tutteAperte ? "Chiudi tutto" : "Apri tutto";
  }

  if (bottone) {
    bottone.addEventListener("click", function () {
      var apri = !schede.every(function (d) { return d.open; });
      schede.forEach(function (d) { d.open = apri; });
      aggiornaBottone();
    });
  }

  schede.forEach(function (d) { d.addEventListener("toggle", aggiornaBottone); });

  window.addEventListener("hashchange", apriDaHash);
  apriDaHash();
  aggiornaBottone();
})();
