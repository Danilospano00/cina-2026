/* Service worker: tiene il sito sul telefono per l'uso senza rete.
   build.py sostituisce i tre segnaposto qui sotto a ogni build. */
var VERSIONE = '__VERSIONE__';
var PRECACHE = __PRECACHE__;
var MAPPE = __MAPPE__;

var APP = 'cina2026-app-' + VERSIONE;
// Le mappe stanno in una cache a parte che sopravvive ai deploy: sono 30 MB e le
// scarica l'utente a mano. Cambiano URL (?v=) solo se si rigenerano i .pmtiles.
var CACHE_MAPPE = 'cina2026-mappe';

self.addEventListener('install', function (ev) {
  ev.waitUntil(
    caches.open(APP).then(function (c) {
      return c.addAll(PRECACHE.map(function (u) { return new Request(u, { cache: 'reload' }); }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (ev) {
  var valide = MAPPE.map(function (u) { return new URL(u, self.registration.scope).href; });
  ev.waitUntil(
    caches.keys().then(function (nomi) {
      return Promise.all(nomi.filter(function (n) {
        return n.indexOf('cina2026-app-') === 0 && n !== APP;
      }).map(function (n) { return caches.delete(n); }));
    }).then(function () {
      // via le mappe di una generazione precedente
      return caches.open(CACHE_MAPPE).then(function (c) {
        return c.keys().then(function (reqs) {
          return Promise.all(reqs.filter(function (r) {
            return valide.indexOf(r.url) < 0;
          }).map(function (r) { return c.delete(r); }));
        });
      });
    }).then(function () { return self.clients.claim(); })
  );
});

/* pmtiles legge il file a pezzi con richieste Range. In cache c'è il file intero:
   si risponde 206 con la fetta richiesta. */
function fetta(risposta, range) {
  var m = /bytes=(\d+)-(\d*)/.exec(range || '');
  if (!m) return risposta;
  return risposta.arrayBuffer().then(function (buf) {
    var da = +m[1];
    var a = m[2] ? Math.min(+m[2], buf.byteLength - 1) : buf.byteLength - 1;
    if (da >= buf.byteLength) {
      return new Response(null, { status: 416, headers: { 'Content-Range': 'bytes */' + buf.byteLength } });
    }
    var pezzo = buf.slice(da, a + 1);
    return new Response(pezzo, {
      status: 206,
      headers: {
        'Content-Type': 'application/octet-stream',
        'Content-Length': String(pezzo.byteLength),
        'Content-Range': 'bytes ' + da + '-' + a + '/' + buf.byteLength
      }
    });
  });
}

function conTimeout(promessa, ms) {
  return new Promise(function (ok, ko) {
    var t = setTimeout(function () { ko(new Error('timeout')); }, ms);
    promessa.then(function (r) { clearTimeout(t); ok(r); }, function (e) { clearTimeout(t); ko(e); });
  });
}

function dallaCache(req) {
  return caches.match(req, { ignoreSearch: true }).then(function (r) {
    if (r) return r;
    // start_url "." → la cartella: in cache c'è come index.html
    if (req.url.slice(-1) === '/') return caches.match(req.url + 'index.html');
  });
}

self.addEventListener('fetch', function (ev) {
  var req = ev.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.slice(-8) === '.pmtiles') {
    ev.respondWith(
      caches.open(CACHE_MAPPE).then(function (c) {
        return c.match(req.url);
      }).then(function (r) {
        return r ? fetta(r, req.headers.get('range')) : fetch(req);
      })
    );
    return;
  }

  // Pagine: prima la rete, così un deploy si vede subito. In Cina github.io può
  // essere lento o bloccato: dopo 4 secondi vince la copia sul telefono.
  if (req.mode === 'navigate') {
    ev.respondWith(
      conTimeout(fetch(req), 4000).then(function (r) {
        if (r.ok) {
          var copia = r.clone();
          caches.open(APP).then(function (c) { c.put(req, copia); });
        }
        return r;
      }).catch(function () {
        return dallaCache(req).then(function (r) {
          return r || caches.match(new URL('index.html', self.registration.scope).href);
        });
      })
    );
    return;
  }

  // CSS, JS, icone, KML: hanno ?v=<hash> o non cambiano, quindi prima la cache.
  ev.respondWith(
    caches.match(req).then(function (r) {
      return r || fetch(req).catch(function () { return dallaCache(req); });
    })
  );
});
