# Kling Omni Prompting Guide (Kling 3.0 Omni und Kling O1)

**Stand: 11. Oktober 2026**  
**Fokus:** Kling 3.0 Omni und Kling O1 („Omni Video“): Referenzbilder, Elements, Feature-Video (Kamera-, Bewegungs- und Anschlussreferenz), Video-Edit mit Base-Video, First/Last Frame, Multi-Shot (nur 3.0 Omni), Referenzsyntax `<<<image_1>>>` / `<<<element_1>>>` / `<<<video_1>>>` bzw. `@`-Namen, Mengenlimits  
**Ziel:** jede Eingabe bekommt im Prompt eine eindeutige Rolle, und der Prompt sagt in einem Satz, **was mit welcher Referenz geschehen soll**

> Die wichtigste Regel: Für Omni ist **jede Referenz ein Teil des Prompts**. Kling sagt das selbst: „the images, videos, elements, and text you upload are all treated as prompts“. Ein Omni-Prompt ist deshalb kein Szenentext mit Anhängen, sondern eine **Anweisung über Referenzen**: „Change the jacket in `<<<video_1>>>` to the jacket from `<<<image_1>>>`.“ Wer die Referenzen nicht beim Namen nennt, überlässt dem Modell, welches Bild wofür gedacht ist.

---

## 1. Quellenlage und Vertrauensstufen

### Stufe A: Primärquellen (offiziell)

1. **Kling-API-Doku Omni Video**: 3.0 Omni (`…/3-0-omni/video-omni`) und O1 (`…/o1/video-omni`) in der neuen API, plus die **Legacy-Seite** `…/3-0-omni/video-omni/legacy` (`/v1/videos/omni-video`, `model_name` `kling-v3-omni` bzw. `kling-video-o1`). **Dieser Proxy ruft beide Omni-Modelle über die Legacy-API auf** (§7). Daraus stammen Syntax, Rollen und Limits.
2. **Capability Map** (Stand 2026-05-19) und **Changelog** (u. a. 2026-04-23 und 2026-06-17 zu Referenzvideo und 4K).
3. **Offizielle User Guides**: „KLING VIDEO O1 User Guide“ (15. Dez. 2025, mit offiziellen **Prompt-Strukturen** für jede Edit- und Referenzaufgabe), „Kling VIDEO 3.0 Omni Model User Guide“ (6. Feb. 2026), „Kling Element Library User Guide“ (5. Feb. 2026).

Markiert als **[Doku]** bzw. **[User Guide]**.

### Stufe B: Praxis

Community-Guides (fal.ai, Morphic) behandeln Omni nur am Rand. Wo sie zitiert werden: **[Praxis]**.

### Stufe C: eigene Empfehlungen

Abgeleitete Regeln, vor allem zur Nummerierung im Proxy und zur Formulierung von Edits: **[Empfehlung]**.

### Was nicht übernommen wurde

Aussagen wie „Omni editiert beliebig lange Videos“, „Omni erzeugt Ton beim Video-Edit“ oder „O1 kann Multi-Shot“. Die Doku widerspricht allen drei.

---

## 2. Was Omni offiziell ist

O1 war laut Kling „the world's first unified multimodal video model“: Referenzgenerierung, Text-to-Video, Start/End-Frames, Inpainting, Transformation, Stilisierung und „Video Extension“ (als Next-Shot-Generierung) in einem Modell. 3.0 Omni ist der Nachfolger auf der 3.0-Basis mit Ton, Multi-Shot, Video-Character-Elements mit Stimme und 15 Sekunden.

### 2.1 Kernfähigkeiten im Vergleich

| Bereich | Kling 3.0 Omni | Kling O1 |
|---|---|---|
| Proxy-Modell-ID | `kling-3.0-omni` (Alias `kling-v3-omni`) | `kling-o1` (Alias `kling-video-o1`) |
| Dauer | 3–15 s | 3–10 s; **nur Startbild ohne weitere Referenzen: 5 oder 10 s** |
| Auflösung | 720p, 1080p, 4K | 720p, 1080p |
| Seitenverhältnis | 16:9, 9:16, 1:1; **Pflicht ohne Startbild und ohne Edit** | dito |
| Text-to-Video | ✔ (mit Ton, Multi-Shot) | ✔ (ohne Ton) |
| First Frame / First+Last | ✔ / ✔ (bis 3 Elements dazu) | ✔ / ✔ (**keine** Elements, nicht bei > 2 Bildern) |
| Referenzbilder + Elements | ✔ (Limits §4) | ✔ (nur Multi-Image-Elements) |
| Video-Character-Elements | ✔ | ✘ |
| Feature-Video (Referenz) | ✔, 3–15 s | ✔, 3–10 s |
| Base-Video (Edit) | ✔ | ✔ |
| Multi-Shot | ✔ (bis 6 Shots) | ✘ |
| Nativer Ton | ✔ (`generate_audio`), **nicht** mit Referenz- oder Edit-Video | ✘ (nur Originalton eines Videos) |
| Element-Stimme | ✔ | ✘ |
| Promptlänge im Proxy (Legacy) | 2500 Zeichen | 2500 Zeichen |
| `negative_prompt` | nicht im Legacy-Omni-Schema | dito |

### 2.2 Was 3.0 Omni gegenüber O1 offiziell besser kann [User Guide]

- deutlich bessere Element-Konsistenz und Promptbefolgung, „fewer visual distortions“,
- Ton und Multi-Shot bei Text-to-Video,
- Video-Character-Elements (3–8 s Video, Aussehen + Stimme),
- Stimme an Multi-Image-Elements binden,
- bis 15 s.

Für Video-Edit und „Prompt Transformation“ sagt der 3.0-Omni-Guide: „function the same as in O1“. Die O1-Prompt-Strukturen (§9) gelten also für beide.

### 2.3 Wann Omni und wann Kling 3.0?

| Aufgabe | Modell |
|---|---|
| Startbild animieren, Element aus dem Startbild stabil halten | Kling 3.0 reicht (`kling_3_0.md`) |
| Figuren/Produkte **ohne** Startbild in eine neue Szene setzen | **Omni** (Referenzbilder/Elements) |
| bestehendes Video verändern (Objekt, Hintergrund, Stil, Wetter) | **Omni Edit** (oder Multi-Element-Edit, `kling_tools.md`) |
| nächsten/vorherigen Shot zu einem Video erzeugen | **Omni Feature-Video** |
| Kamerabewegung oder Körperbewegung eines Videos übernehmen | **Omni Feature-Video**; für präzise Körperbewegung Kling 3.0 Motion Control |

---

## 3. Das mentale Modell: Referenzvertrag

Bevor du schreibst, lege für **jede** Eingabe fest:

| Eingabe | Was sie liefert | Was sie **nicht** liefert |
|---|---|---|
| Referenzbild (`reference`) | Aussehen eines Subjekts, eines Orts oder eines Stils – je nachdem, was der Prompt sagt | Bildausschnitt, Pose, Kamerawinkel (außer der Prompt verlangt es) |
| Element | stabiles Aussehen aus mehreren Ansichten, ggf. Stimme | Ort, Handlung, Kamera |
| Startbild (`first_frame`) | den exakten ersten Frame, Seitenverhältnis | Bewegung, Ton |
| Endbild (`last_frame`) | den exakten letzten Frame | den Weg dorthin |
| Feature-Video (`reference` vom Typ Video) | Kamerabewegung, Körperbewegung, Kontext für Vor-/Nachshot, Stil | wird **nicht** editiert |
| Base-Video (`base_video`) | das Material, das verändert wird; Länge und Seitenverhältnis der Ausgabe | – |

Der häufigste Fehler: ein Referenzbild ohne Rolle im Prompt. Dann weiß das Modell nicht, ob es eine Figur, einen Ort oder einen Stil liefern soll. Die offiziellen Beispiele lösen das immer im Satz: „The video style matches that of `<<<image_2>>>`“, „sits on the sofa from `[@Image1]`“.

---

## 4. Harte Limits [Doku]

### 4.1 Dateien

| | 3.0 Omni | O1 |
|---|---|---|
| Bilder | jpg/jpeg/png, ≥ 300 px, Seitenverhältnis 1:2.5–2.5:1; **≤ 10 MB über die Legacy-API (Proxy)** | dito |
| Video | mp4/mov, ≤ 200 MB, **3–15.5 s** (Proxy: 3–15 s), Kanten 700–4553 px, Fläche ≤ 8 294 400 px, 24–60 fps (Ausgabe 24 fps), max. 1 Video, nur per URL | mp4/mov, ≤ 200 MB, **3–10 s**, max. 1 Video |

### 4.2 Mengen von Bildern und Elements (3.0 Omni)

| Situation | Limit |
|---|---|
| mit Startbild bzw. Start+Endbild | max. 3 Elements |
| kein Video, nur Multi-Image-Elements | Referenzbilder + Elements ≤ 7 |
| kein Video, nur Video-Character-Elements | ≤ 3 |
| kein Video, beide Element-Typen | Video-Character ≤ 3 **und** Referenzbilder + Multi-Image ≤ 4 |
| mit Video, nur Multi-Image-Elements | Referenzbilder + Elements ≤ 4 |
| mit Video, Video-Character-Elements | Doku widersprüchlich: einmal „≤ 1“, einmal „not supported“; Video-Character-Elements und Bilder nicht gleichzeitig |

**O1:** ohne Video ≤ 7 Bilder/Elements, mit Video ≤ 4; nur Multi-Image-Elements; bei Start+Endbild keine Elements; mit mehr als zwei Bildern kein Start/End-Frame.

### 4.3 Kombinationsregeln

- **Edit (Base-Video):** kein Start-/Endbild, kein Multi-Shot, kein nativer Ton. Die Ausgabe hat **die Länge des Eingangsvideos**; `seconds` wird ignoriert. Abgerechnet wird die gerundete Eingangsdauer.
- **Feature-Video:** 3.0 Omni erlaubt Multi-Shot nur im **Intelligence-Modus** (Changelog 2026-06-17: `multi_shot=true`, `shot_type=intelligence`, Shotbeschreibungen im Prompt). Ton muss aus sein. O1: zusätzlich nur ein Startbild, kein Endbild.
- **Ton:** Sobald ein Video im Spiel ist, gibt es keinen nativen Ton. Der Originalton lässt sich mit `provider_options.kling.keep_original_sound: "yes"` übernehmen (Proxy-Default: `"no"`).
- **Nur Endbild** ist nie erlaubt.
- **4K mit Referenzvideo (3.0 Omni):** Changelog 2026-04-23 schließt es aus, Changelog 2026-06-17 meldet „4K generation is now supported“. **Nicht verifiziert.**

---

## 5. Schritt 1: Modus wählen

| Proxy-Task | Eingaben | Omni-Funktion |
|---|---|---|
| `text_to_video` | nur `prompt`, `aspect_ratio` | Text-to-Video |
| `image_to_video` | Bild `first_frame` (+ Elements) | Startbild |
| `first_last_frame` | `first_frame` + `last_frame` (+ Elements nur 3.0 Omni) | Start/End-Frame |
| `reference_to_video` | 1–8 Referenzen (Bilder, Elements, max. 1 Video) mit Rolle `reference` | Referenzgenerierung; ein Video wird hier als **Feature**-Video übergeben |
| `edit` | Video `base_video` (+ bis zu 4 Bilder/Elements) | Video-Edit |
| `multi_shot` (nur 3.0 Omni) | `shots` oder `prompt` + `shot_mode=intelligence`, optional `first_frame` + Elements | Multi-Shot |

**[Empfehlung]** Wenn du unsicher bist, ob ein Video bearbeitet oder nur zitiert werden soll, frag: *Soll das Ergebnis dasselbe Material mit Änderungen sein?* → `edit`. *Soll es neues Material sein, das sich am Video orientiert?* → `reference_to_video`.

---

## 6. Die Masterformeln [User Guide]

### 6.1 Referenzgenerierung (Bilder/Elements)

> **[Detailed description of Elements] + [Interactions/actions between Elements] + [Environment or background] + [Visual directions like lighting, style, etc]**

### 6.2 Text-to-Video

> **Subject (subject description) + Movement + Scene (scene description) + (Cinematic Language + Lighting + Atmosphere)**

Laut Guide gilt: „the level of details in the prompt determines the richness of content in the generated video“.

### 6.3 Edit und Feature-Video

Die O1-Guides geben für jede Aufgabe eine **Satzschablone** vor (§9). Sie sind der wichtigste offizielle Prompt-Baustein für Omni.

### 6.4 Arbeitsformel [Empfehlung]

```
[Aufgabe als Verb mit Referenzen]           Change … in <<<video_1>>> to … from <<<image_1>>>
[Was unverändert bleiben soll]              Keep the camera movement, timing and the person's face unchanged.
[Details zur neuen Sache]                   The jacket is matte black leather with silver zippers.
[Licht/Stil, nur wenn es sich ändern darf]  Match the existing evening light.
```

Für Referenzgenerierung:

```
[Wer, über Referenz]  [tut was]  [mit wem/was, über Referenz]  [wo, über Referenz oder Text]
[Kamera]  [Licht/Stil, ggf. "in the style of <<<image_n>>>"]  [Ton, nur 3.0 Omni ohne Video]
```

---

## 7. Referenzsyntax und Nummerierung

### 7.1 Zwei Schreibweisen [Doku]

| API | Bild | Element | Video |
|---|---|---|---|
| Legacy (`/v1/videos/omni-video`) – **so ruft der Proxy auf** | `<<<image_1>>>` | `<<<element_1>>>` | `<<<video_1>>>` |
| neue API (`/omni-video/…`) und App | `@image_1` | `@Name` (z. B. `@Zhang`) | `@video_1` |

Die User Guides und App-Beispiele schreiben `@Kling Lipstick`, `[@Image1]`, `[@Video]`. **Über diesen Proxy verwendest du die Legacy-Form `<<<…_n>>>`.** Der `name` einer Referenz wird derzeit nicht als `@Name` in den Prompt eingesetzt.

### 7.2 Nummerierung im Proxy

- `<<<image_n>>>`: n-tes **Bild** in der Reihenfolge der `references`, zählt ab 1. Der Proxy schreibt alle Bilder (auch Start-/Endbild, mit `type` markiert) in dieser Reihenfolge in `image_list`.
- `<<<element_n>>>`: n-tes **Element** in der Reihenfolge der Element-Referenzen.
- `<<<video_1>>>`: das eine Video (Feature oder Base).

**Unsicherheit:** Ob Kling Start-/Endbilder in der `image_n`-Zählung mitzählt, ist nicht dokumentiert. **[Empfehlung]** Start-/Endbilder nicht über `<<<image_n>>>` ansprechen, Referenzbilder **vor** Frame-Bildern in die `references` legen und im Prompt einen sprechenden Beschreiber mitführen: `<<<image_1>>> (the red sofa)`.

### 7.3 Namen von Elements [Doku]

Für `@Name`: Element-Namen dürfen keine Teilstrings voneinander sein (`@Zhang` / `@ZhangSan`) und nicht mit Prompttext kollidieren (`@gmail` bei einer E-Mail-Adresse). Element-Namen ≤ 20 Zeichen, Beschreibungen ≤ 100 Zeichen. Der Guide empfiehlt „distinctive and relevant“ Namen und eine Beschreibung mit Kernmerkmalen und Schlüsseldetails.

### 7.4 Jede Referenz mindestens einmal nennen

Die Multi-Elements-Doku formuliert es ausdrücklich („the prompt must include references to the video and image(s) required for the editing“). Für Omni zeigen alle offiziellen Beispiele dasselbe Muster. **[Empfehlung]** Eine Referenz, die im Prompt nicht vorkommt, liefert nichts Verlässliches und verbraucht einen Platz im Limit.

---

## 8. Referenzgenerierung (Bilder und Elements)

### 8.1 Offizielle Beispiele (Legacy-Syntax)

```
<<<image_1>>> strolling through the streets of Tokyo, encountered <<<element_1>>> and
<<<element_2>>>, and jumped into the arms of <<<element_2>>>. The video style matches
that of <<<image_2>>>
```

```
Pure black background. In the darkness, a river of color—matching the <<<element_1>>>
shade—streaks across, leaving a rich, flawless trail. The trail then "comes alive,"
flowing like liquid and elegantly spreading and blending on the surface to form
patterned designs <<<image_1>>>.
```
(Original: `@Kling Lipstick` und `@Image`.)

### 8.2 Rolle eines Bildes im Satz festlegen

| Rolle | Formulierung |
|---|---|
| Figur/Objekt | `<<<image_1>>> (the banana cat) walks …` |
| Ort/Hintergrund | `… sits on the sofa from <<<image_2>>>` / `background <<<image_2>>>` |
| Stil/Look | `The video style matches that of <<<image_3>>>` / `Cinematic look <<<image_3>>>` |
| Kleidung | `<<<element_1>>> wears the coat from <<<image_2>>>` |

### 8.3 Interaktion beschreiben

Kling betont „multi-subject fusion“: Mehrere Subjekte behalten ihre Merkmale auch in Interaktion. Der Prompt muss die **Beziehung** liefern: wer wen anschaut, wer was übergibt, wer wo steht. Ohne Interaktion stehen Referenzen oft nebeneinander wie in einer Collage [Empfehlung].

### 8.4 Aussehen nicht doppelt beschreiben [Empfehlung]

Ein Element trägt das Aussehen. Wiederholt der Text Haarfarbe oder Kleidung abweichend, kämpfen beide Quellen. Beschreibe Zustand und Handlung, nicht Identität.

---

## 9. Video-Edit (Base-Video): offizielle Satzschablonen

Alle Schablonen stammen aus dem O1 User Guide und gelten laut 3.0-Omni-Guide auch für 3.0 Omni. Hier in Legacy-Syntax.

### 9.1 Hinzufügen

```
Add [Beschreibung] from <<<image_1>>> to <<<video_1>>>
Add [Beschreibung] to <<<video_1>>>
Add <<<element_1>>> to <<<video_1>>>
Add <<<element_1>>> and [Beschreibung] from <<<image_1>>> to <<<video_1>>>
```

Offizielles API-Beispiel: `Put the crown from <<<image_1>>> on the girl in blue from <<<video_1>>>.`

### 9.2 Entfernen

```
Remove [Beschreibung] from <<<video_1>>>
```
Laut Guide genügt „remove bystanders“ als natürliche Anweisung; das Modell rekonstruiert den Hintergrund.

### 9.3 Einstellung oder Winkel ändern

```
Generate [another angle/composition, e.g. close-up, wide shot] in <<<video_1>>>
```

### 9.4 Subjekt ändern

```
Change [Subjekt] in <<<video_1>>> to [Zielsubjekt]
Change [Subjekt] in <<<video_1>>> to [Zielsubjekt] from <<<image_1>>>
Change [Subjekt] in <<<video_1>>> to <<<element_1>>>
```

### 9.5 Hintergrund ändern

```
Change the background in <<<video_1>>> with [Beschreibung]
Change the background in <<<video_1>>> with <<<image_1>>>
```

### 9.6 Lokale Änderung

```
Change [Inhalt] in <<<video_1>>> to [Zielinhalt]
Change [Inhalt] in <<<video_1>>> to [Zielinhalt] from <<<image_1>>>
```

### 9.7 Restyle

```
Change <<<video_1>>> to [Stil] style
Change <<<video_1>>> to the style of <<<image_1>>>
```
Offiziell gezeigte Stile: American cartoon, Japanese anime, cyberpunk, pixel art, ink wash painting, watercolor, clay, figure, Monet-inspired, wool felt.

### 9.8 Umfärben, Wetter, Green Screen

```
Change the [Objekt] in the <<<video_1>>> to [Farbe]
Change the [Objekt] in the <<<video_1>>> to [Farbe] from <<<image_1>>>
Change <<<video_1>>> to [Wetter, z. B. "a rainy day"]
Change the background in <<<video_1>>> to a green screen, and keep [was bleiben soll]
```

### 9.9 Kombinationen

Laut Guide lassen sich Aufgaben in einem Prompt kombinieren („adding a subject while modifying the background“, „changing the style while using elements“). **[Empfehlung]** Höchstens zwei Änderungen pro Durchgang. Jede weitere Änderung erhöht das Risiko, dass das Modell mehr verändert als verlangt.

### 9.10 Scope schließen [Empfehlung]

Die Schablonen sagen, was sich ändert, aber nicht, was bleibt. Ergänze einen Satz:

```
Keep everything else in <<<video_1>>> unchanged: the camera movement, timing, the
woman's face and the lighting.
```

### 9.11 Edit-Regeln im Überblick

- Ausgabe = Länge des Eingangsvideos, Seitenverhältnis vom Video (`aspect_ratio` wird nicht gesendet).
- Kein Start-/Endbild, kein Multi-Shot, kein nativer Ton.
- Originalton behalten: `provider_options.kling.keep_original_sound: "yes"`. Geänderte Mundbewegungen passen dann nicht unbedingt zum Ton [Empfehlung].
- Bis zu 4 Bilder/Elements zusätzlich.

---

## 10. Feature-Video: Anschluss, Kamera, Bewegung

### 10.1 Offizielle Schablonen [User Guide]

```
Based on <<<video_1>>>, generate the next shot: [Shotbeschreibung]
Based on <<<video_1>>>, generate the previous shot: [Shotbeschreibung]
Take <<<image_1>>> as the start frame. Generate a new video following the camera movement of the <<<video_1>>>
Animate the character in <<<image_1>>> with the same motion as the character in the <<<video_1>>>
```

Offizielles API-Beispiel:
```
Referring to the camera movement style in <<<video_1>>>, generate a video: <<<element_1>>>
and <<<element_2>>> strolling through the streets of Tokyo, encountering <<<image_1>>> by chance.
```

### 10.2 Next Shot gut schreiben

Offizielles Beispiel:
```
Based on <<<video_1>>>, generate the next shot: from the back seat, show a medium shot of
a middle-aged man and a young man in front. They angle slightly apart, forming a tense,
restrained opposition as they turn to look out their windows. The background is
blurred, and soft natural light creates muted olive-green and brown tones with light
film grain.
```

Bausteine: neue **Kameraposition**, wer im Bild ist, **eine** Handlung, Licht und Grade, die zum Quellvideo passen. Das ist der Omni-Ersatz für die nicht mehr dokumentierte Kling-Video-Extension.

### 10.3 Was zu beachten ist

- Bei Proxy-Task `reference_to_video` wird ein Video als Feature übergeben (Rolle `reference`).
- Ton aus (3.0 Omni), höchstens Originalton.
- **[Empfehlung]** Für Körperbewegung mit hoher Präzision ist Kling 3.0 Motion Control die spezialisiertere Funktion (`kling_3_0.md` §17). Omni „same motion as“ ist flexibler, aber weniger exakt.

---

## 11. First/Last Frame in Omni

Offizielle Schablonen:
```
Take <<<image_1>>> as the start frame, [describe changes in subsequent frames]
Take <<<image_1>>> as the start frame, take <<<image_2>>> as the end frame, [describe the changes between start and end frames]
```

Im Proxy legst du Start- und Endbild über die Rollen `first_frame` und `last_frame` fest; der Proxy setzt `type: first_frame/end_frame`. Der Prompt muss die Bilder dann nicht mehr per Index benennen, sondern beschreibt **den Übergang** [Empfehlung, wegen der Zählunsicherheit §7.2].

- 3.0 Omni: bis zu 3 Elements dazu.
- O1: keine Elements, nicht mit mehr als zwei Bildern; reines Startbild nur 5 oder 10 s.
- Bilder sollen sich ähneln; starke Unterschiede erzeugen laut Grundlagen-Guide einen Schnitt.

---

## 12. Multi-Shot mit 3.0 Omni

### 12.1 Regeln

Wie bei Kling 3.0: 1–6 Shots, je ≥ 1 s, Summe = Gesamtdauer, Shot-Prompt ≤ 512 Zeichen. Im Proxy `shots[{prompt, seconds}]` oder `shot_mode=intelligence`. Mit Feature-Video nur Intelligence (Changelog).

### 12.2 Offizielle Muster

```
Shot 1 (2s): Wide shot, @Boxer A and @Boxer B face off in the center of the rooftop, feet apart in a boxing stance.
Shot 2 (2s): Both move in, testing each other up close: @Boxer A throws a quick punch, @Boxer B sidesteps and blocks.
Shot 3 (3s): @Boxer A continues the attack, landing a punch on @Boxer B's head, and @Boxer B retaliates.
Shot 4 (4s): Wide shot, the two boxers continue their intense fight.
Shot 5 (2s): A bird's-eye view of the scene shows the two separated and having stopped fighting.
```

Über den Proxy als `shots` mit `<<<element_1>>>`/`<<<element_2>>>` statt `@Boxer A/B`:

```json
{
  "model": "kling-3.0-omni",
  "task": "multi_shot",
  "seconds": 13,
  "aspect_ratio": "16:9",
  "references": [
    {"type": "element", "asset_id": "asset-kling-element-111"},
    {"type": "element", "asset_id": "asset-kling-element-222"}
  ],
  "shots": [
    {"seconds": 2, "prompt": "Wide shot, <<<element_1>>> (boxer A) and <<<element_2>>> (boxer B) face off in the center of a rooftop at dusk, feet apart in a boxing stance."},
    {"seconds": 2, "prompt": "Medium shot, <<<element_1>>> throws a quick jab, <<<element_2>>> sidesteps and blocks."},
    {"seconds": 3, "prompt": "Close-up, <<<element_1>>> lands a punch on <<<element_2>>>'s head, <<<element_2>>> retaliates."},
    {"seconds": 4, "prompt": "Wide handheld shot, the two boxers continue the intense fight, city lights behind them."},
    {"seconds": 2, "prompt": "Bird's-eye view, the two boxers step apart and stop fighting, chests heaving."}
  ]
}
```

Ohne Startbild gilt `aspect_ratio` als Pflicht. Der Proxy schickt `16:9`, wenn nichts gesetzt ist.

### 12.3 Dialog über Shots

Offizielles Muster (Elements mit gebundener Stimme):
```
Shot 1 (3s): Mid-shot, background @Image. @Grace sits on the sofa eating cookies as @Alan
walks in holding @Samoyed. @Samoyed lunges for the cookie in @Grace's hand. @Grace says,
"Hey! Watch your dog!"
Shot 2 (2s): @Alan sits beside her, pulling the leash and lifting @Samoyed. Close-up,
@Alan says, "He just likes cookies more than me."
Shot 3 (3s): Close-up, @Grace smiles and says, "Well, he has good taste at least."
```

Für Dialogregeln (feste Namen, Aktion vor Zeile, Sprecherwechsel markieren) siehe `kling_3_0.md` §14. Sie gelten für 3.0 Omni unverändert.

---

## 13. Ton in Omni

- **3.0 Omni ohne Video:** `generate_audio: true` erzeugt nativen Ton (Dialog, SFX, Musik). Sprachen und Dialogformeln wie Kling 3.0.
- **Mit Video (Feature oder Base):** kein nativer Ton. Der Proxy lehnt `generate_audio` dann ab. Originalton: `provider_options.kling.keep_original_sound: "yes"`.
- **O1:** nie nativer Ton.
- **Element-Stimme:** Ein Element mit gebundener Stimme spricht in dieser Stimme. Keine Stimmfarbe im Prompt nachschieben (User Guide: „not recommended to set the tone again“).
- Der Element-Guide nennt für Stimmaufnahmen 5–30 s, eine Person, saubere Umgebung, moderates Tempo, neutrale Emotion. Der 3.0-Omni-Guide nennt für das Hinzufügen einer Stimme zu einem Multi-Image-Element „≥ 3 s“. Im Zweifel 5–30 s verwenden.

---

## 14. Parameter vs. Prompt

| Feld (Proxy) | Werte | Hinweis |
|---|---|---|
| `seconds` | 3.0 Omni 3–15, O1 3–10 (reines Startbild 5/10) | bei `edit` ignoriert bzw. `auto` |
| `resolution` / `quality` | 720p, 1080p, 4K (nur 3.0 Omni) | 4K mit Video unklar |
| `aspect_ratio` | 16:9, 9:16, 1:1 | nur T2V, Referenzgenerierung, Multi-Shot ohne Startbild |
| `generate_audio` | bool (nur 3.0 Omni, nicht mit Video) | |
| `shots`, `shot_mode` | nur 3.0 Omni | |
| `provider_options.kling.keep_original_sound` | `"yes"`/`"no"` | Default `"no"` |
| `references[].role` | `first_frame`, `last_frame`, `reference`, `base_video` | Video mit Rolle ≠ `base_video` = Feature |

Kein `negative_prompt`-Feld im Legacy-Omni-Schema. Die Doku sagt: „Text prompt words, which can include positive and negative descriptions.“ Verbote also als Sätze in den Prompt.

---

## 15. Ausgearbeitete Beispiele

### 15.1 Produkt aus Element in neuer Szene (3.0 Omni, 8 s)

```json
{
  "model": "kling-3.0-omni",
  "task": "reference_to_video",
  "seconds": 8,
  "aspect_ratio": "9:16",
  "resolution": "1080p",
  "generate_audio": true,
  "references": [
    {"type": "element", "asset_id": "asset-kling-element-333"},
    {"type": "image", "url": "https://…/marble_bathroom.png"}
  ],
  "prompt": "<<<element_1>>> (the amber perfume bottle) stands on a wet marble shelf in the bathroom from <<<image_1>>>. Slow macro push-in, water droplets run down the glass, warm morning light from a frosted window on the left. Soft water drips and a quiet room tone, no music, no on-screen text."
}
```

### 15.2 Edit: Hintergrund tauschen, alles andere behalten (O1)

```json
{
  "model": "kling-o1",
  "task": "edit",
  "references": [
    {"type": "video", "role": "base_video", "url": "https://…/interview.mp4"},
    {"type": "image", "url": "https://…/library.png"}
  ],
  "provider_options": {"kling": {"keep_original_sound": "yes"}},
  "prompt": "Change the background in <<<video_1>>> with <<<image_1>>>. Keep the man, his gestures, the framing and the timing unchanged, and match the warm side light of <<<image_1>>> on his face."
}
```

### 15.3 Next Shot aus einem vorhandenen Clip (3.0 Omni)

```json
{
  "model": "kling-3.0-omni",
  "task": "reference_to_video",
  "seconds": 5,
  "aspect_ratio": "16:9",
  "references": [{"type": "video", "url": "https://…/car_scene.mp4"}],
  "prompt": "Based on <<<video_1>>>, generate the next shot: a close-up through the windshield of the driver, a middle-aged man in a black suit, gripping the wheel and glancing at the rear-view mirror. Same muted olive-green and brown grade with light film grain, soft overcast light."
}
```

### 15.4 Restyle (O1)

```
Change <<<video_1>>> to wool felt style. Keep the camera movement, the composition and
the girl's actions unchanged.
```

### 15.5 Kleidung aus Bild auf Element in neuer Szene (3.0 Omni)

```
<<<element_1>>> (the young woman) walks down a sunlit runway wearing the coat from
<<<image_1>>>. Tracking shot from the front at eye level, then she stops and turns
once. Clean white set, soft top light, fashion lookbook style.
```

---

## 16. Häufige Fehler und Diagnose

| Symptom | Ursache | Abhilfe |
|---|---|---|
| Referenzbild wird als Hintergrund statt als Figur benutzt | Rolle im Prompt fehlt | Rolle im Satz festlegen (§8.2) |
| Falsches Bild wird verwendet | Nummerierung verwechselt | Reihenfolge der `references` prüfen, Beschreiber in Klammern mitführen |
| 400 wegen Mengenlimit | zu viele Bilder/Elements, v. a. mit Video | Limits §4.2; mit Video ≤ 4 |
| 400 `generate_audio` | Ton zusammen mit Video verlangt | Ton aus, ggf. `keep_original_sound` |
| Edit verändert zu viel | Scope nicht geschlossen, zu viele Änderungen | „Keep … unchanged“, max. zwei Änderungen |
| Edit-Ergebnis anders lang als erwartet | Ausgabe = Länge des Eingangsvideos | Eingangsvideo vorher schneiden (3–15 s bzw. 3–10 s) |
| Element-Figur driftet | Aussehen im Text abweichend beschrieben | Aussehen streichen, nur Handlung/Zustand |
| O1 lehnt Start+End mit Elements ab | O1 erlaubt das nicht | 3.0 Omni nehmen |
| O1 lehnt 7 s mit reinem Startbild ab | nur 5/10 s | 5 oder 10 s, oder ein Referenzbild ergänzen |
| Multi-Shot mit Feature-Video schlägt fehl | nur Intelligence erlaubt | `shot_mode=intelligence`, Shots im Prompt beschreiben |
| `@Name` wirkt nicht | Proxy nutzt Legacy-Syntax | `<<<element_n>>>` verwenden |
| Video wird abgelehnt | Länge, Auflösung (< 700 px), fps oder Größe | Limits §4.1 |

---

## 17. Master-Checkliste

- [ ] Modus klar: Referenzgenerierung, Startbild, Start+End, Edit, Feature-Video, Multi-Shot?
- [ ] Jede Referenz im Prompt genannt, mit Rolle (Figur, Ort, Stil, Kleidung, zu editierendes Video)?
- [ ] Nummerierung `<<<image_n>>>` / `<<<element_n>>>` passt zur Reihenfolge der `references`?
- [ ] Start-/Endbilder über Rollen gesetzt, nicht über `<<<image_n>>>` angesprochen?
- [ ] Mengenlimits eingehalten (ohne Video ≤ 7, mit Video ≤ 4; O1 nur Multi-Image-Elements)?
- [ ] Edit: Schablone aus §9 plus „Keep … unchanged“?
- [ ] Edit/Feature: kein `generate_audio`; Originalton bewusst gewählt?
- [ ] `aspect_ratio` gesetzt, wenn weder Startbild noch Edit?
- [ ] O1: Dauer 3–10 s (reines Startbild 5/10), kein Multi-Shot, kein Ton?
- [ ] Verbote als Sätze im Prompt (kein `negative_prompt`-Feld)?
- [ ] Prompt ≤ 2500 Zeichen, Shot-Prompts ≤ 512?

---

## 18. Merksystem

- **Referenz = Prompt.** Jede Eingabe braucht im Satz eine Rolle.
- **7 / 4 / 1:** ohne Video sieben Bilder+Elements, mit Video vier, genau ein Video.
- **Base ändert, Feature zitiert.**
- **Video heißt: kein nativer Ton.**
- **Edit-Länge = Input-Länge.**
- **O1 = 10 s, stumm, ohne Multi-Shot.**

---

## 19. Behauptungen, die nicht pauschal als gesichert gelten

- Start-/Endbilder würden in `<<<image_n>>>` sicher mitgezählt (nicht dokumentiert).
- 4K funktioniere mit Referenzvideo (widersprüchliche Changelog-Einträge).
- Video-Character-Elements funktionierten zusammen mit einem Referenzvideo (Doku widersprüchlich: „≤ 1“ vs. „not supported“).
- Omni erzeuge beim Edit neuen Ton oder synchronisiere Lippen neu.
- `@Name` funktioniere über diesen Proxy.
- Mehr Referenzen bedeuteten mehr Konsistenz.
- O1 und 3.0 Omni reagierten auf identische Prompts gleich (3.0 Omni folgt laut Kling dem Text deutlich stärker).
- Omni-Edit ersetze maskengenaues Compositing (es ist semantisch, nicht pixelgenau steuerbar).

---

## 20. Quellen

### Primärquellen
1. Kling API: 3.0 Omni Video – https://kling.ai/document-api/api/video/3-0-omni/video-omni
2. Kling API: O1 Video – https://kling.ai/document-api/api/video/o1/video-omni
3. Kling API Legacy: Omni Video – https://kling.ai/document-api/api/video/3-0-omni/video-omni/legacy (`<<<…>>>`-Syntax, `image_list`, `element_list`, `video_list`, `refer_type`, Limits, Beispiele)
4. Kling API: Elements – https://kling.ai/document-api/api/video/3-0-omni/elements
5. Capability Map Video – https://kling.ai/document-api/guides/capability-map/video
6. Changelog – https://kling.ai/document-api/updates/api
7. KLING VIDEO O1 User Guide – https://kling.ai/quickstart/klingai-video-o1-user-guide (Prompt-Strukturen)
8. Kling VIDEO 3.0 Omni Model User Guide – https://kling.ai/quickstart/klingai-video-3-omni-model-user-guide
9. Kling Element Library User Guide – https://kling.ai/quickstart/klingai-element-library-3-user-guide

### Praxisabgleich
10. Interne Recherche `tasks/research/kling.md` und Proxy-Code (`providers/kling/models.py`, `provider.py`) für Task-Zuordnung, Nummerierung und Defaults.

### Quellenwarnung
Die App zeigt Omni mit `@`-Auswahl und eigenen Limits (z. B. Video „≤ 2K“, Bilder ≤ 10 MB). Die API-Limits unterscheiden sich teilweise (Kanten bis 4553 px, neue API Bilder bis 50 MB). Für Requests über den Proxy gelten die Legacy-Limits und `GET /v1/models`.

---

## Schlussformel

Ein guter Omni-Prompt beantwortet sechs Fragen:

1. Welche Aufgabe: neu erzeugen, editieren, anschließen oder Bewegung/Kamera übernehmen?
2. Welche Referenz spielt welche Rolle, und steht jede davon im Satz?
3. Was soll sich ändern, und was bleibt ausdrücklich gleich?
4. Wie interagieren die Subjekte miteinander und mit dem Ort?
5. Welche Kamera, welches Licht, welcher Stil, und woher kommen sie (Text oder Referenz)?
6. Gibt es Ton, und darf es ihn bei diesen Eingaben überhaupt geben?
