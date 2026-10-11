# Google Video-Provider: Native Capability-Katalog (Veo 3.1 + Gemini Omni Flash)

Stand: 2026-10-11. Recherche aus Primärquellen (ai.google.dev, docs.cloud.google.com/gemini-enterprise-agent-platform, cloud.google.com Pricing, offizielles GoogleCloudPlatform-Notebook).
Feldnamen sind englisch und exakt so übernommen, wie Google sie dokumentiert.

> **Wichtiger Hinweis zur Namensänderung:** „Vertex AI“ heißt in der Doku jetzt **Gemini Enterprise Agent Platform** (kurz „Agent Platform“). Alte URLs unter `docs.cloud.google.com/vertex-ai/generative-ai/docs/...` leiten auf `docs.cloud.google.com/gemini-enterprise-agent-platform/...` um, teils auf unpassende Seiten. Hostnamen und Endpunkte bleiben `aiplatform.googleapis.com`. Im SDK heißt der Schalter jetzt `GOOGLE_GENAI_USE_ENTERPRISE=True` bzw. `genai.Client(enterprise=True, ...)`; `vertexai=True` taucht in Node-Beispielen weiter auf.

---

## 0. Kurzfazit (TL;DR)

| Thema | Gemini Developer API (API-Key) | Vertex AI / Agent Platform (ADC/Service Account) |
|---|---|---|
| Veo-3.1-IDs | nur Preview: `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`, `veo-3.1-lite-generate-preview`, **alle drei mit Shutdown am 2026-10-22**, Ersatz laut Google: `gemini-omni-1.1-flash` | GA: `veo-3.1-generate-001`, `veo-3.1-fast-generate-001` (Release 2025-11-17, Retirement „2026-11-17 or later“). Preview: `veo-3.1-lite-generate-001` (Release 2026-04-02) |
| Veo-Endpunkt | `POST /v1beta/models/{model}:predictLongRunning` und `GET /v1beta/{operation.name}` | `POST .../publishers/google/models/{model}:predictLongRunning` und `POST ...:fetchPredictOperation` |
| Veo-Region | n/a | laut Locations-Tabelle **nur `us-central1`**. SDK-Beispiele nutzen aber `location=global`, siehe „Unklar“ |
| Omni-IDs | GA `gemini-omni-1.1-flash`; Preview `gemini-omni-flash-preview` mit Shutdown 2026-10-22 (Changelog nannte vorher 2026-09-30) | nur Preview: `gemini-omni-1.1-flash-preview` und `gemini-omni-flash-preview` (Retirement 2027-06-30). **Keine GA-ID auf Vertex** |
| Omni-Endpunkt | Interactions API `POST https://generativelanguage.googleapis.com/v1beta/interactions` | Interactions API `POST https://aiplatform.googleapis.com/v1beta1/projects/{P}/locations/global/interactions`. Das Model-Datenblatt nennt auch „GenerateContent API: Supported“, dafür gibt es aber kein Video-Beispiel |
| Omni async | `background: true` ist im API-Schema vorhanden, laut Doku „for standard Gemini models“. Für Omni nicht explizit dokumentiert, aber implizit genannt („Set background=false … for faster“) | **Explizit dokumentiert**: `background: true` liefert `{"id","status":"in_progress"}`, Polling über `GET .../interactions/{id}` |
| Omni-Region | n/a; Edit/Extend **hochgeladener** Videos ist in EWR/CH/UK nicht verfügbar | nur `global` (CMEK zusätzlich `us`/`eu`) |

---

## 1. Veo 3.1: Modell-IDs und Lebenszyklus

### 1.1 Gemini Developer API

| Modell | ID | Status | Release | Shutdown | Ersatz |
|---|---|---|---|---|---|
| Veo 3.1 | `veo-3.1-generate-preview` | Preview | 2025-10-15 | **2026-10-22** | `gemini-omni-1.1-flash` |
| Veo 3.1 Fast | `veo-3.1-fast-generate-preview` | Preview | 2025-10-15 | **2026-10-22** | `gemini-omni-1.1-flash` |
| Veo 3.1 Lite | `veo-3.1-lite-generate-preview` | Preview | 2026-03-31 | **2026-10-22** | `gemini-omni-1.1-flash` |
| (Veo 3.0 / 2.0) | `veo-3.0-*-001`, `veo-2.0-generate-001` | abgeschaltet | – | 2026-06-30 | „veo-3.1-…-preview or the GA models on the Gemini Enterprise Agent Platform“ |

- Die Gemini API listet **keine** `-001`-GA-IDs für Veo 3.1. Die Deprecation-Tabelle verweist für GA-Veo ausdrücklich auf die Agent Platform (Vertex).
- Folge: Ab dem 2026-10-22 gibt es nach heutigem Doku-Stand **kein Veo 3.1 mehr auf der Gemini Developer API**. Google sagt, Shutdown-Daten seien „earliest possible dates“.
- Quellen: https://ai.google.dev/gemini-api/docs/deprecations, https://ai.google.dev/gemini-api/docs/veo, https://ai.google.dev/gemini-api/docs/models/veo-3.1-generate-preview, https://ai.google.dev/gemini-api/docs/changelog

### 1.2 Vertex AI / Agent Platform

| Modell | ID | Launch Stage | Release | Retirement |
|---|---|---|---|---|
| Veo 3.1 Generate | `veo-3.1-generate-001` | **GA** | 2025-11-17 | 2026-11-17 or later |
| Veo 3.1 Fast Generate | `veo-3.1-fast-generate-001` | **GA** | 2025-11-17 | 2026-11-17 or later |
| Veo 3.1 Lite Generate | `veo-3.1-lite-generate-001` | **Preview** | 2026-04-02 | – |

- `veo-3.1-generate-preview` und `veo-3.1-fast-generate-preview` tauchen auf Vertex nur noch in Alt-Beispielen der Reference-Seite auf. Eine Websuche fand Vertex-Release-Notes (März 2026), nach denen die Preview-Endpunkte am 2026-04-02 entfernt wurden. Das wurde nicht direkt verifiziert.
- Consumption laut Datenblatt: „Provisioned Throughput: Supported; Batch: Not supported; **Pay-as-you-go: Not supported**; Fixed quota: Supported“. Das ist ungewöhnlich, siehe „Unklar“.
- Quelle: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/veo/3-1-generate

---

## 2. Veo 3.1: Endpunkte, Operation, Download

### 2.1 Gemini Developer API

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:predictLongRunning
Header: x-goog-api-key: $KEY
Body:   {"instances":[{...}], "parameters":{...}}
→ {"name":"models/{model}/operations/{id}"}

GET https://generativelanguage.googleapis.com/v1beta/{name}     (Header x-goog-api-key)
→ {"done":true,"response":{"generateVideoResponse":{"generatedSamples":[{"video":{"uri":"..."}}], ...}}}

Download: GET {video.uri} mit Header x-goog-api-key, Redirects folgen (curl -L)
```

- Ergebnis: `response.generateVideoResponse.generatedSamples[0].video.uri`.
- **Aufbewahrung: 2 Tage**, danach gelöscht. Wird ein Video für eine Extension referenziert, startet der 2-Tage-Timer neu. Eine Extension zählt als neues Video.
- Latenz: mindestens etwa 11 s, maximal etwa 6 min in Spitzenzeiten.
- Bilder und Videos gibt die REST-Doku als `{"inlineData":{"mimeType":"image/png","data":"<b64>"}}` an, sowohl für `image`, `lastFrame` und `referenceImages[].image` als auch für `video`. Siehe „Unklar“ zu `bytesBase64Encoded`.
- Banner auf der Seite: „This feature is currently only available with the generateContent API.“ Das widerspricht den Beispielen, die durchgehend `predictLongRunning` nutzen. Es wirkt wie ein fehlplatzierter Banner.
- Quelle: https://ai.google.dev/gemini-api/docs/veo

### 2.2 Vertex AI

```
POST https://us-central1-aiplatform.googleapis.com/v1/projects/{P}/locations/us-central1/publishers/google/models/{MODEL}:predictLongRunning
Authorization: Bearer <ADC token>
→ {"name":"projects/{P}/locations/us-central1/publishers/google/models/{MODEL}/operations/{OP}"}

POST https://us-central1-aiplatform.googleapis.com/v1/projects/{P}/locations/us-central1/publishers/google/models/{MODEL}:fetchPredictOperation
Body: {"operationName":"projects/.../operations/{OP}"}
→ {"name":..., "done":true, "response":{
     "@type":"type.googleapis.com/cloud.ai.large_models.vision.GenerateVideoResponse",
     "raiMediaFilteredCount":0,
     "videos":[{"gcsUri":"gs://BUCKET/TIMESTAMPED_FOLDER/sample_0.mp4","mimeType":"video/mp4"}]}}
```

- Ohne `storageUri` gilt laut Doku: „video bytes are returned in the response“. Der übliche Feldname ist `videos[].bytesBase64Encoded`. Er steht in der aktuellen Doku nicht im Beispiel, siehe „Unklar“.
- Mit `storageUri` (`gs://…`) schreibt Google nach GCS. Der Download braucht dann eigene GCS-Credentials (Storage Object Viewer). Es gibt keine Google-seitige Aufbewahrungsfrist, weil die Daten im eigenen Bucket liegen.
- Schema `GenerateVideoResponse`: `generatedSamples[]` (Media mit `video`), `raiMediaFilteredCount` (int), `raiMediaFilteredReasons[]` (string). Die REST-Antwort von `fetchPredictOperation` nutzt laut Beispiel `videos[]`.
- Optional: `parameters.pubsubTopic` (`projects/{p}/topics/{t}`) für Fortschritts-Events.
- Quellen: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-text, https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/Shared.Types/GenerateVideoResponse, https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/Shared.Types/VideoGenerationModelResult

---

## 3. Veo 3.1: Request-Schema

### 3.1 `instances[]` (Vertex-Schema `VideoGenerationModelInstance`; Gemini nutzt dieselben Namen)

| Feld | Typ | Bedeutung und Regeln |
|---|---|---|
| `prompt` | string | Pflicht bei `referenceImages`. Gemini: max. 1.024 Token |
| `image` | Image | erstes Frame. **Schließt `video` und `referenceImages` aus** |
| `lastFrame` | Image | letztes Frame, **nur zusammen mit `image`** |
| `video` | Video | Ohne `mask` bedeutet das Extension, mit `mask` Edit. Schließt `image` und `referenceImages` aus |
| `mask` | Mask | `maskMode`: `insert`, `remove`, `remove_static`, `outpaint`. Für 3.1 **nicht dokumentiert/unterstützt** (siehe 4.) |
| `referenceImages[]` | ReferenceImage | `{image, referenceType: "asset"|"style"}`. „up to 3 asset images or 1 style image“. Schließt `image`, `video` und `lastFrame` aus |
| `cameraControl` | string | `fixed`, `pan_left`, `pan_right`, `tilt_up`, `tilt_down`, `truck_left`, `truck_right`, `pedestal_up`, `pedestal_down`, `push_in`, `pull_out`. Nur mit `image`. Für 3.1 nicht in den Modellseiten genannt (Pricing ordnet „camera controls“ Veo 2 zu) |

**Image (Vertex):** `{"mimeType":"image/jpeg"|"image/png", "bytesBase64Encoded": "...", | "gcsUri":"gs://..."}`. Maximal 20 MB. Empfohlen sind 720p oder mehr in 16:9 oder 9:16, andere Formate werden skaliert oder mittig beschnitten (`resizeMode`).
**Video (Vertex):** `mimeType` ∈ `video/mov`, `video/mpeg`, `video/mp4`, `video/mpg`, `video/avi`, `video/wmv`, `video/mpegps`, `video/flv`; Daten als `gcsUri` oder `bytesBase64Encoded`. Für Extension laut Guide **MP4**.
**Mask:** `mimeType` (png, jpeg, webp oder Video-Typen), `maskMode`, `bytesBase64Encoded`/`gcsUri`.

### 3.2 `parameters` (Vertex-Schema `VideoGenerationModelParams`)

| Feld | Werte / Default | Gemini API | Vertex |
|---|---|---|---|
| `aspectRatio` | `"16:9"` (Default), `"9:16"` | ✓ | ✓ |
| `durationSeconds` | 4, 6, 8. Pflicht 8 bei 1080p, 4k, Referenzbildern und Extension (Gemini); Lite: 8 bei 1080p und Referenzen | ✓ (als String in der Tabelle: `"4"`, `"6"`, `"8"`) | ✓ (number; Default 8) |
| `resolution` | `"720p"` (Default), `"1080p"`, `"4k"` | ✓ (4k nicht bei Lite; Extension nur 720p) | ✓ (siehe Modelltabelle) |
| `negativePrompt` | string | nicht dokumentiert | ✓ |
| `personGeneration` | Gemini: `allow_all`/`allow_adult` je Modus. Vertex-Schema: `dont_allow`, `allow_adult` (Default), `allowAll`; der How-to-Guide schreibt `disallow` | ✓ | ✓ |
| `seed` | uint32 0–4294967295 | ✓ („slightly improves determinism“) | ✓. Bei `sampleCount>1` erhält jedes Video einen eigenen Seed. Mit `enhancePrompt` ist das Ergebnis nicht deterministisch |
| `numberOfVideos` / `sampleCount` | Gemini: `numberOfVideos` = **1**; Vertex: `sampleCount` **1–4** | 1 | 1–4 |
| `generateAudio` | bool, Default **true** | nicht dokumentiert (Ton ist bei 3.1 „Always on“) | ✓. Ohne Audio ist der Preis niedriger |
| `enhancePrompt` | bool, Default **true** | – | ✓ (`enablePromptRewriting` ist deprecated) |
| `storageUri` | `gs://bucket/pfad/` | – | ✓ (ohne: Bytes in der Antwort) |
| `compressionQuality` | `optimized` (Default), `lossless` | – | ✓ |
| `resizeMode` | `pad` (Default), `crop`. Für i2v | – | ✓ |
| `fps` | int; Modelle können nur 24 | – | ✓ (Schema) |
| `pubsubTopic` | `projects/{p}/topics/{t}` | – | ✓ |
| `task` | `textToVideo`, `imageToVideo`, `referenceToVideo`, `edit`, `extend`, `upscale`. Optional, sonst wird der Task aus den Inputs abgeleitet | – | ✓ (Schema) |

`personGeneration` in der Gemini API: Bei Veo 3.1 und Fast gilt für Text-to-Video und Extension **nur `allow_all`**, für Image-to-Video, Interpolation und Referenzbilder **nur `allow_adult`**. Bei Lite gilt dasselbe ohne Extension. In **EU, UK, CH und MENA** ist **`allow_adult` der einzige erlaubte Wert**.

Quellen: https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/Shared.Types/VideoGenerationModelInstance, https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/Shared.Types/VideoGenerationModelParams, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-an-image, https://ai.google.dev/gemini-api/docs/veo (Abschnitt „Veo API parameters and specifications“)

---

## 4. Veo 3.1: Modi und Fähigkeiten je Modell

### 4.1 Gemini Developer API (Preview-IDs)

| Modus | 3.1 / 3.1 Fast | 3.1 Lite |
|---|---|---|
| Text-to-Video | ✓ | ✓ |
| Image-to-Video (`image`) | ✓ | ✓ |
| First/Last Frame (`image`+`lastFrame`) | ✓ | ✓ |
| Reference-to-Video, asset (≤3) | ✓ (nur 8 s) | ✗ |
| Style-Referenz | ✗ (nur `asset` dokumentiert) | ✗ |
| Extension (`video`) | ✓: +7 s pro Schritt, ≤20 Schritte, Input ≤141 s, nur 720p, 16:9 oder 9:16, **muss ein Veo-Video aus den letzten 2 Tagen sein**. Output ist **ein kombiniertes Video** bis 148 s | ✗ |
| Insert/Remove/Outpaint/Upscale | ✗ | ✗ |
| Auflösungen | 720p (Default), 1080p (8 s), 4k (8 s) | 720p, 1080p (8 s) |
| Videos pro Request | 1 | 1 |
| Ton | immer an | immer an |
| fps | 24 | 24 |

### 4.2 Vertex AI (Modellseite plus How-to-Seiten)

| Modus | `veo-3.1-generate-001` | `veo-3.1-fast-generate-001` | `veo-3.1-lite-generate-001` (Preview) |
|---|---|---|---|
| Text-to-Video | ✓ | ✓ | ✓ |
| Image-to-Video | ✓ | ✓ | ✓ laut Fähigkeiten und How-to-Liste; das Datenblatt sagt aber „Image: Not supported“ (Widerspruch) |
| First/Last Frame | ✓ | ✓ | ✓ (How-to listet Lite) |
| Reference-to-Video (asset, ≤3) | ✓ | ✓ | ✗ |
| Style-Referenz | ✗ (Datenblatt: nur „Asset images“) | ✗ | ✗ |
| Extension | ✓ | ✓ | ✓ (laut Datenblatt und Extend-Seite) |
| Edit (Insert/Remove/Outpaint via `mask`) | nicht dokumentiert. Die Edit-Seite listet **nur Omni** | – | – |
| Upscale | nur `task: upscale` im Schema, keine Doku oder Seite | – | – |
| Längen | 4, 6, 8 s; Referenzbilder nur 8 s | 4, 6, 8 | 4, 6, 8 |
| Output-Auflösung | 720p, 1080p, **4K** | 720p, 1080p | 720p, 1080p |
| Input-Auflösung | 720p, 1080p | 720p, 1080p | 720p, 1080p |
| Videos pro Prompt | bis 4 | bis 4 | bis 4 |
| Bild-Input max. | 20 MB | 20 MB | 20 MB |
| fps / MIME | 24 / `video/mp4` | 24 / mp4 | 24 / mp4 |
| Promptsprache | Englisch | Englisch | Englisch |

**Vertex-Extension:** Input-MP4 1–30 s, 24 fps, 720p/1080p/4k, 16:9 oder 9:16. Die Extension ist **7 s** lang, insgesamt sind bis **37 s** möglich (Omni: 40 s). Ob der Output das kombinierte Video oder nur das Segment ist, steht nicht explizit da. Das Input-Video wird per `video.gcsUri` übergeben („the Veo video that you're extending“).

Quellen: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/veo/3-1-generate, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/extend-videos, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-references, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-first-and-last-frames, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/edit-videos

### 4.3 RAI / Safety

- Vertex: `raiMediaFilteredCount` und `raiMediaFilteredReasons[]` in der Operation-Response.
- Gemini API: gefilterte Videos werden nicht berechnet. Veo 3.1 blockiert manchmal wegen Audio-Problemen, auch das kostet nichts. Ob die Felder in `generateVideoResponse` gleich heißen, zeigt die Gemini-Doku nicht. Laut Praxis aus dem bestehenden Guide und Community-Code: ja, als `raiMediaFilteredCount` und `raiMediaFilteredReasons`.
- SynthID in jeder Ausgabe. Vertex zusätzlich C2PA Content Credentials.

---

## 5. Veo 3.1: Regionen, Quotas, Preise

### 5.1 Regionen (Vertex)

Die Locations-Tabelle (per Browser ausgewertet, Checkmarks per CSS-Klasse `compare-yes`) zeigt für `veo-3.1-generate-001`, `veo-3.1-fast-generate-001` und `veo-3.1-lite-generate-001` **nur `us-central1`**: kein `global`, keine EU-Region, keine `us`/`eu`-Multi-Region. Das Modell-Datenblatt sagt ebenfalls „United States: us-central1“.
Quelle: https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations

### 5.2 Quotas

- Vertex: „Regional online prediction requests per base model per minute: 50“ (das Datenblatt schreibt fälschlich „tokens“). Quota-Metrik: `long_running_online_prediction_requests_per_base_model`. https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/quotas
- Gemini API: Limits pro Projekt und Tier, einsehbar nur in AI Studio. RPD-Reset um Mitternacht Pacific. Zusätzlich gibt es spend-basierte Limits pro 10 Minuten: Tier 1 $10, Tier 2 $50, Tier 3 $200. Bei Überschreitung kommt `429 RESOURCE_EXHAUSTED`. Veo hat **keinen Free Tier**. https://ai.google.dev/gemini-api/docs/rate-limits

### 5.3 Preise (USD pro Sekunde Output)

| Modell | Gemini API (mit Audio) | Vertex mit Audio | Vertex ohne Audio |
|---|---|---|---|
| Veo 3.1 | 720p/1080p $0.40, 4k $0.60 | 720p/1080p $0.40, 4k $0.60 | 720p/1080p $0.20, 4k $0.40 |
| Veo 3.1 Fast | 720p $0.10, 1080p $0.12, 4k $0.30 | $0.10 / $0.12 / 4k $0.30 | $0.08 / $0.10 / 4k $0.25 |
| Veo 3.1 Lite | 720p $0.05, 1080p $0.08 | $0.05 / $0.08 | $0.03 / $0.05 |

Die Vertex-Pricing-Seite listet 4k für Fast, das Fast-Datenblatt nennt aber nur 720p und 1080p. Siehe „Unklar“.
Quellen: https://ai.google.dev/gemini-api/docs/pricing, https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing#veo

---

## 6. Gemini Omni Flash: Modell-IDs

| Backend | ID | Status | Release | Shutdown/Retirement | Bemerkung |
|---|---|---|---|---|---|
| Gemini API | `gemini-omni-1.1-flash` | **Stable/GA**, nur Paid Tier | 2026-08-27 | keine angekündigt | Context Window 1.048.576 Token; Output 3–10 s, 360p/720p/1080p/4K, 24 fps |
| Gemini API | `gemini-omni-flash-preview` | Preview | 2026-06-30 | **2026-10-22** (Deprecation-Tabelle; Changelog vom 27.08. nannte 2026-09-30) | Ersatz: `gemini-omni-1.1-flash` |
| Vertex | `gemini-omni-1.1-flash-preview` | Preview | 2026-08-27 | – | volle Modi |
| Vertex | `gemini-omni-flash-preview` | Preview | 2026-06-30 | 2027-06-30 | **nur T2V und Edit**, nur 720p; kein I2V, keine Referenzen, kein First/Last, keine Extension |

Auf Vertex gibt es **keine** GA-ID `gemini-omni-1.1-flash`. Die Locations-Tabelle führt `gemini-omni-1.1-flash-preview` als „Latest supported model version“.
Quellen: https://ai.google.dev/gemini-api/docs/models/gemini-omni-flash, https://ai.google.dev/gemini-api/docs/deprecations, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-1-1-flash, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-flash-preview

---

## 7. Gemini Omni Flash: Endpunkte und Ausführungsmodi

### 7.1 Gemini Developer API

- `POST https://generativelanguage.googleapis.com/v1beta/interactions` (Header `x-goog-api-key` oder `?key=`).
- `GET /v1beta/interactions/{id}`, `POST /v1beta/interactions/{id}/cancel` (nur für laufende Background-Interactions), `DELETE` existiert ebenfalls.
- `interaction.output_video` gibt es **nur im SDK**. Über REST liest man aus `steps[]` den Step mit `type:"model_output"` und darin `content[]` mit `{"type":"video","mime_type":"video/mp4","data"|"uri"}`.
- **Default-Modus ist synchron**: Die Antwort enthält das Video inline als base64.
- **`background: true`:** Das Feld existiert im Schema („Whether to run the model interaction in the background“). Die Background-Doku nennt „standard Gemini models … and Managed Agents“. Die Omni-Seite erwähnt `background` nur in der Empfehlung „Set background=false, store=false, stream=false for faster, synchronous unary generation“. Ein explizites Omni-Beispiel mit `background=true` gibt es auf der Gemini-API-Seite **nicht**. Wahrscheinlich funktioniert es, verifiziert ist es nicht. **`store=false` ist mit `background` inkompatibel.**
- Status-Werte: `in_progress`, `requires_action`, `completed`, `failed`, `cancelled`, `incomplete`, `queued`.
- **Known issue:** `GET /v1beta/interactions/{id}` liefert das Video **inline als base64 (`data`)**, auch wenn mit `delivery:"uri"` erzeugt wurde. Die `uri` ist nur in der Create-Response oder im SSE-Stream garantiert. Für den Proxy heißt das: Bei Background plus Polling muss man mit Inline-Bytes rechnen. Bei Videos über 4 MB kann das zu Payload-Problemen führen.
- Multi-Turn: `previous_interaction_id` setzt `store=true` voraus (Default true). Eine Folge-Interaction auf eine noch laufende (`in_progress`) gibt `400`.
- Interaction-Retention: Paid Tier **55 Tage**, Free Tier 1 Tag (Omni ist ohnehin nur Paid).
- Streaming: `stream: true` (SSE-Events `interaction.created`, `step.start`, `step.delta`, `step.stop`, `interaction.completed`).
- Quellen: https://ai.google.dev/gemini-api/docs/omni, https://ai.google.dev/api/interactions-api, https://ai.google.dev/gemini-api/docs/background-execution, https://ai.google.dev/gemini-api/docs/interactions

### 7.2 Vertex AI

- `POST https://aiplatform.googleapis.com/v1beta1/projects/{P}/locations/global/interactions`
- `GET .../interactions/{id}` (optional `?stream=true` für den Replay als SSE), `POST .../interactions/{id}/cancel` (nur Background; „Users will still be charged for partially generated tokens“), `DELETE .../interactions/{id}`, `GET .../interactions?page_size=..` (List; Default 10, max. 500).
- Dokumentierte Modi (wörtlich): „Synchronous: stateless“, „Synchronous: stateful (store=true)“, „Synchronous: stateful streaming (store+stream)“, „**Asynchronous: Set background to true** to run video generation in the background and retrieve the result later using the interaction ID.“ Antwort beim Async-Create: `{"id":"…","status":"in_progress","object":"interaction"}`.
  - Achtung: Im REST-Beispiel steht `"background": true` fälschlich **innerhalb** des `input`-Parts. Das offizielle Notebook setzt es korrekt auf Top-Level (`client.interactions.create(..., background=True)`) und pollt `client.interactions.get(id=...)`, bis `status ∈ {completed, failed}`.
- Retention: „Stored and asynchronous interactions are retained for up to **7 days**“ (T2V-Seite und Interactions-Overview) bzw. „**14 days**“ (I2V-, First/Last-, Referenz-, Edit- und Extend-Seiten). Widerspruch, siehe „Unklar“.
- Endpunkte: nur `locations/global`; `us`/`eu` nur mit CMEK.
- GenerateContent: Das Datenblatt sagt „GenerateContent API: Supported“. Für Videoausgabe gibt es aber **keinen** dokumentierten Request (kein `responseModalities: VIDEO`-Beispiel). Alle Video-How-tos nutzen ausschließlich die Interactions API. **Empfehlung: Interactions API verwenden.**
- Quellen: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-text, https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/interactions-api, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/interactions, https://github.com/GoogleCloudPlatform/generative-ai/blob/main/vision/getting-started/gemini_omni_1_1_flash_video_gen.ipynb

---

## 8. Gemini Omni Flash: Request-Schema

```json
{
  "model": "gemini-omni-1.1-flash",            // Vertex: "gemini-omni-1.1-flash-preview"
  "input": "prompt"  |  [ {content part}, ... ]  // Vertex-Stateful-Beispiele: [{"type":"user_input","content":[...]}]
  "response_format": {                          // Objekt oder Array von ResponseFormat
    "type": "video",
    "aspect_ratio": "16:9" | "9:16",            // Gemini: Default 16:9; Vertex: sonst aus dem Prompt abgeleitet
    "resolution": "360p" | "720p" | "1080p" | "4k",  // Default 720p; 1080p/4k sind upscaled
    "duration": "3s" … "10s",                   // String, ganze Zahl + "s"
    "delivery": "inline" | "uri",
    "gcs_uri": "gs://bucket/prefix/"            // nur Vertex; „Required for Vertex if delivery mode is URI“
  },
  "generation_config": { "video_config": { "task": "text_to_video" | "image_to_video" | "reference_to_video" | "edit" | "extend" } },
  "previous_interaction_id": "v1_…",
  "store": true, "stream": false, "background": false
}
```

**Content-Parts im `input`:**

| Typ | Gemini API | Vertex |
|---|---|---|
| `{"type":"text","text":…}` | ✓ | ✓ |
| `{"type":"image","mime_type":…,"data":b64}` oder `"uri"` (Files API) | ✓ (jpeg/png in den Beispielen) | ✓ (`uri: gs://…` oder `data`); MIME png/jpeg/webp/heic/heif; ≤10 Bilder; 20 MB inline, 30 MB aus GCS |
| `{"type":"video","mime_type":…,"uri"|"data"}` | ✓, empfohlen über die Files API | ✓, `gs://` oder inline; MIME `video/3gpp`, `mp4`, `mpeg`, `quicktime`, `webm`, `x-flv`, `x-ms-wmv` (Schema: auch `mov`, `avi`, `wmv`); ≤3 Videos, je ≤10 s; 16:9/9:16; 360p–4K |
| Audio | **nicht unterstützt** („Uploading audio references is unsupported“) | **nicht unterstützt** („Audio: Not supported“) |

- Rollen lassen sich im Prompt über Tags binden: `<FIRST_FRAME>`, `<LAST_FRAME>`, `<IMAGE_REF_N>` und `<VIDEO_REF_N>` (0-basiert). Für komplexe Fälle gibt es Prefix-Deklarationen wie `[# Sources <FIRST_FRAME>@Image1]`.
- Ohne `task` erkennt das Modell den Modus selbst. Google empfiehlt, zuerst über den Prompt zu steuern, weil `task` zusätzliche Constraints setzt.
- Bei `task: image_to_video` gilt: ein Bild ist das Startframe, ein zweites Bild das Endframe (so steht es im Schema).
- Nicht unterstützt: System Instructions, `temperature`/`top_p`, Stop Sequences, **negative prompts** (Negatives gehören in den Prompt), YouTube-URLs, Multi-Video-Reasoning. Auf der Gemini API zusätzlich kein Provisioned Throughput.
- Das Feld `duration` dokumentiert nur Vertex (How-to plus Notebook: „3s - 10s“). Die Gemini-Omni-Guide-Seite nennt kein Duration-Feld, das gemeinsame API-Reference-Schema (`VideoResponseFormat.duration`) und das Modelldatenblatt („Output video 3s-10s“) aber schon.
- Quellen: https://ai.google.dev/gemini-api/docs/omni, https://ai.google.dev/api/interactions-api, https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/interactions-api, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-references

---

## 9. Gemini Omni Flash: Modi

| Modus | Umsetzung | `gemini-omni-1.1-flash` (Gemini) / `-1.1-flash-preview` (Vertex) | `gemini-omni-flash-preview` (Vertex) |
|---|---|---|---|
| Text-to-Video | nur Text | ✓ | ✓ (720p) |
| Image-to-Video | 1 Bild + Prompt (`image_to_video`) | ✓ | ✗ |
| First/Last Frame (Interpolation) | 2 Bilder (`image_to_video`) | ✓ | ✗ |
| Reference-to-Video (Bilder) | mehrere Bilder (`reference_to_video`); keine harte Maximalzahl auf der Gemini API, Vertex ≤10 Bilder pro Prompt; Notebook empfiehlt ≤5 Bilder | ✓ | ✗ |
| Video-Referenz | ≤3 Clips je ≤3 s; Audio der Referenz wird ignoriert | ✓ | ✗ |
| Edit (Video-to-Video per Prompt) | Video + Prompt (`edit`); Upload-Input ≤10 s | ✓ | ✓ |
| Multi-Turn-Edit | `previous_interaction_id` (benötigt `store=true`) | ✓ | (Vertex-Beispiele mit Stateful listen nur 1.1) |
| Extend | Fortsetzung von 3–10 s am Ende (`extend`); Upload-Input ≤10 s (Vertex-Seite: Input 1–30 s); gesamt bis **40 s**; nur am Ende, kein Prepend und kein Mittelteil; Bild-Referenz mit `<IMAGE_REF_0>` möglich | ✓ | ✗ |
| Upscaling | über `resolution` 1080p/4k (Output wird upscaled); kein eigener Upscale-Task | ✓ | ✗ |
| Ton | wird immer generiert (Sprache, Musik, SFX). Voice-Editing nicht unterstützt. Hochgeladene Videos mit Dialog lassen sich nicht um weiteren Dialog verlängern (per Multi-Turn schon) | ✓ | ✓ |

**Regionale Einschränkungen (Gemini API):** Edit und Extend **hochgeladener** Videos sind in **EWR, Schweiz und UK nicht verfügbar**; mit modellgenerierten Videos (Multi-Turn) geht es. Bilder mit Minderjährigen dürfen in EWR/CH/UK nicht hochgeladen oder bearbeitet werden. Bilder bestimmter bekannter Personen sind gesperrt. Für Vertex sind solche Einschränkungen nicht dokumentiert.

Quellen: https://ai.google.dev/gemini-api/docs/omni (Limitations), https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/extend-videos, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/edit-videos

---

## 10. Gemini Omni Flash: Output-Delivery

### Gemini API
- Default `inline`: `steps[].content[]` mit `{"type":"video","mime_type":"video/mp4","data":"<b64>"}`.
- Bei Videos **über 4 MB** (alles über 720p) empfiehlt Google `delivery:"uri"`. Die Antwort enthält dann `"uri":"https://generativelanguage.googleapis.com/v1beta/files/{ID}:download?alt=media"`.
- Danach `GET /v1beta/files/{ID}` pollen, bis `state == "ACTIVE"` (oder `FAILED`), und mit `GET /v1beta/files/{ID}:download?alt=media` herunterladen (API-Key nötig).
- Files API: Dateien werden **nach 48 h gelöscht**; 20 GB pro Projekt; max. 2 GB pro Datei. Der Input-Upload für Videos läuft über dieselbe Files API (resumable Upload) und ist danach 48 h gültig.
- Quellen: https://ai.google.dev/gemini-api/docs/omni, https://ai.google.dev/gemini-api/docs/files, https://ai.google.dev/api/files

### Vertex
- Ohne `gcs_uri`/`delivery:uri` kommt das Video inline als `data`.
- Mit `delivery:"uri"` plus `gcs_uri` gilt `content[].uri = "gs://…/123.mp4"`. Lesen braucht GCS-IAM.
- Antwort-`usage` enthält `output_tokens_by_modality[{modality:"video",tokens:…}]` und `total_thought_tokens`. Das eignet sich für die Kostenerfassung.

---

## 11. Gemini Omni Flash: Preise, Quotas, Regionen

**Preise (Gemini API und Vertex identisch):** Input (Text/Bild/Video/Audio) $1.50 pro 1M Token; Text-Output inkl. Reasoning $9.00 pro 1M; **Video-Output $17.50 pro 1M Token**.
Video-Output-Token pro Sekunde laut Vertex-Pricing: 360p **1.931**, 720p **5.792**, 1080p **8.688**, 4k **17.376**. Daraus ergeben sich etwa **$0.034 / $0.101 / $0.152 / $0.304 pro Sekunde**.
Input-Token: 1.120 pro Bild, 32 pro Audio-Sekunde, 5.792 pro Video-Sekunde. Gemini API: kein Free Tier, kein Batch. Die Gemini-Seite nennt nur den 720p-Kurs (etwa $0.10/s); dass für die anderen Auflösungen dieselbe Token-Umrechnung gilt, ist eine Annahme.
Quellen: https://ai.google.dev/gemini-api/docs/pricing, https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing

**Vertex-Consumption:** `gemini-omni-1.1-flash-preview`: „Provisioned Throughput: Supported; Pay-as-you-go: Not supported; Fixed quota: Supported“. Gleichzeitig steht „Standard PayGo: Global“ unter Regionen. `gemini-omni-flash-preview`: nur Fixed quota.
PT-Enforcement-Fenster für Omni Flash Preview: 1–9 GSU 2.000 s, 10–19 200 s, 20–39 100 s, 40–66 50 s, 67+ 30 s. Google empfiehlt, `duration` und `resolution` immer zu setzen, sonst schätzt PT mit Maximalwerten.
Quota-Metrik: `global_generate_content_requests_per_minute_per_project_per_base_model`.
Quellen: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-1-1-flash, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/provisioned-throughput/gemini-omni-models, https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/quotas

**Vertex-Regionen:** beide Omni-Modelle **nur `global`**. Token-Limits: Input 131.072, Output 57.920.

---

## 12. Credential-Validierung (kostenlos)

| Backend | Empfohlener Check | Was er prüft |
|---|---|---|
| Gemini API | `GET https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000` mit `x-goog-api-key` (Default 50 pro Seite, max. 1000) | Key gültig. Zusätzlich lässt sich sehen, welche `veo-*`- und `gemini-omni-*`-IDs der Key sieht. Alternativ `GET /v1beta/models/{id}` |
| Vertex | ADC-Token holen (`google.auth.default()` + refresh), dann projektgebunden und ohne Kosten: `GET https://aiplatform.googleapis.com/v1beta1/projects/{P}/locations/global/interactions?page_size=1` | Token, Projekt, API aktiviert, IAM (`aiplatform`-Rechte). Lädt nichts |
| Vertex (Modellexistenz) | `GET https://us-central1-aiplatform.googleapis.com/v1beta1/publishers/google/models/veo-3.1-generate-001` (`publishers.models.get`) | Model-Garden-Metadaten. Nicht projektgebunden, daher prüft das kein Projekt-IAM |

Diese Vorschläge sind aus den Referenzen abgeleitet und nicht live getestet. Ein `fetchPredictOperation` mit einem Fake-Namen wäre auch möglich, ist aber unsauber.
Quellen: https://ai.google.dev/api/models, https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/interactions-api, https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/v1beta1/publishers.models/get

---

## 13. Abgleich mit `prompt_guides/veo_3_1.md` (Abschnitte 2, 3, 7, 8)

| Aussage im Guide | Status laut Primärquelle |
|---|---|
| IDs `veo-3.1-…-preview` | stimmt für die Gemini API, aber **Shutdown 2026-10-22**. Vertex hat GA-IDs `-001` |
| `sampleCount`/`numberOfVideos` = 1 | nur Gemini API. **Vertex: 1–4** |
| „Lite: keine Extension“ | stimmt für die Gemini API. **Vertex-Lite unterstützt Extension** laut Datenblatt und Extend-Seite |
| „Style-Referenz nicht bei 3.1“ | bestätigt (nur `asset`) |
| „Add/Remove Object läuft über Veo 2“ | Für 3.1 gibt es weiterhin keine Mask-Edit-Doku. Die Edit-Seite listet jetzt nur Omni. Das Schema enthält `mask`/`maskMode` trotzdem |
| Extension +7 s, ≤20×, ≤141 s Input, 720p | Gemini API ✓. **Vertex abweichend:** Input 1–30 s, 720p/1080p/4k, gesamt ≤37 s |
| `personGeneration` `dont_allow`/`allow_adult`/`allow_all` | Gemini nutzt `allow_all`/`allow_adult` je Modus. Das Vertex-Schema schreibt `dont_allow`/`allow_adult`/`allowAll`, der Vertex-Guide `disallow` |
| 2 Tage Retention | Gemini API ✓. Vertex mit `storageUri`: eigener Bucket |
| `lastFrame` erzwingt 8 s (Praxis) | nicht in der Primärdoku. Die Gemini-Tabelle nennt nur 1080p/4k/Referenz/Extension als 8-s-Zwang |

---

## 14. Unklar / nicht verifizierbar

1. **Vertex-Veo-Region:** Locations-Tabelle und Datenblatt nennen nur `us-central1`. Die SDK-Beispiele derselben How-to-Seiten setzen aber `GOOGLE_CLOUD_LOCATION=global`. Ob `locations/global` für Veo funktioniert, ist offen. Sicher ist `us-central1`.
2. **Vertex „Pay-as-you-go: Not supported“** für Veo 3.1 (GA) und Omni 1.1 Preview, während die Pricing-Seite On-Demand-Preise listet und Omni „Standard PayGo: global“ ausweist. Ob ein Projekt ohne PT oder Fixed Quota sofort generieren kann, lässt sich ohne Live-Test nicht klären.
3. **4K auf Vertex:** Das Veo-3.1-Datenblatt nennt 4K für `veo-3.1-generate-001` und nicht für Fast. Die Pricing-Seite nennt 4K auch für Fast. Das Params-Schema nennt nur 720p/1080p. Die How-to-Seiten schreiben „4k (Veo 3.1 Preview models only)“.
4. **Vertex-Lite und Bild-Input:** Das Datenblatt sagt „Image: Not supported“, die Fähigkeiten und How-to-Listen nennen I2V und First/Last für Lite.
5. **Vertex-Interaction-Retention:** 7 Tage (T2V-Seite, Interactions-Overview) gegenüber 14 Tagen (übrige Video-Seiten).
6. **Omni `background:true` auf der Gemini API:** Das Schema hat das Feld, für Omni ist es aber nicht explizit dokumentiert. Bekannter Bug: GET liefert Inline-base64 statt URI. Live verifizieren, bevor man darauf baut.
7. **Omni auf Vertex über `generateContent`:** laut Datenblatt „Supported“, ohne Request-Beispiel (unklar, ob `responseModalities` VIDEO o. Ä.). Nicht verwenden.
8. **Omni-Preview-Shutdown (Gemini API):** Changelog sagt 2026-09-30, Deprecation-Tabelle sagt 2026-10-22.
9. **Gemini-API-Bildformat für Veo:** Die Doku zeigt `inlineData{mimeType,data}`. Ob `bytesBase64Encoded` (Vertex-Stil) auch akzeptiert wird, ist nicht dokumentiert. Der Praxis-Guide verwendet es.
10. **Vertex-Veo-Inline-Output-Feldname** ohne `storageUri`: vermutlich `videos[].bytesBase64Encoded`, in der aktuellen Doku nicht gezeigt.
11. **Vertex-Veo-Extension-Output:** kombiniertes Video oder nur das 7-s-Segment? Nicht explizit. „Up to 37 seconds“ spricht für ein kombiniertes Video.
12. **Veo `mask` (insert/remove/remove_static/outpaint), `task: upscale`, `cameraControl`:** stehen im Schema, aber keine 3.1-Modellseite und kein How-to bestätigt sie. Es gibt keine eigenen Seiten (insert-objects, remove-objects, outpaint und upscale geben 404). Als **nicht unterstützt** behandeln.
13. **RAI-Felder in der Gemini API** (`generateVideoResponse.raiMediaFilteredCount/Reasons`): nicht auf ai.google.dev dokumentiert, nur im Vertex-Schema und laut Praxis.
14. **Gemini-API-Rate-Limits** für Veo und Omni stehen nur in AI Studio und nicht öffentlich in der Doku.
15. **Omni-Preise pro Auflösung (Gemini API):** Die Token-Raten pro Sekunde stehen nur auf der Vertex-Pricing-Seite. Dass die Gemini API dieselben Raten hat, ist angenommen.
16. **Omni-Input-Limits auf der Gemini API:** maximale Bildanzahl und Bildgröße sind nicht genannt (Vertex: 10 Bilder, 20/30 MB).
17. **Vertex-Omni-EU-Einschränkungen** für Edit und Extend hochgeladener Videos: nur für die Gemini API dokumentiert. Für Vertex unbekannt.
18. Ob `veo-3.1-*-001` nach dem 22.10. per Gemini-API-Key erreichbar ist: undokumentiert. Laufzeit-Check über `models.list` empfohlen.
