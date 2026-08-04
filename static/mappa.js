/* Mappa nightlife di una tappa. I dati arrivano da <script id="mapdata"> */
(function () {
  var D = JSON.parse(document.getElementById('mapdata').textContent);

  var map = L.map('map').setView(D.center, D.zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap'
  }).addTo(map);

  function esc(s) {
    return String(s === null || s === undefined ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  // zone
  var zoneLayer = L.layerGroup().addTo(map);
  var zoneRef = {};
  D.zones.forEach(function (z) {
    var scarta = z.rank >= 90;
    var poly = L.polygon(z.poly, {
      color: z.colore,
      weight: 2,
      opacity: 0.85,
      fillColor: z.colore,
      fillOpacity: scarta ? 0.05 : 0.13,
      dashArray: scarta ? '6,5' : null
    }).addTo(zoneLayer);
    poly.bindTooltip(z.nome + (scarta ? ' — non dormirci' : ''), { sticky: true });
    zoneRef[z.id] = poly;
    if (z.dormi_qui) {
      L.circle(z.dormi_qui, {
        radius: z.raggio_m,
        color: z.colore,
        weight: 1.5,
        opacity: 0.9,
        fillOpacity: 0.07,
        dashArray: '3,4'
      })
        .addTo(zoneLayer)
        .bindTooltip('Cerca l\'hotel qui — raggio ' + z.raggio_m + ' m', { sticky: true });
    }
  });

  // locali
  var groups = {};
  Object.keys(D.tipi).forEach(function (t) {
    groups[t] = L.layerGroup().addTo(map);
  });

  D.venues.forEach(function (v) {
    var t = D.tipi[v.tipo];
    if (!t) return;
    var p = D.precisione[v.precisione] || ['?', ''];
    var bad = v.precisione === 'non verificata' || v.precisione === 'approssimativa';
    var m = L.circleMarker(v.coord, {
      radius: 7,
      color: '#fff',
      weight: 2,
      fillColor: t.colore,
      fillOpacity: 0.95
    });
    m.bindPopup(
      '<div class="pt">' + esc(v.nome) +
        (v.nome_zh ? ' <span class="pzh">' + esc(v.nome_zh) + '</span>' : '') + '</div>' +
      '<div class="padr">' + esc(v.indirizzo) + '</div>' +
      '<div class="pvibe">' + esc(v.vibe) + '</div>' +
      '<div class="pmeta">' + esc(v.prezzo) + ' · ' + esc(v.orari) +
        '<br>' + esc(v.stato) + '</div>' +
      '<span class="prec' + (bad ? ' bad' : '') + '" title="' + esc(p[1]) + '">posizione: ' +
        esc(p[0]) + '</span><br>' +
      '<a class="btn" style="margin-top:8px" target="_blank" rel="noopener" href="' +
        esc(D.amap[v.nome]) + '">Apri in Amap (GCJ-02) &rarr;</a>'
    );
    m.bindTooltip(v.nome, { direction: 'top' });
    m.addTo(groups[v.tipo]);
  });

  // metro e punti di riferimento
  var metroLayer = L.layerGroup().addTo(map);
  D.metro.forEach(function (s) {
    L.circleMarker(s.coord, {
      radius: 4.5,
      color: '#333',
      weight: 1.5,
      fillColor: '#fff',
      fillOpacity: 1
    })
      .bindTooltip('M ' + s.nome + ' (' + s.linee + ')', { direction: 'top' })
      .addTo(metroLayer);
  });

  var lmLayer = L.layerGroup().addTo(map);
  D.landmarks.forEach(function (l) {
    L.marker(l.coord, { opacity: 0.55 })
      .bindTooltip(l.nome, { direction: 'top' })
      .addTo(lmLayer);
  });

  var ctrl = {
    'Zone consigliate': zoneLayer,
    Metro: metroLayer,
    'Punti di riferimento': lmLayer
  };
  Object.keys(D.tipi).forEach(function (k) {
    ctrl[D.tipi[k].label] = groups[k];
  });
  L.control.layers(null, ctrl, { collapsed: window.innerWidth < 860 }).addTo(map);

  // click sulla scheda -> zoom sulla zona
  document.querySelectorAll('.zcard').forEach(function (c) {
    c.addEventListener('click', function (ev) {
      if (ev.target.tagName === 'A') return;
      var p = zoneRef[c.dataset.zone];
      if (!p) return;
      map.fitBounds(p.getBounds(), { padding: [40, 40] });
      if (window.innerWidth < 860) {
        document.getElementById('map').scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // Il contenitore sta dentro un layout flex con intestazione sticky: Leaflet
  // misura il div prima che il layout si assesti e il centro finisce altrove.
  // Rimisura e ricentra appena il browser ha finito di disporre la pagina.
  var box = document.getElementById('map');

  function risistema() {
    map.invalidateSize({ animate: false });
    map.setView(D.center, D.zoom, { animate: false });
  }

  requestAnimationFrame(risistema);
  window.addEventListener('load', risistema);

  if (window.ResizeObserver) {
    var primo = true;
    new ResizeObserver(function () {
      if (primo) {
        primo = false;
        return;
      }
      map.invalidateSize({ animate: false });
    }).observe(box);
  } else {
    window.addEventListener('resize', function () {
      map.invalidateSize();
    });
  }
})();
