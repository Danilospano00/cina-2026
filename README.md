# Sud della Cina — 5-27 novembre 2026

Sito statico del viaggio: itinerario, mappe nightlife, voli, treni, hotel, checklist.
Generato da file JSON, pubblicato su GitHub Pages, pensato per stare come segnalibro
sulla schermata Home di un iPhone.

## Come funziona

```
data/          i contenuti. È l'unica cosa da modificare a mano
  viaggio.json   le sette tappe, date, cosa vedere, stato hotel
                 (`hotel` accetta un oggetto o una lista: a Hong Kong sono due strutture)
  treni.json     le sette tratte ferroviarie
  voli.json      opzioni di volo internazionale
  checklist.json preparativi
  mappe/*.json   una mappa nightlife per tappa
static/        CSS, JS e Leaflet vendorizzato
build.py       genera tutto
docs/          OUTPUT. È quello che GitHub Pages pubblica: non modificarlo a mano
```

Rigenerare:

```bash
.venv/bin/python build.py
```

Serve **Pillow** (genera le icone PWA). Il python di Homebrew è externally-managed e non
lo installa a sistema, quindi c'è un venv in `site/.venv`. Se manca:

```bash
python3 -m venv .venv && .venv/bin/pip install Pillow
```

Attenzione: `build.py` fa `rmtree(docs/)` **prima** di generare le icone. Se Pillow manca,
il build crasha con `docs/` già svuotata — non è un problema, basta rilanciare col venv.

Anteprima locale (il browser blocca `file://` per gli script):

```bash
cd docs && python3 -m http.server 8778
# http://127.0.0.1:8778/
```

## Aggiungere una sezione

1. Un file in `data/`.
2. Una funzione `build_<nome>()` in `build.py` che ritorna `pagina(titolo, corpo, "<file>.html")`.
3. Una riga in `SEZIONI` e una chiamata `w("<file>.html", build_<nome>(...))` in `main()`.

Il guscio — intestazione, navigazione, tema chiaro/scuro, meta per iOS — arriva da
`pagina()` e non va replicato.

## Aggiungere una mappa

Copia `data/mappe/chengdu.json` e cambia i dati.

- `zones[]` — `rank` 1 = migliore, `rank: 99` per «esiste ma non dormirci».
  `poly` sono i vertici `[lat, lon]`, `dormi_qui` il centro per cercare l'hotel,
  `raggio_m` quanto ha senso allargare.
- `venues[]` — `tipo` tra `club`, `pub`, `live`, `expat`. `zona` è l'`id` di una zona
  oppure `null` se il locale sta fuori da tutte.
- `precisione` — onestà sul pin: `poi` (geocodificato sul punto), `strada` (via giusta,
  civico no), `approssimativa` (±100-300 m), `non verificata` (dedotta, da confermare).

`build.py` non verifica niente da solo: se sposti un poligono, ricontrolla che i locali
ci cadano dentro.

## Il punto delle coordinate

**Tutte le coordinate nei JSON sono WGS-84**, quelle di GPS e OpenStreetMap.

La Cina impone per legge un offset sulle coordinate delle mappe pubbliche: Amap, Baidu e
Dianping usano **GCJ-02** (Baidu addirittura BD-09, un ulteriore offset sopra GCJ-02). A
Chengdu la differenza è di **circa 360 m** — la distanza tra «sotto l'hotel» e «dall'altra
parte del quartiere».

- Non incollare mai una coordinata di questi file dentro Amap o Baidu.
- Usa il link «Apri in Amap» nel popup di ogni locale: la conversione la fa `build.py`.
- Coordinate prese da Dianping o Amap sono GCJ-02: vanno convertite **all'indietro** prima
  di finire nel JSON.

Hong Kong è fuori dal problema: lì Google Maps funziona.

## Pubblicazione

GitHub Pages serve la cartella `docs/` del branch `main`. Dopo ogni modifica:

```bash
python3 build.py && git add -A && git commit -m "..." && git push
```

CSS e JS hanno un `?v=<hash>` in coda: senza, dopo un deploy il telefono continua a
servire la versione vecchia dalla cache.

## Il repo è pubblico

Non mettere nei JSON codici di prenotazione, numeri di carta, dati del passaporto o
indirizzi privati. Solo informazioni che potrebbe leggere chiunque.

Lo stato delle spunte della checklist non sta nel repo: vive nel `localStorage` del
browser, quindi resta sul telefono ed è per-dispositivo.

## Limiti dichiarati

- I locali sono **venue fissi**, non eventi datati: a novembre 2026 saranno quasi
  certamente ancora lì, ma il calendario delle serate va scoutato a ridosso.
- Fonti: Resident Advisor per i club, ricerca cinese per craft beer e livehouse,
  Nominatim/OSM per le coordinate.
- I prezzi dei treni sono di agosto 2026. Le tratte 4 (Yangshuo → Guiyang) e 6 (Chengdu →
  Chongqing West) sono nuove e le tariffe sono **derivate, mai lette su Trip.com**.
- Il volo internazionale è **prenotato** (HKG 6 nov 12:00 → 27 nov 08:10): la pagina Voli
  resta come traccia del metodo, non come listino.
- I locali marcati `approssimativa` o `non verificata` vanno confermati su Amap prima di
  prendere un Didi.
