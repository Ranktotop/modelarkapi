# Spezifikation: AI Video Studio – API-Vertrag (T2)

**Status:** abgenommen am 11.10.2026 · **Stand:** 11.10.2026 · **Grundlage:**
[plan.md](../tasks/plan.md), [ADR-001](architektur/README.md),
[research/google.md](../tasks/research/google.md), [research/kling.md](../tasks/research/kling.md),
[research/litellm-openai.md](../tasks/research/litellm-openai.md)

Dieser Vertrag legt fest, wie Clients den Proxy ansprechen: Endpunkte, Feldnamen,
Typen, IDs, Fehler und Modell-Metadaten. Alle Umsetzungs-Tasks (T3–T29)
richten sich danach. Was hier nicht steht, gehört nicht zur öffentlichen
Schnittstelle.

Die Schlüsselwörter **muss**, **soll** und **kann** sind verbindlich gemeint.

---

## 1. Grundprinzipien

1. **Ein Aufruf für alle Modelle.** `POST /v1/videos` nimmt für jedes Modell
   dieselben Felder an. Ein Modellwechsel ändert nur `model`.
2. **Abwärtskompatibel.** Alle heute dokumentierten Seedance-Felder bleiben
   gültig (Abschnitt 17). Neue Felder sind additiv.
3. **LiteLLM-sicher.** Jede Funktion ist über LiteLLM 1.95 bis 1.105 erreichbar,
   soweit LiteLLM die Route durchreicht (Abschnitt 18). Wo LiteLLM Grenzen hat,
   gibt es einen dokumentierten Ausweg.
4. **Fähigkeiten sind maschinenlesbar.** Was ein Modell kann, steht im
   Capability-Dokument (Abschnitt 13). Die Validierung im Proxy und die
   UI-Formulare nutzen dasselbe Dokument.
5. **Nativ bleibt möglich.** Jede Provider-Funktion ist zusätzlich unter
   `/v1/providers/{provider}/…` mit den Original-Parametern erreichbar
   (Abschnitt 16).
6. **`POST` wartet nie auf die Generierung.** Jeder Create-Aufruf antwortet
   sofort mit `queued` oder `in_progress`.

---

## 2. Endpunkte

### 2.1 Einheitliche Fläche

| Methode | Pfad | Zweck | Über LiteLLM |
|---|---|---|---|
| POST | `/v1/videos` | Job erstellen (alle Tasks) | ✔ |
| GET | `/v1/videos/{id}` | Status | ✔ |
| GET | `/v1/videos/{id}/content` | Ergebnis herunterladen (`?variant=`, `?output=`) | ✔ (nur Hauptvideo, Abschnitt 18) |
| GET | `/v1/videos/{id}/last_frame` | Letztes Frame (Seedance) | ✘ |
| POST | `/v1/videos/{id}/remix` | Bestehendes Ergebnis per Prompt bearbeiten | ✔ (Extras nur über `extra_body`) |
| POST | `/v1/videos/edits` | Video bearbeiten | ✔ (Extras nur über `extra_body`) |
| POST | `/v1/videos/extensions` | Video verlängern | ✔ (Extras nur über `extra_body`) |
| GET | `/v1/videos` | Liste | ✘ (LiteLLM routet nicht) |
| DELETE | `/v1/videos/{id}` | Abbrechen bzw. lokal löschen | ✘ (LiteLLM: 405) |
| POST | `/v1/audio/speech` | Text-to-Speech (OpenAI-Format) | ✔ |
| GET | `/v1/models` | Modellliste mit Capabilities und Guide-Link | ✘ (LiteLLM erzeugt eigene Liste) |
| GET | `/v1/models/{id}` | Ein Modell inklusive Prompt-Guide-Volltext | ✘ |
| GET | `/v1/prompt-guides` | Liste der Guides | ✘ |
| GET | `/v1/prompt-guides/{guide}` | Guide als `text/markdown` | ✘ |
| GET | `/v1/litellm/config` | LiteLLM-`model_list` mit `model_info` (YAML oder JSON) | – (Admin-Werkzeug) |
| POST | `/v1/media/references` | Datei hochladen (bestehend) | ✘ |
| DELETE | `/v1/media/references/{id}` | Upload löschen (bestehend) | ✘ |
| GET/POST/DELETE | `/v1/assets[/{id}]` | Wiederverwendbare Assets (Elements, Voices, Real-Human) | ✘ |
| POST/GET | `/v1/videos/characters[/{id}]` | OpenAI-Characters als Asset | ✔ (in T28 zu verifizieren) |
| GET | `/v1/real-human/configuration` | bestehend | ✘ |
| GET | `/health` | Health je Provider | – |

Alle Routen gibt es zusätzlich ohne `/v1`-Präfix, wie heute.
Über LiteLLM erhalten Apps Modell-Metadaten und Prompt Guides aus
`GET /v1/model/info` (`model_info`, Abschnitt 15).

### 2.2 Native Fläche

`/v1/providers/{provider}/…` mit `provider` ∈ {`modelark`, `google`, `kling`}.
Details stehen in Abschnitt 16.

---

## 3. IDs

### 3.1 Video-IDs nach außen

Jede Antwort mit Video-Objekt (Create, Status, Remix, Edit, Extension, Liste)
**muss** die ID im LiteLLM-Format enthalten:

```
video_<base64("litellm:custom_llm_provider:openai;model_id:<upstream-modell>;video_id:<interne-id>")>
```

- `<upstream-modell>` ist exakt der `model`-Wert, den der Proxy im Create
  empfangen hat. LiteLLM hat ihn bereits auf `litellm_params.model` ohne
  `openai/` umgeschrieben; bei direkten Aufrufen ist es der vom Client
  gesendete Wert ohne `openai/`.
- Kodierung: **Standard-Base64 mit Padding**, exakt wie LiteLLMs Dekodierer
  (`litellm/types/videos/utils.py`). Bei ASCII-IDs ohne `?`, `>`, `~` und `;`
  entstehen dabei nie `/` oder `+`; IDs mit diesen Zeichen bleiben unkodiert,
  damit sie im URL-Pfad sicher sind.
- Eingehend akzeptiert jeder Endpunkt **beide Formen**: die kodierte ID und die
  interne ID. Fehlendes Padding wird ergänzt.
- Für Remix, Edit und Extension ist `model_id` das Modell des **neuen** Jobs.

### 3.2 Interne IDs

| Form | Herkunft |
|---|---|
| `cgt-…` | ModelArk-Task (unverändert wie heute) |
| bestehende Real-Human-IDs | unverändert |
| `vid-<provider>-<uuid4hex>` | lokales Jobregister, z. B. `vid-veo-…`, `vid-omni-…`, `vid-kling-…`, `vid-native-…` |

Interne IDs dürfen nur `[A-Za-z0-9_-]` enthalten.

### 3.3 Weitere IDs

| Präfix | Bedeutung |
|---|---|
| `ref-…` | Upload im Media-Store (`POST /v1/media/references`; bisher ohne Präfix, beide Formen gültig) |
| `asset-kling-element-<id>`, `asset-kling-voice-<id>`, `asset-modelark-<id>` | Assets aus `/v1/assets` |
| `char-…` | OpenAI-Character (ein Alias auf ein Asset) |

---

## 4. Eingangskodierung

### 4.1 Content-Types

`POST`-Routen **müssen** `application/json` und `multipart/form-data`
annehmen. `/remix`, `/edits` und `/extensions` werden von LiteLLM als JSON
gesendet.

### 4.2 Strukturierte Felder

Jedes Feld vom Typ Objekt oder Array (`references`, `shots`, `provider_options`,
`speech`, `audio`, `commerce`, `selections`, `reference_urls`, `content` …)
**muss** in allen drei Formen angenommen werden:

1. als JSON-Wert (JSON-Body)
2. als JSON-String (in JSON oder Multipart)
3. in Multipart-Klammernotation, wie sie LiteLLM ab 1.100 erzeugt:
   - `references[][url]=…`, `references[][type]=…` → Array aus Objekten.
     Ein neues Objekt beginnt, sobald sich ein Schlüssel wiederholt.
   - `tags[]=a`, `tags[]=b` → Array aus Skalaren
   - `provider_options[kling][mode]=pro` → verschachtelte Objekte

**Empfehlung für Clients:** Strukturierte Felder als JSON-String senden. Das
ist laut Test in allen LiteLLM-Versionen gleich robust.

### 4.3 Typumwandlung

Multipart-Werte kommen als Strings. Der Proxy wandelt anhand des Schemas um:

- Integer: `seconds`, `n`, `seed`, `duration`, `priority` …
- Float: `speed`, `audio_volume` …
- Boolean (`true`/`false`/`1`/`0`/`yes`/`no`/`on`/`off`): `generate_audio`, `real_human` …

Ein nicht umwandelbarer Wert führt zu `400 invalid_request`.

### 4.4 `extra_body`

Liegt im Body ein Objekt `extra_body` vor (bei Direktaufrufen möglich), werden
seine Felder auf oberster Ebene eingemischt. Felder auf oberster Ebene haben
Vorrang. LiteLLM selbst zieht `extra_body` vorher flach.

### 4.5 Dateien

- `input_reference` als Multipart-Datei wird angenommen (OpenAI-kompatibel).
  Der Typ wird **ausschließlich über die Dateisignatur** bestimmt; Dateiname
  und deklarierter MIME-Typ werden ignoriert (LiteLLM sendet immer
  `input_reference.png`).
- Weitere Multipart-Dateien unter `references[]` sind nur bei Direktaufrufen
  möglich.
- **`input_reference` als URL-String oder JSON-Objekt wird mit 400 abgelehnt.**
  Die Fehlermeldung nennt `references` als Alternative.

---

## 5. `POST /v1/videos`: Request

### 5.1 Felder

| Feld | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `model` | string | ja | Modell-ID (Abschnitt 12). Präfixe `openai/`, `google/`, `kling/`, `modelark/` werden entfernt |
| `prompt` | string | je Task | Text-Prompt. Längenlimit je Modell im Capability-Dokument |
| `task` | enum | nein | Abschnitt 6. Fehlt das Feld, wird der Task abgeleitet (6.3) |
| `references` | array\<Reference\> | je Task | Eingaben (Abschnitt 7) |
| `seconds` | int \| string | nein | Ziel-Dauer in Sekunden (OpenAI-Feld). `"auto"` oder `-1` bedeutet: Modell wählt |
| `size` | string | nein | OpenAI-Format `BREITExHÖHE`. Wird in `resolution` und `aspect_ratio` übersetzt (8.2) |
| `resolution` | enum | nein | `360p`, `480p`, `720p`, `1080p`, `4k` |
| `aspect_ratio` | enum | nein | `16:9`, `9:16`, `1:1`, `4:3`, `3:4`, `21:9`, `adaptive`. Alias: `ratio` |
| `negative_prompt` | string | nein | Unerwünschte Inhalte |
| `seed` | int | nein | Seed (soweit unterstützt) |
| `generate_audio` | bool | nein | Ton erzeugen |
| `quality` | enum | nein | `standard`, `pro` (Kling `std`/`pro`, Kling Avatar und weitere) |
| `n` | int | nein | Anzahl der Varianten (Veo auf Vertex 1–4). Default 1 |
| `shots` | array\<Shot\> | nein | Multi-Shot (8.6) |
| `effect` | string | bei `effect` | Effekt-ID (Kling `effect_scene`) |
| `speech` | Speech | nein | Sprechtext für `lip_sync`, `avatar` und Commerce (8.7) |
| `audio` | AudioOptions | nein | Optionen für Lip Sync und Video-to-Audio (8.8) |
| `selections` | array\<Selection\> | bei `multi_element_edit` | Objektauswahl (8.9) |
| `edit_mode` | enum | bei `multi_element_edit` | `addition`, `swap`, `removal` |
| `commerce` | CommerceFields | bei Commerce-Tasks | Produkt- und Sprechertexte (8.10) |
| `watermark` | bool | nein | Provider-Wasserzeichen (Seedance, Kling) |
| `enhance_prompt` | bool | nein | Prompt-Umschreibung durch den Provider (Veo auf Vertex) |
| `person_generation` | enum | nein | `allow_adult`, `allow_all`, `dont_allow` (Veo) |
| `output_format` | enum | nein | `mp4`, `mov` (Seedance 2.5) |
| `return_last_frame` | bool | nein | Seedance |
| `parameter_policy` | enum | nein | `strict` oder `adapt` (Abschnitt 9) |
| `webhook_url` | string | nein | Ausgehender Webhook des Proxys (Abschnitt 11.4) |
| `provider_options` | object | nein | Native Zusatzfelder (Abschnitt 10) |
| `user` | string | nein | OpenAI-Feld; wird an Seedance als `safety_identifier` weitergegeben |
| `metadata` | object | nein | Wird gespeichert und zurückgegeben (nur bei Direktaufrufen; LiteLLM entfernt das Feld) |

Unbekannte Felder werden mit `400 unsupported_parameter` abgelehnt, sofern sie
nicht in Abschnitt 17 (Kompatibilität) stehen oder `parameter_policy=adapt`
gesetzt ist (dann werden sie ignoriert und protokolliert).

### 5.2 Remix, Edits und Extensions (OpenAI-Routen)

| Route | Abbildung |
|---|---|
| `POST /v1/videos/{id}/remix` `{prompt, …extra}` | `task=edit` mit der Ausgabe von `{id}` als `base_video` (Omni: Multi-Turn über `previous_interaction_id`) |
| `POST /v1/videos/edits` `{prompt, video:{id}, model?, …extra}` | `task=edit`; `video.id` ist eine Video-ID, ein `ref-…` oder ein `data:`-URI |
| `POST /v1/videos/extensions` `{prompt, seconds, video:{id}, model?, …extra}` | `task=extend` |

Fehlt `model`, wird das Modell des Quelljobs verwendet. Alle Felder aus 5.1
sind über `extra_body` zusätzlich nutzbar.

---

## 6. Tasks

### 6.1 Vokabular

| Task | Bedeutung | Pflicht-Eingaben | Optionale Eingaben |
|---|---|---|---|
| `text_to_video` | Video aus Text | `prompt` | – |
| `image_to_video` | Bild als erstes Frame | 1 × `image`/`first_frame` | `prompt`, Elements, Voices |
| `first_last_frame` | Übergang zwischen zwei Bildern | `image`/`first_frame` + `image`/`last_frame` | `prompt`, Elements |
| `reference_to_video` | Inhalte, Stil und Personen aus Referenzen | ≥ 1 Referenz (`image`, `video`, `audio`, `element`) mit Rolle `reference` | `prompt` |
| `multi_shot` | Mehrere Einstellungen in einem Clip | `shots` oder `prompt` mit `shot_mode=intelligence` | Referenzen wie bei `image_to_video` / `reference_to_video` |
| `edit` | Bestehendes Video verändern | 1 × `video`/`base_video` (oder `task_id`) + `prompt` | Bild-Referenzen, Elements |
| `extend` | Video zeitlich fortsetzen | 1 × `video`/`base_video` (oder `task_id`) | `prompt`, Bild-Referenzen |
| `stitch` | Mehrere Clips zu einer Sequenz verbinden | ≥ 2 × `video`/`reference` | `prompt` |
| `motion_control` | Bewegung aus einem Video auf eine Figur übertragen | 1 × `image`/`subject` (oder Element) + 1 × `video`/`motion` | `prompt` |
| `lip_sync` | Lippen eines Videos an Ton anpassen | 1 × `video`/`base_video` (oder `task_id`) + (`audio`/`speech` **oder** `speech.text`) | `audio`-Optionen |
| `avatar` | Sprechende Figur aus Bild und Ton | 1 × `image`/`subject` + (`audio`/`speech` **oder** `speech.text`) | `prompt`, `quality` |
| `effect` | Effekt-Vorlage anwenden | `effect` + 1 oder 2 × `image`/`subject` (je nach Effekt) | – |
| `multi_element_edit` | Objekte im Video hinzufügen, tauschen, entfernen | `video`/`base_video` + `selections` + `edit_mode` (+ Bilder bei addition/swap) | `prompt`, `negative_prompt` |
| `video_to_audio` | Ton für ein vorhandenes Video | 1 × `video`/`base_video` (oder `task_id`) | `prompt` (Soundeffekte), `audio.bgm_prompt`, `audio.asmr` |
| `text_to_audio` | Soundeffekt oder Musik aus Text | `prompt`, `seconds` | – |
| `commerce_talking_agent` | Sprechendes Produktvideo | `commerce`, Avatar-Bild oder Avatar-ID, Produktbild(er) | `speech`, `voice` |
| `commerce_goods_studio` | Produktvideo aus Bild und Text | Produktbild + `commerce.title` | `commerce.description`, `seconds`, `aspect_ratio` |
| `commerce_apparel` | Kleidungsvideo (Apparel Replicator) | Quellvideo, Produktbild(er) | Modelbild, `commerce`, Voice, BGM |

### 6.2 Ergebnisarten je Task

| Task | Ausgabe |
|---|---|
| alle außer den beiden folgenden | Video (`variant=video`) |
| `video_to_audio` | Video mit Ton (`variant=video`) **und** Tonspur (`variant=audio`) |
| `text_to_audio` | Audio (`variant=audio`; `variant=video` liefert 404) |

### 6.3 Ableitung, wenn `task` fehlt

Die Regeln werden der Reihe nach geprüft; die erste passende gewinnt:

1. `effect` gesetzt → `effect`
2. `selections` gesetzt → `multi_element_edit`
3. Rolle `motion` vorhanden → `motion_control`
4. `shots` gesetzt → `multi_shot`
5. Rolle `base_video` und `audio`/`speech` bzw. `speech.text` vorhanden → `lip_sync`
6. Rolle `base_video` vorhanden → `edit`
7. Rollen `first_frame` und `last_frame` vorhanden → `first_last_frame`
8. Genau ein Bild ohne Rolle oder mit Rolle `first_frame`, sonst keine Referenzen → `image_to_video`
9. Irgendeine Referenz vorhanden → `reference_to_video`
10. Sonst → `text_to_video`

Seedance-Felder (`omni_reference_task_type`) haben Vorrang vor dieser
Ableitung (Abschnitt 17).

---

## 7. Referenzen

### 7.1 Objekt

```json
{
  "type": "image | video | audio | element | voice",
  "role": "first_frame | last_frame | reference | subject | motion | base_video | speech | product | model | avatar | bgm",
  "url": "https://… | data:<mime>;base64,…",
  "upload_id": "ref-…",
  "task_id": "video_… | cgt-… | vid-…",
  "output": 0,
  "asset_id": "asset-…",
  "name": "Anzeigename für den Prompt",
  "real_human": false
}
```

- **Genau eine Quelle** aus `url`, `upload_id`, `task_id` oder `asset_id`.
- `type` ist Pflicht, außer bei `task_id` (dann `video`) und `asset_id` (dann vom Asset).
- `role` ist optional. Ohne Rolle gilt: Bild → `reference`
  (bei Task `image_to_video`: `first_frame`), Video → `reference`
  (bei `edit`, `extend`, `lip_sync`, `video_to_audio`: `base_video`), Audio →
  `reference` (bei `lip_sync` und `avatar`: `speech`).
- `output` wählt bei `task_id` die Variante (Default 0).
- `name` dient nur der Anzeige und wird nicht an Provider weitergegeben. Kling
  adressiert Referenzen im Prompt über die API-Platzhalter `<<<image_n>>>`,
  `<<<video_n>>>`, `<<<element_n>>>` und `<<<voice_n>>>`; `n` zählt ab 1 in der
  Reihenfolge des `references`-Arrays je Typ. Die `@Name`-Schreibweise der
  Kling-App gilt für die API nicht.
- `real_human=true` aktiviert die bestehende Seedance-Asset-Verifizierung. Bei
  anderen Providern führt das Flag zu `400 unsupported_parameter`.

### 7.2 Quellen und wie der Proxy sie bereitstellt

| Quelle | Seedance / Kling (brauchen URL) | Google (braucht Bytes, Files API oder GCS) |
|---|---|---|
| `https://`-URL | unverändert weitergeben | Proxy lädt herunter (7.3) |
| `data:`-URI | Proxy speichert im Media-Store und gibt die `PUBLIC_BASE_URL`-Adresse weiter | dekodieren |
| `upload_id` | Media-Store-URL | lokal lesen |
| `task_id` | Ergebnis-URL bzw. lokale Datei über den Media-Store | lokale Datei bzw. Upstream-Referenz (Veo-Extension, Omni-Multi-Turn) |
| `asset_id` | native Asset-ID | nicht unterstützt (400) |

Ohne `PUBLIC_BASE_URL` können Seedance und Kling nur `https://`-URLs nutzen;
andere Quellen führen dann zu `400 public_base_url_required`.

### 7.3 Download externer URLs (SSRF-Schutz)

Wo der Proxy eine URL selbst abruft, gilt:
- nur `https`; der Host wird aufgelöst, private, Loopback-, Link-Local- und
  Multicast-Adressen werden abgelehnt (auch nach jedem Redirect; höchstens 3)
- Größenlimit je Typ (Bild 30 MB, Video 200 MB, Audio 15 MB), Timeout
- der Typ wird über die Dateisignatur geprüft

### 7.4 Limits für `data:`-URIs

Höchstens `MAX_INLINE_REFERENCE_BYTES` (Default 25 MB) dekodiert pro Referenz,
insgesamt höchstens `MAX_UPLOAD_BYTES` pro Request.

---

## 8. Gemeinsame Parameter

### 8.1 Dauer

- `seconds` (OpenAI) und `duration` (Seedance) sind Synonyme. Sind beide
  gesetzt und unterschiedlich, gibt es 400.
- `-1` oder `"auto"`: Das Modell wählt die Dauer (Seedance); bei anderen
  Modellen gilt der Default aus dem Capability-Dokument.
- Kling `text_to_audio`: Float 3.0–10.0 mit einer Nachkommastelle.
- Tasks ohne Dauer (`motion_control`, `edit` bei Kling Omni und Seedance-Edit,
  `lip_sync`, `effect`): `seconds` führt bei `strict` zu 400 und wird bei
  `adapt` ignoriert.

### 8.2 `size`, `resolution`, `aspect_ratio`

- `size` wird übersetzt, indem die Kanten auf das Seitenverhältnis gekürzt und
  der nächstliegende Wert aus `aspect_ratio` gewählt wird. Die Auflösungsstufe
  ergibt sich aus der kürzeren Kante (360 → `360p`, 480/496 → `480p`,
  720 → `720p`, 1080 → `1080p`, ≥ 2160 → `4k`). Die heutige
  Seedance-Tabelle (`SIZE_TO_FORMAT`) bleibt als exakte Zuordnung erhalten.
- Explizite `resolution` und `aspect_ratio` haben Vorrang vor `size`.
- `adaptive`: Seitenverhältnis kommt vom Eingabebild oder -video (Seedance).
  Bei Kling Image-to-Video gibt es kein `aspect_ratio`; das Feld wird bei
  `adapt` ignoriert und bei `strict` abgelehnt, sofern es nicht `adaptive` ist.
- In der Antwort steht `size` als `BREITExHÖHE` gemäß Seedance-Tabelle bzw.
  der tatsächlichen Ausgabe (soweit bekannt).

### 8.3 Ton

`generate_audio` (bool) wird abgebildet auf:
- Seedance `generate_audio`
- Veo auf Vertex `generateAudio` (Gemini API: immer an)
- Kling `audio: native|off` (neue API) bzw. `sound: on|off` (Legacy)
- Omni: immer an; `false` ist bei `strict` ein Fehler
- Bei Kling Omni bedeutet `provider_options.kling.audio = "original"`: Ton des
  Referenzvideos übernehmen

### 8.4 Qualität

`quality` ∈ {`standard`, `pro`} wird abgebildet auf Kling `mode` `std`/`pro`
(Legacy-Endpunkte, Avatar, Multi-Elements). Bei Endpunkten der neuen Kling-API
legt `resolution` die Qualität fest; dort ist `quality` nur ein Alias
(`standard` → 720p, `pro` → 1080p), sofern `resolution` fehlt.

### 8.5 Mehrere Ergebnisse

`n` > 1 ist nur bei Modellen mit `max_outputs` > 1 erlaubt (Veo auf Vertex: 4).
Die Ergebnisse sind über `GET /v1/videos/{id}/content?output=i` abrufbar.
Über LiteLLM ist nur `output=0` erreichbar; Apps, die über LiteLLM mehrere
Varianten brauchen, senden `n` Einzelanfragen.

### 8.6 Shots

```json
{"shot_mode": "customize | intelligence",
 "shots": [{"prompt": "…", "seconds": 3}, {"prompt": "…", "seconds": 2}]}
```
- 1–6 Shots, Shot-Prompt ≤ 512 Zeichen, die Summe der `seconds` muss der
  Gesamtdauer entsprechen (fehlt `seconds` am Request, wird sie gesetzt).
- `shot_mode=intelligence`: kein `shots`, das Modell teilt `prompt` selbst auf.
- Kling neue API: Übersetzung in die Prompt-Syntax `shot n, m, words;`;
  Legacy: `multi_prompt`.

### 8.7 Speech

```json
{"text": "…", "voice": "<voice-id>", "language": "en", "speed": 1.0}
```
Bei `lip_sync` und `avatar` erzeugt der Proxy aus `speech.text` zuerst TTS
(Kling) und verwendet die `audio_id`. Alternativ liefert eine Audio-Referenz
mit Rolle `speech` den Ton.

### 8.8 AudioOptions

| Feld | Task | Kling-Feld |
|---|---|---|
| `start_ms`, `end_ms` | `lip_sync` | `sound_start_time`, `sound_end_time` |
| `insert_at_ms` | `lip_sync` | `sound_insert_time` (Default 0) |
| `volume` | `lip_sync` | `sound_volume` (0–2) |
| `original_volume` | `lip_sync` | `original_audio_volume` (0–2) |
| `face_id` | `lip_sync` | Auswahl aus `identify-face`; Default: die Person mit dem längsten Intervall |
| `bgm_prompt` | `video_to_audio` | `bgm_prompt` |
| `asmr` | `video_to_audio` | `asmr_mode` |

### 8.9 Selections (`multi_element_edit`)

```json
[{"frame_index": 0, "points": [{"x": 0.42, "y": 0.55}]}]
```
Höchstens 10 Frames mit je höchstens 10 Punkten; Koordinaten in [0, 1].
Bilder für `addition` (1–2) und `swap` (1) kommen als Referenzen mit Rolle
`reference`.

### 8.10 CommerceFields

```json
{"title": "…", "description": "…", "script": "…", "speech_rate": 1.0,
 "bgm": true, "product_info": "…", "avatar_id": "…"}
```
Zuordnung zu den Kling-Solution-Feldern in Abschnitt 16.3.

---

## 9. Validierung und `parameter_policy`

- **`strict`**: Jeder nicht unterstützte Wert führt zu `400` mit einer Meldung,
  die die erlaubten Werte nennt.
- **`adapt`**: Der Proxy passt Werte an das Modell an und lehnt nur ab, was
  sich nicht sinnvoll anpassen lässt (z. B. ein fehlendes Pflichtbild). Regeln:
  - Zahlen: nächster erlaubter Wert (bei Gleichstand der größere)
  - Auflösung: nächste erlaubte Stufe, bevorzugt nach unten
  - Seitenverhältnis: nächstliegendes erlaubtes Verhältnis
  - nicht unterstützte optionale Felder: verworfen; `negative_prompt` wird bei
    Omni als „Avoid: …“ an den Prompt angehängt
  - Erzwungene Werte (z. B. Veo 8 s bei Referenzen) werden gesetzt
- Jede Anpassung wird im Job unter `adjustments[]` gespeichert
  (`{field, requested, applied, reason}`) und in der Direkt-Antwort
  zurückgegeben.
- Default: **`strict`** (Abnahme, Abschnitt 21); per
  `DEFAULT_PARAMETER_POLICY` konfigurierbar. Die gültigen Werte jedes Modells
  stehen im Capability-Dokument, damit Clients vorab prüfen können.

---

## 10. `provider_options`

```json
{"provider_options": {"kling": {"camera_control": {…}}, "google": {"compressionQuality": "lossless"}, "modelark": {"service_tier": "flex"}}}
```

- Nur der Block des Zielproviders wird ausgewertet; andere Blöcke werden
  ignoriert. So kann eine App für mehrere Provider gleichzeitig Optionen
  mitschicken und trotzdem das Modell wechseln.
- Schlüssel werden **unverändert** in den nativen Request gemischt (bei Kling
  neue API in `settings`/`options` nach Feldname; Google in `parameters` bzw.
  `response_format`; ModelArk auf oberster Ebene).
- Je Provider gibt es eine **Allowlist** dokumentierter nativer Felder.
  Unbekannte Schlüssel → `400 unsupported_parameter` (bei `adapt`: ignoriert).
  Felder, die der Proxy selbst verwaltet (Auth, Modell, Callback,
  `storageUri`, `external_task_id`), sind gesperrt.
- Werte aus `provider_options` überschreiben einheitlich abgebildete Werte.

---

## 11. Antworten

### 11.1 Video-Objekt

```json
{
  "id": "video_…",
  "object": "video",
  "model": "veo-3.1-fast-generate-001",
  "status": "queued | in_progress | completed | failed",
  "progress": 0,
  "created_at": 1791720000,
  "completed_at": null,
  "expires_at": null,
  "seconds": "8",
  "size": "1280x720",
  "error": null,
  "usage": {"provider": "google", "backend": "vertex", "units": null},
  "remixed_from_video_id": null,

  "provider": "google",
  "task": "text_to_video",
  "provider_status": "running",
  "outputs": [{"index": 0, "variants": ["video"], "mime_type": "video/mp4", "seconds": 8}],
  "adjustments": [],
  "last_frame_available": false,
  "metadata": {}
}
```

- Felder **oberhalb** der Leerzeile überleben LiteLLM. Die übrigen sind nur bei
  Direktaufrufen sichtbar (LiteLLM verwirft sie).
- `progress`: Schätzung. 0 bei `queued`, ab 50 bei `in_progress` (sofern der
  Provider keinen Wert liefert), 100 bei Abschluss.
- `expires_at`: Zeitpunkt, ab dem das Ergebnis nicht mehr abrufbar ist
  (Provider-Aufbewahrung bzw. Output-TTL des Proxys).
- `usage` ist ein freies Objekt und überlebt LiteLLM. Es enthält Provider,
  Backend und, soweit bekannt, Verbrauchsangaben (Omni-Tokens, Kling-Units,
  Seedance-Usage).

### 11.2 Status-Abbildung

| Einheitlich | Seedance | Veo | Omni | Kling (neu / Legacy) |
|---|---|---|---|---|
| `queued` | `queued` | (Operation angelegt, `done` fehlt, noch nie gepollt) | `queued` | `submitted` |
| `in_progress` | `running` | `done=false` | `in_progress`, `requires_action` | `processing` |
| `completed` | `succeeded` | `done=true`, ≥ 1 Video | `completed` | `succeeded` / `succeed` |
| `failed` | `failed`, `cancelled`, `expired` | `error` gesetzt oder 0 Videos (RAI) | `failed`, `cancelled`, `incomplete` | `failed` |

Mehrstufige Jobs (Lip Sync, Multi-Elements, Real-Human) sind `in_progress`,
bis der letzte Schritt abgeschlossen ist; `provider_status` nennt den Schritt
(z. B. `face_identification`, `asset_processing`).

### 11.3 Fehler

Fehler-Antworten (HTTP ≥ 400) und `error` im Video-Objekt haben dieselbe Form:

```json
{"error": {"code": "content_policy", "message": "…", "type": "invalid_request_error", "param": "prompt", "provider_code": "1301", "retryable": false}}
```

| `code` | HTTP | Bedeutung | Quellen |
|---|---|---|---|
| `invalid_request` | 400 | Formfehler, Typfehler | – |
| `unsupported_task` | 400 | Modell kann den Task nicht | – |
| `unsupported_parameter` | 400 | Feld oder Wert vom Modell nicht unterstützt | – |
| `reference_limit` | 400 | Anzahl, Dauer, Größe oder Format einer Referenz verletzt | – |
| `reference_unavailable` | 400 | Referenz-URL nicht abrufbar, Quelljob abgelaufen | – |
| `public_base_url_required` | 400 | Upload-Weg ohne `PUBLIC_BASE_URL` | – |
| `content_policy` | 400 | Inhaltsfilter (Eingabe oder Ausgabe) | Kling 1300/1301, Veo RAI, Seedance Sensitive-Content, Omni Safety |
| `region_restricted` | 400 | Funktion in der Region gesperrt | Omni-Edit/Extend in EWR/CH/UK, `personGeneration` |
| `model_unavailable` | 404 | Modell unbekannt, abgekündigt oder nicht freigeschaltet | Kling 1203, Google 404 |
| `invalid_api_key` | 401 | Proxy-Key falsch | – |
| `upstream_credentials_invalid` | 503 | Provider-Credentials ungültig | – |
| `upstream_credentials_unavailable` | 503 | Provider-Credentials noch nicht geprüft | – |
| `upstream_forbidden` | 403 | Provider verweigert Zugriff | Kling 1103, Google 403 |
| `billing` | 402 | Guthaben oder Paket leer | Kling 1101/1102, Google Billing |
| `rate_limited` | 429 | Rate- oder Parallelitätslimit (`retryable=true`) | Kling 1302/1303, Google 429, ModelArk 429 |
| `upstream_error` | 502 | Provider-Fehler (`retryable` je nach Fall) | 5xx |
| `upstream_timeout` | 504 | Zeitüberschreitung | – |
| `video_not_ready` | 409 | Ergebnis noch nicht fertig | – |
| `output_expired` | 410 | Ergebnis abgelaufen | – |
| `interrupted` | – (nur im Job) | Job durch Neustart verloren | – |

### 11.4 Ausgehende Webhooks (`webhook_url`)

Ist `webhook_url` gesetzt, sendet der Proxy bei jedem Wechsel auf
`in_progress`, `completed` oder `failed` einen `POST` mit dem Video-Objekt.
Format und Signatur folgen *Standard Webhooks* (`webhook-id`,
`webhook-timestamp`, `webhook-signature`; Secret `WEBHOOK_SECRET`), mit
Wiederholungen bei Fehlern. Der Event-Typ lautet `video.in_progress`,
`video.completed` bzw. `video.failed` (OpenAI-Namen). Provider-eigene
Callbacks nutzt der Proxy nicht; er pollt.

- Ohne konfiguriertes `WEBHOOK_SECRET` wird `webhook_url` mit
  `400 invalid_request` abgelehnt; es gehen nie unsignierte Webhooks raus.
- Ziele müssen `https` sein und dürfen nicht auf private, Loopback- oder
  Link-Local-Adressen auflösen.
- `callback_url` bleibt das native Seedance-Feld (Abschnitt 17): ModelArk ruft
  den Client dann direkt im ModelArk-Format auf.

### 11.5 Liste

`GET /v1/videos?limit=&after=&order=&model=&status=&provider=` liefert
`{object:"list", data, first_id, last_id, has_more}` über ModelArk-Tasks und
das lokale Register. Die bisherigen Parameter (`page_num`, `page_size`,
`filter.*`) bleiben gültig. Fällt ein Provider aus, enthält die Antwort die
übrigen Einträge und `warnings[]`.

### 11.6 Löschen

| Provider | Wirkung |
|---|---|
| Seedance | `DELETE` beim Provider (wie heute) |
| Omni | `cancel` beim Provider, sofern laufend (Teilkosten möglich), dann lokal löschen |
| Veo, Kling | nur lokal löschen; der Provider-Job läuft weiter und wird berechnet |

Antwort: `{id, object:"video.deleted", deleted:true}`. Bisherige
Seedance-Clients erhalten zusätzlich die bisherigen Felder.

### 11.7 Content

`GET /v1/videos/{id}/content?variant=&output=`

| `variant` | Inhalt |
|---|---|
| `video` (Default) | Hauptergebnis (MIME aus der Datei: `video/mp4` oder `video/quicktime`) |
| `audio` | Tonspur bzw. Audio-Ergebnis (`audio/mpeg`; `?format=wav` liefert WAV, falls vorhanden) |
| `watermarked` | Version mit Wasserzeichen (Kling, falls angefordert) |
| `last_frame` | wie `/last_frame` (Seedance) |
| `thumbnail`, `spritesheet` | nicht unterstützt → `400 unsupported_parameter` |

Über LiteLLM kommt immer das Hauptergebnis an, und LiteLLM meldet stets
`video/mp4` als Typ; die Bytes stimmen trotzdem (auch bei `text_to_audio`).

---

## 12. Modell-IDs

### 12.1 Echte Modelle

| Provider | IDs (Beispiele) | Hinweise |
|---|---|---|
| ModelArk | `dreamina-seedance-2-5-260628`, `dreamina-seedance-2-0-fast-260128`, `seedance-1-5-pro-…` | dynamisch aus ModelArk; Familie über das Datumssuffix |
| Google Veo | `veo-3.1-generate-001`, `veo-3.1-fast-generate-001`, `veo-3.1-lite-generate-001` (Vertex); `veo-3.1-*-generate-preview` (Gemini API bis 22.10.2026) | dynamisch je Backend |
| Google Omni | `gemini-omni-1.1-flash` (Gemini API), `gemini-omni-1.1-flash-preview`, `gemini-omni-flash-preview` (Vertex) | dynamisch je Backend |
| Kling | `kling-3.0-turbo`, `kling-3.0`, `kling-3.0-omni`, `kling-o1`, `kling-2.6`, `kling-2.5-turbo` | Aliase: `kling-v3`, `kling-v3-omni`, `kling-video-o1`, `kling-v2-6`, `kling-v2-5-turbo` |

### 12.2 Virtuelle Modelle (Funktionen ohne Modellwahl)

| ID | Tasks |
|---|---|
| `kling-lip-sync` | `lip_sync` |
| `kling-avatar` | `avatar` |
| `kling-effects` | `effect` |
| `kling-multi-elements` | `multi_element_edit` |
| `kling-video-to-audio` | `video_to_audio` |
| `kling-text-to-audio` | `text_to_audio` |
| `kling-tts` | nur `/v1/audio/speech` |
| `kling-commerce` | `commerce_talking_agent`, `commerce_goods_studio`, `commerce_apparel` |

Virtuelle Modelle erscheinen in `/v1/models` mit `"virtual": true` und lassen
sich in LiteLLM wie echte Modelle registrieren.

### 12.3 Routing

Präfixtabelle (erste Übereinstimmung): `veo-` → Google Veo,
`gemini-omni-` → Google Omni, `kling-` → Kling, alles andere → ModelArk.
Bei Omni mit beiden konfigurierten Backends: GA-ID → Gemini API,
`-preview`-IDs → Vertex, sofern `GOOGLE_OMNI_BACKEND=both`; sonst das
konfigurierte Backend.

---

## 13. Capability-Dokument v2

`GET /v1/models` (und `model_info.capabilities` im LiteLLM-Export):

```json
{
  "id": "veo-3.1-fast-generate-001",
  "object": "model",
  "owned_by": "google",
  "name": "Veo 3.1 Fast",
  "virtual": false,
  "links": {"prompt_guide": "/v1/prompt-guides/veo_3_1"},
  "capabilities": {
    "schema_version": 2,
    "provider": "google",
    "backend": "vertex",
    "family": "veo-3.1-fast",
    "launch_stage": "ga",
    "prompt": {"max_chars": 4000, "required": true},
    "outputs": {"max": 4, "types": ["video"]},
    "parameters": {
      "seconds": {"values": [4, 6, 8], "default": 8},
      "resolution": {"values": ["720p", "1080p"], "default": "720p"},
      "aspect_ratio": {"values": ["16:9", "9:16"], "default": "16:9"},
      "generate_audio": {"default": true},
      "negative_prompt": {},
      "seed": {"min": 0, "max": 4294967295},
      "enhance_prompt": {"default": true},
      "person_generation": {"values": ["allow_adult", "allow_all", "dont_allow"], "default": "allow_adult"}
    },
    "tasks": {
      "text_to_video": {},
      "image_to_video": {"references": [{"role": "first_frame", "types": ["image"], "min": 1, "max": 1, "max_bytes": 20971520, "formats": ["image/jpeg", "image/png"]}]},
      "first_last_frame": {"references": [
        {"role": "first_frame", "types": ["image"], "min": 1, "max": 1},
        {"role": "last_frame", "types": ["image"], "min": 1, "max": 1}]},
      "reference_to_video": {
        "references": [{"role": "reference", "types": ["image"], "min": 1, "max": 3}],
        "parameters": {"seconds": {"values": [8]}}},
      "extend": {"references": [{"role": "base_video", "types": ["video"], "min": 1, "max": 1, "min_seconds": 1, "max_seconds": 30}]}
    },
    "constraints": [
      {"if": {"resolution": ["1080p", "4k"]}, "then": {"seconds": [8]}, "message": "1080p und 4k erfordern 8 Sekunden"}
    ],
    "continuation": "video_extension",
    "features": {"real_human": false, "last_frame_output": false, "watermark": false, "callback": true},
    "provider_options": ["compressionQuality", "resizeMode"]
  }
}
```

Regeln:
- `parameters` gelten modellweit; `tasks.<task>.parameters` überschreiben sie
  für diesen Task (Schnittmenge).
- `constraints` sind bedingte Einschränkungen: Erfüllt der Request alle
  `if`-Bedingungen, gelten die `then`-Werte. Die UI wertet sie aus, der Proxy
  ebenso.
- Reference-Slots: `role`, `types`, `min`, `max` und optional `max_bytes`,
  `formats`, `min_seconds`, `max_seconds`, `total_max_seconds`, `min_px`,
  `max_px`, `aspect_range`.
- Gruppenlimits (z. B. Kling Omni „Bilder + Elements ≤ 7“) stehen als
  `"limits": [{"roles": ["reference"], "types": ["image", "element"], "max": 7, "if": {"has_video": false}}]`
  im Task.
- `continuation` ∈ {`last_frame`, `video_extension`, `multi_turn`, `none`}
  steuert den „Fortsetzen“-Weg der UI.
- Felder aus v1 (`resolutions`, `ratios`, `durations`, `defaults`,
  `reference_limits`, `task_types`, `supports_frames` …) bleiben für
  Seedance-Modelle zusätzlich erhalten, damit bestehende Clients
  weiterlaufen.

`GET /v1/models/{id}` liefert dasselbe Objekt plus
`prompt_guide: {id, title, updated, language, markdown}`.

---

## 14. Prompt Guides

- Ablage: `prompt_guides/<guide>.md` plus `prompt_guides/manifest.yaml`:

  ```yaml
  guides:
    - id: veo_3_1
      file: veo_3_1.md
      title: Veo 3.1 Prompting Guide
      language: de
      updated: 2026-09-04
      models: [veo-3.1-]      # Modell-ID-Präfixe
  ```
- `GET /v1/prompt-guides` → `{object:"list", data:[{id, title, language, updated, models, url}]}`
- `GET /v1/prompt-guides/{id}` → `text/markdown; charset=utf-8`; mit
  `Accept: application/json` → `{id, title, …, markdown}`.
- Zuordnung Modell → Guide über die Präfixe in `models`; der längste passende
  Präfix gewinnt, ein Modell hat höchstens einen Guide. Modelle ohne Guide:
  `links.prompt_guide = null`.
- Authentifizierung wie alle anderen Routen (Proxy-Key).

---

## 15. LiteLLM-Export

`GET /v1/litellm/config?format=yaml|json&name_template=&api_base=`

- Erzeugt für jedes aktive Modell (inkl. virtueller Modelle) einen
  `model_list`-Eintrag:

  ```yaml
  - model_name: veo_31_fast_api            # aus name_template
    litellm_params:
      model: openai/veo-3.1-fast-generate-001
      api_base: https://modelark.marcmeese.de/v1
      api_key: os.environ/MODELARK_PROXY_API_KEY
    model_info:
      mode: video_generation               # audio_speech für kling-tts
      provider: google
      capabilities: {…}                    # Abschnitt 13
      prompt_guide: "…Markdown-Volltext…"
      prompt_guide_url: https://modelark.marcmeese.de/v1/prompt-guides/veo_3_1
  ```
- `name_template` (Default `{family_slug}_api`) bildet das bestehende
  Namensschema nach (z. B. `seedance_25_api`).
- Der Export schreibt nichts in LiteLLM; er erzeugt nur die Config.
- Apps lesen Capabilities und Guide über LiteLLM mit `GET /v1/model/info`
  (Filter auf `model_name` clientseitig).

---

## 16. Native Routen

### 16.1 Gemeinsame Regeln

- Request-Body: nativer Body des Providers, ohne Auth und ohne Callback
  (setzt der Proxy). Referenzen dürfen zusätzlich `ref-…`-IDs und `data:`-URIs
  verwenden; der Proxy ersetzt sie durch die vom Provider erwartete Form.
- Antwort auf Create: die native Antwort des Providers plus
  `{"proxy": {"id": "video_…", "status_url": "/v1/videos/video_…"}}`. Jeder
  native Generierungsjob landet im Jobregister und ist über
  `/v1/videos/{id}` und `/content` abrufbar.
- Native `GET`-Abfragen geben die native Antwort zurück; Ergebnis-URLs werden
  durch Proxy-URLs ersetzt (Kling-URLs sind hotlink-geschützt).

### 16.2 ModelArk

| Pfad | Native Entsprechung |
|---|---|
| `POST /v1/providers/modelark/tasks` | `POST /contents/generations/tasks` (rohes `content`-Array) |
| `GET /v1/providers/modelark/tasks[/{id}]`, `DELETE …/{id}` | Abfrage, Liste, Löschen |

Die Real-Human-Assets laufen über `/v1/assets` bzw. das bestehende
`real_human`-Flag.

### 16.3 Google

| Pfad | Native Entsprechung |
|---|---|
| `POST /v1/providers/google/veo/{model}:predictLongRunning` | Veo-Request (`instances`, `parameters`) über das konfigurierte Backend |
| `GET /v1/providers/google/veo/operations/{proxy-id}` | Operation-Status (Gemini `GET` bzw. Vertex `fetchPredictOperation`) |
| `POST /v1/providers/google/interactions` | Omni-Interaction (`background` wird erzwungen) |
| `GET /v1/providers/google/interactions/{proxy-id}`, `POST …/cancel`, `DELETE …` | Abfrage, Abbruch, Löschen |

### 16.4 Kling

| Pfad | Native Entsprechung |
|---|---|
| `POST /v1/providers/kling/{text-to-video\|image-to-video\|omni-video\|motion-control}/{model}` | neue API |
| `POST /v1/providers/kling/v1/videos/{text2video\|image2video\|omni-video\|motion-control}` | Legacy-API |
| `POST /v1/providers/kling/v1/videos/avatar/image2video` | Avatar |
| `POST /v1/providers/kling/v1/videos/identify-face` | Gesichtserkennung (synchron, kostenpflichtig) |
| `POST /v1/providers/kling/v1/videos/advanced-lip-sync` | Lip Sync |
| `POST /v1/providers/kling/v1/videos/effects` | Effekte |
| `GET /v1/providers/kling/effects` | Effekt-Katalog (vom Proxy gepflegt: ID, Name, Bildanzahl) |
| `POST /v1/providers/kling/v1/videos/multi-elements/{init-selection\|add-selection\|delete-selection\|clear-selection\|preview-selection}` | Multi-Element-Session (für interaktive Auswahl in der UI) |
| `POST /v1/providers/kling/v1/videos/multi-elements` | Multi-Element-Create |
| `POST /v1/providers/kling/v1/videos/image-recognize` | Bilderkennung (Hilfsfunktion) |
| `POST /v1/providers/kling/v1/audio/{tts\|text-to-audio\|video-to-audio}` | Audio |
| `POST/GET /v1/providers/kling/v1/general/{advanced-custom-elements\|advanced-presets-elements\|custom-voices\|presets-voices}`, `POST …/{delete-advanced-elements\|delete-voices}` | Elements und Voices |
| `POST /v1/providers/kling/v1/general/ai-multi-shot` | Zusatzansichten für Elements |
| `POST /v1/providers/kling/solutions/{talking_agent\|e-commerce/goods_studio\|e-commerce/clothing_dupe}` | Video-Commerce |
| `GET /v1/providers/kling/tasks?task_ids=…`, `GET /v1/providers/kling/v1/…/{task_id}` | Abfragen |
| `GET /v1/providers/kling/account/costs` | Ressourcenpakete (höchstens 1 QPS, vom Proxy gedrosselt) |

Bewusst **nicht** angeboten: Bild-Endpunkte, `/solutions/virtual_try_on`
(Entscheidung des Nutzers) sowie die nicht mehr dokumentierten Endpunkte
(Abschnitt 20).

---

## 17. Kompatibilität mit bestehenden Seedance-Clients

| Bestehendes Feld | Bedeutung im neuen Vertrag |
|---|---|
| `input_reference_url` (+ `_media_type`, `_role`) | eine Referenz mit `url`, `type`, `role` |
| `input_reference_task_id` | eine Referenz `{task_id, role: "first_frame"}` mit dem letzten Frame (Seedance-Weg); bei `continuation=video_extension` → `task=extend` |
| `reference_urls[]` (String oder `{url, media_type, role, real_human}`) | `references[]` |
| `content[]` (rohes ModelArk-Array) | nur bei ModelArk; bei anderen Providern `400 unsupported_parameter` |
| `omni_reference_task_type` (`auto`, `reference`, `edit`, `extend`) | `task` (`auto` = Ableitung) |
| `ratio` | `aspect_ratio` |
| `duration`, `frames`, `camera_fixed`, `service_tier`, `execution_expires_after`, `priority`, `safety_identifier` | ModelArk-Felder; bei anderen Providern 400 bzw. bei `adapt` ignoriert |
| `real_human` (oberste Ebene) | gilt für `input_reference_url` bzw. den Upload |
| `callback_url` | unverändert an ModelArk durchgereicht (nativer Callback); für einheitliche Webhooks dient `webhook_url` |
| Antwortfelder `provider_status`, `last_frame_available`, `service_tier` | bleiben erhalten |
| `GET /v1/videos?page_num&page_size&filter.*` | bleibt gültig |
| IDs `cgt-…` | werden weiter angenommen; Antworten enthalten künftig `video_…` (3.1) |

**Verhaltensänderung:** Antworten enthalten IDs im `video_…`-Format.
Direkt-Clients, die IDs mit `cgt-` vergleichen, müssen umgestellt werden; das
UI-Backend wird in T4 angepasst.

---

## 18. Nutzung über LiteLLM (Leitfaden für Apps)

1. Modell in LiteLLM aus dem Export registrieren (Abschnitt 15).
2. Metadaten und Guide: `GET /v1/model/info` → `model_info.capabilities`,
   `model_info.prompt_guide`.
3. Create: alle Felder aus 5.1 auf oberster Ebene; **strukturierte Felder als
   JSON-String** senden.
4. Dateien: als `data:`-URI in `references[].url` oder als öffentliche
   `https`-URL. Für genau eine Bilddatei geht auch `input_reference` als
   Multipart-Datei.
5. Remix, Edits, Extensions: zusätzliche Felder **nur in `extra_body`**.
6. Status und Content: `GET /v1/videos/{id}` und `…/content` mit der ID aus
   der Create-Antwort.
7. Nicht über LiteLLM erreichbar: Liste, Löschen, `variant`, `output > 0`,
   `last_frame`, Assets, Guides als Ressource. Diese Funktionen sind direkt
   beim Proxy mit dem Proxy-Key nutzbar.
8. Statusdetails bei Fehlern stehen in `error.code` und `error.message`;
   Provider und Backend stehen in `usage`.

---

## 19. Task × Modell-Matrix

✔ = unterstützt, – = nicht unterstützt. Detailregeln stehen im
Capability-Dokument des jeweiligen Modells.

| Task | Seedance 2.5 | Seedance 2.0 / Fast / Mini | Seedance 1.x | Veo 3.1 / Fast | Veo 3.1 Lite | Omni 1.1 | Omni Flash Preview (Vertex) | Kling 3.0 Turbo | Kling 3.0 | Kling 3.0 Omni | Kling O1 | Kling 2.6 | Kling 2.5 Turbo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `text_to_video` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `image_to_video` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | – | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `first_last_frame` | ✔ | ✔ | 1.0 Pro ✔ | ✔ | ✔ | ✔ | – | – | ✔ | ✔ | ✔ | ✔ (1080p) | ✔ (1080p) |
| `reference_to_video` | ✔ (Bild/Video/Audio) | ✔ | – | ✔ (≤ 3 Bilder, 8 s) | – | ✔ (Bilder, ≤ 3 Videos) | – | – | Elements | ✔ | ✔ | Voices | – |
| `multi_shot` | – | – | – | – | – | – | – | ✔ (Prompt-Syntax) | ✔ | ✔ | – | – | – |
| `edit` | ✔ | ✔ (ohne Task-Typ) | – | – | – | ✔ | ✔ | – | – | ✔ | ✔ | – | – |
| `extend` | ✔ | ✔ (ohne Task-Typ) | – | ✔ | Vertex ✔ | ✔ | – | – | – | – | – | – | – |
| `stitch` | ✔ | ✔ | – | – | – | – | – | – | – | – | – | – | – |
| `motion_control` | – | – | – | – | – | – | – | – | ✔ | – | – | ✔ | – |

Virtuelle Kling-Modelle: `lip_sync`, `avatar`, `effect`,
`multi_element_edit`, `video_to_audio`, `text_to_audio`, TTS, Commerce
(Abschnitt 12.2). Seedance 1.x wird in T22 genau erhoben; die Spalte ist
vorläufig.

---

## 20. Abdeckung der Recherche

Jede Fähigkeit aus den Research-Berichten ist genau einer Stelle zugeordnet.

| Fähigkeit | Abbildung |
|---|---|
| **Veo** T2V, I2V, First/Last, Referenzbilder (asset) | Tasks 6.1 |
| Veo Extension (Gemini: Veo-Video ≤ 2 Tage; Vertex: Upload 1–30 s) | `extend`; Quelle `task_id` oder Upload |
| Veo `aspectRatio`, `resolution`, `durationSeconds`, `seed`, `personGeneration`, `negativePrompt`, `generateAudio`, `enhancePrompt`, `sampleCount` | 5.1 / 8.x |
| Veo `compressionQuality`, `resizeMode`, `pubsubTopic`, `fps` | `provider_options.google` (`pubsubTopic` gesperrt, Proxy pollt) |
| Veo `storageUri` | gesperrt; der Proxy nutzt Inline-Bytes (ADR-001) |
| Veo `mask` (insert/remove/outpaint), `task: upscale`, `cameraControl`, Style-Referenz | **nicht angeboten**: für 3.1 nicht dokumentiert bzw. nicht unterstützt |
| **Omni** T2V, I2V, First/Last, Referenzbilder, Videoreferenzen, Edit, Extend, Multi-Turn | Tasks; Multi-Turn über `task_id`/Remix |
| Omni `response_format` (`aspect_ratio`, `resolution` inkl. 360p, `duration`, `delivery`) | 5.1; `delivery` verwaltet der Proxy |
| Omni `stream` | nicht angeboten (Proxy nutzt `background`) |
| Omni `cancel`, `delete` | `DELETE /v1/videos/{id}` |
| **Kling** T2V, I2V, First/Last, Multi-Shot, native Audio, Voices, Elements | Tasks, Referenzen `element`/`voice` |
| Kling Omni `refer_image`, `feature_video`, `base_video`, `audio: original` | `reference_to_video`, `edit`, `provider_options.kling.audio` |
| Kling Motion Control (`character_orientation`, `keep_original_sound`) | `motion_control`; `provider_options.kling` |
| Kling Avatar, TTS, Lip Sync (inkl. Face Identification), Text-to-Audio, Video-to-Audio | virtuelle Modelle, 8.7/8.8, `/v1/audio/speech` |
| Kling Effects (219), Multi-Elements, Image Recognition, AI Multi-Shot | `effect`, `multi_element_edit`, native Routen |
| Kling Elements, Voices (Custom/Preset, CRUD) | `/v1/assets`, native Routen |
| Kling Commerce (Talking Agent, Goods Studio, Apparel) | Commerce-Tasks |
| Kling `watermark_info`, `external_task_id`, `callback_url` | `watermark`; `external_task_id` verwaltet der Proxy; Benachrichtigung über `webhook_url` |
| Kling Account (Costs, Billing) | Health; `/v1/providers/kling/account/costs` |
| Kling Video-Extend, Multi-Image2Video, `camera_control`, Motion Brush, Legacy-Lip-Sync, alte Elements | **nicht angeboten**: nicht mehr dokumentiert; die Felder stehen auch nicht in der `provider_options`-Allowlist |
| Kling Bild-Endpunkte, Virtual Try-On | **ausgeschlossen** (Nutzerentscheidung) |
| **Seedance** alle heutigen Felder | Abschnitt 17; Vollständigkeit prüft T22 |
| OpenAI Remix, Edits, Extensions, Characters | 5.2, 2.1 |
| OpenAI `variant` thumbnail/spritesheet | nicht unterstützt (kein Provider liefert sie) |

---

## 21. Entscheidungen der Abnahme (11.10.2026)

1. **`parameter_policy`-Default ist `strict`.** Nicht unterstützte Werte
   führen zu `400` mit den erlaubten Werten. Clients prüfen die gültigen
   Werte vorab über das Capability-Dokument (`/v1/models` bzw.
   `model_info.capabilities` über LiteLLM). `adapt` bleibt pro Request
   wählbar.
2. **Alle Antworten liefern IDs im `video_…`-Format** (Abschnitt 3.1);
   eingehend werden beide Formen akzeptiert.
3. **Ausgehende Webhooks** (Abschnitt 11.4) werden umgesetzt (Task T6b),
   über das eigene Feld `webhook_url`; `callback_url` bleibt Seedance-nativ.
