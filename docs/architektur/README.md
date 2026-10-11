# Architektur

## Datenfluss

```text
Client → LiteLLM Gateway → ModelArk OpenAI Video Proxy → BytePlus ModelArk
Browser → Seedance Web Studio ────────────────┘
                                      ↓                         ↓
                         temporäre Referenz-URL        asynchroner Seedance-Task
                                      ↓
                  optional: CreateAsset → Active → DeleteAsset
```

LiteLLM verwendet seinen OpenAI-Videoadapter. Dieser Proxy nimmt die
OpenAI-ähnliche Anfrage entgegen, baut daraus einen ModelArk-Task und gibt die
Task-ID in einem OpenAI-Videoobjekt zurück. Status und Ergebnis werden danach
über eigene GET-Endpunkte abgefragt.

LiteLLM hält dabei keine Create-Verbindung bis zum fertigen Video offen und
pollt gestartete Videojobs nicht automatisch im Hintergrund. Es kodiert
Provider- und Deployment-Informationen in die ausgegebene Video-ID, damit ein
späterer `GET /v1/videos/{id}` wieder beim richtigen Upstream landet. Das
regelmäßige Aufrufen dieses Status-Endpunkts ist Aufgabe des API-Clients oder
eines anwendungseigenen Job-Workers. Das entspricht auch dem von LiteLLM für
Vertex AI Veo dokumentierten Create-, Poll- und Downloadablauf.

## Komponenten

- `app.py`: HTTP-Routen, Authentifizierung, Validierung und Streaming.
- `translation.py`: Feld-, Format- und Statusübersetzung.
- `client.py`: authentifizierter asynchroner ModelArk-Client.
- `assets.py`: HMAC-signierter asynchroner ModelArk-Assets-Client.
- `asset_jobs.py`: persistente Real-Human-Orchestrierung und Remote-Cleanup.
- `media.py`: Signaturprüfung und zeitlich begrenzte Ablage von Uploads.
- `config.py`: Konfiguration aus `.env` beziehungsweise Prozessumgebung.
- `schemas.py`: OpenAI-nahe Video- und Listenobjekte.
- `ui/backend/server.py`: Single-User-Session, temporäres Jobregister und
  serverseitige Kommunikation mit dem Proxy.
- `ui/frontend`: React-/TypeScript-Studio, das als statische Anwendung vom
  UI-Backend ausgeliefert wird.

## Übersetzungsgrenze

Normale ModelArk-Jobs bleiben zustandsarm. Automatisch registrierte Real-Human-
Referenzen benötigen dagegen eine lokale Zuordnung zwischen Referenz,
temporärer Asset-ID und späterer Provider-Task-ID. Diese Zuordnung wird in
SQLite im persistenten Proxy-Volume gespeichert und nach Ablauf der TTL
entfernt.

Standardfelder werden übersetzt; ModelArk-Funktionen ohne OpenAI-Entsprechung
werden als klar benannte Erweiterungen angenommen. Für Sonderfälle steht das
rohe `content`-Array zur Verfügung. Es wird weitgehend unverändert an ModelArk
weitergereicht, unterliegt aber den Referenz-Limits des Proxys.

## Parallelität

Proxy und UI-Backend verwenden durchgehend asynchrone HTTP-Clients. Ein
Create-Aufruf wartet nur auf die ModelArk-Task-ID und niemals auf die eigentliche
Videogenerierung. Während Seedance einen Task rendert, hält der Container keine
offene Generierungsanfrage und kann weitere Tasks, Statusabfragen, Uploads und
Downloads annehmen.

Beide internen HTTP-Pools erlauben standardmäßig 100 gleichzeitige
Upstream-Verbindungen. Das Status-Polling der UI verarbeitet laufende Jobs in
begrenzten parallelen Gruppen, damit ein langsamer Statusaufruf nicht alle
anderen Jobs verzögert und ModelArk trotzdem nicht mit unbegrenzten Abfragen
überlastet wird.

Bei Real-Human-Aufrufen gibt `POST /v1/videos` bereits vor Abschluss von
`CreateAsset` eine lokale Job-ID zurück. Begrenzte Hintergrundworker pollen
Assets und Provider-Jobs parallel. Dadurch blockiert eine langsame
Gesichtsprüfung weder den HTTP-Worker noch andere Generierungen.

Das interne Real-Human-Polling und das externe Client-Polling haben
unterschiedliche Aufgaben: Die Proxy-Worker treiben Verifizierung und
Generierung unabhängig von Statusanfragen weiter; Client beziehungsweise UI
fragen lediglich den persistierten aktuellen Zustand ab. Das UI-Backend pollt
aktive Jobs standardmäßig alle 10 Sekunden, während das Browser-Frontend die
angezeigte Jobliste alle 5 Sekunden aktualisiert.

Der UI-Container läuft absichtlich mit einem Uvicorn-Prozess: Die Arbeit ist
I/O-lastig, und mehrere Prozesse würden das SQLite-Jobregister sowie Cleanup-
Schleifen unnötig duplizieren. Horizontale UI-Replikation ist für diesen
Single-User-Betrieb nicht vorgesehen.

## Grenzen

- Er umgeht keine Gesichts-, Rechte- oder Inhaltsprüfung.
- Er kann Assets nur in einer bereits verifizierten und konfigurierten Gruppe
  erstellen; die Lebendprüfung selbst bleibt bei BytePlus.
- Er speichert Ergebnisse nicht dauerhaft.
- Er wartet bei `POST /v1/videos` nicht auf die fertige Generierung.
- Er ersetzt keine öffentlich erreichbare Medienablage für Video-Uploads.

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
