# Implementierungsplan: AI Video Studio – zentrale Video-KI-Plattform

## Zielbild

Dieses Repository wird zum **zentralen Register für Video-KI-Modelle**. Jeder
Provider wird **nativ mit allen Fähigkeiten** angebunden und nach außen über
zwei Flächen angeboten:

1. **Einheitliche OpenAI-Videoschnittstelle** (`/v1/videos`, `/v1/models`,
   `/v1/audio/speech`): Jedes Modell wird gleich aufgerufen, Spezialfunktionen
   laufen über einheitliche Zusatzfelder. Die Apps sprechen diese Fläche über
   **LiteLLM** an und können Modelle wechseln, ohne ihren Code anzupassen.
2. **Native Provider-Routen** (`/v1/providers/{provider}/…`): Sie reichen die
   Original-Parameter des Providers 1:1 durch, ebenfalls mit Proxy-Auth,
   Jobregister und Download.

Dazu kommen **Prompt Guides** pro Modellfamilie. Sie sind über unsere REST-API,
über `GET /v1/models/{id}` und über LiteLLM (`/v1/model/info` →
`model_info.prompt_guide`) abrufbar. Das Web Studio heißt künftig
**„AI Video Studio“** und bildet alle Fähigkeiten ab.

Provider: **BytePlus ModelArk (Seedance)**, **Google Veo 3.1**, **Google
Gemini Omni** (jeweils Gemini API und/oder Vertex AI) und **Kling**.

Grundsatz des Nutzers: *nichts auf später verschieben*. Jede bekannte Fähigkeit
ist im Plan enthalten. Bewusst ausgeschlossen sind nur reine Bild-Endpunkte
(Kling-Bildgenerierung, Virtual Try-On), weil das hier ein Video-Proxy ist.

## Entscheidungen des Nutzers

| Datum | Frage | Entscheidung |
|---|---|---|
| 11.10. | Google-Zugang | Gemini API **und** Vertex AI; Region einstellbar |
| 11.10. | Veo-Versionen | nur **Veo 3.1** (3.1, Fast, Lite) |
| 11.10. | Branding | **„AI Video Studio“**; Paket- und Image-Namen bleiben |
| 11.10. | Omni `store=true` | ja |
| 11.10. | Weitere Provider | **Kling**, mit allen Fähigkeiten (inkl. Motion Control, Lip Sync, Effekte, Avatar, Audio) |
| 11.10. | Kling-Zugang | **API-Key** vorhanden |
| 11.10. | API-Flächen | **beides**: einheitlich `/v1/videos` **und** native Provider-Routen |
| 11.10. | Kling-Umfang | Video + Audio + Assets (Elements, Voices) + Video-Commerce; **ohne** Bild-Endpunkte und Try-On |
| 11.10. | Prompt Guides über LiteLLM | als **Text in `model_info`**, kein separater Pass-Through |
| 11.10. | Umsetzung | vollständig, nichts zurückstellen |

## Recherchegrundlage

Die Detailberichte (mit Quellen und „Unklar“-Abschnitten) sind die
verbindliche Grundlage der Umsetzung:

- [research/google.md](research/google.md): Veo 3.1 und Omni auf Gemini API und Vertex AI
- [research/kling.md](research/kling.md): vollständiger Kling-Katalog (neue und Legacy-API, 219 Effekte)
- [research/litellm-openai.md](research/litellm-openai.md): OpenAI-Videoprotokoll und LiteLLM-Verhalten (gegen v1.95 und v1.105 getestet)

### Fakten mit direkter Auswirkung auf die Architektur

**Google**
- **Veo 3.1 verschwindet am 22.10.2026 aus der Gemini API** (Preview-IDs werden
  abgeschaltet, Nachfolger ist Omni). Danach gibt es Veo nur auf **Vertex**:
  `veo-3.1-generate-001` und `veo-3.1-fast-generate-001` sind GA,
  `veo-3.1-lite-generate-001` ist Preview.
- **Regionen je Modellfamilie:** Omni läuft auf Vertex nur in `global`. Veo
  ist laut Doku nur in `us-central1` verfügbar, **laut T1 aber auch in
  `global` erreichbar** (nicht in `europe-west4`). Region bleibt je Familie
  einstellbar.
- **Omni** läuft auf beiden Backends über die **Interactions API**, mit
  `background: true` und Polling (Vertex dokumentiert, Gemini API **in T1 live
  bestätigt**).
- **Vertex Pay-as-you-go funktioniert** (T1 live: Veo 3.1 Lite in `global`);
  Videos kommen ohne `storageUri` inline unter
  `response.videos[].bytesBase64Encoded`.
- **Dein LiteLLM ist v1.104.2**, schickt Create also schon als Multipart mit
  Klammernotation. T4 ist damit vermutlich bereits für den heutigen Betrieb
  relevant (gegen den echten Server noch nicht getestet).
- Die Gemini API **sperrt Omni-Edit und -Extend für hochgeladene Videos in
  EWR, CH und UK**. Für einen Nutzer in Deutschland ist deshalb Vertex der
  sinnvolle Standard für diese Modi.
- Veo-Parameter, die es nur auf Vertex gibt: `sampleCount` 1–4,
  `negativePrompt`, `generateAudio`, `enhancePrompt`, `compressionQuality`,
  `resizeMode`, `storageUri`.

**Kling**
- Es gibt **zwei API-Generationen**. Die neue legt das Modell in den Pfad
  (`/text-to-video/kling-3.0`, `contents/settings/options`, Abfrage über
  `/tasks`). Die Legacy-API `/v1/…` nutzt `model_name` im Body. Avatar, Lip Sync,
  TTS, Audio, Effekte, Elements, Voices und Multi-Elements gibt es **nur im
  `/v1`-Schema**.
- Aktuelle Modelle: 3.0 Turbo, 3.0, 3.0 Omni, O1, 2.6, 2.5 Turbo. Die
  Fähigkeiten unterscheiden sich stark (Dauer, 4K, Multi-Shot, Audio,
  Elements, Motion Control).
- Kostenloser Credential-Check: `GET /account/costs` (höchstens 1 QPS).
  Ergebnis-URLs sind hotlink-geschützt und werden nach 30 Tagen gelöscht. Ein
  HTTP 429 hat drei verschiedene Ursachen (Abrechnung, Rate Limit,
  Parallelitätslimit).

**LiteLLM und das OpenAI-Protokoll**
- Die OpenAI-Videos-API wurde am 24.09.2026 eingestellt. LiteLLM setzt das
  Protokoll aber weiter um, und darauf bauen wir.
- **Ab LiteLLM 1.100 wird Create immer als Multipart gesendet**, verschachtelte
  Felder in Klammernotation (`reference_urls[][url]`), Booleans als Strings.
  Unser Parser versteht das heute laut Code nicht (gegen den echten Server noch
  nicht getestet).
- Extrafelder kommen bei Create oben im Body durch, bei Remix, Edit und
  Extension nur über `extra_body`.
- Nur die Create-ID enthält die Modellinformation. Folgeaufrufe auf Remix-,
  Edit- und Extension-Jobs routet LiteLLM sonst falsch. **Workaround
  (getestet):** Der Proxy gibt IDs gleich im LiteLLM-Format aus.
- Antwortfelder außerhalb des OpenAI-Schemas verwirft LiteLLM. `DELETE`, die
  Liste, `variant` und `/last_frame` sind über LiteLLM nicht erreichbar.
- `model_info` darf beliebige Schlüssel tragen. `/v1/model/info` gibt sie auch
  an Nicht-Admin-Keys zurück (laut Code; in T1 verifizieren).

## Architekturentscheidungen

**A1: Zwei API-Flächen über einem Provider-Kern.**
`providers/<name>/` enthält pro Provider einen nativen Client (Auth, Fehler,
Retry), einen nativen Router (`/v1/providers/<name>/…`) und einen Adapter vom
einheitlichen Vertrag auf native Aufrufe. Beide Flächen teilen Jobregister,
Media-Store, Download und Credential-Status.

**A2: Einheitlicher Vertrag mit Task-Vokabular.**
`POST /v1/videos` bekommt das Feld `task` mit diesen Werten:
- Generierung: `text_to_video`, `image_to_video`, `first_last_frame`, `reference_to_video`, `multi_shot`
- Bearbeitung: `edit`, `extend`, `motion_control`, `lip_sync`, `avatar`, `effect`, `multi_element_edit`
- Audio: `video_to_audio`, `text_to_audio`
- Commerce: `commerce_talking_agent`, `commerce_goods_studio`, `commerce_apparel`

Eingaben laufen über ein typisiertes Feld `references[]` mit `type` (`image`,
`video`, `audio`, `element`, `voice`), Quelle (`url`, `id` oder `task_id`) und
`role` (z. B. `first_frame`, `last_frame`, `reference`, `style`, `base_video`,
`feature_video`, `motion`, `face`, `speech`). Einheitliche Parameter:
`seconds`, `size`, `resolution`, `aspect_ratio`, `negative_prompt`, `seed`,
`generate_audio`, `quality`, `n`, `shots[]` und `effect`. `provider_options{}`
reicht native Zusatzfelder kontrolliert durch. Ist `task` nicht gesetzt, wird er
aus den Referenzen abgeleitet. Bestehende Seedance-Felder (`reference_urls`,
`input_reference_url`, `content`, `omni_reference_task_type` …) bleiben gültig.

**A3: LiteLLM-robuster Eingang.** Jedes strukturierte Feld wird angenommen als
JSON-Objekt, als JSON-String oder in Multipart-Klammernotation. Strings werden
in Typen umgewandelt. Bei Remix wird `extra_body` gelesen.

**A4: IDs im LiteLLM-Format.** Antworten enthalten
`video_<base64("litellm:custom_llm_provider:openai;model_id:<upstream-modell>;video_id:<intern>")>`.
Eingehend werden beide Formen angenommen. Intern bleiben `cgt-…` (Seedance)
und `vid-<provider>-<uuid>` (lokales Register).

**A5: Ein Jobregister für alles, was nicht 1:1 ein ModelArk-Task ist.** Dazu
gehören Google-Operationen und -Interactions, Kling-Tasks beider
API-Generationen (mit Endpunkttyp), mehrstufige Abläufe (Lip Sync:
identify-face, danach advanced-lip-sync) und Jobs aus nativen Routen. Statusfelder:
`provider_status`, `error{code,message}` (wichtige Infos landen dort, weil das
LiteLLM übersteht) und `outputs[]` für mehrere Ergebnisse (Veo
`sampleCount`). Ergebnisse, die als Bytes kommen (Vertex inline, Omni inline),
oder deren URLs hotlink-geschützt sind, werden in `data/outputs/` mit TTL
gespeichert.

**A6: Ausführungsmodelle.** Lazy Polling bei Statusabfrage (Seedance, Veo,
Kling), Hintergrundworker für synchrone oder mehrstufige Abläufe (Omni ohne
`background`, Lip Sync, Multi-Element-Sessions). Die Worker sind wie
`asset_jobs` begrenzt und neustartfest. `POST` wartet nie auf die Generierung.

**A7: Konfiguration pro Provider und Familie.**
- Google: `GEMINI_API_KEY`, `VERTEX_PROJECT`, Service-Account oder ADC;
  Backend und Region **je Familie** (`GOOGLE_VEO_BACKEND=vertex`,
  `GOOGLE_VEO_LOCATION=us-central1`, `GOOGLE_OMNI_BACKEND=vertex|gemini`,
  `GOOGLE_OMNI_LOCATION=global`).
- Kling: `KLING_API_KEY`, `KLING_BASE_URL`.
- Die Modellliste entsteht dynamisch aus den Upstreams. Ist Veo in der Gemini
  API abgeschaltet, verschwindet es dort automatisch.

**A8: Credentials und Health pro Provider.** Status `valid`, `invalid`,
`checking` oder `disabled`. Die Middleware sperrt nur betroffene Provider; die
Proxy-API-Key-Prüfung bleibt global. Kein Provider ist Pflicht.

**A9: Fähigkeiten sind die einzige Wahrheit.** Pro Modell beschreibt das
Capability-Dokument v2: unterstützte `tasks`, pro Task die erlaubten und
nötigen `references` (Typ, Rolle, Anzahl, Dauer, Größe), Parameterbereiche
(teils abhängig vom Task, z. B. Veo-Referenzen nur mit 8 s) und
Provider-Extras. Validierung, `/v1/models`, LiteLLM-Export und UI-Formulare
leiten sich ausschließlich daraus ab.

**A10: Prompt Guides als Ressource.** `prompt_guides/*.md` plus ein Manifest
(`prompt_guides/manifest.yaml`: Guide → Modellfamilien, Stand, Sprache).
Endpunkte:
- `GET /v1/prompt-guides`: Liste
- `GET /v1/prompt-guides/{guide}`: `text/markdown`
- `GET /v1/models/{id}`: enthält `prompt_guide` (Volltext) und `links.prompt_guide`
- `GET /v1/models`: nur den Link, damit die Liste klein bleibt

**A11: LiteLLM-Export.** `GET /v1/litellm/config` (und eine CLI) erzeugt
`model_list`-Einträge für alle aktiven Modelle, mit
`model_info.capabilities`, `model_info.prompt_guide` (Volltext) und
`prompt_guide_url`. Der LiteLLM-`model_name` darf frei gewählt werden (dein Schema ist z. B.
`seedance_25_api`): LiteLLM löst die `model_id` aus A4 über
`litellm_params.model` (`openai/<upstream-modell>`) auf. Der Export
übernimmt dieses Namensschema als konfigurierbare Vorlage.

**A12: Referenzen und Uploads (geändert in T2).** Jede Quelle funktioniert
für jeden Provider, sonst wäre ein Modellwechsel nicht nahtlos. Quellen sind
`https`-URL, `data:`-URI (Upload-Weg über LiteLLM), Upload-ID, Job-ID oder
Asset-ID. Seedance und Kling bekommen öffentliche URLs (Media-Store über
`PUBLIC_BASE_URL`). Google bekommt Bytes, Files-API- oder Inline-Daten; dafür
lädt der Proxy externe URLs **mit SSRF-Schutz** selbst herunter (nur `https`,
keine privaten Adressen, auch nicht nach Redirects, Größenlimits). Details:
[docs/SPEC.md](../docs/SPEC.md) Abschnitt 7.

## Abhängigkeitsgraph

```text
T1 Live-Verifikation (kostenfrei) ──► T2 Einheitlicher API-Vertrag (Contract first)
                                          │
        ┌─────────────┬──────────────┬────┴─────────┬──────────────┐
        T3 Provider-  T4 Eingang/IDs T5 Config/    T6 Jobregister T8 Prompt-Guide-
        Kern+Seedance (LiteLLM)      Health        + Worker       Registry + Export
        └─────┬───────┴──────┬───────┴──────┬───────┘                │
              T7 Capability v2 + Validierung + UI-Formular-Engine ◄──┘
                     │
   ┌─────────────────┼──────────────────────┬────────────────────┐
 Google            Kling                  Seedance             Guides (Inhalt)
 T9 Backends+Veo   T14 Client+T2V/I2V     T22 Vollständigkeit  T23 Omni-Guide
 T10 Veo-Modi      T15 Omni/O1                                 T24 Kling-Guides
 T11 Veo-Extend    T16 Motion Control                          T25 Veo/Seedance-Pflege
 T12 Omni Basis    T17 Elements/Voices
 T13 Omni Ref/Edit T18 Lip Sync/Avatar
                   T19 Audio (TTS/T2A/V2A)
                   T20 Effekte/Multi-Elements
                   T21 Commerce
   └─────────────────┴──────────┬───────────┘
          T26 UI-Assets/Bibliotheken ─► T27 UI-Branding/Feinschliff
          T28 LiteLLM-Ende-zu-Ende ─► T29 Doku
```

Nach Checkpoint 1 laufen **Google**, **Kling**, **Seedance** und **Guides**
unabhängig voneinander und lassen sich parallel bearbeiten.

## Aufgabenliste

Format je Task: Beschreibung · Akzeptanzkriterien · Verifikation ·
Abhängigkeiten · Dateien · Umfang. Grundregel für alle Tasks: Tests nur mit
Mock-Transports. Bezahlte oder biometrische Live-Läufe nur nach ausdrücklicher
Freigabe (AGENTS.md).

### Phase 0: Verträge und Risiken

#### T1: Live-Verifikation mit kostenfreien Aufrufen und ADR
**Beschreibung:** Folgende Aufrufe prüfen:
- **Gemini:** `GET /v1beta/models`, um die verfügbaren Veo- und Omni-IDs festzustellen.
- **Vertex:** ADC-Token, `GET …/locations/global/interactions?page_size=1`,
  Verfügbarkeit von Veo in `us-central1` und `global`.
- **Kling:** `GET /account/costs`.
- **LiteLLM:** Liefert dein LiteLLM-`/v1/model/info` einen großen Text in
  `model_info` an einen normalen App-Key aus?

Außerdem einen protokollierenden Mock-Upstream gegen deine LiteLLM-Version
laufen lassen (Multipart-Format). Zwei Punkte werden **nur gemeldet, nicht
getestet**, weil ein Test Geld kostet: Bei Vertex steht „Pay-as-you-go: Not
supported“, und offen ist, ob Omni auf der Gemini API mit `background`
arbeitet. Für beides holt T1 deine Freigabe ein. Die Entscheidungen A1–A12
werden als ADR festgehalten.
**Akzeptanz:** Verfügbarkeitstabelle Modell × Backend × Region; LiteLLM-Version und Multipart-Format belegt; `model_info`-Auslieferung an einen App-Key belegt; ADR im Repo.
**Verifikation:** Mitschnitte ohne Secrets im ADR; Review durch den Nutzer.
**Abh.:** keine · **Dateien:** `docs/architektur/README.md` · **Umfang:** S

#### T2: Einheitlicher API-Vertrag (Contract first)
**Beschreibung:** Den Vertrag aus A2 bis A5 und A10/A11 als Spezifikation
ausarbeiten:
- Task-Vokabular; je Task die Pflicht- und optionalen Referenzen
- Feldnamen und Typen samt JSON-, String- und Klammer-Varianten
- Antwortobjekt (`outputs[]`, `provider_status`, `error.code`-Katalog)
- ID-Format, Layout der nativen Routen
- Audio-Ausgaben: `/v1/audio/speech` für TTS; `text_to_audio` als
  `/v1/videos`-Task mit Audio-MIME und als native Route
- Prompt-Guide- und Export-Endpunkte
- Abbildungstabelle Task × Provider × Modell als Referenz für T9–T22

Bestehende Seedance-Felder bleiben gültig (Kompatibilitätsteil).
**Akzeptanz:** Jede Fähigkeit aus den drei Research-Berichten ist entweder einem einheitlichen Task bzw. Feld oder einer nativen Route zugeordnet, keine bleibt offen; Beispiele für LiteLLM ≤1.99 und ≥1.100.
**Verifikation:** Review durch den Nutzer; Abgleich gegen die Feature-Matrizen in `research/*.md`.
**Abh.:** T1 · **Dateien:** `docs/SPEC.md` (die API-Referenz in `docs/` wird in T29 daraus erzeugt) · **Umfang:** M

### Phase 1: Fundament

#### T3: Provider-Kern und Seedance-Adapter (Refactor ohne Verhaltensänderung)
**Beschreibung:** `providers/base.py` enthält Protokoll, Registry und
`provider_for(model)`; `providers/seedance/` kapselt den bestehenden
ModelArk-Code inklusive Real-Human. Die Routen in `app.py` delegieren nur noch.
**Akzeptanz:** Alle bestehenden Tests sind ohne Änderung grün; Routing-Tests für alle Präfixe.
**Verifikation:** `pytest`.
**Abh.:** T2 · **Dateien:** `providers/{base,seedance}/…`, `app.py`, `models.py`, `tests/test_providers.py` · **Umfang:** M

#### T4: LiteLLM-robuster Eingang und IDs im LiteLLM-Format
**Beschreibung:** Den Parser auf Klammernotation, JSON-Strings, Typumwandlung
und `extra_body` erweitern. IDs werden nach A4 kodiert und dekodiert; Remix,
Status, Content und Delete akzeptieren beide Formen. Das UI-Backend kommt mit
beiden Formen zurecht (Altjobs mit `cgt-…`).
**Akzeptanz:** Die echten Request-Bodies aus `research/litellm-openai.md` (v1.95 JSON, v1.105 Multipart) ergeben identische interne Requests; Folgeaufrufe mit kodierten IDs funktionieren.
**Verifikation:** Regressionstests mit den Original-Bodies aus dem Bericht.
**Abh.:** T3 · **Dateien:** `app.py` (Parser), `ids.py`, `ui/backend/server.py`, Tests · **Umfang:** M

#### T5: Konfiguration, Credentials und Health pro Provider
**Beschreibung:** Settings nach A7 einführen; Status, Middleware und `/health`
pro Provider (A8); kostenfreie Checks (ModelArk wie bisher,
Gemini `GET /models`, Vertex Interactions-List, Kling `/account/costs` mit
1-QPS-Grenze). `/v1/models` führt die Listen dynamisch zusammen.
**Akzeptanz:** Fällt ein Provider aus, sind die anderen weiter erreichbar; der Proxy startet mit beliebiger Teilmenge oder ganz ohne Provider; die 401-Pfade sind unverändert.
**Verifikation:** Tests für die Provider-Kombinationen; manuell `/health` und `/v1/models` über „Local Full Stack“.
**Abh.:** T3 · **Dateien:** `config.py`, `app.py`, `providers/base.py`, `.env.example`, Tests · **Umfang:** M

#### T6: Jobregister, Output-Speicher und Worker-Framework
**Beschreibung:** Die Tabelle `provider_jobs` nach A5 (inkl. `outputs[]`,
Endpunkttyp, mehrstufiger Zustand), lokaler Output-Speicher mit TTL und ein
generisches Framework für Lazy Polling und Hintergrundworker (Semaphore, Backoff,
Fortsetzung nach Neustart). Dazu Download-Streaming für Upstream-URLs mit
Auth-Header und für lokale Dateien, mit `?output=i`, Allowlists pro Provider und
Redirect-Prüfung.
**Akzeptanz:** Jobs überstehen einen Neustart; mehrstufige Jobs setzen dort fort, wo sie standen; TTL löscht DB-Einträge und Dateien.
**Verifikation:** Unit-Tests (Neustart, TTL, Worker-Begrenzung, Streaming).
**Abh.:** T3 · **Dateien:** `provider_jobs.py`, `outputs.py`, `workers.py`, Tests · **Umfang:** M

#### T6b: Ausgehende Webhooks
**Beschreibung:** `callback_url` am Request; der Proxy sendet bei
Statuswechseln das Video-Objekt nach *Standard Webhooks* (Signatur mit
`WEBHOOK_SECRET`, Wiederholungen mit Backoff, Zustellstatus im Register).
**Akzeptanz:** Signatur ist mit der Referenzbibliothek prüfbar; Wiederholungen nach Fehlern; ein Neustart verliert keine ausstehende Zustellung.
**Verifikation:** Tests mit einem lokalen Empfänger.
**Abh.:** T6 · **Dateien:** `webhooks.py`, Tests · **Umfang:** S

#### T7: Capability-Schema v2, Validierungs-Engine und fähigkeitsgesteuerte UI
**Beschreibung:** Das Capability-Dokument nach A9 einführen, dazu eine
generische Validierung (Task, Referenzen, Parameter, Regeln wie „Referenzen
erfordern 8 s“). Seedance wird darauf umgestellt, das Verhalten bleibt
identisch. Die UI ersetzt die fest verdrahteten `MODES` durch eine Engine, die
Formulare aus `tasks` und `references` erzeugt: Upload-Slots je Rolle,
Parameterfelder, gesperrte Werte mit Begründung. Der Modell-Picker gruppiert
nach Provider.
**Akzeptanz:** Mit Seedance-Modellen ist die UI funktional unverändert; die bestehenden Seedance-Validierungstests sind unverändert grün; neue Felder sind optional.
**Verifikation:** `pytest`; `npm run build`; Browser-Check (Chrome DevTools).
**Abh.:** T3 · **Dateien:** `models.py`/`capabilities.py`, `validation.py`, `ui/frontend/src/{types.ts,App.tsx,forms/*}` · **Umfang:** L (aufteilen in T7a Backend-Schema und Validierung, T7b UI-Formular-Engine)

#### T8: Prompt-Guide-Registry, Endpunkte und LiteLLM-Export
**Beschreibung:** Das Manifest für die vorhandenen drei Guides anlegen und die
Endpunkte nach A10 sowie den Export nach A11 bauen. Die UI zeigt den Guide des
gewählten Modells in einem Seitenpanel (Markdown-Rendering).
**Akzeptanz:** `GET /v1/models/{seedance-2-5-…}` enthält den Guide-Volltext; der Export erzeugt gültiges LiteLLM-YAML mit `model_info.prompt_guide`; Modelle ohne Guide bekommen `null`.
**Verifikation:** Tests; Export in ein lokales LiteLLM laden (Scratch-venv) und `/v1/model/info` prüfen.
**Abh.:** T5 (Modellliste), T7 (capabilities) · **Dateien:** `prompt_guides/manifest.yaml`, `prompt_guides.py`, `litellm_export.py`, `app.py`, UI · **Umfang:** M

### Checkpoint 1: Fundament
- [ ] `pytest` und `npm run build` grün; Seedance unverändert (nur kostenfreie Endpunkte geprüft).
- [ ] Vertrag (T2) und ADR vom Nutzer abgenommen.
- [ ] Ab hier laufen die Stränge Google, Kling, Seedance und Guides parallel.

### Phase 2: Google (Veo 3.1 und Omni)

#### T9: Google-Backends und Veo Text→Video
**Beschreibung:** `GeminiApiBackend` (API-Key) und `VertexBackend`
(`google-auth`, Token-Refresh, Region je Familie) hinter einer
Schnittstelle. Veo-Familien-Specs (Preview- und GA-IDs auf die Familie
aufgelöst), dazu `text_to_video` mit allen Parametern je Backend:
- Gemini: `aspectRatio`, `resolution`, `durationSeconds`, `personGeneration`, `seed`
- Vertex zusätzlich: `negativePrompt`, `generateAudio`, `enhancePrompt`,
  `sampleCount` (→ `outputs[]`), `compressionQuality`, `resizeMode`

RAI-Filter werden auf `error.code` abgebildet. Dazu die native Route
`/v1/providers/google/veo/…`.
**Akzeptanz:** Text→Video funktioniert mit beiden Backends per API und UI; backendspezifische Parameter werden beim jeweils anderen Backend mit 400 abgelehnt; `n>1` liefert mehrere Outputs.
**Verifikation:** Parametrisierte MockTransport-Tests für beide Backends. Optionaler Live-Test nur mit Freigabe.
**Abh.:** T4–T7 · **Dateien:** `providers/google/{backend,veo,router}.py`, `pyproject.toml`, Tests · **Umfang:** M

#### T10: Veo Bild→Video, Start+Ende und Referenzbilder
**Beschreibung:** `image`, `lastFrame` und `referenceImages` (höchstens 3,
`asset`; nicht bei Lite) aus dem Media-Store, mit allen Regeln (8 s bei
Referenzen, 1080p und 4k; `personGeneration` je Modus; EU-Einschränkung).
**Akzeptanz:** Alle Bildmodi funktionieren mit beiden Backends; jede Regel liefert ein synchrones 400.
**Verifikation:** Tests für die Body-Erzeugung je Modus und Backend; UI-Check.
**Abh.:** T9 · **Dateien:** `providers/google/veo.py`, `media.py`, Tests · **Umfang:** M

#### T11: Veo-Extension
**Beschreibung:** `extend` mit backendspezifischen Regeln. Gemini API: +7 s,
720p, Lite nicht unterstützt. Vertex: Eingabe 1–30 s, Lite unterstützt. Quelle
ist ein eigener Job (`task_id`) oder, auf Vertex, ein hochgeladenes Video. Die
Fortsetzen-Aktion der UI nutzt diesen Weg.
**Akzeptanz:** Die Extension funktioniert auf beiden Backends; unzulässige Quellen liefern 400.
**Verifikation:** Tests; UI-Check.
**Abh.:** T10 · **Dateien:** `providers/google/veo.py`, UI, Tests · **Umfang:** S

#### T12: Omni Text→Video, Bild→Video und Start+Ende
**Beschreibung:** Interactions API auf beiden Backends mit `store=true`,
`response_format` (Ratio, 360p–4k, `duration` 3–10 s, Delivery-Weg) und
`video_config.task`. Vertex arbeitet mit `background: true` und Polling; die
Gemini API je nach T1-Ergebnis mit `background` oder über den Worker. Der
Output kommt über Files API, inline oder GCS in den Output-Speicher (auch für
den bekannten Fall, dass ein URI angefragt, aber inline geliefert wird). Dazu
die native Route `/v1/providers/google/omni/…`.
**Akzeptanz:** `POST` antwortet sofort; Status und Content funktionieren auf beiden Backends; ein Neustart verliert keinen Hintergrundjob.
**Verifikation:** Tests mit verzögerten Mocks, Neustart-Test.
**Abh.:** T9 · **Dateien:** `providers/google/{omni,router}.py`, Tests · **Umfang:** M

#### T13: Omni-Referenzen, Edit, Extend und Multi-Turn
**Beschreibung:**
- `reference_to_video`: Bilder (Limit je Backend) und Videoreferenzen (höchstens 3 à 3 s)
- `edit` und `extend` mit hochgeladenem Video (Gemini: Files API und
  EWR-Sperre, die als klarer Fehler gemeldet wird; Vertex: GCS oder inline)
- Multi-Turn über `previous_interaction_id`, ausgelöst durch einen
  `task_id`-Verweis auf einen eigenen Omni-Job
- Cleanup hochgeladener Dateien

**Akzeptanz:** Alle Modi funktionieren per API und UI; Limits und Regionssperren liefern verständliche 400er.
**Verifikation:** Tests je Modus und Backend.
**Abh.:** T12 · **Dateien:** `providers/google/omni.py`, `backend.py`, Tests · **Umfang:** M

### Checkpoint 2: Google
- [ ] Alle Google-Tests grün (beide Backends); UI-Check aller Veo- und Omni-Modi.
- [ ] Optional mit Freigabe: Live-Läufe (Veo Lite 4 s auf Vertex, Omni 360p).

### Phase 3: Kling (parallel zu Phase 2)

#### T14: Kling-Client, Text→Video und Bild→Video
**Beschreibung:** Client für beide API-Generationen:
- API-Key-Auth und Fehlerklassen (1101/1102 nicht wiederholen, 1302/1303 mit Backoff)
- Abfrage über `/tasks` bzw. `/v1/…/{id}`
- Download in den Output-Speicher, weil Kling-URLs hotlink-geschützt sind

Specs für alle sechs Modelle aus der Matrix in `research/kling.md` (Dauer,
Auflösung, 4K, Ratios). Abgedeckte Tasks:
- `text_to_video`, `image_to_video` und `first_last_frame` über die neue API
  (Legacy nur dort, wo nötig)
- `multi_shot` (bis 6 Shots über `shots[]`)
- native Audio (`generate_audio`), `negative_prompt`, `quality`

Dazu die native Route `/v1/providers/kling/…`.
**Akzeptanz:** Alle sechs Modelle sind in API und UI mit korrekt eingeschränkten Optionen nutzbar; Fehlercodes werden korrekt abgebildet.
**Verifikation:** MockTransport-Tests für beide Generationen; optionaler Live-Test nur mit Freigabe.
**Abh.:** T4–T7 · **Dateien:** `providers/kling/{client,models,video,router}.py`, Tests · **Umfang:** M

#### T15: Kling Omni (3.0 Omni, O1): Referenzen und Video-Edit
**Beschreibung:** `reference_to_video` (`refer_image`, `feature_video`,
Elements) und `edit` (`base_video`), mit den Audio-Modi `native` und
`original` sowie den Modellregeln (z. B. bei O1 Start+Ende ohne Elements).
**Akzeptanz:** Alle Omni-Kombinationen aus der Matrix funktionieren per API und UI, Verstöße liefern 400.
**Verifikation:** Tests für die Body-Erzeugung.
**Abh.:** T14, T17 (Elements) · **Dateien:** `providers/kling/omni.py`, Tests · **Umfang:** M

#### T16: Kling Motion Control
**Beschreibung:** Task `motion_control` (Bild + Bewegungsvideo,
`character_orientation`, Original-Ton behalten, Elements) für 3.0 und 2.6.
**Akzeptanz:** Funktioniert per API und UI; Video-Limits werden geprüft.
**Verifikation:** Tests.
**Abh.:** T14 · **Dateien:** `providers/kling/motion.py`, Tests · **Umfang:** S

#### T17: Kling Elements und Voices (Asset-Verwaltung)
**Beschreibung:** Native Routen für Custom- und Preset-Elements bzw.
-Voices: anlegen (asynchron), abrufen, auflisten, löschen. Im einheitlichen
Vertrag als `references[{type: element|voice, id}]` nutzbar. Dazu eine
einheitliche Asset-Übersicht `GET /v1/assets?provider=…` (auch für
Seedance-Real-Human).
**Akzeptanz:** Der vollständige Lebenszyklus ist per API nutzbar; Elements und Voices lassen sich in T2V, I2V, Omni und Motion Control verwenden.
**Verifikation:** Tests für den Lebenszyklus.
**Abh.:** T14 · **Dateien:** `providers/kling/assets.py`, `app.py`, Tests · **Umfang:** M

#### T18: Kling Lip Sync und Avatar
**Beschreibung:** `lip_sync` als mehrstufiger Worker-Job: `identify-face`,
dann Gesichtsauswahl (automatisch oder per `face_id`), dann
`advanced-lip-sync` mit Audio-Datei oder TTS-Text. `avatar` aus Bild plus
Audio oder Text.
**Akzeptanz:** Beide Tasks laufen mit einem `POST` vollständig durch; mehrstufige Fehler landen sauber in `error`.
**Verifikation:** Worker-Tests mit Mocks für jede Stufe.
**Abh.:** T14, T6 · **Dateien:** `providers/kling/{lipsync,avatar}.py`, Tests · **Umfang:** M

#### T19: Kling Audio (TTS, Text→Audio, Video→Audio)
**Beschreibung:**
- TTS (synchron) über OpenAI `POST /v1/audio/speech` (Voices als `voice`) und nativ
- `text_to_audio` (Soundeffekte und Musik)
- `video_to_audio` (Ton für ein Video)

Content liefert den richtigen MIME-Typ.
**Akzeptanz:** `/v1/audio/speech` ist OpenAI-kompatibel (über LiteLLM nutzbar); beide Audio-Tasks liefern abrufbare Ergebnisse.
**Verifikation:** Tests.
**Abh.:** T14 · **Dateien:** `providers/kling/audio.py`, `app.py`, Tests · **Umfang:** M

#### T20: Kling-Effekte und Multi-Element-Bearbeitung
**Beschreibung:** Task `effect` mit allen 219 `effect_scene`-Werten
(Katalog als Daten, abrufbar über `GET /v1/providers/kling/effects`).
`multi_element_edit` (Elemente hinzufügen, tauschen, entfernen) als
Session-Ablauf im Worker.
**Akzeptanz:** Alle Effekte sind wählbar und validiert; die Multi-Element-Session läuft mit einem `POST` durch.
**Verifikation:** Tests; UI-Check der Effekt-Auswahl (Suche).
**Abh.:** T14, T6 · **Dateien:** `providers/kling/{effects,multi_elements}.py`, `data/kling_effects.json`, Tests · **Umfang:** M

#### T21: Kling Video-Commerce
**Beschreibung:** Die Tasks `commerce_talking_agent`, `commerce_goods_studio`
und `commerce_apparel` über die Solutions-API (Abfrage `/solutions`).
**Akzeptanz:** Alle drei Abläufe funktionieren per API und UI mit validierten Eingaben.
**Verifikation:** Tests.
**Abh.:** T14, T17 · **Dateien:** `providers/kling/solutions.py`, Tests · **Umfang:** M

### Checkpoint 3: Kling
- [ ] Alle Kling-Tests grün; jede Fähigkeit aus `research/kling.md` ist abgedeckt (Checkliste).
- [ ] Optional mit Freigabe: Live-Läufe (2.5 Turbo 5 s, ein Lip Sync).

### Phase 4: Seedance vollständig

#### T22: Seedance-Lückenanalyse und Abbildung auf den Vertrag
**Beschreibung:** Die aktuelle ModelArk-API-Referenz recherchieren und mit dem
Proxy abgleichen (alle Parameter, Tasks, Modelle). Fehlendes wird ergänzt, und
alle Seedance-Fähigkeiten werden auf das einheitliche Task-Vokabular
abgebildet (z. B. `omni_reference_task_type` → `task`).
**Akzeptanz:** Ein Rechercheprotokoll `research/seedance.md` liegt vor; jede dort genannte Fähigkeit ist umgesetzt; die Altfelder funktionieren weiter.
**Verifikation:** Tests; Vergleichstabelle.
**Abh.:** T7 · **Dateien:** `providers/seedance/…`, `tasks/research/seedance.md`, Tests · **Umfang:** M

### Phase 5: Prompt Guides (Inhalt; parallel ab Checkpoint 1)

#### T23: Prompt Guide Gemini Omni Flash
**Beschreibung:** Recherchebasiert, in Struktur und Qualitätsniveau wie die
vorhandenen Guides (Quellenstufen, Masterformel, Modusmatrix, Grenzen,
Beispiele), inklusive Edit-, Extend- und Multi-Turn-Regie.
**Akzeptanz:** Primärquellen sind belegt; das Manifest ist aktualisiert; der Guide ist über API und LiteLLM-Export abrufbar.
**Verifikation:** Review durch den Nutzer.
**Abh.:** T8 · **Dateien:** `prompt_guides/gemini_omni_flash.md`, Manifest · **Umfang:** M

#### T24: Prompt Guides Kling
**Beschreibung:** Ein Guide pro Familie, also 3.0 (inkl. Turbo und Multi-Shot),
3.0 Omni / O1 und 2.6 / 2.5 Turbo. Dazu aufgabenbezogene Kapitel für Motion
Control, Lip Sync, Avatar, Effekte und Elements.
**Akzeptanz/Verifikation:** wie T23.
**Abh.:** T8 · **Dateien:** `prompt_guides/kling_*.md`, Manifest · **Umfang:** M (bei Bedarf je Familie eine Task)

#### T25: Bestehende Guides pflegen und Lücken schließen
**Beschreibung:** Den Veo-Guide um die Korrekturen aus `research/google.md`
ergänzen (`sampleCount`, Lite-Extension auf Vertex, Extension-Limits,
Abschaltung der Preview-IDs). Die Zuordnung der Seedance-Modelle klären: Der
2.0-Fast-Guide gilt laut eigenem Text für die ganze 2.0-Serie. Für die
Seedance-1.x-Modelle wird ein Guide erstellt, sofern sie weiter angeboten
werden.
**Akzeptanz:** Jedes Modell in `/v1/models` hat einen Guide.
**Verifikation:** automatischer Test „jedes aktive Modell hat einen Manifest-Eintrag“.
**Abh.:** T8, T22 · **Dateien:** `prompt_guides/*`, Manifest · **Umfang:** S–M

### Phase 6: UI und Integration

#### T26: UI-Assetbibliotheken und Spezial-Workflows
**Beschreibung:**
- Bibliotheken: Kling-Elements und -Voices (anlegen, wählen, löschen) und
  Seedance-Real-Human in einer Asset-Ansicht
- Effekt-Galerie mit Suche
- Lip-Sync- und Avatar-Formulare (Audio-Upload oder TTS-Text, Gesichtsauswahl)
- Multi-Shot-Editor (Shots mit Prompt und Dauer)
- Ergebnisanzeige für Audio und für mehrere Outputs

**Akzeptanz:** Jede Task aus T2 ist in der UI auslösbar; fehlende Eingaben werden vor dem Absenden benannt.
**Verifikation:** `npm run build`; Browser-Check je Task (ohne Absenden bzw. mit Mock-Proxy).
**Abh.:** T7b, T13, T21 · **Dateien:** `ui/frontend/src/**`, `ui/backend/server.py` (Asset- und Audio-Durchreichung) · **Umfang:** L (aufteilen: Assets / Spezialformulare / Ergebnisanzeige)

#### T27: Branding „AI Video Studio“ und Provider-Texte
**Beschreibung:** Header, Titel, Login und Footer. Der Kostenhinweis nennt den
Provider des Modells; Prompt-Tipps verweisen auf den Guide; Jobdetails zeigen
Provider, Task und Backend.
**Akzeptanz:** „Seedance“ und „BytePlus“ kommen nur noch in providerbezogenen Texten vor.
**Verifikation:** `npm run build`; grep; Browser-Check auf Desktop- und Mobilbreite.
**Abh.:** T26 · **Dateien:** `ui/frontend/**` · **Umfang:** S

#### T28: LiteLLM-Ende-zu-Ende-Kompatibilität
**Beschreibung:** Eine automatisierte Integrationssuite, die einen echten
LiteLLM-Proxy (deine Version und die aktuelle, jeweils in einem Scratch-venv)
vor unseren Proxy mit gemockten Providern setzt. Geprüft wird pro Provider:
Create mit Extrafeldern (JSON und Multipart), Status, Content, Remix/Extension
über `extra_body`, `/v1/audio/speech`, `/v1/model/info` mit Guide und
Capabilities aus dem Export. Was LiteLLM nicht durchreicht (`DELETE`, die
Liste, `variant`), wird dokumentiert.
**Akzeptanz:** Die Suite ist für beide LiteLLM-Versionen grün und ohne Netzwerkzugriff auf Provider ausführbar.
**Verifikation:** Suite läuft lokal; sie ist als optionaler Test-Marker eingebunden.
**Abh.:** T13, T21, T22, T8 · **Dateien:** `tests/integration/test_litellm.py`, Hilfsskripte · **Umfang:** M

#### T29: Dokumentation und Konfiguration
**Beschreibung:** Zu aktualisieren:
- README und alle `docs/*`-Kapitel: Architektur, Installation (alle
  Variablen, Service Account, Regionen, Kling-Key), API-Referenz
  (Vertrag, native Routen, IDs), Video-Generierung (Fähigkeitsmatrix
  aus `/v1/models` generiert), LiteLLM-Integration (Export, Konventionen,
  Grenzen), Web Studio, Fehlerbehebung (Kling-429-Klassen,
  Google-Regionssperren)
- `.env.example`, `compose.yaml` (Mount für das Service-Account-JSON)
- `pyproject.toml`

**Akzeptanz:** Jeder Provider lässt sich allein nach der Doku einrichten; die Matrix in der Doku stimmt mit der API überein.
**Verifikation:** Review durch den Nutzer.
**Abh.:** T28 · **Dateien:** `README.md`, `docs/**`, `.env.example`, `compose.yaml`, `pyproject.toml` · **Umfang:** M

### Checkpoint: Fertig
- [ ] `pytest` (inkl. LiteLLM-Suite), `npm run build` und `./build.sh` (Imagebau) grün.
- [ ] Full Stack über „Local Full Stack“ geprüft; Health aller Provider grün.
- [ ] Abdeckungsprüfung: Jede Zeile der Feature-Matrizen in `research/*.md` ist einer erledigten Task zugeordnet.
- [ ] Review und Freigabe durch den Nutzer.

## Risiken und Gegenmaßnahmen

| Risiko | Auswirkung | Gegenmaßnahme |
|---|---|---|
| Veo verschwindet am 22.10. aus der Gemini API | Hoch | Veo standardmäßig über Vertex; dynamische Modellliste |
| Vertex „Pay-as-you-go: Not supported“ | erledigt | T1: Veo Lite lief ohne Provisioned Throughput |
| Omni-Edit/Extend über die Gemini API in der EU gesperrt | Mittel | Standard-Backend für Omni ist Vertex; klarer Fehlercode |
| LiteLLM ändert das Wire-Format erneut | Hoch | Toleranter Parser (A3), Integrationssuite gegen zwei Versionen (T28) |
| Kling hat zwei API-Generationen mit abweichenden Feldern | Mittel | Getrennte Mapper je Generation, gemeinsamer Statusnormalisierer, Tests je Generation |
| Kling-Modelle werden abgekündigt (Code 1203) | Mittel | Dynamische Prüfung und permissiver Fallback; 1203 → klarer Fehler |
| Umfang (29 Tasks) | Hoch | Contract first (T2), danach vier parallele Stränge; jede Task ist für sich lieferbar |
| Refactor bricht Seedance oder Real-Human | Hoch | T3 ohne Testanpassung; Charakterisierungstests |
| Speicherbedarf durch Outputs (Inline-Bytes, Kling-Downloads) | Mittel | TTL, Größenlimits, Streaming-Decode in Dateien |
| Kosten durch versehentliche Live-Tests | Mittel | Nur Mocks; Live-Tests nur mit Freigabe |

## Offene Punkte (ohne Nutzerentscheidung; werden in T1/T2 geklärt)

- Ob 3.0 Turbo native Audio hat, obwohl das API-Schema kein Feld dafür zeigt
  (T14: das Capability-Flag folgt dem API-Schema).
- Ob die nicht mehr dokumentierten Kling-Endpunkte (Video-Extend,
  Multi-Image) noch antworten: **nicht** einbauen, solange sie nicht
  dokumentiert sind; ggf. kostenfrei prüfen.
