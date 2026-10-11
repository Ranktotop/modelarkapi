# Kling AI Developer API – Capability-Katalog (Video & video-nahe Audio-Funktionen)

Stand der Recherche: **2026-10-11**. Primärquelle: die offizielle Doku unter `https://kling.ai/document-api/…`.
`app.klingai.com/global/dev/document-api/...` leitet dorthin weiter. Fast jede Seite gibt es auch als
LLM-taugliches Markdown, wenn man `.md` an die URL hängt, z. B.
`https://kling.ai/document-api/api/video/3-0-omni/text-to-video.md`. Der vollständige Index liegt unter
`https://kling.ai/document-api/llms.txt`. Die „Legacy“-Seiten (`…/legacy`) gibt es nicht als Markdown.
Sie wurden im Browser gerendert und ausgelesen (Chrome DevTools).

Alles, was **nicht** aus der offiziellen Doku stammt, ist mit **[Drittquelle]** markiert.

---

## 0. TL;DR für die Proxy-Integration

* **Zwei API-Generationen laufen parallel:**
  * **Neue API** (seit 2026-06-17 bzw. 2026-07-15): Die Modellversion steckt im **Pfad**, z. B.
    `POST /text-to-video/kling-3.0`. Die Struktur ist `contents[]` + `settings` + `options`. Abgefragt wird
    einheitlich über `GET/POST /tasks`. Status-Enum: `submitted|processing|succeeded|failed`.
    **Nur API-Key-Auth.**
  * **Legacy API** (`/v1/videos/...`): Das Modell wird über den Body-Parameter `model_name` gewählt.
    Jeder Endpunkt hat eine eigene Abfrage `/v1/videos/<feature>/{id}`. Status-Enum:
    `submitted|processing|succeed|failed` (**`succeed` ohne „ed“!**). Funktioniert mit API-Key **und**
    mit AK/SK-JWT. Laut Changelog sind „keine Deprecation-Pläne“ angekündigt.
  * Alle Nicht-Generierungs-Features (Avatar, Lip Sync, TTS, Audio, Effects, Elements, Voices,
    Multi-Elements) gibt es **nur** im `/v1/...`-Schema, also im Legacy-Stil mit `task_status`/`succeed`.
    Sie verlangen aber kein `model_name` mehr.
* **Auth:** `Authorization: Bearer <API_KEY>`. Für Legacy-Endpunkte geht alternativ ein JWT (HS256,
  `iss=AK`, `exp`, `nbf`), signiert mit dem SK.
* **Base URL:** `https://api-singapore.klingai.com` (global). `https://api-beijing.klingai.com` ist der
  China-Endpoint. Der alte Endpoint `https://api.klingai.com` wurde ersetzt.
* **Kostenloser Credential-Check:** `GET /account/costs?start_time=<ms>&end_time=<ms>`. Die Doku nennt ihn
  ausdrücklich „free to call“. Maximal **1 QPS**.
* **Aktuelle Video-Modelle:** Kling 3.0 Turbo, Kling 3.0, Kling 3.0 Omni, Kling O1, Kling 2.6,
  Kling 2.5 Turbo. **v1.x, v2.0-master und v2.1(-master) stehen nicht mehr in der Doku.**
  Laut [Drittquelle] liefern `kling-v1-6`, `kling-v2-master` und `kling-v2-1-master` inzwischen
  `404 / code 1203 "model … has been discontinued"`.
* **Aus der Doku verschwunden** (früher vorhanden): Video Extension (`/v1/videos/video-extend`),
  Multi-Image-to-Video (`/v1/videos/multi-image2video`), `camera_control`, `static_mask`/`dynamic_masks`
  (Motion Brush), text-getriebener Lip Sync (`/v1/videos/lip-sync`) und das alte Elements-API. Siehe §12.
* **Ergebnis-URLs** werden nach **30 Tagen gelöscht**. Sie sind „hotlink protected“, also selbst
  herunterladen und speichern.

---

## 1. Quellenübersicht (alle offiziell, sofern nicht anders markiert)

| Thema | URL |
|---|---|
| Doku-Index | https://kling.ai/document-api/llms.txt |
| Quick Start | https://kling.ai/document-api/guides/get-started/quick-start |
| Capability Map Video | https://kling.ai/document-api/guides/capability-map/video (Stand 2026-05-19) |
| Authentication | https://kling.ai/document-api/api/get-started/authentication |
| Error Codes | https://kling.ai/document-api/api/get-started/error-codes |
| Concurrency | https://kling.ai/document-api/api/get-started/concurrency-rules |
| Callback / Webhook Signature | https://kling.ai/document-api/api/get-started/callbacks |
| Kling 3.0 Turbo T2V / I2V | https://kling.ai/document-api/api/video/3-0-turbo/text-to-video , …/image-to-video |
| Kling 3.0 & 3.0 Omni (T2V, I2V, Omni, Motion, Elements, Voice) | https://kling.ai/document-api/api/video/3-0-omni/{text-to-video,image-to-video,video-omni,motion-control,elements,voice-customization} |
| Kling O1 | https://kling.ai/document-api/api/video/o1/video-omni , …/o1/elements |
| Kling 2.6 | https://kling.ai/document-api/api/video/2-6/{text-to-video,image-to-video,motion-control,voice-customization} |
| Kling 2.5 Turbo | https://kling.ai/document-api/api/video/2-5-turbo/{text-to-video,image-to-video} |
| Motion Control 3.0 / 2.6 | https://kling.ai/document-api/api/video/motion-control , …/motion-control/2-6 |
| Legacy-Varianten | jeweils `<seite>/legacy`, z. B. https://kling.ai/document-api/api/video/3-0-omni/text-to-video/legacy |
| Multi-Elements | https://kling.ai/document-api/api/video/multi-elements |
| Avatar / TTS | https://kling.ai/document-api/api/video/avatar , …/avatar/text-to-speech |
| Lip Sync / Face Recognition | https://kling.ai/document-api/api/video/lip-sync , …/lip-sync/face-detection |
| Image Recognition | https://kling.ai/document-api/api/video/image-recognition |
| Audio (T2A / V2A) | https://kling.ai/document-api/api/video/audio-generation/{text-to-audio,video-to-audio} |
| Video Effects | https://kling.ai/document-api/api/effects/video-effects , Effects Center: https://kling.ai/document-api/api/effects/templates |
| Solutions | https://kling.ai/document-api/api/ecommerce-replication/{apparel,goods-studio,video-commerce,virtual-try-on} |
| Account Usage / Deduction | https://kling.ai/document-api/api/assets/account-usage , …/billing-deduction/{balance,package} |
| Pricing Video | https://kling.ai/document-api/pricing/base/video |
| Changelog | https://kling.ai/document-api/updates/api |

---

## 2. Authentifizierung, Domains, Konventionen

Quelle: https://kling.ai/document-api/api/get-started/authentication , https://kling.ai/document-api/guides/get-started/quick-start , https://kling.ai/llms.txt

* **Domain global:** `https://api-singapore.klingai.com`. Laut Doku für Server außerhalb Chinas gedacht.
  Der frühere Host `https://api.klingai.com` wurde ersetzt.
* **Domain China:** `https://api-beijing.klingai.com`. Steht nur in `kling.ai/llms.txt`, nicht in der API-Doku.
* **API Key** („for all models“): Er wird in der Console (`https://kling.ai/dev/api-key`) erzeugt und nur
  einmal angezeigt. Header: `Authorization: Bearer <API_KEY>`.
* **AK/SK-JWT**: Laut Doku *„API only applicable to legacy version design standards“*. Die
  Unterscheidung: „Modellversion im Pfad = neu; `model_name` im Body = legacy.“
  * Das JWT folgt RFC 7519. Header `{"alg":"HS256","typ":"JWT"}`, Payload
    `{"iss": AK, "exp": now+1800, "nbf": now-5}`, signiert mit dem SK. Gesendet wird es als
    `Authorization: Bearer <JWT>`.
  * Changelog 2026-06-17: „Kling 3.0 Turbo … The new API supports authentication via API Key only.“
* Requests verwenden `Content-Type: application/json`.
* **Bilder** werden fast überall als URL **oder** als rohes Base64 **ohne** `data:image/...;base64,`-Präfix
  akzeptiert. **Videos** werden in der Regel nur als URL akzeptiert.
* **`external_task_id`** ist eine eigene Task-ID. Sie muss pro Account eindeutig sein und kann zum Abfragen
  genutzt werden. In der neuen API heißt sie `options.external_task_id`, im Response `external_id`.
* **Wasserzeichen:** `watermark_info: {"enabled": bool}` (neu: `options.watermark_info`; in den
  Solutions-APIs `options.watermark`). Der Default ist `false`. Ist es aktiviert, liefert der Response
  zusätzlich `watermark_url`. Eigene Wasserzeichen werden nicht unterstützt.

---

## 3. Modellliste und Capability-Matrix

Quellen: Capability Map (https://kling.ai/document-api/guides/capability-map/video), die einzelnen API-Seiten, Legacy-Seiten, Changelog, Pricing.

### 3.1 Modell-Identifier

| Modell (Doku-Name) | Neue API: Pfad-Segment | Legacy: `model_name` | Status (Doku) |
|---|---|---|---|
| Kling 3.0 Turbo | `/text-to-video/kling-3.0-turbo`, `/image-to-video/kling-3.0-turbo` | – (gibt es nur in der neuen API) | GA seit 2026-06-17, „NEW“ |
| Kling 3.0 | `/text-to-video/kling-3.0`, `/image-to-video/kling-3.0`, `/motion-control/kling-3.0` | `kling-v3` | GA seit 2026-02-25 („HOT“) |
| Kling 3.0 Omni | `/omni-video/kling-3.0-omni` | `kling-v3-omni` (auf `/v1/videos/omni-video`) | GA seit 2026-02-25 |
| Kling O1 (Video O1) | `/omni-video/kling-o1` | `kling-video-o1` (Default auf `/v1/videos/omni-video`) | GA seit 2025-12 |
| Kling 2.6 | `/text-to-video/kling-2.6`, `/image-to-video/kling-2.6`, `/motion-control/kling-2.6` | `kling-v2-6` (auch Default von `/v1/videos/motion-control`) | GA seit 2025-12-15 |
| Kling 2.5 Turbo | `/text-to-video/kling-2.5-turbo`, `/image-to-video/kling-2.5-turbo` | `kling-v2-5-turbo` | GA seit 2025-10-20 |
| Kling 2.1 / 2.1 Master / 2.0 Master / 1.x | – | `kling-v2-1`, `kling-v2-1-master`, `kling-v2-master`, `kling-v1-6`, `kling-v1-5`, `kling-v1` | **Nicht mehr in den Legacy-Enums.** [Drittquelle] meldet `404/1203 "discontinued"` für v1-6, v2-master, v2-1-master (https://github.com/griptape-ai/griptape-nodes-library-standard/issues/695, Okt. 2026) |

Legacy-Enums laut den aktuellen Legacy-Seiten:
* `/v1/videos/text2video` und `/v1/videos/image2video`: `model_name` ∈ {`kling-v2-5-turbo`, `kling-v2-6`, `kling-v3`}, **Pflicht**.
* `/v1/videos/omni-video`: `model_name` ∈ {`kling-video-o1`, `kling-v3-omni`}, Default `kling-video-o1`.
* `/v1/videos/motion-control`: `model_name` ∈ {`kling-v2-6`, `kling-v3`}, Default `kling-v2-6`.

Hinweis: Auf der Elements-Seite steht „Video-customized elements are only supported for
**kling-video-o3** and later models“. Gemeint ist offenbar Kling 3.0 (Omni). `kling-video-o3` ist kein
dokumentierter `model_name`.

### 3.2 Matrix: Eckdaten (Capability Map)

| Modell | Input | Dauer | Auflösung | Seitenverhältnis (T2V / Omni) |
|---|---|---|---|---|
| Kling 3.0 Turbo | Text, Bild | 3–15 s (ganzzahlig) | 720p, 1080p | 16:9, 9:16, 1:1 |
| Kling 3.0 | Text, Bild, Video (nur Motion Control) | 3–15 s | 720p, 1080p, 4K | 16:9, 9:16, 1:1 |
| Kling 3.0 Omni | Text, Bild, Video | 3–15 s | 720p, 1080p, 4K (4K **nicht** mit Referenzvideo laut Changelog 2026-04-23; seit 2026-06-17 „4K generation is now supported“ auch für Ref.-Video, siehe §13) | 16:9, 9:16, 1:1 |
| Kling O1 | Text, Bild, Video | 3–10 s (bei reinem First-Frame nur 5/10) | 720p, 1080p | 16:9, 9:16, 1:1 |
| Kling 2.6 | Text, Bild, Video (nur Motion Control) | 5, 10 s | 720p, 1080p | 16:9, 9:16, 1:1 |
| Kling 2.5 Turbo | Text, Bild | 5, 10 s | 720p, 1080p | 16:9, 9:16, 1:1 |

Bei Image-to-Video (Turbo/3.0/2.6/2.5) gibt es **kein `aspect_ratio`**. Das Seitenverhältnis kommt vom Bild.

Legacy-Mapping: `mode` = `std` → 720p, `pro` → 1080p, `4k` → 4K. Die Deduction-API schreibt dazu:
„Legacy: mode parameter mapped as 720p=std, 1080p=pro“.

### 3.3 Matrix: Features pro Modell (Capability Map + API-Seiten)

| Feature | 3.0 Turbo | 3.0 | 3.0 Omni | O1 | 2.6 | 2.5 Turbo |
|---|---|---|---|---|---|---|
| T2V Single-Shot | ✔ | ✔ | ✔ (über omni-video, nur Prompt) | ✔ (Capability Map: nur 5/10 s) | ✔ (5/10 s; 720p nur stumm) | ✔ |
| Multi-Shot (bis 6 Shots) | ✔ (nur über Prompt-Syntax) | ✔ | ✔ | ✘ | ✘ | ✘ |
| Native Audio | Capability Map: ✔; **im API-Schema gibt es aber kein `audio`-Feld** (Pricing: „With Native Audio“) | ✔ `audio: native` | ✔ `native`/`original` | ✘ (nur `original` = Ton des Referenzvideos) | ✔ (nur 1080p) | ✘ |
| First-Frame I2V | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| First+Last-Frame | ✘ | ✔ | ✔ | ✔ (keine Elements, keine weiteren Ref.-Bilder) | ✔ (nur 1080p, stumm) | ✔ (nur 1080p) |
| Nur Last-Frame | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ |
| Elements | ✘ | ✔ (Video-Charakter + Multi-Image, max. 3) | ✔ | ✔ (nur Multi-Image-Elements) | ✘ | ✘ |
| Voice Control (eigene Stimme) | ✘ | Capability Map ✘ (Legacy-Doku erlaubt `voice_list` über Element-Voice-Binding, siehe §6) | ✘ (Stimme über Element mit gebundener Voice) | ✘ | ✔ (5/10 s, 1080p, max. 2 Voices) | ✘ |
| Motion Control | ✘ | ✔ (kein 4K) | ✘ | ✘ | ✔ | ✘ |
| Video-Referenz / Video-Edit | ✘ | ✘ | ✔ | ✔ | ✘ | ✘ |
| 4K | ✘ | ✔ | ✔ | ✘ | ✘ | ✘ |

Für alle Modelle laut Capability Map „Global Capabilities“: Avatar, Lip Sync, Multi-Element Video
Editing, Video-to-Audio und Text-to-Audio.

---

## 4. Neue API (Modell im Pfad)

Gemeinsamer Aufbau:

```json
{
  "prompt": "...",                         // nur T2V
  "contents": [ {"type": "...", ...} ],    // I2V / Omni / Motion
  "settings": { ... },
  "options": {
    "callback_url": "https://...",
    "external_task_id": "string",
    "watermark_info": {"enabled": false}
  }
}
```

Create-Response (alle neuen Endpunkte):

```json
{"code":0,"message":"string","request_id":"string",
 "data":{"id":"string","status":"submitted","create_time":1781080778802,"update_time":1781080794151,"external_id":"string"}}
```

### 4.1 Text-to-Video

| Pfad | `prompt` max. | `settings` |
|---|---|---|
| `POST /text-to-video/kling-3.0-turbo` | 3072 Zeichen (empfohlen ≤ 2500) | `resolution` ∈ {720p (Default), 1080p}; `aspect_ratio` ∈ {16:9 (Default), 9:16, 1:1}; `duration` int 3–15 (Default 5). **Kein `audio`, kein `multi_shot`.** Multi-Shot nur über die Prompt-Syntax. |
| `POST /text-to-video/kling-3.0` | 3072 (≤ 2500 empf.) | `multi_shot` bool (Default **true**); `audio` ∈ {native, off (Default)}; `resolution` ∈ {720p (Default), 1080p, 4k}; `aspect_ratio` wie oben; `duration` 3–15 (Default 5) |
| `POST /text-to-video/kling-2.6` | 2500 | `audio` ∈ {native, off}; `resolution` ∈ {720p, 1080p}; **native Audio nur mit 1080p**; `aspect_ratio`; `duration` ∈ {5, 10} |
| `POST /text-to-video/kling-2.5-turbo` | 2500 | `resolution` ∈ {720p, 1080p}; `aspect_ratio`; `duration` ∈ {5, 10} |

Multi-Shot-Prompt-Syntax (3.0 / Turbo / 3.0 Omni): `"shot n, m, words; shot n, m, words;"`.
Dabei ist n die Shot-Nummer (1–6), m die Dauer in Sekunden (≥ 1, die Summe muss `duration` ergeben) und
words der Shot-Prompt (max. 512 Zeichen). Bei `multi_shot=false` wird kein Multi-Shot erzeugt.

Quellen: https://kling.ai/document-api/api/video/3-0-turbo/text-to-video , https://kling.ai/document-api/api/video/3-0-omni/text-to-video , https://kling.ai/document-api/api/video/2-6/text-to-video , https://kling.ai/document-api/api/video/2-5-turbo/text-to-video

### 4.2 Image-to-Video

`contents[]`-Typen:

| Pfad | erlaubte `contents[].type` | `settings` |
|---|---|---|
| `POST /image-to-video/kling-3.0-turbo` | `prompt` (`text`), `first_frame` (`url`) | `resolution` 720p/1080p; `duration` 3–15. **Nur First Frame.** |
| `POST /image-to-video/kling-3.0` | `prompt`, `first_frame` (Pflicht), `last_frame` (optional), `element` (`element_id`, `id`; max. 3) | `multi_shot` (Default true), `audio` native/off, `resolution` 720p/1080p/4k, `duration` 3–15 |
| `POST /image-to-video/kling-2.6` | `prompt`, `first_frame`, `last_frame`, `voice` (`voice_id`, `id`; max. 2; nur wenn `audio`≠off) | `audio` native/off (native → nur 1080p), `resolution` 720p/1080p (First+Last → nur 1080p), `duration` 5/10 |
| `POST /image-to-video/kling-2.5-turbo` | `prompt`, `first_frame`, `last_frame` | `resolution` (First+Last → nur 1080p), `duration` 5/10 |

Bildregeln (alle I2V-Varianten der neuen API):
* Formate .jpg/.jpeg/.png, **≤ 50 MB**, Breite und Höhe ≥ 300 px, Seitenverhältnis 1:2.5 bis 2.5:1.
* Übergabe als URL oder Base64.
* „Last-frame only“ wird nicht unterstützt.

Prompt-Länge: 3.0/Turbo 3072 (≤ 2500 empf.), 2.6/2.5 2500.

Prompt-Referenzen in der neuen API: `@Name` für Element oder Voice. Element-Namen sollten keine
Teilstrings voneinander sein. Bei 2.6 werden Voices mit `@xxx` referenziert, z. B. `@sweet`.

Quellen: https://kling.ai/document-api/api/video/3-0-turbo/image-to-video , https://kling.ai/document-api/api/video/3-0-omni/image-to-video , https://kling.ai/document-api/api/video/2-6/image-to-video , https://kling.ai/document-api/api/video/2-5-turbo/image-to-video

### 4.3 Omni Video (Referenzen, Video-Edit)

`POST /omni-video/kling-3.0-omni` und `POST /omni-video/kling-o1`

`contents[].type` ∈ {`prompt`, `first_frame`, `last_frame`, `refer_image`, `feature_video`, `base_video`, `element`}.
Bilder und Videos haben `url` und optional `id` (Index für die Prompt-Referenz). `element` hat
`element_id` und `id` (Pflicht).

| | 3.0 Omni | O1 |
|---|---|---|
| Prompt | ≤ 3072 (≤ 2500 empf.), Multi-Shot-Syntax, `@image_1`/`@Zhang`/`@video_1` | ≤ 2500, `@…`-Referenzen, kein Multi-Shot |
| `settings.multi_shot` | bool, Default true | – |
| `settings.audio` | `native`, `original` (Ton des Ref.-Videos), `off` (Default) | `original`, `off` |
| `settings.resolution` | 720p, 1080p, 4k | 720p, 1080p |
| `settings.aspect_ratio` | 16:9/9:16/1:1; **Pflicht, wenn weder First Frame noch Ref.-Video vorhanden** | dito |
| `settings.duration` | 3–15 | 3–10; bei reinem First Frame ohne `refer_image`/Video nur 5 oder 10 |
| Bilder | jpg/jpeg/png, ≤ 50 MB, ≥ 300 px, 1:2.5–2.5:1 | dito |
| Ref.-Video | mp4/mov, ≤ 200 MB, **3–15.5 s**, Kantenlänge 700–4553 px, Fläche ≤ 8 294 400 px, Seitenverhältnis 0.4–2, 24–60 fps (Ausgabe 24 fps), **max. 1 Video, nur per URL** | mp4/mov, ≤ 200 MB, **3–10 s**, 700–2160 px, 24–60 fps, max. 1 |
| `feature_video` (Referenz) | Multi-Shot möglich (dann `multi_shot=true`), `audio` muss `off` sein | nur First Frame zusätzlich definierbar, kein Last Frame |
| `base_video` (zu editierendes Video) | kein First/Last Frame, kein Multi-Shot, kein `native` | kein First/Last Frame |
| Elements | Video-Charakter- und Multi-Image-Elements (Limits siehe unten) | **nur Multi-Image-Elements**; bei First+Last Frame keine Elements |

Mengen-Limits für 3.0 Omni (Bilder und Elements):
* Mit First Frame bzw. First+Last Frame: max. 3 Elements.
* Ohne Ref.-Video, nur Multi-Image-Elements: Ref.-Bilder + Elements ≤ 7.
* Ohne Ref.-Video, nur Video-Charakter-Elements: ≤ 3.
* Ohne Ref.-Video, beide Element-Typen gemischt: Video-Charakter-Elements ≤ 3 und Ref.-Bilder + Multi-Image-Elements ≤ 4.
* Mit Ref.-Video, nur Multi-Image-Elements: Ref.-Bilder + Elements ≤ 4.
* Mit Ref.-Video, nur Video-Charakter-Elements: ≤ 1.
* Mit Ref.-Video: Video-Charakter-Elements und Multi-Image-Elements bzw. Ref.-Bilder nicht gleichzeitig.

Für O1 gilt: ohne Ref.-Video ≤ 7, mit Ref.-Video ≤ 4.

Legacy-Hinweis zum Video-Edit (`refer_type: base`): Die Ausgabedauer entspricht der Länge des
Eingangsvideos, `duration` wird ignoriert. Abgerechnet wird nach der gerundeten Input-Dauer.

Quellen: https://kling.ai/document-api/api/video/3-0-omni/video-omni , https://kling.ai/document-api/api/video/o1/video-omni

### 4.4 Motion Control

`POST /motion-control/kling-3.0` und `POST /motion-control/kling-2.6`

* `contents[].type` ∈ {`prompt` (≤ 2500 Zeichen), `image` (Aussehen; URL/Base64), `video` (Bewegung; URL), `element` (**nur 3.0**, max. 1)}.
* `settings.character_orientation` ist **Pflicht** und ∈ {`image`, `video`}:
  * `image`: Das Referenzvideo darf ≤ 10 s lang sein.
  * `video`: Das Referenzvideo darf ≤ 30 s lang sein.
  * Mit Element gilt immer die Orientierung aus dem Video.
* `settings.audio` ∈ {`original` (Default), `off`}.
* `settings.resolution` ∈ {720p (Default), 1080p}. Laut Capability Map kein 4K.
* **Keine `duration`.** Die Ausgabe folgt der Länge des Referenzvideos und kann kürzer werden, wenn sich
  weniger als die volle Bewegung extrahieren lässt (mindestens 3 s). Abgerechnet wird nach Output-Dauer.
* Bild: jpg/jpeg/png, ≤ 50 MB (neu; Legacy: ≤ 10 MB), ≥ 300 px, 1:2.5–2.5:1.
* Video: mp4/mov, ≤ 100 MB, 340–3850 px, 3 s bis 10 bzw. 30 s.

Quellen: https://kling.ai/document-api/api/video/motion-control , https://kling.ai/document-api/api/video/motion-control/2-6

### 4.5 Task-Abfrage (neue API, gilt für alle neuen Video-Endpunkte)

* **`GET /tasks?task_ids=a,b,c`** oder **`?external_task_ids=…`**. Die beiden Parameter schließen sich
  gegenseitig aus. Batch per Komma; ein Limit ist nicht dokumentiert. Bei `/solutions` sind es max. 20.
* **`POST /tasks`** (Cursor-Liste): Body `start_time`/`end_time` (ms; Default: end−30 Tage bzw. jetzt),
  `cursor` (`next_cursor`; überschreibt die Zeitangaben), `limit` (Default 100, max. 500) und
  `filters: [{key:"status",values:[…]},{key:"product_type",values:["video"|"image"|"try_on"]}]`.
  Response: `data.result[]`, `count`, `next_cursor`, `has_more`.
* Laut Doku werden „nur async tasks“ abgefragt.

Antwortobjekt pro Task (auch der Callback-Body der neuen API):

```json
{
  "id":"893605946402811985", "status":"submitted|processing|succeeded|failed",
  "message":"Fehlergrund", "create_time":ms, "update_time":ms, "external_id":"…",
  "outputs":[
    {"type":"video","id":"…","url":"…","watermark_url":"…","duration":"5.04"},
    {"type":"image","url":"…","watermark_url":"…","group_id":"…"},
    {"type":"audio","id":"…","mp3_url":"…","wav_url":"…","mp3_duration":"…","wav_duration":"…"},
    {"type":"voice","id":"…","name":"…","url":"…","owned_by":"kling|<creatorId>","status":"succeeded|deleted"},
    {"type":"element","id":"…","name":"…","description":"…","element_type":"video_character_elements|multi_image_elements",
     "references":[{"type":"image","role":"frontal|reference","url":"…"},{"type":"video","role":"refer","url":"…"},
                   {"type":"voice","role":"refer","url":"…","id":"…","name":"…","owned_by":"…"}],
     "owned_by":"…","status":"succeeded|deleted","tags":[{"id":1,"name":"…","description":"…"}]}
  ],
  "billing":[{"charge_type":"cash|unit","cash_type":"balance|test_balance","amount":"…","currency":"CNY|USD",
              "package_type":"video|image|audio","list_price":"…"}]
}
```

Quellen: Abschnitte „Query Task“ auf allen neuen Seiten, z. B. https://kling.ai/document-api/api/video/3-0-omni/text-to-video

---

## 5. Legacy API – Video-Generierung (`/v1/videos/...`, `model_name`)

Allgemein:
* Create-Response:
  `data: {task_id, task_info:{external_task_id}, task_status, created_at, updated_at}`
* Einzelabfrage `GET /v1/videos/<feature>/{task_id}`. Laut Doku auch per `external_task_id` im Pfad
  möglich (beides wird als „Path Parameter“ beschrieben).
* Listenabfrage `GET /v1/videos/<feature>?pageNum=1..1000&pageSize=1..500` (Default 1/30).
* Ergebnis:
  `data.task_result.videos[] = {id, url, watermark_url, duration}`, dazu `task_status_msg`,
  `watermark_info`, `final_unit_deduction` und `final_balance_deduction{quota,list_price}`.
* **Status `succeed`**, nicht `succeeded`.

Quellen: die Legacy-Seiten, z. B. https://kling.ai/document-api/api/video/3-0-omni/text-to-video/legacy

### 5.1 `POST /v1/videos/text2video`

| Feld | Typ | Pflicht | Werte / Default / Limits |
|---|---|---|---|
| `model_name` | string | ja | `kling-v2-5-turbo`, `kling-v2-6`, `kling-v3` (ein altes Feld `model` wird toleriert; leer bedeutet laut Doku „V1“ und ist faktisch veraltet) |
| `multi_shot` | bool | nein | Default false. Bei true: `prompt` ungültig und kein First/End Frame |
| `shot_type` | string | bei `multi_shot` | `customize`, `intelligence` |
| `prompt` | string | bedingt | ≤ 2500. Pflicht bei `multi_shot=false` oder `shot_type=intelligence`. `<<<voice_1>>>` für Voices (max. 2, `sound` muss `on` sein) |
| `multi_prompt` | array | bei customize | `[{index:int, prompt:str(≤512), duration:"n"}]`, 1–6 Shots, Summe = `duration` |
| `negative_prompt` | string | nein | ≤ 2500 |
| `sound` | string | nein | `on`/`off` (Default off) |
| `mode` | string | nein | `std` (720p, Default), `pro` (1080p), `4k` |
| `aspect_ratio` | string | nein | 16:9 (Default), 9:16, 1:1 |
| `duration` | **string** | nein | "3"…"15" (Default "5"); 2.6/2.5 nur "5"/"10" |
| `watermark_info`, `callback_url`, `external_task_id` | | nein | |

### 5.2 `POST /v1/videos/image2video`

Wie text2video, aber:
* `image`: URL oder Base64 ohne Präfix, jpg/jpeg/png, **≤ 10 MB**, ≥ 300 px, 1:2.5–2.5:1.
* `image_tail` (End Frame).
  * Die Legacy-Doku sagt „mindestens eines von `image`/`image_tail`“.
  * Die Capability Map sagt dagegen „End Frame Only: Not supported“ für alle aktuellen Modelle.
* `element_list: [{element_id: long}]`, max. 3.
* `voice_list: [{voice_id}]`, max. 2. **Schließt sich mit `element_list` gegenseitig aus.** Die
  `voice_id` stammt aus dem Custom-Voice-API, *nicht* aus dem Lip-Sync-API.
* Kein `aspect_ratio`.
* `multi_shot`/`shot_type`/`multi_prompt` wie in §5.1.
* Seit 2026-05-07 ist Multi-Shot zusammen mit First/Last Frame für `kling-v3`/`kling-v3-omni` erlaubt.
* `camera_control`, `static_mask`, `dynamic_masks` und `cfg_scale` stehen **nicht mehr** im Schema (siehe §12).

### 5.3 `POST /v1/videos/omni-video`

| Feld | Werte / Hinweise |
|---|---|
| `model_name` | `kling-video-o1` (Default), `kling-v3-omni` |
| `multi_shot`, `shot_type`, `multi_prompt` | wie in §5.1 |
| `prompt` | ≤ 2500. Referenzen mit `<<<image_1>>>`, `<<<element_1>>>`, `<<<video_1>>>` |
| `image_list` | `[{image_url, type?: "first_frame"|"end_frame"}]`. **Kein `type` setzen, wenn das Bild kein Start- oder End-Frame ist.** Bild ≤ 10 MB. Bei O1 sind Start/End Frame nicht möglich, wenn mehr als zwei Bilder übergeben werden |
| `element_list` | `[{element_id}]`. Limits wie in §4.3 |
| `video_list` | `[{video_url, refer_type: "base"(Default)|"feature", keep_original_sound: "yes"|"no"}]`. Max. 1 Video, ≤ 200 MB, 3–15.5 s (Obergrenze modellabhängig), 700–4553 px |
| `sound` | `on`/`off`. **Mit Ref.-Video nur `off`** |
| `mode` | `std`, **`pro` (Default bei Omni!)**, `4k` |
| `aspect_ratio` | Pflicht ohne First Frame und ohne Video-Edit |
| `duration` | "3"–"15". Bei `refer_type=base` ignoriert, dann gilt die Input-Länge |

### 5.4 `POST /v1/videos/motion-control`

* `model_name` ∈ {`kling-v2-6` (Default), `kling-v3`}.
* `prompt` ≤ 2500.
* `image_url` (Pflicht; URL oder Base64, ≤ 10 MB, 300–65536 px).
* `video_url` (Pflicht; mp4/mov, ≤ 100 MB, 340–3850 px, 3–30 s).
* `element_list` (max. 1).
* `keep_original_sound` yes (Default) / no.
* `character_orientation` (Pflicht) ∈ {image, video}.
* **`mode` (Pflicht)** ∈ {std, pro}.
* `watermark_info`, `callback_url`, `external_task_id`.
* Abfrage über `GET /v1/videos/motion-control/{id}` bzw. die Liste.

Quelle: https://kling.ai/document-api/api/video/3-0-omni/motion-control/legacy

---

## 6. Elements (Subjekt-/Charakter-Bibliothek) – „Advanced Elements“

Quelle: https://kling.ai/document-api/api/video/3-0-omni/elements (identisch zu o1/elements und image/…/elements)

| Methode | Pfad | Zweck |
|---|---|---|
| POST | `/v1/general/advanced-custom-elements` | Element erstellen (async) |
| GET | `/v1/general/advanced-custom-elements/{task_id}` | Einzelabfrage |
| GET | `/v1/general/advanced-custom-elements?pageNum&pageSize` | Liste eigener Elements (pageNum 1–1000, pageSize 1–500, Default 30) |
| GET | `/v1/general/advanced-presets-elements?pageNum&pageSize` | Offizielle Preset-Elements |
| POST | `/v1/general/delete-advanced-elements` | Löschen, Body `{element_id}`. **Die Image-Element-Seiten nennen stattdessen `/v1/general/delete-elements`** (Widerspruch, siehe §14) |

Create-Body:
* `element_name` (≤ 20 Zeichen, Pflicht) und `element_description` (≤ 100, Pflicht).
* `reference_type` ∈ {`video_refer`, `image_refer`} (Pflicht).
* `element_image_list: {frontal_image, refer_images:[{image_url}]}`.
  * Ein Frontalbild plus 1–3 weitere Bilder.
  * jpg/jpeg/png, ≤ 10 MB, ≥ 300 px, 1:2.5–2.5:1, URL oder Base64.
* `element_video_list: {refer_videos:[{video_url}]}`.
  * mp4/mov, 3–8 s, 1080p, 16:9 oder 9:16, max. 1 Video, ≤ 200 MB.
  * Nur realistische, humanoide Figuren.
  * Enthält das Video Sprache, wird automatisch eine Voice erstellt und gebunden.
* `element_voice_id` (string): bindet eine Voice. Bei Multi-Image-Elements nur für Figuren bzw. Humanoide.
* `tag_list: [{tag_id}]` mit o_101 Hottest, o_102 Character, o_103 Animal, o_104 Item, o_105 Costume,
  o_106 Scene, o_107 Effect, o_108 Others.
* `callback_url`, `external_task_id`.

Ergebnis:

```
task_result.elements[] = {element_id, element_name, element_description, reference_type,
                          element_image_list, element_video_list,
                          element_voice_info{voice_id, voice_name, trial_url, owned_by},
                          tag_list, owned_by, status: "succeed"|"deleted"}
```

Weitere Punkte:
* Das alte Elements-API (vor 2026-02-25) ist eine **separate Bibliothek**. Abfragen über beide APIs
  hinweg sind nicht möglich. Die alte Doku ist nur noch über https://ksurl.cn/QYFWJef0 verlinkt und wurde
  nicht geprüft.
* Zusatz-Endpunkt **AI Multi-Shot**: `POST /v1/general/ai-multi-shot`, Body `element_frontal_image`. Er
  erzeugt weitere Ansichten eines Elements, 3 Sets pro Aufruf, 0.5 Units.
  Quelle: https://kling.ai/document-api/api/image/common/subject-completion

---

## 7. Voices (Custom und Preset)

Quelle: https://kling.ai/document-api/api/video/3-0-omni/voice-customization (identisch für 2.6)

| Methode | Pfad | Hinweise |
|---|---|---|
| POST | `/v1/general/custom-voices` | `voice_name` (≤ 20, Pflicht), `voice_url` (mp3/wav/mp4/mov, eine saubere Stimme, 5–30 s) **oder** `video_id` (Video aus Kling 2.6 mit Sound, aus dem Avatar-API oder aus dem Lip-Sync-API), `callback_url`, `external_task_id`. 0.05 Units |
| GET | `/v1/general/custom-voices/{task_id}` | `task_result.voices[] = {voice_id, voice_name, trial_url, owned_by}` |
| GET | `/v1/general/custom-voices?pageNum&pageSize` | pageSize 1–1000 |
| GET | `/v1/general/presets-voices?pageNum&pageSize` | offizielle Voices (`owned_by: "kling"`) |
| POST | `/v1/general/delete-voices` | `{voice_id}`, nur Custom Voices |

Diese `voice_id`s werden verwendet in 2.6 I2V (`contents[].type=voice` bzw. legacy `voice_list`), in der
Element-Voice-Bindung und in Video Commerce. Die **TTS- und Lip-Sync-Voice-IDs** (z. B. `oversea_male1`)
sind ein anderer Namensraum.

---

## 8. Avatar, TTS, Lip Sync, Audio, Effects, Multi-Elements (nur `/v1`, ohne `model_name`)

Alle haben das Legacy-Antwortformat (`task_id`/`task_status` mit `succeed`), Einzel- und
Listenabfrage, `callback_url` und `external_task_id`.

### 8.1 Avatar (Digital Human: Bild + Audio)

`POST /v1/videos/avatar/image2video`; Abfrage über `GET …/image2video/{id}` und `GET …/image2video?pageNum&pageSize`.

* `image` (Pflicht): URL oder Base64, jpg/jpeg/png, ≤ 10 MB, ≥ 300 px, 1:2.5–2.5:1.
* Genau eines von `audio_id` (aus TTS, ≤ 30 Tage alt, 2–300 s) **oder** `sound_file`
  (URL oder Base64; mp3/wav/m4a/aac, ≤ 5 MB, 2–300 s).
* `prompt` (≤ 2500): Aktionen, Emotion, Kamera.
* `mode` ∈ {std (Default), pro}.
* `watermark_info`.
* Ergebnis: `task_result.videos[{id,url,watermark_url,duration}]`.
* Preis: 0.4 Units/s (720p, std) bzw. 0.8 Units/s (1080p, pro). Bis 5 min Länge (Changelog 2025-12-04).

Quelle: https://kling.ai/document-api/api/video/avatar

### 8.2 TTS

`POST /v1/audio/tts` ist **synchron**: Das Ergebnis kommt direkt im Response, und es ist kein Query-Endpunkt dokumentiert.

* `text` ≤ 1000 Zeichen (Pflicht).
* `voice_id` (Pflicht).
* `voice_language` ∈ {zh (Default), en} (Pflicht).
* `voice_speed` 0.8–2.0 (Default 1.0, eine Nachkommastelle).
* Response: `task_result.audios[{id, url, duration}]`. Die `id` wird als `audio_id` für Avatar und Lip Sync
  verwendet und ist 30 Tage gültig.
* Die Voice-Liste liegt in einem externen Dokument:
  https://docs.qingque.cn/s/home/eZQDvafJ4vXQkP8T9ZPvmye8S?identityId=2E1MlYrrPk4. Beispiel: `oversea_male1`.
  Eine [Drittquelle]-Liste (ComfyUI) steht in §12.4.
* 0.05 Units/Aufruf.

Quelle: https://kling.ai/document-api/api/video/avatar/text-to-speech

### 8.3 Lip Sync (zweistufig, audio-getrieben)

1. **Face Identification:** `POST /v1/videos/identify-face`.
   * Body: `video_id` (Kling-Video, ≤ 30 Tage, ≤ 60 s) **oder** `video_url` (mp4/mov, ≤ 100 MB, 2–60 s,
     720p/1080p, Kanten 512–2160 px).
   * Antwort synchron:
     `data.session_id` und `face_data[{face_id, face_image, start_time(ms), end_time(ms)}]`.
   * **Kostenpflichtig: 0.05 Units.**
2. **Create:** `POST /v1/videos/advanced-lip-sync`.
   * `session_id` (Pflicht).
   * `face_choose[]` (Pflicht; **aktuell nur 1 Person**) mit:
     * `face_id`
     * genau eines von `audio_id` (TTS, 2–60 s) **oder** `sound_file` (URL/Base64, mp3/wav/m4a/aac, ≤ 5 MB, 2–60 s)
     * `sound_start_time`, `sound_end_time`, `sound_insert_time` (ms, Pflicht; der Ausschnitt muss ≥ 2 s
       sein und sich ≥ 2 s mit dem Gesichtsintervall überlappen)
     * `sound_volume` 0–2 (Default 1), `original_audio_volume` 0–2 (Default 1)
   * Außerdem `watermark_info`, `callback_url`, `external_task_id`.
   * Abfrage: `GET /v1/videos/advanced-lip-sync/{id}` und die Liste. Ergebnis:
     `task_info.parent_video{id,url,duration}`, `task_result.videos[]`.
   * Preis: 0.5 Units pro 5 s.
* **Text-getriebener Lip Sync** (Text → TTS → Lippen) ist im aktuellen API **nicht als Modus dokumentiert**.
  Workaround: erst `/v1/audio/tts` aufrufen, dann `audio_id` übergeben. Zum alten
  `/v1/videos/lip-sync` mit `mode: text2video|audio2video` siehe §12.

Quellen: https://kling.ai/document-api/api/video/lip-sync , https://kling.ai/document-api/api/video/lip-sync/face-detection

### 8.4 Image Recognition (Hilfsfunktion)

`POST /v1/videos/image-recognize` ist synchron.

* Body: `image` (URL/Base64, ≤ 10 MB).
* Ergebnis: `task_result.images[{type: object_seg|head_seg|face_seg|cloth_seg, is_contain, url}]`.
* 0.1 Units. Gedacht für Multi-Image-to-Video und Multi-Elements.

Quelle: https://kling.ai/document-api/api/video/image-recognition

### 8.5 Text-to-Audio (SFX/Musik aus Text)

`POST /v1/audio/text-to-audio`

* `prompt` ≤ 200 (Pflicht).
* `duration` float 3.0–10.0, eine Nachkommastelle (Pflicht).
* `external_task_id`, `callback_url`.
* Abfrage: `GET /v1/audio/text-to-audio/{id}` und die Liste. Ergebnis:
  `task_result.audios[{id, url_mp3, url_wav, duration_mp3, duration_wav}]`.
* 0.25 Units/Aufruf.

Quelle: https://kling.ai/document-api/api/video/audio-generation/text-to-audio

### 8.6 Video-to-Audio (Sound-Design für ein Video)

`POST /v1/audio/video-to-audio`

* Genau eines von `video_id` (Kling-Video, ≤ 30 Tage, 3–20 s) **oder** `video_url` (mp4/mov, ≤ 100 MB, 3–20 s).
* `sound_effect_prompt` ≤ 200, `bgm_prompt` ≤ 200, `asmr_mode` bool (Default false).
* Ergebnis: `task_result.videos[{id,url,duration}]` (das Video mit Ton) **und** `audios[{id,url_mp3,url_wav,…}]`.
* 0.25 Units/Aufruf.

Quelle: https://kling.ai/document-api/api/video/audio-generation/video-to-audio

### 8.7 Multi-Element Video Editing (Elemente hinzufügen, tauschen, entfernen)

Session-Workflow (Session 24 h gültig):

| Schritt | Endpunkt | Body / Ergebnis |
|---|---|---|
| Init | `POST /v1/videos/multi-elements/init-selection` | `video_id` (≤ 30 Tage) **oder** `video_url` (mp4/mov, **2–5 s oder 7–10 s**, 720–2160 px, 24/30/60 fps). Liefert `session_id, fps, original_duration, width, height, total_frame, normalized_video` |
| Auswahl hinzufügen | `POST …/add-selection` | `session_id, frame_index, points[{x,y∈[0,1]}]`. Max. 10 Frames, max. 10 Punkte pro Frame, ein Frame pro Aufruf. Liefert RLE- und PNG-Masken |
| Auswahl löschen | `POST …/delete-selection` | dieselben Koordinaten wie beim Hinzufügen |
| Auswahl leeren | `POST …/clear-selection` | `session_id` |
| Vorschau | `POST …/preview-selection` | liefert `video, video_cover, tracking_output` |
| Create | `POST /v1/videos/multi-elements` | `session_id`, `edit_mode` ∈ {addition, swap, removal}, `image_list[{image}]` (addition: 1–2 Bilder, swap: 1, removal: keins; Bilder vorab zuschneiden, ≤ 10 MB), `prompt` ≤ 2500 mit `<<<video_1>>>`/`<<<image_1>>>`, `negative_prompt`, `mode` std/pro, `duration` "5"/"10" (5 nur bei 2–5-s-Input, 10 nur bei 7–10 s), `watermark_info` |
| Abfrage | `GET /v1/videos/multi-elements/{id}` und Liste | |

Die Selection-Endpunkte geben `final_balance_deduction` zurück; ob sie Geld kosten, ist unklar.

Quelle: https://kling.ai/document-api/api/video/multi-elements

### 8.8 Video Effects (Templates)

`POST /v1/videos/effects`

* `effect_scene` (Pflicht): 219 Werte, davon 204 Single-Image- und 15 Dual-Image-Effekte. Die Liste ist im
  Anhang.
* `input.image` (Single) oder `input.images` (genau 2 Bilder, links/rechts; für Dual-Effekte wie
  `hug_pro`, `kiss_pro`). Jeweils ≤ 10 MB, ≥ 300 px, 1:2.5–2.5:1.
* `callback_url`, `external_task_id`.
* Kein `model_name`, `duration` oder `mode` mehr in der aktuellen Doku.
* Abfrage: `GET /v1/videos/effects/{id}` und Liste (pageNum/pageSize). Ergebnis:
  `task_result.videos[{id,url,watermark_url}]`.
* Der Preis hängt vom Template ab (Effects-Preisliste).
* Effekte werden regelmäßig eingestellt, z. B. `magic_match_tree` am 2026-07-03 sowie
  `kiss`, `hug`, `fight` (ohne `_pro`) am 2026-01-30.

Quellen: https://kling.ai/document-api/api/effects/video-effects , https://kling.ai/document-api/api/effects/templates

### 8.9 Solution-APIs (Video, neue Struktur)

Sie verwenden `contents`/`settings`/`options`, die Abfrage läuft über `GET /solutions?task_ids=…`
(max. 20) und `POST /solutions` (Cursor). Status-Enum `succeeded`.

| Endpunkt | Kurzbeschreibung |
|---|---|
| `POST /solutions/e-commerce/clothing_dupe` (AI Apparel Replicator) | `contents[].type` ∈ product_info, source_video, product_image, model_image, bgm, voice; `resolution` 720p/1080p; `aspect_ratio` 9:16…21:9 |
| `POST /solutions/e-commerce/goods_studio` | `ref_image`, `goods_title`, `goods_description`; `duration` 15/30/60; aspect 9:16/1:1/16:9 |
| `POST /solutions/talking_agent` (Video Commerce) | `avatar_image`/`avatar_id`, `ref_image`, `goods_*`, `speech_script`; `voice_id`, `speech_rate` 0.8/1.0/1.2, `bgm_enabled` … |
| `POST /solutions/virtual_try_on` | Bild-Output (nicht Video); `product_image` + `person_image` (URL; JPG/PNG/WebP, ≤ 2048 px, ≤ 10 MB); `keep_face`/`keep_pose`/`keep_background` |

Quellen: https://kling.ai/document-api/api/ecommerce-replication/{apparel,goods-studio,video-commerce,virtual-try-on}

---

## 9. Account / Balance – kostenloser Credential-Check

### `GET /account/costs` ← **empfohlener Validierungs-Call**

* Die Doku sagt: „This API is **free to call** … Please note to control the request rate (**QPS<=1**)“.
* Query-Parameter: `start_time` (int ms, **Pflicht**), `end_time` (int ms, **Pflicht**),
  `resource_pack_name` (optional).
* Auth: `Authorization: Bearer <API_KEY>` (laut Doku).
* Response:

```json
{"code":0,"message":"string","request_id":"string",
 "data":{"code":0,"msg":"string",
   "resource_pack_subscribe_infos":[{"resource_pack_name":"…","resource_pack_id":"…",
     "resource_pack_type":"decreasing_total|constant_period","total_quantity":200.0,
     "remaining_quantity":118.0,  // bis zu 12 h verzögert!
     "purchase_time":ms,"effective_time":ms,"invalid_time":ms,
     "status":"toBeOnline|online|expired|runOut"}]}}
```

* Validierungslogik: `HTTP 200 && code==0` heißt, die Credentials sind gültig.
  * `401` mit 1000–1004: Auth-Fehler.
  * `403/1103`: keine Berechtigung.
  * Aktive Pakete erkennt man an `status=="online"`.
  * Der **Balance-Teil** (Pay-as-you-go-Guthaben) taucht hier nicht auf, nur Ressourcenpakete.

Quelle: https://kling.ai/document-api/api/assets/account-usage

### Deduction-Details (nicht als kostenlos ausgewiesen; nicht als Ping verwenden)

* `POST /account/billing/balance`: Body `start_time`/`end_time` (ms; Pflicht ohne Cursor), `limit`
  (≤ 500), `filters[{key:"api_key_name",values}]`, `cursor`. Liefert `detail[]` mit `task_id`,
  `api_key_name`, `product_function`, `model_name`, `resolution`, `duration`, `refer_video_input`,
  `video_sound`, `voice_control`, `balance_before/after`, `deduction_amount`, `list_price`, `currency`.
* `POST /account/billing/package`: entsprechend für Unit-Abzüge aus Ressourcenpaketen.

Quellen: https://kling.ai/document-api/api/assets/billing-deduction/balance , …/package

Alternative read-only Checks (Preis nicht ausgewiesen, nicht verifiziert): `GET /v1/general/presets-voices`
und `GET /v1/general/advanced-presets-elements`.

---

## 10. Callbacks und Webhook-Signatur

Quelle: https://kling.ai/document-api/api/get-started/callbacks

* Wird `callback_url` gesetzt, schickt der Server bei **jedem Statuswechsel** einen POST
  (`submitted` → `processing` → `succeeded`/`failed`). Der Callback **dupliziert** also mehrfach pro Task.
* **Neuer Callback** (neue API): Body wie das Task-Objekt in §4.5 (`id`, `status`, `outputs[]`, `billing[]`).
  Bei Elements heißt das Feld im Callback `materials`, in der Query `references` (Doku-Inkonsistenz).
* **Legacy-Callback** (alle `/v1`-Endpunkte; laut Doku „Kling 3.0 Omni and earlier models“):

```json
{"task_id","task_status":"submitted|processing|succeed|failed","task_status_msg",
 "created_at","updated_at","final_unit_deduction","final_balance_deduction":{"quota","list_price"},
 "task_info":{"parent_video":{"id","url","duration"},"external_task_id"},
 "task_result":{"images":[{"index","url"}],"videos":[{"id","url","duration"}]}}
```

* **Webhook Signature** (seit 2026-08-07, optional) folgt dem *Standard Webhooks*-Schema:
  * Header `webhook-id`, `webhook-timestamp` (Sekunden), `webhook-signature: v1,<base64> [v1,<base64> …]`.
  * Signiert wird `{id}.{timestamp}.{rawBody}` mit HMAC-SHA256. Der Key ist Base64-dekodiert, nach dem
    Entfernen des Präfixes `whsec_`.
  * Zeitfenster ±5 min. Der Vergleich muss in konstanter Zeit erfolgen.
  * In Python geht das mit `pip install standardwebhooks`.
  * Beim Rotieren gilt eine Übergangsfrist von 7 Tagen, in der mehrere Signaturen geschickt werden.
  * Ein Test-Callback aus der Console ist höchstens alle 6 s möglich (Body: `status:"submitted"`, `outputs:[]`).
  * Header werden nur gesendet, wenn ein Webhook-Secret existiert.
  * Der Callback-Endpunkt muss HTTPS sein, wenn die Signatur genutzt wird.
* Retry-Verhalten, Timeouts und Absender-IPs des Callbacks sind **nicht dokumentiert**.

---

## 11. Fehlercodes, Concurrency, Rate Limits, Ergebnis-URLs

### 11.1 Fehlercodes

Quelle: https://kling.ai/document-api/api/get-started/error-codes

| HTTP | code | Bedeutung |
|---|---|---|
| 200 | 0 | OK |
| 401 | 1000 / 1001 / 1002 / 1003 / 1004 | Auth fehlgeschlagen / leer / ungültig / noch nicht gültig (nbf) / abgelaufen (exp) |
| 429 | 1100 | Account-Status anormal |
| 429 | 1101 | Zahlungsrückstand (Postpaid) |
| 429 | 1102 | Ressourcenpaket leer oder abgelaufen (Prepaid) |
| 403 | 1103 | Kein Zugriff auf Ressource/Modell |
| 400 | 1200 / 1201 | ungültige Parameter (Details in `message`) |
| 404 | 1202 | ungültige Methode |
| 404 | 1203 | Ressource existiert nicht, z. B. das Modell. [Drittquelle]: auch für „model … has been discontinued“ |
| 400 | 1300 | Plattform-Policy |
| 400 | 1301 | Content-Security getriggert |
| 429 | 1302 | Rate-Limit |
| 429 | 1303 | Concurrency/QPS über dem Paket-Limit (`"parallel task over resource pack limit"`) |
| 429 | 1304 | IP-Whitelist-Policy |
| 500 / 503 / 504 | 5000 / 5001 / 5002 | intern / Wartung / Timeout (Backlog) |

Wichtig: **429 hat drei verschiedene Ursachen** (Billing 110x, Rate-Limit 1302, Concurrency 1303). Nur
1302 und 1303 sollten mit Backoff wiederholt werden, nicht 1101 und 1102.

### 11.2 Concurrency

Quelle: https://kling.ai/document-api/api/get-started/concurrency-rules

* Das Limit wird pro **Account × Modellversion × Pakettyp (video/image)** berechnet und von allen
  API-Keys eines Accounts geteilt.
* Ein Task belegt ab `submitted` bis zum Ende einen Slot, auch wenn er fehlschlägt.
* Pro Video- oder Try-On-Task ist es 1 Slot, pro Bild-Task entspricht es `n`.
* Gilt mehr als ein Paket, zählt das Paket mit dem höchsten Concurrency-Wert.
* Query-Endpunkte belegen keine Concurrency.
* „The system does not impose any QPS limits“, mit Ausnahme von `/account/costs` (≤ 1 QPS) und dem
  Test-Callback.
* Bei Überschreitung kommt `1303`. Empfohlen ist exponentieller Backoff (≥ 1 s).

### 11.3 Ergebnis-URLs

* Alle Ergebnisse werden **nach 30 Tagen gelöscht** (Changelog 2025-09-29 und in allen Response-Kommentaren).
* Die URLs sind „hotlink protection / anti-leech format“.
* Die `duration` ist ein String in Sekunden, z. B. `"5.04"`.
* Beispiel-Hosts aus der Doku: `p1-kling.klingai.com`, `p2-kling.klingai.com`, `v1-kling.klingai.com`,
  `v4-kling.kechuangai.com`, `p1.a.kwimgs.com`, `h1.inkwai.com`, `s15-kling.klingai.com`. Der
  tatsächliche Host der Ergebnis-Videos ist nicht verbindlich spezifiziert.
* Typische Laufzeiten: Video 1–5 min, Element 30 s bis 2 min (Kling Skills).
  Quelle: https://kling.ai/document-api/api/get-started/kling-skills

---

## 12. Historische / nicht mehr dokumentierte Funktionen

Die aktuelle offizielle Doku enthält **keine** Seiten mehr zu den folgenden Punkten. Alte Deep-Links wie
`/document-api/apiReference/model/videoExtension` oder `…/multiImageToVideo` leiten auf
`/guides/get-started/overview` um. Die Angaben unten stammen aus dem offiziellen Changelog (historische
Einträge) oder aus [Drittquellen]. Für die Integration gelten sie als **nicht verfügbar bzw. nicht
verifiziert**.

| Funktion | Historischer Endpunkt | Stand |
|---|---|---|
| Video Extension | `POST /v1/videos/video-extend` | Laut Changelog seit 2024 (v1.0), für v1.5/v1.6 ab 2025-03-31 („4–5 s pro Extension“). Galt nur für v1.x-Modelle, die heute discontinued sind. **Nicht mehr dokumentiert.** |
| Multi-Image-to-Video | `POST /v1/videos/multi-image2video` | Im Changelog 2025-08-15 erwähnt („102 % performance improvement“). **Keine aktuelle Doku-Seite.** Ersatz: Omni Video mit `refer_image`/Elements |
| Camera Control | `camera_control` in text2video/image2video (`type` simple / down_back / forward_up / right_turn_forward / left_turn_forward; `config` horizontal/vertical/pan/tilt/roll/zoom) | Laut Changelog nur v1.0/v1.5. **Nicht mehr im Schema.** Ersatz: Kamerabewegung im Prompt |
| Motion Brush | `static_mask`, `dynamic_masks[{mask, trajectories[{x,y}]}]` | Laut Changelog nur v1.5 PRO. **Nicht mehr im Schema.** |
| Lip Sync (alt) | `POST /v1/videos/lip-sync` mit `input{video_id|video_url, mode: text2video|audio2video, text (≤ 120), voice_id, voice_language, voice_speed, audio_type, audio_url|audio_file}` | [Drittquelle] ComfyUI (`comfy_api_nodes/nodes_kling.py`, master, Okt. 2026) nutzt das noch über deren Proxy. Offiziell ersetzt durch `advanced-lip-sync` (§8.3) |
| Elements (alt) | `/v1/general/custom-elements` | Laut Changelog 2026-02-25 weiterhin nutzbar, aber eine getrennte Bibliothek. Doku nur über https://ksurl.cn/QYFWJef0 |
| Modelle v1, v1-5, v1-6, v2-master, v2-1, v2-1-master | `model_name` | Nicht mehr in den Enums. [Drittquelle] GitHub-Issue #695 (griptape, 2026-10-02): `404/1203 "The model 'kling-v1-6' has been discontinued and is no longer available."` (auch für v2-master und v2-1-master beobachtet) |
| Virtual Try-On v1/v1.5 (`kolors-virtual-try-on`) | `/v1/images/kolors-virtual-try-on` | Seit 2026-09-15 auf die 3.0-Pipeline umgestellt, kompatibel; neu ist `/solutions/virtual_try_on` |

### 12.4 [Drittquelle] Lip-Sync- und TTS-Voice-IDs (ComfyUI `VOICES_CONFIG`)

Quelle: https://raw.githubusercontent.com/comfyanonymous/ComfyUI/master/comfy_api_nodes/nodes_kling.py

* **en:** girlfriend_4_speech02, genshin_vindi2, zhinen_xuesheng, AOT, ai_shatang, genshin_klee2,
  genshin_kirara, ai_kaiya, oversea_male1, ai_chenjiahao_712, chat1_female_new-3, chat_0407_5-1,
  cartoon-boy-07, uk_boy1, cartoon-girl-01, PeppaPig_platform, ai_huangzhong_712, ai_huangyaoshi_712,
  ai_laoguowang_712, chengshu_jiejie, you_pingjing, calm_story1, uk_man2, laopopo_speech02,
  heainainai_speech02, reader_en_m-v1, commercial_lady_en_f-v1
* **zh** (Auswahl): genshin_vindi2, zhinen_xuesheng, tiyuxi_xuedi, ai_shatang, tiexin_nanyou,
  girlfriend_1_speech02, girlfriend_2_speech02, zhuxi_speech02, uk_oldman3, dongbeilaotie_speech02,
  chongqingxiaohuo_speech02, chuanmeizi_speech02, chaoshandashu_speech02, ai_taiwan_man2_speech02,
  xianzhanggui_speech02, tianjinjiejie_speech02, diyinnansang_DB_CN_M_04-v2, yizhipiannan-v1,
  tianmeixuemei-v1, daopianyansang-v1, mengwa-v1

Die offizielle Liste liegt im qingque-Dokument (§8.2) und wurde nicht abgeglichen.

---

## 13. Preise (Resource-Pack-Units; USD in Klammern laut Doku)

Quelle: https://kling.ai/document-api/pricing/base/video

| Modell / Feature | 720p | 1080p | 4K |
|---|---|---|---|
| 3.0 Turbo (with native audio) | 0.8 U/s ($0.112) | 1.0 U/s ($0.14) | – |
| 3.0, ohne Audio | 0.6 ($0.084) | 0.8 ($0.112) | 3.0 ($0.42) |
| 3.0, mit Audio, ohne Voice | 0.9 | 1.2 | 3.0 |
| 3.0 Motion Control | 0.9 | 1.2 | – |
| 3.0 Omni, kein Video-Input, ohne Audio | 0.6 | 0.8 | 3.0 |
| 3.0 Omni, kein Video-Input, mit Audio | 0.8 | 1.0 | 3.0 |
| 3.0 Omni, mit Video-Input | 0.9 | 1.2 | 3.0 |
| O1, ohne / mit Video-Input | 0.6 / 0.9 | 0.8 / 1.2 | – |
| 2.6, ohne Audio | 0.3 | 0.5 | – |
| 2.6, mit Audio (ohne / mit Voice) | – | 1.0 / 1.2 | – |
| 2.6 Motion Control | 0.5 | 0.8 | – |
| 2.5 Turbo | 0.3 | 0.5 | – |
| Avatar | 0.4 U/s | 0.8 U/s | – |
| TTS / Face Recognition / Custom Voice | 0.05 U/Aufruf | | |
| Lip Sync | 0.5 U pro 5 s | | |
| Text-to-Audio / Video-to-Audio | 0.25 U/Aufruf | | |
| Image Recognition | 0.1 U/Aufruf | | |

Dazu der Changelog vom 2026-06-17: „3.0 Omni … Reference video duration expanded to 3–15 seconds, and
4K video generation is now supported … 3 units per second“.

---

## 14. Gotchas für den Proxy

1. **Zwei Statusvokabulare:** In der neuen API (`/tasks`, `/solutions`, neuer Callback) heißt es
   `succeeded`, in allen `/v1/*`-Endpunkten und im Legacy-Callback `succeed`.
2. **Zwei Feldnamen-Welten:**
   * Neu: `id`/`status`/`message`/`create_time`/`outputs[].url`/`external_id`.
   * Legacy: `task_id`/`task_status`/`task_status_msg`/`created_at`/`task_result.videos[].url`/`task_info.external_task_id`.
3. **`duration` hat zwei Typen:** In der neuen API ist es ein `int`, in Legacy und Multi-Elements ein
   **String** (`"5"`). Auch in den Responses ist die Dauer immer ein String.
4. **Defaults unterscheiden sich:**
   * Neu T2V/I2V 3.0: `multi_shot` = **true** (Legacy: false).
   * Legacy omni-video: `mode` = **pro** (sonst std).
   * Motion Control: `audio` = `original`.
5. **Resolution und Mode:** Neu wird `resolution` (720p/1080p/4k) gesetzt, Legacy `mode` (std/pro/4k).
   2.6 mit Audio und 2.5/2.6 mit First+Last Frame erzwingen 1080p (pro); bei 720p muss mit Fehler
   gerechnet werden.
6. **Kein `aspect_ratio` bei I2V.** Bei Omni ist es **Pflicht**, wenn weder First Frame noch Video vorhanden ist.
7. **Base64 ohne `data:`-Präfix.** Videos werden in der Regel nur als URL angenommen; der Proxy muss
   Uploads also selbst hosten.
8. **Bildlimits unterscheiden sich:** Die neue API erlaubt ≤ 50 MB, Legacy-, Avatar- und Element-Endpunkte ≤ 10 MB.
9. **Voice und Element in Legacy-I2V schließen sich gegenseitig aus** (`voice_list` vs. `element_list`).
   Die TTS-/Lip-Sync-Voice-IDs sind nicht die Custom-Voice-IDs.
10. **Abrechnung bei Motion Control und Omni-Video-Edit** richtet sich nach der Output- bzw. Input-Dauer,
    nicht nach `duration`.
11. **Concurrency 1303** ist kein Parameterfehler. Hier mit Backoff retryen; bei 1102 (Paket leer) nicht.
12. **`/account/costs`** braucht `start_time`/`end_time` und meldet `remaining_quantity` mit bis zu 12 h
    Verzögerung. Für ein Echtzeit-Guthaben ist der Endpunkt also ungeeignet.
13. **Kling 3.0 Turbo existiert nur in der neuen API**, also mit API-Key und ohne Legacy-Pendant.
14. **Callbacks** kommen bei jedem Statuswechsel. Die Verarbeitung muss idempotent sein. Signaturprüfung
    ist optional (Standard Webhooks).
15. **Ergebnis-URLs** sind 30 Tage gültig und hotlink-geschützt, also sofort herunterladen und speichern.

---

## 15. Unklar / nicht verifizierbar

* **Native Audio bei 3.0 Turbo:** Capability Map und Pricing sagen „Supported/With Native Audio“, das
  Request-Schema hat aber **kein `audio`-Feld**. Ob Turbo immer mit Ton generiert, ist unklar.
* **Voice Control bei 3.0:** Laut Capability Map nicht unterstützt. Legacy-I2V (`voice_list`) und Pricing
  („With Native Audio x No Voice Control“) deuten auf eine Variante hin, die aktuell nur für 2.6 gilt.
  Für `kling-v3` nicht verifiziert.
* **4K mit Referenzvideo (3.0 Omni):** Changelog 2026-04-23 sagt „except for reference video“,
  Changelog 2026-06-17 sagt „4K generation is now supported“. Die neue API-Doku schränkt das nicht ein.
  Vermutlich jetzt unterstützt, aber nicht bestätigt.
* **End-Frame-only in Legacy-I2V:** Das Schema sagt „mindestens eines von image/image_tail“, die
  Capability Map sagt „nicht unterstützt“.
* **Delete-Element-Pfad:** Die Video-Doku nennt `/v1/general/delete-advanced-elements`, die Image-Doku
  `/v1/general/delete-elements`.
* **Batch-Limit von `GET /tasks`:** nicht dokumentiert (bei `/solutions` sind es 20).
* **Ob `GET /tasks` auch Legacy-Tasks findet** (`/v1/videos/text2video`): nicht dokumentiert. Vermutlich
  nein, weil die Doku von „async tasks“ der neuen API spricht.
* **Ob v1.x-, v2.0- und v2.1-Modelle offiziell abgeschaltet sind:** Es gibt keine offizielle Ankündigung
  im Changelog. Die Fehlermeldung „discontinued“ stammt nur aus einer [Drittquelle].
* **Video Extension, Multi-Image-to-Video und Legacy-Lip-Sync** sind offiziell nicht mehr dokumentiert.
  Ob die Endpunkte noch antworten, wurde nicht getestet (kein Live-Call; AGENTS.md: keine bezahlten Tests).
* **`/account/costs`** liefert kein Pay-as-you-go-Balance-Guthaben. Ob es dafür einen kostenlosen
  Endpunkt gibt, ist nicht dokumentiert.
* **Callback:** Retries, Timeout, Absender-IPs und die erwartete HTTP-Antwort (außer „return HTTP 200“
  beim Test) sind nicht dokumentiert.
* **Exakter Host und Signatur-/Ablaufmechanik der Ergebnis-URLs** („hotlink protection“): nicht spezifiziert.
* **TTS-Voice-Liste:** Sie liegt nur in einem externen qingque-Dokument und wurde nicht ausgelesen.
* **Sprachen von Native Audio / Voice:** Für Video ist keine Sprachliste dokumentiert. Für TTS gibt es nur zh/en.
* **Kosten der Multi-Elements-Selection-Schritte** (`final_balance_deduction` im Response): nicht ausgewiesen.
* **Das alte Elements-API** (ksurl-Link) wurde nicht geprüft.
* **`kling-video-o3`** wird in der Elements-Doku erwähnt, ist aber kein dokumentierter `model_name`.
* **China-Endpoint** `api-beijing.klingai.com` steht nur in `kling.ai/llms.txt`. Die Gültigkeit globaler
  API-Keys dort wurde nicht geprüft.

---

## Anhang A: `effect_scene`-Werte (219, Stand der Doku)

Quelle: https://kling.ai/document-api/api/effects/video-effects

Dual-Image-Effekte (15, `input.images`): pet_skateboard, daily_ootd, toss_run, switch_to_silk,
studio_look, french_elegance, finger_swipe, smooth_transition, kiss_pro, snow_night_kiss, eternal_kiss,
cheers_2026, fight_pro, hug_pro, heart_gesture_pro

Vollständige Enum-Liste:

```
net_the_fish, birthday_board, summer_fireworks, blow_blaze, champagne_birthday, pet_working_daily,
pet_roll_window, pet_crash_earth, makeup_style, hair_dressup, barbie_transform, critter_paste,
wiggle_faces_pets, paw_headbang, food_splash, dj_pet, pet_diving, disco_paws, pet_fitness, j_var_live,
pet_burst, idol_live, beast_striker, african_sway, jealousy_sway, chubby_fish, shrug_dance, soccer_star,
bra_hot_dance, arg_hot_dance, fra_hot_dance, bra_goal, arg_goal, por_goal, victory_slide, samba_fever,
bicycle_kick, football_dance_2, red_card_sent_off, football_dance, magic_world_vlog, magic_world_vlog_9_16,
air_dunk, whirling_beverage_9_16, tennis_trend, tennis_trend_9_16, football_live_9_16, whirling_beverage,
f1_live, football_live, spielberg_transition, korean_baseball_9_16, korean_baseball, pet_skateboard,
daily_ootd, tiny_beast_printer, landmark_reveal, winter_charm, flash_ride, maestro_of_magic,
magic_carpet_ride, good_luck_spirit, shooting_star, sparkler_wand, sovereign_scepter, dirt_rush,
return_of_the_king, dance_with_dragon, minimalist_light, martial_meow, sassy_shake, knock_at_a_door_revenge,
palm_sized_figure_pro, prank_box, perler_beads, spring_bloom, toss_run, switch_to_silk, get_rich_quick,
make_it_rain, twist_shake, the_hip_sway, send_my_love, funky_martian, wealth_drive, the_high_kick,
the_exercise, lucky_veggie, studio_look, flash_drive, shush_my_dreams, french_elegance, finger_swipe,
advent_of_flora, smooth_transition, kiss_pro, raid_check, snow_night_kiss, eternal_kiss, fortune_in_motion,
chinese_trend, sedan_chair_dance, skyfall, good_luck_dance, laicai_dance, yangge_dance, color_mixing,
lantern_festival_cuju, unique_firework, unique_spring_couplets, horse_mask, fortune_knocks_cartoon,
tangyuan_to_animal, hot_feet_dance, swag_dance, pigeon_dance, bloodline_dance, chanel_dance, cute_dance,
love_theme_song, pumpitup_dance, city_to_village, fortune_god_transform, new_year_feast, ring_in_new,
horse_year_firework, crystal_horse, drunk_dance, drunk_dance_pet, daoma_dance, bouncy_dance,
smooth_sailing_dance, new_year_greeting, lion_dance, prosperity, great_success, golden_horse_fortune,
red_packet_box, lucky_horse_year, lucky_red_packet, lucky_money_come, lion_dance_pet, dumpling_making_pet,
fish_making_pet, pet_red_packet, lantern_glow, expression_challenge, overdrive, heart_gesture_dance, poping,
martial_arts, running, nezha, motorcycle_dance, subject_3_dance, ghost_step_dance, phantom_jewel, zoom_out,
cheers_2026, fight_pro, hug_pro, heart_gesture_pro, dollar_rain_pro, pet_bee_pro, countdown_teleport,
santa_random_surprise, magic_match_tree, bullet_time_360, happy_birthday, birthday_star, thumbs_up_pro,
tiger_hug_pro, pet_lion_pro, surprise_bouquet, bouquet_drop, glamour_photo_shoot, box_of_joy,
first_toast_of_the_year, my_santa_pic, santa_gift, steampunk_christmas, snowglobe, christmas_photo_shoot,
ornament_crash, santa_express, instant_christmas, coronation_of_frost, building_sweater, spark_in_the_snow,
scarlet_and_snow, bullet_time_lite, jumping_ginger_joy, pure_white_wings, black_wings, golden_wing,
pink_pink_wings, venomous_spider, throne_of_king, luminous_elf, woodland_elf, guardian_spirit, swish_swish,
snowboarding, witch_transform, vampire_transform, pumpkin_head_transform, demon_transform, mummy_transform,
zombie_transform, cute_pumpkin_transform, halloween_escape, pet_moto_rider, running_man, 3d_cartoon_2,
pet_dance, swing_swing, day_to_night, surfsurf, skateskate
```
