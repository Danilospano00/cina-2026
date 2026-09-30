#!/usr/bin/env python3
"""Ritaglia da OpenStreetMap (build giornaliera Protomaps) una mappa vettoriale per tappa.

Output: tiles/<slug>.pmtiles, che build.py copia in docs/tiles/. Il sito li disegna con
protomaps-leaflet e il service worker li salva sul telefono per l'uso senza rete.

Non gira dentro build.py: scarica dalla rete e ci mette un minuto. Va rilanciato solo
se cambia l'area da coprire (nuovi locali lontani, un hotel spostato, data/offline.json).

    python3 mappe_offline.py            # tutte le tappe
    python3 mappe_offline.py chengdu    # una sola

Serve la CLI `pmtiles` (brew install pmtiles).
"""
import json
import math
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).parent
MAPPE = ROOT / "data" / "mappe"
CONF = json.loads((ROOT / "data" / "offline.json").read_text(encoding="utf-8"))
OUT = ROOT / "tiles"

BUILDS = "https://build-metadata.protomaps.dev/builds.json"


def ultima_build():
    req = urllib.request.Request(BUILDS, headers={"User-Agent": "cina-2026-site"})
    with urllib.request.urlopen(req) as r:
        builds = json.load(r)
    return "https://build.protomaps.com/" + builds[-1]["key"]


def riquadro(lat_min, lon_min, lat_max, lon_max, m):
    """Allarga un riquadro di m metri per lato."""
    dlat = m / 111_320
    dlon = m / (111_320 * math.cos(math.radians((lat_min + lat_max) / 2)))
    return lat_min - dlat, lon_min - dlon, lat_max + dlat, lon_max + dlon


def anello(b):
    lat_min, lon_min, lat_max, lon_max = b
    return [[[lon_min, lat_min], [lon_max, lat_min], [lon_max, lat_max],
             [lon_min, lat_max], [lon_min, lat_min]]]


def regione(d):
    """Area dei locali (zone, pin, metro, landmark) + un riquadro per ogni punto extra."""
    punti = [p for z in d["zones"] for p in z["poly"]]
    punti += [x["coord"] for k in ("venues", "metro", "landmarks") for x in d.get(k, [])]
    lats = [p[0] for p in punti]
    lons = [p[1] for p in punti]
    poligoni = [anello(riquadro(min(lats), min(lons), max(lats), max(lons), CONF["margine_m"]))]
    for x in CONF["extra"].get(d["slug"], []):
        lat, lon = x["coord"]
        poligoni.append(anello(riquadro(lat, lon, lat, lon, CONF["raggio_m"])))
    return {"type": "MultiPolygon", "coordinates": poligoni}


def main():
    if not shutil.which("pmtiles"):
        sys.exit("Manca la CLI pmtiles: brew install pmtiles")
    solo = set(sys.argv[1:])
    mappe = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(MAPPE.glob("*.json"))]
    mappe = [d for d in mappe if not solo or d["slug"] in solo]

    sorgente = ultima_build()
    print(f"  sorgente {sorgente}")
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for d in mappe:
            geo = pathlib.Path(tmp) / f'{d["slug"]}.geojson'
            geo.write_text(json.dumps(regione(d)), encoding="utf-8")
            dest = OUT / f'{d["slug"]}.pmtiles'
            subprocess.run(
                ["pmtiles", "extract", sorgente, str(dest),
                 f"--region={geo}", f'--maxzoom={CONF["maxzoom"]}'],
                check=True, capture_output=True,
            )
            print(f'  {d["slug"]:<10} {dest.stat().st_size / 1e6:5.1f} MB')


if __name__ == "__main__":
    main()
