# Kling Tools Prompting Guide (virtuelle Modelle)

**Stand: 11. Oktober 2026**  
**Fokus:** Kling-Spezialfunktionen, die dieser Proxy als virtuelle Modelle anbietet: `kling-lip-sync`, `kling-avatar`, `kling-effects`, `kling-multi-elements`, `kling-text-to-audio`, `kling-video-to-audio`, `kling-tts` und `kling-commerce` (Talking Agent, Goods Studio, Apparel Replicator)  
**Ziel:** für jede Funktion wissen, **welche Eingabe die Arbeit macht**, was der Prompt überhaupt noch steuert und wie Skripte, Selling Points, Stimmen und Auswahlpunkte formuliert sein müssen

> Die wichtigste Regel: Bei den Kling-Tools ist der Prompt **selten der Hauptkanal**. Bei Lip Sync steuert das Audio, bei Effects die Vorlage, bei Multi-Elements die Auswahl, bei Commerce das Skript und die Produktdaten. Gute Ergebnisse entstehen hier durch **saubere Eingaben** (Gesicht frontal, Audio sauber und richtig geschnitten, Produktbild freigestellt, Skript sprechbar) und durch einen kurzen Prompt, der nur das tut, wofür er gedacht ist.

---

## 1. Quellenlage und Vertrauensstufen

### Stufe A: Primärquellen (offiziell)

Kling-API-Doku zu Avatar, Text-to-Speech, Lip Sync und Face Detection, Text-to-Audio, Video-to-Audio, Video Effects, Multi-Elements sowie den Solutions Video Commerce (`talking_agent`), Goods Studio und AI Apparel Replicator (`clothing_dupe`). Dazu die User Guides „Kling AI Avatar 2.0“ (5. Dez. 2025) und „KLING VIDEO 2.6“ (Abschnitt Sound Effects). Markiert als **[Doku]** bzw. **[User Guide]**.

### Stufe B: Drittquellen

Die einzige verfügbare Liste der TTS-Voice-IDs außerhalb des offiziellen (nicht ausgelesenen) qingque-Dokuments stammt aus dem ComfyUI-Quellcode. Markiert als **[Drittquelle]**.

### Stufe C: eigene Empfehlungen

Vieles bei diesen Tools ist nicht als „Prompt-Guide“ dokumentiert, nur als Feldbeschreibung. Formulierungsregeln, die daraus abgeleitet sind, stehen als **[Empfehlung]**.

### Proxy-Bezug

Die Tools laufen über `POST /v1/videos` mit dem jeweiligen virtuellen Modell (TTS über `POST /v1/audio/speech`). Der Task ergibt sich aus dem Modell, nur `kling-commerce` braucht `task`. Die Feldnamen in diesem Guide sind die des Proxys; die Kling-Namen stehen in Klammern.

---

## 2. Übersicht

| Proxy-Modell | Task | Eingaben (Rollen) | Prompt steuert | Ausgabe |
|---|---|---|---|---|
| `kling-lip-sync` | `lip_sync` | Video `base_video` + Audio `speech` **oder** `speech.text` | **nichts** (wird nicht gesendet) | Video |
| `kling-avatar` | `avatar` | Bild `subject` + Audio `speech` **oder** `speech.text` | Mimik, Gesten, Kamera | Video |
| `kling-effects` | `effect` | `effect` + 1 oder 2 Bilder `subject` | **nichts** | Video |
| `kling-multi-elements` | `multi_element_edit` | Video `base_video` + `selections` + `edit_mode` (+ 1–2 Bilder) | die Änderung, mit `<<<video_1>>>`/`<<<image_1>>>` | Video |
| `kling-text-to-audio` | `text_to_audio` | `prompt`, `seconds` 3–10 | Klang | Audio |
| `kling-video-to-audio` | `video_to_audio` | Video `base_video` | SFX (`prompt`), Musik (`audio.bgm_prompt`) | Video mit Ton + Audio |
| `kling-tts` | – (`/v1/audio/speech`) | `input`, `voice`, `language`, `speed` | – | MP3 |
| `kling-commerce` | `commerce_talking_agent` | Avatar-Bild oder `commerce.avatar_id`, Produktbilder, `commerce.*` | Aktionen des Avatars | Video |
| `kling-commerce` | `commerce_goods_studio` | 1–5 Produktbilder, Titel, Beschreibung | – (Titel/Beschreibung sind der Prompt) | Video 15/30/60 s |
| `kling-commerce` | `commerce_apparel` | Quellvideo, 1–5 Produktbilder, optional Model-Bilder, BGM, Stimme | – (`commerce.product_info`) | Video |

---

## 3. Text-to-Speech (`kling-tts`)

TTS ist auch die Grundlage für Lip Sync und Avatar mit `speech.text`.

### 3.1 Fakten [Doku]

- `POST /v1/audio/speech` mit `{"model": "kling-tts", "input": "…", "voice": "<tts-voice-id>", "language": "en", "speed": 1.0}`.
- `input` ≤ **1000 Zeichen**; Kling prüft den Inhalt.
- `language` ∈ {`zh`, `en`} und muss **zur Stimme passen**.
- `speed` 0.8–2.0, eine Nachkommastelle.
- Die Voice-IDs sind ein **eigener Namensraum** (z. B. `oversea_male1`). Custom/Preset-Voices für Videos (`asset-kling-voice-…`) und Commerce-Voices sind etwas anderes.
- Offizielle Liste: externes qingque-Dokument (Dateinamen „Voice Name#Voice ID#Voice Language“). **Nicht ausgelesen.** Eine **[Drittquelle]**-Liste (ComfyUI) nennt u. a. für `en`: `oversea_male1`, `uk_boy1`, `uk_man2`, `calm_story1`, `reader_en_m-v1`, `commercial_lady_en_f-v1`, `chat1_female_new-3`, `cartoon-girl-01`; für `zh` u. a. `zhinen_xuesheng`, `ai_shatang`, `tianmeixuemei-v1`. Vor produktivem Einsatz testen.

### 3.2 Text für TTS schreiben

- **Satzzeichen steuern Pausen.** Der Avatar-Guide: „Use punctuation marks like commas to separate text and enable proper pausing.“
- Aus dem 2.6-Guide übertragbar **[Empfehlung]**: Englische Wörter klein, Akronyme und Eigennamen groß („KLING“, „USB-C“), damit sie buchstabiert bzw. richtig betont werden.
- Zahlen, Preise und Einheiten so schreiben, wie sie gesprochen werden sollen („twenty-nine ninety-nine“ statt „29.99 €“), wenn die Aussprache wichtig ist **[Empfehlung]**.
- Deutsch ist **keine** TTS-Sprache. Deutscher Text mit `language: en` klingt bestenfalls wie ein englischer Sprecher, der Deutsch liest **[Empfehlung, nicht getestet]**.

### 3.3 Länge

Für Lip Sync darf das Ergebnis höchstens 60 s, für Avatar höchstens 300 s lang sein. Als Faustregel ergeben 1000 Zeichen englischer Text bei `speed 1.0` grob 60 bis 70 s Sprache **[Empfehlung]**. Für Lip Sync deshalb deutlich unter 1000 Zeichen bleiben.

---

## 4. Lip Sync (`kling-lip-sync`)

### 4.1 Was passiert [Doku]

Zweistufig: Kling erkennt Gesichter im Video (Face Identification, kostenpflichtig) und legt dann einen Tonausschnitt auf **genau ein** Gesicht. Der Proxy erledigt beide Schritte im Hintergrund. Text-getriebenes Lip Sync gibt es im aktuellen Kling-API nicht als eigenen Modus. Der Proxy erzeugt aus `speech.text` zuerst TTS und nutzt dessen `audio_id`.

### 4.2 Eingaben

```json
{
  "model": "kling-lip-sync",
  "references": [
    {"type": "video", "role": "base_video", "url": "https://…/presenter.mp4"},
    {"type": "audio", "role": "speech", "url": "https://…/line.mp3"}
  ],
  "audio": {"start_ms": 0, "end_ms": 6200, "insert_at_ms": 500, "volume": 1.0, "original_volume": 0.3}
}
```
oder statt der Audio-Referenz:
```json
"speech": {"text": "Welcome back, everyone. Today we test three hiking boots.", "voice": "oversea_male1", "language": "en", "speed": 1.0}
```

| Feld | Bedeutung | Regeln |
|---|---|---|
| Video | Kling-Video (≤ 30 Tage) oder Upload | mp4/mov, ≤ 100 MB, **2–60 s**, 720p/1080p, Kanten 512–2160 px |
| Audio `speech` | mp3/wav/m4a/aac | ≤ 5 MB, **2–60 s** |
| `audio.start_ms` / `end_ms` | Ausschnitt aus dem Ton | Ausschnitt ≥ 2 s; `end_ms` ≤ Länge des Tons |
| `audio.insert_at_ms` | wo im Video der Ton beginnt | Ton muss im Video liegen und sich **≥ 2 s** mit dem Gesichtsintervall überlappen |
| `audio.volume` | Lautstärke des neuen Tons | 0–2, Default 1 |
| `audio.original_volume` | Lautstärke des Originaltons | 0–2, Default 1; ohne Wirkung bei stummem Video |
| `audio.face_id` | welches Gesicht | Default im Proxy: die Person mit dem **längsten** sichtbaren Intervall |

### 4.3 Proxy-Defaults, die man kennen muss

- `insert_at_ms` ist ohne Angabe der **Beginn des gewählten Gesichtsintervalls**.
- `end_ms` ist bei `speech.text` die TTS-Länge. Bei einer **hochgeladenen** Audiodatei setzt der Proxy ohne Angabe `min(Gesichtsintervall, 60 s)`. **Ist die Audiodatei kürzer, gib `audio.end_ms` selbst an**, sonst liegt das Ende hinter dem Tonende und Kling lehnt ab.
- Der Prompt wird bei Lip Sync **nicht** an Kling geschickt.

### 4.4 Was gute Ergebnisse macht [Empfehlung, abgeleitet aus Doku und Avatar-Guide]

- **Ein** gut sichtbares, frontales Gesicht über die ganze Sprechzeit; Mund unverdeckt, keine starke Kopfdrehung.
- Bei mehreren Personen `audio.face_id` bewusst setzen (die längste Person ist nicht immer die sprechende).
- Ton sauber: eine Stimme, keine Musik darunter (Musik kann man über `original_volume` aus dem Original behalten).
- `original_volume` auf 0–0.3 senken, wenn im Originalvideo gesprochen wird; sonst überlagern sich zwei Stimmen.
- Satzlänge an die Gesichtssichtbarkeit anpassen; der Ton läuft nicht über das Video hinaus.

---

## 5. Avatar (`kling-avatar`)

### 5.1 Was es ist [Doku, User Guide]

Aus **einem Bild** und **Ton** entsteht ein sprechender oder singender Avatar. Das Bild ist zugleich der Startframe. Avatar 2.0 schafft laut Guide bis zu **5 Minuten**, stabile Handbewegungen, Gesang, Rap, verschiedene Figurentypen (real, Cartoon, Tiere) und mehrere Sprachen über hochgeladenes Audio (Guide-Beispiele: Englisch, Japanisch, Koreanisch, Chinesisch).

### 5.2 Eingaben

| Feld | Regeln |
|---|---|
| Bild `subject` | jpg/png, ≤ 10 MB, ≥ 300 px, 1:2.5–2.5:1 |
| Audio `speech` | mp3/wav/m4a/aac, ≤ 5 MB, **2–300 s**; oder `speech.text` → TTS (≤ 1000 Zeichen, zh/en) |
| `prompt` | ≤ 2500 Zeichen: **Aktionen, Emotion, Kamera** |
| `resolution` / `quality` | 720p (std) oder 1080p (pro) |

Die Dauer ergibt sich aus dem Ton.

### 5.3 Der Avatar-Prompt [User Guide]

Der Prompt beschreibt **nicht**, was gesagt wird (das liefert das Audio), sondern **Performance**: Emotion, Gesten, Blick, Körper, Kamera.

Offizielle Beispiele:
```
Excited and joyful, the child raises her hands covered in paint, laughing and
interacting with the colorful art supplies on the table, camera zooms in.
```
```
Put hands together in front of your chest, and finally hold them together and tell a
story naturally.
```
```
The female singer sings to the audience while looking confident, occasionally looking
and smiling at the camera, hand on the microphone, natural movements on the arms,
stationary shot.
```
```
In a commercial advertisement, a person holds a product in one hand and speaks directly
to the camera, delivering a clear tagline. The gesture is deliberate and confident,
with the product slightly lifted toward the viewer.
```
```
The man is angry, shown in both facial expression and action.
```

### 5.4 Formel [Empfehlung, aus den Beispielen]

```
[Emotion/Grundhaltung], [Blickrichtung], [1–2 Gesten mit Ablauf "then/finally"],
[Bewegungsqualität: natural, subtle, energetic], [Kamera: stationary / slow zoom in /
subtle handheld].
```

- **Kamera** ausdrücklich nennen. Ein Creator-Beispiel arbeitet sogar mit Verboten: „Very subtle handheld camera movement. No cars passing by. No distortions. Very natural movements“.
- Gesten nur, wenn die Hände im Bild Platz haben.
- Bei langen Clips (Minuten) eher Grundhaltung und wiederkehrende Gesten beschreiben als eine Handlungskette.

### 5.5 Bild für den Avatar [Empfehlung, gestützt auf die Commerce-Doku]

Einzelperson, Gesicht klar und frontal, Mund unverdeckt, gleichmäßiges Licht, keine Sonnenbrille, keine starken Filter. Für Gesten Halbkörper mit sichtbaren Händen.

---

## 6. Video Effects (`kling-effects`)

### 6.1 Fakten [Doku]

- `effect` = eine Vorlage aus dem Katalog (219 laut Doku: 204 mit einem Bild, 15 mit zwei Bildern). Der Proxy pflegt den Katalog mit Bildanzahl unter `GET /v1/providers/kling/effects`.
- **Kein Prompt, keine Dauer, keine Auflösung.** Die Vorlage legt alles fest.
- Single-Image-Effekte: genau **1** Bild. Dual-Image-Effekte (z. B. `hug_pro`, `kiss_pro`, `fight_pro`, `heart_gesture_pro`, `daily_ootd`, `smooth_transition`, `pet_skateboard`): genau **2** Bilder.
- Bei Dual-Effekten werden zwei **Porträts** zu einem Komposit gestellt: **erstes Bild links, zweites rechts**.
- Bilder jpg/png, ≤ 10 MB, ≥ 300 px, 1:2.5–2.5:1.
- Vorlagen werden regelmäßig eingestellt (z. B. `magic_match_tree` am 2026-07-03; `kiss`, `hug`, `fight` ohne `_pro` am 2026-01-30). Vor der Nutzung den Katalog abfragen.

### 6.2 Was zählt

Da es keinen Prompt gibt, entscheidet **das Bild** [Empfehlung]:
- Das Motiv muss zur Vorlage passen: `pet_*`-Effekte mit einem Haustier, Personeneffekte mit einer gut sichtbaren Person, Ganzkörper-Tanzeffekte mit Ganzkörperbild.
- Ein Subjekt, zentriert, freier Hintergrund, keine Gruppenfotos.
- Bei Dual-Effekten zwei ähnlich aufgebaute Porträts (Ausschnitt, Licht, Blickrichtung zur Mitte).

```json
{"model": "kling-effects", "effect": "hug_pro",
 "references": [
   {"type": "image", "role": "subject", "url": "https://…/left_person.jpg"},
   {"type": "image", "role": "subject", "url": "https://…/right_person.jpg"}
 ]}
```

---

## 7. Multi-Element-Editing (`kling-multi-elements`)

### 7.1 Was es tut [Doku]

In einem vorhandenen Video wird ein Objekt **markiert** (Klickpunkte auf Frames), dann **hinzugefügt**, **getauscht** oder **entfernt**. Kling verfolgt die Auswahl selbst über das Video.

### 7.2 Eingaben

| Feld | Regeln |
|---|---|
| Video `base_video` | mp4/mov, **2–5 s oder 7–10 s**, 720–2160 px, 24/30/60 fps; Kling-Video ≤ 30 Tage oder Upload |
| `selections` | 1–10 Frames, je 1–10 Punkte `{x, y}` in [0, 1] |
| `edit_mode` | `addition` (1–2 Bilder), `swap` (genau 1 Bild), `removal` (kein Bild) |
| Bilder | Rolle `reference`; **vorher auf das Objekt zuschneiden**, Kling schneidet nicht selbst; ≤ 10 MB |
| `prompt` | ≤ 2500, mit `<<<video_1>>>` und `<<<image_n>>>` |
| `negative_prompt` | ≤ 2500 |
| `resolution` / `quality` | 720p (std) / 1080p (pro) |

Ausgabe: **5 s** bei 2–5-s-Eingabe, **10 s** bei 7–10-s-Eingabe. Videos zwischen 5 und 7 s lehnt der Proxy ab.

### 7.3 Auswahlpunkte setzen

- Koordinaten sind relativ (0–1) zur Bildbreite bzw. -höhe. Die Doku ist bei der Ecke uneindeutig formuliert; üblich und vermutlich gemeint ist **(0, 0) oben links** [Empfehlung, nicht verifiziert].
- `frame_index` ist die Framenummer im (normalisierten) Video. Bei 24 fps liegt Sekunde 2 bei Frame 48.
- **[Empfehlung]** Punkte **mitten auf** das Objekt setzen, nicht auf Kanten. Mehrere Punkte auf verschiedene Teile eines Objekts (Kopf, Körper) statt eines Punkts. Wenn das Objekt verdeckt wird oder sich stark dreht, einen weiteren Frame markieren.
- Für interaktive Auswahl mit Maskenvorschau gibt es die nativen Session-Routen (`/v1/providers/kling/v1/videos/multi-elements/{init,add,delete,clear,preview}-selection`). Der virtuelle Proxy-Weg führt die Auswahl ohne Vorschau aus.

### 7.4 Offizielle Prompt-Schablonen [Doku]

| Modus | Englisch | Chinesisch |
|---|---|---|
| `addition` | `Using the context of <<<video_1>>>, seamlessly add [x] from <<<image_1>>>` | `基于<<<video_1>>>中的原始内容，以自然生动的方式，将<<<image_1>>>中的【】，融入<<<video_1>>>的【】` |
| `swap` | `swap [x] from <<<image_1>>> for [x] from <<<video_1>>>` | `使用<<<image_1>>>中的【】，替换<<<video_1>>>中的【】` |
| `removal` | `Delete [x] from <<<video_1>>>` | `删除<<<video_1>>>中的【】` |

Die Doku verlangt, dass der Prompt das Video **und** die benötigten Bilder referenziert.

### 7.5 Ausformulierte Beispiele

```
Delete the chick from <<<video_1>>>
```
(offizielles Beispiel)

```
swap the red ceramic mug from <<<image_1>>> for the white paper cup on the desk from <<<video_1>>>
```

```
Using the context of <<<video_1>>>, seamlessly add the small brown terrier from
<<<image_1>>> sitting on the left side of the sofa, matching the warm lamp light.
```

**[Empfehlung]** Das `[x]` im Video so benennen, dass es zur markierten Auswahl passt („the white paper cup on the desk“), und beim Hinzufügen Ort und Licht angeben. Im `negative_prompt` Substantive wie `blurry edges, duplicate object, flicker`.

---

## 8. Text-to-Audio (`kling-text-to-audio`)

### 8.1 Fakten [Doku]

- `prompt` **≤ 200 Zeichen**, `seconds` 3.0–10.0 (eine Nachkommastelle).
- Ergebnis MP3 und WAV.
- Laut 2.6-Guide gedacht für „standalone audio“ (Sound Effect Generation). Ob Sprache erzeugt wird, ist nicht dokumentiert; dafür ist TTS da.

### 8.2 Prompt-Formel [User Guide, 2.6-Soundregeln]

- **SFX:** `Quelle (Objekt/Handlung) + Zustand + Klangcharakter`, z. B. „a heavy wooden door suddenly slams, sharp bang with a short room echo“.
- **Musik:** `Instrument + Genre + Emotion`, z. B. „solo piano, slow jazz, melancholic“.
- **Atmo:** `Ort + Schichten`, z. B. „rainy night street, rain on awnings, distant traffic, occasional car horn“.

### 8.3 Regeln [Empfehlung]

- 200 Zeichen reichen für **ein** Klangereignis oder **eine** Atmo, nicht für eine Abfolge.
- Akustik nennen: „close-miked“, „distant“, „in a small tiled bathroom“, „outdoors, dry“.
- Dauer zum Ereignis passend wählen: ein Türknall braucht 3 s, eine Atmo 10 s.
- Für längere Atmo mehrere Clips erzeugen und schneiden.

---

## 9. Video-to-Audio (`kling-video-to-audio`)

### 9.1 Fakten [Doku]

- Video 3–20 s (Kling-Video ≤ 30 Tage oder mp4/mov ≤ 100 MB).
- `prompt` → Kling `sound_effect_prompt` (≤ 200), `audio.bgm_prompt` (≤ 200), `audio.asmr` → `asmr_mode` („enhances detailed sound effects … suitable for highly immersive content“).
- Ergebnis: das Video **mit Ton** und separate Audiodateien.
- Laut Changelog für alle Kling-Videos und für eigene Uploads.

### 9.2 Prompts aufteilen [Empfehlung]

| Kanal | Inhalt | Beispiel |
|---|---|---|
| `prompt` (SFX) | Geräusche, die zu sichtbaren Aktionen gehören | „footsteps on gravel, a car door closing, birds in the distance“ |
| `audio.bgm_prompt` | Musikbett | „calm acoustic guitar, warm, slow tempo“ |
| `audio.asmr` | Nahklang | nur für Nahaufnahmen (Schneiden, Gießen, Kratzen) |

- SFX in der **Reihenfolge der Bildereignisse** nennen.
- Wer keine Musik will, lässt `bgm_prompt` leer. Ob das Modell dann sicher keine Musik erzeugt, ist **nicht dokumentiert**.
- Typischer Einsatz: stumme Clips aus Kling 2.5 Turbo, 2.6 First/Last Frame oder Omni-Edit nachvertonen.

```json
{"model": "kling-video-to-audio",
 "references": [{"type": "video", "role": "base_video", "task_id": "vid-kling-…"}],
 "prompt": "knife slicing through crisp vegetables on a wooden board, a pan sizzling, soft kitchen room tone",
 "audio": {"bgm_prompt": "light bossa nova, relaxed, low volume", "asmr": true}}
```

---

## 10. Video Commerce (`kling-commerce`)

Drei Solutions mit eigenem Eingabemodell. Gemeinsam: Bilder jpg/png/webp bis 50 MB, ≥ 300 px, 1:2.5–2.5:1; Auflösung 720p/1080p.

### 10.1 Talking Agent (`commerce_talking_agent`)

#### Was es tut [Doku]

Ein Avatar spricht ein Verkaufsskript. Die Pipeline erzeugt das Bild frei und repariert die Lippen in einem Nachbearbeitungsmodell. Daher eignet sie sich laut Doku für **Skripte über 15 Sekunden** und mehrsprachige Voice-overs. Zwei Modi entstehen automatisch:

| Modus | wenn | Ergebnis | Sprechtempo |
|---|---|---|---|
| **Creator Voiceover** | keine Produktdaten | Avatar die ganze Zeit im Bild | `commerce.speech_rate` 0.8 / 1.0 / 1.2 |
| **Product Voiceover** | Produktbild, Titel, Preis, Zielgruppe oder Selling Points vorhanden | Wechsel aus Avatar-, Avatar-mit-Produkt- und Produkt-Close-up-Shots | **nicht** einstellbar |

#### Eingaben im Proxy

| Proxy | Kling | Regeln |
|---|---|---|
| Bild Rolle `avatar` **oder** `commerce.avatar_id` | `avatar_image` / `avatar_id` | genau eins von beiden |
| `speech.voice` (oder `commerce.voice`) | `settings.voice_id` | **Pflicht** bei Avatar-Bild, **verboten** bei `avatar_id` (Bibliotheks-Avatare haben eigene Stimme) |
| Bilder Rolle `product` | `ref_image` | 0–5; im Product-Modus ≥ 1 |
| `commerce.title` | `goods_title` | ≤ 500; im Product-Modus Pflicht |
| `commerce.price` | `goods_price` | ≤ 256 |
| `commerce.audience[]` | `goods_target_audience` | bis 20 × ≤ 200 |
| `commerce.selling_points[]` | `goods_selling_point` | bis 20 × ≤ 500 |
| `commerce.script` | `speech_script` | **Pflicht**, ≤ 2000 |
| `commerce.allow_polish` | `settings.allow_polish` | Kling-Default `false` = Skript wortgetreu |
| `commerce.bgm` | `settings.bgm_enabled` | Musik wählt das System |
| `prompt` | `settings.action_prompt` | ≤ 2500, Performance des Avatars |
| `aspect_ratio` | | `9:16` (Default) oder `16:9` |

Bibliotheks-Avatare: `avatar_eva_female`, `avatar_oliver_male`, `avatar_elena_female`, `avatar_adam_male`, `avatar_anna_female`, `avatar_rajput_male`, `avatar_mia_female`, `avatar_river_male`, `avatar_marcus_male`, `avatar_vivian_female`, `avatar_lee_male`, `avatar_toto_cartoon`.

Stimmen für eigene Avatar-Bilder: `male_calm_informative`, `female_clear_rational`, `female_gentle_soothing`, `female_bright_engaging`, `male_crisp_persuasive`, `female_intelligent_narrative`, `male_clear_professional`, `male_energetic_sporty`, `female_warm_rich`. Eigene Stimmen sind nicht möglich.

#### Das Skript [Doku + Empfehlung]

- Laut Doku „colloquial text that can be read aloud directly“. Keine Regieanweisungen, keine Klammern, keine Emojis, keine Aufzählungszeichen im Skript **[Empfehlung]**.
- **Die Skriptlänge bestimmt Dauer und Kosten**, eine Dauer lässt sich nicht setzen.
- `allow_polish: false` (Default), wenn der Text freigegeben ist (Rechtstexte, Markenclaims). `true`, wenn das System glätten darf.
- Welche Sprachen unterstützt werden, nennt die Doku nicht ausdrücklich („multilingual voiceovers“). Die Stimmen sind englisch benannt. **Sprache testen**, bevor man sich auf etwas anderes als Englisch verlässt.

Aufbau, der für Verkaufsvideos funktioniert **[Empfehlung]**:
1. **Hook** (1 Satz, Problem oder Neugier),
2. **Produkt + Kernnutzen** (1–2 Sätze),
3. **2–3 Belege** (je 1 kurzer Satz, konkret),
4. **Angebot/Preis**, falls gewünscht,
5. **Call to Action** (1 Satz).

Etwa 130–150 Wörter ergeben grob eine Minute **[Empfehlung]**.

#### Selling Points und Zielgruppe [Empfehlung]

Die Felder sind Material für die Shotplanung und ggf. die Skriptpolitur, keine Bildunterschriften.
- **Selling Point** = ein überprüfbares Merkmal plus Nutzen, kurz: „IP67 dust and water resistance“ (offizielles Beispiel), „30-hour battery, one charge for the whole weekend“.
- Keine Superlative ohne Beleg („best ever“), keine Mehrfachaussagen in einem Eintrag.
- **Zielgruppe** knapp und konkret: „Campers“ (offizielles Beispiel), „commuters in rainy cities“.
- Was im Skript gesagt wird, sollte zu den Selling Points passen, sonst zeigt das Bild etwas anderes, als der Ton sagt.

#### Action-Prompt (`prompt`)

Wie beim Avatar (§5.4): Haltung, Gesten, Blick. Im Product-Modus laut Doku: Hände entspannt und sichtbar, weil der Avatar mit dem Produkt gerendert wird.

```
Friendly and confident, she looks into the camera, smiles at the start, uses open
hand gestures on the key points and briefly lifts the product toward the camera when
she mentions it. Natural, relaxed movement.
```

#### Bildanforderungen [Doku]

- Avatar: Einzelperson, Gesicht frontal und klar, Mund frei; keine Gruppenfotos, Profile, Sonnenbrillen, starken Filter; hochauflösend, gleichmäßiges Licht.
- Produkt: zentriert, ruhiger Hintergrund, gleichmäßiges Licht; 1–5 Ansichten (vorn, Seite, Detail); keine Bilder mit viel Text, Wasserzeichen oder Montage-Artefakten.

#### Beispiel

```json
{
  "model": "kling-commerce",
  "task": "commerce_talking_agent",
  "aspect_ratio": "9:16",
  "resolution": "1080p",
  "references": [
    {"type": "image", "role": "avatar", "url": "https://…/host.png"},
    {"type": "image", "role": "product", "url": "https://…/lantern_front.png"},
    {"type": "image", "role": "product", "url": "https://…/lantern_detail.png"}
  ],
  "speech": {"voice": "female_bright_engaging"},
  "commerce": {
    "title": "Trailbeam Camping Lantern",
    "price": "39 USD",
    "audience": ["Campers", "Families with kids"],
    "selling_points": ["IP67 dust and water resistance", "30-hour battery on one charge", "Warm and cold light modes"],
    "script": "Ever had your lantern die on the second night? This is the Trailbeam. It's waterproof, it runs thirty hours on one charge, and you can switch between warm and bright white light. Grab yours for thirty-nine dollars before your next trip.",
    "allow_polish": false,
    "bgm": true
  },
  "prompt": "Cheerful and natural, she holds the lantern at chest height, points at the switch when mentioning the light modes and smiles into the camera at the end."
}
```

### 10.2 Goods Studio (`commerce_goods_studio`)

#### Fakten [Doku]

- Aus Produktbildern, Titel und Beschreibung entsteht ein **Produktvideo von 15, 30 oder 60 s**; das System analysiert Bilder und Kernargumente und baut daraus Szenen.
- Eingaben: 1–5 Bilder Rolle `product`, `commerce.title` (Pflicht, ≤ 200), `commerce.description` (≤ 2000), `seconds` 15/30/60, `aspect_ratio` 9:16/1:1/16:9.
- Kein Prompt-Feld; **Titel und Beschreibung sind der Prompt.**
- Bilder: lange Kante ≥ 1000 px, sauberer Hintergrund, zentriert, gleichmäßiges Licht, mehrere Winkel.

#### Beschreibung schreiben [Empfehlung]

```
[Was es ist, Material, Farbe]. [Für wen und wofür]. [3–5 Kernmerkmale, je ein Satz].
[Stimmung/Umgebung, in der das Produkt gezeigt werden soll].
```

Beispiel:
```
Handmade matte black ceramic coffee mug, 350 ml, with a raw clay base. For slow
morning coffee at home. Keeps drinks warm longer thanks to thick walls. Dishwasher
safe. Comfortable wide handle. Show it in a calm Scandinavian kitchen with soft
morning light.
```

- Längere Videos (60 s) brauchen mehr Material: mehr Ansichten und mehr Merkmale. Bei nur einem Bild lieber 15 s.
- Keine Preise oder Rabattcodes in die Beschreibung, wenn sie nicht im Bild erscheinen sollen. Ob Text eingeblendet wird, ist nicht dokumentiert.

### 10.3 AI Apparel Replicator (`commerce_apparel`)

#### Fakten [Doku]

- Ein **Referenzvideo** mit Kleidung wird zur Vorlage: Kling tauscht das Kleidungsstück gegen das eigene Produkt und behält Tempo, Kamera, Bewegung, Szenenästhetik und Präsentationsstil.
- Ausgabe 5–180 s, so lang wie das Referenzvideo.
- Eingaben:

| Proxy | Kling | Regeln |
|---|---|---|
| Video `base_video` | `source_video` | mp4/mov, ≤ 100 MB, **5–180 s**, Kanten 576–4553 px, Fläche ≤ 8 294 400 px, Seitenverhältnis 0.4–2, 24–60 fps (Ausgabe 24 fps) |
| Bilder `product` | `product_image` | 1–5 |
| Bilder `model` | `model_image` | 0–5; ohne = Model aus dem Video |
| Audio `bgm` | `bgm` | 0–1; mp3/m4a/wav, ≤ 50 MB; wird geloopt/gekürzt; ohne = automatische Musik |
| `speech.voice` / `commerce.voice` | `voice` | optional; **mit** Stimme = TTS-Voice-over, **ohne** = Talking-Head mit nativem Ton |
| `commerce.product_info` | `product_info` | ≤ 2500, Produktbeschreibung |
| `aspect_ratio` | | 9:16, 2:3, 3:4, 1:1, 4:3, 3:2, 16:9, 21:9 |

Stimmen: `energetic_sales_girl`, `gentle_sales_woman`, `crisp_sales_girl`, `mature_sales_woman`, `calm_sales_woman`, `soft_sales_woman`, `energetic_sales_boy`, `enthusiastic_sales_man`, `steady_sales_man`, `calm_sales_man`.

#### Was gute Ergebnisse macht [Doku + Empfehlung]

- Produktbilder: lange Kante ≥ 1000 px, sauberer Hintergrund, zentriert, gleichmäßiges Licht, mehrere Ansichten; **keine** Text-Wasserzeichen oder starken Filter.
- Referenzvideo mit **demselben Kleidungstyp** wählen (Kleid ↔ Kleid, Jacke ↔ Jacke). Je ähnlicher Schnitt und Länge, desto weniger muss das Modell erfinden **[Empfehlung]**.
- `product_info` beschreibt das **Kleidungsstück**, nicht die Szene: Typ, Schnitt, Länge, Material, Farbe, Muster, Details (Knöpfe, Kragen, Taschen), Passform. Die Szene kommt aus dem Video.

```
Women's midi wrap dress in sage green viscose with a subtle white polka dot print,
V-neck, short flutter sleeves, self-tie waist belt, flowing A-line skirt ending below
the knee. Relaxed fit, lightweight, slightly sheer in bright light.
```

---

## 11. Häufige Fehler

| Funktion | Symptom | Ursache | Abhilfe |
|---|---|---|---|
| Lip Sync | „no face“ | kein erkennbares Gesicht | frontales, unverdecktes Gesicht |
| Lip Sync | falsche Person bewegt die Lippen | Default = längstes Gesichtsintervall | `audio.face_id` setzen |
| Lip Sync | Ablehnung wegen Zeiten | Ausschnitt < 2 s, Überlappung < 2 s, `end_ms` > Tonlänge | Zeiten prüfen, bei Upload `end_ms` setzen |
| Lip Sync | zwei Stimmen hörbar | Originalton läuft mit | `original_volume` senken |
| Avatar | steife Figur | kein Performance-Prompt | Emotion, Gesten, Kamera beschreiben |
| TTS | falsche Aussprache | Sprache passt nicht zur Stimme, Akronyme klein | `language` passend, Akronyme groß |
| Effects | 400 Bildanzahl | Single/Dual verwechselt | Katalog prüfen (1 oder 2 Bilder) |
| Effects | Vorlage existiert nicht | eingestellt | Katalog neu abfragen |
| Multi-Elements | 400 Videolänge | 5–7 s oder > 10 s | auf 2–5 s oder 7–10 s schneiden |
| Multi-Elements | falsches Objekt bearbeitet | Punkte auf Kante/Hintergrund | Punkte mittig, mehrere Punkte/Frames |
| Multi-Elements | eingefügtes Objekt mit Hintergrundresten | Bild nicht zugeschnitten | Objekt vorher freistellen |
| Text-to-Audio | Prompt abgelehnt | > 200 Zeichen | ein Ereignis, kürzer |
| Video-to-Audio | ungewollte Musik | Musik nicht ausgeschlossen | `bgm_prompt` leer lassen, im SFX-Prompt „no music“ (Wirkung nicht garantiert) |
| Talking Agent | 400 Stimme | Stimme bei `avatar_id` gesetzt oder fehlt bei Avatar-Bild | Regel §10.1 |
| Talking Agent | 400 `speech_rate` | im Product-Modus gesetzt | weglassen |
| Talking Agent | Video zu lang/teuer | Skript zu lang | Skript kürzen |
| Goods Studio | eintönige 60 s | zu wenig Material | mehr Ansichten und Merkmale oder 15/30 s |
| Apparel | Kleidung verformt | Referenzvideo zeigt anderen Kleidungstyp | passendes Referenzvideo |

---

## 12. Checkliste

- [ ] Richtiges virtuelles Modell (und bei Commerce der richtige `task`)?
- [ ] Prompt nur dort, wo er etwas steuert (nicht bei Lip Sync und Effects)?
- [ ] TTS: Text ≤ 1000 Zeichen, Sprache zh/en passend zur Voice-ID, Satzzeichen für Pausen?
- [ ] Lip Sync: Video 2–60 s, Audio 2–60 s, ein frontales Gesicht, Zeiten geprüft, `face_id` bei mehreren Personen?
- [ ] Avatar: Performance-Prompt mit Emotion, Gesten, Kamera; Audio 2–300 s?
- [ ] Effects: Vorlage im aktuellen Katalog, Bildanzahl 1 oder 2, links/rechts bedacht?
- [ ] Multi-Elements: Video 2–5 oder 7–10 s, Punkte mittig, Bilder zugeschnitten, Schablone mit `<<<video_1>>>`/`<<<image_1>>>`?
- [ ] Audio-Tools: ein Ereignis pro 200 Zeichen, SFX und Musik getrennt?
- [ ] Talking Agent: Skript sprechbar, Länge = Dauer, `allow_polish` bewusst, Stimme/Avatar-Regel erfüllt, Selling Points konkret?
- [ ] Goods Studio: Titel, Beschreibung mit Merkmalen, Bilder ≥ 1000 px, Dauer zum Material passend?
- [ ] Apparel: passendes Referenzvideo, `product_info` beschreibt nur das Kleidungsstück, Stimme bewusst gewählt oder weggelassen?

---

## 13. Behauptungen, die nicht pauschal als gesichert gelten

- Lip Sync könne mehrere Personen gleichzeitig synchronisieren (aktuell nur eine).
- Der Prompt beeinflusse Lip Sync oder Effects.
- TTS-Voice-IDs, Video-Voices und Commerce-Voices seien austauschbar.
- TTS spreche Deutsch.
- Talking Agent spreche jede Sprache gleich gut (nicht dokumentiert, testen).
- Video-to-Audio erzeuge ohne `bgm_prompt` sicher keine Musik.
- Text-to-Audio erzeuge verständliche Sprache.
- Die ComfyUI-Liste der TTS-Stimmen sei vollständig und aktuell.
- Effect-Vorlagen blieben dauerhaft verfügbar.
- Multi-Element-Koordinaten hätten den Ursprung sicher oben links (Doku-Formulierung uneindeutig).

---

## 14. Quellen

### Primärquellen
1. Avatar – https://kling.ai/document-api/api/video/avatar
2. Text to Speech – https://kling.ai/document-api/api/video/avatar/text-to-speech
3. Lip Sync – https://kling.ai/document-api/api/video/lip-sync ; Face Detection – …/lip-sync/face-detection
4. Text to Audio – https://kling.ai/document-api/api/video/audio-generation/text-to-audio
5. Video to Audio – https://kling.ai/document-api/api/video/audio-generation/video-to-audio
6. Video Effects – https://kling.ai/document-api/api/effects/video-effects ; Effects Center – https://kling.ai/document-api/api/effects/templates
7. Multi-Elements – https://kling.ai/document-api/api/video/multi-elements
8. Video Commerce (talking_agent) – https://kling.ai/document-api/api/ecommerce-replication/video-commerce
9. Goods Studio – https://kling.ai/document-api/api/ecommerce-replication/goods-studio
10. AI Apparel Replicator – https://kling.ai/document-api/api/ecommerce-replication/apparel
11. Kling AI Avatar 2.0 User Guide – https://kling.ai/quickstart/kling-ai-avatar-2-user-guide
12. KLING VIDEO 2.6 User Guide (SFX- und Musikformeln) – https://kling.ai/quickstart/klingai-video-26-audio-user-guide
13. Changelog – https://kling.ai/document-api/updates/api

### Drittquellen
14. ComfyUI `comfy_api_nodes/nodes_kling.py` (TTS-Voice-IDs) – https://raw.githubusercontent.com/comfyanonymous/ComfyUI/master/comfy_api_nodes/nodes_kling.py

### Praxisabgleich
15. Interne Recherche `tasks/research/kling.md`, `docs/SPEC.md` (§8.7–8.10) und Proxy-Code (`providers/kling`) für Feldzuordnung und Defaults.

---

## Schlussformel

Für jedes Kling-Tool gilt dieselbe Prüfung:

1. Welche Eingabe macht hier die eigentliche Arbeit (Audio, Vorlage, Auswahl, Skript, Produktdaten)?
2. Erfüllt diese Eingabe die harten Grenzen (Dauer, Größe, Anzahl, Sprache)?
3. Steuert der Prompt hier überhaupt etwas, und wenn ja, nur das, wofür er gedacht ist?
4. Passt das, was man hört, zu dem, was man sieht?
