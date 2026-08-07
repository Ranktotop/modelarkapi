# API-Referenz

## Modelle

`GET /v1/models` liefert ausschließlich die im BytePlus-Konto als verfügbar
gemeldeten Seedance-Modelle einschließlich veröffentlichter Versions-ID,
Anzeigename und modellabhängiger `capabilities` für Auflösung,
Seitenverhältnis und Dauer. Der Abruf ist read-only und wird serverseitig
kurzzeitig zwischengespeichert.

## Authentifizierung

Ist `PROXY_API_KEY` gesetzt, erwarten alle `/v1`-Routen:

```http
Authorization: Bearer <PROXY_API_KEY>
```

Fehler werden im OpenAI-Stil zurückgegeben:

```json
{"error":{"message":"…","type":"invalid_request_error","param":null,"code":"…"}}
```

## Endpunkte

| Methode | Pfad | Funktion |
|---|---|---|
| `GET` | `/health` | Prozesszustand und letzter Credential-Check; bleibt auch bei ungültigen Upstream-Zugängen HTTP 200 |
| `POST` | `/v1/media/references` | temporäre Referenzdateien hochladen |
| `DELETE` | `/v1/media/references/{id}` | temporäre Referenz entfernen |
| `GET` | `/v1/real-human/configuration` | Assets-API und Gruppe read-only prüfen |
| `POST` | `/v1/videos` | Generierungstask erstellen |
| `GET` | `/v1/videos` | Tasks auflisten und filtern |
| `GET` | `/v1/videos/{id}` | Taskstatus lesen |
| `DELETE` | `/v1/videos/{id}` | Task abbrechen oder Datensatz löschen |
| `GET` | `/v1/videos/{id}/content` | fertiges MP4 streamen |
| `GET` | `/v1/videos/{id}/last_frame` | optionales letztes PNG-Frame streamen |

Die gleichen Routen ohne `/v1` existieren für die Kompatibilität, werden aber
nicht im OpenAPI-Schema angezeigt.

## GET `/v1/real-human/configuration`

Führt ohne Videogenerierung einen signierten, read-only `ListAssetGroups`-
Aufruf aus und bestätigt, ob AK/SK, Projekt und konfigurierte Asset-Gruppe
zusammenpassen. Geheimnisse werden nicht zurückgegeben.

## POST `/v1/videos`

Der Endpunkt akzeptiert JSON oder `multipart/form-data`.

| Feld | Typ | Bedeutung |
|---|---|---|
| `model` | string | Alias, Modell-ID oder Endpoint-ID |
| `prompt` | string | Textanweisung |
| `seconds` | string/int | OpenAI-Dauer; wird zu `duration` |
| `size` | string | OpenAI-Größe; wird zu Auflösung und Seitenverhältnis |
| `input_reference` | file | eine lokale Bild- oder MP4/MOV-Referenz |
| `input_reference_url` | string | eine öffentliche Referenz-URL |
| `input_reference_media_type` | string | `image`, `video`, `audio` oder MIME-Typ |
| `input_reference_role` | string | `first_frame`, `last_frame` oder passende Referenzrolle |
| `reference_urls` | string[]/object[] | URLs, optional mit `media_type` und `role` |
| `real_human` | boolean | Multipart-Einzelreferenz temporär als Real-Human-Asset registrieren |
| `content` | object[] | fortgeschrittenes ModelArk-Content-Array |
| `user` | string | OpenAI-Nutzerkennung; wird zu `safety_identifier` |
| `input_reference_task_id` | string | letztes Frame eines früheren Tasks als First-Frame |

Ein Objekt in `reference_urls` kann zusätzlich `real_human: true` enthalten.
Der Create-Endpunkt gibt dann sofort eine lokale `video-rh-…`-ID zurück,
registriert die Referenz im Hintergrund und verwendet nach `Active` die
temporäre Asset-ID. Status, Download und Löschen verwenden weiterhin dieselben
`/v1/videos/{id}`-Routen.

Asset-IDs sind ein internes Implementierungsdetail. Die Felder `asset_id`,
`input_reference_asset`, `reference_asset_ids` und `reference_assets` sowie
`asset://`-URIs in `content` werden mit HTTP 400 abgewiesen.

Direkt weitergereichte Optionen:

`resolution`, `ratio`, `duration`, `frames`, `generate_audio`, `watermark`,
`camera_fixed`, `return_last_frame`, `seed`, `service_tier`,
`execution_expires_after`, `priority`, `callback_url`, `safety_identifier`.
ModelArk prüft, ob das gewählte Modell die jeweilige Option unterstützt.

Beispielantwort:

```json
{
  "id": "cgt-…",
  "object": "video",
  "status": "queued",
  "created_at": 1786040000,
  "progress": 0,
  "seconds": "5",
  "size": "1280x720",
  "model": "dreamina-seedance-2-0-fast-260128"
}
```

## GET `/v1/videos`

Unterstützte Query-Parameter: `page_num`, `page_size` (oder OpenAI-Alias
`limit`), `filter.status`, wiederholtes `filter.task_ids` und `filter.model`.
Unbekannte Parameter werden nicht an ModelArk weitergereicht.

```bash
curl -H "Authorization: Bearer $PROXY_KEY" \
  'http://localhost:8080/v1/videos?page_num=1&page_size=20&filter.status=succeeded'
```

Die Antwort enthält `object: "list"`, `data`, `total`, Seitendaten und – wenn
berechenbar – `has_more`.

## Statusobjekt

ModelArk wird wie folgt abgebildet: `queued → queued`,
`running → in_progress`, `succeeded → completed`; `failed`, `cancelled` und
`expired` erscheinen als `failed`. Die Erweiterungen `provider_status`,
`last_frame_available` und `service_tier` erhalten zusätzliche Details.

## Temporäre Medien-API

`POST /v1/media/references` akzeptiert bis zu 15 Multipart-Dateien im Feld
`files`. Die Antwort enthält je Datei `id`, öffentliche `url`, `media_type`,
`kind`, ursprünglichen Dateinamen und `expires_at`. Bild-, Video- und
Audiolimits werden nach erkannter Dateisignatur geprüft. Für den Endpunkt ist
`PUBLIC_BASE_URL` erforderlich.

```bash
curl -X POST http://localhost:8080/v1/media/references \
  -H "Authorization: Bearer $PROXY_KEY" \
  -F 'files=@reference.png' \
  -F 'files=@motion.mp4' \
  -F 'files=@sound.mp3'
```
