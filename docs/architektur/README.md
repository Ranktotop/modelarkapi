# Architektur

## Datenfluss

```text
Client → LiteLLM Gateway ─┐
Direkter Client ──────────┼→ AI Video Studio Proxy (/v1/videos, /v1/models, …)
Browser → Studio-Backend ─┘        │
                                   ├→ BytePlus ModelArk   (Seedance)
                                   ├→ Gemini API / Vertex (Veo 3.1, Gemini Omni Flash)
                                   └→ Kling               (Video, Audio, Assets, Commerce)

Referenzen:  temporäre Referenz-URL (Seedance, Kling)  |  Bytes direkt (Google)
Ergebnisse:  ModelArk-URL (Seedance)  |  lokaler Output-Speicher (Google, Kling)
Optional:    Seedance Real-Human: CreateAsset → Active → DeleteAsset
```

LiteLLM verwendet seinen OpenAI-Videoadapter. Der Proxy nimmt die OpenAI-ähnliche
Anfrage entgegen, wählt den Anbieter über das Modellpräfix und gibt eine
Video-ID im LiteLLM-Format zurück. Status und Ergebnis werden danach über
eigene GET-Endpunkte abgefragt. Ein Modellwechsel ändert nur `model`.

LiteLLM hält dabei keine Create-Verbindung bis zum fertigen Video offen und
pollt gestartete Videojobs nicht automatisch im Hintergrund. Es kodiert
Provider- und Deployment-Informationen in die ausgegebene Video-ID, damit ein
späterer `GET /v1/videos/{id}` wieder beim richtigen Upstream landet. Das
regelmäßige Aufrufen dieses Status-Endpunkts ist Aufgabe des API-Clients oder
eines anwendungseigenen Job-Workers. Das entspricht auch dem von LiteLLM für
Vertex AI Veo dokumentierten Create-, Poll- und Downloadablauf.

## Komponenten

Proxy (`src/modelark_proxy/`):

- `app.py`: HTTP-Routen, Authentifizierung, Eingangskodierung (JSON, Multipart,
  Klammernotation, `extra_body`), Streaming und Hintergrundschleifen.
- `providers/base.py`: Anbieter-Vertrag und Modellrouting. Präfixe `veo-` und
  `gemini-omni-` gehen an Google, `kling-` an Kling, alles andere an ModelArk.
  Ein Namensraum (`openai/`, `google/`, `kling/`, `modelark/`) wird entfernt.
- `providers/seedance.py`: ModelArk-Tasks, `content`-Arrays, Draft-Modus,
  Real-Human-Einbindung, Übersetzung des einheitlichen Vertrags.
- `providers/google.py`, `google_backends.py`, `veo.py`, `omni.py`: Veo
  (Operationen) und Omni (Interactions) über Gemini API oder Vertex AI;
  Backend und Region je Familie.
- `providers/kling/` (`provider.py`, `client.py`, `models.py`, `assets.py`,
  `effects.json`): Kling-Client mit Fehlerabbildung, Modellkatalog, virtuelle
  Modelle, mehrstufige Jobs, native Durchleitung, Elements und Voices.
- `models.py`: Capability-Profile der Seedance-Familien (Datumssuffix wird
  entfernt).
- `capabilities.py`, `validation.py`, `unified.py`: Capability-Dokument v2,
  Validierung (`strict`/`adapt`) und Normalisierung des einheitlichen Requests
  inklusive Task-Ableitung.
- `references.py`, `downloads.py`, `media.py`: Auflösung aller Referenzquellen zu
  Bytes oder URLs, SSRF-geschützter Abruf, Upload-Ablage mit Signaturprüfung.
- `provider_jobs.py`, `outputs.py`, `workers.py`: lokales Jobregister
  (`vid-<anbieter>-<uuid>`, SQLite), Output-Speicher mit TTL und begrenzte,
  neustartfeste Worker für mehrstufige Jobs.
- `webhooks.py`: Watches, signierte Auslieferung (Standard Webhooks) mit
  Wiederholung.
- `credentials.py`, `google_auth.py`: Credential-Zustand je Anbieter, Vertex-Token.
- `ids.py`: Video-IDs (`video_…`) und Character-IDs (`character_…`) im LiteLLM-Format.
- `prompt_guides.py`, `litellm_export.py`, `audio.py`: Prompt-Guide-Registry,
  `model_list`-Export, Audiolänge (mutagen) für Kling Lip Sync.
- `client.py`, `assets.py`, `asset_jobs.py`: ModelArk-Client, HMAC-signierter
  Assets-Client und persistente Real-Human-Orchestrierung.
- `translation.py`, `schemas.py`, `errors.py`, `config.py`: Feld- und
  Statusübersetzung, Objekte, Fehlerformat, Konfiguration.

Außerdem:

- `prompt_guides/`: Markdown-Guides plus `manifest.yaml`.
- `ui/backend/server.py`: Single-User-Session, temporäres Jobregister und
  serverseitige Kommunikation mit dem Proxy.
- `ui/frontend`: React-/TypeScript-Studio „AI Video Studio“, vom UI-Backend als
  statische Anwendung ausgeliefert. Seine Formulare entstehen aus dem
  Capability-Dokument.

## Zwei API-Flächen, ein Kern

| Fläche | Pfad | Zweck |
|---|---|---|
| Einheitlich | `/v1/videos`, `/v1/models`, `/v1/audio/speech`, `/v1/assets`, `/v1/prompt-guides`, `/v1/litellm/config` | OpenAI-kompatibel, für LiteLLM und Apps |
| Nativ | `/v1/providers/modelark/tasks`, `/v1/providers/google/veo/…`, `/v1/providers/google/interactions`, `/v1/providers/kling/…` | Original-Parameter des Anbieters; erzeugte Jobs landen im selben Register |

Beide Flächen teilen Jobregister, Media-Store, Download und Credential-Status.

## Zustand

Das Seedance-Verhalten bleibt zustandsarm: Task-ID gleich ModelArk-Task (`cgt-…`).
Zustand hält der Proxy dort, wo es nötig ist:

| Speicher | Inhalt | Standardpfad |
|---|---|---|
| `provider_jobs` (SQLite) | Jobs von Google und Kling, mehrstufige Zustände, Webhook-Watches und -Auslieferungen | `./data/provider-jobs.db` |
| Output-Speicher | Ergebnisse, die als Bytes kommen (Vertex, Omni) oder hotlink-geschützte URLs haben (Kling) | `./data/outputs` |
| Asset-Jobs (SQLite) | Zuordnung Real-Human-Referenz, temporäre Asset-ID, Task-ID | `./data/proxy-jobs.db` |
| Media-Store | temporäre Uploads | `./data/references` |

Im Docker-Stack liegen Datenbanken und Outputs im Volume `server_state`
(`/app/state`). Jobs und Outputs laufen nach `PROVIDER_JOB_TTL_SECONDS` ab
(Standard 48 Stunden).

Standardfelder werden übersetzt; ModelArk-Funktionen ohne einheitliche
Entsprechung bleiben als Altfelder oder über `provider_options` erreichbar. Für
Sonderfälle steht bei Seedance das rohe `content`-Array zur Verfügung. Es wird
weitgehend unverändert an ModelArk weitergereicht, unterliegt aber den
Referenz-Limits des Proxys.

## Parallelität

Proxy und UI-Backend verwenden durchgehend asynchrone HTTP-Clients. Ein
Create-Aufruf wartet nur auf die Annahme beim Anbieter und niemals auf die
eigentliche Videogenerierung. Während ein Anbieter rendert, hält der Container
keine offene Generierungsanfrage und kann weitere Tasks, Statusabfragen, Uploads
und Downloads annehmen.

Statusabfragen von Google- und Kling-Jobs sind lazy: Der Proxy fragt den Anbieter
bei `GET /v1/videos/{id}`, höchstens alle `PROVIDER_STATUS_MIN_INTERVAL_SECONDS`
je Job. Mehrstufige Abläufe (Kling Lip Sync, Multi-Element-Edit) und
Real-Human-Jobs laufen dagegen in begrenzten Hintergrundworkern
(`PROVIDER_WORKER_CONCURRENCY`, `ASSET_WORKER_CONCURRENCY`) weiter, auch wenn
niemand den Status abfragt. Webhook-Watches pollen ebenfalls im Hintergrund.

Beide internen HTTP-Pools erlauben standardmäßig 100 gleichzeitige
Upstream-Verbindungen. Das Status-Polling der UI verarbeitet laufende Jobs in
begrenzten parallelen Gruppen, damit ein langsamer Statusaufruf nicht alle
anderen Jobs verzögert und die Anbieter trotzdem nicht mit unbegrenzten
Abfragen überlastet werden.

Bei Real-Human-Aufrufen gibt `POST /v1/videos` bereits vor Abschluss von
`CreateAsset` eine lokale Job-ID zurück. Das interne Polling und das externe
Client-Polling haben unterschiedliche Aufgaben: Die Proxy-Worker treiben
Verifizierung und Generierung unabhängig von Statusanfragen weiter; Client
beziehungsweise UI fragen lediglich den persistierten aktuellen Zustand ab. Das
UI-Backend pollt aktive Jobs standardmäßig alle 10 Sekunden, während das
Browser-Frontend die angezeigte Jobliste alle 5 Sekunden aktualisiert.

Der UI-Container läuft absichtlich mit einem Uvicorn-Prozess: Die Arbeit ist
I/O-lastig, und mehrere Prozesse würden das SQLite-Jobregister sowie Cleanup-
Schleifen unnötig duplizieren. Horizontale UI-Replikation ist für diesen
Single-User-Betrieb nicht vorgesehen.

## Credentials je Anbieter

`credentials.py` prüft jeden konfigurierten Anbieter mit einem kostenfreien
Read-only-Aufruf (ModelArk: API-Key und IAM; Google: `models.list` und/oder
Vertex-`interactions`; Kling: `account/costs`). Ein Anbieter ohne Zugangsdaten
ist `disabled` und wird weder gelistet noch geroutet. Ein ungültiger Anbieter
blockiert nur sich selbst; die Proxy-API-Key-Prüfung bleibt global.

## Grenzen

- Er umgeht keine Gesichts-, Rechte- oder Inhaltsprüfung.
- Er kann Seedance-Assets nur in einer bereits verifizierten und konfigurierten
  Gruppe erstellen; die Lebendprüfung selbst bleibt bei BytePlus.
- Er speichert Ergebnisse nicht dauerhaft; Google- und Kling-Ergebnisse liegen nur
  bis zum Ablauf des Jobs (`PROVIDER_JOB_TTL_SECONDS`) im Output-Speicher.
- Er wartet bei `POST /v1/videos` nicht auf die fertige Generierung.
- Er ersetzt keine öffentlich erreichbare Medienablage für Video-Uploads bei
  Seedance und Kling.
- Kling kennt keinen Abbruch: `DELETE` löscht nur lokal, der Anbieter-Job läuft
  weiter und wird berechnet. Das gilt auch für Veo.

## ADR-001: Multi-Provider-Plattform (AI Video Studio)

**Status:** angenommen am 11.10.2026 · **Plan:** `tasks/plan.md`

### Kontext

Der Proxy wird vom Seedance-Adapter zum zentralen Register für Video-KI-Modelle.
Angebunden werden BytePlus ModelArk (Seedance), Google Veo 3.1 und Gemini Omni
(Gemini API und Vertex AI) sowie Kling, jeweils mit allen nativen Fähigkeiten.
Andere Anwendungen nutzen die Modelle über LiteLLM und sollen sie wechseln
können, ohne ihren Code anzupassen.

### Entscheidungen

1. **Zwei API-Flächen über einem Provider-Kern.** Einheitlich unter
   `/v1/videos`, `/v1/models` und `/v1/audio/speech` (OpenAI-kompatibel, für
   LiteLLM); nativ unter `/v1/providers/{provider}/…` mit den
   Original-Parametern. Beide teilen Jobregister, Media-Store, Download und
   Credential-Status.
2. **Einheitlicher Vertrag mit Task-Vokabular** (`task`, typisierte
   `references[]`, `provider_options`). Bestehende Seedance-Felder bleiben
   gültig.
3. **LiteLLM-robuster Eingang.** Strukturierte Felder werden als JSON, als
   JSON-String oder in Multipart-Klammernotation angenommen; bei Remix wird
   `extra_body` gelesen.
4. **IDs im LiteLLM-Format.** Antworten enthalten
   `video_<base64("litellm:custom_llm_provider:openai;model_id:<upstream-modell>;video_id:<intern>")>`;
   eingehend werden beide Formen akzeptiert. `model_id` ist die
   **Upstream-Modell-ID** (z. B. `dreamina-seedance-2-5-260628`). LiteLLM löst sie
   über `litellm_params.model` (`openai/<upstream-modell>`) zur Deployment-Gruppe
   auf, deshalb darf der LiteLLM-`model_name` frei gewählt werden
   (z. B. `seedance_25_api`).
5. **Ein lokales Jobregister** (`vid-<provider>-<uuid>`) für alles, was nicht
   1:1 ein ModelArk-Task ist; Ergebnisse, die als Bytes kommen oder deren URLs
   hotlink-geschützt sind, werden mit TTL lokal gespeichert.
6. **`POST` wartet nie auf die Generierung.** Lazy Polling bei Statusabfrage;
   synchrone oder mehrstufige Abläufe laufen in begrenzten, neustartfesten
   Hintergrundworkern.
7. **Konfiguration pro Provider und Modellfamilie.** Google-Backend und
   -Region sind je Familie einstellbar (`GOOGLE_VEO_*`, `GOOGLE_OMNI_*`).
8. **Credentials und Health pro Provider.** Ein ausgefallener Provider
   blockiert die anderen nicht; die Proxy-API-Key-Prüfung bleibt global.
9. **Capability-Dokument v2 als einzige Wahrheit** für Validierung,
   `/v1/models`, LiteLLM-Export und UI-Formulare.
10. **Prompt Guides als Ressource:** `prompt_guides/` plus Manifest,
    `GET /v1/prompt-guides[/{guide}]` und Volltext in `GET /v1/models/{id}`.
11. **LiteLLM-Export:** erzeugt `model_list`-Einträge mit
    `model_info.capabilities` und `model_info.prompt_guide` (Volltext). Apps
    lesen beides über `GET /v1/model/info`; ein Pass-Through ist nicht nötig.
12. **Referenzen je Provider.** Seedance und Kling erhalten öffentliche URLs
    aus dem Media-Store; Google erhält lokale Inhalte (base64, Files API, GCS).
    Externe URLs für Google werden abgelehnt (keine SSRF-Fläche).
    *Nachtrag:* Externe URLs für Google werden inzwischen gemäß SPEC 7.2
    SSRF-geschützt vom Proxy abgerufen (nur `https`, öffentliche Adressen,
    Größenlimit, Dateisignaturprüfung).

### Verifikation am 11.10.2026 (nur kostenfreie, lesende Aufrufe)

| Prüfung | Ergebnis |
|---|---|
| Gemini API `GET /v1beta/models` | `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`, `veo-3.1-lite-generate-preview` (Abschaltung laut Google am 22.10.2026); `gemini-omni-1.1-flash` und `gemini-omni-flash-preview` (Methoden laut Liste: `generateContent`) |
| Vertex Service Account | Token erfolgreich; `GET …/locations/global/interactions` → HTTP 200 (API aktiv, IAM ausreichend) |
| Vertex Publisher-Modelle | `veo-3.1-generate-001` GA, `veo-3.1-fast-generate-001` GA, `veo-3.1-lite-generate-001` Preview, `gemini-omni-1.1-flash-preview` Preview, `gemini-omni-flash-preview` Preview; `gemini-omni-1.1-flash` auf Vertex **nicht** vorhanden |
| Vertex Veo-Regionen (`fetchPredictOperation` auf eine nicht existierende Operation) | `us-central1` und **`global`** erreichbar (Antwort „Operation nicht gefunden“); `europe-west4` → Modell nicht verfügbar |
| Kling `GET /account/costs` | HTTP 200, `code: 0` – API-Key gültig |
| LiteLLM (normaler App-Key) | `GET /v1/model/info` → HTTP 200 inklusive `model_info` und `litellm_params.api_base`; `mode: video_generation` für Seedance. Die LiteLLM-Version ist für App-Keys nicht abrufbar. |

### Kostenpflichtige Prüfung (vom Nutzer freigegeben, 11.10.2026)

| Prüfung | Ergebnis |
|---|---|
| Vertex Veo 3.1 Lite (`veo-3.1-lite-generate-001`, Region `global`, 4 s, 720p, mit Ton, ohne `storageUri`) | Funktioniert **ohne Provisioned Throughput** (Pay-as-you-go). Fertig nach ca. 23 s. Ergebnis inline unter `response.videos[].bytesBase64Encoded` mit `mimeType`, dazu `raiMediaFilteredCount`; ca. 1,0 MB MP4. |
| Gemini API Omni (`gemini-omni-1.1-flash`, 3 s, 360p, `delivery: uri`, `background: true`, `store: true`) | `background: true` wird **angenommen**. `GET /v1beta/interactions/{id}` liefert `status: completed` und den Output als `steps[type=model_output].content[type=video].uri` (Files API). Der in der Doku beschriebene Fehler (Inline statt URI beim GET) trat **nicht** auf. Datei: `state: ACTIVE`, Ablauf nach 48 h, Download mit API-Key ohne Host-Wechsel. Usage-Angabe: 5 793 Video-Output-Tokens. |

Nicht im Log festgehalten: ob der Create-Aufruf sofort mit `in_progress`
zurückkam. Polling per `GET` funktioniert jedenfalls, daher wird Omni
asynchron mit Polling umgesetzt; T12 prüft das sofortige Zurückkehren.

### Konsequenzen

- Standard für Veo: Vertex, Region `global` (oder `us-central1`); Veo über die
  Gemini API nur, solange die Modellliste es meldet.
- Omni auf Vertex nur mit Preview-IDs; auf der Gemini API GA. Die
  Modellliste wird dynamisch aus beiden Backends gebildet.
- Vertex liefert Veo-Videos ohne `storageUri` inline als base64 (≈ 1,35 Zeichen
  pro Byte). Der Proxy dekodiert sie in den Output-Speicher; GCS ist nicht nötig.
- Omni auf der Gemini API läuft mit `background: true` und Polling; ein
  synchroner Worker ist nicht nötig.
- Die Credential-Prüfungen aus dieser Tabelle werden als Health-Checks
  übernommen.
