# BytePlus ModelArk Seedance – Capability-Katalog und Lückenanalyse

Stand der Recherche: **2026-10-11**. Primärquelle ist die BytePlus-ModelArk-Doku (`docs.byteplus.com/en/docs/ModelArk/…`).
Die Seiten werden per JavaScript gerendert. Ausgelesen wurde deshalb das eingebettete Markdown (`window._ROUTER_DATA … curDoc.MDContent`),
zuerst im Browser über Chrome DevTools, danach per `curl` auf dieselbe SSR-Seite. Gegengeprüft wurde mit Volcengine
(`docs.volcengine.com/api/doc/getDocDetail?LibraryCode=ark&DocumentCode=create-video-generation-task-api`).
Alles, was nicht aus der BytePlus-Doku stammt, ist markiert: **[Volcengine]** für die China-Doku, **[Code]** für das
Verhalten des Proxys, geprüft durch Lesen des Codes oder einen Offline-Aufruf von `build_task_payload`.

Gelesene Seiten und deren Aktualisierungsstand (`UpdatedTime`):

| Thema | URL | Stand |
|---|---|---|
| Create a video generation task | https://docs.byteplus.com/en/docs/ModelArk/1520757 (= `create-video-generation-task-api`) | 2026-10-08 |
| Retrieve a video generation task | https://docs.byteplus.com/en/docs/ModelArk/get-video-generation-task-api | 2026-09-28 |
| List video generation tasks | https://docs.byteplus.com/en/docs/ModelArk/list-video-generation-tasks-api | 2026-10-08 |
| Cancel or delete a video generation task | https://docs.byteplus.com/en/docs/ModelArk/cancel-or-delete-video-generation-tasks-api | 2026-10-08 |
| Dreamina Seedance 2.5 tutorial | https://docs.byteplus.com/en/docs/ModelArk/2607688 (= `seedance-2-5`) | 2026-09-28 |
| Dreamina Seedance 2.5 prompt guide | https://docs.byteplus.com/en/docs/ModelArk/2607689 (= `seedance-2-5-prompt-guide`) | 2026-09-28 |
| Dreamina Seedance 2.0 series tutorial | https://docs.byteplus.com/en/docs/ModelArk/seedance-2-0 | 2026-09-29 |
| Video generation tutorial (alle Modelle) | https://docs.byteplus.com/en/docs/ModelArk/video-generation-tutorial | 2026-09-28 |
| Model list | https://docs.byteplus.com/en/docs/ModelArk/model-list | 2026-09-28 |
| Model deprecations | https://docs.byteplus.com/en/docs/ModelArk/1350667 | 2026-09-28 (Text: 10.09.2026) |
| Error codes | https://docs.byteplus.com/en/docs/ModelArk/error-codes | 2026-10-06 |
| Create portrait videos with Dreamina Seedance models | https://docs.byteplus.com/en/docs/ModelArk/seedance-portrait-asset-guide | 2026-10-08 |
| Digital character library | https://docs.byteplus.com/en/docs/ModelArk/avatar-library | 2026-09-28 |
| Add real-human assets to asset library | https://docs.byteplus.com/en/docs/ModelArk/upload-real-person-portrait-assets | 2026-09-28 |
| Copyrighted IP video generation | https://docs.byteplus.com/en/docs/ModelArk/generate-copyright-video | 2026-09-28 |
| Seedance 2.x Badcase-Report-API | https://docs.byteplus.com/en/docs/ModelArk/2389900 | 2026-08-28 |
| [Volcengine] 创建视频生成任务 | https://www.volcengine.com/docs/82379/1520757 | 2026-10-08 |

---

## 0. Kurzfassung

* **Endpunkte:** `POST/GET /api/v3/contents/generations/tasks`, `GET/DELETE /api/v3/contents/generations/tasks/{id}`.
  Base URL: `https://ark.ap-southeast.bytepluses.com`. Authentifizierung nur per API-Key (`Authorization: Bearer $ARK_API_KEY`).
* **Aktive Modelle:** `dreamina-seedance-2-5-260628`, `dreamina-seedance-2-0-260128`, `dreamina-seedance-2-0-fast-260128`,
  `dreamina-seedance-2-0-mini-260615`, `seedance-1-0-pro-250528` und `seedance-1-0-pro-fast-251015`.
  `seedance-1-5-pro-251215` ist **„Retired“** und wird am **11.11.2026, 17:00 UTC+8** abgeschaltet
  (Ersatz: `dreamina-seedance-2-0-mini-260615`). **Seedance 1.0 lite i2v/t2v** ist seit dem **13.05.2026** abgeschaltet
  (automatischer Ersatz: `dreamina-seedance-2-0-fast-260128`).
* **Neu bzw. vom Proxy noch nicht abgedeckt:** `draft` plus `content[].type="draft_task"` (Draft-Modus für 2.5 und 1.5 pro),
  Base64-Eingaben (`data:image/…`, `data:audio/…`), öffentliche Asset-IDs `asset://…` (Digital-Character-Bibliothek),
  `filter.service_tier` in der Liste und die Antwortfelder `draft`, `draft_task_id`, `seed`, `frames`, `framespersecond`
  und `output_format`. Der einheitliche Vertrag (`references`, `task`, `aspect_ratio`, `seconds:"auto"`) wird für Seedance
  **nicht** ausgewertet. Siehe §11.
* **Falsche Grenzen im Proxy:** Der `seed`-Höchstwert ist 2147483647, nicht 4294967295. Die Standarddauer von 2.5 ist `-1`,
  nicht 5. `seed` und `camera_fixed` sind laut Doku nur für 1.x dokumentiert, `priority` nur für 2.x und `service_tier=flex`
  nur für 1.x. `generate_audio` wird bei 1.0 pro/pro fast trotzdem gesetzt. `ratio=adaptive` ist für 1.0-Text-to-Video
  unzulässig.

---

## 1. Endpunkte, Authentifizierung, Region

Quellen: Create, Get, List und Cancel/Delete (URLs siehe oben).

| Operation | Methode und Pfad | API-Explorer-Action |
|---|---|---|
| Task anlegen | `POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks` | `CreateContentsGenerationsTasks` |
| Task abfragen | `GET …/api/v3/contents/generations/tasks/{id}` | `GetContentsGenerationsTask` |
| Tasks auflisten | `GET …/api/v3/contents/generations/tasks?page_num=&page_size=&filter.status=&filter.task_ids=&filter.model=&filter.service_tier=` | `ListContentsGenerationsTasks` |
| Abbrechen oder löschen | `DELETE …/api/v3/contents/generations/tasks/{id}` | `DeleteContentsGenerationsTasks` |

* Für alle vier Endpunkte gilt: „This API supports only API Key authentication.“
* `model` darf eine Modell-ID **oder eine Endpoint-ID** sein, also ein eigener Inference-Endpoint mit eigenem
  Rate-Limit, Monitoring und Billing-Modus.
* Aktivierung von Seedance 2.0 und 2.5: Das Konto braucht ein Guthaben über 30 USD, einen AI Savings Plan ab 30 USD oder
  ein Seedance-Ressourcenpaket.
  Quelle: https://docs.byteplus.com/en/docs/ModelArk/seedance-model-activation-usage-and-refund

---

## 2. Create task – Request-Body (vollständig)

Quelle: https://docs.byteplus.com/en/docs/ModelArk/1520757. Gegenprüfung: [Volcengine] 1520757.

### 2.1 Top-Level-Felder

| Feld | Typ | Default | Werte / Bereich | Modelle (laut Doku) |
|---|---|---|---|---|
| `model` | string, **required** | – | Modell-ID oder Endpoint-ID | alle |
| `content` | object[], **required** | – | siehe §2.2 | alle |
| `omni_reference_task_type` *(new)* | string | `auto` | `auto`, `reference`, `edit`, `extend` | **nur 2.5** |
| `resolution` | string | modellabhängig | `480p`, `720p`, `1080p`, `4k` (Matrix §8) | alle |
| `ratio` | string | modellabhängig | `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`, `adaptive` | alle (Einschränkungen §2.4) |
| `duration` | integer | modellabhängig | 2.5: `[4,30]` oder `-1`. 2.0er-Serie: `[4,15]` oder `-1`. 1.5 pro: `[4,12]` oder `-1`. 1.0 pro/pro fast: `[2,12]` | alle |
| `frames` | integer | – | `[29,289]` mit `25+4n`. Hat Vorrang vor `duration` | **nur 1.0 pro, 1.0 pro fast** |
| `generate_audio` | boolean | `true` | – | **2.5, 2.0er-Serie, 1.5 pro** (laut [Volcengine] nur 2.5 und 2.0) |
| `watermark` | boolean | `false` | `true` = Text „AI Generated“ unten rechts | alle |
| `output_format` *(new)* | string | `mp4` | `mp4`, `mov` (H.264, yuv444p, PCM-Audio) | **nur 2.5** |
| `seed` | integer | `-1` | **`[-1, 2147483647]`** | laut Liste **nur 1.5 pro, 1.0 pro, 1.0 pro fast** (Widerspruch siehe §12) |
| `camera_fixed` | boolean | `false` | – | **nur 1.5 pro, 1.0 pro, 1.0 pro fast**. „Reference-image scenarios are not supported.“ |
| `return_last_frame` | boolean | `false` | Liefert `content.last_frame_url` (JPEG, gleiche Pixelmaße, ohne Wasserzeichen) | alle |
| `draft` | boolean | `false` | `true` erzeugt ein 480p-Draft-Video | **nur 2.5 und 1.5 pro** |
| `service_tier` | string | `default` | `default` (online), `flex` (offline, 50 % Preis, TPD-Quota) | `flex` **nicht** für 2.5 und die 2.0er-Serie. Nachträglich nicht änderbar |
| `callback_url` | string | – | Webhook-URL, siehe §7 | alle |
| `execution_expires_after` | integer | `172800` | `[3600, 259200]` Sekunden ab `created_at` | alle |
| `priority` | integer | `0` | `[0, 9]`, höher wird früher bedient (pro Endpoint) | **nur 2.5 und 2.0er-Serie**. Nicht kombinierbar mit `service_tier=flex` |
| `safety_identifier` | string | – | stabile End-User-ID, **≤ 64 Zeichen**, Hash empfohlen | alle |
| `tools` | object[] | – | `[{ "type": "web_search" }]` | **[Volcengine] nur China** (2.5 und 2.0er-Serie). Fehlt in der BytePlus-Doku vollständig |

Antwort von Create: `{ "id": "cgt-…" }`. Die Task-ID wird 7 Tage aufbewahrt. Bei `draft:true` ist sie die Draft-Task-ID.

**Alte Prompt-Parameter (schwache Validierung):** `--rs 720p --rt 16:9 --dur 5 --seed 11 --cf false --wm true`, angehängt an
`content[].text`. Das geht nur für `resolution`, `ratio`, `duration`, `frames`, `seed`, `camera_fixed` und `watermark`.
Ungültige Werte werden dabei ignoriert oder lösen einen Fehler aus. Empfohlen ist der Request-Body mit strenger Validierung.

### 2.2 `content[]`-Elemente

| `type` | Pflichtfelder | `url`-Formen | Rollen (`role`) | Modelle |
|---|---|---|---|---|
| `text` | `text` | – | – | alle |
| `image_url` | `image_url.url` | öffentliche URL, **Base64** `data:image/<fmt-lowercase>;base64,…`, **`asset://<ASSET_ID>`** | `first_frame` (oder leer bei genau einem Bild), `last_frame`, `reference_image` | first_frame: alle. last_frame: alle außer 1.0 pro fast. reference_image: 2.5 (1–30), 2.0er-Serie (1–9) |
| `video_url` | `video_url.url` | öffentliche URL, `asset://…` (**kein Base64**) | `reference_video` (fest) | 2.5 (≤10), 2.0er-Serie (≤3) |
| `audio_url` | `audio_url.url` | öffentliche URL, **Base64** `data:audio/<fmt>;base64,…`, `asset://…` | `reference_audio` (fest) | 2.5 (≤10, auch nur Audio), 2.0er-Serie (≤3, nur zusammen mit Bild oder Video) |
| `draft_task` | `draft_task.id` | – | – | **2.5, 1.5 pro** |

Zulässige Kombinationen: Text · Text(opt.) + Bild · + Video · + Audio (Audio allein nur bei 2.5) · Bild + Audio · Bild + Video ·
Video + Audio · Bild + Video + Audio · Draft-Task-ID.

**Gegenseitiger Ausschluss:** Image-to-Video mit erstem Frame, Image-to-Video mit erstem und letztem Frame und
Omni-Reference (`reference_*`) lassen sich **nicht mischen**. Ein Workaround ist, im Prompt ein Referenzbild als Start- oder
Endbild zu benennen. Bei abweichenden Seitenverhältnissen von erstem und letztem Frame gewinnt der erste Frame, der letzte
wird zugeschnitten. Beide Bilder dürfen identisch sein.

**Bezug im Prompt:** Assets werden als `@Image 1`/`Image 1`, `@Video 1` und `@Audio 1` referenziert. Gezählt wird pro Typ
in Array-Reihenfolge ab 1. **Ein Verweis per Asset-ID im Prompt ist nicht zulässig.**

### 2.3 Eingabegrenzen

Quellen: Create, 2.5-Tutorial („Usage limits“) und Video-Tutorial („Limitations“).

* **Bild:** jpeg, png, webp, bmp, tiff, gif. Ab 1.5 pro zusätzlich heic und heif. Seitenverhältnis (B/H) `[0.4, 2.5]`,
  Kantenlänge `[300, 6000]` px, < 30 MB pro Bild, Request-Body ≤ 64 MB. Keine großen Dateien als Base64.
* **Video:** mp4 und mov. Codecs H.264/AVC oder H.265/HEVC. Audio AAC oder MP3 (bei mov laut 2.5-Tutorial zusätzlich PCM).
  Auflösung 480p–4k, Seitenverhältnis `[0.4, 2.5]`, Kanten `[300, 6000]` px. Pixelzahl `[407 696, 8 295 044]`,
  ≤ 200 MB, 24–60 fps.
  * 2.5: 2–30 s pro Clip, für **Edit-Tasks 4–30 s**, höchstens 10 Clips mit zusammen ≤ 30 s.
  * 2.0er-Serie: 2–15 s pro Clip, höchstens 3 Clips mit zusammen ≤ 15 s.
* **Audio:** wav und mp3, ≤ 15 MB, Request-Body ≤ 64 MB.
  * 2.5: 2–30 s pro Clip, höchstens 10 Clips mit zusammen ≤ 30 s.
  * 2.0er-Serie: 2–15 s pro Clip, höchstens 3 Clips mit zusammen ≤ 15 s.
* **Echte Gesichter:** 2.5 und die 2.0er-Serie lehnen Bilder und Videos mit realen Gesichtern ab
  (`InputImageSensitiveContentDetected.PrivacyInformation` / `InputVideo…PrivacyInformation`). Für Porträts gibt es drei
  Wege, siehe §9.
* Erzeugtes Audio ist immer **Mono**.
* Prompt-Sprachen: Alle Modelle verstehen Englisch. 2.0 zusätzlich es, id, pt und ja. 2.5 zusätzlich es, id, pt, ja, ms, th,
  ar, vi und ko. Laut 2.5-Tutorial sind das „11 Sprachen inkl. Chinesisch“. Empfohlen sind höchstens 1000 englische Wörter.

### 2.4 `ratio`-Regeln pro Task und Modell

| Task | 2.5 | 2.0er-Serie | 1.5 pro | 1.0 pro / pro fast |
|---|---|---|---|---|
| Text-to-Video | `adaptive` oder fest | `adaptive` oder fest | `adaptive` oder fest | **nur fest, kein `adaptive`** |
| Erster bzw. erster+letzter Frame | **nur `adaptive`** (übernimmt das Seitenverhältnis von `first_frame`) | `adaptive` oder fest | `adaptive` oder fest | `adaptive` oder fest |
| Omni Edit / Extend | **nur `adaptive`** | `adaptive` oder fest | – | – |
| Omni Reference | `adaptive` oder fest | `adaptive` oder fest | – | – |
| Default | `adaptive` | `adaptive` | `adaptive` | T2V `16:9`, I2V `adaptive` |

Pixelmaße (Auszug; Unterschiede zwischen den Familien):

| Auflösung/Verhältnis | 2.5 | 2.0er-Serie / 1.5 pro | 1.0er-Serie |
|---|---|---|---|
| 480p 16:9 | 854×480 | 864×496 | 864×480 |
| 480p 9:16 | 480×854 | 496×864 | 480×864 |
| 720p 16:9 | 1280×720 | 1280×720 | 1248×704 |
| 1080p 16:9 | 1920×1080 | 1920×1080 | 1920×1088 |
| 4k 16:9 | – | 3840×2160 (nur 2.0) | – |

Die volle Tabelle mit 4:3, 1:1, 3:4 und 21:9 steht in der Create-Doku. Weichen Bild- und Zielverhältnis bei I2V voneinander
ab, wird das Bild mittig zugeschnitten (Formel im Video-Tutorial, Abschnitt „Image cropping rules“).

### 2.5 `duration` und `frames`

* Bei `duration=-1` wählt das Modell selbst eine ganze Sekundenzahl im gültigen Bereich (2.0er-Serie, 1.5 pro, 2.5 außer Edit).
  Bei **2.5 Edit** entspricht die Dauer dem Quellvideo. Sie kann eine Nachkommastelle haben und bis zu etwa 0,4 s kürzer sein.
* Zurückgegebene `duration` = `floor(frames/24)`. Beispiel: 133 Frames ergeben 5.
* `frames` (nur 1.0): `25+4n` im Bereich `[29,289]`. Beispiel: 2,4 s ergeben 57 Frames, also 2,375 s. Bei gesetztem `frames`
  liefert GET `frames` statt `duration`.
* Ausgabe immer mit 24 fps.

---

## 3. Seedance 2.5 – Task-Typen, Constraints, Fehlerbehandlung

Quelle: https://docs.byteplus.com/en/docs/ModelArk/2607688 (#2.5_compatibility, #2.5_task_type_intro, #2.5_error_handling).

| Task | Auslöser | Constraints |
|---|---|---|
| Text-to-Video | nur Text | keine |
| Erster bzw. erster+letzter Frame | `role` = `first_frame`/`last_frame` | `ratio` muss `adaptive` sein |
| Omni → reference | ≥ 1 `reference_image`/`_video`/`_audio` | keine |
| Omni → edit | ≥ 1 `reference_video` und Prompt mit Edit-Absicht („edit the video“, „add“, „remove“, „replace“ …) | `ratio=adaptive`, `duration=-1`, Video 4–30 s |
| Omni → extend | ≥ 1 `reference_video` und Prompt mit Extend-Absicht („extend forward/backward“, „continue“ …) | `ratio=adaptive` |

* **Synchron:** Ist `omni_reference_task_type` explizit `edit` oder `extend`, wird beim Submit geprüft. Ein Verstoß liefert
  sofort einen 400er, und es entsteht kein Task.
* **Asynchron:** Bei `auto` oder fehlendem Feld sowie bei First/Last-Frame-Verstößen schlägt der Task erst nach dem Start fehl,
  mit `InvalidParameter.TaskTypeConstraint`. Erkennt das Modell einen anderen Task als angegeben, kommt
  `InvalidParameter.TaskTypeMismatch`, auch dann asynchron.
* Empfehlung bei `auto`: `ratio=adaptive`, `duration=-1` und Referenzvideos mit 4–30 s.
* 2.5 1080p wird mit **10 Bit und H.265/HEVC** ausgegeben, 2.0 4k ebenso. 2.0 1080p und alle 480p/720p-Ausgaben haben 8 Bit.
* Die 2.0er-Serie kann „Extend“ auch als **Stitching** von bis zu 3 Clips („Video 1 → Video 2 → Video 3“). Einen eigenen
  Parameter dafür gibt es nicht, die Steuerung läuft rein über den Prompt
  (Quelle: https://docs.byteplus.com/en/docs/ModelArk/seedance-2-0, „Extend video“).

---

## 4. Draft-Modus

Quellen: 2.5-Tutorial #2.5_draft_mode und Video-Tutorial #5acd28c8.

**Schritt 1:** `"draft": true`. Erlaubt ist nur `resolution=480p`, jede andere Auflösung führt zu einem Fehler.

* 2.5: Abrechnung wie ein normales 480p-Video.
* 1.5 pro: Abrechnung mit Faktor 0,6 (mit Audio). `return_last_frame` und `service_tier=flex` werden nicht unterstützt.

**Schritt 2:** `content: [{ "type": "draft_task", "draft_task": { "id": "<draft-task-id>" } }]`.
Die Draft-ID ist 7 Tage ab `created_at` gültig.

| Regel | 2.5 | 1.5 pro |
|---|---|---|
| Feste Werte | `model` gleich wie im Draft. `draft` weglassen oder `false`. `resolution` **nur `1080p`** | `model` gleich |
| Automatisch übernommen | `content.text`, alle Referenzen, `duration`, `ratio`, `seed`, `generate_audio`, `omni_reference_task_type`. **Nicht erneut senden – sonst Fehler, auch bei identischem Wert** | `content.text`, `content.image_url`, `generate_audio`, `seed`, `ratio`, `duration`, `camera_fixed` |
| Neu setzbar | `return_last_frame`, `output_format`, `watermark`, `service_tier`, `execution_expires_after`, `priority`, `callback_url`, `safety_identifier` | `resolution`, `watermark`, `service_tier`, `return_last_frame` usw. |

Das GET-Antwortfeld `draft` (bool) wird laut Doku „nur von 1.5 pro“ geliefert. `draft_task_id` steht im Final-Task.

---

## 5. Get, List, Delete – Parameter und Antwortfelder

Quellen: Get, List und Cancel/Delete (URLs siehe oben).

### 5.1 GET `/tasks/{id}` und `items[]` von List

| Feld | Typ | Bedeutung |
|---|---|---|
| `id` | string | Task-ID |
| `model` | string | `Modellname-Version` |
| `status` | string | `queued`, `running`, `cancelled`, `succeeded`, `failed`. **Zusätzlich `expired`** (laut Delete-Tabelle und Callback, fehlt in der Get-Liste) |
| `error` | object\|null | `{code, message}` |
| `content.video_url` | string | 24 h gültig. Bei 2.5 höchstens **100 Downloads** |
| `content.last_frame_url` | string | nur bei `return_last_frame=true`. 24 h, bei 2.5 höchstens 100 Downloads |
| `created_at`, `updated_at` | int | Unix-Sekunden |
| `duration` **oder** `frames` | int | je nachdem, was im Request stand |
| `framespersecond` | int | 24 |
| `resolution`, `ratio` | string | tatsächlich verwendete Werte |
| `seed` | int | verwendeter Seed |
| `generate_audio` | bool | 2.5, 2.0er-Serie, 1.5 pro |
| `output_format` | string | `mp4`/`mov` (2.5) |
| `draft` | bool | nur 1.5 pro |
| `draft_task_id` | string | im Final-Task aus einem Draft |
| `service_tier` | string | tatsächlich verwendet |
| `execution_expires_after` | int | Sekunden |
| `priority` | int | effektive Priorität |
| `safety_identifier` | string | Echo |
| `usage.completion_tokens`, `usage.total_tokens` | int | Input-Tokens sind immer 0. Die 2.0er-Serie hat eine Mindest-Tokenmenge |
| `usage.tool_usage.web_search` | int | **[Volcengine]**, nur bei `tools` |

Retention: Abfragbar sind nur Tasks aus `[T-7 Tage, T)`. Abgebrochene Tasks werden nach 24 h automatisch gelöscht.

### 5.2 List-Query-Parameter

| Parameter | Typ | Default | Bereich |
|---|---|---|---|
| `page_num` | int | 1 | `[1, 500]` |
| `page_size` | int | 20 | `[1, 500]` |
| `filter.status` | string | – | `queued`, `running`, `cancelled`, `succeeded`, `failed` |
| `filter.task_ids` | string[] | – | wiederholbar: `filter.task_ids=a&filter.task_ids=b` |
| `filter.model` | string | – | **eine** Modell-ID oder Endpoint-ID. Pflicht bei API-Key-Rechten „Custom“ |
| `filter.service_tier` | string | `default` | `default`, `flex` |

Antwort: `items[]` und `total`.

### 5.3 DELETE `/tasks/{id}`

| Status | Wirkung | Status danach |
|---|---|---|
| `queued` | wird aus der Queue entfernt | `cancelled` |
| `running` | **nicht möglich** | – |
| `succeeded`, `failed`, `expired` | Datensatz wird gelöscht | nicht mehr abfragbar |
| `cancelled` | **nicht möglich** | – |

**Keine Response-Felder** (leerer Body).

---

## 6. Rate Limits und Aufbewahrung

Quellen: Model list #7571da3f, 2.5-Tutorial #2.5_rate_limits, Video-Tutorial „Rate limits“ und „Retention period“.

* Die Limits gelten pro Hauptkonto und Modell, unabhängig von der Version. Bei Überschreitung kommt `429 Too Many Requests`.
  Ist das Concurrency-Limit erreicht, werden neue Tasks **gequeued, nicht abgelehnt**.

| Modell | RPM Enterprise / Individual | Concurrency Ent. / Ind. | flex |
|---|---|---|---|
| 2.5 | 600 / 180 | 10 / 3 | nicht unterstützt |
| 2.0 (nicht 4K) | 600 / 180 | 10 / 3 | nicht unterstützt |
| 2.0 **4K** | **15 / 15** | **1 / 1** | nicht unterstützt |
| 2.0 fast, 2.0 mini | 600 / 180 | 10 / 3 | nicht unterstützt |
| 1.0 pro, 1.0 pro fast, 1.5 pro | 600 | 10 | TPD 500B |

* Nicht-Inferenz-APIs (pro Konto): GET Task **20 QPS**, List **1 QPS**, DELETE **20 QPS**.
* Aufbewahrung: Task-Datensätze 7 Tage. Video- und Last-Frame-URL 24 h, bei 2.5 höchstens 100 Downloads.
  Empfohlen wird ein TOS-Datenabo zur Sicherung.

---

## 7. Callback (`callback_url`)

Quellen: Create (`callback_url`) und Video-Tutorial #caf01f12 „Use webhook notifications“.

* Bei jeder Statusänderung schickt ModelArk einen `POST` an `callback_url`. Der Body hat dieselbe Struktur wie die Antwort von
  GET `/tasks/{id}`.
* Mögliche Status: `queued`, `running`, `succeeded`, `failed`, `expired`. `cancelled` taucht in der Callback-Liste nicht auf.
* Kommt bei `succeeded`/`failed` nicht innerhalb von 5 s eine Erfolgsbestätigung, wird der Callback **dreimal wiederholt**.
* Beispiel-Body:
  `{"id":"cgt-…","model":"dreamina-seedance-2-5-260628","status":"running","created_at":…,"updated_at":…,"service_tier":"default","execution_expires_after":172800}`
* Die Doku nennt **keine Signatur und keine Authentifizierung** des Callbacks.

---

## 8. Modelle und Capability-Matrix

Quellen: Model list, Video-Tutorial „Model capabilities“, 2.5- und 2.0-Tutorial, Create und Model deprecations.

| | 2.5 | 2.0 | 2.0 fast | 2.0 mini | 1.5 pro | 1.0 pro | 1.0 pro fast |
|---|---|---|---|---|---|---|---|
| Model-ID | `dreamina-seedance-2-5-260628` | `dreamina-seedance-2-0-260128` | `dreamina-seedance-2-0-fast-260128` | `dreamina-seedance-2-0-mini-260615` | `seedance-1-5-pro-251215` (**Retired**, aus am 11.11.2026) | `seedance-1-0-pro-250528` | `seedance-1-0-pro-fast-251015` |
| T2V | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| I2V erster Frame | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| I2V erster+letzter Frame | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Ref.-Bilder | 1–30 | 1–9 | 1–9 | 1–9 | ✗ | ✗ | ✗ |
| Ref.-Videos | ≤10 (Σ 30 s) | ≤3 (Σ 15 s) | ≤3 | ≤3 | ✗ | ✗ | ✗ |
| Ref.-Audio | ≤10 (Σ 30 s), auch allein | ≤3, nur mit Bild/Video | dito | dito | ✗ | ✗ | ✗ |
| Edit / Extend | ✓ (Task-Hint) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Audio-Ausgabe (`generate_audio`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Draft | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| `return_last_frame` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Auflösungen (Default) | 480p/720p/1080p (720p) | 480p/720p/1080p/4k (720p) | 480p/720p (720p) | 480p/720p (720p) | 480p/720p/1080p (720p) | 480p/720p/1080p (**1080p**) | 480p/720p/1080p (**1080p**) |
| Dauer (Default) | 4–30 oder -1 (**-1**) | 4–15 oder -1 (5) | dito | dito | 4–12 oder -1 (5) | 2–12 (5) | 2–12 (5) |
| `frames` | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| `output_format` | mp4, mov | mp4 | mp4 | mp4 | mp4 | mp4 | mp4 |
| `seed` / `camera_fixed` | ✗ laut Liste (siehe §12) | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ |
| `priority` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| `service_tier=flex` | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ |

Abgeschaltet: `bytedance-seedance-1-0-lite-i2v-250428` und `bytedance-seedance-1-0-lite-t2v-250428`.
Deprecation am 23.03.2026, Abschaltung am 13.05.2026. Empfohlener Ersatz `…-1-0-pro-fast-251015`, automatisch umgestellt
auf `dreamina-seedance-2-0-fast-260128`. Quelle: https://docs.byteplus.com/en/docs/ModelArk/1350667 („Third batch“).

---

## 9. Porträts, Assets und weitere Plattformfunktionen

* **Trusted Model Outputs:** Gesichtshaltige Videos von 2.5 und 2.0 (ab 11.03.2026), ihre Last-Frames (ab 16.04.2026)
  und Seedream-5.0-Bilder (ab 16.04.2026) aus **demselben Konto** gelten 30 Tage lang als vertrauenswürdige Eingabe.
  Voraussetzung: Die Datei ist unverändert, also nicht komprimiert und nicht weitergeleitet.
  Quelle: seedance-portrait-asset-guide#trust-model-output.
  Für den Proxy heißt das: Eine `content.video_url` aus einem früheren Task kann direkt als `reference_video` dienen
  (Edit/Extend). Innerhalb von 24 h geht das mit der Original-URL, danach nur nach eigener Sicherung.
* **Digital-Character-Bibliothek:** Vorgefertigte Charaktere mit eigener Asset-ID, die als `asset://<ASSET_ID>` in
  `image_url.url` übergeben werden. Freigeschaltet wird sie per Zustimmung im Playground. Es gibt auch Assets ohne Porträt.
  Quellen: avatar-library, seedance-portrait-asset-guide#preset-avatar.
* **Autorisierte Real-Person-Assets:** QR-Flow mit Liveness-Check im Playground. Die Assets landen in einer privaten
  Asset-Gruppe und werden ebenfalls als `asset://…` in `image_url`, `video_url` oder `audio_url` verwendet.
  Quelle: upload-real-person-portrait-assets. Der Proxy deckt das bereits über die Asset-API ab (`real_human=true`).
* **Copyrighted-IP-Templates:** **Nur im Playground**, kein API-Feld. Quelle: generate-copyright-video.
* **Badcase-Report-API** (`CasePlatformV1BadcaseReport` und `…Query` unter
  `https://prompt-pilot.ap-southeast.bytepluses.com/case-platform`): Damit lassen sich Seedance-2.x-Task-IDs als
  Qualitätsfall melden. Vorher muss „Model Generations Quality Diagnostics“ aktiviert werden. Quelle: 2389900. Optional.
* **[Volcengine] `tools: [{type:"web_search"}]`:** Websuche für 2.5 und 2.0. Auf BytePlus nicht dokumentiert.

### 9.1 Seedance-relevante Fehlercodes

Quelle: https://docs.byteplus.com/en/docs/ModelArk/error-codes.

* `InvalidParameter.TaskTypeConstraint` und `InvalidParameter.TaskTypeMismatch` (2.5, meist asynchron).
* `Input{Text,Image,Video,Audio}SensitiveContentDetected`, jeweils mit den Varianten `.PolicyViolation` (Copyright) und
  `.PrivacyInformation` (reale Person).
* `Output{Video,Audio}SensitiveContentDetected[.PolicyViolation]`.
* Für alle gilt HTTP 400 `BadRequest`. Rate-Limit-Überschreitungen liefern 429.

---

## 10. Ist-Zustand des Proxys (kurz)

Geprüfte Dateien: `src/modelark_proxy/providers/seedance.py`, `models.py`, `translation.py`, `schemas.py`, `app.py` und
`unified.py`.

* Durchgereichte Felder (`PASSTHROUGH_FIELDS`): `resolution`, `ratio`, `duration`, `frames`, `output_format`,
  `omni_reference_task_type`, `generate_audio`, `watermark`, `camera_fixed`, `return_last_frame`, `seed`, `service_tier`,
  `execution_expires_after`, `priority`, `callback_url` und `safety_identifier`. Rohes `content[]` wird angehängt,
  `asset://` darin jedoch abgelehnt.
* Rollen: `reference_image`, `first_frame` und `last_frame` (Bild), `reference_video` und `reference_audio`.
* Validierung: Auflösung, Verhältnis und Dauer pro Modell; Referenzzahl; Audio braucht ein Bild oder Video
  (außer bei 2.5); Frame- und Referenzrollen werden nicht gemischt; `last_frame` nur zusammen mit `first_frame`;
  2.5 `adaptive` und `-1` bei Edit/Extend/I2V; `output_format` und `omni_reference_task_type` nur bei 2.5;
  `frames` nur bei 1.0.
* [Code] Offline geprüft: `build_task_payload` ignoriert `references`, `task`, `aspect_ratio`, `draft` und `tools`
  stillschweigend. `seconds:"auto"` führt zu einem 400er. `seed=4000000000`, `priority=12` und `service_tier=flex` gehen
  bei 2.0 ungeprüft durch. `generate_audio:true` wird immer gesetzt, auch bei 1.0 pro und bei Draft-Final-Tasks.

---

## 11. Lückenanalyse und Empfehlungen

Priorität: **H** = falsches Verhalten oder blockierte Funktion, **M** = fehlendes Feature, **L** = Komfort oder Doku.

| # | Bereich | Befund (Proxy vs. API) | Prio | Empfehlung |
|---|---|---|---|---|
| 1 | Einheitlicher Vertrag | `SeedanceProvider.create_video` ruft `build_task_payload` mit Altfeldern auf. `references`, `task`, `aspect_ratio` werden **nicht** ausgewertet [Code]. Die Capability-v2-Doku bewirbt trotzdem `aspect_ratio`, die Tasks `edit`, `extend` und `stitch` sowie `base_video`. Folge: `/v1/videos/edits`, `/v1/videos/extensions` und `/remix` liefern für Seedance `references=[{task_id, role:"base_video"}]`, und daraus wird stillschweigend ein **reiner Text-to-Video-Task** | **H** | Seedance wie Kling/Google auf `normalize_request` und `validate` umstellen. Abbildung: `task` → Rollen und `omni_reference_task_type` (`edit`/`extend`/`reference`; `stitch` → `extend` bzw. `auto`); `base_video` → `reference_video` mit der aufgelösten `video_url` des Quell-Tasks (Trusted Output, §9); `aspect_ratio` → `ratio`; `seconds:"auto"` → `duration:-1`. Die Altfelder bleiben gültig |
| 2 | Draft-Modus | `draft` fehlt in `PASSTHROUGH_FIELDS` und wird verworfen. `content[].draft_task` ist nur über rohes `content` möglich. Dann setzt der Proxy aber `generate_audio` (und ggf. `ratio` über `size`) zusätzlich, was bei 2.5 laut Doku **immer einen Fehler** auslöst | **H** | `draft` durchreichen; nur 2.5 und 1.5 pro, nur `resolution=480p`. Ein eigenes Feld bzw. eine Referenz `draft_task_id` (Task-ID) → `{"type":"draft_task","draft_task":{"id":…}}`. In diesem Modus **keine** übernommenen Felder setzen (`generate_audio`, `ratio`, `duration`, `seed`, `omni_reference_task_type`, Texte und Referenzen ablehnen). Bei 2.5 `resolution` auf `1080p` erzwingen. Capability `features.draft` pro Modell |
| 3 | `generate_audio`-Default | `payload.setdefault("generate_audio", …)` gilt für jedes Modell. 1.0 pro und pro fast unterstützen das Feld laut Doku nicht (strenge Validierung) | **H** | Nur bei 2.5, der 2.0er-Serie und 1.5 pro setzen. Im Capability-Dokument `generate_audio` nur für diese Modelle ausweisen |
| 4 | `seed` | Capability-Bereich `[-1, 4294967295]`; die API erlaubt `[-1, 2147483647]`. Laut Feldliste nur für 1.x dokumentiert | **H** | Maximum auf 2147483647 korrigieren. Pro Modell ausweisen: 1.x sicher, 2.x unklar (§12). Nicht hart ablehnen, solange unklar |
| 5 | Default-Dauer 2.5 | `default_duration=5`; die API-Vorgabe ist `-1` | M | `default_duration=-1` (`"auto"`) für `dreamina-seedance-2-5` |
| 6 | `ratio` für 1.0 | `adaptive` wird bei 1.0 pro/pro fast auch für Text-to-Video akzeptiert, die API erlaubt dort nur feste Verhältnisse. Der Default wird pauschal mit `16:9` angegeben, die API nimmt bei I2V `adaptive` | M | Constraint: 1.0 + T2V verbietet `adaptive`. Default abhängig vom Task |
| 7 | `camera_fixed` | Keine Prüfung. Laut Doku nur 1.5 pro und 1.0, nicht bei Referenzbildern | M | Pro Modell validieren und in den Capabilities nur für 1.x ausweisen |
| 8 | `priority` / `service_tier` | Kein Bereichs- oder Modellcheck. `priority` erlaubt `[0,9]` und nur 2.x. `flex` gibt es nur für 1.x und nicht zusammen mit `priority` | M | Validieren (`priority` 0–9 nur 2.x; `service_tier ∈ {default, flex}`, `flex` nur 1.x, nicht mit `priority`) |
| 9 | `execution_expires_after` | Kein Bereichscheck `[3600, 259200]` | L | Validieren |
| 10 | `safety_identifier` | Wird aus `user` übernommen, aber ohne Längenprüfung (≤ 64) | L | Längere Werte hashen (z. B. SHA-256 hex = 64 Zeichen), statt die Anfrage scheitern zu lassen |
| 11 | `frames` | Wird nur pro Modell geprüft. Format `25+4n` in `[29,289]` wird nicht geprüft | L | Wert validieren und `frames` in den Capabilities von 1.0 als Parameter führen |
| 12 | Base64-Eingaben | `_validate_public_reference_url` erlaubt nur http(s). Die API nimmt `data:image/…;base64` und `data:audio/…;base64`, für Video nicht | M | `data:`-URIs für Bild und Audio zulassen (Größenlimits beachten: Bild < 30 MB, Audio ≤ 15 MB, Body ≤ 64 MB). Alternativ wie bisher Upload in den Media-Store |
| 13 | Öffentliche Asset-IDs | `asset://` und `asset_id` werden abgelehnt (`_reject_public_asset_references`). Damit sind die **Digital-Character-Bibliothek** und Plattform-Assets nicht nutzbar | M | Explizit erlaubte Quelle `asset_id` (`asset-…`) für Seedance 2.x/2.5, gemappt auf `asset://…` mit Typ und Rolle aus der Referenz. Die internen Real-Human-Assets bleiben wie bisher |
| 14 | Referenzlängen 2.5 Edit | Für die Clip-Länge gilt überall ein Minimum von 2 s; bei 2.5-Edit sind es 4–30 s | L | Task-spezifisches `min_seconds=4` für `edit` bei 2.5 |
| 15 | Antwortfelder | `byteplus_to_openai` verwirft `seed`, `frames`, `framespersecond`, `ratio`, `resolution` (nur indirekt über `size`), `output_format`, `generate_audio`, `draft`, `draft_task_id`, `priority`, `execution_expires_after` und `safety_identifier` | M | Als Zusatzfelder ausgeben (`VideoObject` erlaubt `extra`). Mindestens `seed`, `draft`, `draft_task_id`, `output_format`, `resolution`, `ratio` und `duration`/`frames` |
| 16 | `size`-Mapping | `FORMAT_TO_SIZE` nutzt die 2.0-Pixelmaße. 2.5 480p sind 854×480, 1.0 720p sind 1248×704 usw. Damit meldet `size` für 2.5 und 1.0 teils falsche Pixel | L | Pixeltabelle pro Familie (§2.4) und eingehende `size` tolerant auf (Auflösung, Verhältnis) abbilden |
| 17 | List | `filter.service_tier` fehlt in `allowed`. `page_num` ist nicht auf ≤ 500 begrenzt. Die List-API hat nur **1 QPS** | M | `filter.service_tier` ergänzen, `page_num` ≤ 500 prüfen, gegebenenfalls ein 1-QPS-Throttle für List |
| 18 | DELETE | Der Proxy setzt pauschal `status: "cancelled"`, auch wenn ein abgeschlossener Task **gelöscht** wurde. Ein `running`-Task kann nicht abgebrochen werden (Upstream-Fehler) | L | Vorher den Status lesen (oder den Upstream-Fehler mappen): `queued` → `cancelled`, sonst `deleted: true`. Für `running` eine klare 409 |
| 19 | Status `expired` | Wird auf `failed` mit `task_expired` gemappt. Das ist korrekt; `provider_status` bleibt erhalten | – | – |
| 20 | Modelltabelle | `seedance-1-5-pro` ist **Retired** und wird am 11.11.2026 abgeschaltet. 1.0 lite fehlt richtigerweise. Alte IDs mit Präfix `bytedance-` werden von `family_name` nicht normalisiert | M | 1.5 pro als `deprecated` mit `shutdown_at=2026-11-11T09:00:00Z` und Ersatz `dreamina-seedance-2-0-mini` markieren; ab dann aus `/v1/models` nehmen. Optional das Präfix `bytedance-` entfernen |
| 21 | Rate Limits | Die 4K-Grenzen bei 2.0 (RPM 15, Concurrency 1) und die Account-Limits stehen nicht im Capability-Dokument | L | Als Info-Feld `rate_limits` ausgeben; 4K mit Hinweis |
| 22 | `tools` / `web_search` | Nicht durchgereicht. Auf BytePlus nicht dokumentiert, nur [Volcengine] | L | Nicht einbauen, solange BytePlus es nicht dokumentiert. Höchstens als optionales natives Feld mit einem kostenpflichtigen Live-Test (nur mit Freigabe) |
| 23 | Callback | `callback_url` wird roh durchgereicht. Der ModelArk-Callback ist unsigniert, der eigene `webhook_url`-Mechanismus existiert bereits | L | `callback_url` dokumentieren als „unsigniert, Body = GET-Antwort, Status inkl. `expired`, 3 Retries bei Endzuständen“. Für Clients `webhook_url` empfehlen |
| 24 | `stitch`-Task | Die Capabilities bieten `stitch` bei 2.x und 2.5 an; die API kennt das nur als Extend per Prompt | L | `stitch` → `omni_reference_task_type=extend` (2.5) bzw. reine `reference_video`-Liste (2.0). Doku-Hinweis, dass der Prompt den Übergang beschreiben muss |
| 25 | Bildformate | Erlaubt sind heic und heif ab 1.5 pro sowie bmp, tiff und gif. Ob der Media-Store diese MIME-Typen annimmt, wurde nicht geprüft | L | MIME-Whitelist des Media-Stores mit §2.3 abgleichen |

Vollständig und korrekt abgedeckt sind: Auflösungen, Dauerbereiche und Referenzlimits pro Modell, `output_format` nur bei 2.5,
`omni_reference_task_type` samt synchroner Prüfung der `edit`/`extend`-Constraints, 2.5 First/Last-Frame mit `adaptive`,
Audio allein nur bei 2.5, `last_frame` nicht bei 1.0 pro fast, `frames` nur bei 1.0 sowie Last-Frame-Verkettung über
`input_reference_task_id`.

---

## 12. Unklar / nicht verifizierbar

1. **`seed` bei 2.x und 2.5:** Die Feldliste in Create nennt nur 1.5 pro, 1.0 pro und 1.0 pro fast. Die Draft-Tabelle von 2.5
   führt `seed` aber als „automatisch übernommenen“ Parameter, und die GET-Antwort liefert `seed` für jeden Task. Ob 2.x
   einen gesetzten `seed` annimmt, ignoriert oder ablehnt, klärt nur ein Live-Test (kostenpflichtig, nur mit Freigabe).
2. **`generate_audio` bei 1.0 pro/pro fast:** Laut Doku nicht unterstützt. Ob `generate_audio:true` dort zu einem Fehler
   führt oder ignoriert wird, ist unbelegt. Der aktuelle Proxy sendet es immer.
3. **`generate_audio` bei 1.5 pro:** BytePlus listet 1.5 pro als unterstützt, [Volcengine] nicht. Dort fehlt 1.5 pro in der
   Create-Doku allerdings ganz.
4. **Status `expired`** fehlt in der Statusliste von Get und List, taucht aber in Delete und Callback auf. Ob
   `filter.status=expired` funktioniert, ist nicht dokumentiert.
5. **Callback-Retries** sind nur für `succeeded`/`failed` dokumentiert, nicht für `expired`. Signatur und Header sind
   undokumentiert.
6. **Tabellen widersprechen sich:** Die Übersicht im Video-Tutorial nennt für 2.5 nur „MP4“ und ohne `adaptive`, Create, das
   2.5-Tutorial und Model list dagegen `mp4, mov` und `adaptive`. Ausgegangen wurde von Create, der neuesten Seite.
7. **`tools`/`web_search`** und `usage.tool_usage` sind nur bei [Volcengine] dokumentiert. Ob BytePlus das Feld annimmt, ist
   unbekannt.
8. **Pixelmaße bei 1.5 pro** sind in der Create-Tabelle mit denen der 2.0er-Serie identisch. Gemessen wurde das nicht.
9. **Mindest-Tokenmenge der 2.0er-Serie:** Sie wird erwähnt, aber nicht beziffert. Preise wurden nicht recherchiert
   (Seite `1544106`).
10. **Ein „2.5 fast“ oder „2.5 mini“** existiert laut Model list (Stand 28.09.2026) nicht. Ein neues Release erkennt der Proxy
    über `VERSION_SUFFIX` und den Fallback.
11. **Base64 bei Video** ist ausdrücklich nicht vorgesehen (nur URL oder Asset-ID). Getestet wurde das nicht.
12. Es wurde **kein Live-Request** ausgeführt (keine kostenpflichtige Generierung, keine biometrischen Daten). Alle Angaben
    stammen aus der Doku bzw. aus dem Lesen und Offline-Ausführen des Proxy-Codes.
