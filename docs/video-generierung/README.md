# Video-Generierung

Jeder Anbieter arbeitet asynchron. Ein `POST /v1/videos` erzeugt zunächst eine
Video-ID; danach wird gepollt und das Ergebnis heruntergeladen. Alle Modelle
nehmen dieselben Felder an (Vertrag: [SPEC.md](../SPEC.md)); ein Modellwechsel
ändert nur `model`. Was ein Modell kann, steht im Capability-Dokument unter
`GET /v1/models` (`capabilities.tasks`, `parameters`, `constraints`).

## Tasks und Modelle

`task` ist optional und wird sonst aus den Referenzrollen und Feldern abgeleitet
(Reihenfolge: `effect`, `selections`, Rolle `motion`, `shots`, `base_video` mit
Sprache, `base_video`, `first_frame`+`last_frame`, genau ein Bild,
irgendeine Referenz, sonst `text_to_video`).

Verfügbarkeit laut Capability-Profilen im Code (✔ = angeboten, – = nicht):

| Task | Seedance 2.x | Seedance 1.x | Veo 3.1 / Fast | Veo 3.1 Lite | Omni 1.1 Flash | Omni Flash Preview | Kling 3.0 | Kling 3.0 Turbo | Kling 3.0 Omni | Kling O1 | Kling 2.6 | Kling 2.5 Turbo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `text_to_video` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `image_to_video` | ✔ | ✔ | ✔ | ✔ | ✔ | – | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `first_last_frame` | ✔ | 1.5 Pro, 1.0 Pro | ✔ | ✔ | ✔ | – | ✔ | – | ✔ | ✔ | ✔ (1080p) | ✔ (1080p) |
| `reference_to_video` | ✔ | – | ✔ | – | ✔ | – | – | – | ✔ | ✔ | – | – |
| `multi_shot` | – | – | – | – | – | – | ✔ | ✔ | ✔ | – | – | – |
| `edit` | ✔ | – | – | – | ✔ | ✔ | – | – | ✔ | ✔ | – | – |
| `extend` | ✔ | – | ✔ | Vertex ✔ | ✔ | – | – | – | – | – | – | – |
| `stitch` | ✔ | – | – | – | – | – | – | – | – | – | – | – |
| `motion_control` | – | – | – | – | – | – | ✔ | – | – | – | ✔ | – |

Die Kling-Werkzeuge sind virtuelle Modelle: `kling-lip-sync` (`lip_sync`),
`kling-avatar` (`avatar`), `kling-effects` (`effect`), `kling-multi-elements`
(`multi_element_edit`), `kling-video-to-audio`, `kling-text-to-audio`,
`kling-commerce` (`commerce_talking_agent`, `commerce_goods_studio`,
`commerce_apparel`) und `kling-tts` (nur `/v1/audio/speech`).

Beispiele für den einheitlichen Request:

```json
{
  "model": "kling-3.0",
  "task": "first_last_frame",
  "prompt": "Eine weiche Kamerafahrt zwischen beiden Szenen",
  "references": [
    {"type": "image", "role": "first_frame", "url": "https://media.example/first.png"},
    {"type": "image", "role": "last_frame", "url": "https://media.example/last.png"}
  ],
  "seconds": 6,
  "resolution": "1080p"
}
```

```json
{
  "model": "veo-3.1-generate-001",
  "prompt": "Cinematic macro shot of rain on a red leaf",
  "seconds": 8,
  "resolution": "720p",
  "aspect_ratio": "16:9",
  "n": 2
}
```

## Gemeinsame Parameter

- **Dauer:** `seconds` und `duration` sind Synonyme (widersprüchliche Werte ergeben
  400). `"auto"` oder `-1` bedeutet bei Seedance automatische Dauer. Tasks ohne
  Dauer (z. B. `motion_control`, Kling-`edit`) lehnen `seconds` bei `strict` ab.
- **Format:** `size` (`BREITExHÖHE`) wird in `resolution` und `aspect_ratio`
  übersetzt; explizite Felder haben Vorrang. Bei Kling-Image-Tasks folgt das
  Seitenverhältnis dem Bild (`adaptive`).
- **Ton:** `generate_audio` wird je Modell abgebildet (Seedance, Veo auf Vertex,
  Kling `audio`/`sound`). Omni erzeugt immer Ton.
- **`parameter_policy`:** `strict` (Standard, änderbar über `DEFAULT_PARAMETER_POLICY`) lehnt nicht unterstützte Werte mit
  400 und den erlaubten Werten ab. `adapt` wählt den nächsten erlaubten Wert
  (Zahlen: bei Gleichstand der größere; Auflösung: bevorzugt nach unten), verwirft
  nicht unterstützte optionale Felder und schreibt jede Änderung nach
  `adjustments[]` (`field`, `requested`, `applied`, `reason`).
- **Mehrere Ergebnisse:** `n` bis `outputs.max` (Veo auf Vertex 4). Abruf über
  `/content?output=i`.
- **Anbieterfelder:** `provider_options.<anbieter>`; nur der Block des Zielmodells
  wird ausgewertet, unbekannte Schlüssel ergeben 400.

## Seedance-Regeln

Seedance akzeptiert sowohl den einheitlichen Vertrag (`references`, `task`,
`aspect_ratio`, `seconds: "auto"`) als auch die bisherigen Felder
(`reference_urls`, `ratio`, `duration`, `omni_reference_task_type`, `content`).
Im einheitlichen Pfad werden Rollen auf `first_frame`, `last_frame` oder
`reference_image`/`reference_video`/`reference_audio` abgebildet; `edit`, `extend`,
`remix` und `stitch` werden zu Referenzvideos, bei Seedance 2.5 zusätzlich mit
`omni_reference_task_type` (`edit`, `extend`; `stitch` wird zu `extend`).

### Text-to-Video

```json
{
  "model": "dreamina-seedance-2-0-fast-260128",
  "prompt": "Cinematic macro shot of rain on a red leaf",
  "duration": 5,
  "resolution": "720p",
  "ratio": "16:9",
  "generate_audio": true
}
```

### First-Frame und First-/Last-Frame

Eine Bildreferenz mit Rolle `first_frame` startet das Video exakt aus diesem
Bild; ein zweites Bild mit `last_frame` legt das Endbild fest:

```json
{
  "prompt": "A smooth camera transition between both scenes",
  "reference_urls": [
    {"url":"https://media.example/first.png", "media_type":"image", "role":"first_frame"},
    {"url":"https://media.example/last.png", "media_type":"image", "role":"last_frame"}
  ],
  "duration": 6
}
```

First-/Last-Frame und multimodale `reference_*`-Rollen sind laut ModelArk
getrennte Szenarien. Der Proxy weist Mischungen vor dem Upstream-Aufruf zurück.

### Multimodale Generierung und Bearbeitung

`reference_image`, `reference_video` und `reference_audio` können gemeinsam
verwendet werden. Der Prompt beschreibt, wie `Image 1`, `Video 1` und `Audio 1`
verwendet werden. Damit sind Stil-/Bewegungsübertragung, Videobearbeitung,
Verlängerung und das Verbinden von Clips erreichbar. Bei Seedance 2.0 darf Audio
nicht allein stehen; Seedance 2.5 akzeptiert auch reine Audioreferenzen.

### Modellabhängige Ausgabeoptionen

| | Seedance 2.5 | Seedance 2.0 | Seedance 2.0 Fast/Mini |
|---|---|---|---|
| `resolution` | 480p, 720p, 1080p | 480p, 720p, 1080p, 4k | 480p, 720p |
| `duration` | 4–30 oder `-1` | 4–15 oder `-1` | 4–15 oder `-1` |
| `ratio` | `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`, `adaptive` | wie 2.5 | wie 2.5 |
| Referenzen | 30 Bilder, 10 Videos, 10 Audio | 9 Bilder, 3 Videos, 3 Audio | 9 Bilder, 3 Videos, 3 Audio |
| Referenzlänge | je 2–30 s, zusammen ≤ 30 s | je 2–15 s, zusammen ≤ 15 s | je 2–15 s, zusammen ≤ 15 s |
| Audio ohne Bild/Video | ja | nein | nein |
| `output_format` | `mp4`, `mov` | `mp4` | `mp4` |
| `omni_reference_task_type` | `auto`, `reference`, `edit`, `extend` | – | – |
| Draft | ja | – | – |

Seedance 1.5 Pro: 480p–1080p, 4–12 s oder `-1`, Draft möglich, **abgekündigt**
(`launch_stage: deprecated`, Abschaltung 2026-11-11, Nachfolger
`dreamina-seedance-2-0-mini`). Seedance 1.0 Pro und Pro Fast: 2–12 s, Standard
1080p und 16:9, `frames` möglich, kein Audio; Pro Fast ohne `last_frame`.

1080p bei Seedance 2.5 und 4k bei Seedance 2.0 liefern 10-Bit-Farbtiefe mit
H.265/HEVC. Nicht jeder Player spielt das ab; VLC, mpv oder QuickTime sind der
verlässliche Weg.

### Feldregeln

| Feld | Regel |
|---|---|
| `generate_audio` | nur bei Modellen mit Audio; 1.0 Pro und Pro Fast lehnen es ab. Standard `DEFAULT_GENERATE_AUDIO` (`true`) |
| `camera_fixed` | nur 1.x, nicht zusammen mit Referenzbildern |
| `priority` | 0–9, nur 2.x, nicht zusammen mit `service_tier=flex` |
| `service_tier` | `default` oder `flex`; `flex` nur 1.x |
| `execution_expires_after` | 3600–259200 Sekunden |
| `frames` | 25 + 4n im Bereich 29–289, nur Modelle mit Frames (1.0 Pro, Pro Fast); stattdessen `duration` |
| `ratio` | `adaptive` bei 1.0 Pro nur mit Eingabebild |
| `safety_identifier` | aus `user`; über 64 Zeichen wird der Wert als SHA-256 gehasht |
| `data:`-URIs | nur Bild und Audio, nicht Video |
| Asset-IDs | `references[].asset_id` mit öffentlicher `asset-…`-ID wird zu `asset://asset-…` |

### Draft-Modus

Seedance 2.5 und 1.5 Pro können erst eine günstige Vorschau und danach das
Endvideo erzeugen:

1. Erste Anfrage mit `"draft": true`. Der Draft wird in 480p gerendert; eine
   andere Auflösung ergibt 400.
2. Zweite Anfrage mit `draft_task_id` (die ID des Drafts) und ausschließlich den
   Endfeldern: `resolution`, `watermark`, `return_last_frame`, `output_format`,
   `service_tier`, `execution_expires_after`, `priority`, `callback_url`,
   `safety_identifier`. Bei Seedance 2.5 ist das Endvideo nur in 1080p möglich
   (Standard).
3. Felder, die das Endvideo vom Draft erbt (`prompt`, Referenzen, `duration`,
   `ratio`, `seed`, `generate_audio`, `omni_reference_task_type`, `frames`,
   `camera_fixed`, `draft`), werden vom Proxy abgelehnt, auch mit gleichem Wert.

### Bearbeiten und Verlängern ohne Task-Typ

Nur Seedance 2.5 kennt `omni_reference_task_type`. Bei Seedance 2.0, 2.0 Fast und
2.0 Mini gibt es kein Feld, das eine Bearbeitung von einer gewöhnlichen
Referenzgenerierung unterscheidet: Beides ist derselbe multimodale Request mit
`role: "reference_video"`. Die Absicht transportiert ausschließlich der Prompt.

```json
{
  "model": "dreamina-seedance-2-0-fast",
  "prompt": "Edit Video 1: remove everyone except the protagonist.",
  "reference_urls": [
    {"url": "https://media.example/clip.mp4", "media_type": "video"}
  ]
}
```

Weil der Proxy hier keinen Task-Typ kennt, erzwingt er weder `ratio: "adaptive"`
noch `duration: -1`. Wird `omni_reference_task_type` an ein 2.0-Modell gesendet,
antwortet der Proxy mit HTTP 400. Ob ein Modell den Typ akzeptiert, steht in
`capabilities.task_types`; eine leere Liste bedeutet, dass der Prompt der einzige
Steuerweg ist.

### Task-Typen bei Seedance 2.5

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "prompt": "Video edit: remove everyone in @Video1 except the protagonist.",
  "omni_reference_task_type": "edit",
  "reference_urls": [
    {"url": "https://media.example/clip.mov", "media_type": "video"}
  ],
  "output_format": "mov"
}
```

- `edit` verlangt mindestens eine Videoreferenz von 4–30 s; `ratio` ist
  `adaptive` und `duration` ist `-1`, weil das Ergebnis Seitenverhältnis und
  Länge des Originals behält. Der Prompt muss die Bearbeitungsabsicht nennen.
- `extend` verlangt ebenfalls eine Videoreferenz und `ratio: "adaptive"`; die
  Länge ist mit `[4, 30]` oder `-1` frei wählbar.
- First-/Last-Frame-Tasks übernehmen das Seitenverhältnis des Startbilds und
  laufen deshalb ebenfalls mit `adaptive`.

Der Proxy setzt diese erzwungenen Werte selbst und lehnt widersprüchliche
Angaben sofort mit HTTP 400 ab. Weicht der vom Modell erkannte Task-Typ
trotzdem ab, meldet ModelArk asynchron `InvalidParameter.TaskTypeMismatch`.

Mit `return_last_frame: true` entsteht ein PNG-Endframe, abrufbar über
`/v1/videos/{id}/last_frame`; es eignet sich als First-Frame eines Folgetasks
(`input_reference_task_id`).

## Veo 3.1

Modelle: `veo-3.1-generate-001`, `veo-3.1-fast-generate-001`,
`veo-3.1-lite-generate-001` (Vertex); `veo-3.1-*-generate-preview` (Gemini API,
laut Google bis 22.10.2026). Standard-Backend ist Vertex.

| Thema | Regel |
|---|---|
| Dauer | 4, 6 oder 8 s; 1080p und 4k nur mit 8 s |
| Auflösung | 720p, 1080p, 4k (Lite: 720p, 1080p) |
| Format | 16:9 oder 9:16 |
| `first_last_frame`, `reference_to_video` | nur 8 s; Referenzbilder: 1–3 (nicht Lite) |
| Bilder | JPEG oder PNG bis 20 MB |
| `extend` | Vertex: MP4 von 1–30 s, Verlängerung fester Länge von 7 s (auch Lite). Gemini API: nur Veo-Videos dieses Proxys per `task_id`, 8 s, 720p, nicht Lite |
| Vertex-only | `n` bis 4, `generate_audio`, `negative_prompt`, `enhance_prompt`, `person_generation=dont_allow`, `provider_options.google` (`compressionQuality`, `resizeMode`) |
| Gemini API | `n` = 1; bei Bild-Tasks `person_generation=allow_adult` |

Nicht angeboten: Masken, Upscale, Kamerasteuerung und Stil-Referenz (für 3.1 nicht
dokumentiert), `storageUri` (der Proxy nutzt Inline-Bytes), `pubsubTopic`.
Löschen entfernt nur den lokalen Eintrag; der Anbieter-Job läuft weiter.

## Gemini Omni Flash

Modelle: `gemini-omni-1.1-flash` (Gemini API), `gemini-omni-1.1-flash-preview` und
`gemini-omni-flash-preview` (Vertex). Standard-Backend ist Vertex; mit
`GOOGLE_OMNI_BACKEND=both` laufen GA-IDs über die Gemini API und `-preview`-IDs
über Vertex. Der Proxy nutzt
die Interactions API mit `background: true` und Polling.

- Dauer 3–10 s; Auflösung 360p, 720p, 1080p, 4k (Flash Preview: nur 720p);
  Format 16:9 oder 9:16.
- Tasks: Text, Bild, First/Last, Referenzen (bis 10 Bilder und 3 Videos von
  höchstens 3 s), `edit`, `extend`. `gemini-omni-flash-preview` kann nur Text und
  `edit`.
- Video-Eingaben (`base_video`): MP4 oder MOV bis 20 MB; Vertex 1–30 s, Gemini API
  bis 10 s.
- Mehrstufige Bearbeitung: Ist `base_video` ein früherer Omni-Job desselben
  Backends, nutzt der Proxy `previous_interaction_id` (Multi-Turn) und lädt das
  Video nicht erneut hoch. `POST /v1/videos/{id}/remix` nutzt diesen Weg.
- Omni erzeugt immer Ton; `negative_prompt` wird bei `adapt` als „Avoid: …“ an den
  Prompt gehängt.
- `DELETE` bricht einen laufenden Job beim Anbieter ab (Teilkosten möglich) und
  löscht ihn dann lokal.

Hinweis: Edit und Extend über die Gemini API sind laut Recherche im EWR
eingeschränkt; Vertex ist der Standard. Für Vertex-Omni ist das nicht belegt.

## Kling

Zugang: `KLING_API_KEY`, Endpunkt `KLING_BASE_URL`. Der Proxy spricht je nach
Modell die neue API (`kling-3.0-turbo`) oder die Legacy-Endpunkte; Aliase wie
`kling-v3`, `kling-v3-omni`, `kling-video-o1`, `kling-v2-6`, `kling-v2-5-turbo`
werden erkannt.

| Modell | Dauer | Auflösung | Besonderheiten |
|---|---|---|---|
| `kling-3.0-turbo` | 3–15 s | 720p, 1080p | nur Neue API; Text, Bild, Multi-Shot |
| `kling-3.0` | 3–15 s | 720p, 1080p, 4k | Audio, Multi-Shot, Elements (≤ 3), Motion Control |
| `kling-3.0-omni` | 3–15 s | 720p, 1080p, 4k | Referenzen, Edit, Multi-Shot, Audio |
| `kling-o1` | 3–10 s | 720p, 1080p | Referenzen, Edit |
| `kling-2.6` | 5 oder 10 s | 720p, 1080p | Audio nur mit 1080p, Voices (≤ 2), Motion Control |
| `kling-2.5-turbo` | 5 oder 10 s | 720p, 1080p | First/Last nur mit 1080p |

**Prompt-Referenzen.** Kling adressiert Eingaben im Prompt mit
`<<<image_n>>>`, `<<<video_n>>>`, `<<<element_n>>>` und `<<<voice_n>>>`; `n` zählt
ab 1 je Typ in der Reihenfolge des `references`-Arrays. Die `@Name`-Schreibweise
der Kling-App gilt für die API nicht. Der Proxy schreibt den Prompt nicht um.

**Elements und Voices** (`type: "element"|"voice"`, `asset_id` aus `/v1/assets`)
steuern Image-to-Video: Kling 3.0 nimmt Elements, Kling 2.6 Voices, nie beides,
und beide nur mit Startbild. Omni-Modelle nehmen Bilder und Elements zusammen
(höchstens 7, mit Referenzvideo 4) und höchstens ein Referenzvideo.

**Multi-Shot.** `shot_mode: "customize"` mit 1–6 `shots` (Prompt ≤ 512 Zeichen,
ganze Sekunden; die Summe muss `seconds` entsprechen und wird sonst gesetzt) oder
`shot_mode: "intelligence"` (nur `prompt`). Die neue API erhält die Prompt-Syntax
`shot n, m, …;`, Legacy `multi_prompt`.

**Motion Control** (`kling-3.0`, `kling-2.6`): Rolle `subject` (Bild oder Element)
und `motion` (Video, 3–30 s). Die Dauer folgt dem Motion-Video. Standard ist
`provider_options.kling.character_orientation = "image"`; weitere Option
`keep_original_sound`.

**Lip Sync** (`kling-lip-sync`): ein Video mit Rolle `base_video` (2–60 s) und
entweder ein Audio mit Rolle `speech` oder `speech.text` mit `speech.voice`
(Kling-TTS-Stimme). Der Job läuft mehrstufig im Worker (Gesichtserkennung,
TTS, Rendering; `provider_status` nennt den Schritt). Ohne `audio.end_ms` endet die
Synchronisation an der gemessenen Länge der Audiodatei (höchstens Gesichtsintervall
und 60 s). `audio` steuert `start_ms`, `end_ms`, `insert_at_ms`, `volume`,
`original_volume` und `face_id`; ohne `face_id` gilt das Gesicht mit dem längsten
Intervall.

**Avatar** (`kling-avatar`): Bild mit Rolle `subject` plus Audio oder
`speech.text`; `resolution` 720p/1080p.

**Effekte** (`kling-effects`): `effect` aus dem Katalog
`GET /v1/providers/kling/effects` (219 Vorlagen mit 1 oder 2 Bildern).

**Multi-Element-Edit** (`kling-multi-elements`): Video mit Rolle `base_video`
(2–10 s), `edit_mode` (`addition`, `swap`, `removal`) und `selections`
(höchstens 10 Frames mit je höchstens 10 Punkten, Koordinaten in [0, 1]); Bilder
für `addition` (1–2) und `swap` (1).

**Audio.** `kling-text-to-audio` (Prompt ≤ 200 Zeichen, 3,0–10,0 s, Ergebnis
`variant=audio`), `kling-video-to-audio` (Video 3–20 s; `audio.bgm_prompt`,
`audio.asmr`; liefert `video` und `audio`), `kling-tts` über
`POST /v1/audio/speech`.

**Video-Commerce** (`kling-commerce`): `commerce_talking_agent` (Avatar-Bild oder
`commerce.avatar_id`, Produktbilder, Skript in `commerce.script`),
`commerce_goods_studio` (Produktbilder, `commerce.title`, 15, 30 oder 60 s) und
`commerce_apparel` (Quellvideo 5–180 s, Produktbilder, optional Modell-Bilder,
Musik). Zusätzliche Ergebnisbilder von Apparel sind Varianten
`product_image_n` und `model_image_n`.

**Grenzen.** Kling kennt keinen Abbruch: `DELETE` löscht nur lokal, der Job läuft
weiter und wird berechnet. Kling-Ergebnis-URLs sind hotlink-geschützt; der Proxy
lädt sie in den Output-Speicher. Ob Turbo immer mit Ton generiert, ist offen (das
Request-Schema hat kein Audiofeld; das Capability-Flag folgt dem Schema).

## Fortsetzen

`capabilities.continuation` steuert den Weg: `last_frame` (Seedance:
`return_last_frame` und `input_reference_task_id`), `video_extension` (Veo:
`task=extend` mit `task_id`) und `multi_turn` (Omni: `previous_interaction_id`
über `base_video`/Remix).

## Prompt Guides

Für jede Modellfamilie liegt ein Guide unter `prompt_guides/`
(`GET /v1/prompt-guides`): Seedance 2.5 und 2.0, Veo 3.1, Gemini Omni Flash und
vier Kling-Guides (3.0, Omni/O1, 2.x, Werkzeuge). Seedance 1.x hat keinen Guide.
Siehe [Entwicklung und Tests](../entwicklung-und-tests/README.md#prompt-guides).
