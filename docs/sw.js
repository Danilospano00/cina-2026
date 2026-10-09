/* Service worker: tiene il sito sul telefono per l'uso senza rete.
   build.py sostituisce i tre segnaposto qui sotto a ogni build. */
var VERSIONE = "5c58a978d4";
var PRECACHE = ["./", "assets/app.css?v=9ca9286d", "assets/checklist.js?v=84b18e25", "assets/countdown.js?v=ecfe49a6", "assets/icon-180.png", "assets/icon-512.png", "assets/itinerario.js?v=1c26837a", "assets/leaflet/images/layers-2x.png", "assets/leaflet/images/layers.png", "assets/leaflet/images/marker-icon-2x.png", "assets/leaflet/images/marker-icon.png", "assets/leaflet/images/marker-shadow.png", "assets/leaflet/leaflet.css", "assets/leaflet/leaflet.js", "assets/mappa.js?v=acb48e16", "assets/protomaps/LICENSE", "assets/protomaps/protomaps-leaflet.js", "assets/pwa.js?v=31061a40", "checklist.html", "hotel.html", "index.html", "itinerario.html", "kml/chengdu.kml", "kml/chongqing.kml", "kml/guangzhou.kml", "kml/guiyang.kml", "kml/hongkong.kml", "kml/shenzhen.kml", "kml/yangshuo.kml", "manifest.webmanifest", "mappe/chengdu.html", "mappe/chongqing.html", "mappe/guangzhou.html", "mappe/guiyang.html", "mappe/hongkong.html", "mappe/shenzhen.html", "mappe/yangshuo.html", "mappe.html", "serate.html", "shenzhen.html", "treni.html"];
var MAPPE = ["tiles/chengdu.pmtiles?v=01b70e60", "tiles/chongqing.pmtiles?v=d481c0f1", "tiles/guangzhou.pmtiles?v=fa626c35", "tiles/guiyang.pmtiles?v=cad75052", "tiles/hongkong.pmtiles?v=9586cc12", "tiles/shenzhen.pmtiles?v=e252625a", "tiles/yangshuo.pmtiles?v=9a27ba62"];

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
