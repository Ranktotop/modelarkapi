# Recherche: OpenAI-Videos-API, LiteLLM-Proxy und Auslieferung von Prompt-Guides

Stand: 2026-10-11. Gegenstand: Wie verhalten sich die OpenAI-Videos-API und LiteLLM
(Modelle vom Typ `openai/<model>` mit eigener `api_base`) gegenüber unserem Proxy,
und wie kommen erweiterte Fähigkeiten und Prompt-Guides zuverlässig zu den Client-Apps?

Methodik:

- Primärquellen: OpenAI-Referenz und -Guide (developers.openai.com, weil
  platform.openai.com HTTP 403 liefert), LiteLLM-Doku, LiteLLM-Quellcode
  **v1.95.0** (im Repo-venv installiert: `.venv/lib/python3.14/site-packages/litellm/`)
  und **v1.105.0** (aktuelles PyPI-Release, Wheel separat entpackt), GitHub-Issues und -PRs.
- **Empirische Tests:** Beide LiteLLM-Versionen liefen als echter Proxy
  (`litellm --config`, Ports 4099/4105, isolierte Scratch-venvs) vor einem Mock-Upstream,
  der jede eingehende Anfrage protokollierte. Kein echter Provider, keine kostenpflichtige
  Generierung. Ergebnisse aus diesen Tests sind mit **[Test]** markiert.
- Die Code-Zeilenangaben beziehen sich auf v1.95.0, sofern nichts anderes dasteht.
  GitHub-Permalinks haben die Form
  `https://github.com/BerriAI/litellm/blob/v1.95.0/<pfad>#L<n>`.

---

## 0. Kernaussagen

1. **Die OpenAI-Videos-API gibt es nicht mehr.** Sora 2 und die Videos-API wurden am
   **24.09.2026** abgeschaltet und haben keinen Nachfolger. Die Spezifikation gilt nur noch als
   „historisch“. Für uns bleibt sie trotzdem der De-facto-Vertrag, weil LiteLLM genau diese
   Routen weiter implementiert.
2. **Unbekannte Felder beim Create kommen durch.** Top-Level-Felder und `extra_body` werden
   ohne Allowlist an `api_base` weitergereicht; nur LiteLLM-interne Schlüssel
   (z. B. `metadata`) werden entfernt. **[Test]**
3. **Breaking Change ab LiteLLM v1.100.0:** Create wird *immer* als `multipart/form-data`
   gesendet. Verschachtelte Objekte und Arrays werden dabei im Stil des OpenAI-SDK
   (`reference_urls[][url]=…`) flachgeklopft, Booleans kommen als `"false"` an. Unser Proxy
   versteht diese Klammernotation derzeit nicht. **[Test]**
4. **Remix, Edits und Extensions** reichen nur `extra_body` weiter. Unbekannte Top-Level-Felder
   gehen dort verloren. **[Test]**
5. **Antwortfelder:** LiteLLM baut die Antwort über das Pydantic-Modell `VideoObject` neu auf.
   Unsere Erweiterungsfelder (`provider_status`, `last_frame_available`, `service_tier` …)
   **verschwinden** bei Create, Status, Remix, Edit und Extension. Bei List bleiben sie
   erhalten, aber List ist über den Proxy ohnehin nicht routbar. **[Test]**
6. **Über den LiteLLM-Proxy nicht nutzbar:** `DELETE /v1/videos/{id}` (HTTP 405),
   `GET /v1/videos` (ohne Modell nicht routbar), `?variant=` bei `/content` (wird verworfen,
   Content-Type ist fest `video/mp4`) und `/last_frame`. **[Test]**
7. **ID-Falle:** Nur die vom Create zurückgegebene ID enthält die `model_id` und ist dauerhaft
   routbar. Status-, Remix-, Edit- und Extension-Antworten kodieren dagegen
   `model_id:` *leer*. Wer diese IDs verwendet, landet beim Default-OpenAI-Endpunkt und nicht
   bei uns. **[Test]**
   Abhilfe ohne Patch an LiteLLM: Unser Proxy gibt selbst bereits LiteLLM-kodierte IDs zurück.
   LiteLLM übernimmt sie dann unverändert. **[Test]**
8. **Metadaten:** `/v1/models` liefert über LiteLLM keine Upstream-Felder wie `capabilities`.
   `model_info` in der LiteLLM-Config darf aber **beliebige eigene Schlüssel** enthalten
   (`capabilities`, `prompt_guide_url` …). `/model/info` und `/v1/model/info` geben sie
   zurück, auch für Nicht-Admin-Keys, dann gefiltert auf deren Modelle. **[Test + Code]**
9. **Pass-Through funktioniert** für `/v1/prompt-guides/...` unter dem LiteLLM-Host. Mit
   `auth: true` brauchen Nicht-Admin-Keys allerdings `allowed_passthrough_routes`, und die
   Doku nennt diese Funktion „Enterprise“. **[Test mit Master-Key + Code]**

---

## 1. OpenAI-Videos-API (Stand 2026, inzwischen abgeschaltet)

### 1.1 Status

- Auf der Deprecations-Seite steht: „On March 24th, 2026, we notified developers using the
  Videos API …“ und „removal from the API on September 24, 2026“. Betroffen sind die
  Videos-API sowie `sora-2`, `sora-2-pro`, `sora-2-2025-10-06`, `sora-2-2025-12-08` und
  `sora-2-pro-2025-10-06`. Als Ersatz ist „---“ eingetragen.
  Quelle: https://developers.openai.com/api/docs/deprecations
- API-Referenz und Guide tragen den Hinweis „The Sora 2 models and Videos API were shut down
  on September 24, 2026 … kept for historical purposes“.
  Quellen: https://developers.openai.com/api/reference/resources/videos ,
  https://developers.openai.com/api/docs/guides/video-generation

### 1.2 Endpunkte

Quelle: https://developers.openai.com/api/reference/resources/videos

| Methode | Pfad | Parameter |
|---|---|---|
| POST | `/videos` | `prompt` (Pflicht), `input_reference` (Objekt mit genau einem von `file_id` oder `image_url`; als Multipart alternativ eine Datei), `model` (`sora-2` [Default], `sora-2-pro`, datierte Snapshots), `seconds` (`"4"` [Default], `"8"`, `"12"`; laut Guide auch 16/20), `size` (`720x1280` [Default], `1280x720`, `1024x1792`, `1792x1024`; laut Guide bei `sora-2-pro` auch 1080p) |
| POST | `/videos/{video_id}/remix` | `prompt`. Laut Guide „being deprecated in favor of edits“ |
| GET | `/videos/{video_id}` | – |
| GET | `/videos` | Query: `after`, `limit`, `order` (`asc`/`desc`) → `{object:"list", data, first_id, last_id, has_more}` |
| DELETE | `/videos/{video_id}` | → `{id, deleted, object:"video.deleted"}` |
| GET | `/videos/{video_id}/content` | Query: `variant` = `video` (Default, MP4) \| `thumbnail` (WebP) \| `spritesheet` (JPEG) |
| POST | `/videos/edits` | `prompt`, `video: {id}`. Laut Guide ist auch ein hochgeladenes Video möglich; dann muss `model` gesetzt sein, und die Funktion steht nur berechtigten Kunden offen |
| POST | `/videos/extensions` | `prompt`, `seconds`, `video: {id}`. Bis zu 20 s je Extension, höchstens 6 Extensions (120 s) |
| POST | `/videos/characters` | Multipart: `name`, `video` (MP4, empfohlen 2–4 s) → `{id, created_at, name}` |
| GET | `/videos/characters/{character_id}` | – |

Weitere Punkte aus dem Guide
(https://developers.openai.com/api/docs/guides/video-generation):

- `input_reference` geht entweder als Multipart-Datei (JPEG/PNG/WebP) oder als JSON mit
  `file_id`/`image_url`. Das Bild dient als erstes Frame und muss zur Zielgröße `size` passen.
- Ein Request kann bis zu 2 Characters enthalten; der Prompt muss den Namen des Characters
  nennen.
- Webhooks melden `video.completed` und `video.failed`.
- Empfohlenes Polling: alle 10–20 s, bei Bedarf mit Backoff.
- Download-URLs gelten bis zu 1 h. Der Batch-API-Weg unterstützt nur `POST /v1/videos` und
  nur JSON.
- Prompting-Hinweise stehen im Guide („Effective prompting“) und in einem separaten
  Prompting-Guide, also **in der Dokumentation und nicht in der API**.

### 1.3 Video-Objekt

`id`, `object:"video"`, `created_at`, `completed_at`, `expires_at`, `error`
(`code`, `message`, optional `headers` und `misalignment{…}`), `model`, `progress`,
`prompt`, `remixed_from_video_id`, `seconds`, `size`, `status`
(`queued|in_progress|completed|failed`).
Quelle: https://developers.openai.com/api/reference/resources/videos

### 1.4 OpenAI-Model-Objekt (für Abschnitt 5)

`id`, `created`, `object:"model"`, `owned_by`, optional `shutdown_date`. Felder für
Fähigkeiten oder Dokumentation gibt es nicht.
Quelle: https://developers.openai.com/api/reference/resources/models

---

## 2. Was LiteLLMs Proxy für ein `openai/`-Modell mit eigener `api_base` unterstützt

### 2.1 Routen im Proxy

Quelle: `litellm/proxy/video_endpoints/endpoints.py` (v1.95.0, Z. 32–915), Liste aus den
`@router`-Dekoratoren. In v1.105.0 und auf `main` ist der Stand gleich; Prüfung per `grep`:
kein `router.delete`.

| Route | LiteLLM-Proxy | Upstream-Aufruf | Getestet |
|---|---|---|---|
| `POST /v1/videos` | ja | `POST {api_base}/videos` | ✔ |
| `GET /v1/videos/{id}` | ja | `GET {api_base}/videos/{orig_id}` | ✔ |
| `GET /v1/videos/{id}/content` | ja, **ohne `variant`** | `GET …/{orig_id}/content` | ✔ Der Query-Parameter wurde verworfen; die Antwort hat immer `media_type="video/mp4"` (endpoints.py Z. 390–394) |
| `POST /v1/videos/{id}/remix` | ja | `POST …/{orig_id}/remix` | ✔ |
| `POST /v1/videos/edits` | ja | `POST {api_base}/videos/edits` | ✔ |
| `POST /v1/videos/extensions` | ja | `POST {api_base}/videos/extensions` | ✔ |
| `POST/GET /v1/videos/characters[/{id}]` | ja | `…/videos/characters` | nicht getestet |
| `GET /v1/videos` (List) | Route vorhanden, **aber nicht zu uns routbar** | – | ✘ siehe 2.3 |
| `DELETE /v1/videos/{id}` | **fehlt** | – | ✘ HTTP 405 „Method Not Allowed“ (1.95 und 1.105) |
| `GET /v1/videos/{id}/last_frame` (unsere Erweiterung) | fehlt | – | – |

Ergänzende Belege:

- Das SDK exportiert in `litellm/videos/__init__.py` kein `video_delete`, nur
  `video_generation`, `video_list`, `video_status`, `video_content`, `video_remix`,
  `video_edit`, `video_extension`, `video_create_character` und `video_get_character`.
  Der Transformationscode für Delete existiert zwar
  (`llms/openai/videos/transformation.py` Z. 375–412), wird aber nirgends angebunden.
- Die LiteLLM-Doku zu Videos führt Delete ebenfalls nicht und sagt zu List
  „requires custom_llm_provider“: https://docs.litellm.ai/docs/videos

### 2.2 Kodierung der Video-IDs

- Format: `"video_" + base64("litellm:custom_llm_provider:{provider};model_id:{model};video_id:{orig}")`.
  Quelle: `litellm/types/videos/utils.py` Z. 15, 38–56 sowie die Vorlage
  `SpecialEnums.LITELLM_MANAGED_VIDEO_COMPLETE_STR`.
- Beim Dekodieren gilt: Nur IDs mit dem Präfix `video_`, die nach Base64-Dekodierung ein `;`
  enthalten, werden zerlegt. Fehlendes Padding wird ergänzt (Z. 28–35, 59–113).
- `encode_video_id_with_provider` gibt eine **bereits kodierte ID unverändert** zurück
  (Z. 43–49). Darauf beruht der Workaround in 2.4.
- Upstream bekommen wir immer die Original-ID, weil `extract_original_video_id` beim
  Status-, Content-, Remix-, Delete-, Edit- und Extension-Request greift
  (`transformation.py` Z. 213, 245, 388, 425, 514, 543). **[Test: `cgt-123` kam an.]**
- Routing beim Folgeaufruf: Der Proxy dekodiert die `model_id` und ruft
  `llm_router.resolve_model_name_from_model_id()` auf (endpoints.py Z. 250–269).
  Diese Funktion akzeptiert entweder einen Modellgruppennamen oder einen Wert, für den
  `litellm_params.model` gleich `model_id` ist oder auf `/model_id` endet
  (`router.py` Z. 9498–9545).
  Bei uns kodiert das Create `model_id:m1`, und `openai/m1` passt. **[Test]**
- **Inkonsistente IDs [Test, 1.95.0 und 1.105.0]:**
  - Create liefert `…model_id:m1;video_id:cgt-123`, weil
    `transform_video_create_response` das Modell übergibt (Z. 184–185).
  - Status, Remix, Edit und Extension kodieren dagegen mit `model_id=None`
    (Z. 283, 450, 530, 562), also `…model_id:;video_id:cgt-123`.
  - Dieselbe Ressource hat damit **zwei verschiedene IDs**.
  - Ruft man Status oder Content mit der ID *ohne* Modell auf, ist kein Modell gesetzt.
    `route_llm_request` ruft dann `litellm.avideo_status` direkt auf
    (`proxy/route_llm_request.py` Z. 525–545), mit Provider `openai` und **ohne unsere
    `api_base`**. Die Anfrage geht an den OpenAI-Default; im Test kam ein HTTP-500-Parse-Fehler,
    und der Mock erhielt nichts.
  - Folge: Jobs aus Remix, Edit oder Extension lassen sich über LiteLLM **nicht pollen**.
  - Zugehöriges Issue: https://github.com/BerriAI/litellm/issues/33423 (offen; dort leere
    `model_id` schon beim Create, mit `STORE_MODEL_IN_DB`). Fix-PR, offen, deckt auch
    Remix/Edit/Extension ab: https://github.com/BerriAI/litellm/pull/44614

### 2.3 List und Delete

- **List:** `video_list` im Proxy setzt nur `query_params` und optional
  `custom_llm_provider`, aber nie `model` (endpoints.py Z. 130–200). Ohne Modell geht
  `route_llm_request` an `litellm.avideo_list` vorbei am Router
  (route_llm_request.py Z. 525–545), also ohne die `api_base` des Deployments.
  - **[Test]** Ohne Header: HTTP 400 „LLM Provider NOT provided“.
  - **[Test]** Mit `?custom_llm_provider=openai`: Anfrage an den OpenAI-Default, HTTP 500;
    der Mock erhielt nichts.
  - Ein `?model=` wird nicht ausgewertet. **[Test]**
  - Issue: https://github.com/BerriAI/litellm/issues/22130 (stale geschlossen).
- **Delete:** Es gibt keine Proxy-Route, **[Test]** liefert HTTP 405.
- Die Antwort auf List wird übrigens als Dict durchgereicht (Z. 334–373); Zusatzfelder wie
  `total` blieben dort erhalten. Das ist aber nur über das SDK mit expliziter `api_base`
  erreichbar.

### 2.4 Workaround für stabile IDs (getestet)

Unser Proxy gibt in **allen** Video-Antworten (Create, Status, Remix, Edit, Extension, List)
die ID bereits im LiteLLM-Format zurück:

```
video_ + base64("litellm:custom_llm_provider:openai;model_id:<upstream-model-id>;video_id:<interne-id>")
```

Bei eingehenden Anfragen akzeptiert er beide Formen und dekodiert sie zur internen ID.

**[Test, 1.95.0]:**

- Der Mock lieferte beim Remix eine so kodierte ID.
- LiteLLM reichte sie unverändert durch.
- Der anschließende `GET /v1/videos/{id}` wurde korrekt an den Mock geroutet
  (`GET /v1/videos/cgt-999`).

Einschränkungen:

- `<upstream-model-id>` muss dem Teil hinter `openai/` in `litellm_params.model` entsprechen
  oder dem LiteLLM-Modellnamen.
- Teilen sich mehrere Deployments dieselbe Upstream-ID, nimmt LiteLLM den ersten Treffer
  (`router.py` Z. 9527–9545).

### 2.5 Antwortobjekt: Felder gehen verloren

- `VideoObject` ist ein Pydantic-`BaseModel` ohne `extra="allow"`
  (`litellm/types/videos/main.py` Z. 8–24; `model_config == {}`).
  Unbekannte Felder werden verworfen. **[Test]** `provider_status`, `last_frame_available`
  und `prompt_guide_url` fehlten in der LiteLLM-Antwort.
- Erhalten bleiben: `id`, `object`, `status`, `created_at`, `completed_at`, `expires_at`,
  `error`, `progress`, `remixed_from_video_id`, `seconds`, `size`, `model` und `usage`.
  Das Feld `prompt` aus der OpenAI-Spezifikation fehlt ebenfalls.
- `model` wird in der Antwort durch den **LiteLLM-Modellgruppennamen** ersetzt.
  **[Test]** `"model":"seedance-test"` statt `m1`.
- Für Statusdetails taugt deshalb nur `error` (ein Dict, wird durchgereicht) als Transportweg.
  Zum Beispiel `error.code`/`error.message` bei `failed`.

---

## 3. Durchreichen unbekannter Request-Felder

### 3.1 Create (`POST /v1/videos`)

Codepfad v1.95.0:

1. Der Proxy liest den Body vollständig (JSON oder Form) in `data`; die Datei
   `input_reference` wird separat übernommen (endpoints.py Z. 79–84).
2. Der Router ruft `litellm.avideo_generation(**data)` auf; alle Felder landen in `**kwargs`.
3. `VideoGenerationRequestUtils.get_requested_video_generation_optional_param`
   (`litellm/videos/utils.py` Z. 47–98) übernimmt **alle** kwargs und filtert nur
   `filter_out_litellm_params` heraus (`litellm/utils.py` Z. 3509–3528, Liste
   `all_litellm_params`). `extra_body` wird zusätzlich **flach in die Top-Level-Parameter
   gemischt** (Z. 83–94).
4. `OpenAIVideoConfig.map_openai_params` gibt alles unverändert zurück
   (`llms/openai/videos/transformation.py` Z. 62–69). `get_supported_openai_params`
   (Z. 47–60) dient nur der Information und **filtert nicht**.
5. `transform_video_create_request` (Z. 104–140) baut `CreateVideoRequest(**params)`. Das ist
   ein `TypedDict`, akzeptiert zur Laufzeit also beliebige Schlüssel. Nur `input_reference`
   wird als Datei abgetrennt.
6. **v1.95.0:** Ohne Datei geht der Request als JSON raus, mit Datei als Multipart
   (`llms/custom_httpx/llm_http_handler.py` Z. 6858, 6962).
   **v1.100.0 und neuer (getestet mit 1.105.0):** immer Multipart, siehe 3.2.

**[Test 1.95.0, JSON-Request an LiteLLM]** – beim Mock kam an:

```json
{"model":"m1","prompt":"fox","seconds":"5","size":"1280x720","user":"u1",
 "reference_urls":[{"url":"https://e/x.png","media_type":"image","role":"first_frame"}],
 "negative_prompt":"blur","task":"edit","generate_audio":false,
 "audio_url":"https://e/a.mp3","priority":3}
```

Was dabei auffällt:

- `extra_body.{audio_url,priority}` wurde flachgezogen.
- `metadata` wurde entfernt.
- `model` wurde auf das Upstream-Modell umgeschrieben.

**[Test 1.95.0, Multipart-Request an LiteLLM]:** Form-Felder kommen als Strings durch,
z. B. `reference_urls` als JSON-String. Das passt zu unserem Parser
(`src/modelark_proxy/app.py` Z. 139–146).

### 3.2 Breaking Change ab v1.100.0: Create wird immer als Multipart gesendet

- PR „fix: match OpenAI SDK wire format on image/video routes“, gemergt am 24.08.2026:
  https://github.com/BerriAI/litellm/pull/38104 . Auslöser war Punkt 1 in
  https://github.com/BerriAI/litellm/issues/36493 .
- Im Code: `OpenAIVideoConfig.use_multipart_form_data() -> True`
  (v1.105.0 `llms/openai/videos/transformation.py` Z. 107). Im Handler steht der Zweig
  `files=serialize_multipart_form_fields(data)` (v1.105.0 `llm_http_handler.py`
  Z. 7240–7262), die Serialisierung liegt in `litellm_core_utils/llm_request_utils.py`
  Z. 16–106.
- Eingrenzung über GitHub-Tags: Die Methode fehlt in `v1.98.0` und `v1.99.0` und ist ab
  `v1.100.0` vorhanden.
- **[Test 1.105.0, derselbe JSON-Request]** – beim Mock kam an:

  ```
  multipart/form-data:
  model=m1, prompt=fox, seconds=5,
  reference_urls[][url]=https://e/x.png, reference_urls[][media_type]=image,
  reference_urls[][role]=first_frame, reference_urls[]=https://e/y.png,
  negative_prompt=blur, generate_audio=false, content[][type]=text, content[][text]=hi,
  priority=3
  ```

  - Arrays aus Objekten werden zu wiederholten `key[][sub]`-Teilen.
  - Skalare Listen werden zu wiederholten `key[]`-Teilen.
  - Booleans und Zahlen kommen als Strings an.
  - Unser Parser liest nur `reference_urls` und `content` als JSON-String; **die
    Klammer-Felder würde er als unbekannte Schlüssel behandeln**. Das ist aus dem Code
    abgeleitet und nicht gegen unseren echten Server getestet.
- **[Test 1.105.0]** Ein bereits JSON-kodierter String
  (`"reference_urls":"[{\"url\":…,\"real_human\":true}]"`) kommt als *ein* Form-Feld
  unverändert an. Diese Kodierung ist versionsübergreifend robust.

### 3.3 `input_reference`

- Multipart-Datei → wird durchgereicht, aber **immer mit Dateiname `input_reference.png`**.
  Den Content-Type rät LiteLLM aus den Bytes (`_add_image_to_files`, Z. 565–577 mit
  `ImageEditRequestUtils.get_image_content_type`).
  **[Test]** Ein MP4 mit `ftyp`-Box kam als `input_reference.png` mit `image/heic` an.
  Unser Proxy muss den Typ also über die Dateisignatur bestimmen und darf weder Dateiname
  noch MIME-Typ trauen.
- `input_reference` als **URL-String** in JSON → wird als *Dateiinhalt* hochgeladen: eine
  „PNG“, deren Inhalt der URL-Text ist. **[Test]** Ebenfalls dokumentiert als Nachtrag in
  https://github.com/BerriAI/litellm/issues/36493 .
- `input_reference` als **JSON-Objekt** (`{"image_url":…}`, OpenAI-JSON-Form) → **Fehler**:
  `'dict' object has no attribute 'read'`, HTTP 400/500 nach Retries. **[Test 1.95.0]**
- Folgerung: Für URL-Referenzen unsere eigenen Felder (`input_reference_url`,
  `reference_urls`) verwenden, niemals `input_reference`.

### 3.4 Remix, Edits, Extensions

- Remix: `video_remix` übergibt nur `video_id`, `prompt` und `extra_body`
  (`videos/main.py` Z. 560–650). `transform_video_remix_request` setzt
  `data = {"prompt": prompt}; data.update(extra_body)` (`transformation.py` Z. 230–258).
- Edits und Extensions verhalten sich analog (Z. 504–519, 533–552).
- **[Test 1.95.0]** Remix, Edit und Extension mit `negative_prompt` (top-level) und
  `extra_body:{seed}`: Beim Mock kam nur `{"prompt":…,"seed":7}` an, **`negative_prompt`
  fehlte**.
- Diese Routen senden JSON, auch in 1.105.0. **[Test]** Remix kam als `application/json`.
- Edit/Extension aus Form-Bodies: Der Bugfix „Stream consumed“ wurde gemergt
  (https://github.com/BerriAI/litellm/pull/36513 ,
  https://github.com/BerriAI/litellm/issues/36487 ). Upload-Datei bei Edits:
  https://github.com/BerriAI/litellm/pull/38155 .

### 3.5 Ergebnis für unsere Erweiterungsfelder

| Weg | Create | Remix/Edit/Extension |
|---|---|---|
| Top-Level-Feld (JSON) | ✔ (≤1.99 als JSON, ≥1.100 als Multipart mit Klammernotation) | ✘ wird verworfen |
| `extra_body` | ✔ (flachgezogen) | ✔ (flachgezogen) |
| Feld als JSON-String | ✔ in allen Versionen gleich | ✔ über `extra_body` |
| Multipart-Datei | nur `input_reference`, nur eine Datei, Name/MIME unzuverlässig | ✘ |

---

## 4. Modell-Metadaten und Prompt-Guides über LiteLLM

### 4.1 `/v1/models`

- LiteLLM erzeugt die Liste selbst aus der Config und fragt die Upstream-`/v1/models`
  **nicht** ab. **[Test 1.95.0]** Antwort:
  `{"id":"seedance-test","object":"model","created":1677610602,"owned_by":"openai"}`;
  der Mock erhielt keinen `/v1/models`-Aufruf.
- In 1.105.0 kommt zusätzlich `"mode":"video_generation"` hinzu. **[Test]**
- Query-Optionen in 1.105.0: `include_metadata` (liefert nur Fallbacks),
  `return_wildcard_routes`, `scope` und `healthy_only`. Keine davon bringt `model_info`
  mit. Quelle: v1.105.0 `proxy/proxy_server.py` Z. 11545 ff.; der Docstring verweist
  selbst auf `/model/info`.
- Unsere `capabilities` aus der Upstream-`/v1/models` erreichen LiteLLM-Clients also **nicht**.

### 4.2 `model_info` mit eigenen Schlüsseln

- **[Test 1.95.0 und 1.105.0]** Diese Config:

  ```yaml
  model_info:
    mode: video_generation
    prompt_guide_url: https://…/v1/prompt-guides/m1
    capabilities: {frames: true, reference_limits: {image: 9}}
  ```

  `GET /model/info` lieferte `model_info.prompt_guide_url` und `model_info.capabilities`
  unverändert zurück. `api_key` wurde entfernt
  (`remove_sensitive_info_from_deployment`,
  `proxy/common_utils/openai_endpoint_utils.py` Z. 15 ff.).
- Laut Doku dürfen beliebige `model_info`-Felder gesetzt werden; sie „pass straight through
  to `GET /model/info`“. Die Aussage bezieht sich dort auf Modelle, die per API angelegt
  werden: https://docs.litellm.ai/docs/proxy/model_management
- `/model_group/info` enthält eigene Schlüssel **nicht**, weil `ModelGroupInfo` feste Felder
  hat (`types/router.py`). **[Test]**
- **Zugriff für Nicht-Admin-Keys:**
  - `/model/info` und `/v1/model/info` stehen in `LiteLLMRoutes.info_routes`
    (`proxy/_types.py` Z. 529–551).
  - `non_proxy_admin_allowed_routes_check` lässt `/model/info` explizit zu
    (`proxy/auth/route_checks.py` Z. 253, 273–275: „/model/info just shows models user has
    access to“).
  - Die Ergebnisliste wird auf die Modelle des Keys bzw. Teams gefiltert
    (`_get_v1_model_info_allowed_model_names`, `proxy_server.py` Z. 12684–12713).
  - Nicht getestet: Ein Virtual Key ließ sich nicht anlegen, weil keine Datenbank lief.
- Abfrage für ein einzelnes Modell: `GET /v1/model/info?litellm_model_id=<deployment-id>`.
  Einen Filter nach Modellgruppenname gibt es nicht direkt, der Client filtert die Liste
  selbst.

### 4.3 Pass-Through für `/v1/prompt-guides/...`

- **[Test 1.95.0 und 1.105.0, Master-Key]** Diese Config funktioniert:

  ```yaml
  general_settings:
    pass_through_endpoints:
      - path: /v1/prompt-guides
        target: http://<proxy>/v1/prompt-guides
        include_subpath: true
        auth: true
        headers: {Authorization: Bearer <PROXY_API_KEY>}
  ```

  `GET :4099/v1/prompt-guides/m1` lieferte `text/markdown` vom Mock. Der Upstream sah dabei
  den hinterlegten Upstream-Key und nicht den Client-Key.
- **Authentifizierung:**
  - Mit `auth: true` hängt LiteLLM `user_api_key_auth` an die Route
    (`pass_through_endpoints.py` Z. 2770–2782). Der Code-Kommentar dort sagt:
    „Authentication on a pass-through endpoint used to be enterprise-only … The safe option
    must always be free“. In 1.95.0 ist `auth` also offenbar nicht mehr Enterprise-gesperrt.
  - **Aber:** Für Nicht-Admin-Keys verlangt `_require_auth_pass_through_access`, dass die
    Route in `allowed_passthrough_routes` in den Metadaten des Keys oder Teams steht
    (`proxy/auth/route_checks.py` Z. 617–675). Sonst antwortet LiteLLM mit 403.
  - Die Doku markiert `auth` und die Allow/Deny-Listen weiterhin als „(Enterprise)“ und
    „only proxy admins can set“: https://docs.litellm.ai/docs/proxy/pass_through
- **Bekannte Probleme:**
  - `include_subpath` mit `auth` ungleich `true` → Virtual Keys bekommen 401 mit einer
    irreführenden Admin-Fehlermeldung:
    https://github.com/BerriAI/litellm/issues/36280 (offen).
  - Config-Pass-Throughs gelten nicht als LLM-API-Routen; `allowed_passthrough_routes` wird
    von `/key/generate` in der OSS-Version laut Issue nicht akzeptiert:
    https://github.com/BerriAI/litellm/issues/36508 (offen).
  - File-less Multipart wurde zu urlencoded; behoben in PR #38104.
- Ein Pass-Through umgeht die `models`-Allowlist des Keys. Für öffentliche Guides ist das
  unkritisch.

---

## 5. Konventionen für Prompting-Hinweise und Modell-Doku in OpenAI-kompatiblen APIs

- **OpenAI** liefert im Model-Objekt nur `id`, `created`, `object`, `owned_by` und
  `shutdown_date`. Prompting-Guidance steht ausschließlich in der Dokumentation (Guide-Kapitel
  „Effective prompting“ und ein separater Prompting-Guide). Eine Konvention, Guides über die
  API auszuliefern, gibt es nicht.
  Quellen: https://developers.openai.com/api/reference/resources/models ,
  https://developers.openai.com/api/docs/guides/video-generation
- **OpenRouter** erweitert das Model-Objekt um `description`, `architecture.input_modalities`
  und `output_modalities`, `supported_parameters`, `default_parameters` und
  **`links.details`**. Das ist das verbreitetste Vorbild für Zusatzfelder plus Doku-Link.
  Quelle: https://openrouter.ai/docs/api/api-reference/models/get-models
- **LiteLLM** nutzt `model_info` (freie Schlüssel, siehe 4.2) und `mode`. Der öffentliche
  Model Hub (`/public/model_hub`, `/public/model_hub/info` in
  `proxy/public_endpoints/public_endpoints.py`) ist eine UI-orientierte Variante.
- Empfehlung abgeleitet: Zusatzfelder im Model-Objekt nach OpenRouter-Muster benennen, und
  zwar additiv: `capabilities`, `supported_parameters`, `description` und
  `links: {prompt_guide: "<url>"}`. Den Guide selbst als eigene Ressource mit
  `text/markdown` ausliefern. Unbekannte Felder ignorieren OpenAI-Clients ohnehin.

---

## 6. Versionen und bekannte Bugs

| Version / Datum | Änderung | Quelle |
|---|---|---|
| v1.78/1.79 (Okt. 2025) | Videos-Router und Proxy-Endpunkte eingeführt (PR gemergt 24.10.2025) | https://github.com/BerriAI/litellm/pull/15841 |
| Nov. 2025 | Video-Routen brauchten Admin-Rechte (behoben) | https://github.com/BerriAI/litellm/issues/16470 |
| v1.95.0 (02.08.2026) | im Repo installiert; Create JSON ohne Datei, Multipart mit Datei | lokaler Code |
| v1.100.0 (06.09.2026) | Create immer Multipart mit SDK-Klammernotation; Pass-Through behält Multipart bei | PR #38104 (s. o.), Tag-Vergleich |
| v1.105.0 (aktuell auf PyPI) | Verhalten wie 1.100 bei Videos; `/v1/models` liefert zusätzlich `mode`; weiterhin kein DELETE, kein `variant`, Antwortfelder werden verworfen | Test + Diff |

Offene Bugs mit Bezug zu uns:

- #33423: leere `model_id` in Video-IDs; Status/Content treffen den falschen Key oder
  Endpunkt. Fix-PR #44614 ist offen.
- #36493: Video- und Image-Routen für OpenAI-kompatible Backends, inklusive des Problems mit
  der URL in `input_reference`.
- #36280 und #36508: Auth bei Pass-Through für Virtual Keys.
- #20708 (im Issue #33423 erwähnt): `first_id`/`last_id` bei List waren nicht kodiert. In
  1.95.0 ist das behoben (`transformation.py` Z. 351–371).

---

## 7. Empfehlungen

### 7.1 Erweiterte Fähigkeiten zuverlässig durch LiteLLM bringen

1. **Wire-Format robust machen (Pflicht vor jedem LiteLLM-Upgrade über 1.99 hinaus).**
   Unser `POST /v1/videos` sollte beim Multipart-Parsing zusätzlich
   - die OpenAI-SDK-Klammernotation (`key[]`, `key[][sub]`, `key[sub]`) wieder zu
     Listen und Objekten zusammensetzen,
   - typisierte Strings koerzieren (`"false"`, `"3"`),
   - für **alle** strukturierten Felder JSON-Strings akzeptieren, im JSON-Body ebenfalls.

   Ein Regressionstest sollte genau den unter 3.2 protokollierten Body nachstellen.
2. **Client-Konvention:** Strukturierte Erweiterungen als **JSON-String** schicken, z. B.
   `"reference_urls": "[…]"` oder `"options": "{…}"`. Skalare Felder bleiben top-level.
   Bei Remix, Edit und Extension gehört **alles** in `extra_body`.
3. **Kein `input_reference` mit URL oder Objekt** verwenden, sondern `input_reference_url`
   bzw. `reference_urls`. Dateien besser vorher über `/v1/media/references` hochladen; diese
   Route müsste dann allerdings auch per Pass-Through erreichbar sein.
4. **IDs selbst LiteLLM-kompatibel kodieren** (siehe 2.4). Dann werden Status-, Remix-, Edit-
   und Extension-IDs routbar und stabil. Eingehend nimmt der Proxy beide Formen an.
   Alternativ die Clients verpflichten, nur die Create-ID zu verwenden; für Remix, Edit und
   Extension reicht das aber nicht.
5. **Status-Zusatzinformationen** gehen bei LiteLLM verloren. Kritisches gehört in
   `error{code,message}`. Details wie `last_frame` und `provider_status` über eine eigene
   Route via Pass-Through anbieten (z. B. `/v1/videos-ext/{id}`) oder den Client direkt beim
   Proxy abfragen lassen.
6. **DELETE, List, `variant` und `last_frame`** sind über LiteLLMs Video-Routen nicht
   erreichbar. Wenn Apps sie brauchen, braucht es einen Pass-Through mit eigenem Präfix
   (z. B. `/modelark/v1/videos…`). Das bricht allerdings die Modellunabhängigkeit; besser ist
   es, diese Funktionen als optionale Features zu behandeln.
7. Einheitliche Benennung über alle Provider hinweg, z. B. `negative_prompt`,
   `reference_urls[{url,media_type,role}]`, `task` und `quality`. Der Proxy übersetzt dann
   pro Provider. Unbekannte Felder für das gewählte Modell lehnt er mit 400 ab; die
   `capabilities` sind die Grundlage dafür.

### 7.2 Prompt-Guides über LiteLLM ausliefern

1. **Primär per Discovery über `model_info`:** In der LiteLLM-Config je Modell
   `model_info.capabilities` (generiert aus unserer `/v1/models`) und
   `model_info.prompt_guide_url` pflegen. Apps lesen `GET /v1/model/info` mit ihrem Virtual
   Key; das funktioniert für Nicht-Admins, gefiltert auf erlaubte Modelle.
   Nachteil: Die Daten werden doppelt gepflegt. Gegenmittel: ein Sync-Skript, das aus
   `GET /v1/models` des Proxys den YAML-Block erzeugt.
2. **Inhalt per Pass-Through:** Die Route `/v1/prompt-guides` mit `include_subpath: true`
   und `auth: true` unter dem LiteLLM-Host freigeben. Für Nicht-Admin-Keys muss
   `allowed_passthrough_routes` gesetzt werden (Enterprise-Status unklar, siehe unten).
   Fallback: `auth: false` für öffentliche, nicht sensible Guides, oder ein eigener
   Read-only-Token im Header.
3. **In unserer eigenen API:** `GET /v1/prompt-guides/{model}` mit `text/markdown`, plus
   `links.prompt_guide` und `prompt_guide` in den Objekten von `GET /v1/models` (nach
   OpenRouter-Muster). Für LiteLLM-Clients wirkt das nur über Punkt 1 und 2.
4. **Nicht empfohlen:** Guide-Text in Video-Antworten einbetten. LiteLLM verwirft solche Felder.

---

## Unklar / nicht verifizierbar

- **Nicht-Admin-Virtual-Keys** auf `/v1/model/info` und auf Pass-Through mit `auth: true`
  wurden nicht getestet, weil ohne PostgreSQL keine Virtual Keys erzeugt werden konnten. Die
  Aussagen dazu stammen aus dem Code (`route_checks.py`, `proxy_server.py`) und der Doku.
- **Enterprise-Pflicht:** Ob `allowed_passthrough_routes` in der OSS-Version setzbar ist,
  bleibt offen. Die Doku sagt „Enterprise, only proxy admins can set“, Issue #36508 sagt
  „not accepted by `/key/generate` on the open-source build“, der Code-Kommentar in 1.95 sagt,
  `auth` sei nicht mehr Enterprise-gesperrt. Die Auth selbst läuft in OSS, ob das
  Freischalten für Keys funktioniert, ist ungeklärt.
- Ob unser echter Proxy die Klammernotation aus 3.2 wirklich ablehnt oder still ignoriert,
  ist aus dem Code abgeleitet (`app.py` Z. 115–148) und **nicht** gegen den laufenden Server
  getestet. `form.multi_items()` und das Dict-Verhalten bei wiederholten Schlüsseln müssten
  mit einem Test geprüft werden.
- Character-Routen (`/v1/videos/characters`) wurden über LiteLLM nicht getestet.
- Ob die Videos-Routen in einer LiteLLM-Version nach 1.105.0 DELETE, `variant` oder
  `extra="allow"` bekommen, ist offen. Auf `main` war am 11.10.2026 kein `router.delete` in
  `video_endpoints/endpoints.py` vorhanden.
- Bei den OpenAI-Spezifikationen widersprechen sich Referenz und Guide bei `seconds`
  (Enum 4/8/12 vs. 16/20) und bei der Größe (1080p). Die Seiten sind archiviert, eine Klärung
  ist nicht mehr möglich.
- Die genaue Version, mit der die Video-Endpunkte erschienen sind (PR #15841, gemergt
  24.10.2025), ließ sich nur auf v1.78.x/v1.79.x eingrenzen und nicht exakt bestimmen.
- `platform.openai.com/docs/api-reference/videos` lieferte HTTP 403. Verwendet wurde der
  inhaltsgleiche Nachfolger auf developers.openai.com.
