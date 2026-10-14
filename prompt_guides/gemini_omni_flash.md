# Gemini Omni Flash Prompting Guide

**Stand: 14. Oktober 2026**  
**Fokus:** Google Gemini Omni Flash (`gemini-omni-1.1-flash` auf der Gemini API, `gemini-omni-1.1-flash-preview` und `gemini-omni-flash-preview` auf Vertex AI / Gemini Enterprise Agent Platform) für Text-to-Video, Image-to-Video, First/Last Frame, Referenzen aus Bildern und kurzen Videoclips, Video-Editing, Multi-Turn-Editing, Extension und nativen Ton  
**Ziel:** aus einer Idee eine Anweisung machen, die Omnis Weltwissen nutzt, statt gegen es anzuschreiben – und die trotzdem genau festlegt, **wie viele Einstellungen** entstehen, **welche Datei welche Rolle hat**, **was sich ändern darf** und **was man hört**

> Die wichtigste Regel: Omni ist kein Shot-Zettel-Ausführer wie Veo, sondern ein **Regisseur mit Weltwissen**. Ohne Gegenanweisung baut Omni aus deinem Prompt eine kleine Erzählung **aus mehreren Einstellungen** – mit Ton, Musik und gegebenenfalls Dialog. Ein guter Omni-Prompt sagt deshalb zuerst, *ob* geschnitten werden darf („In a single continuous shot, no scene cuts“), beschreibt dann die Absicht statt jedes Details, bindet jede Datei per Tag an eine Rolle und benennt den Ton ausdrücklich. Edits dagegen sind **kurz**: eine Änderung, plus „Keep everything else the same.“

---

## 1. Quellenlage und Vertrauensstufen

Omni ist ein junges Modell (Preview seit Mai/Juni 2026, Version 1.1 seit 27. August 2026). Viele Angaben im Netz beziehen sich auf die erste Version oder auf Produktoberflächen. Dieser Guide markiert deshalb jede nicht offensichtliche Aussage:

- **(offiziell)** – steht so in einer Google-Primärquelle (Stufe A).
- **(praxisverifiziert)** – in diesem Projekt live beobachtet (Stufe B).
- **(Community)** – aus Drittquellen, nicht von Google bestätigt (Stufe C).
- **(Empfehlung)** – eigene Ableitung dieses Guides aus den Quellen; plausibel, aber nicht getestet.
- **(unverifiziert)** – widersprüchlich oder ungeprüft; nicht darauf bauen.

### Stufe A: Primärquellen

1. [Gemini API: Gemini Omni Flash](https://ai.google.dev/gemini-api/docs/omni) – Modi, Request-Form, Limitierungen, Regionalsperren und vor allem der Abschnitt **„Gemini Omni Flash prompt guide“** (Single Scene, Negatives, Edit-Prompts, Audio, Timing, Meta Prompting, Text, Extension, Tags).
2. [Google DeepMind: How to create effective prompts with Gemini Omni](https://deepmind.google/models/gemini-omni/prompt-guide/) – die fünf Promptelemente, Kameravokabular, „World understanding“ als Unterschied zu Veo, Text-Rendering, Referenzen, Storyboards, Extension, First/Last Frame.
3. [Google Blog: Gemini Omni 1.1 Flash lets you build with more control](https://blog.google/innovation-and-ai/technology/developers-tools/build-with-gemini-omni-1-1-flash/) (27. August 2026) – Neuerungen von 1.1 (10 s Kontext bei Extension, 40 s gesamt, First/Last Frame, 360p-Drafts, 4K-Upscaling, Video-Referenzen) mit Beispielprompts.
4. [Gemini Cookbook: Get_started_Omni.ipynb](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_Omni.ipynb) – Prompting-Tipps 1–5, Tag-Beispiele, Hinweise zum `task`-Parameter und zu `thinking_level`.
5. [GoogleCloudPlatform: gemini_omni_1_1_flash_video_gen.ipynb](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/vision/getting-started/gemini_omni_1_1_flash_video_gen.ipynb) – Vertex-Sicht: Source- vs. Reference-Media, Empfehlung „≤5 Bilder, ≤3 Videos“, Beispielprompts.
6. Vertex-AI-/Agent-Platform-Doku: [Referenzen](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-references), [Edit](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/edit-videos), [Extend](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/extend-videos), [Modellseite Omni 1.1 Flash](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-1-1-flash).
7. Die projektinterne Recherche `tasks/research/google.md` (Abschnitte 6–11), die die API-Fakten aus diesen Quellen bündelt.

### Stufe B: verifizierte Praxis

- **Live-Test ADR-001 (11.10.2026):** `gemini-omni-1.1-flash` über die Gemini API, 3 s, 360p, `background: true`, `store: true`, `delivery: "uri"` – wurde angenommen, `GET /v1beta/interactions/{id}` lieferte `status: completed` und eine Files-API-URI; 5 793 Video-Output-Tokens für 3 s 360p.
- **Proxy-Implementierung** (`src/modelark_proxy/providers/omni.py`, `google.py`): wie die einheitlichen Felder in Omni-Requests übersetzt werden. Was der Proxy *sendet*, ist damit gesichert; wie Omni auf jede Kombination *reagiert*, ist es nicht.

Es gibt **noch keine** systematischen Prompt-Tests in diesem Projekt. Alles über Bildwirkung stammt aus Stufe A oder ist als Empfehlung markiert.

### Stufe C: Community und Produktoberflächen

- Drittanbieter-Guides (OpenArt, Atlas Cloud, Morphic, diverse Blogs) wiederholen überwiegend die offiziellen Tipps; Eigenes (z. B. „Kamera in 3–8 Wörtern ans Ende“) ist nicht belegt.
- **Google Flow und die Gemini-App** nutzen Omni mit eigenen Defaults, eigener Montage und teils Funktionen, die die API **nicht** hat (z. B. Audio-Referenzen, siehe §27). Was dort geht, ist nicht automatisch ein API-Feature.

### Was nicht als Primärquelle behandelt wurde

Die generische [Vertex-Seite „Video generation prompt guide“](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/video-gen-prompt-guide) nennt Omni zwar im Einleitungssatz, ist inhaltlich aber ein **Veo-Guide**: Sie empfiehlt ein Negativprompt-Feld mit Substantivliste und behauptet, Ton gebe es nur bei `veo-3.0-generate-001`. Beides gilt für Omni **nicht** (§15, §13). Für Omni gilt die Omni-Seite der Gemini API.

---

## 2. Was Gemini Omni Flash offiziell ist

Gemini Omni Flash ist Googles nativ multimodales Video-Modell auf Gemini-Basis. Google nennt drei Kerneigenschaften **(offiziell)**: native Multimodalität (Text, Bild, Video als Input; Video mit Ton als Output), **konversationelles Editing** über die Interactions API und **Weltwissen** („an understanding of physics with Gemini's knowledge of history, science, and cultural context“).

### 2.1 Offiziell bestätigte Kernfähigkeiten

| Bereich | Stand (11.10.2026) |
|---|---|
| Modell-ID Gemini API | `gemini-omni-1.1-flash` (GA, nur Paid Tier); `gemini-omni-flash-preview` (Shutdown 22.10.2026) |
| Modell-ID Vertex | `gemini-omni-1.1-flash-preview` (volle Modi); `gemini-omni-flash-preview` (nur Text-to-Video und Edit, nur 720p). **Keine** GA-ID auf Vertex |
| API | Interactions API (`/v1beta/interactions`), nicht `predictLongRunning` |
| Dauer | 3–10 s pro Aufruf, ganze Sekunden |
| Auflösung | 360p, 720p (Default), 1080p und 4k – **1080p und 4k sind hochskaliert** |
| Seitenverhältnis | 16:9 (Default) oder 9:16 – **kein 1:1**; ein Edit behält das Format des Quellvideos |
| Framerate | 24 fps |
| Ton | wird **immer** erzeugt (Sprache, Musik, SFX); Steuerung nur über den Prompt |
| Negativprompt-Feld | **gibt es nicht** – Negatives gehören in den normalen Prompt |
| System Instructions, `temperature`, `top_p`, Stop Sequences | nicht unterstützt |
| Image-to-Video | ein Bild + Prompt; das Modell entscheidet anhand des Prompts, wie es das Bild nutzt |
| First/Last Frame | zwei Bilder (Task `image_to_video`) |
| Bildreferenzen | Subjekt-, Objekt- **und Stilreferenzen** per `<IMAGE_REF_N>`; Vertex ≤10 Bilder; Google empfiehlt ≤5 |
| Videoreferenzen | max. 3 Clips, je ≤3 s; „work best with likenesses“; Ton der Referenz wird ignoriert |
| Audio-Referenzen | **nicht unterstützt** (API) |
| Edit | Video + Prompt; hochgeladenes Video ≤10 s (Gemini API), Vertex 1–30 s |
| Multi-Turn-Edit | über `previous_interaction_id` auf ein früheres Omni-Ergebnis |
| Extension | Fortsetzung **nur am Ende**, 3–10 s pro Schritt, bis **40 s gesamt**; nutzt die letzten **10 s** als Kontext |
| Voice-Editing | nicht unterstützt |
| Sprache | Englisch vollständig unterstützt; andere Sprachen „not evaluated“ |
| Wasserzeichen | SynthID in jeder Ausgabe; Vertex zusätzlich C2PA |
| Regionale Sperre (Gemini API) | Edit/Extend **hochgeladener** Videos in EWR, Schweiz und UK nicht verfügbar; Bilder mit Minderjährigen dort nicht erlaubt |

### 2.2 Modellvarianten richtig wählen

- **`gemini-omni-1.1-flash`** (Gemini API) – die GA-Variante mit allen Modi. Standardwahl.
- **`gemini-omni-1.1-flash-preview`** (Vertex) – funktional dieselbe 1.1-Generation, als Preview geführt.
- **`gemini-omni-flash-preview`** (Vertex) – die erste Generation: **nur Text-to-Video und Edit, nur 720p**, keine Bilder als Startframe, keine Referenzen, keine Extension. Auf der Gemini API wird sie am 22.10.2026 abgeschaltet. Nur noch für Altbestände.

Welche Modi ein Modell im Proxy tatsächlich anbietet, steht verbindlich in `GET /v1/models/{id}` unter `capabilities.tasks`.

### 2.3 Omni gegenüber Veo 3.1: Was anders ist

| Thema | Veo 3.1 | Omni Flash |
|---|---|---|
| Grundhaltung | präzise Anweisungen nötig | „you don't have to be as prescriptive“ – Omni füllt Details aus Weltwissen **(offiziell, DeepMind)** |
| Schnitte | ein Take pro Aufruf ist der Normalfall | **mehrere Einstellungen sind der Default**; Single Shot muss man verlangen **(offiziell)** |
| Dauer | 4/6/8 s | 3–10 s, jede ganze Sekunde |
| Negativprompt | eigenes Feld (Vertex) | kein Feld, nur im Prompt |
| Stilreferenz | nicht bei 3.1 | `in the style of <IMAGE_REF_0>` dokumentiert **(offiziell)** |
| Text im Bild | unzuverlässig | ausdrücklich als Stärke beworben („correct and readable“) **(offiziell)** |
| Editing | kein konversationelles Editing | Kernfunktion, auch für Kamera, Stil, Aktion |
| Extension | +7 s, bis ~148 s, 720p | +3–10 s, bis 40 s, 10 s Kontext |
| Videoreferenzen | nein | bis 3 × 3 s |

Konsequenz: **Veo-Prompts funktionieren bei Omni, aber oft schlechter als nötig.** Ein Veo-Shot-Zettel ohne „single continuous shot“ kann bei Omni zu einer Mini-Montage werden, und lange Edit-Prompts verursachen ungewollte Änderungen.

---

## 3. Plattformmatrix und dieser Proxy

| Oberfläche | Zugriff | Besonderheit |
|---|---|---|
| Gemini API | API-Key, `generativelanguage.googleapis.com/v1beta/interactions` | GA-Modell; EWR/CH/UK-Sperre für Edit/Extend hochgeladener Videos; Ergebnis per Files API 48 h abrufbar |
| Vertex AI / Agent Platform | Service Account, `aiplatform.googleapis.com/v1beta1/.../locations/global/interactions` | nur Preview-IDs; Region nur `global`; Input-Video für Extend 1–30 s; Interactions 7–14 Tage gespeichert (Doku widersprüchlich) |
| Google Flow, Gemini-App | Abo | eigene Defaults, Montage, Draft-Funktionen; teils Funktionen ohne API-Gegenstück |
| **Dieser Proxy** | einheitliche API `/v1/videos` | übersetzt `seconds`, `aspect_ratio`, `resolution`, `task`, `references` in den Omni-Request; welches Google-Backend Omni nutzt, ist serverseitig konfiguriert (`GOOGLE_OMNI_*`) |

### 3.1 Was der Proxy für dich erledigt (praxisverifiziert aus dem Code)

- `seconds` → `response_format.duration` (`"8s"`), `aspect_ratio` und `resolution` → `response_format`. Fehlen die Felder, setzt der Proxy die Defaults **8 s, 16:9, 720p**. Omni muss Dauer und Format also **nie** aus dem Prompt ableiten.
- **Ausnahme Edit:** Bei `task: "edit"` (auch `/v1/videos/edits` und Remix) sendet der Proxy nur `resolution`. Google lehnt `aspect_ratio` beim Edit ab („Aspect ratio cannot be set in response format for edit task“) und dokumentiert dort auch kein `duration` **(praxisverifiziert)**. Im Capability-Dokument steht deshalb für `edit` `aspect_ratio: adaptive` und `seconds: auto`. Wer `aspect_ratio` oder `seconds` trotzdem mitschickt, bekommt mit `strict` einen 400-Fehler; `adapt` verwirft die Werte und meldet sie unter `adjustments`.
- Referenzen werden als Inhalts-Parts vor den Prompt gestellt, und zwar in dieser Reihenfolge: `first_frame`, `last_frame`, alle `reference`-Einträge (in der Reihenfolge deines `references`-Arrays), `base_video`, dann der Text.
- Für jeden Task außer `text_to_video` setzt der Proxy `generation_config.video_config.task` (`first_last_frame` → `image_to_video`).
- Verweist `base_video` per `task_id` auf einen **fertigen Omni-Job desselben Backends**, lädt der Proxy das Video nicht neu hoch, sondern sendet `previous_interaction_id`. Das ist Googles Multi-Turn-Weg – und auf der Gemini API der **einzige** Weg, mit dem Nutzer im EWR Videos bearbeiten oder verlängern können.
- Externe URLs als Referenz werden für Google abgelehnt. Dateien gehen über `POST /v1/media/references` (`upload_id`) oder als frühere Jobs (`task_id`).
- Jobs laufen asynchron (`background: true`, `store: true`); du pollst `GET /v1/videos/{id}`.

### 3.2 Was es im Proxy nicht gibt

`negative_prompt`, `seed`, `n`, `generate_audio`, `enhance_prompt` und `person_generation` sind für Omni keine Parameter. Mit `parameter_policy: "strict"` (Default) führt das zu einem Fehler, mit `"adapt"` werden sie verworfen und unter `adjustments` gemeldet. Das in Googles Cookbook beschriebene `thinking_level` (`low`/`high`) reicht der Proxy derzeit **nicht** durch; Omni läuft mit dem Google-Default.

---

## 4. Das mentale Modell: Absicht, Struktur, Rollen, Ton

Omni plant intern (Google: „internal reasoning to plan physics, lighting, object interactions, and cinematic timing before synthesizing frames“, Cookbook). Es braucht deshalb weniger Mikroanweisungen als Veo, aber **klare Entscheidungen** an vier Stellen. Halte sie fest, bevor du schreibst.

### 4.1 Structure Contract: ein Shot oder eine Sequenz?

Die wichtigste Entscheidung bei Omni. Ohne Anweisung entsteht eine Sequenz mit Schnitten **(offiziell)**.

- **Ein durchgehender Take** → ausdrücklich verlangen: `In a single continuous shot, no scene cuts.`
- **Eine Sequenz** → Anzahl und Reihenfolge der Einstellungen festlegen, am besten mit Timecodes (§12).
- **Rapid-Fire-Montage** → Takt angeben: `every 1s cut to a new …`.

### 4.2 Media Contract: Source oder Reference?

Das Vertex-Notebook unterscheidet zwei Rollen **(offiziell)**:

| Rolle | Bedeutung | Beispiele |
|---|---|---|
| **Source Media** | wird **wörtlich** zur Grundlage | Startbild bei I2V, Start- und Endbild, das zu bearbeitende Video |
| **Reference Media** | liefert Subjekt, Identität, Stil oder Bewegung, aber **nicht** den Bildausschnitt | Figuren, Produkte, Stilbilder, Storyboards, kurze Bewegungsclips |

Jede Datei hat genau eine Rolle. Schreibe sie mit Tags in den Prompt (§8). Der häufigste Omni-Fehler mit Bildern ist, dass eine Referenz als Startbild gelesen wird oder umgekehrt **(offiziell als Risiko genannt, Cookbook)**.

### 4.3 Sound Contract: Was hört man?

Ton entsteht immer. Lege fest: Dialog (wörtlich oder `No dialogue`), Musik (Stil/Funktion oder ausdrücklich keine), Geräusche und Atmosphäre.

### 4.4 Change Contract (nur Edit, Multi-Turn, Extension)

Was ändert sich – genau **eine** Sache? Und was bleibt? Bei Omni ist die Antwort auf das Zweite fast immer: `Keep everything else the same.`

---

## 5. Die Masterformel

### 5.1 Die offiziellen Bausteine

Google DeepMind nennt fünf Elemente **(offiziell)**, ohne feste Reihenfolge:

| Element | Leitfrage (DeepMind) |
|---|---|
| Shot framing and motion | Weit, halbnah oder nah? Gleitet die Kamera sanft oder stürzt sie plötzlich? |
| Style | Realistisch oder filmisch? Geerdet oder majestätisch? „Tell Gemini Omni the effect you want … and leave the model to work out the details.“ |
| Lighting | Woher kommt das Licht – Sonne, Straßenlaterne, off-screen? Ist es klar, warm, ätherisch? |
| Location | Wo spielt die Szene? „You don't need to describe every single little detail, as Omni will work with your overall intention.“ |
| Action | Was passiert, wer und was ist beteiligt, wie bewegen und interagieren sie sich? |

Die Gemini-API-Doku ergänzt **(offiziell)**: Szenenbeschreibung, Kamerabewegung, Licht und Stimmung; dazu die Single-Scene-Anweisung, Tonbeschreibung, Timing und exakten Bildtext.

### 5.2 Arbeitsformel dieses Guides (Empfehlung)

```
[Struktur: single continuous shot / Sequenz mit Timecodes]
+ [Kamera: Einstellungsgröße + eine Bewegung]
+ [Subjekt + Aktion]  (bei Referenzen: Tag statt Aussehen)
+ [Ort + Tageszeit]
+ [Licht + Stil/Look]
+ [Ton: Dialog / Musik / Sound design]
+ [Bildtext exakt in Anführungszeichen, falls gewünscht]
+ [kurze Verbote: No dialogue. No text overlay.]
```

Eine feste Reihenfolge ist **nicht** offiziell vorgegeben. Die offiziellen Beispiele stellen die Struktur- und Kameraangabe meist an den Anfang („Continuous, unbroken handheld shot of …“) und die Verbote ans Ende. Diese Reihenfolge ist eine gute Voreinstellung.

### 5.3 Das offizielle Single-Scene-Beispiel

```
Continuous, unbroken handheld shot of a fluffy tabby cat sitting on a sunny windowsill,
looking out into a leafy garden. The cat's tail twitches slowly, and its ears rotate
slightly toward ambient noises. Sunbeams illuminate dust motes in the air.
Sound design: Gentle breeze, distant bird chirps. No dialogue.
```

Darin steckt die ganze Formel: Struktur + Kamera (`Continuous, unbroken handheld shot`), Subjekt, Ort, kleine konkrete Bewegungen, Licht (`Sunbeams … dust motes`), Ton mit Label (`Sound design:`), Verbot (`No dialogue`).

### 5.4 Wie viel Text?

Omni hat kein dokumentiertes Prompt-Limit für Video (Kontextfenster 1 M Tokens). Die offiziellen Beispiele reichen von vier Wörtern (`Fish swimming, tracking shot`) bis zu ~150 Wörtern (Stilprogression im DeepMind-Guide). **Empfehlung:**

- Generierung: 40–120 Wörter. Mehr nur, wenn eine Sequenz mit Timecodes beschrieben wird.
- Edit und Multi-Turn: **ein bis zwei Sätze.** Lange Edit-Prompts verursachen laut Google ungewollte Änderungen **(offiziell)**.
- Extension: ein Satz für „was passiert als Nächstes“, plus Kamera und Ton.

### 5.5 Meta Prompting

Google dokumentiert, dass man Omni auf allgemeine Qualitätsprinzipien hinweisen kann **(offiziell)**, zum Beispiel:

```
Consider micro-detail, expression and timing to create a very rich, detailed but
entirely natural scene.
```
```
Be extremely detailed in your descriptions of characters and environments. Apply
costume design principles to characters.
```
```
Include plenty of appropriate detail in the background elements to make the scene
feel realistic and natural.
```

Diese Sätze ersetzen keine Regie, sind aber – anders als `8K, masterpiece` – vom Hersteller als wirksam beschrieben. Nutze höchstens einen davon pro Prompt **(Empfehlung)**.

---

## 6. Schritt 1: Genau einen Modus wählen

### 6.1 Entscheidungsbaum

1. Gibt es **keine** Datei? → **Text-to-Video** (`task` weglassen oder `text_to_video`).
2. Soll ein bestimmtes Bild **wörtlich der erste Frame** sein? → **Image-to-Video** (`first_frame`).
3. Stehen Anfangs- **und** Endbild fest? → **First/Last Frame** (`first_frame` + `last_frame`).
4. Sollen Figuren, Produkte, ein Stil oder eine Bewegung **übernommen**, aber neu inszeniert werden? → **Reference-to-Video** (Bilder und/oder bis zu 3 Clips ≤3 s, Rolle `reference`).
5. Soll ein **vorhandenes Video verändert** werden (Objekt, Stil, Licht, Kamera, Aktion)? → **Edit** (`base_video`).
   - Ist das Video ein **früherer Omni-Job** dieses Proxys? → als `task_id` übergeben; der Proxy nutzt Multi-Turn.
6. Soll ein Video **am Ende weitergehen**? → **Extend** (`base_video`, `seconds` = Länge der Fortsetzung).

### 6.2 Modusmatrix im Proxy

| Modus (`task`) | Referenzen (Rolle: Typ) | `seconds` | Prompt-Kern | Wichtigste Falle |
|---|---|---|---|---|
| `text_to_video` | keine | 3–10 | Struktur, Szene, Ton | ungewollte Schnitte |
| `image_to_video` | `first_frame`: 1 Bild | 3–10 | Bewegung, Kamera, Ton | Prompt erfindet, was im Bild nicht ist |
| `first_last_frame` | `first_frame` + `last_frame`: je 1 Bild | 3–10 | der Weg zwischen den Bildern | Bilder passen räumlich nicht zusammen |
| `reference_to_video` | `reference`: bis 10 Bilder, bis 3 Videos ≤3 s | 3–10 | Szene + Tag-Bindung | Referenz wird als Startbild gelesen |
| `edit` | `base_video` (+ optional `reference`-Bilder) | 3–10 | **eine** Änderung + „Keep everything else the same.“ | zu langer Prompt |
| `extend` | `base_video` (+ optional `reference`-Bilder) | 3–10 (neuer Teil) | was als Nächstes passiert | Gesamtlänge >40 s, Dialog bei Upload |

Auf `gemini-omni-flash-preview` (Vertex) existieren nur `text_to_video` und `edit`, beide 720p.

### 6.3 Kombinierte Wünsche aufteilen

„Mach das Video im Anime-Stil, tausch den Hund gegen eine Katze und häng fünf Sekunden an“ sind drei Schritte. Omni ist auf Ketten ausgelegt: erst Generierung, dann **ein** Edit pro Turn, dann Extension. Jeder Schritt ist ein eigener Job, den man prüfen und notfalls verwerfen kann **(Empfehlung, gestützt auf Googles „one change at a time“)**.

---

## 7. Schritt 2: Parameter aus dem Prompt heraushalten

### 7.1 In Feldern einstellen

| Feld (Proxy) | Werte | Omni-Feld | Anmerkung |
|---|---|---|---|
| `seconds` | 3–10 (Default 8); bei Edit nur `auto` | `response_format.duration` | bei Extend: Länge der Fortsetzung; bei Edit nicht gesendet |
| `aspect_ratio` | `16:9`, `9:16`; bei Edit nur `adaptive` | `response_format.aspect_ratio` | kein 1:1; bei Edit nicht gesendet |
| `resolution` | `360p`, `720p`, `1080p`, `4k` | `response_format.resolution` | 1080p/4k hochskaliert; `gemini-omni-flash-preview` nur 720p |
| `task` | siehe §6.2 | `generation_config.video_config.task` | weglassen = Proxy leitet ihn aus den Rollen ab |
| `references[].role` | `first_frame`, `last_frame`, `reference`, `base_video` | Reihenfolge der Inhalts-Parts | Tags im Prompt binden die Rolle zusätzlich |
| `parameter_policy` | `strict`, `adapt` | – | `adapt` korrigiert unpassende Werte und meldet sie |

### 7.2 Im Prompt beschreiben

Struktur (ein Shot oder Sequenz), Kamera, Subjekt, Aktion, Ort, Licht, Stil, Ton, exakter Bildtext, zeitliche Abfolge, Verbote, Rollenbindung der Dateien.

### 7.3 Was nicht in den Prompt gehört

- **Dauer, Seitenverhältnis, Auflösung als Text** („7 second video“, „9:16“, „in 4K“). Google zeigt in Vertex-Beispielen zwar Prompts wie `5 second, 9:16 video.` und schreibt, man könne diese Angaben „alternatively“ im Prompt machen – im Proxy sind die Felder aber gesetzt (beim Edit gibt das Quellvideo Dauer und Format vor). Ein abweichender Text stiftet nur Widerspruch **(Empfehlung)**.
- Ausnahme: Der offizielle Upscaling-Beispielprompt endet mit `photorealistic, 4k` als **Look-Beschreibung**. Das ist unschädlich, ersetzt aber nicht `resolution`.
- Framerate-Wünsche. Omni rendert 24 fps; „12fps line boiling“ im DeepMind-Beispiel ist ein **Stilmittel**, keine Ausgabe-Framerate.

---

## 8. Schritt 3: Dateien per Tag an Rollen binden

### 8.1 Einfache Tags (offiziell empfohlen)

| Tag | Bedeutung | Offizielles Beispiel |
|---|---|---|
| `<FIRST_FRAME>` | Bild ist der Startframe | `<FIRST_FRAME> a woman is walking` |
| `<LAST_FRAME>` | Bild ist der Endframe; **nur mit** `<FIRST_FRAME>` | `<FIRST_FRAME> <LAST_FRAME> a woman is walking` |
| `<IMAGE_REF_N>` | Bild ist Referenz (0-basiert) | `in the style of <IMAGE_REF_0> a woman <IMAGE_REF_1> is walking` |
| `<VIDEO_REF_N>` | Video ist Figuren-/Objektreferenz (0-basiert) | `the person in <VIDEO_REF_0> is playing the violin` |

Das Stilbeispiel ist wichtig: **Dieselbe Tag-Art bindet je nach Satzbau Stil oder Subjekt.** `in the style of <IMAGE_REF_0>` macht das Bild zur Stilreferenz, `a woman <IMAGE_REF_1>` zur Identitätsreferenz.

Offizielles Beispiel mit sechs Referenzbildern und Timecodes:

```
[0-3s] A studio fashion sequence. Starting with woman <IMAGE_REF_0>, she is holding <IMAGE_REF_1>
[3-6s] Then we see the man <IMAGE_REF_2> holding <IMAGE_REF_3>
[6-10s] And finally another woman <IMAGE_REF_4> who is holding <IMAGE_REF_5> while walking.
```

Offizielles Cookbook-Beispiel (Figuren und Accessoires kreuzweise gebunden):

```
In a single unbroken scene around a twilight campfire in a forest:
<IMAGE_REF_0> is wearing <IMAGE_REF_5>,
<IMAGE_REF_2> is wearing <IMAGE_REF_3>,
and <IMAGE_REF_4> is wearing <IMAGE_REF_1>.
They smile happily together as embers float into the evening sky.
```

### 8.2 Deklarationen für komplexe Fälle (offiziell)

Bei vielen Dateien mit gemischten Rollen kann man die Zuordnung **am Anfang** des Prompts deklarieren und **am Ende** in Worten bestätigen:

```
[# Sources <FIRST_FRAME>@Image1] [# References <IMAGE_REF_0>@Image2] a woman <IMAGE_REF_0>
is walking. Use Image1 as the starting frame. Use Image2 as a reference for the video
generation.
```

```
[# References <IMAGE_REF_0>@Image1 <VIDEO_REF_0>@Video1] The woman in <VIDEO_REF_0> is
playing the violin shown in <IMAGE_REF_0>. Use Video1 as a character reference and Image1
as an object reference.
```

Weitere offizielle Deklarationen: `[# Sources <FIRST_FRAME>@Image1 <LAST_FRAME>@Image1]` (dasselbe Bild als Anfang und Ende → **Loop**), `[# Sources <VIDEO_0>@Video1]` (Video als zu bearbeitende Quelle), `[# Sources <PREVIOUS_VIDEO>@Video1]` (Video des vorigen Turns verlängern).

Offizielle Schlusssätze:

- Startframe: `Use this image as the starting frame.`
- Loop: `Use this image as the first frame and the last frame.`
- Referenzbilder: `Use the given image(s) as references for video generation. The images should not be used as literal initial frames.`
- Referenzvideos: `Use the given video(s) as references. Do not use them as a source for video editing.`

Beachte die Zählweise: `ImageN`/`VideoN` in Deklarationen zählen **ab 1** über alle Bilder bzw. Videos im Input; `<IMAGE_REF_N>`/`<VIDEO_REF_N>` zählen **ab 0**.

### 8.3 Nummerierung im Proxy

Der Proxy stellt die Dateien in der Reihenfolge `first_frame`, `last_frame`, `reference` (in Array-Reihenfolge), `base_video` vor den Prompt.

- **Reference-to-Video:** Alle Bilder sind Referenzen. `<IMAGE_REF_0>` = erstes Bild in deinem `references`-Array, `<IMAGE_REF_1>` = zweites usw.; `<VIDEO_REF_0>` = erstes Video. **(Empfehlung, folgt der Cookbook-Aussage „0-indexed matching the order in input“; nicht live geprüft.)**
- **Edit/Extend mit Referenzbildern:** `<IMAGE_REF_0>` = erstes `reference`-Bild. Das Basisvideo bekommt **keinen** `VIDEO_REF`-Tag, denn es ist Source, nicht Referenz.
- **Startbild plus Referenzbild** gleichzeitig ist im einheitlichen Vertrag **nicht** vorgesehen: `image_to_video` erlaubt nur `first_frame`. Google dokumentiert die Kombination nativ (§8.2), der Proxy bietet dafür keine Rolle an.

### 8.4 Tags sind Bindung, keine Beschreibung

Wenn ein Referenzbild das Aussehen liefert, beschreibe im Text **nicht** noch einmal Haarfarbe, Kleidung und Gesicht – nur die Rolle in der Szene (`the woman <IMAGE_REF_0> pours coffee`). Doppelte, leicht abweichende Beschreibungen erzeugen Drift **(Empfehlung, gleiche Logik wie bei Veo)**. Ein kurzes Unterscheidungswort hilft dagegen, wenn mehrere Personen im Bild sind (`the woman <IMAGE_REF_0>`, `the man <IMAGE_REF_1>`).

---

## 9. Schritt 4: Kamera

### 9.1 Offizielles Vokabular

Der DeepMind-Guide nennt ausdrücklich **(offiziell)**:

- Kontinuität: `one continuous shot`, `oner`
- Fixe Kamera: `static`, `locked off`, `fixed`
- Bewegungen: `push in`, `punch in`, `dolly zoom`
- Kameratypen: `natural smartphone zoom`, `film camera`, `webcam style`

Im Blog und in der Doku kommen dazu: `tracking shot`, `handheld`, `whip-pan`, `pans`, `pulls back`, `snap-zoom`, `360-degree orbital rotation`, `close-up low-angle shot`, `macro close-up`, `shallow depth of field`.

### 9.2 Kameraformel (Empfehlung)

```
[Einstellungsgröße + Winkel] + [eine Bewegung + Tempo] + [was dadurch sichtbar wird]
```

Offizielles Beispiel für eine Kamera-Kette in **einem** Satz (als Edit):

```
Change the camera angle, a close-up on his shoes, quickly tilting up to medium shot,
then widening.
```

Und für eine aufwendige Bewegung (Blog, Extension):

```
Continue the video. Execute a cinematic optical dolly-zoom shot. The camera dollies forward
while simultaneously zooming out, keeping the character's frozen shocked face locked at the
exact same size. The long corridor of stone pillars in the background dramatically stretches
and deepens with intense optical perspective distortion. Clean architecture, continuous
unbroken shot.
```

Das Muster: **Fachbegriff + beobachtbare Wirkung** (`keeping the face locked at the exact same size`, `corridor … stretches`). Das ist präziser als das Fachwort allein.

### 9.3 Kamera und Schnitte

Bei Omni ist eine Kamerabeschreibung **keine** Garantie für einen einzigen Take. Wer `tracking shot` schreibt, aber nicht `continuous`, kann trotzdem Schnitte bekommen. Schreibe beides: `Continuous tracking shot …, no scene cuts.`

### 9.4 Kamera nachträglich ändern

Omni kann die Kamera eines **vorhandenen** Videos per Edit ändern **(offiziell, DeepMind)**:

```
Change the camera angle to be over the violinist's shoulder.
```

Das ist ein echter Unterschied zu Veo: Ein fast gelungener Take muss nicht neu gewürfelt werden, nur weil die Perspektive nicht passt.

---

## 10. Schritt 5: Subjekt, Aktion und Weltwissen

### 10.1 Weniger vorschreiben, mehr meinen

DeepMind formuliert den Unterschied zu Veo ausdrücklich **(offiziell)**: „With Veo, you need to share precise instructions … with Gemini Omni, you don't have to be as prescriptive. Instead, tell Omni what you want to create.“

Praktisch heißt das:

- **Komplexe Handlungen benennen statt zerlegen.** „When you refer to a complex action Gemini Omni understands your intention … You don't need to describe it across every frame.“ Also `she performs a perfect triple axel`, nicht zehn Teilbewegungen.
- **Wissen abrufen statt erklären.** Offizielle Beispiele: `claymation explainer of protein folding, everything is made out of clay, no hands, stop motion, accurate` oder `Explain the difference between regular computing and quantum computing. Visualize this sentence using …`.
- **Orte als Absicht.** `an alien landscape with clear, azure water` reicht; Omni ergänzt Details.

### 10.2 Wo Präzision trotzdem nötig ist

Weniger vorschreiben gilt für **Details, die das Modell plausibel ergänzen kann**. Präzise bleiben musst du bei **(Empfehlung)**:

- **Anzahl** von Personen und Objekten (`two people`, `exactly three cups`).
- **Wer tut was**, wenn mehrere Figuren im Bild sind.
- **Markenrelevanten Details** (Produktfarbe, Logo-Position) – besser über ein Referenzbild.
- **Allem, was nicht passieren darf** (keine Schnitte, kein Dialog, kein Text).

### 10.3 Aktionsformel (Empfehlung)

```
[Subjekt] + [sichtbare Handlung] + [Auslöser oder Timing] + [Ergebnis/Endzustand]
```

- Schwach: `a chipmunk in the woods`.
- Stark (offizielles Beispiel): `A little chipmunk darting out of the woods from the left side of the screen and sniffing the air inquisitively before darting out of frame on the right side`.

Bildrichtung (`from the left side of the screen`) und Ausgang (`out of frame on the right side`) sind billige, wirksame Angaben.

### 10.4 Ereignisgesteuerte Effekte

Omni versteht Bedingungen wie „immer wenn X passiert, dann Y“ **(offiziell, Cookbook „Key moments understanding“)**:

```
The style of the video changes every time the person touches the mirror
```
```
The lights of the apartments start turning on in sync with the music.
```

Das ist bei Omni ein eigenes Regiewerkzeug: Effekte an Handlungen oder Musik koppeln, statt Zeitpunkte zu raten.

---

## 11. Schritt 6: Licht, Stil, Look

### 11.1 Licht

DeepMind fragt nach Quelle, Qualität und Wirkung **(offiziell)**. Dieselbe Formel wie bei Veo funktioniert **(Empfehlung)**:

```
[Lichtquelle] + [Richtung] + [Härte/Qualität] + [Farbe] + [was es sichtbar macht]
```

Beispiel aus dem Blog: `Sunlight filters through the translucent foliage, creating a warm, glowing effect.`

### 11.2 Stil

- Stilbegriffe funktionieren: `anime`, `claymation`, `watercolour`, `stop motion`, `pixel art`, `risograph print`, `graphite pencil sketch` **(offiziell, in Beispielen)**.
- **Stil per Bild:** `in the style of <IMAGE_REF_0>` **(offiziell)**.
- **Stilwechsel innerhalb eines Videos** ist dokumentiert (DeepMind: „four-part stylistic progression“, Crayon → Bleistift → Glas → Risograph). Das ist eine Omni-Stärke, aber benenne jede Stufe konkret.
- **Durchgehende Effekte festnageln:** `Maintain the microscope lens effect throughout the entire video.` (Blog). Ohne diesen Satz kann ein Look mitten im Clip wechseln, besonders bei Sequenzen **(Empfehlung)**.

### 11.3 Qualitätswörter

Googles eigene Beispiele verwenden `cinematic`, `hyper-detailed textures`, `photorealistic`, `4k`. Sie schaden offenbar nicht, aber sie ersetzen weder Licht noch Kamera. Ein bis zwei davon am Ende reichen **(Empfehlung)**.

---

## 12. Schritt 7: Timing, Schnitte und Sequenzen

### 12.1 Einen Shot erzwingen

Offizielle Formulierungen **(offiziell)**:

- `In a single unbroken scene`
- `In a single continuous shot`
- `No scene cuts`
- `One continuous shot, no jump cuts.`
- `Continuous handheld shot, no scene cuts`

**Empfehlung:** Eine Formulierung am Anfang (`Continuous, unbroken shot of …`) **und** ein Verbot am Ende (`No scene cuts.`). Bei First/Last Frame benutzt Google genau diese Doppelung.

### 12.2 Zeitpunkte in natürlicher Sprache (offiziell)

```
After 3 seconds, a woman enters the scene.
At 5s the chorus starts in the background audio.
Every 2s cut to a new frame.
In a rapid fire sequence, every half a second (12 frames at 24fps) change the scene to a new location.
```

### 12.3 Timecode-Syntax (offiziell)

```
[0-3s] A person is walking
[3-6s] They stop and turn around
[6-10s] They start running
```

Regeln **(Empfehlung, wo nicht anders markiert)**:

- Schreibweise `[0-3s]` wie in der Doku. Das Cookbook nutzt auch `At 0:05` in Fließtext – beides wird offenbar verstanden; mische es nicht in einem Prompt.
- Die Blöcke sollen lückenlos sein und genau bei `seconds` enden. Ein `[6-10s]`-Block in einem 8-Sekunden-Job hat keinen Platz.
- Ein Block pro Ereignis; unter ~2 s pro Block wird es unscharf – außer bei bewusster Rapid-Fire-Montage.
- Timecodes sind ein **Zeitbudget**, kein framegenauer Schnittplan.
- Timecodes erzeugen **nicht automatisch** Schnitte. Wer an den Grenzen keine Schnitte will, schreibt `in one continuous shot` dazu (offizielles Beispiel: `[0-10s] Single unbroken continuous camera shot …`).
- Bei **Extension** zählt `0s` ab Beginn des **neuen** Teils **(offiziell)**.

### 12.4 Bewusste Sequenzen

Omni kann Montagen. Wer sie will, sollte sie **steuern**, statt sie zuzulassen:

```
[0-3s] Wide shot: a fishing harbour at dawn, boats rocking gently.
[3-6s] Medium close-up: an old fisherman coils a rope, looking out to sea.
[6-8s] Close-up: his weathered hands tie a knot. Same character throughout.
Sound design: gulls, water lapping against hulls, a distant engine. No music. No dialogue.
```

`Same character throughout` ist eine Empfehlung dieses Guides für Identitätskonstanz über Schnitte; für echte Konstanz ist ein Referenzbild stärker.

---

## 13. Schritt 8: Den Ton führen

### 13.1 Was offiziell gilt

- Ton wird **immer** erzeugt; es gibt keinen Schalter **(offiziell)**.
- „By default the model will try to generate an appropriate audio track … This might not always be what you want.“ Besonders **Musik** solltest du beschreiben **(offiziell)**.
- Offizielle Musikbeispiele: `Include calm background music`, `The video has a high energy techno beat`, `The audio is a low tinny radio broadcast in the background, playing a song`, `The music swells`, `dramatic music score`.
- Entfernen: `No dialogue`, `No extra sound effects`, `No dialogue or voiceover` **(offiziell)**.
- Audio-Referenzen (eigene Musik, Stimme) werden von der API **nicht** unterstützt; Voice-Editing ebenfalls nicht **(offiziell)**.

### 13.2 Schreibweise (Empfehlung)

Google nutzt im Single-Scene-Beispiel das Label `Sound design:`. Eine feste Präfix-Konvention wie bei Veo (`SFX:`, `Ambient noise:`) ist für Omni **nicht** dokumentiert, schadet aber nicht. Bewährt ist eine eigene Tonzeile am Ende:

```
Sound design: [Geräusche + Atmosphäre]. Music: [Besetzung/Stil/Einsatz] | No music. [Dialog oder No dialogue.]
```

### 13.3 Dialog

Offizielle Beispiele zeigen Dialog als Handlung mit Zitat **(offiziell)**:

```
The man in the blue sweater replies: "Did your father go out on the boat too?"
```
```
Camera slightly pans and we now see she is talking to a man with curly hair, we see man's
back, he says "I see it too" dramatic music score
```

Regeln **(Empfehlung)**:

- Sprecher eindeutig benennen (`the man in the blue sweater`), nicht `he`, wenn mehrere Personen im Bild sind.
- Kurz bleiben: Faustregel ~2–2,5 Wörter pro Sekunde gesprochener Zeit, für 8 s also ein bis zwei kurze Sätze.
- Nur das Gesprochene in Anführungszeichen. Anführungszeichen markieren bei Omni **auch Bildtext** (§14) – mach durch `says`/`replies` vs. `a sign that says` klar, was gesprochen und was geschrieben wird.
- Dialog in anderen Sprachen als Englisch ist von Google **nicht evaluiert** **(offiziell)**. Deutscher Dialog kann funktionieren, ist aber ungetestet.

### 13.4 Dialog bei Extension

- Hochgeladene Videos, in denen jemand spricht, kann man **nicht** um weiteren Dialog verlängern **(offiziell)**; schweigende Fortsetzungen gehen.
- Über Multi-Turn (früherer Omni-Job → `previous_interaction_id`) ist Dialog in der Fortsetzung unterstützt **(offiziell)**. Im Proxy: Basisvideo als `task_id` des früheren Omni-Jobs übergeben.

---

## 14. Schritt 9: Text im Bild

Omni wird ausdrücklich für lesbaren Text beworben – anders als Veo **(offiziell)**: „Gemini Omni will render in a way that is correct and readable.“

### 14.1 Exakten Wortlaut vorgeben

Wenn in der Szene natürlicherweise Text vorkommt (Schilder, Kennzeichen, Ladenfronten), lege ihn fest – sonst erfindet Omni ihn **(offiziell)**:

```
There is a street sign that says: "This is an AI generation by Omni", there is a storefront
that says: "All you need AI", there's a car with the number plate: "OMNI1.1"
```

### 14.2 Animierte Typografie

```
One word on the screen at a time: "did, you, know, that, Omni, can, do, awesome, text?"
Each word appears for 1s with a different animated style. No dialogue.
```

DeepMind nennt die Stellschrauben **(offiziell)**: Schriftart, Platzierung, Animation, Standzeit („exposure“) und Synchronität zum Bild.

### 14.3 Kein Text gewünscht

`No text overlay on screen.` **(offiziell, Cookbook)**. Bei Dialogszenen zusätzlich `no subtitles` **(Empfehlung)**.

### 14.4 Grenzen (Empfehlung)

„Correct and readable“ ist eine Herstelleraussage, keine Garantie. Für Rechtstexte, Preise und Logos gilt weiter: prüfen, und im Zweifel im Schnitt setzen. Kurze Wörter in Großbuchstaben sind erfahrungsgemäß stabiler als lange Sätze – das ist für Omni aber nicht getestet.

---

## 15. Schritt 10: Negativsteuerung

Es gibt **kein** Negativprompt-Feld. Google: „you can put your negatives in the regular prompt: e.g., ‚Do not do X‘“ **(offiziell)**.

### 15.1 Offizielle Muster

- `No dialogue` / `No dialogue or voiceover.`
- `No embellishments`
- `No extra sound effects`
- `No text overlay on screen.`
- `No scene cuts` / `no jump cuts`
- `do not show the drawing in the final video` (Image-to-Video-Beispiel)
- `no hands` (Claymation-Beispiel)

### 15.2 Regeln (Empfehlung)

- **Kurz und konkret**, als eigene Sätze am Ende. Google sagt „simple negative prompts“.
- **Keine langen Verbotslisten.** Fünf bis zehn „no X“ verschieben die Aufmerksamkeit auf genau diese Dinge. Nimm nur auf, was im letzten Ergebnis tatsächlich störte oder was typischerweise auftritt (Schnitte, Musik, Dialog, Text).
- **Positiv formulieren, wo es geht:** `the subject alone in the frame throughout` statt `no other people`; `static locked-off shot` statt `don't move the camera`.
- Das `negative_prompt`-Feld des einheitlichen Vertrags gibt es für Omni nicht (§3.2) – Inhalte von dort in den Prompt übernehmen.

---

## 16. Text-to-Video

### 16.1 Template

```
[Continuous, unbroken shot | Sequenz-Angabe] of [Subjekt mit 2–3 konkreten Merkmalen],
[Handlung mit Richtung/Timing], in [Ort, Tageszeit]. [Kamera: Einstellung + Bewegung].
[Licht], [Stil/Look]. Sound design: [Geräusche, Atmosphäre]. [Musik oder No music].
[Dialog oder No dialogue]. [No scene cuts.]
```

### 16.2 Beispiel: ruhiger Single Shot

```json
{
  "model": "gemini-omni-1.1-flash",
  "prompt": "Continuous, unbroken shot of a steaming ceramic mug on a worn oak café table. Slow push-in from a medium shot to a close-up as steam curls upward and catches the light. Low morning sun rakes in from camera left through a rain-flecked window, warm amber tones, shallow depth of field, subtle film grain. Sound design: soft rain on glass, a faint ceramic clink, low café murmur far in the background. No music. No dialogue. No scene cuts.",
  "seconds": 8,
  "aspect_ratio": "16:9",
  "resolution": "720p"
}
```

### 16.3 Beispiel: Weltwissen statt Detailregie

```
Claymation explainer of how a volcano erupts: magma rising through layers of clay rock,
pressure building, then a lava fountain. Everything is made out of clay, stop motion,
scientifically accurate, no hands. A short text label appears for each stage:
"MAGMA", "PRESSURE", "ERUPTION". Upbeat playful music. No dialogue.
```

Hier **soll** Omni schneiden und erklären; deshalb fehlt die Single-Shot-Anweisung absichtlich.

### 16.4 Beispiel: Rapid-Fire-Montage (angelehnt an das offizielle Muster)

```
Make a rapid fire video that shows a different rare gemstone every 1s, each one rotating
slowly on black velvet under a single soft spotlight. Include a clean white text label
naming each gemstone. Upbeat music. No dialogue.
```

---

## 17. Image-to-Video

### 17.1 Offizielle Hinweise

- Das Modell **entscheidet anhand des Prompts**, wie es das Bild nutzt **(offiziell)**. Im Proxy ist der Task zusätzlich auf `image_to_video` gesetzt.
- „Use high-resolution images and provide specific motion descriptions. Vague prompts like ‚make it move‘ produce less compelling results than detailed descriptions of the camera movement, subject motion, and environmental effects.“ **(offiziell)**
- Ein Bild kann auch nur **Bewegungsvorlage** sein: `turn this into realistic footage, using the drawing only as a guide for movement, do not show the drawing in the final video` **(offiziell)**.

### 17.2 Template

```
<FIRST_FRAME> [Kamerabewegung]. [Was sich im Bild bewegt – Subjekt, Umgebung, Licht].
[Was am Ende sichtbar ist]. Single continuous shot, no scene cuts.
Sound design: [...]. [Musik/Dialog-Anweisung].
```

Das Tag `<FIRST_FRAME>` ist bei einem einzigen Bild nicht zwingend, macht die Rolle aber eindeutig **(Empfehlung)**.

### 17.3 Beispiel

```json
{
  "model": "gemini-omni-1.1-flash",
  "prompt": "<FIRST_FRAME> Slow dolly-in on the robot as it raises its glowing amber lantern high above its head. Shimmering crystal dust swirls gently around the cavern and the lantern light spreads across the crystal walls. Single continuous shot, no scene cuts. Sound design: soft crystalline chimes, a low cavern echo. Calm ambient music. No dialogue.",
  "seconds": 6,
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "references": [
    {"upload_id": "<id aus POST /v1/media/references>", "type": "image", "role": "first_frame"}
  ]
}
```

### 17.4 Die eiserne Regel

Was nicht im Startbild ist, muss **plausibel hineinkommen** (durch Bildrand, Tür, Kamerafahrt) – sonst bricht das Bild. Omni ist hier toleranter als Veo, weil es Szenen bewusst weiterentwickelt (offizielles Beispiel: `Everything shakes as the cavern crumbles and a dragon wakes up.`). Wer **keine** neuen Elemente will, schreibt `No new subjects enter the frame.` **(Empfehlung)**.

---

## 18. First Frame und Last Frame

### 18.1 Offizielle Hinweise

- Zwei Bilder, beschrieben wird **der Übergang** **(offiziell)**.
- „Clearly define what is in your initial frame, specify the exact camera movement or transition path that takes place in between, and state precisely what the final frame should reveal.“ **(offiziell, DeepMind)**
- Ideal für Orbits, Zoom-Übergänge und Loops **(offiziell)**.
- Dasselbe Bild als Anfang und Ende ergibt einen **Loop** (`[# Sources <FIRST_FRAME>@Image1 <LAST_FRAME>@Image1]`) **(offiziell)**. Im Proxy: dasselbe `upload_id` als `first_frame` und `last_frame` übergeben **(Empfehlung, nicht getestet)**.

### 18.2 Template

```
<FIRST_FRAME> <LAST_FRAME> [Was im ersten Bild ist] – [Kamerabewegung/Übergang mit Richtung]
– [was das letzte Bild enthüllt]. One continuous shot, no jump cuts.
Sound design: [...]. [Musik/Dialog].
```

### 18.3 Offizielle Beispiele

```
A close-up low-angle shot of a stylish drummer in a beige suit playing a red drum kit in a
grand hall transitions as the camera whip-pans to the side, revealing an older saxophonist
playing alongside a ballet dancer spinning in a white outfit under soft purple stage lights.
One continuous shot, no jump cuts.
```
```
The camera moves around the bench to reveal the man's face. One continuous shot with no cuts.
```
```
A smooth cinematic transition from a lush green forest at sunrise to a snowy forest under a
starry night sky.
```

### 18.4 Request im Proxy

```json
{
  "model": "gemini-omni-1.1-flash",
  "prompt": "<FIRST_FRAME> <LAST_FRAME> The camera slowly orbits 180 degrees around the bench, starting behind the man looking at the lake and ending on his face in profile as he smiles. Golden late-afternoon light stays constant. One continuous shot, no jump cuts. Sound design: light wind, distant ducks. No music. No dialogue.",
  "seconds": 6,
  "aspect_ratio": "16:9",
  "references": [
    {"upload_id": "<start>", "type": "image", "role": "first_frame"},
    {"upload_id": "<ende>", "type": "image", "role": "last_frame"}
  ]
}
```

### 18.5 Wann der Modus scheitert (Empfehlung)

Wie bei Veo: Wenn beide Bilder nicht plausibel derselbe Raum sind oder Licht und Farbe stark abweichen, entsteht ein Morph statt einer Kamerabewegung. Erzeuge beide Frames am besten mit demselben Bildmodell aus demselben Ausgangsbild; Google empfiehlt dafür Nano Banana **(offiziell, Cookbook)**.

---

## 19. Reference-to-Video: Bilder, Stile, Storyboards, Videoclips

### 19.1 Offizielle Regeln

- Referenzen werden **nicht** als Startframe benutzt; das Modell extrahiert Subjekt, Identität oder Stil und setzt sie in eine neue Umgebung **(offiziell)**.
- Anzahl: Vertex ≤10 Bilder pro Prompt; das Vertex-Notebook empfiehlt **„no more than 5 reference images and 3 reference videos“**; das Doku-Beispiel nutzt 6 Bilder. Proxy-Limit: 10 Bilder, 3 Videos.
- Videoreferenzen: max. 3 Clips, je ≤3 s, „work best with likenesses“, ihr Ton wird **ignoriert** **(offiziell)**.
- „Referencing or reasoning across multiple videos is not supported. Attempting multi-video prompting may result in degraded model performance“ **(offiziell)**. Mehrere Videoreferenzen sind also erlaubt, aber riskanter als eine.
- Bilder mit bestimmten bekannten Personen werden abgelehnt; im EWR/CH/UK keine Bilder mit Minderjährigen (Gemini API) **(offiziell)**.

### 19.2 Template

```
[Struktur]. [Subjekt <IMAGE_REF_0>] [Handlung] [mit/bei <IMAGE_REF_1>] in [Ort].
[Kamera], [Licht], [Stil oder: in the style of <IMAGE_REF_2>].
Sound design: [...]. [Musik/Dialog]. Use the given images as references for video
generation. The images should not be used as literal initial frames.
```

Der Schlusssatz ist der offizielle Schutz gegen „Referenz wird als Startbild gelesen“.

### 19.3 Beispiel: Figur und Produkt

```json
{
  "model": "gemini-omni-1.1-flash",
  "task": "reference_to_video",
  "prompt": "In a single continuous shot, the woman <IMAGE_REF_0> unpacks the sneaker <IMAGE_REF_1> from a cardboard box on a bright kitchen table, turns it in her hands and smiles. Medium shot, slow push-in, soft daylight from a window on the left, clean natural look. Sound design: cardboard rustle, a quiet kitchen room tone. Light acoustic music. No dialogue. No text overlay on screen. Use the given images as references for video generation. The images should not be used as literal initial frames.",
  "seconds": 8,
  "aspect_ratio": "9:16",
  "references": [
    {"upload_id": "<frau>", "type": "image", "role": "reference"},
    {"upload_id": "<sneaker>", "type": "image", "role": "reference"}
  ]
}
```

### 19.4 Beispiel: Stilreferenz

```
In the style of <IMAGE_REF_0>, a lighthouse keeper <IMAGE_REF_1> climbs the spiral stairs of
a lighthouse at night, lantern in hand. Single continuous shot, the camera follows him upward.
Sound design: wind howling outside, footsteps on iron steps. No dialogue.
```

### 19.5 Beispiel: Bewegung aus Videoclips (offizielles Muster, Blog)

```
Use the three uploaded videos of dancers and replace them with the provided characters. Have
them perform their individual dances from the reference videos, all together in the large,
open space from the provided image. The dog character dog.png should do the classical dance
from dance3.mp4. The octopus octo.png should do the hip hop dance from dance1.mp4, and the bear
bear.png should do the breakdance from dance2.mp4. The final result should be one continuous
shot with no scene cuts.
```

Im Proxy gibt es keine Dateinamen im Prompt-Kontext; ersetze sie durch Tags (`the dog <IMAGE_REF_0> performs the dance from <VIDEO_REF_0>`) **(Empfehlung)**. Halte die Clips kurz (≤3 s), eindeutig (eine Person, klarer Hintergrund) und schreib, was **aus** dem Clip übernommen wird (Bewegung, Person, Objekt).

### 19.6 Storyboard als Referenz

Ein einzelnes Storyboard-Bild mit mehreren Panels kann eine Handlung vorgeben **(offiziell, DeepMind)**:

```
Show me this story. Follow the story exactly in order starting top left. Entire story in
10 seconds. Cinematic
```

Im Proxy: Storyboard als `reference`-Bild, `seconds` passend setzen (dann darf „in 10 seconds“ im Prompt nur stehen, wenn `seconds` 10 ist).

---

## 20. Video-Editing

### 20.1 Die offizielle Kernregel

„Simple prompts work best for video editing. Overly descriptive prompts can lead to unintended changes.“ Und: „When editing a specific aspect of the video, include ‚Keep everything else the same‘.“ **(offiziell)**

| Vermeiden (offiziell) | Vereinfacht (offiziell) |
|---|---|
| `In the video of the man sitting on the sofa, please add a small black cat that runs from the right side of the screen, jumps onto his lap, and then he starts to stroke its head while looking down.` | `Add a cat that jumps onto his lap, he begins to pet it. Keep everything else the same.` |
| `Please remove the cell phone that the person is holding in their hand and fill in the background so it looks like they are just holding their hand empty.` | `Make the phone invisible. Keep everything else the same.` |

### 20.2 Was man editieren kann (offizielle Beispiele)

- **Objekte:** `Change the butterfly to a bee.` · `Put a fashionable hat on this person` · `Change the dog to the cat. Remove the backpack and add a propeller hat.`
- **Stil:** `Make this video anime`
- **Licht:** `Change the lighting to be more dramatic`
- **Text:** `Change the text on the sign to say "Omni Flash"`
- **Kamera:** `Change the camera angle to be over the violinist's shoulder.`
- **Aktion/Effekte:** `Edit this keeping everything the same. Add animated motion effects coming out of the skateboard.`
- **Ereignisgebunden:** `When the person touches the mirror, make the mirror ripple beautifully like liquid, and the person's arm turns into reflective mirror material`

Das Vertex-Notebook zeigt auch **mehrere Änderungen in einem Prompt** (`Change the dog to the cat. Remove the backpack and add a propeller hat. Change the tennis balls to balls of yarn.`). Das geht – aber jede zusätzliche Änderung erhöht das Risiko ungewollter Nebeneffekte. Für Produktion: eine Änderung pro Job **(Empfehlung)**.

### 20.3 Edit mit Referenzbild

Neue Figur, neues Objekt oder neuer Stil können per Bild kommen **(offiziell, Vertex)**:

```
Replace the mug in his hand with the bottle <IMAGE_REF_0>. Keep everything else the same.
```

### 20.4 Request im Proxy

Hochgeladenes Video (≤10 s auf der Gemini API, 1–30 s auf Vertex):

```json
{
  "model": "gemini-omni-1.1-flash",
  "task": "edit",
  "prompt": "Make the phone invisible. Keep everything else the same.",
  "references": [
    {"upload_id": "<video>", "type": "video", "role": "base_video"}
  ]
}
```

Alternativ über den OpenAI-kompatiblen Weg `POST /v1/videos/edits` mit `{"video": {"id": "<video_id>"}, "prompt": "…"}` oder `POST /v1/videos/{video_id}/remix`.

> **EWR-Hinweis:** Auf der Gemini API sind Edit und Extend **hochgeladener** Videos in EWR, Schweiz und UK nicht verfügbar **(offiziell)**. Läuft das Omni-Backend des Proxys über die Gemini API aus diesen Regionen, funktionieren nur Edits früherer **Omni-Jobs** (Multi-Turn, §21). Für Vertex ist eine solche Sperre nicht dokumentiert **(unverifiziert)**.

### 20.5 Dauer und Format beim Edit

Ein Edit übernimmt Seitenverhältnis und Länge des Quellvideos. Google lehnt `aspect_ratio` beim Edit ab **(praxisverifiziert)**; die Edit-Beispiele von Google enthalten weder `aspect_ratio` noch `duration` **(offiziell)**. Der Proxy sendet deshalb nur `resolution`. `seconds` und `aspect_ratio` lässt du weg (oder setzt `auto` bzw. `adaptive`).

---

## 21. Multi-Turn-Editing

### 21.1 Wie es funktioniert

„Each turn builds on the previous result. The model remembers the video context, applying your changes while preserving elements you did not mention.“ **(offiziell)** Jeder Turn erzeugt ein **neues** Video; die vorige Fassung bleibt als eigener Job erhalten.

Im Proxy: Den früheren Omni-Job als `base_video` per `task_id` übergeben (oder `/v1/videos/{id}/remix` bzw. `/v1/videos/extensions` nutzen). Der Proxy sendet dann `previous_interaction_id` statt das Video erneut hochzuladen. Voraussetzungen: Der Quelljob ist **fertig** und lief auf **demselben Google-Backend**; die gespeicherte Interaction muss bei Google noch existieren (Gemini API 55 Tage, Vertex 7–14 Tage).

### 21.2 Prompt-Regeln

- **Nur die Änderung** beschreiben, nicht die Szene neu erzählen **(offiziell)**.
- `Keep everything else the same.` anhängen **(offiziell)**.
- Kette statt Sammelauftrag: offizielles DeepMind-Beispiel `Change the butterfly to a bee.` → `Change the bee into a small swarm of fireflies.`
- Pro Turn eine Dimension: erst Objekt, dann Licht, dann Kamera **(Empfehlung)**.

### 21.3 Beispiel

```json
{
  "model": "gemini-omni-1.1-flash",
  "task": "edit",
  "prompt": "Change the car color to metallic blue. Keep everything else the same.",
  "references": [
    {"task_id": "<video_id des früheren Omni-Jobs>", "role": "base_video"}
  ]
}
```

### 21.4 Offene Frage: `task` und Multi-Turn

Das Gemini-Cookbook warnt: „Specifying an explicit `task` parameter forces a standalone generation workflow and prevents you from chaining edits using `previous_interaction_id`“, und `task: "extend"` „adds strict constraints (such as disabling multimodal reference inputs)“. Der Proxy setzt bei `edit` und `extend` den Task **immer**, auch zusammen mit `previous_interaction_id`. Ob Omni in dieser Kombination den Verlauf vollständig nutzt, ist in diesem Projekt **nicht live geprüft** **(unverifiziert)**. Wenn ein Multi-Turn-Edit die Szene sichtbar „vergisst“ (andere Figuren, anderer Ort), ist das der erste Verdacht – dann im Prompt auf das bisherige Video verweisen (`In this video, …`) und das Ergebnis melden.

---

## 22. Extension

### 22.1 Offizielle Mechanik

- Fortsetzung **nur am Ende**, kein Voranstellen, keine Mitte **(offiziell)**.
- Pro Schritt 3–10 s (Doku) bzw. „in 10-second increments“ (Blog, DeepMind); gesamt bis **40 s** **(offiziell)**. Im Proxy steuert `seconds` die Länge des neuen Teils.
- Omni nutzt die **letzten 10 s** als Kontext (Vorgänger nur die letzte Sekunde). „Some of the final frames in your input video will be edited to make the transition seamless.“ **(offiziell)**
- Hochgeladene Videos ≤10 s (Gemini API) bzw. 1–30 s (Vertex); bei Multi-Turn gilt die Grenze nicht **(offiziell)**.
- Referenzbilder (und laut Doku auch Videos) dürfen neue Figuren einführen: `Extend this video: have the character shown in <IMAGE_REF_0> enter the scene and wave.` **(offiziell)**
- Ob das Ergebnis das **kombinierte** Video oder nur das neue Segment ist, ist nicht eindeutig dokumentiert **(unverifiziert)**. Prüfe die Länge des Ergebnisses, bevor du es weiterverarbeitest.

### 22.2 Prompt-Regeln (offiziell, ergänzt)

- Einstieg: `Extend this video`, `Continue the scene:`, `Continue the video.`, `The scene continues`.
- Beschreibe **nur, was als Nächstes passiert** – und ob die Szene **weiterläuft** oder **geschnitten** wird (`Show the same characters in the next scene`).
- **Ton fortschreiben**, besonders wenn er sich ändern soll: `The music continues into the chorus`.
- Timestamps zählen **ab Beginn der Extension**: `After 2s cut to a new scene with the same characters`.
- **Empfehlung:** Kamera und Licht ausdrücklich weiterführen (`the camera keeps its slow pull-back, the light stays golden`), wenn kein Bruch gewollt ist.

### 22.3 Offizielle Beispielkette (Blog)

```
Prompt 1: Continue the video. Execute a cinematic optical dolly-zoom shot. […] continuous unbroken shot.
Prompt 2: Continue the video. The camera executes a fast mechanical snap-zoom directly into the character's wide eyes. Stylized cinematic camera control.
Prompt 3: Continue the video. Time completely freezes into a static moment: the character, their windblown coat. The camera performs a smooth, high-speed 360-degree orbital rotation around the frozen character, showcasing dramatic 3D depth and parallax across the colonnade. Flawless continuity.
```

Dialogkette (DeepMind):

```
Prompt 1: The man in the blue sweater replies: "Did your father go out on the boat too?"
Prompt 2: The camera pulls back in one continuous movement as he continues his story: "He used to say that this harbour had a soul. And that the boats were a part of us." The music swells.
```

### 22.4 Request im Proxy

```json
{
  "model": "gemini-omni-1.1-flash",
  "task": "extend",
  "prompt": "Continue the scene: the camera keeps its slow pull-back as the fisherman sets down the rope and walks toward the end of the pier. The light stays soft and golden. Sound design: gulls, water lapping, his footsteps on wooden planks. The gentle guitar music continues. No dialogue.",
  "seconds": 8,
  "references": [
    {"task_id": "<video_id des früheren Omni-Jobs>", "role": "base_video"}
  ]
}
```

Oder `POST /v1/videos/extensions` mit `{"video": {"id": "<video_id>"}, "prompt": "…", "seconds": 8}`.

### 22.5 Checkliste vor jeder Extension

1. Bleibt die Gesamtlänge ≤40 s?
2. Ist das Basisvideo ein Omni-Job (Multi-Turn)? Dann sind Dialog und EWR kein Problem. Ist es ein Upload? Dann ≤10 s (Gemini API), kein neuer Dialog, nicht im EWR über die Gemini API.
3. Soll die Szene weiterlaufen oder geschnitten werden? Steht das im Prompt?
4. Ist der Ton (Musik läuft weiter? wird sie lauter?) beschrieben?
5. Sollen neue Figuren kommen? Dann per Referenzbild und `<IMAGE_REF_0>` – siehe aber §21.4.

---

## 23. Ein professioneller Iterationsworkflow

### Pass 0: Struktur festlegen

Ein Shot oder Sequenz? Welche Dateien, welche Rollen? Dauer, Format. Prüfen, ob der Modus auf dem gewählten Modell existiert (`GET /v1/models/{id}`).

### Pass 1: Draft in 360p

Google bewirbt 360p ausdrücklich für Iteration: bis zu 60 % schneller und rund **ein Drittel der Kosten** von 720p **(offiziell)**. Abgeleitete Kosten pro Sekunde Output (Vertex-Token-Raten, für die Gemini API angenommen): 360p ≈ 0,034 $, 720p ≈ 0,10 $, 1080p ≈ 0,15 $, 4k ≈ 0,30 $.

### Pass 2: Eine Variable pro Durchgang

Google beschreibt den Draft-Room-Ansatz: „generate 3-4 draft variations in 360p, varying one thing at a time and compare them side by side“ **(offiziell, Blog)**. Es gibt keinen `seed`; Varianten sind separate Aufrufe.

### Pass 3: Reparieren per Edit statt neu würfeln

Ist der Draft fast richtig, korrigiere ihn per Multi-Turn-Edit (Kamera, Licht, ein Objekt). Das ist bei Omni oft billiger und stabiler als ein neuer Prompt **(Empfehlung)**.

### Pass 4: Finale Auflösung

1080p und 4k sind **hochskaliert** **(offiziell)** – sie verändern nicht die Komposition, sondern die Schärfe. Ob ein Final-Render in 1080p denselben Inhalt wie der 360p-Draft liefert, ist **nicht** garantiert: Es ist ein neuer Aufruf. **Empfehlung:** Den finalen Prompt in 720p testen und erst dann hochgehen.

### Pass 5: Verlängern

Erst wenn der Master steht, per Extension verlängern; jede Fortsetzung einzeln prüfen.

### Prompt-Erweiterung durch Gemini

DeepMind empfiehlt, einen knappen Prompt von Gemini ausformulieren zu lassen **(offiziell)**. Prüfe danach, ob Struktur (ein Shot?), Anzahl der Figuren, Dialog und Verbote erhalten geblieben sind – Optimierer fügen gern Schnitte, Musik und zusätzliche Handlung ein **(Empfehlung)**.

---

## 24. Fehlerdiagnose

### 24.1 Ungewollte Schnitte oder Montage

Omnis Default **(offiziell)**. `In a single continuous shot` an den Anfang, `No scene cuts.` ans Ende. Timecode-Blöcke ggf. durch Fließtext ersetzen oder `in one continuous shot` ergänzen.

### 24.2 Edit verändert Dinge, die gleich bleiben sollten

Prompt zu lang **(offiziell)**. Auf einen Satz kürzen, `Keep everything else the same.` anhängen, eine Änderung pro Turn.

### 24.3 Referenzbild erscheint als Startbild (oder als Bild im Bild)

Rollenverwechslung **(offiziell als Risiko genannt)**. Tags verwenden, Schlusssatz `The images should not be used as literal initial frames.` ergänzen, `task: "reference_to_video"` explizit setzen.

### 24.4 Startbild wird nur als Inspiration genutzt

Umgekehrter Fall. `<FIRST_FRAME>` in den Prompt, `Use this image as the starting frame.` ans Ende, `task: "image_to_video"`.

### 24.5 Ungewollte Musik oder Sprache

`No music.` bzw. `No dialogue or voiceover.` und stattdessen die gewünschte Atmosphäre benennen. Keine Person in Sprechpose beschreiben, wenn niemand sprechen soll.

### 24.6 Text im Bild ist falsch oder erfunden

Exakten Wortlaut in Anführungszeichen angeben **(offiziell)**; bei unerwünschtem Text `No text overlay on screen.`. Lange Texte kürzen.

### 24.7 Look wechselt mitten im Video

Durchgängigkeit verlangen: `Maintain the [effect/style] throughout the entire video.` **(offiziell als Muster)**.

### 24.8 Identität driftet über Schnitte oder Turns

Referenzbild statt Textbeschreibung; Aussehen nicht doppelt beschreiben; bei Sequenzen `same character throughout`; Multi-Turn statt Neugenerierung.

### 24.9 Mehrere Videoreferenzen vermischen sich

Multi-Video-Reasoning ist laut Google nicht unterstützt **(offiziell)**. Auf eine Videoreferenz reduzieren oder pro Clip genau eine Person/Bewegung und eine klare Zuordnung im Prompt.

### 24.10 Edit/Extend eines hochgeladenen Videos scheitert

EWR/CH/UK-Sperre der Gemini API **(offiziell)**, Video >10 s (Gemini API), oder Dialog-Extension eines Uploads. Lösung: Video als Omni-Job erzeugen und per `task_id` weiterverarbeiten, oder Vertex-Backend nutzen (dort keine Sperre dokumentiert, unverifiziert).

### 24.11 Job fertig, aber kein Video

Der Proxy meldet `content_policy` („Omni returned no video“). Safety-Filter greifen auf Prompt **und** Ausgabe und unterscheiden sich je Region **(offiziell)**. Häufige Auslöser: erkennbare reale Personen, Minderjährige (EWR), Marken, Gewalt. Prompt oder Bild ändern; derselbe Prompt erneut bringt meist dasselbe.

### 24.12 Multi-Turn „vergisst“ die Szene

Siehe §21.4. Quelljob noch vorhanden? Gleiches Backend? Prompt auf die Änderung reduzieren und mit `In this video,` beginnen.

### 24.13 Validierungsfehler im Proxy

`unsupported_parameter` bei `negative_prompt`, `seed`, `n`, `generate_audio` usw.: Omni kennt sie nicht (§3.2). `seconds` außerhalb 3–10, `resolution` ≠ 720p auf `gemini-omni-flash-preview` oder mehr als 10 Bild- bzw. 3 Videoreferenzen werden abgelehnt (oder mit `parameter_policy: "adapt"` angepasst, wo möglich). Halte Videoreferenzen selbst auf ≤3 s; verlass dich nicht darauf, dass eine zu lange Datei schon vor dem Upload abgefangen wird.

---

## 25. Master-Checkliste vor dem Absenden

### Modus und Parameter
- [ ] Genau ein Modus; existiert er auf diesem Modell (`capabilities.tasks`)?
- [ ] `seconds` 3–10 gesetzt; bei Extend = Länge des **neuen** Teils; Gesamtlänge ≤40 s? Bei Edit weglassen.
- [ ] `aspect_ratio` 16:9 oder 9:16 (bei Edit weglassen); kein Format- oder Dauerwunsch im Prompt, der den Feldern widerspricht?
- [ ] `resolution` bewusst: 360p für Drafts, 720p als Standard, 1080p/4k (hochskaliert) für das Finale?
- [ ] Keine Felder, die Omni nicht kennt (`negative_prompt`, `seed`, `generate_audio`)?

### Struktur
- [ ] Single Shot gewünscht? Dann `single continuous shot` **und** `No scene cuts.`
- [ ] Sequenz gewünscht? Dann Anzahl/Reihenfolge der Einstellungen oder Timecodes, die genau bei `seconds` enden?

### Bild
- [ ] Kamera: Einstellungsgröße + eine Bewegung + was sie zeigt?
- [ ] Subjekt und Handlung konkret, Anzahl eindeutig?
- [ ] Ort als Absicht, Licht mit Quelle und Qualität, ein Stil?
- [ ] Durchgängige Effekte mit `throughout the entire video` festgenagelt?

### Dateien
- [ ] Jede Datei hat genau eine Rolle (Source vs. Reference)?
- [ ] Tags (`<FIRST_FRAME>`, `<LAST_FRAME>`, `<IMAGE_REF_N>`, `<VIDEO_REF_N>`) passen zur Reihenfolge im `references`-Array?
- [ ] Aussehen nicht doppelt in Text und Bild beschrieben?
- [ ] ≤5 Bilder empfohlen (≤10 erlaubt), ≤3 Videoclips à ≤3 s?
- [ ] Keine erkennbaren realen Personen; im EWR keine Minderjährigen?

### Ton
- [ ] Musik beschrieben oder `No music.`?
- [ ] Dialog wörtlich mit benanntem Sprecher, kurz – oder `No dialogue`?
- [ ] Geräusche/Atmosphäre in einer eigenen Zeile?

### Text
- [ ] Gewünschter Bildtext exakt in Anführungszeichen – oder `No text overlay on screen.`?

### Edit, Multi-Turn, Extension
- [ ] Edit-Prompt ein bis zwei Sätze, eine Änderung, `Keep everything else the same.`?
- [ ] Basisvideo als `task_id` eines Omni-Jobs (Multi-Turn) statt Upload, wo möglich?
- [ ] Upload: ≤10 s (Gemini API), nicht im EWR über die Gemini API, kein neuer Dialog bei Extension?
- [ ] Extension: Fortsetzung oder Schnitt benannt, Ton fortgeschrieben, Timestamps ab Beginn der Extension?

---

## 26. Merksystem

### Die vier Fragen vor jedem Omni-Prompt

1. **Schnitt oder kein Schnitt?** (Default ist Schnitt.)
2. **Welche Datei ist Source, welche Reference?** (Tags!)
3. **Was hört man – und was nicht?** (Ton ist immer an.)
4. **Generieren oder ändern?** (Ändern = kurz + „Keep everything else the same.“)

### Die Zahlen

- **3–10** – Sekunden pro Aufruf und pro Extension.
- **40** – maximale Gesamtlänge mit Extensions.
- **10** – Sekunden Kontext, die Extension liest; Upload-Grenze für Edit/Extend (Gemini API).
- **3 × 3** – höchstens drei Videoreferenzen à drei Sekunden.
- **5 (10)** – empfohlene (erlaubte Vertex-) Zahl an Referenzbildern.
- **0 / 1** – `<IMAGE_REF_0>` zählt ab 0, `Image1` in Deklarationen ab 1.

### Die Formel

```
Struktur → Kamera → Subjekt + Aktion (Tags) → Ort → Licht + Stil → Ton → Bildtext → kurze Verbote
```

### Die Edit-Formel

```
[Eine Änderung in einem Satz]. Keep everything else the same.
```

---

## 27. Behauptungen, die nicht pauschal als gesichert gelten

- **„Omni unterstützt Audio-Referenzen.“** – DeepMind-Guide (`They move to the music from <audio>`) und die Cookbook-Vergleichstabelle („Up to 5 reference images & 5 audio tracks“) behaupten das; die API-Doku sagt ausdrücklich „Uploading audio references is unsupported“. Für die API gilt: **nicht unterstützt**. Der Proxy bietet keine Audio-Referenz für Omni an.
- **„Veo ist besser für Extension, First/Last Frame und 1080p/4K.“** – So steht es in der Vergleichstabelle des Cookbooks, die offenbar aus der Zeit vor Omni 1.1 stammt. Omni 1.1 kann alle drei.
- **„Extension ist immer 10 s.“** – Blog und DeepMind sagen „10-second increments“, Doku und Cookbook „3–10 second continuation“. Im Proxy bestimmt `seconds` die Länge; ob jede Länge gleich gut funktioniert, ist ungetestet.
- **„Es gibt keine Obergrenze für Referenzbilder.“** – Die Gemini-API-Doku nennt keine; Vertex nennt ≤10, das Vertex-Notebook empfiehlt ≤5, das Cookbook spricht von „up to 5“, zeigt aber selbst 6.
- **„Ein Negativprompt-Feld verbessert Omni.“** – Gibt es nicht; die generische Vertex-Promptseite mit Substantivlisten bezieht sich auf Veo.
- **„`task` setzen ist immer sicherer.“** – Google empfiehlt das Gegenteil: zuerst über den Prompt steuern, `task` nur bei Fehlinterpretation, weil er Constraints hinzufügt (z. B. kein Multi-Turn-Chaining, keine Referenzen bei `extend` laut Cookbook). Der Proxy setzt `task` trotzdem für alle Nicht-T2V-Modi (§3.1, §21.4).
- **„1080p/4K bringen mehr Details in die Komposition.“** – Beide sind hochskaliert.
- **„Deutsche Prompts funktionieren gleich gut.“** – Nur Englisch ist offiziell vollständig unterstützt; andere Sprachen „have not been evaluated“.
- **„Kamera gehört ans Ende des Prompts.“** – Community-Tipp ohne Google-Beleg; die offiziellen Beispiele stellen die Kamera überwiegend an den Anfang.
- **„Omni rendert jeden Text korrekt.“** – Herstelleraussage, nicht getestet; lange Texte und Kleingedrucktes prüfen.
- **„Was in Flow oder der Gemini-App geht, geht auch über die API.“** – Nein; Abo-Oberflächen haben eigene Funktionen und Defaults.
- **„Omni ist deterministisch reproduzierbar.“** – Es gibt keinen `seed`; jeder Aufruf ist eine neue Variante.

---

## 28. Quellen

### Primärquellen (Stufe A)

1. [Gemini API: Gemini Omni Flash](https://ai.google.dev/gemini-api/docs/omni) (abgerufen 11.10.2026) – Modi, Tags, Limitierungen, Regionalsperren, „Gemini Omni Flash prompt guide“.
2. [Google DeepMind: How to create effective prompts with Gemini Omni](https://deepmind.google/models/gemini-omni/prompt-guide/) – Promptelemente, Kamera, Weltwissen, Text, Referenzen, Storyboard, Extension, First/Last Frame.
3. [Google Blog: Gemini Omni 1.1 Flash lets you build with more control](https://blog.google/innovation-and-ai/technology/developers-tools/build-with-gemini-omni-1-1-flash/) (27.08.2026) – 1.1-Neuerungen und Beispielprompts.
4. [Gemini Cookbook: Get_started_Omni.ipynb](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_Omni.ipynb) – Prompting-Tipps, Tags, `task`-Warnung, `thinking_level`.
5. [GoogleCloudPlatform: gemini_omni_1_1_flash_video_gen.ipynb](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/vision/getting-started/gemini_omni_1_1_flash_video_gen.ipynb) – Source vs. Reference Media, ≤5 Bilder/≤3 Videos, Vertex-Beispiele.
6. Agent Platform / Vertex: [References](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-references), [Edit](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/edit-videos), [Extend](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/extend-videos), [Omni 1.1 Flash](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-1-1-flash).
7. [Gemini API: Interactions API Reference](https://ai.google.dev/api/interactions-api) und [Pricing](https://ai.google.dev/gemini-api/docs/pricing).

### Praxisabgleich (Stufe B)

8. ADR-001 in `docs/architektur/README.md` – Live-Test `gemini-omni-1.1-flash` (3 s, 360p, `background`, URI-Delivery) am 11.10.2026.
9. `tasks/research/google.md` (Abschnitte 6–11) – gebündelte API-Fakten und Widersprüche.
10. Proxy-Code `src/modelark_proxy/providers/omni.py` und `google.py` – Feldübersetzung, Reihenfolge der Inhalts-Parts, Multi-Turn über `previous_interaction_id`.

### Bewusst nachrangig (Stufe C)

11. [Vertex: Video generation prompt guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/video-gen-prompt-guide) – generisch, Veo-geprägt; für Omni teils falsch (Negativfeld, Ton).
12. Drittanbieter-Guides (z. B. [OpenArt](https://openart.ai/blog/gemini-omni-flash-prompt-guide/), [Atlas Cloud](https://www.atlascloud.ai/de/blog/guides/gemini-omni-prompt-guide)) – nur als Abgleich; keine Aussage dieses Guides stützt sich allein darauf.

### Quellenwarnung

Omni ist auf Vertex nur als Preview verfügbar, und Google ändert Limits, Modi und Modell-IDs in schneller Folge (Preview-Abschaltung auf der Gemini API am 22.10.2026). Offizielle Quellen widersprechen sich an mehreren Stellen (§27). Für eine konkrete Produktion gilt zuletzt, was `GET /v1/models/{id}` im Proxy meldet und was ein kurzer 360p-Test zeigt.

---

## Schlussformel

Ein meisterhafter Omni-Prompt beantwortet acht Fragen ohne Widerspruch:

1. Welcher Modus läuft, und gibt es ihn auf diesem Modell?
2. Ein durchgehender Shot oder eine Sequenz – und steht das ausdrücklich im Prompt?
3. Welche Datei ist Source, welche Reference, und welcher Tag bindet sie?
4. Wie beobachtet die Kamera, und was macht ihre Bewegung sichtbar?
5. Was geschieht – benannt als Absicht, präzise nur dort, wo Omni nicht raten darf (Anzahl, Rollen, Marken)?
6. In welchem Licht und Stil, und bleibt der Look über das ganze Video gleich?
7. Was hört man – Musik, Geräusche, Dialog – und was ausdrücklich nicht? Welcher Text steht wörtlich im Bild?
8. Bei Edit und Extension: Was ist die **eine** Änderung oder das **eine** nächste Ereignis – und bleibt alles andere gleich?
