/* Registra il service worker e gestisce il download delle mappe offline. */
(function () {
  var script = document.currentScript;
  var base = script.dataset.base || './';
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register(base + 'sw.js');

  if (!navigator.onLine) document.documentElement.classList.add('offline');
  window.addEventListener('online', function () { document.documentElement.classList.remove('offline'); });
  window.addEventListener('offline', function () { document.documentElement.classList.add('offline'); });

  var box = document.getElementById('offline');
  if (!box || !('caches' in window)) return;
  var btn = box.querySelector('button');
  var stato = box.querySelector('.stato');
  var mappe = JSON.parse(box.dataset.mappe); // [{slug, city, url, mb}]
  var CACHE = 'cina2026-mappe';

  function presenti() {
    return caches.open(CACHE).then(function (c) {
      return Promise.all(mappe.map(function (m) {
        return c.match(new URL(m.url, location.href).href).then(function (r) { return !!r; });
      }));
    });
  }

  function mostra() {
    return presenti().then(function (ok) {
      var n = ok.filter(Boolean).length;
      mappe.forEach(function (m, i) {
        var cella = document.querySelector('[data-offline="' + m.slug + '"]');
        if (cella) cella.textContent = ok[i] ? '✓' : '—';
      });
      if (n === mappe.length) {
        stato.textContent = 'Tutte le ' + n + ' mappe sono sul telefono.';
        btn.textContent = 'Riscarica';
      } else {
        stato.textContent = n + ' di ' + mappe.length + ' mappe sul telefono.';
      }
      return ok;
    });
  }

  btn.addEventListener('click', function () {
    btn.disabled = true;
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist();
    caches.open(CACHE).then(function (c) {
      var i = 0;
      function prossima() {
        if (i >= mappe.length) return;
        var m = mappe[i++];
        stato.textContent = 'Scarico ' + m.city + ' (' + i + ' di ' + mappe.length + ', ' + m.mb + ' MB)…';
        var url = new URL(m.url, location.href).href;
        return fetch(url, { cache: 'reload' }).then(function (r) {
          if (!r.ok) throw new Error(m.city + ': HTTP ' + r.status);
          return c.put(url, r);
        }).then(prossima);
      }
      return prossima();
    }).then(mostra).catch(function (err) {
      stato.textContent = 'Download interrotto: ' + err.message + '. Riprova con una rete stabile.';
    }).then(function () { btn.disabled = false; });
  });

  mostra();
})();
