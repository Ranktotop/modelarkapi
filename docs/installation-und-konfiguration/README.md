# Installation und Konfiguration

## Entwicklung: VS Code

Entwicklungsserver werden ausschließlich über die eingecheckte
VS-Code-Konfiguration **Local Full Stack** (`.vscode/launch.json`) gestartet. Sie
lädt die Secrets aus `.env` und startet Proxy (`8081`), Studio-Backend (`3000`)
und Vite-Frontend (`5173`). Einzelne Konfigurationen genügen, wenn nur eine
Komponente gebraucht wird. Ein direkter `uvicorn`- oder Vite-Start sowie
`docker compose up/run` sind für die Entwicklung nicht vorgesehen.

Die Python- und Node-Umgebung wird einmalig eingerichtet:

```bash
cp .env.example .env
# Werte eintragen; .env ist von Git ausgeschlossen
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
cd ui/frontend && npm ci
```

Nach dem Start zuerst die kostenfreien Prüfungen nutzen:

```bash
curl http://127.0.0.1:8081/health
curl -H "Authorization: Bearer $PROXY_API_KEY" \
  http://127.0.0.1:8081/v1/real-human/configuration
```

Ein Serverstart berechtigt zu keiner kostenpflichtigen oder biometrischen
Generierung.

## Deployment: Docker Compose

Docker ist für Image-/Build-Prüfungen und das Deployment reserviert und wird nur
auf ausdrückliche Anforderung gestartet:

```bash
docker compose up -d
curl http://localhost:5192/health   # Proxy
curl http://localhost:5191/health   # Studio
```

| Service | Image | Host-Port → Container | Volumes |
|---|---|---|---|
| `server` (Alias `modelarkapi_server`) | `ranktotop/modelarkapi:backend-${IMG_VERSION:-latest}` | `5192 → 8080` | `reference_media`, `server_state` (`/app/state`), `./secrets` (schreibgeschützt nach `/app/secrets`) |
| `ui` (Alias `modelarkapi_ui`) | `ranktotop/modelarkapi:frontend-${IMG_VERSION:-latest}` | `5191 → 3000` | `ui_state` (`/app/data`) |

Die erwartete Antwort von `/health` enthält `"status":"ok"`, `version`,
`credentials` (ModelArk, für Altclients) und `providers` (Zustand je Anbieter).
Die interaktive OpenAPI-Ansicht liegt unter `/docs`.

Der Compose-Stack setzt `REQUIRE_PROXY_API_KEY=true`, legt Datenbanken und
Outputs unter `/app/state` ab (`ASSET_JOB_DB`, `PROVIDER_JOB_DB`, `OUTPUT_DIR`)
und reicht die Anbieter-Variablen aus `.env` durch.

### Google-Zugangsdaten für Vertex AI

Die Service-Account-JSON gehört in `./secrets` (nicht in Git). In `.env` steht
nur der Dateiname:

```dotenv
VERTEX_PROJECT=mein-projekt
GOOGLE_CREDENTIALS_FILE=service-account.json
```

Compose setzt daraus `GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/service-account.json`.
Bleibt `GOOGLE_CREDENTIALS_FILE` leer, verwendet der Proxy Application Default
Credentials. Für lokale Läufe über VS Code steht in `.env` stattdessen der
Host-Pfad in `GOOGLE_APPLICATION_CREDENTIALS`.

## Umgebungsvariablen

Ein Anbieter ist aktiv, sobald seine Zugangsdaten gesetzt sind
(`ARK_API_KEY`/IAM, `GEMINI_API_KEY` oder `VERTEX_PROJECT`, `KLING_API_KEY`).
Ohne jeden Anbieter startet der Proxy mit einer Warnung.

### Proxy und Medien

| Variable | Standard | Zweck |
|---|---:|---|
| `PROXY_API_KEY` | leer | Bearer-Key für alle API-Routen außer Health und Referenzmedien |
| `REQUIRE_PROXY_API_KEY` | `false` | bei `true` Start nur mit mindestens 32 Zeichen langem Proxy-Key |
| `PUBLIC_BASE_URL` | leer | öffentliche HTTPS-URL des Proxys; für Uploads und `data:`-/Upload-Referenzen bei Seedance und Kling nötig |
| `MODEL_CACHE_TTL_SECONDS` | `300` | Cache-Dauer der live abgerufenen Modelllisten (ModelArk und Google) |
| `DEFAULT_GENERATE_AUDIO` | `true` | Seedance-Standard für `generate_audio` bei Modellen mit Audio |
| `MEDIA_DIR` | `./data/references` | temporäre Referenzablage |
| `MEDIA_TTL_SECONDS` | `86400` | lokale Aufbewahrungsdauer |
| `MEDIA_CLEANUP_INTERVAL_SECONDS` | `900` | periodische Medien- und Job-Bereinigung |
| `MAX_UPLOAD_BYTES` | `209715200` | maximale Größe eines Uploads (`input_reference`, `/v1/media/references`) |
| `MAX_INLINE_REFERENCE_BYTES` | `26214400` | maximale dekodierte Größe einer `data:`-Referenz |
| `REQUEST_TIMEOUT_SECONDS` | `60` | Timeout für Anbieter-API-Aufrufe |
| `OMNI_CREATE_TIMEOUT_SECONDS` | `600` | Timeout für das Anlegen einer Omni-Interaction; Vertex hält den Aufruf teils offen, bis das Video fertig ist (live beobachtet). Ein Create wird nie wiederholt |
| `DOWNLOAD_TIMEOUT_SECONDS` | `600` | Timeout für Ergebnisstreams und -downloads |
| `MAX_UPSTREAM_CONNECTIONS` | `100` | maximale parallele Anbieter-Verbindungen |
| `MAX_KEEPALIVE_CONNECTIONS` | `20` | wiederverwendete Verbindungen |
| `UPSTREAM_RETRY_ATTEMPTS` | `3` | Versuche je Anbieter-Aufruf bei Verbindungsfehlern (DNS, Connect) |
| `UPSTREAM_RETRY_BACKOFF_SECONDS` | `0.5` | Basiswartezeit des exponentiellen Retry-Backoffs |
| `UPSTREAM_RETRY_MAX_BACKOFF_SECONDS` | `5` | Obergrenze einer einzelnen Retry-Wartezeit |
| `PROMPT_GUIDES_DIR` | `./prompt_guides` | Ordner mit `manifest.yaml` und den Guides |
| `DEFAULT_PARAMETER_POLICY` | `strict` | `strict` oder `adapt`; gilt für alle Anbieter, wenn der Request kein `parameter_policy` setzt |

### Credential-Prüfung

| Variable | Standard | Zweck |
|---|---:|---|
| `CREDENTIAL_VALIDATION_INTERVAL_SECONDS` | `10800` | Abstand der erneuten Prüfung aller Anbieter |
| `CREDENTIAL_VALIDATION_TIMEOUT_SECONDS` | `10` | Timeout je einzelner Prüfung |
| `CREDENTIAL_REVALIDATION_INTERVAL_SECONDS` | `30` | verkürzter Abstand, solange ein Anbieter nicht `valid` ist |

### Seedance (BytePlus ModelArk)

| Variable | Standard | Zweck |
|---|---:|---|
| `ARK_API_KEY` | leer | ModelArk API Key; wird beim Start read-only geprüft |
| `ARK_BASE_URL` | AP-Southeast ModelArk `/api/v3` | Upstream-Basis-URL |
| `ALLOWED_DOWNLOAD_HOST_SUFFIXES` | `.bytepluses.com,.volces.com` | erlaubte Hosts für Ergebnisdownloads (kommagetrennt) |
| `BYTEPLUS_ACCESS_KEY_ID` | leer | AK des dedizierten IAM-Users für Management- und Assets-API |
| `BYTEPLUS_SECRET_ACCESS_KEY` | leer | SK des IAM-Users; ausschließlich serverseitig |
| `BYTEPLUS_ASSET_GROUP_ID` | leer | verifizierte `group-…`-ID der Person |
| `BYTEPLUS_PROJECT_NAME` | `default` | gemeinsames Projekt von Gruppe und Inferenzendpunkt |
| `BYTEPLUS_ASSET_REGION` | `ap-southeast-1` | Signaturregion der Assets API |
| `BYTEPLUS_ASSET_ENDPOINT` | `https://ark.ap-southeast-1.byteplusapi.com` | signierter ModelArk-OpenAPI-Endpunkt |

### Google (Veo, Gemini Omni)

| Variable | Standard | Zweck |
|---|---:|---|
| `GEMINI_API_KEY` | leer | Gemini Developer API |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` | Basis-URL der Gemini API |
| `VERTEX_PROJECT` | leer | Google-Cloud-Projekt für Vertex AI |
| `GOOGLE_APPLICATION_CREDENTIALS` | leer | Pfad der Service-Account-JSON; leer = Application Default Credentials |
| `GOOGLE_VEO_BACKEND` | `vertex` | `vertex` oder `gemini` |
| `GOOGLE_VEO_LOCATION` | `us-central1` | Vertex-Region für Veo (`global` ist erreichbar, siehe ADR-001) |
| `GOOGLE_OMNI_BACKEND` | `vertex` | `vertex`, `gemini` oder `both` |
| `GOOGLE_OMNI_LOCATION` | `global` | Vertex-Region für Omni |
| `GOOGLE_DOWNLOAD_HOST_SUFFIXES` | `.googleapis.com,.googleusercontent.com` | erlaubte Hosts für Google-Ergebnisse |
| `GOOGLE_CREDENTIALS_FILE` | leer | nur Compose: Dateiname in `./secrets` |

Ein Backend ist nur aktiv, wenn dessen Zugang gesetzt ist (`vertex` braucht
`VERTEX_PROJECT`, `gemini` braucht `GEMINI_API_KEY`). Für Veo und Omni kann je ein
Backend gewählt werden. `GOOGLE_OMNI_BACKEND=both` nutzt beide: GA-Omni-IDs
(`gemini-omni-1.1-flash`) laufen über die Gemini API, `-preview`-IDs über Vertex AI;
dafür sind `GEMINI_API_KEY` und `VERTEX_PROJECT` nötig. Ein Job pollt immer das
Backend, das ihn angelegt hat. Die Modellliste wird je Backend live gebildet
(Gemini: `models.list`; Vertex: Abruf der bekannten Publisher-Modelle).
Veo-Preview-IDs der Gemini API enden laut Google am 22.10.2026.

### Kling

| Variable | Standard | Zweck |
|---|---:|---|
| `KLING_API_KEY` | leer | Kling API Key |
| `KLING_BASE_URL` | `https://api-singapore.klingai.com` | API-Basis-URL |
| `KLING_COSTS_MIN_INTERVAL_SECONDS` | `1.0` | Mindestabstand zwischen Aufrufen von `GET /v1/providers/kling/account/costs` (der Proxy wartet, lehnt nicht ab) |
| `KLING_DOWNLOAD_HOST_SUFFIXES` | `.klingai.com,.kechuangai.com,.kwimgs.com,.inkwai.com` | erlaubte Hosts für Ergebnisse |

### Jobregister, Outputs und Webhooks

| Variable | Standard | Zweck |
|---|---:|---|
| `PROVIDER_JOB_DB` | `./data/provider-jobs.db` | SQLite-Register für Google- und Kling-Jobs, Webhooks |
| `PROVIDER_JOB_TTL_SECONDS` | `172800` | Lebensdauer von Jobs und Outputs |
| `PROVIDER_WORKER_CONCURRENCY` | `10` | parallele Worker für mehrstufige Jobs |
| `PROVIDER_POLL_INTERVAL_SECONDS` | `5` | Takt des Workers beim Pollen mehrstufiger Jobs |
| `PROVIDER_STATUS_MIN_INTERVAL_SECONDS` | `2` | Mindestabstand der Anbieter-Abfragen je Job |
| `OUTPUT_DIR` | `./data/outputs` | lokaler Speicher für Ergebnisse |
| `WEBHOOK_SECRET` | leer | Signaturschlüssel für `webhook_url` (`whsec_<base64>` oder beliebiger String); ohne ihn wird `webhook_url` abgelehnt |
| `WEBHOOK_INTERVAL_SECONDS` | `5` | Takt der Status- und Auslieferungsschleife |
| `WEBHOOK_TIMEOUT_SECONDS` | `10` | Timeout je Auslieferung |
| `WEBHOOK_MAX_ATTEMPTS` | `8` | Versuche, bevor eine Auslieferung verworfen wird |

### Real-Human-Asset-Jobs (Seedance)

| Variable | Standard | Zweck |
|---|---:|---|
| `ASSET_JOB_DB` | `./data/proxy-jobs.db` | persistenter Zustand temporärer Asset-Jobs |
| `ASSET_POLL_INTERVAL_SECONDS` | `5` | Mindestabstand der `GetAsset`-Prüfungen |
| `ASSET_MAINTENANCE_INTERVAL_SECONDS` | `2` | Takt des nicht blockierenden Job-Workers |
| `ASSET_MAX_PROCESSING_SECONDS` | `3600` | maximale Asset-Aufbereitungszeit |
| `ASSET_JOB_TTL_SECONDS` | `86400` | maximale Job- und Remote-Asset-Lebenszeit |
| `ASSET_WORKER_CONCURRENCY` | `10` | parallele Asset-/Job-Worker |
| `ASSET_CLEANUP_RETRIES` | `5` | begrenzt den Exponenten des Cleanup-Backoffs |
| `ASSET_TRANSIENT_RETRY_SECONDS` | `5` | Basiswartezeit, bevor ein Job nach Netzwerkausfall erneut läuft (gilt auch für Anbieter-Worker) |
| `ASSET_TRANSIENT_RETRY_MAX_SECONDS` | `60` | Obergrenze dieser Wartezeit |
| `ASSET_ORPHAN_CLEANUP_INTERVAL_SECONDS` | `900` | Abstand des Remote-Reconcilers |
| `ASSET_ORPHAN_TTL_SECONDS` | `86400` | Mindestalter verwaister App-Assets vor Löschung |

Beispiel für ein Mehr-Anbieter-Setup:

```dotenv
ARK_API_KEY=…
BYTEPLUS_ACCESS_KEY_ID=…
BYTEPLUS_SECRET_ACCESS_KEY=…
VERTEX_PROJECT=mein-projekt
GOOGLE_VEO_BACKEND=vertex
GOOGLE_VEO_LOCATION=global
GOOGLE_OMNI_BACKEND=vertex
GOOGLE_OMNI_LOCATION=global
KLING_API_KEY=…
WEBHOOK_SECRET=whsec_…
PUBLIC_BASE_URL=https://video-proxy.example.com
PROXY_API_KEY=replace-with-at-least-32-random-characters
```

(Beispielwerte nie durch echte Schlüssel in der Dokumentation ersetzen.)

## Modelllisten

`GET /v1/models` vereinigt die Modelle aller aktiven Anbieter. Ein Anbieter, der
ausfällt, fehlt nur in der Liste; erst wenn alle ausfallen, antwortet die Route
mit dem ersten Fehler.

- **ModelArk:** kombiniert die im Konto als `Available` gemeldeten
  Seedance-Modellfamilien aus `ListModelActivations` mit deren Versionen aus
  `ListFoundationModelVersions` (braucht AK/SK). BytePlus liefert dabei keine
  Auflösungen oder Dauern; der Proxy ergänzt je Familie die in der offiziellen
  Video-API dokumentierte Capability-Matrix. Modelle ohne Profil bleiben
  aufgelistet und werden dann nur von ModelArk validiert.
- **Google:** Gemini API über `models.list`; Vertex über die bekannten
  Publisher-Modelle (Veo 3.1 Standard, Fast, Lite; Omni Preview).
- **Kling:** feste Liste (`kling-3.0-turbo`, `kling-3.0`, `kling-3.0-omni`,
  `kling-o1`, `kling-2.6`, `kling-2.5-turbo`) plus virtuelle Modelle
  (`kling-lip-sync`, `kling-avatar`, `kling-effects`, `kling-multi-elements`,
  `kling-video-to-audio`, `kling-commerce`).

Fehlende oder ungültige Zugangsdaten beenden den Proxy nicht. `/health` meldet
den Zustand unter `providers` (`valid`, `checking`, `invalid`, `disabled`);
Fachrouten des betroffenen Anbieters liefern bis zur nächsten erfolgreichen
Prüfung HTTP `503` mit `upstream_credentials_invalid`. Standardmäßig wird alle
drei Stunden erneut geprüft. Eine serverseitige Freischaltung wird damit ohne
Neustart erkannt; geänderte Umgebungsvariablen erfordern einen Neustart.

Ein Netzwerkausfall ist dabei kein abgelehnter Zugang. Ist ein Anbieter während
der Prüfung nicht erreichbar, behält ein zuvor gültiger Zugang den Zustand
`valid`; `/health` nennt den Grund unter `message`. War der Zugang noch nie
bestätigt, lautet der Zustand `checking`, und Fachrouten antworten mit `503
upstream_credentials_unavailable`. Solange der Zustand nicht `valid` ist, wird im
verkürzten Takt aus `CREDENTIAL_REVALIDATION_INTERVAL_SECONDS` erneut geprüft.

`.env` ist von Git ausgeschlossen. API-Schlüssel dürfen weder committed noch in
Logs, Fehlermeldungen oder Screenshots veröffentlicht werden. Unabhängige
Schlüssel können mit `openssl rand -hex 32` erzeugt werden.

Die IAM-Einrichtung ist unter
[Real-Human-Assets](../real-human-assets/README.md#dedizierten-iam-user-und-aksk-anlegen)
Schritt für Schritt beschrieben.

## AI Video Studio

Für den zweiten Compose-Service werden `UI_USERNAME`, ein mindestens 16 Zeichen
langes `UI_PASSWORD` und ein zufälliger `UI_SESSION_SECRET` mit mindestens 32
Zeichen benötigt. Das Studio läuft auf Port 3000 (Host `5191`) und verwendet
intern `PROXY_API_KEY`. Der Compose-Stack erzwingt API-Key und HTTPS-Cookie als
Production-Defaults. Alle UI-Variablen und der temporäre Lebenszyklus sind unter
[AI Video Studio](../web-studio/README.md) dokumentiert.
