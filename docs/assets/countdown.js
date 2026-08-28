/* Conto alla rovescia verso la partenza. */
(function () {
  var el = document.getElementById('countdown');
  if (!el) return;
  var partenza = new Date(el.dataset.partenza + 'T00:00:00');
  var rientro = new Date(el.dataset.rientro + 'T23:59:59');

  function giorni(a, b) {
    return Math.ceil((b - a) / 86400000);
  }

  function tick() {
    var ora = new Date();
    if (ora < partenza) {
      var g = giorni(ora, partenza);
      el.textContent = g === 1 ? 'Si parte domani' : 'Mancano ' + g + ' giorni alla partenza';
    } else if (ora <= rientro) {
      el.textContent = 'Viaggio in corso · giorno ' + (giorni(partenza, ora) + 1) +
        ' di ' + giorni(partenza, rientro);
    } else {
      el.textContent = 'Viaggio concluso';
    }
  }

  tick();
  setInterval(tick, 3600000);
})();
