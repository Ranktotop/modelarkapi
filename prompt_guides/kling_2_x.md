# Kling 2.x Prompting Guide (Kling 2.6 und Kling 2.5 Turbo)

**Stand: 11. Oktober 2026**  
**Fokus:** Kling 2.6 (nativer Ton, Voice Control mit `<<<voice_1>>>`, Motion Control) und Kling 2.5 Turbo (stummes, günstiges Text- und Image-to-Video) mit ihren festen 5/10-Sekunden-Takes und den 1080p-Regeln für Ton und First/Last Frame  
**Ziel:** einen einzelnen, kurzen Take so beschreiben, dass Bild **und** Ton beim ersten Versuch stimmen, ohne gegen die harten Parameterregeln der 2.x-Modelle zu laufen

> Die wichtigste Regel: Kling 2.x rendert **einen Take von 5 oder 10 Sekunden**. Kein Multi-Shot, keine Elements, keine freie Dauer. Ein guter 2.x-Prompt ist ein **Einzelbild mit Bewegung**: ein Ort, ein bis zwei Figuren, eine Handlung, und bei 2.6 eine klar zugeordnete Tonspur. Wer Ton oder Start- und Endbild will, rendert in **1080p**, sonst lehnt Kling ab.

---

## 1. Quellenlage und Vertrauensstufen

### Stufe A: Primärquellen (offiziell)

1. **Kling-API-Doku** für 2.6 (Text-to-Video, Image-to-Video, Motion Control, Voice Customization) und 2.5 Turbo, die **Legacy-Seiten** (`model_name` `kling-v2-6`, `kling-v2-5-turbo`; `<<<voice_1>>>`, `negative_prompt`) und die **Capability Map** (Stand 2026-05-19). Der Proxy ruft beide Modelle über die **Legacy-API** auf.
2. **„KLING VIDEO 2.6 User Guide“** (16. Dez. 2025): Audio-Formel, Dialogregeln P1–P4, Trigger-Wörter, Voice-Control-Regeln mit erlaubten und verbotenen Schreibweisen.
3. **Grundlagen-Guides** „Text-to-Video“, „Image-to-Video“, „Start and End Frames“, „Standard Mode & Professional Mode“ (24. Nov. 2025). Sie stammen aus der 1.x/2.0-Zeit, sind aber die offiziellen Formeln für stummes Kling und gelten für 2.5 Turbo unverändert.
4. **„Motion Control“ User Guide** (5. März 2026), Teil 2.6.

Markiert als **[Doku]** bzw. **[User Guide]**.

### Stufe B/C

Community-Quellen behandeln 2.x kaum noch gesondert: **[Praxis]**. Eigene Ableitungen: **[Empfehlung]**.

### Was nicht übernommen wurde

`camera_control`, Motion Brush, `cfg_scale` und Video-Extension. Diese Funktionen stehen nicht mehr im Schema (Proxy bietet sie nicht an). Ältere „Kling 2.x Prompt“-Sammlungen, die sie empfehlen, beziehen sich auf 1.x-Modelle.

---

## 2. Was Kling 2.6 und 2.5 Turbo offiziell sind

### 2.1 Kernfähigkeiten

| Bereich | Kling 2.6 | Kling 2.5 Turbo |
|---|---|---|
| Proxy-Modell-ID | `kling-2.6` (Alias `kling-v2-6`) | `kling-2.5-turbo` (Alias `kling-v2-5-turbo`) |
| Dauer | **5 oder 10 s** | **5 oder 10 s** |
| Auflösung | 720p, 1080p | 720p, 1080p |
| Seitenverhältnis | T2V: 16:9, 9:16, 1:1; I2V: vom Bild | dito |
| Nativer Ton | ✔, **nur 1080p** | ✘ |
| Voice Control (eigene/preset Stimmen) | ✔, nur I2V, 5/10 s, 1080p, max. 2 Voices | ✘ |
| First Frame | ✔ | ✔ |
| First + Last Frame | ✔, **nur 1080p und stumm** | ✔, **nur 1080p** |
| Multi-Shot, Elements | ✘ | ✘ |
| Motion Control | ✔ | ✘ |
| `negative_prompt` | ✔ (≤ 2500) | ✔ (≤ 2500) |
| Prompt | ≤ 2500 Zeichen | ≤ 2500 Zeichen |
| Dialogsprachen | **nur Chinesisch und Englisch**; andere werden ins Englische übersetzt | – |

### 2.2 Die 1080p-Regeln auf einen Blick

| Wunsch | Kling 2.6 | Kling 2.5 Turbo |
|---|---|---|
| Ton | nur 1080p | nicht verfügbar |
| Start + Endbild | nur 1080p **und ohne Ton** | nur 1080p |
| Voice | nur 1080p, nur mit Startbild, Ton an | nicht verfügbar |

Der Proxy prüft das: Mit `parameter_policy=strict` gibt es 400, mit `adapt` setzt er die Auflösung auf 1080p bzw. schaltet den Ton bei First/Last Frame ab und meldet die Anpassung.

`quality: standard` entspricht 720p (Kling „std“), `pro` 1080p („pro“).

### 2.3 Standard vs. Professional [User Guide]

Kling beschreibt die Modi so: Standard ist schneller und günstiger, mit „soft and pleasing“ Farben, gut für Porträts, Tiere und Szenen mit viel Bewegung. Professional liefert „richer details“, stabilere Kamera und reichere Komposition, gut für Architektur und Landschaft. Bei 2.x ist Professional zugleich 1080p, also Voraussetzung für Ton.

### 2.4 Welches Modell wofür

| Aufgabe | Modell |
|---|---|
| günstige stumme Clips, Massenvarianten, Moodboards | 2.5 Turbo |
| kurze Clips mit Dialog, Voice-over, Gesang, SFX | 2.6 (1080p) |
| wiederkehrende Stimme über viele Clips | 2.6 mit Voice (I2V) |
| Bewegung aus einem Video auf eine Figur übertragen | 2.6 oder 3.0 Motion Control |
| mehrere Shots, mehr als 10 s, Elements, 4K | Kling 3.0 (`kling_3_0.md`) |
| Dialog in Japanisch, Koreanisch, Spanisch | Kling 3.0 |

---

## 3. Das mentale Modell: ein Take, ein Beat, ein Tonvertrag

### 3.1 Shot-Vertrag

Ein 5-Sekunden-Take trägt **eine** Bewegung. Ein 10-Sekunden-Take trägt eine Bewegung mit Auflösung oder zwei kurze Beats. Der Grundlagen-Guide formuliert es so: „Keep the visual content as simple as possible, aiming for a completion within 5 to 10 seconds.“

### 3.2 Bild-Vertrag (I2V)

Das Startbild liefert Szene, Figuren und Seitenverhältnis. Der Prompt liefert **nur Bewegung** (und bei 2.6 Ton). Laut Guide kann eine Beschreibung, die stark vom Bild abweicht, „a camera cut or transition“ auslösen.

### 3.3 Ton-Vertrag (2.6)

Wer spricht, was genau, in welchem Ton; welche Geräusche; Musik ja/nein. Der 2.6-Guide empfiehlt ausdrücklich, „to focus on one core theme in each creation to avoid stacking too many elements (e.g., multiple ambient sounds + complex speech)“.

---

## 4. Die offiziellen Formeln

### 4.1 Text-to-Video (stumm, 2.5 Turbo und 2.6 ohne Ton) [User Guide]

> **Prompt = Subject (Subject Description) + Subject Movement + Scene (Scene Description) + (Camera Language + Lighting + Atmosphere)**

- **Subject Description**: in mehreren kurzen Sätzen (Haar, Kleidung, Accessoires, Gesicht, Haltung).
- **Movement**: „straightforward and suitable for a 5-second video“.
- **Scene**: Vorder- und Hintergrund in wenigen Sätzen, „suitable for what can be displayed within a 5-second video“.
- **Camera Language**: ultra-wide angle, bokeh, close-up, telephoto, low-angle, high-angle, aerial view, depth of field.
- **Lighting**: ambient lighting, morning light, sunset, interplay of light and shadow, Tyndall effect, artificial lighting.

### 4.2 Image-to-Video [User Guide]

> **Prompt = Subject + Movement, Background + Movement …**

Offizielles Beispiel der Steigerung:
```
Put on sunglasses
Mona Lisa puts on sunglasses with her hand
Mona Lisa puts on sunglasses with her hand, and a ray of light appears in the background
```
Nur die zweite und dritte Fassung steuern zuverlässig. Ohne Subjekt und Bewegung „decides the model on its own“, bei Gemälden oft ein Schwenk über das Bild, bei Fotos oft ein fast statisches Video.

### 4.3 Mit Ton (2.6) [User Guide]

> **Prompt = Scene + Element (Subject Description) + Movement + Audio (Dialogue / Singing / Sound Effects / Pure Music) + Other (Style / Emotion / Camera)**

Kurzform aus dem Guide: „[the scene you want to see] + [the action that happens] + [the sound you want to hear]“.

### 4.4 Mit Voice Control (2.6) [User Guide]

> **Prompt = Scene + [Element (element description) @ Voice Name] + Motion + Audio + Others**

Über den Proxy wird `@ Voice Name` zu `<<<voice_n>>>` (§9).

---

## 5. Modusmatrix

| Proxy-Task | Eingaben | 2.6 | 2.5 Turbo | Falle |
|---|---|---|---|---|
| `text_to_video` | `prompt`, `aspect_ratio` | 5/10 s, Ton nur 1080p | 5/10 s, stumm | Ton bei 720p |
| `image_to_video` | Bild `first_frame` | + Voices (≤ 2) | ✔ | Prompt beschreibt Szene neu |
| `first_last_frame` | `first_frame` + `last_frame` | nur 1080p, stumm | nur 1080p | Bilder zu verschieden |
| `motion_control` | Bild `subject` + Video `motion` | ✔ | ✘ | Halb-/Ganzkörper passen nicht |

---

## 6. Parameter vs. Prompt

### 6.1 In Feldern

| Proxy-Feld | Werte | Kling (Legacy) |
|---|---|---|
| `seconds` | 5, 10 | `duration` "5"/"10" |
| `resolution` / `quality` | 720p/1080p bzw. standard/pro | `mode` std/pro |
| `aspect_ratio` | 16:9, 9:16, 1:1 (nur ohne Bild) | `aspect_ratio` |
| `generate_audio` | bool (2.6) | `sound` on/off |
| `negative_prompt` | Text | `negative_prompt` |
| Voice-Referenzen | `{"type": "voice", "asset_id": "asset-kling-voice-<id>"}` | `voice_list` |

### 6.2 Im Prompt

Subjekt, Bewegung, Szene, Kamera, Licht, Atmosphäre; bei 2.6 Dialog, Sprecherzuordnung, Stimmprofil, SFX, Atmo, Musik.

### 6.3 Nirgends

Dauerangaben („a 7-second clip“; es gibt nur 5/10), „4K“, Seitenverhältnis als Text, Mehrfach-Shots („cut to …“). 2.x hat kein Multi-Shot.

---

## 7. Kamera, Handlung, Licht

### 7.1 Kamera

Eine Bewegung pro Take. Offizielle Beispiele aus der 2.x-Zeit:
- „The camera zooms into a beacon tower on the Great Wall, first-person perspective, high-speed flight, symmetrical composition, motion blur“
- „A circling camera shot captures a handsome young man dressed in ancient clothing …“
- „On an alien planet, the streetscape of a cyberpunk city, … the camera slowly advances forward“
- im 2.6-Guide: „the camera holding a slow, subtle zoom in on the speaker in mid-close-up“, „The camera closely follows the vacuum's path“

Die alten Kameraparameter (horizontal, vertical, zoom, pan, tilt, roll; Master Shots) gibt es nicht mehr als Feld. Schreibe die Bewegung in Worten.

### 7.2 Handlung

- Bewegung soll laut Guide „comply with the laws of physics“ und im Bild plausibel sein.
- Komplexe Physik (springende Bälle, Wurfbahnen) ist laut Guide schwierig.
- Zahlen sind unzuverlässig („not sensitive to numbers“).
- Mehrere Subjekte: nacheinander aufzählen, jedes mit seiner Bewegung.

### 7.3 Licht und Stil

Wie Kling 3.0: Quelle, Richtung, Farbe, was es trifft. Herkunfts- und Stilwörter wirken stark („Oriental mood“, „China“, „Asia“ erzeugen laut Guide leichter chinesische Ästhetik). Split-Screen geht laut Guide mit Formulierungen wie „4 camera angles, representing spring, summer, autumn, and winter“.

---

## 8. Ton bei Kling 2.6

### 8.1 Was 2.6 kann [User Guide]

Sprache (direkt in die Kamera, Voice-over, Mehrpersonendialog), Gesang und Rap, Instrumentalmusik, SFX, Atmo, Mischungen. Alles in einem Durchgang, synchron zum Bild. Voraussetzung: `generate_audio: true` und `resolution: 1080p`.

### 8.2 Sprache

- **Nur Chinesisch und Englisch.** Andere Sprachen werden automatisch ins Englische übersetzt (FAQ).
- Englische Wörter möglichst **kleinschreiben**, **Akronyme und Eigennamen großschreiben** (Guide-Hinweis zur Aussprache).
- Für Gesang und Dialog **10 s** statt 5 s, „for more complete and stable results“.

### 8.3 Dialogformel [User Guide]

> **Dialogue: "Sentence" + Emotion + Speech Speed + Tone + Character Label**

- Eine Figur: `[Man speaking]`, „Sentence“ + deep + fast.
- Mehrere Figuren: `[Character A, angrily] says, "…" [Character B, calmly] replies, "…"`.
- Anführungszeichen grenzen den Toninhalt ab.

### 8.4 Die vier Dialogregeln [User Guide]

| Regel | Richtig | Falsch |
|---|---|---|
| **P1 Structured Naming** | `[Character A: Black-suited Agent]` und `[Character B: Female Assistant]`, danach immer gleich | `[Agent] says … Then, he says …` |
| **P2 Visual Anchoring** | `The black-suited agent slams his hand on the table. [Black-suited Agent, angrily shouting]: "Where is the truth?"` | Zeile ohne vorausgehende Handlung |
| **P3 Audio Details** | `[Black-suited Agent, raspy, deep voice]: "Don't move." [Female Assistant, clear, fearful voice]: "I'm scared."` | `[Man] says … [Woman] says …` |
| **P4 Temporal Control** | `[Agent]: "Why?" Immediately, [Assistant]: "Because it's time."` (optional „this is when the speaker switches“) | zwei Zeilen ohne Verbindung |

Für Zuhörer schreibt der Guide „During this, [Name] remains silent.“

### 8.5 Trigger-Wörter [User Guide]

| Typ | Wörter | Beispiel |
|---|---|---|
| Sprechen | speaking, asking, telling/narrating, explaining | „An old man sitting by the fireplace, slowly telling a story.“ |
| Lautstärke/Klarheit | whispering, softly speaking, clearly speaking / crisp voice | „Two friends … whispering a secret.“ |
| Stimmfarbe | hoarse voice, deep voice | „A middle-aged man telling a scary story in a deep voice.“ |
| Gesang | singing, loud singing, vibrato, falsetto | „A singer adding a beautiful vibrato to the high note.“ |

### 8.6 SFX, Musik, Gesang [User Guide]

- **SFX:** `Sound Source (Action/Object) + State + Professional Sound Effect`, Struktur: „[Object: Wooden Door] suddenly [Action: Slams] + [Sound Effect: Bang]“.
- **Instrumentalmusik:** `Instrument + Genre + Emotion`, z. B. „Piano performance + jazz + melancholy“.
- **Gesang:** `"Lyrics" + Singing Style + Accompaniment + Emotion`; Stile wie pop, opera, country; Techniken wie high-pitched, vibrato, gentle singing.
- **Hintergrund** als eigener Satz: „Background: Soft beauty BGM playing.“

### 8.7 Offizielle 2.6-Beispiele

Produkt-Livestream:
```
In a beauty live-streaming room, warm yellow lighting illuminates the table, with
lipstick samples displayed on either side. [Caucasian beauty influencer] raises a matte
dusty rose lipstick. [Caucasian beauty influencer, sweet and fresh voice] says:
"Perfect for yellow undertones! Brightens the complexion without drying, and the finish
looks beautifully soft all day." Background: Soft beauty BGM playing.
```

Interview mit Sprecherwechsel:
```
Dialog: [Caucasian male host] sits in front of the microphone, slightly leaning forward.
[Caucasian male host, steady voice] says: "Today we're excited to have Dr. Sarah Miller
from Stanford AI Lab. Sarah, your research on neural networks is groundbreaking."
During this, [African-American female guest] remains silent. Immediately,
[African-American female guest] raises her chin slightly, holding the microphone.
[African-American female guest, gentle voice] says: "Thank you for having me."
```

Voice-over ohne Figur:
```
At the World Cup final, the lights are dazzling, and the stands are roaring with
excitement. (No characters, just narration) [Narrator, excited male voice] as the ball
hits the net: "The game is over!" Background: Fans erupt in cheers, and the camera
captures the moment the ball enters the net from the goalkeeper's perspective.
```

### 8.8 Ton abschalten bzw. begrenzen [Empfehlung]

Wenn du stumme Clips willst, setze `generate_audio: false` (bei 2.6 Default aus). Wenn Ton an ist, aber keine Musik: „No background music, only [Atmo].“ Wenn keine Sprache: „No dialogue, no voice-over.“ Das ist nicht offiziell belegt, aber die einzige Steuerung, die neben dem Schalter existiert.

---

## 9. Voice Control bei Kling 2.6

### 9.1 Was es ist [Doku, User Guide]

Eine **Custom Voice** (aus 5–30 s sauberer Einzelstimme oder aus einem Kling-2.6-Video mit Ton) oder eine **Preset Voice** wird an eine Figur gebunden. Die Stimme bleibt über Clips hinweg gleich und passt Tonfall und Rhythmus an die Szene an.

Regeln:
- nur **Image-to-Video** (Text-to-Video wird laut Guide „not available yet“),
- nur **5/10 s und 1080p**, Ton muss an sein (der Proxy setzt `generate_audio` automatisch, sobald eine Voice-Referenz dabei ist),
- höchstens **2 Voices** pro Clip,
- Voice-IDs aus der Custom-Voice-API bzw. Preset-Liste, **nicht** die TTS-/Lip-Sync-Voice-IDs (z. B. `oversea_male1`),
- Voice-Erstellung und -Nutzung nur für **Chinesisch und Englisch**; „voice consistency may be weaker in singing scenarios“.

Im Proxy: Voice über `/v1/assets` anlegen, dann `{"type": "voice", "asset_id": "asset-kling-voice-<id>"}` in `references`.

### 9.2 Syntax im Prompt

| API | Schreibweise |
|---|---|
| Legacy (**Proxy**) | `<<<voice_1>>>`, `<<<voice_2>>>` in der Reihenfolge der Voice-Referenzen |
| neue API / App | `@VoiceName` (z. B. `@sweet`) |

Offizielles Legacy-Beispiel: `The man<<<voice_1>>> said: "Hello"`. Die Doku sagt dazu: „The simpler the syntax structure, the better.“ Wird eine Voice in `voice_list` übergeben **und** im Prompt referenziert, rechnet Kling den Clip als „with specified voice“ ab.

### 9.3 Richtige Platzierung [User Guide]

Die Stimme steht **direkt hinter dem Figurennamen**, vor der Zeile:

```
[Livestream Host]<<<voice_1>>>: "This top is a trending must-have!"
```

Zwei Figuren:
```
[Teacher]<<<voice_1>>>: "Turn to page 20." [Student]<<<voice_2>>>: "Okay, teacher."
```

Offizielles Beispiel (App-Syntax, über den Proxy mit `<<<voice_n>>>`):
```
Police interrogation scene. In a tense police interrogation, [Detective Li @Mr. Wang's
voice] stands and demands, "Where's the evidence?" [Suspect Zhang @Xiaohong's voice]
lowers his head, trembling slightly, and replies, "I don't know anything." The overall
tone is serious and intense, with close-up shots focusing on their exchange.
```

Empfohlen sind **zwei** Sprecher; bei drei und mehr nimmt die Qualität laut Guide ab.

### 9.4 Verbotene Schreibweisen [User Guide]

| Fehlertyp | Beispiel (falsch) |
|---|---|
| Stimme ohne Figur | `[<<<voice_1>>>] calmly says: "Welcome to today's weather forecast."` |
| zwei Figuren, eine Stimme | `[Guard A]<<<voice_1>>> … [Guard B]<<<voice_1>>> …` |
| Stimme hinter dem Dialog | `[A]: "Line A." [B]: "Line B." <<<voice_1>>>` |
| Stimme vor der Figur, losgelöst | `<<<voice_1>>>. [Character]: "Dialogue"` |
| Stimme im Dialogtext | `[Protagonist]: "I've decided <<<voice_1>>> to leave this place."` |
| Stimme an Handlung oder Geräusch | `[police siren]<<<voice_1>>> wailing` |
| Stimme an stumme Figur | Stimme an einen Verkäufer gebunden, der nichts sagt |
| Attributkonflikt | `[A tall man]<<<voice_1>>>`, wobei die Stimme eine hohe Kinderstimme ist, plus „a sharp, high-pitched female child voice“ im Text |

**[Empfehlung]** Wenn eine Stimme gebunden ist, im Text keine widersprechende Stimmfarbe angeben. Emotion und Tempo („trembling“, „firmly“) sind weiterhin sinnvoll.

---

## 10. First/Last Frame

- 2.6: nur 1080p und stumm. 2.5 Turbo: nur 1080p.
- Laut Guide: „Choose two similar images with the same theme for smoother transitions within 5 seconds. Large differences may trigger a shot switch.“
- Typischer offizieller Workflow: beide Bilder mit Kling-Bildgenerierung erzeugen, dann verbinden.
- Der Prompt beschreibt den Weg: „Camera zooms out, the girl smiles“ (offizielles Legacy-Beispiel).
- **Nur Endbild** ist nicht möglich.

---

## 11. Motion Control mit Kling 2.6

Gleiche Mechanik wie bei 3.0 (siehe `kling_3_0.md` §17), mit drei Unterschieden:
- **keine Elements** (kein Gesichts-Binding),
- Preis niedriger,
- die 2.6-Guide-Beispiele zeigen den Prompt für Szenendetails: „A girl wearing a white tank top and a denim skirt.“, „A corgi runs in, circling around a girl's feet.“

Kernregeln [User Guide]: Ganzkörper ↔ Ganzkörper, Halbkörper ↔ Halbkörper; Bewegungsvideo ohne Schnitte und ohne Kamerabewegung; moderates Tempo; eine Person (sonst wird die größte genommen); Video 3–30 s (≤ 10 s bei `character_orientation=image`); Ausgabe so lang wie die extrahierbare Bewegung, mindestens 3 s. Der Proxy setzt `character_orientation` ohne Angabe auf `image`; die Kling-App auf `video`.

---

## 12. Negativsteuerung

- Beide Modelle haben `negative_prompt` (≤ 2500 Zeichen), der Proxy reicht es durch.
- Die Legacy-Doku empfiehlt trotzdem, „to supplement negative prompt via negative sentences within positive prompts“.
- **[Empfehlung]** `negative_prompt` als kurze Substantivliste (`blurry, distorted hands, extra fingers, watermark, subtitles`), echte Verbote als Satz im Prompt („No subtitles, no background music.“). Ein Negativfeld ersetzt keine fehlende Regie.

---

## 13. Templates

### 13.1 2.5 Turbo / stumm, Text-to-Video

```
[Kamera + Einstellung], [Subjekt mit 2–3 Merkmalen in kurzen Sätzen] [eine Bewegung],
[Szene in 1–2 Sätzen]. [Licht]. [Atmosphäre/Look].
```

### 13.2 Image-to-Video stumm

```
[Subjekt aus dem Bild] [Bewegung]. [Zweites Subjekt] [Bewegung]. [Hintergrund] [Bewegung].
The camera [eine Bewegung].
```

### 13.3 2.6 mit Dialog (1080p, 10 s)

```
[Ort, Licht, Atmo]. [Figur A: Beschreibung] [sichtbare Handlung].
[Figur A, Stimmprofil] says: "[Satz]." During this, [Figur B] remains silent.
Immediately, [Figur B] [Handlung]. [Figur B, Stimmprofil] replies: "[Satz]."
Background: [SFX/Atmo/Musik]. [Kamera].
```

### 13.4 2.6 mit Voices (I2V, 1080p)

```
[Szene]. [Figur A]<<<voice_1>>> [Handlung] and says, "[Satz]."
Immediately, [Figur B]<<<voice_2>>> [Handlung] and replies, "[Satz]." [Stimmung], [Kamera].
```

### 13.5 2.6 Voice-over / Produkt

```
Visual: [Produkt in Umgebung, Licht]. [Narrator, Stimmprofil]: "[Claim]."
Background: [Geräusch passend zum Produkt]. The camera [Bewegung zum Produkt].
```

### 13.6 2.6 Gesang

```
[Ort, Licht]. [Sänger:in mit Merkmalen] [Haltung, Instrument].
[Sänger:in, Stimmqualität] sings: "[Lyrics]." [Begleitung], [Emotion]. [Kamera].
```

---

## 14. Ausgearbeitete Beispiele

### 14.1 2.5 Turbo: günstige Moodboard-Variante (5 s, 720p)

```json
{
  "model": "kling-2.5-turbo",
  "seconds": 5,
  "resolution": "720p",
  "aspect_ratio": "16:9",
  "prompt": "A medieval sailing ship sails on the sea on a foggy night. Bright moonlight breaks through the clouds and lights the wet sails. The camera slowly advances toward the bow. Cold blue tones, eerie atmosphere.",
  "negative_prompt": "blurry, text, watermark"
}
```

### 14.2 2.6: Werbespot mit Sprecherin (10 s, 1080p)

```json
{
  "model": "kling-2.6",
  "seconds": 10,
  "resolution": "1080p",
  "aspect_ratio": "9:16",
  "generate_audio": true,
  "prompt": "In a kitchen, the oven door is half open, revealing a golden chiffon cake resting on the table. [Latina girl] gently breaks the cake with her hands, crumbs falling, her eyes shining with excitement. [Latina girl, proud and sweet voice] says: \"My first success. Look at that crumb!\" Background: upbeat BGM. Medium close-up, slow push-in."
}
```
(offizielles Beispiel, ergänzt um Kamera)

### 14.3 2.6 mit zwei Voices (I2V, 10 s)

```json
{
  "model": "kling-2.6",
  "task": "image_to_video",
  "seconds": 10,
  "resolution": "1080p",
  "references": [
    {"type": "image", "role": "first_frame", "url": "https://…/farewell_platform.png"},
    {"type": "voice", "asset_id": "asset-kling-voice-111"},
    {"type": "voice", "asset_id": "asset-kling-voice-222"}
  ],
  "prompt": "Family farewell on a train platform. [Father]<<<voice_1>>> lowers his head slightly and says, \"The train is about to depart.\" Immediately, [Daughter]<<<voice_2>>> wipes away tears and responds, \"Dad, please don't go.\" Sorrowful tone, medium shot, quiet station ambience."
}
```

### 14.4 2.6 First/Last Frame (5 s, 1080p, stumm)

```json
{
  "model": "kling-2.6",
  "task": "first_last_frame",
  "seconds": 5,
  "resolution": "1080p",
  "references": [
    {"type": "image", "role": "first_frame", "url": "https://…/girl_close.png"},
    {"type": "image", "role": "last_frame", "url": "https://…/girl_wide.png"}
  ],
  "prompt": "The camera zooms out slowly, the girl smiles and tucks her hair behind her ear."
}
```

---

## 15. Häufige Fehler und Diagnose

| Symptom | Ursache | Abhilfe |
|---|---|---|
| 400 bei 7 s | nur 5/10 s | 5 oder 10 |
| 400 / Anpassung bei Ton | 2.6-Ton nur 1080p | `resolution: 1080p` |
| Ton fehlt bei First/Last (2.6) | 2.6 rendert Start+End stumm | Ton separat (`kling-video-to-audio`) oder Kling 3.0 |
| 400 bei First/Last in 720p | nur 1080p | 1080p |
| Voice abgelehnt | kein Startbild, 720p, Ton aus, > 2 Voices, falscher ID-Typ | I2V, 1080p, max. 2 Custom/Preset-Voices |
| Falsche Stimme an falscher Figur | Voice-Tag falsch platziert | direkt hinter den Figurennamen (§9.3) |
| Dialog auf Englisch statt Zielsprache | nur zh/en | zh/en verwenden oder Kling 3.0 |
| Abgeschnittene Sätze | 5 s zu kurz | 10 s, kürzere Sätze |
| Eine Figur spricht beide Zeilen | P4 fehlt | „Immediately,“ / „this is when the speaker switches“ |
| Video fast statisch (I2V) | nur Objektnennung, keine Bewegung | Subjekt + Bewegung ausschreiben |
| Schnitt im Clip | Prompt weicht stark vom Bild ab | nur Bewegung im Bild beschreiben |
| Falsche Anzahl Objekte | Zahlen unzuverlässig | Anzahl über das Startbild vorgeben |

---

## 16. Master-Checkliste

- [ ] Dauer 5 oder 10 s (Dialog/Gesang: 10)?
- [ ] Ton nur mit 2.6 und 1080p?
- [ ] First/Last nur 1080p (2.6 zusätzlich stumm)?
- [ ] I2V: nur Bewegung beschrieben, nichts Neues ins Bild geholt?
- [ ] Dialog in Chinesisch oder Englisch, englische Wörter klein, Akronyme groß?
- [ ] Feste Figurennamen, Aktion vor Zeile, Stimmprofil je Figur, Sprecherwechsel markiert?
- [ ] Voices: I2V, 1080p, max. 2, `<<<voice_n>>>` direkt hinter dem Figurennamen, keine widersprechende Stimmfarbe?
- [ ] Eine Kamerabewegung, kein Schnittvokabular?
- [ ] Verbote als Sätze im Prompt, `negative_prompt` als Substantivliste?

---

## 17. Merksystem

- **5 oder 10.** Nichts dazwischen.
- **Ton = 1080p.** Start+End bei 2.6 = 1080p und stumm.
- **zh/en.** Mehr Sprachen nur mit Kling 3.0.
- **Name, Aktion, Zeile, Wechsel.** Die vier Dialogregeln.
- **Figur, dann Voice, dann Zeile:** `[Figur]<<<voice_1>>>: "…"`.

---

## 18. Behauptungen, die nicht pauschal als gesichert gelten

- 2.5 Turbo könne Ton erzeugen.
- 2.6 könne Ton in 720p oder bei First/Last Frame.
- Voice Control funktioniere bei Text-to-Video (laut Guide noch nicht).
- TTS-/Lip-Sync-Voice-IDs seien als 2.6-Voices nutzbar (getrennte Namensräume).
- `@VoiceName` funktioniere über diesen Proxy (Legacy: `<<<voice_n>>>`).
- `camera_control` oder Motion Brush seien bei 2.x verfügbar.
- Deutscher Dialog werde nativ gesprochen.
- Drei oder mehr Voices funktionierten so gut wie zwei.

---

## 19. Quellen

### Primärquellen
1. Kling API 2.6 Text/Image to Video – https://kling.ai/document-api/api/video/2-6/text-to-video , …/image-to-video
2. Kling API 2.6 Voice Customization – https://kling.ai/document-api/api/video/2-6/voice-customization
3. Kling API 2.5 Turbo – https://kling.ai/document-api/api/video/2-5-turbo/text-to-video , …/image-to-video
4. Kling API Legacy Image to Video – https://kling.ai/document-api/api/video/3-0-omni/image-to-video/legacy (`<<<voice_1>>>`, `negative_prompt`-Empfehlung)
5. Kling API Motion Control 2.6 – https://kling.ai/document-api/api/video/motion-control/2-6
6. Capability Map Video – https://kling.ai/document-api/guides/capability-map/video
7. KLING VIDEO 2.6 User Guide – https://kling.ai/quickstart/klingai-video-26-audio-user-guide
8. Grundlagen-Guides – https://kling.ai/quickstart/text-to-video-prompt-guide , …/image-to-video-guide , …/ai-video-start-end-frames , …/how-to-choose-video-mode
9. Motion Control User Guide – https://kling.ai/quickstart/motion-control-user-guide

### Praxisabgleich
10. Interne Recherche `tasks/research/kling.md` und Proxy-Code (`providers/kling`) für Constraints und Defaults.

### Quellenwarnung
Die Grundlagen-Guides beschreiben ältere Kling-Versionen (Standard/Professional, 5/10 s). Ihre Formeln gelten weiter, ihre Hinweise auf Kamerasteuerung und Motion Brush nicht.

---

## Schlussformel

Ein guter Kling-2.x-Prompt beantwortet fünf Fragen:

1. Reicht ein Take von 5 oder 10 Sekunden, und ist die Auflösung passend zu Ton und Frames gewählt?
2. Wer ist im Bild, und welche **eine** Bewegung passiert?
3. Was liefert das Bild, und beschreibt der Text wirklich nur, was sich bewegt?
4. Wer sagt was, mit welcher Stimme, und ist der Sprecherwechsel markiert?
5. Was hört man außerdem, und ist Musik gewollt?
