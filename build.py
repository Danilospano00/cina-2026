#!/usr/bin/env python3
"""
Genera il sito statico del viaggio in Cina del Sud da data/*.json.

Output in docs/ , che è la cartella pubblicata da GitHub Pages.

Sezioni:
  index.html       riepilogo, conto alla rovescia, le nove tappe
  itinerario.html  tappa per tappa
  mappe.html       indice delle sette mappe nightlife
  mappe/<slug>.html + kml/<slug>.kml
  voli.html        opzioni di volo internazionale
  treni.html       le nove tratte ferroviarie
  hotel.html       stato delle nove prenotazioni
  checklist.html   preparativi, con spunte salvate sul telefono

Uso:  python3 build.py
"""
import hashlib
import html
import json
import math
import pathlib
import shutil
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
MAPPE = DATA / "mappe"
STATIC = ROOT / "static"
OUT = ROOT / "docs"

SEZIONI = [
    ("index.html", "Riepilogo"),
    ("itinerario.html", "Itinerario"),
    ("mappe.html", "Mappe"),
    ("voli.html", "Voli"),
    ("treni.html", "Treni"),
    ("hotel.html", "Hotel"),
    ("checklist.html", "Checklist"),
]

TIPI = {
    "club": {"label": "Club / elettronica", "colore": "#e8590c", "icona": "C"},
    "pub": {"label": "Pub / craft beer", "colore": "#2f9e44", "icona": "P"},
    "live": {"label": "Livehouse / band", "colore": "#9c36b5", "icona": "L"},
    "expat": {"label": "Expat / internazionale", "colore": "#1098ad", "icona": "E"},
}

PRECISIONE = {
    "poi": ("esatta", "Geocodifica sul punto (OSM)"),
    "strada": ("livello strada", "Il pin cade sulla via giusta, non sul civico"),
    "approssimativa": ("approssimativa", "Derivata dall'indirizzo: può scostare di 100-300 m"),
    "non verificata": ("NON verificata", "Posizione dedotta, da confermare su Amap prima di andarci"),
}

e = html.escape

# Impronta dei file statici: finisce in coda agli URL come ?v=... . Senza,
# dopo un deploy il telefono continua a servire CSS e JS dalla cache.
VER = {}


def asset(nome):
    return f"{nome}?v={VER.get(nome, '0')}"


# --- datum shift -----------------------------------------------------------
# La Cina impone per legge un offset sulle coordinate pubbliche (GCJ-02).
# OSM/GPS usano WGS-84. Amap/Baidu/Dianping usano GCJ-02 (Baidu ancora BD-09).
# Senza conversione i pin si spostano di ~300-600 m.
_A = 6378245.0
_EE = 0.00669342162296594323


def _tf_lat(x, y):
    r = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    r += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    r += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return r


def _tf_lon(x, y):
    r = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    r += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    r += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return r


def wgs84_to_gcj02(lat, lon):
    """WGS-84 -> GCJ-02. Serve per aprire un punto in Amap senza sfasamento."""
    dlat = _tf_lat(lon - 105.0, lat - 35.0)
    dlon = _tf_lon(lon - 105.0, lat - 35.0)
    rad = lat / 180.0 * math.pi
    magic = 1 - _EE * math.sin(rad) ** 2
    sqrt_magic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrt_magic) * math.pi)
    dlon = (dlon * 180.0) / (_A / sqrt_magic * math.cos(rad) * math.pi)
    return round(lat + dlat, 6), round(lon + dlon, 6)


# --- link ------------------------------------------------------------------
def booking_url(query, checkin, checkout):
    q = urllib.parse.urlencode(
        {
            "ss": query,
            "checkin": checkin,
            "checkout": checkout,
            "group_adults": 1,
            "no_rooms": 1,
            "group_children": 0,
        }
    )
    return "https://www.booking.com/searchresults.it.html?" + q


def trip_url(city, checkin, checkout):
    q = urllib.parse.urlencode({"city": city, "checkin": checkin, "checkout": checkout, "adult": 1})
    return "https://it.trip.com/hotels/list?" + q


def hostelworld_url(city, checkin, checkout):
    q = urllib.parse.urlencode({"search_keywords": city, "dateFrom": checkin, "dateTo": checkout})
    return "https://www.hostelworld.com/search?" + q


def amap_url(lat, lon, nome):
    glat, glon = wgs84_to_gcj02(lat, lon)
    q = urllib.parse.urlencode({"position": f"{glon},{glat}", "name": nome, "coordinate": "gaode"})
    return "https://uri.amap.com/marker?" + q


# --- guscio ----------------------------------------------------------------
def pagina(titolo, corpo, attiva, depth=0, testa="", coda="", main_class="", body_class=""):
    """Guscio comune: intestazione, navigazione, corpo. depth = livelli sotto docs/."""
    rel = "../" * depth
    nav = "".join(
        '<a href="{}{}"{}>{}</a>'.format(rel, f, ' class="on"' if f == attiva else "", e(lab))
        for f, lab in SEZIONI
    )
    mc = f' class="{main_class}"' if main_class else ""
    bc = f' class="{body_class}"' if body_class else ""
    return f"""<!doctype html>
<html lang="it"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(titolo)}</title>
<meta name="description" content="Viaggio nel sud della Cina, 3-27 novembre 2026: itinerario, mappe, voli, treni, hotel.">
<meta name="theme-color" content="#c2410c">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Cina 2026">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="{rel}manifest.webmanifest">
<link rel="apple-touch-icon" href="{rel}assets/icon-180.png">
<link rel="icon" href="{rel}assets/icon-180.png">
<link rel="stylesheet" href="{rel}assets/{asset("app.css")}">
{testa}</head><body{bc}>
<header class="top"><div class="top-in">
 <a class="brand" href="{rel}index.html"><b>Sud della Cina</b><span>3-27 nov 2026</span></a>
 <nav>{nav}</nav>
</div></header>
<main{mc}>{corpo}</main>
{coda}</body></html>"""


def lista(voci, cls=""):
    if not voci:
        return ""
    c = f' class="{cls}"' if cls else ""
    return "<ul{}>{}</ul>".format(c, "".join(f"<li>{e(v)}</li>" for v in voci))


def tabella(intestazioni, righe, cls=""):
    """righe: liste di celle <td> già formattate. cls="tight" per le tabelle
    strette, che su telefono stanno in larghezza senza scorrimento."""
    th = "".join(f"<th>{e(x)}</th>" for x in intestazioni)
    tr = "".join("<tr>{}</tr>".format("".join(celle)) for celle in righe)
    c = f' class="{cls}"' if cls else ""
    return (
        f'<div class="scroll"><table{c}><thead><tr>{th}</tr></thead>'
        f"<tbody>{tr}</tbody></table></div>"
    )


SOTTOTITOLO = (
    "<h4 style=\"margin:11px 0 4px;font-size:12px;text-transform:uppercase;"
    "letter-spacing:.5px;color:var(--ink-3)\">{}</h4>"
)


# --- pagina: riepilogo -----------------------------------------------------
def build_home(viaggio, treni, voli):
    tot_notti = sum(t["notti"] for t in viaggio["tappe"])
    con_mappa = [t for t in viaggio["tappe"] if t["mappa"]]

    righe = []
    for t in viaggio["tappe"]:
        link = (
            f'<a href="mappe/{e(t["mappa"])}.html">mappa</a>'
            if t["mappa"]
            else '<span class="muted">—</span>'
        )
        wk = ' <span class="tag soft">weekend</span>' if t["weekend"] else ""
        righe.append(
            [
                f'<td><a href="itinerario.html#{e(t["id"])}"><b>{e(t["nome"])}</b></a> '
                f'<span class="muted">{e(t["nome_zh"])}</span>{wk}</td>',
                f'<td>{e(t["date"])}</td>',
                f'<td class="num">{t["notti"]}</td>',
                f"<td>{link}</td>",
            ]
        )

    scelta = next(o for o in voli["opzioni"] if o["id"] == voli["scelta"])
    aperti = [
        ("Volo A/R Italia ⇄ Hong Kong",
         f'obiettivo sotto 1000€, il minimo verificato oggi e\' {scelta["prezzo"]}', "voli.html"),
        ("9 hotel su Trip.com", "uno per tappa, nessuno ancora prenotato", "hotel.html"),
        ("8 tratte in treno", "le vendite aprono 15 giorni prima di ogni partenza", "treni.html"),
        ("Preparativi", "VPN, eSIM, pagamenti, assicurazione", "checklist.html"),
    ]
    aperti_html = "".join(
        f'<div class="card"><div class="stop-head"><h3>{e(a)}</h3>'
        f'<span class="when"><a class="btn" href="{e(u)}">apri</a></span></div>'
        f'<p class="arrivo" style="margin:0">{e(b)}</p></div>'
        for a, b, u in aperti
    )

    corpo = f"""<div class="page">
<h1>{e(viaggio["titolo"])}</h1>
<p class="lede">{e(viaggio["sottotitolo"])}</p>
<div class="card">
  <div id="countdown" data-partenza="{e(viaggio["partenza"])}" data-rientro="{e(viaggio["rientro"])}"
       style="font-size:19px;font-weight:600;margin-bottom:6px">&nbsp;</div>
  <p class="muted" style="margin:0">{e(viaggio["rotta"])}</p>
  <p class="muted" style="margin:8px 0 0">{len(viaggio["tappe"])} tappe · {tot_notti} notti ·
   {len(con_mappa)} mappe nightlife · {treni["totale_eur"]}€ di treni interni</p>
</div>

<h2>Le tappe</h2>
{tabella(["Tappa", "Date", "Notti", "Nightlife"], righe, "tight")}

<h2>Da chiudere</h2>
{aperti_html}

<h2>Regole del viaggio</h2>
<div class="card">{lista(viaggio["regole"])}</div>

<div class="warn"><b>Prima di partire:</b> installa e testa la VPN in Italia — in Cina i siti dei
provider sono bloccati e non la scarichi più. Scarica anche i KML delle mappe e le mappe offline
di Organic Maps: funzionano senza rete e senza VPN.</div>
</div>"""
    return pagina(
        "Sud della Cina — 3-27 novembre 2026",
        corpo,
        "index.html",
        coda=f'<script src="assets/{asset("countdown.js")}"></script>',
    )


# --- pagina: itinerario ----------------------------------------------------
def build_itinerario(viaggio):
    schede = []
    for i, t in enumerate(viaggio["tappe"], 1):
        wk = ' <span class="tag soft">weekend</span>' if t["weekend"] else ""
        mappa = (
            f'<a class="btn" href="mappe/{e(t["mappa"])}.html">Mappa nightlife</a>'
            if t["mappa"]
            else ""
        )
        schede.append(
            f'<div class="card" id="{e(t["id"])}">'
            f'<div class="stop-head"><span class="tag grey">{i}</span>'
            f'<h3>{e(t["nome"])}</h3><span class="zh">{e(t["nome_zh"])}</span>{wk}'
            f'<span class="when">{e(t["date"])} · {t["notti"]} notti</span></div>'
            f'<p class="arrivo">{e(t["arrivo"])}</p>'
            + SOTTOTITOLO.format("Cosa vedere")
            + lista(t["cosa_vedere"])
            + SOTTOTITOLO.format("Cibo")
            + lista(t["cibo"])
            + f'<div class="links">{mappa}'
            f'<a class="btn" href="hotel.html#{e(t["id"])}">Hotel</a></div></div>'
        )

    corpo = f"""<div class="page narrow">
<h1>Itinerario</h1>
<p class="lede">{e(viaggio["rotta"])}</p>
{"".join(schede)}
<div class="card"><div class="stop-head"><span class="tag">27</span>
 <h3>Rientro</h3><span class="when">27 novembre</span></div>
 <p class="arrivo" style="margin:0">Volo internazionale da Hong Kong.</p></div>
</div>"""
    return pagina("Itinerario — Sud della Cina", corpo, "itinerario.html")


# --- pagina: indice mappe --------------------------------------------------
def build_mappe_index(mappe, viaggio):
    righe = []
    for d in sorted(mappe, key=lambda x: x["checkin"]):
        top = sorted(d["zones"], key=lambda z: z["rank"])[0]
        incerti = sum(
            1 for x in d["venues"] if x["precisione"] in ("approssimativa", "non verificata")
        )
        righe.append(
            [
                f'<td><a href="mappe/{e(d["slug"])}.html"><b>{e(d["city"])}</b></a> '
                f'<span class="muted">{e(d["city_zh"])}</span></td>',
                f'<td>{e(d["tappa"].split(" — ")[0])}</td>',
                f'<td>{e(top["nome"])}</td>',
                f'<td class="num">{len(d["venues"])}</td>',
                f'<td class="num">{incerti}</td>',
                f'<td><a class="btn" href="kml/{e(d["slug"])}.kml" download>KML</a></td>',
            ]
        )

    senza = " e ".join(t["nome"] for t in viaggio["tappe"] if not t["mappa"])

    corpo = f"""<div class="page">
<h1>Mappe nightlife</h1>
<p class="lede">Per ogni tappa: dove dormire per avere la vita notturna a piedi, con i locali
veri che rendono una zona tale. Link a Booking e Trip.com con le date già impostate.</p>

{tabella(["Tappa", "Date", "Zona consigliata", "Locali", "Da riverificare", "Offline"], righe)}

<p class="muted">{e(senza)} non hanno una mappa: villaggio Dong e montagna, nessuna scena serale
da mappare.</p>

<h2>Usarle sul telefono</h2>
<div class="card">
<p style="margin-top:0">Le pagine <b>HTML</b> servono adesso, per scegliere la zona e prenotare.
Richiedono rete: in Cina continentale funzionano con la VPN attiva.</p>
<p>I file <b>KML</b> servono in loco. Installa <a href="https://organicmaps.app" target="_blank"
rel="noopener">Organic Maps</a>, scarica le mappe delle regioni <b>prima di partire</b>, poi apri
il KML con l'app: i segnaposti finiscono nei preferiti e restano leggibili <b>senza rete e senza
VPN</b>.</p>
<p style="margin-bottom:0">Regioni da scaricare: Guangdong, Guangxi, Guizhou, Sichuan, Chongqing,
Hong Kong.</p>
</div>

<div class="warn"><b>Coordinate:</b> tutti i dati sono in WGS-84, lo standard di GPS e
OpenStreetMap. La Cina impone per legge un offset sulle mappe pubbliche (GCJ-02): a Chengdu la
differenza è di circa 360 m. Non incollare mai una coordinata di queste pagine dentro Amap o
Baidu — usa il link «Apri in Amap» nel popup di ogni locale, che fa la conversione da solo.</div>

<h2>Quanto fidarsi</h2>
<div class="card">
<p style="margin-top:0">Le <b>zone</b> sono ancorate a punti geocodificati su OpenStreetMap in
tutte le tappe: si possono usare per prenotare. È la precisione dei <b>singoli pin</b> che
cambia.</p>
{lista([
  "Chengdu, Shenzhen, Guangzhou — geocodificati uno per uno con controllo dei bounding box. I più affidabili.",
  "Chongqing — cluster confermati, civici dedotti dall'indirizzo.",
  "Hong Kong — zone geocodificate, civici dei bar no. Qui però Google Maps funziona: cerca il nome.",
  "Guiyang — scena molto povera, due soli pin. La sera vera è Qingyun Road, e si mangia.",
  "Yangshuo — tutto su West Street, 500 m. I pin sono indicativi: la via è la mappa.",
])}
<p class="muted" style="margin-bottom:0">I locali marcati «approssimativa» o «non verificata»
vanno confermati su Amap prima di prendere un Didi.</p>
</div>
</div>"""
    return pagina("Mappe nightlife — Sud della Cina", corpo, "mappe.html")


# --- pagina: una mappa -----------------------------------------------------
def build_mappa(d):
    zones = sorted(d["zones"], key=lambda z: z["rank"])
    ci, co = d["checkin"], d["checkout"]

    cards = []
    for z in zones:
        scarta = z["rank"] >= 90
        badge = "DA EVITARE" if scarta else "#" + str(z["rank"])
        links = ""
        if not scarta:
            bq = f'{z["nome"].split(" + ")[0]}, {d["city"]}'
            links = (
                '<div class="links">'
                f'<a class="btn" href="{e(booking_url(bq, ci, co))}" target="_blank" '
                f'rel="noopener">Booking · {e(bq)}</a>'
                f'<a class="btn" href="{e(trip_url(d["city"], ci, co))}" target="_blank" '
                f'rel="noopener">Trip.com · {e(d["city"])}</a></div>'
            )
        met = " · ".join(e(m) for m in z["metro"])
        cards.append(
            f'<div class="zcard{" off" if scarta else ""}" data-zone="{e(z["id"])}" '
            f'style="--zc:{e(z["colore"])}">'
            f'<div class="stop-head"><span class="rk">{badge}</span>'
            f'<h3>{e(z["nome"])}</h3><span class="zh">{e(z["nome_zh"])}</span>'
            f'<span class="when">{e(z["distretto"])}</span></div>'
            f'<p style="margin:0 0 9px;font-size:14px">{e(z["verdetto"])}</p>'
            f'{lista(z["perche"], "pro")}{lista(z["contro"], "con")}'
            f'<p class="muted" style="margin:0 0 8px">Metro: {met}</p>{links}</div>'
        )

    leg = "".join(
        f'<span><i style="background:{x["colore"]}"></i>{e(x["label"])}</span>'
        for x in TIPI.values()
    )

    payload = {
        "center": d["center"],
        "zoom": d["zoom"],
        "zones": zones,
        "venues": d["venues"],
        "metro": d.get("metro", []),
        "landmarks": d.get("landmarks", []),
        "tipi": TIPI,
        "precisione": PRECISIONE,
        "amap": {x["nome"]: amap_url(x["coord"][0], x["coord"][1], x["nome"]) for x in d["venues"]},
    }

    corpo = f"""<div id="wrap">
<div id="side">
 <h1 style="font-size:22px">{e(d["city"])} <span class="muted">{e(d["city_zh"])}</span></h1>
 <p class="muted" style="margin:0 0 2px">Dove dormire per avere la vita notturna a piedi</p>
 <p class="muted" style="margin:0">{e(d["tappa"])}</p>
 <div class="legend">{leg}</div>
 <div class="links" style="margin-bottom:14px">
  <a class="btn" href="../kml/{e(d["slug"])}.kml" download>Scarica KML</a>
  <a class="btn" href="../mappe.html">Tutte le mappe</a>
 </div>
 <div class="warn" style="margin:0 0 16px">{e(d["note"])}
  Ogni locale ha il link «Apri in Amap» già convertito in GCJ-02.</div>
 {"".join(cards)}
</div>
<div id="map"></div>
</div>"""

    testa = '<link rel="stylesheet" href="../assets/leaflet/leaflet.css">\n'
    coda = (
        '<script type="application/json" id="mapdata">'
        + json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
        + "</script>\n"
        '<script src="../assets/leaflet/leaflet.js"></script>\n'
        f'<script src="../assets/{asset("mappa.js")}"></script>'
    )
    return pagina(
        f'{d["city"]} — dove dormire per la vita notturna',
        corpo,
        "mappe.html",
        depth=1,
        testa=testa,
        coda=coda,
        main_class="mapmain",
        body_class="mapbody",
    )


# --- pagina: voli ----------------------------------------------------------
def build_voli(voli):
    opzioni = []
    for o in voli["opzioni"]:
        badge = (
            '<span class="tag">SCELTA</span>'
            if o["consigliata"]
            else '<span class="tag grey">alternativa</span>'
        )
        vett = tabella(
            ["Vettore", "Prezzo", "Durata", "Alleanza", "Nota"],
            [
                [
                    f'<td><b>{e(x["nome"])}</b></td>',
                    f'<td class="num">{e(x["prezzo"])}</td>',
                    f'<td>{e(x["durata"])}</td>',
                    f'<td>{e(x["alleanza"])}</td>',
                    f'<td class="muted">{e(x["nota"])}</td>',
                ]
                for x in o["vettori"]
            ],
        )
        opzioni.append(
            f'<div class="card"><div class="stop-head">{badge}<h3>{e(o["titolo"])}</h3>'
            f'<span class="when">{e(o["prezzo"])}</span></div>'
            f'<p class="arrivo">{e(o["come_funziona"])}</p>'
            f'{vett}{lista(o["pro"], "pro")}{lista(o["contro"], "con")}</div>'
        )

    giudizi = {"ottimo": "ok", "buono": "soft", "medio": "grey", "scarso": "grey", "evita": "grey"}
    gate = tabella(
        ["Gateway", "Prezzo", "Andata", "Ritorno", "Vettore", "Giudizio"],
        [
            [
                f'<td><b>{e(g["citta"])}</b></td>',
                f'<td class="num">{e(g["prezzo"])}</td>',
                f'<td>{e(g["andata"])}</td>',
                f'<td>{e(g["ritorno"])}</td>',
                f'<td>{e(g["vettore"])}</td>',
                f'<td><span class="tag {giudizi[g["giudizio"]]}">{e(g["giudizio"])}</span> '
                f'<span class="muted">{e(g["nota"])}</span></td>',
            ]
            for g in voli["gateway"]
        ],
    )

    esiti = {"scelto": "ok", "ok": "soft", "caro": "grey", "evita": "grey"}
    date = tabella(
        ["Partenza", "Rientro", "Giorni", "Esito", "Nota"],
        [
            [
                f'<td>{e(c["partenza"])}</td>',
                f'<td>{e(c["rientro"])}</td>',
                f'<td class="num">{c["giorni"]}</td>',
                f'<td><span class="tag {esiti[c["esito"]]}">{e(c["esito"])}</span></td>',
                f'<td class="muted">{e(c["nota"])}</td>',
            ]
            for c in voli["date"]["coppie"]
        ],
    )

    ricerche = "".join(
        f'<a class="btn" href="{e(r["url"])}" target="_blank" rel="noopener">{e(r["nome"])}</a>'
        for r in voli["ricerche"]
    )

    corpo = f"""<div class="page">
<h1>{e(voli["titolo"])}</h1>
<p class="lede">{e(voli["obiettivo"])}</p>
<div class="warn">{e(voli["nota"])}</div>

<h2>Le tre strade</h2>
{"".join(opzioni)}

<h2>Cerca ora</h2>
<div class="card"><div class="links" style="margin:0">{ricerche}</div>
<p class="muted" style="margin:10px 0 0">Controlla sempre anche Roma, non solo Milano.</p></div>

<h2>Round-trip per gateway</h2>
<p class="muted">Con il filtro «entrambe le tratte sotto le 18-19h».</p>
{gate}

<h2>Date</h2>
<div class="warn">{e(voli["date"]["regola"])}</div>
<p class="muted">Finestra consigliata: <b>{e(voli["date"]["finestra"])}</b>.</p>
{date}

<h2>Come sono stati ottenuti questi numeri</h2>
<div class="card">{lista(voli["metodo"])}</div>
</div>"""
    return pagina("Voli — Sud della Cina", corpo, "voli.html")


# --- pagina: treni ---------------------------------------------------------
def build_treni(treni):
    righe = []
    for t in treni["tratte"]:
        flag = "" if t["verificato"] else ' <span class="tag grey">da verificare</span>'
        nota = f'<br><span class="muted">{e(t["note"])}</span>' if t["note"] else ""
        righe.append(
            [
                f'<td class="num">{t["n"]}</td>',
                f'<td><b>{e(t["da"])}</b> → <b>{e(t["a"])}</b>{flag}{nota}</td>',
                f'<td>{e(t["treno"])}</td>',
                f'<td>{e(t["durata"])}</td>',
                f'<td class="num">{t["cny"]} CNY<br><b>{t["eur"]}€</b></td>',
            ]
        )
    righe.append(
        [
            "<td></td>",
            "<td><b>Totale</b></td>",
            "<td></td>",
            "<td></td>",
            f'<td class="num">{treni["totale_cny"]} CNY<br><b>{treni["totale_eur"]}€</b></td>',
        ]
    )

    p = treni["prenotazione"]
    crit = treni["criticita"]

    corpo = f"""<div class="page">
<h1>{e(treni["titolo"])}</h1>
<p class="lede">{e(treni["nota"])}</p>

{tabella(["#", "Tratta", "Treno", "Durata", "2ª classe"], righe)}

<div class="warn"><b>{e(crit["titolo"])}</b>{lista(crit["punti"])}</div>

<h2>Prenotare</h2>
<div class="card">
<p style="margin-top:0">Le vendite aprono <b>{e(p["apertura_vendite"])}</b>: non si può comprare
tutto in anticipo. Metti in calendario il giorno di apertura per il G905, che è l'unico
irrinunciabile.</p>
<p>Su <b>{e(p["dove"])}</b> la commissione è {e(p["commissione"])}. L'alternativa è
{e(p["alternativa"])}.</p>
<div class="links" style="margin:0">
 <a class="btn primary" href="{e(p["url"])}" target="_blank" rel="noopener">Trip.com treni</a>
 <a class="btn" href="https://www.12306.cn" target="_blank" rel="noopener">12306 ufficiale</a>
</div></div>

<h2>Note</h2>
<div class="card">{lista([
  "Il rientro G905 da solo vale il 46% del budget treni. Il volo CKG → HKG a volte scende sotto i 100€: confronta.",
  "Tratte 2 e 8 hanno anche treni ordinari K/T a ~25 CNY, ma fermano in stazioni diverse e ci mettono il doppio.",
  "Tratta 7: il C778 impiega 1h45 in più del G2447 e costa uguale o poco meno. Prendi il G.",
  "Porta sempre il passaporto: serve per ritirare i biglietti e per salire.",
])}</div>
</div>"""
    return pagina("Treni — Sud della Cina", corpo, "treni.html")


# --- pagina: hotel ---------------------------------------------------------
def build_hotel(viaggio):
    stati = {"da cercare": "grey", "cercato": "soft", "prenotato": "ok", "confermato": "ok"}
    schede = []
    for t in viaggio["tappe"]:
        h = t["hotel"]
        st = stati.get(h["stato"], "grey")
        mappa_link = (
            f'<a class="btn" href="mappe/{e(t["mappa"])}.html">Zone sulla mappa</a>'
            if t["mappa"]
            else ""
        )
        schede.append(
            f'<div class="card" id="{e(t["id"])}"><div class="stop-head">'
            f'<h3>{e(t["nome"])}</h3><span class="zh">{e(t["nome_zh"])}</span>'
            f'<span class="tag {st}">{e(h["stato"])}</span>'
            f'<span class="when">{e(t["date"])} · {t["notti"]} notti</span></div>'
            f'<p class="arrivo"><b>Zona:</b> {e(h["zona"])}<br>'
            f'<span class="muted">{e(h["note"])}</span></p>'
            f'<div class="links">'
            f'<a class="btn primary" href="{e(trip_url(h["cerca"], t["checkin"], t["checkout"]))}" '
            f'target="_blank" rel="noopener">Trip.com</a>'
            f'<a class="btn" href="{e(booking_url(h["cerca"], t["checkin"], t["checkout"]))}" '
            f'target="_blank" rel="noopener">Booking</a>'
            f'<a class="btn" href="{e(hostelworld_url(h["cerca"], t["checkin"], t["checkout"]))}" '
            f'target="_blank" rel="noopener">Hostelworld</a>'
            f"{mappa_link}</div></div>"
        )

    corpo = f"""<div class="page narrow">
<h1>Hotel</h1>
<p class="lede">Nove strutture, una per tappa. Camera privata sempre, mai dormitorio. I link
portano alla ricerca con le date già impostate per 1 adulto.</p>

<div class="warn"><b>WiFi:</b> è il vincolo vero, non il prezzo. Le sere sono di lavoro: prima di
prenotare leggi le recensioni che parlano di connessione, soprattutto a Yangshuo e Zhaoxing.</div>

{"".join(schede)}

<h2>Come si aggiorna lo stato</h2>
<div class="card">
<p style="margin-top:0">Il campo <code>stato</code> di ogni tappa sta in
<code>data/viaggio.json</code>. Valori: <code>da cercare</code>, <code>cercato</code>,
<code>prenotato</code>, <code>confermato</code>. Cambialo e rilancia
<code>python3 build.py</code>.</p>
<p style="margin-bottom:0"><b>Il repo è pubblico:</b> non mettere qui codici di prenotazione,
numeri di carta o dati del passaporto. Solo nome struttura, zona e stato.</p>
</div>
</div>"""
    return pagina("Hotel — Sud della Cina", corpo, "hotel.html")


# --- pagina: checklist -----------------------------------------------------
def build_checklist(c):
    gruppi = []
    for g in c["gruppi"]:
        voci = []
        for x in g["voci"]:
            crit = ' <span class="tag soft">critico</span>' if x["critico"] else ""
            voci.append(
                '<div class="check">'
                f'<input type="checkbox" id="cb-{e(x["id"])}" data-id="{e(x["id"])}">'
                f'<label for="cb-{e(x["id"])}">'
                f'<span class="t">{e(x["testo"])}{crit}</span>'
                f'<span class="d">{e(x["dettaglio"])}</span></label></div>'
            )
        gruppi.append(
            '<div class="card" data-group>'
            f'<div class="stop-head"><h3>{e(g["nome"])}</h3>'
            '<span class="when count">0 / 0</span></div>'
            f'<p class="muted" style="margin:0 0 4px">{e(g["scadenza"])}</p>'
            '<div class="progress"><i></i></div>'
            f'{"".join(voci)}</div>'
        )

    corpo = f"""<div class="page narrow">
<h1>{e(c["titolo"])}</h1>
<p class="lede">{e(c["nota"])}</p>
<div class="card"><b id="totale">0 di 0 completate</b>
 <button id="reset" class="btn" style="float:right;cursor:pointer;font:inherit;font-size:13px">
 Azzera</button></div>
{"".join(gruppi)}
</div>"""
    return pagina(
        "Checklist — Sud della Cina",
        corpo,
        "checklist.html",
        coda=f'<script src="assets/{asset("checklist.js")}"></script>',
    )


# --- KML -------------------------------------------------------------------
def kml_style(sid, color_hex):
    """color_hex '#rrggbb' -> KML aabbggrr."""
    r, g, b = color_hex[1:3], color_hex[3:5], color_hex[5:7]
    return (
        f'<Style id="{sid}"><IconStyle><color>ff{b}{g}{r}</color><scale>1.1</scale>'
        "<Icon><href>http://maps.google.com/mapfiles/kml/paddle/wht-blank.png</href></Icon>"
        "</IconStyle>"
        f"<LineStyle><color>ff{b}{g}{r}</color><width>3</width></LineStyle>"
        f"<PolyStyle><color>26{b}{g}{r}</color></PolyStyle></Style>"
    )


def build_kml(d):
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
        f'<name>{e(d["city"])} — nightlife e zone dove dormire</name>',
        f'<description>{e(d["tappa"])}. Coordinate WGS-84. '
        "Importa in Organic Maps o Maps.me: funziona offline, senza VPN.</description>",
    ]
    for t, v in TIPI.items():
        out.append(kml_style(f"t_{t}", v["colore"]))
    for z in d["zones"]:
        out.append(kml_style(f'z_{z["id"]}', z["colore"]))
    out.append(kml_style("metro", "#333333"))

    # zone: contorno come LineString (Organic Maps rende le tracce) + poligono
    out.append("<Folder><name>Zone dove dormire</name>")
    for z in sorted(d["zones"], key=lambda x: x["rank"]):
        ring = z["poly"] + [z["poly"][0]]
        coords = " ".join(f"{lon},{lat},0" for lat, lon in ring)
        tag = "NON DORMIRCI" if z["rank"] >= 90 else "#" + str(z["rank"])
        desc = (
            f'{tag} — {z["distretto"]}\n\n{z["verdetto"]}\n\n'
            + "PRO\n"
            + "\n".join("· " + x for x in z["perche"])
            + "\n\nCONTRO\n"
            + "\n".join("· " + x for x in z["contro"])
            + "\n\nMetro: "
            + " · ".join(z["metro"])
        )
        out.append(
            f'<Placemark><name>{e(tag)} {e(z["nome"])}</name>'
            f"<description>{e(desc)}</description>"
            f'<styleUrl>#z_{e(z["id"])}</styleUrl>'
            "<MultiGeometry>"
            f"<LineString><tessellate>1</tessellate><coordinates>{coords}</coordinates></LineString>"
            "<Polygon><outerBoundaryIs><LinearRing>"
            f"<coordinates>{coords}</coordinates>"
            "</LinearRing></outerBoundaryIs></Polygon>"
            "</MultiGeometry></Placemark>"
        )
        if z["dormi_qui"]:
            lat, lon = z["dormi_qui"]
            hint = (
                "Centro consigliato per la ricerca hotel. "
                f'Raggio utile ~{z["raggio_m"]} m a piedi.'
            )
            out.append(
                f'<Placemark><name>★ Cerca hotel qui — {e(z["nome"])}</name>'
                f"<description>{e(hint)}</description>"
                f'<styleUrl>#z_{e(z["id"])}</styleUrl>'
                f"<Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>"
            )
    out.append("</Folder>")

    for t, meta in TIPI.items():
        vs = [x for x in d["venues"] if x["tipo"] == t]
        if not vs:
            continue
        out.append(f'<Folder><name>{e(meta["label"])}</name>')
        for x in vs:
            plabel = PRECISIONE.get(x["precisione"], ("?", ""))[0]
            desc = (
                f'{x["nome_zh"]}\n{x["indirizzo"]}\n\n{x["vibe"]}\n\n'
                f'Prezzo: {x["prezzo"]}\nOrari: {x["orari"]}\nStato: {x["stato"]}\n'
                f"Posizione: {plabel}"
            )
            lat, lon = x["coord"]
            out.append(
                f'<Placemark><name>{e(x["nome"])}</name>'
                f"<description>{e(desc)}</description>"
                f"<styleUrl>#t_{t}</styleUrl>"
                f"<Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>"
            )
        out.append("</Folder>")

    if d.get("metro"):
        out.append("<Folder><name>Metro</name>")
        for s in d["metro"]:
            lat, lon = s["coord"]
            out.append(
                f'<Placemark><name>M {e(s["nome"])}</name>'
                f'<description>{e(s["linee"])}</description><styleUrl>#metro</styleUrl>'
                f"<Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>"
            )
        out.append("</Folder>")

    out.append("</Document></kml>")
    return "\n".join(out)


# --- icone e manifest ------------------------------------------------------
def build_icone(dest):
    """Icona: carsi del Li River al tramonto. Serve alla schermata Home di iOS."""
    from PIL import Image, ImageDraw

    def disegna(px):
        img = Image.new("RGB", (px, px), "#1b1b1f")
        dr = ImageDraw.Draw(img)
        u = px / 100.0
        dr.rectangle([0, 0, px, 62 * u], fill="#c2410c")
        dr.ellipse([70 * u, 12 * u, 84 * u, 26 * u], fill="#ffe0c4")
        for punti, col in (
            ([(-5, 62), (16, 26), (37, 62)], "#7a2708"),
            ([(28, 62), (52, 18), (76, 62)], "#96310a"),
            ([(60, 62), (82, 34), (105, 62)], "#7a2708"),
        ):
            dr.polygon([(x * u, y * u) for x, y in punti], fill=col)
        dr.rectangle([0, 62 * u, px, px], fill="#16323f")
        for y, w in ((72, 34), (80, 52), (88, 26)):
            dr.rectangle([(50 - w / 2) * u, y * u, (50 + w / 2) * u, (y + 2.5) * u], fill="#2b5a70")
        return img

    for px in (180, 512):
        disegna(px).save(dest / f"icon-{px}.png")


def build_manifest():
    return json.dumps(
        {
            "name": "Sud della Cina — 3-27 novembre 2026",
            "short_name": "Cina 2026",
            "start_url": ".",
            "scope": ".",
            "display": "standalone",
            "background_color": "#f6f5f3",
            "theme_color": "#c2410c",
            "lang": "it",
            "icons": [
                {"src": "assets/icon-180.png", "sizes": "180x180", "type": "image/png"},
                {
                    "src": "assets/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


# --- main ------------------------------------------------------------------
def main():
    if not MAPPE.exists():
        sys.exit(f"Manca {MAPPE}")

    viaggio = json.loads((DATA / "viaggio.json").read_text(encoding="utf-8"))
    treni = json.loads((DATA / "treni.json").read_text(encoding="utf-8"))
    voli = json.loads((DATA / "voli.json").read_text(encoding="utf-8"))
    check = json.loads((DATA / "checklist.json").read_text(encoding="utf-8"))
    mappe = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(MAPPE.glob("*.json"))]

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    (OUT / "mappe").mkdir()
    (OUT / "kml").mkdir()

    for nome in ("app.css", "mappa.js", "checklist.js", "countdown.js"):
        sorgente = STATIC / nome
        shutil.copy2(sorgente, OUT / "assets" / nome)
        VER[nome] = hashlib.md5(sorgente.read_bytes()).hexdigest()[:8]
    shutil.copytree(STATIC / "leaflet", OUT / "assets" / "leaflet")
    build_icone(OUT / "assets")
    (OUT / "manifest.webmanifest").write_text(build_manifest(), encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    def w(nome, testo):
        (OUT / nome).write_text(testo, encoding="utf-8")

    w("index.html", build_home(viaggio, treni, voli))
    w("itinerario.html", build_itinerario(viaggio))
    w("mappe.html", build_mappe_index(mappe, viaggio))
    w("voli.html", build_voli(voli))
    w("treni.html", build_treni(treni))
    w("hotel.html", build_hotel(viaggio))
    w("checklist.html", build_checklist(check))

    for d in mappe:
        w(f'mappe/{d["slug"]}.html', build_mappa(d))
        w(f'kml/{d["slug"]}.kml', build_kml(d))

    n_locali = sum(len(d["venues"]) for d in mappe)
    n_voci = sum(len(g["voci"]) for g in check["gruppi"])
    print(f"  {len(SEZIONI)} sezioni")
    print(f"  {len(mappe)} mappe, {n_locali} locali, {len(mappe)} KML")
    print(f'  {len(viaggio["tappe"])} tappe, {len(treni["tratte"])} tratte, {n_voci} voci checklist')
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
