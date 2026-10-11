# API-Referenz

Der Vertrag mit allen Feldern, Tasks und Regeln steht in [SPEC.md](../SPEC.md).
Diese Seite beschreibt, was der Proxy auf dem Branch `feature/multi-provider`
anbietet.

## Authentifizierung

Ist `PROXY_API_KEY` gesetzt, erwarten alle Routen außer `/health` und
`/media/reference/<token>` (öffentliche Capability-URL für Anbieter-Abrufe):

```http
Authorization: Bearer <PROXY_API_KEY>
```

Fehler haben den OpenAI-Stil; `code` nennt die einheitliche Fehlerklasse:

```json
{"error":{"message":"…","type":"invalid_request_error","param":null,"code":"…"}}
```

Häufige Codes: `invalid_request`, `unsupported_task`, `unsupported_parameter`
(Feld oder Wert vom Modell nicht unterstützt, Meldung nennt die erlaubten
Werte), `reference_limit`, `reference_unavailable`, `public_base_url_required`,
`content_policy`, `model_unavailable` (404), `invalid_api_key` (401),
`upstream_credentials_invalid` / `upstream_credentials_unavailable` (503),
`upstream_forbidden`, `billing` (402), `rate_limited` (429), `upstream_error`
(502), `video_not_ready` (409), `video_running` (409, laufender Seedance-Task),
`output_expired` (410). Fehler im Video-Objekt (`error`) enthalten zusätzlich
gegebenenfalls `provider_code` und `retryable`.

## Endpunkte

Alle Pfade existieren zusätzlich ohne `/v1`-Präfix (nicht im OpenAPI-Schema),
außer den nativen Routen unter `/v1/providers/…`, `/v1/assets` und
`/v1/litellm/config`.

| Methode | Pfad | Funktion |
|---|---|---|
| `GET` | `/health` | Prozesszustand, Version, `credentials` (ModelArk) und `providers` (Zustand je Anbieter); bleibt auch bei ungültigen Zugängen HTTP 200 |
| `GET` | `/v1/models` | Modelle aller aktiven Anbieter mit Capability-Dokument und `links.prompt_guide` |
| `GET` | `/v1/models/{id}` | ein Modell plus `prompt_guide` mit Volltext |
| `GET` | `/v1/prompt-guides` | Liste der Guides |
| `GET` | `/v1/prompt-guides/{guide}` | Guide als `text/markdown`; mit `Accept: application/json` als Objekt mit `markdown` |
| `GET` | `/v1/litellm/config` | LiteLLM-`model_list` (`format=yaml\|json`, `api_base`, `name_template`) |
| `POST` | `/v1/media/references` | bis zu 50 temporäre Referenzdateien hochladen (Feld `files`) |
| `DELETE` | `/v1/media/references/{id}` | temporäre Referenz entfernen |
| `GET` | `/v1/real-human/configuration` | Assets-API und Gruppe read-only prüfen |
| `POST` | `/v1/videos` | Generierungstask erstellen (alle Modelle) |
| `GET` | `/v1/videos` | Jobs aller Anbieter auflisten und filtern |
| `GET` | `/v1/videos/{id}` | Status |
| `DELETE` | `/v1/videos/{id}` | Abbrechen bzw. löschen; Antwort stets `object: "video.deleted"`, `deleted: true` plus die bisherigen Videofelder (Verhalten je Anbieter: [Taskverwaltung](../taskverwaltung/README.md)) |
| `GET` | `/v1/videos/{id}/content` | Ergebnis streamen (`?variant=`, `?output=`, `?format=`) |
| `GET` | `/v1/videos/{id}/last_frame` | letztes PNG-Frame (nur Seedance) |
| `POST` | `/v1/videos/{id}/remix` | Ergebnis per Prompt bearbeiten (`task=edit`) |
| `POST` | `/v1/videos/edits` | Video bearbeiten (`video:{id}`) |
| `POST` | `/v1/videos/extensions` | Video verlängern (`video:{id}`) |
| `GET` `POST` | `/v1/assets` | Kling-Elements und -Voices auflisten (`provider`, `type`, `scope`) bzw. anlegen |
| `GET` `DELETE` | `/v1/assets/{id}` | Asset lesen bzw. löschen |
| `POST` | `/v1/providers/google/veo/{model}:predictLongRunning` | natives Veo-Create |
| `GET` | `/v1/providers/google/veo/operations/{id}` | native Veo-Operation |
| `POST` | `/v1/providers/google/interactions` | native Omni-Interaction (`background` und `store` erzwungen) |
| `GET` `DELETE` | `/v1/providers/google/interactions/{id}` | Interaction lesen bzw. löschen (wie `DELETE /v1/videos/{id}`) |
| `POST` | `/v1/providers/google/interactions/{id}/cancel` | Interaction abbrechen |
| `POST` `GET` | `/v1/providers/modelark/tasks` | natives Seedance-Create (rohes `content`) bzw. Liste |
| `GET` `DELETE` | `/v1/providers/modelark/tasks/{id}` | native Abfrage bzw. Löschen |
| `POST` | `/v1/videos/characters` | OpenAI-Character (Multipart `name`, `video`, optional `description`) als Kling-Video-Element |
| `GET` | `/v1/videos/characters/{id}` | Character lesen |
| `GET` | `/v1/providers/kling/effects` | Effekt-Katalog (219 Einträge: `id`, `name`, `images`) |
| `GET` `POST` | `/v1/providers/kling/{pfad}` | native Kling-Durchleitung |


## Modelle und Capabilities

`GET /v1/models` liefert je Modell `id`, `name`, `owned_by` (`modelark`, `google`,
`kling`), `virtual` (nur Kling-Werkzeuge), `links.prompt_guide` und
`capabilities`. Fällt ein Anbieter aus, fehlt er nur in der Liste.

`capabilities` ist das Dokument v2 (SPEC Abschnitt 13) und Grundlage von
Validierung, UI und LiteLLM-Export:

| Feld | Bedeutung |
|---|---|
| `schema_version`, `provider`, `backend`, `family`, `launch_stage` | Herkunft; `backend` ist `gemini` oder `vertex`; `launch_stage` z. B. `ga`, `preview`, `deprecated` |
| `prompt` | `max_chars`, `required` |
| `outputs` | `max` (Varianten, Veo auf Vertex 4) und `types` (`video`, `audio`) |
| `parameters` | modellweit erlaubte Werte (`values`, `min`, `max`, `default`) |
| `tasks.<task>` | `references` (Slots mit `role`, `types`, `min`, `max`, `max_bytes`, `formats`, Dauergrenzen), `parameters`, `limits`, `prompt_required` |
| `constraints` | bedingte Einschränkungen (`if` → `then`, `message`) |
| `continuation` | `last_frame`, `video_extension`, `multi_turn` oder `none` |
| `features` | z. B. `real_human`, `last_frame_output`, `watermark`, `callback`, `draft` |
| `provider_options` | erlaubte Schlüssel in `provider_options.<anbieter>` |
| `native_fields` | zusätzlich zulässige Anbieterfelder auf oberster Ebene |
| `deprecation` | `shutdown_at`, `replacement` (nur bei angekündigter Abschaltung) |

Seedance-Modelle liefern zusätzlich die Felder des früheren Dokuments (v1):
`resolutions`, `ratios`, `durations` (`-1` = automatisch), `defaults`,
`reference_limits`, `reference_audio_requires_visual`, `reference_media_seconds`,
`output_formats`, `task_types`, `supports_frames`, `supports_last_frame_role`,
`adaptive_ratio_for_frames`.

Seedance 1.5 Pro trägt `launch_stage: "deprecated"` mit
`deprecation.shutdown_at = 2026-11-11T09:00:00Z` und dem Nachfolger
`dreamina-seedance-2-0-mini`. Modelle, die der Proxy nicht kennt, werden
weiterhin aufgelistet und nicht lokal eingeschränkt; ihre Validierung übernimmt
dann der Anbieter.

## GET `/v1/real-human/configuration`

Führt ohne Videogenerierung einen signierten, read-only `ListAssetGroups`-Aufruf
aus und bestätigt, ob AK/SK, Projekt und konfigurierte Asset-Gruppe zusammenpassen.
Ohne Konfiguration antwortet der Aufruf mit `{"configured": false, "verified": false}`.
Geheimnisse werden nicht zurückgegeben. Der Aufruf ist der empfohlene erste Test
nach einem Serverstart.

## POST `/v1/videos`

Der Endpunkt akzeptiert JSON oder `multipart/form-data`. Strukturierte Felder
(`references`, `shots`, `provider_options`, `speech`, `audio`, `commerce`,
`selections`, `reference_urls`, `content`) werden als JSON-Wert, als JSON-String
oder in Multipart-Klammernotation (`references[][url]=…`) angenommen. Boolesche
und ganzzahlige Felder aus Formularen oder JSON-Strings (LiteLLM < 1.100) typt
der Proxy (`generate_audio`, `watermark`, `camera_fixed`, `return_last_frame`,
`real_human`, `enhance_prompt`, `duration`, `frames`, `seed`, `priority`,
`execution_expires_after`, `n`). Ein Objekt `extra_body` wird flach eingemischt;
Felder auf oberster Ebene haben Vorrang.

### Einheitliche Felder

| Feld | Typ | Bedeutung |
|---|---|---|
| `model` | string | Modell-ID; Präfixe `openai/`, `google/`, `kling/`, `modelark/` werden entfernt |
| `prompt` | string | Textanweisung |
| `task` | string | optional; sonst aus Referenzrollen und Feldern abgeleitet |
| `references` | object[] | Eingaben: `type`, `role`, genau eine Quelle (`url`, `upload_id`, `task_id`, `asset_id`), `output`, `name`, `real_human` |
| `seconds` / `duration` | int, float oder `"auto"` | Dauer; `"auto"` und `-1` bedeuten automatisch (Seedance) |
| `size` | string | `BREITExHÖHE`; wird zu `resolution` und `aspect_ratio` |
| `resolution`, `aspect_ratio` (Alias `ratio`) | string | Ausgabeformat |
| `negative_prompt`, `seed`, `generate_audio`, `watermark`, `quality`, `n` | – | je nach Modell laut `capabilities.parameters` |
| `shots`, `shot_mode`, `effect`, `speech`, `audio`, `selections`, `edit_mode`, `commerce` | – | task-spezifische Felder, siehe [Video-Generierung](../video-generierung/README.md) |
| `enhance_prompt`, `person_generation` | – | Veo |
| `output_format`, `return_last_frame` | – | Seedance |
| `parameter_policy` | `strict` \| `adapt` | Standard aus `DEFAULT_PARAMETER_POLICY` (`strict`); `adapt` passt Werte an und meldet `adjustments[]` |
| `provider_options` | object | Anbieterfelder, nur der Block des Zielmodells zählt |
| `webhook_url` | string | HTTPS-Ziel für signierte Statusereignisse (braucht `WEBHOOK_SECRET`; der Host muss öffentlich auflösen, sonst 400) |
| `user` | string | wird bei Seedance zu `safety_identifier` |
| `metadata` | object | wird gespeichert (nur Direktaufrufe) |
| `input_reference` | file | Multipart-Datei, Typ ausschließlich über die Dateisignatur bestimmt; Google und Kling lehnen sie ab, `references` nutzen |

Bei einheitlichen Requests führen Felder, die der Anbieter nicht kennt, zu
`400 unsupported_parameter`; bei `parameter_policy: "adapt"` werden sie verworfen und unter `adjustments`
vermerkt. Die Modell-Validierung findet vor dem Upstream-Aufruf statt; ein
unpassender Wert ergibt HTTP 400 statt einer Task-ID.

Der Standard ergibt sich aus `DEFAULT_PARAMETER_POLICY` (`strict` oder `adapt`, Standard
`strict`) und gilt für alle Anbieter.

### Seedance-Altfelder

Diese Felder bleiben gültig. Ein Request gilt als „einheitlich“, sobald er
`references`, `task`, `aspect_ratio`, `parameter_policy` oder `seconds: "auto"`
enthält; sonst läuft er unverändert über den bisherigen Pfad.

| Feld | Bedeutung |
|---|---|
| `input_reference_url`, `input_reference_media_type`, `input_reference_role` | eine öffentliche Referenz |
| `reference_urls` | URLs (String oder Objekt mit `url`, `media_type`, `role`, `real_human`) |
| `real_human` | Multipart-Einzelreferenz als Real-Human-Asset registrieren |
| `content` | rohes ModelArk-Content-Array (nur ModelArk) |
| `input_reference_task_id` | letztes Frame eines früheren Tasks als First-Frame |
| `omni_reference_task_type` | `auto`, `reference`, `edit`, `extend` (nur 2.5); `auto` = Ableitung |
| `ratio`, `resolution`, `duration`, `frames`, `output_format`, `generate_audio`, `watermark`, `camera_fixed`, `return_last_frame`, `seed` | direkt an ModelArk |
| `service_tier`, `execution_expires_after`, `priority`, `callback_url`, `safety_identifier` | ModelArk-Felder |
| `draft`, `draft_task_id` | Draft-Modus |

Real-Human: `real_human: true` an einem Nicht-Seedance-Modell ergibt
`400 unsupported_parameter` (`param: real_human`).

Asset-IDs: In `references[]` ist `asset_id` mit einer öffentlichen ModelArk-ID
(`asset-…`, wird zu `asset://asset-…`) erlaubt. Die Altfelder `asset_id`,
`input_reference_asset`, `input_reference_asset_type`, `reference_asset_ids`,
`reference_assets` sowie `asset://`-URIs in `content` werden mit HTTP 400
abgewiesen; die temporäre ID einer Real-Human-Registrierung bleibt intern.

Seedance-Prüfungen vor dem Upstream-Aufruf (Details in
[Video-Generierung](../video-generierung/README.md#seedance-regeln)):

- `generate_audio` nur bei Modellen mit Audio (nicht bei 1.0 Pro und 1.0 Pro Fast)
- `camera_fixed` nur bei 1.x und nicht mit Referenzbildern
- `priority` 0–9, nur bei 2.x, nicht mit `service_tier=flex`
- `service_tier` `default` oder `flex` (`flex` nur bei 1.x)
- `execution_expires_after` 3600–259200
- `frames` = 25 + 4n im Bereich 29–289, nur bei Modellen mit Frames
- `safety_identifier` über 64 Zeichen wird als SHA-256 gehasht
- `ratio: "adaptive"` bei 1.0 Pro nur mit Eingabebild
- `callback_url` wird unverändert an ModelArk gereicht und ist **unsigniert**;
  für authentische Benachrichtigungen `webhook_url` verwenden

### Antwort

Der Create-Endpunkt ist asynchron: Die Antwort bestätigt die Annahme, nicht die
Fertigstellung. Ein Client pollt `GET /v1/videos/{id}`, bis `status` gleich
`completed` oder `failed` ist.

```json
{
  "id": "video_bGl0ZWxsbTpj…",
  "object": "video",
  "status": "queued",
  "created_at": 1786040000,
  "progress": 0,
  "seconds": "5",
  "size": "1280x720",
  "model": "dreamina-seedance-2-0-fast-260128"
}
```

Die `id` hat das LiteLLM-Format `video_<base64>`; der Proxy akzeptiert diese und
die interne Form (`cgt-…`, `video-rh-…`, `vid-<anbieter>-<uuid>`). Weitere Felder:

| Feld | Quelle | Bedeutung |
|---|---|---|
| `provider_status` | alle | genauer Anbieterzustand (z. B. `running`, `face_identification`) |
| `provider`, `task`, `outputs[]`, `adjustments[]`, `last_frame_available`, `metadata` | lokales Register | nur bei Direktaufrufen sichtbar (LiteLLM verwirft unbekannte Felder) |
| `usage` | alle | Anbieter, Backend und, soweit bekannt, Verbrauch |
| `seed`, `resolution`, `ratio`, `frames`, `framespersecond`, `output_format`, `generate_audio`, `draft`, `draft_task_id`, `priority`, `execution_expires_after`, `safety_identifier`, `service_tier` | Seedance | von ModelArk zurückgemeldete Einstellungen des Tasks |
| `deleted` | alle | `true` in der `DELETE`-Antwort (zusammen mit `object: "video.deleted"`) |

Statusabbildung (SPEC 11.2): ModelArk `queued → queued`, `running → in_progress`,
`succeeded → completed`; `failed`, `cancelled` und `expired` erscheinen als
`failed`.

## GET `/v1/videos`

Ohne Altparameter vereint die Liste ModelArk-Tasks (die ersten 100) und das lokale
Jobregister (Google, Kling) und sortiert nach `created_at`. Parameter:

| Parameter | Bedeutung |
|---|---|
| `limit` | 1–100, Standard 20 |
| `after` | ID des letzten Eintrags der vorigen Seite (kodiert oder intern) |
| `order` | `desc` (Standard) oder `asc` |
| `model`, `status`, `provider` | Filter (`provider`: `modelark`, `google`, `kling`) |

Die Antwort enthält `object: "list"`, `data`, `first_id`, `last_id`, `has_more`
und `warnings[]` (`{provider, message}`) für Anbieter, die gerade ausfallen; die
übrigen Einträge kommen trotzdem.

Sobald `page_num`, `page_size` oder ein `filter.*`-Parameter vorkommt, verhält sich
die Route wie bisher und listet ausschließlich ModelArk-Tasks mit ModelArk-Paging:
`page_num` (1–500), `page_size` (1–500, Alias `limit`), `filter.status`,
wiederholtes `filter.task_ids`, `filter.model`, `filter.service_tier`. Die Antwort
enthält dann `total`, Seitendaten und – wenn berechenbar – `has_more`.

```bash
curl -H "Authorization: Bearer $PROXY_KEY" \
  'http://127.0.0.1:8081/v1/videos?limit=20&provider=kling&order=desc'
```

LiteLLM leitet die Liste nicht weiter (400).

## GET `/v1/videos/{id}/content`

| `variant` | Inhalt |
|---|---|
| `video` (Standard) | Hauptergebnis (`video/mp4` oder `video/quicktime`) |
| `audio` | Tonspur bzw. Audio-Ergebnis (`audio/mpeg`; `format=wav` für WAV, falls vorhanden) |
| `watermarked` | Kling-Version mit Wasserzeichen, falls vorhanden |
| `last_frame` | wie `/last_frame` (nur Seedance) |
| `product_image_n`, `model_image_n` | Ergebnisbilder von Kling-Apparel |
| `thumbnail`, `spritesheet` | `400 unsupported_parameter` |

`output` wählt bei mehreren Varianten (`n` > 1) das Ergebnis. Vorhandene
Varianten stehen je Ausgabe unter `outputs[].variants`.

Die Plattform erzeugt nur Video: Es gibt keine Route für reine Audio-Erzeugung
(`/v1/audio/speech` ist entfernt). Kling-TTS läuft nur intern für `speech.text` bei
Lip Sync und Avatar.

## Assets

`/v1/assets` verwaltet Kling-Elements und -Voices; für andere Anbieter ist die
Route nicht verfügbar (Seedance-Real-Human-Assets laufen pro Request über
`real_human`).

| Aufruf | Bedeutung |
|---|---|
| `GET /v1/assets?provider=kling&type=element\|voice&scope=custom\|preset` | Liste; jedes Asset hat `id`, `type`, `name`, `status` (`ready`, `processing`, `failed`) |
| `POST /v1/assets` | anlegen: `type`, `name` (≤ 20 Zeichen), `references`; Element zusätzlich `description` (≤ 100 Zeichen) und optional `voice`, `tags` |
| `GET /v1/assets/{id}` / `DELETE` | lesen / löschen (nur fertige Assets) |

IDs: `asset-kling-element-<id>` und `asset-kling-voice-<id>`; während der
Erstellung gilt `asset-kling-element-task-<task>`. Ein Element braucht entweder
genau ein Video oder ein Frontalbild (Rolle `frontal`) plus 1–3 weitere Bilder;
eine Voice genau ein Audio oder Video. Verwendung in `references`:
`{"type":"element","asset_id":"asset-kling-element-…"}`.

### OpenAI-Characters

`POST /v1/videos/characters` (Multipart `name`, `video`, optional `description`)
legt ein Kling-Video-Element an; nötig sind Kling und `PUBLIC_BASE_URL`. Die
Antwort hat `object: "character"`, `id`, `name`, `status`. Die ID hat das Format
`character_<base64>` und umhüllt `char-kling-element-…`; beide Formen werden
angenommen, auch als `asset_id` in `references[]`. `GET /v1/videos/characters/{id}`
liefert den aktuellen Status. Über LiteLLM funktioniert die Anlage; es sendet nur
`name` und `video`.

## Native Routen

- **Google:** `POST /v1/providers/google/veo/{model}:predictLongRunning` nimmt den
  nativen Veo-Body (`instances`, `parameters`) und liefert die native Antwort plus
  `proxy: {id, status_url}`. `GET …/veo/operations/{id}` gibt die native Operation
  zurück.
- **Google Interactions:** `POST /v1/providers/google/interactions` nimmt den
  nativen Omni-Body (`background` und `store` erzwingt der Proxy, bei der Gemini
  API zusätzlich `delivery: uri`) und antwortet nativ plus `proxy: {id, status_url}`.
  `GET …/{id}` liefert die native Interaction, `POST …/{id}/cancel` bricht ab,
  `DELETE …/{id}` verhält sich wie `DELETE /v1/videos/{id}`.
- **ModelArk:** `POST /v1/providers/modelark/tasks` nimmt ein rohes ModelArk-Body
  mit `content`-Array (Upload-IDs und `data:`-Videos werden zu öffentlichen URLs,
  `data:`-Bilder/-Audio gehen unverändert durch) und antwortet nativ plus
  `proxy: {id, status_url}`. `GET …/tasks` listet (native Query-Parameter),
  `GET`/`DELETE …/tasks/{id}` fragen bzw. löschen nativ.
- **Kling:** `/v1/providers/kling/{pfad}` leitet dokumentierte Kling-Pfade durch
  (`v1/videos/…`, `v1/audio/video-to-audio`, `v1/general/…`, `text-to-video/…`,
  `image-to-video/…`, `omni-video/…`, `motion-control/…`, `tasks`, `solutions`,
  `account/costs`, höchstens ein Aufruf pro `KLING_COSTS_MIN_INTERVAL_SECONDS`, Standard 1 s: der Proxy wartet). `solutions/virtual_try_on` und alle anderen Pfade ergeben 404.
  Erzeugte Video-Tasks werden registriert und antworten mit `proxy: {id, status_url}`.

Native Ergebnisse sind über `/v1/videos/{id}` und `/content` abrufbar.

## Temporäre Medien-API

`POST /v1/media/references` akzeptiert bis zu 50 Multipart-Dateien im Feld
`files`. Die Antwort enthält je Datei `id`, öffentliche `url`, `media_type`,
`kind`, ursprünglichen Dateinamen und `expires_at`. Bild-, Video- und
Audiolimits werden nach erkannter Dateisignatur geprüft (Bild 30 MB, Video
200 MB, Audio 15 MB). Für den Endpunkt ist `PUBLIC_BASE_URL` erforderlich.

```bash
curl -X POST http://127.0.0.1:8081/v1/media/references \
  -H "Authorization: Bearer $PROXY_KEY" \
  -F 'files=@reference.png' \
  -F 'files=@motion.mp4' \
  -F 'files=@sound.mp3'
```
