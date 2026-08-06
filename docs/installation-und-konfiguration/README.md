# Installation und Konfiguration

## Docker Compose

```bash
cp .env.example .env
# ARK_API_KEY und gewünschte Werte in .env eintragen
docker compose up --build -d
curl http://localhost:8080/health
curl http://localhost:3000/health
```

Die erwartete Antwort ist `{"status":"ok"}`. Die interaktive OpenAPI-Ansicht
liegt standardmäßig unter `http://localhost:8080/docs`.

## Lokaler Prozess

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
modelark-video-proxy
```

## Umgebungsvariablen

| Variable | Standard | Zweck |
|---|---:|---|
| `ARK_API_KEY` | leer | BytePlus ModelArk API Key; für echte Requests Pflicht |
| `ARK_BASE_URL` | AP-Southeast ModelArk `/api/v3` | Upstream-Basis-URL |
| `PROXY_API_KEY` | leer | optionaler Bearer-Key für alle API-Routen außer Health/Referenzmedien |
| `PUBLIC_BASE_URL` | leer | öffentliche HTTPS-URL des Proxys; für hochgeladene Videos nötig |
| `DEFAULT_MODEL` | Seedance 2.0 | Modell-ID, wenn kein Modell mitgesendet wird |
| `MODEL_MAP` | `{}` | JSON-Abbildung stabiler Alias → freigeschaltete Modell-/Endpoint-ID |
| `DEFAULT_GENERATE_AUDIO` | `true` | Standard für synchron erzeugtes Audio |
| `MEDIA_DIR` | `./data/references` | temporäre Referenzablage |
| `MEDIA_TTL_SECONDS` | `86400` | lokale Aufbewahrungsdauer |
| `MEDIA_CLEANUP_INTERVAL_SECONDS` | `900` | periodische Medienbereinigung |
| `MAX_UPLOAD_BYTES` | `209715200` | maximale Uploadgröße |
| `REQUEST_TIMEOUT_SECONDS` | `60` | Timeout für ModelArk-API-Aufrufe |
| `DOWNLOAD_TIMEOUT_SECONDS` | `600` | Timeout für Ergebnisstreams |
| `MAX_UPSTREAM_CONNECTIONS` | `100` | maximale parallele ModelArk-Verbindungen |
| `MAX_KEEPALIVE_CONNECTIONS` | `20` | wiederverwendete ModelArk-Verbindungen |
| `ALLOWED_DOWNLOAD_HOST_SUFFIXES` | BytePlus/Volces | erlaubte Hosts für Ergebnisdownloads |

Beispiel für Alias-Mapping:

```dotenv
DEFAULT_MODEL=dreamina-seedance-2-0-fast-260128
MODEL_MAP={"seedance":"dreamina-seedance-2-0-fast-260128"}
PROXY_API_KEY=replace-with-a-long-random-value
PUBLIC_BASE_URL=https://video-proxy.example.com
```

`.env` ist von Git ausgeschlossen. API-Schlüssel dürfen weder committed noch
in Logs, Fehlermeldungen oder Screenshots veröffentlicht werden.

## Web Studio

Für den zweiten Compose-Service werden `UI_PASSWORD` und ein zufälliger
`UI_SESSION_SECRET` mit mindestens 32 Zeichen benötigt. Das Studio läuft auf
Port 3000 und verwendet intern `PROXY_API_KEY`. Alle UI-Variablen und der
temporäre Lebenszyklus sind unter
[Seedance Web Studio](../web-studio/README.md) dokumentiert.
