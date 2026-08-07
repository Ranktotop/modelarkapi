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

Für die Entwicklung die eingecheckte VS-Code-Konfiguration **Local Full
Stack** aus `.vscode/launch.json` verwenden. Die folgenden Befehle dienen nur
der einmaligen Einrichtung der Python-Umgebung, nicht dem Serverstart:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
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
| `BYTEPLUS_ACCESS_KEY_ID` | leer | AK des dedizierten IAM-Users für die Assets API |
| `BYTEPLUS_SECRET_ACCESS_KEY` | leer | SK des IAM-Users; ausschließlich serverseitig |
| `BYTEPLUS_ASSET_GROUP_ID` | leer | verifizierte `group-…`-ID der Person |
| `BYTEPLUS_PROJECT_NAME` | `default` | gemeinsames Projekt von Gruppe und Inferenzendpunkt |
| `BYTEPLUS_ASSET_REGION` | `ap-southeast-1` | Signaturregion der Assets API |
| `BYTEPLUS_ASSET_ENDPOINT` | AP-Southeast Assets API | signierter ModelArk-OpenAPI-Endpunkt |
| `ASSET_JOB_DB` | `./data/proxy-jobs.db` | persistenter Zustand temporärer Asset-Jobs |
| `ASSET_POLL_INTERVAL_SECONDS` | `5` | Mindestabstand der `GetAsset`-Prüfungen |
| `ASSET_MAINTENANCE_INTERVAL_SECONDS` | `2` | Takt des nicht blockierenden Job-Workers |
| `ASSET_MAX_PROCESSING_SECONDS` | `3600` | maximale Asset-Aufbereitungszeit |
| `ASSET_JOB_TTL_SECONDS` | `86400` | maximale Job- und Remote-Asset-Lebenszeit |
| `ASSET_WORKER_CONCURRENCY` | `10` | parallele Asset-/Job-Worker |
| `ASSET_CLEANUP_RETRIES` | `5` | begrenzt den Exponenten des Cleanup-Backoffs |
| `ASSET_ORPHAN_CLEANUP_INTERVAL_SECONDS` | `900` | Abstand des Remote-Reconcilers |
| `ASSET_ORPHAN_TTL_SECONDS` | `86400` | Mindestalter verwaister App-Assets vor Löschung |

Beispiel für Alias-Mapping:

```dotenv
DEFAULT_MODEL=dreamina-seedance-2-0-fast-260128
MODEL_MAP={"seedance":"dreamina-seedance-2-0-fast-260128"}
PROXY_API_KEY=replace-with-a-long-random-value
PUBLIC_BASE_URL=https://video-proxy.example.com
```

`.env` ist von Git ausgeschlossen. API-Schlüssel dürfen weder committed noch
in Logs, Fehlermeldungen oder Screenshots veröffentlicht werden.

Die IAM-Einrichtung ist unter
[Real-Human-Assets](../real-human-assets/README.md#dedizierten-iam-user-und-aksk-anlegen)
Schritt für Schritt beschrieben.

## Web Studio

Für den zweiten Compose-Service werden `UI_PASSWORD` und ein zufälliger
`UI_SESSION_SECRET` mit mindestens 32 Zeichen benötigt. Das Studio läuft auf
Port 3000 und verwendet intern `PROXY_API_KEY`. Alle UI-Variablen und der
temporäre Lebenszyklus sind unter
[Seedance Web Studio](../web-studio/README.md) dokumentiert.
