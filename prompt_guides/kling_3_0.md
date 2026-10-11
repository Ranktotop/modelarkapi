# Kling 3.0 Prompting Guide

**Stand: 11. Oktober 2026**  
**Fokus:** Kling 3.0 und Kling 3.0 Turbo für Text-to-Video, Image-to-Video, First/Last Frame, Multi-Shot (inkl. `shot n, m, words;` und Shot-Prompts), nativen Ton mit Dialog, Elements (`<<<element_1>>>` bzw. `@Name`) und Motion Control  
**Ziel:** aus einer Idee einen Regiezettel machen, der Kling 3.0 genau sagt, **wie viele Einstellungen** es gibt, **wer** darin vorkommt, **wer spricht** und **was am Ende jeder Einstellung sichtbar ist**

> Die wichtigste Regel: Kling 3.0 ist ein **Regie-Modell für bis zu 15 Sekunden und bis zu 6 Einstellungen, mit Ton**. Ein guter Prompt entscheidet deshalb zuerst die Struktur: *ein* durchgehender Take oder mehrere Shots, und wenn mehrere, wie viele Sekunden jeder bekommt. Danach kommen Figuren mit festen Namen, Handlung in Reihenfolge, Kamera pro Shot und Dialog, der jeder Zeile genau einen Sprecher zuordnet. Adjektive kommen zuletzt.

---

## 1. Quellenlage und Vertrauensstufen

Dieser Guide trennt durchgehend zwischen Dokumentation, offiziellen Produktguides, Community-Praxis und eigenen Empfehlungen.

### Stufe A: Primärquellen (offiziell)

1. **Kling-API-Dokumentation** (`https://kling.ai/document-api/…`, Index unter `llms.txt`): Text-to-Video und Image-to-Video für Kling 3.0 und 3.0 Turbo, Motion Control, Elements, Capability Map (Stand 2026-05-19), Changelog. Daraus stammen alle Limits und Feldnamen.
2. **Legacy-API-Seiten** (`…/legacy`, im Browser gerendert): `model_name=kling-v3`, `multi_prompt`, `negative_prompt`, `element_list`, Prompt-Referenzen `<<<element_1>>>`. **Dieser Proxy ruft Kling 3.0 über die Legacy-API auf** (siehe §8), deshalb ist diese Seite für die Syntax maßgeblich.
3. **Offizielle Kling User Guides** auf `kling.ai/quickstart/…`: „Kling VIDEO 3.0 Model User Guide“ (6. Feb. 2026), „Kling Element Library User Guide“ (5. Feb. 2026), „Motion Control“ (5. März 2026), „KLING VIDEO 2.6 User Guide“ (Dialogregeln, die 3.0 übernimmt), sowie die älteren Grundlagen-Guides „Text-to-Video“, „Image-to-Video“, „Start and End Frames“ (24. Nov. 2025).

In diesem Guide markiert als **[Doku]** bzw. **[User Guide]**.

### Stufe B: Community-Praxis

fal.ai „Kling 3.0 Prompting Guide“, Morphic „Kling 3.0 / 3.0 Turbo Guide“, VEED, Higgsfield. Diese Quellen sind Anbieter- oder Marketinginhalte. Sie werden nur zitiert, wo sie offizielle Aussagen bestätigen oder eine nachvollziehbare Praxisregel liefern. Markiert als **[Praxis]**.

### Stufe C: eigene Empfehlungen

Regeln, die aus der Modellmechanik abgeleitet, aber nicht offiziell belegt sind. Markiert als **[Empfehlung]**. Sie sind plausibel, aber nicht garantiert.

### Was nicht übernommen wurde

„Magic Keywords“, CFG-Tipps (`cfg_scale` steht nicht mehr im Schema), `camera_control`-Rezepte (seit den 1.x-Modellen nicht mehr im Schema) und Behauptungen wie „Kling 3.0 macht 30 Sekunden“ oder „Turbo hat First/Last Frame“. Beides ist durch die Doku widerlegt.

---

## 2. Was Kling 3.0 offiziell ist

Kling 3.0 ist laut User Guide der Nachfolger von Kling 2.6 auf einem „unified multimodal“ Trainingsframework: nativer Ton, Element-Konsistenz, Multi-Shot und bis zu 15 Sekunden pro Generierung. Kling 3.0 Turbo (GA seit 2026-06-17) ist die schnellere, günstigere Variante mit weniger Steuerkanälen.

### 2.1 Offiziell bestätigte Kernfähigkeiten

| Bereich | Kling 3.0 | Kling 3.0 Turbo |
|---|---|---|
| Proxy-Modell-ID | `kling-3.0` (Alias `kling-v3`) | `kling-3.0-turbo` |
| Kling-API | Legacy `/v1/videos/{text2video,image2video}` mit `model_name=kling-v3` | nur neue API `/{text,image}-to-video/kling-3.0-turbo` |
| Dauer | 3–15 s, ganzzahlig | 3–15 s, ganzzahlig |
| Auflösung | 720p, 1080p, 4K | 720p, 1080p |
| Seitenverhältnis (T2V) | 16:9, 9:16, 1:1 | 16:9, 9:16, 1:1 |
| Seitenverhältnis (I2V) | vom Startbild | vom Startbild |
| Multi-Shot | bis 6 Shots | bis 6 Shots (nur über Prompt-Syntax) |
| First Frame | ✔ | ✔ |
| First + Last Frame | ✔ | ✘ |
| Nur Last Frame | ✘ | ✘ |
| Elements | ✔ max. 3, nur zusammen mit Startbild | ✘ |
| Nativer Ton | ✔ (`generate_audio`) | laut Capability Map ✔, **im Request-Schema aber kein Audio-Feld** (§2.4) |
| Motion Control | ✔ (kein 4K) | ✘ |
| `negative_prompt`-Feld | ✔ (Legacy) | ✘ |
| Promptlänge | Legacy: 2500 Zeichen | 3072 Zeichen, empfohlen ≤ 2500 |
| Länge pro Shot-Prompt | 512 Zeichen | 512 Zeichen |
| Dialogsprachen | Chinesisch, Englisch, Japanisch, Koreanisch, Spanisch [User Guide] | nicht separat dokumentiert |

### 2.2 Was 3.0 gegenüber 2.6 offiziell neu kann [User Guide]

- **Multi-Shot** mit automatischer Shotplanung („Multi-Shot“) oder Kontrolle pro Shot („Custom Multi-Shot“).
- **Startbild + Element-Referenz**: Ein Element „lockt“ eine Figur oder ein Objekt aus dem Startbild, auch bei Zoom, Schwenk oder Neigung.
- **Mehrfiguren-Koreferenz** (3+ Figuren): Dialogzeilen werden der richtigen Figur zugeordnet.
- **Mehrsprachigkeit** (zh, en, ja, ko, es), Code-Switching innerhalb einer Szene, **Dialekte und Akzente** (z. B. Kantonesisch, Sichuanesisch; amerikanisches, britisches, indisches Englisch). Eingaben in anderen Sprachen werden laut Guide **ins Englische übersetzt**.
- **Text im Bild** („native-level text output“): Schilder, Captions und Logos aus dem Startbild bleiben lesbar, neue Schriftzüge werden sauberer gesetzt.
- **15 Sekunden** mit freier Dauer von 3 bis 15 s.

### 2.3 Turbo ist kein „3.0 light“ mit allen Kanälen

Turbo hat **keine** Elements, **kein** First+Last Frame, **kein** `negative_prompt`, **keine** Motion Control und kein 4K. Multi-Shot geht nur über die Prompt-Syntax `shot n, m, words;` (der Proxy baut sie aus `shots`, §10.3). Praxisquellen positionieren Turbo als Iterations- und Batch-Modell, 3.0 als Hero-Shot-Modell [Praxis]. Das deckt sich mit Preis und Funktionsumfang.

**[Empfehlung]** Iteriere Text-to-Video-Ideen in Turbo bei 720p und rendere das Master in Kling 3.0. Ändere beim Wechsel nichts außer dem Modell. Für Element- oder First/Last-Workflows ist Turbo keine Vorstufe, weil die Kanäle fehlen.

### 2.4 Offene Punkte

- **Ton bei Turbo:** Capability Map und Preisliste nennen „with native audio“, das Request-Schema hat aber kein `audio`-Feld, und der Proxy bietet für `kling-3.0-turbo` kein `generate_audio` an. Ob Turbo immer mit Ton rendert, ist **nicht verifiziert**. Schreibe für Turbo trotzdem eine Tonzeile, wenn Ton erwünscht ist, und rechne mit beiden Ausgängen.
- **Voice-IDs bei 3.0:** Die Legacy-Seite erlaubt `voice_list` auch für `kling-v3`, die Capability Map sagt „Voice Control: not supported“. Der Proxy bietet Voices nur für Kling 2.6 an. Eine feste Stimme bekommt eine 3.0-Figur über ein **Element mit gebundener Stimme** (§12.4).
- **Sprachliste für den Ton:** Fünf Sprachen nennt der User Guide. Die API-Doku nennt keine Sprachliste.

---

## 3. Das mentale Modell: Struktur, Besetzung, Tonvertrag

Bevor du formulierst, beantworte drei Fragen für dich, nicht für das Modell.

### 3.1 Strukturvertrag: Take oder Shots?

| Wenn … | dann … |
|---|---|
| eine Bewegung, ein Ort, eine Kamerahaltung | **Single Shot**, Multi-Shot aus (§10.1) |
| ein langer, choreografierter Take ohne Schnitt | **Single Shot**, „one continuous long take without any cuts“ ausschreiben |
| Dialog mit Schuss/Gegenschuss oder Montage | **Multi-Shot**, Shots selbst definieren (Custom) |
| grobe Idee, Schnitt darf das Modell planen | **Multi-Shot mit `shot_mode=intelligence`** |

Laut User Guide folgt das Modell im automatischen Multi-Shot „generally“ dem Prompt, **wechselt aber auf einen einzelnen Shot, wenn die Szene sich dafür eher eignet**. Wer Schnitte zwingend braucht, nimmt Custom Multi-Shot. Dort folgt das Modell laut Guide den Shots „strictly“.

### 3.2 Besetzungsvertrag: Wer ist im Bild, und unter welchem Namen?

Jede Figur bekommt **einen** Namen, der im ganzen Prompt gleich bleibt: `the courier`, nicht abwechselnd `the man`, `he`, `the guy`. Bei Elements ist der Name die Referenz (`<<<element_1>>>`), und die Figur muss im Startbild zu sehen sein (§12).

### 3.3 Tonvertrag: Wer sagt was, und was hört man sonst?

Notiere Dialog pro Sprecher, Soundeffekte, Atmo und Musik getrennt. Der offizielle 2.6-Audioguide, auf dem 3.0 aufbaut, hat dafür vier Regeln (§14.2). Ohne Tonvertrag erfindet das Modell Musik oder Gemurmel, sobald `generate_audio` an ist.

---

## 4. Die offizielle Masterformel

Kling veröffentlicht mehrere Formeln, je nach Modus. Sie sind kompatibel.

### 4.1 Text-to-Video [User Guide]

> **Prompt = Subject (Subject Description) + Subject Movement + Scene (Scene Description) + (Camera Language + Lighting + Atmosphere)**

Subjekt, Bewegung und Szene sind Pflicht, der Klammerteil ist optional. Der Guide zeigt die Steigerung an einem Beispiel:

```
A giant panda is reading a book in a café.
```
```
A giant panda wearing black-framed glasses is reading a book in a café, with the book
placed on the table. On the table, there is also a cup of coffee emitting steam, and
next to it is the café's window.
```
```
In the shot, a medium shot with a blurred background and ambient lighting captures a
scene where a giant panda, adorned with black-framed glasses, is reading a book in a
café. The book rests on the table, accompanied by a cup of coffee that's steaming
gently. Beside the cozy setting is the café's window, with a cinematic color grading
applied to enhance the visual appeal.
```

### 4.2 Image-to-Video [User Guide]

> **Prompt = Subject + Movement, Background + Movement …**

Das Bild liefert die Szene. Der Prompt beschreibt nur, **wer sich wie bewegt**. Mehrere Subjekte werden nacheinander aufgezählt.

### 4.3 Mit Ton (aus dem 2.6-Audioguide, für 3.0 gültig) [User Guide]

> **Prompt = Scene + Element (Subject Description) + Movement + Audio (Dialogue / Singing / Sound Effects / Pure Music) + Other (Style / Emotion / Camera)**

### 4.4 Arbeitsformel für Kling 3.0 [Empfehlung]

Aus den drei offiziellen Formeln und den 3.0-Beispielen ergibt sich diese Reihenfolge:

```
[Struktur: long take ODER Shot-Liste]
[Ort + Zeit + Licht in einem Satz]
[Figuren mit festen Namen und 2–3 sichtbaren Merkmalen bzw. Element-Referenz]
[Handlung in Reihenfolge, Kamera an jeder Station]
[Dialog: Sprecherlabel + Tonfall + "Zeile"]
[Ton: SFX, Atmo, Musik oder ausdrücklich keine Musik]
[Look/Stil in einem Satz]
```

Warum diese Reihenfolge: Die offiziellen 3.0-Beispiele beginnen fast immer mit Ort und Besetzung und erzählen die Handlung dann chronologisch mit Kameraangaben an jeder Station. fal.ai beschreibt dasselbe als „open with the setting and core subjects, then describe the action in order“ [Praxis].

---

## 5. Schritt 1: Genau einen Modus wählen

### 5.1 Entscheidungsbaum

1. Kein Bild? → **Text-to-Video** (`task: text_to_video`).
2. Ein bestimmtes Bild soll der erste Frame sein? → **Image-to-Video** (`image_to_video`).
3. Anfang **und** Ende stehen fest? → **First/Last Frame** (`first_last_frame`, nur Kling 3.0).
4. Mehrere Einstellungen in einem Clip? → **Multi-Shot** (`multi_shot`, `shots` oder `shot_mode=intelligence`).
5. Eine Figur aus dem Startbild muss über Kamerawechsel stabil bleiben? → zusätzlich **Elements** (nur Kling 3.0, nur mit Startbild).
6. Eine Figur soll eine vorgegebene Bewegung aus einem Video nachmachen? → **Motion Control** (`motion_control`, nur Kling 3.0).
7. Referenzbilder ohne Startbild-Rolle, Video-Edit oder Video als Stil-/Kamerareferenz? → **nicht Kling 3.0**, sondern Kling 3.0 Omni (siehe `kling_omni.md`).

### 5.2 Modusmatrix

| Modus | Proxy-Eingaben | Dauer | Ton | Wichtigste Falle |
|---|---|---|---|---|
| Text-to-Video | `prompt` | 3–15 s | 3.0: `generate_audio` | Alles, was nicht im Prompt steht, erfindet das Modell |
| Image-to-Video | `prompt` + Bild `first_frame` | 3–15 s | 3.0: ja | Prompt beschreibt Szene neu statt Bewegung |
| First/Last Frame | + Bild `last_frame` | 3–15 s | ja | Zu unterschiedliche Bilder erzeugen einen Schnitt |
| Multi-Shot (Custom) | `shots[{prompt, seconds}]` | Summe = `seconds` | 3.0: ja | Summe der Shots ≠ Gesamtdauer → 400 |
| Multi-Shot (Intelligence) | `prompt` + `shot_mode=intelligence` | 3–15 s | ja | Modell darf auf einen Shot reduzieren |
| Elements | + `element`-Referenzen (≤ 3) | wie I2V | ja | Element nicht im Startbild → Konsistenzgewinn verpufft |
| Motion Control | Bild `subject` + Video `motion` (+ Element) | folgt Video | Originalton | Ganzkörper/Halbkörper passen nicht zusammen |

### 5.3 Kombinationen

- **Multi-Shot + First/Last Frame** ist seit 2026-05-07 für `kling-v3` erlaubt [Doku, Changelog]. Das Startbild legt den ersten Shot fest, das Endbild den letzten.
- **Multi-Shot + Elements** ist erlaubt, auch beim Proxy (Task `multi_shot` mit bis zu 3 Elements). Auch hier verlangt der Proxy für `kling-3.0` ein `first_frame`, sobald Elements dabei sind.
- **Elements + Voices** schließen sich in der Legacy-API gegenseitig aus. Für 3.0 bietet der Proxy ohnehin keine Voices an.

---

## 6. Schritt 2: Parameter aus dem Prompt heraushalten

Felder werden zuverlässiger befolgt als Sätze.

### 6.1 In Feldern einstellen

| Proxy-Feld | Werte | Kling-Feld (Legacy / neu) |
|---|---|---|
| `seconds` | 3–15 | `duration` (String) / `settings.duration` (int) |
| `resolution` | `720p`, `1080p`, `4k` (nur 3.0) | `mode` std/pro/4k / `settings.resolution` |
| `quality` | `standard`, `pro` | Alias für 720p/1080p, wenn `resolution` fehlt |
| `aspect_ratio` | `16:9`, `9:16`, `1:1` (nur ohne Bild) | `aspect_ratio` / `settings.aspect_ratio` |
| `generate_audio` | bool (nur 3.0) | `sound` on/off |
| `negative_prompt` | Text (nur 3.0) | `negative_prompt` |
| `shots` | `[{prompt ≤ 512, seconds ≥ 1}]`, 1–6 | `multi_prompt` / `shot n, m, words;` |
| `shot_mode` | `customize` (Default), `intelligence` | `shot_type` |
| `references` | Rollen `first_frame`, `last_frame`, Element-Assets, `subject`, `motion` | `image`, `image_tail`, `element_list`, … |
| `watermark` | bool | `watermark_info` |

### 6.2 Im Prompt beschreiben

Struktur (Long Take oder Shotfolge, wenn nicht über `shots`), Kamera, Einstellungsgröße, Subjekt, Aktion, Ort, Licht, Farbstimmung, Material, Dialog, Sprecherzuordnung, Akzent/Sprache, SFX, Atmo, Musik, Stil.

### 6.3 Was in keinen von beiden gehört

- Dauer in Worten („a 15-second video“), wenn `seconds` gesetzt ist. Ausnahme: interne Zeitmarken wie „At the 4th second“ in einem Long Take (§11.3).
- „4K“, „8K“, „ultra HD“ als Qualitätsbeschwörung. 4K ist ein Feld.
- Seitenverhältnis als Text.

---

## 7. Promptlänge und Sprache

- **Länge:** Kling 3.0 über den Proxy (Legacy) höchstens **2500 Zeichen**, Turbo 3072 (empfohlen ≤ 2500). Pro Shot **512 Zeichen**.
- **Länger ist bei 3.0 kein Fehler.** Die offiziellen 15-Sekunden-Beispiele haben 1500 bis 2000 Zeichen. Der ältere Grundlagen-Guide rät dagegen zu „simple words and sentence structures“. Beides passt zusammen: **lange Prompts aus einfachen Sätzen**, chronologisch, ohne Verschachtelung [Empfehlung].
- **Sprache des Prompts:** Alle offiziellen Beispiele sind englisch (Dialoge teils in anderen Sprachen). **[Empfehlung]** Regie auf Englisch schreiben, nur die gesprochenen Zeilen in der Zielsprache.
- **Dialogsprache:** zh, en, ja, ko, es; andere Sprachen werden laut User Guide ins Englische übersetzt. **Deutscher Dialog ist nicht offiziell unterstützt** und landet vermutlich als englische Übersetzung im Ton.

---

## 8. Wie der Proxy Kling 3.0 aufruft (wichtig für die Syntax)

| Modell | Kling-Endpunkt im Proxy | Referenzsyntax im Prompt |
|---|---|---|
| `kling-3.0` | Legacy `/v1/videos/text2video` bzw. `image2video`, `model_name=kling-v3` | `<<<element_1>>>`, `<<<element_2>>>` … in der Reihenfolge der Element-Referenzen |
| `kling-3.0-turbo` | neue API `/text-to-video/kling-3.0-turbo` bzw. `/image-to-video/…` | keine Elements; Multi-Shot als `shot n, m, words;` |
| Motion Control (`kling-3.0`) | Legacy `/v1/videos/motion-control` | Element ohne Prompt-Referenz nötig (max. 1) |

Die offizielle neue API referenziert Elements als `@Name` (z. B. `@Zhang`), die Legacy-API als `<<<element_1>>>`. Der User Guide und die meisten Beispiele im Netz zeigen `@Name`, weil das die App-Syntax ist. **Über diesen Proxy gilt für Kling 3.0 die Legacy-Schreibweise `<<<element_n>>>`.** Der `name` einer Referenz wird für Kling 3.0 derzeit nicht in den Prompt eingesetzt.

**[Empfehlung]** Wenn du einen Prompt aus einem offiziellen Beispiel übernimmst, ersetze `@Name` durch `<<<element_n>>>` und behalte zusätzlich einen sprechenden Beschreiber: `<<<element_1>>> (the courier)`. So bleibt der Prompt lesbar, und das Modell hat beide Anker.

---

## 9. Schritt 3: Kamera

### 9.1 Kameraformel

```
[Einstellungsgröße] + [Winkel] + [eine Bewegung] + [Beziehung zum Subjekt] + [was sichtbar wird]
```

Der Grundlagen-Guide nennt als „Camera Language“: ultra-wide angle, bokeh, close-up, telephoto, low-angle, high-angle, aerial view, depth of field. Die 3.0-Beispiele verwenden zusätzlich: `camera zooms in`, `tracking horizontally`, `stabilizer moves low to the ground`, `orbits … in a smooth 360-degree pan`, `pushes in over the protagonist's shoulder`, `pulls back and freezes on the complete scene`, `cinematic handheld`, `first-person POV`, `bird's-eye view`.

### 9.2 Kamera an das Subjekt binden (offizielles Muster)

Das 3.0-Beispiel für einen langen Take beschreibt nicht nur die Bewegung, sondern die **Beziehung** zur Figur:

```
Authentic workplace texture, one continuous long take without any cuts. The camera
follows the professional woman steadily in a medium shot throughout, moving in sync
with her: the camera tracks her as she walks and freezes instantly when she pauses,
with natural and smooth movements and fluid camera work.
```

Danach folgt die Handlung als Kette von Stationen, jeweils mit „she pauses, the camera freezes in sync“ bzw. „the camera tracks her in sync“. fal.ai fasst das als „define the camera's relationship to the subject“ zusammen [Praxis].

### 9.3 Kamera pro Shot

Bei Multi-Shot bekommt **jeder** Shot seine Einstellungsgröße und Bewegung. Offizielles Beispiel (Custom Multi-Shot, 6 Shots):

```
Shot 1, Low-angle rear wide shot, tracking behind the rider as they move forward.
Shot 2, Low-angle side close-up, a detailed shot of the motorcycle wheel.
Shot 3, First-person POV from the rider, with the handlebars and instrument panel visible ahead.
Shot 4, Frontal medium shot, tracking backward in front of the motorcycle, the rider's helmet facing the camera.
Shot 5, Side-on eye-level tracking shot with slight lateral movement.
Shot 6, High-angle wide shot with a gentle downward tilt. ...
```

### 9.4 Kamerafehler

| Fehler | Wirkung | Besser |
|---|---|---|
| `cinematic` als einzige Kameraangabe | Modell wählt irgendwas | Einstellung + Bewegung benennen (Morphic: „cinematic tells the model nothing“ [Praxis]) |
| zwei Bewegungen gleichzeitig in einem Shot | Schwimmen, Wackeln | eine Bewegung pro Shot, die zweite in den nächsten Shot |
| Schnittwörter (`cut to`) im Single-Shot-Modus | ungewollte Schnitte | `one continuous long take without any cuts` |
| keine Kamera im Long Take | Modell schneidet oder springt | Kamera an das Subjekt binden (§9.2) |
| Kameraparameter aus alten Guides (`camera_control`, Master Shots) | Feld existiert nicht mehr | Bewegung im Prompt beschreiben |

---

## 10. Schritt 4: Multi-Shot

### 10.1 Zwei Wege, ein Schalter

Laut User Guide gibt es „Multi-Shot“ (Modell plant die Schnitte) und „Custom Multi-Shot“ (du definierst Shots und Dauern). In der API heißt das `shot_type: intelligence | customize`, im Proxy `shot_mode`.

| | Intelligence | Customize |
|---|---|---|
| Eingabe | ein `prompt` | `shots[{prompt, seconds}]` |
| Schnittplanung | Modell | du |
| Befolgung | „generally“, darf auf einen Shot reduzieren | „strictly“ |
| Gut für | Dialog mit natürlicher Auflösung, schnelle Skizze | Montage, Werbung, exakte Timings |

**Achtung Default:** In der **neuen** Kling-API ist `multi_shot` bei 3.0 **standardmäßig an**, in der Legacy-API aus. Der Proxy schickt Multi-Shot nur beim Task `multi_shot`. Ein normaler `text_to_video`-Aufruf an `kling-3.0` ist über den Proxy also Single Shot.

### 10.2 Harte Regeln [Doku]

- 1 bis 6 Shots.
- Jeder Shot ≥ 1 s, ganzzahlig.
- Die Summe der Shotdauern muss **exakt** der Gesamtdauer entsprechen (Proxy: fehlt `seconds`, wird es aus der Summe gesetzt; widerspricht es, gibt es 400).
- Shot-Prompt ≤ 512 Zeichen.

### 10.3 Die Syntax `shot n, m, words;`

Die offizielle Prompt-Syntax für 3.0, Turbo und 3.0 Omni in der neuen API:

```
shot 1, 3, wide low-angle shot of a cyclist cresting a hill at dawn;
shot 2, 2, close-up of the spinning front wheel throwing up dust;
shot 3, 3, the cyclist raises one fist, backlit by the rising sun;
```

- `n` = Shotnummer (1–6), `m` = Sekunden (ganzzahlig, **ohne** „s“), `words` = Shot-Prompt.
- Getrennt durch **Standard-Semikolons**.
- Mit `multi_shot=false` erzeugt die Syntax laut Doku **keinen** Multi-Shot.

**Im Proxy schreibst du diese Syntax nicht selbst.** Übergib `shots`; der Proxy übersetzt sie für Turbo in genau diese Zeile und für 3.0 in `multi_prompt`. Manche Praxisguides schreiben `shot 1, 3s, …` [Praxis]; offiziell ist die Dauer eine Zahl ohne Einheit.

```json
{
  "model": "kling-3.0",
  "task": "multi_shot",
  "seconds": 8,
  "generate_audio": true,
  "shots": [
    {"seconds": 3, "prompt": "Wide shot, a narrow ramen bar at night, steam rising. The old cook, grey crew cut, white apron, ladles broth into a bowl."},
    {"seconds": 2, "prompt": "Close-up of the bowl sliding across the wooden counter, broth trembling."},
    {"seconds": 3, "prompt": "Medium shot of the young courier in a wet yellow raincoat catching the bowl. The courier says quietly, \"Thank you.\" Rain hiss outside, no music."}
  ]
}
```

### 10.4 Jeder Shot ist eigenständig lesbar [Empfehlung]

Ein Shot-Prompt wird separat übergeben (`multi_prompt[i].prompt`). Verlasse dich nicht darauf, dass Shot 3 weiß, wer „he“ ist. Nenne in jedem Shot:

1. Einstellung + Kamera,
2. die Figur mit **demselben** Namen bzw. derselben Element-Referenz,
3. **eine** Handlung,
4. falls gesprochen wird: Sprecher + Zeile,
5. Ton nur, wenn er sich ändert.

fal.ai empfiehlt dasselbe: „define main subjects early and keep their descriptions identical across shots“ [Praxis].

### 10.5 Zeitbudget pro Shot [Empfehlung]

| Shotlänge | trägt |
|---|---|
| 1 s | Insert, Reaktion, Detail (Rad, Hand, Blick) |
| 2 s | eine kurze Handlung oder ein kurzer Satz |
| 3–4 s | eine Dialogzeile mit Reaktion, oder eine Bewegung mit Auflösung |
| 5+ s | eine kleine Szene im Shot; dann lieber Long Take |

Ein Dialogsatz von 10 bis 12 Wörtern braucht etwa 3 s. Kürzere Shots schneiden Sätze ab.

### 10.6 Shot-Labels im Fließtext (Intelligence-Modus)

Im Intelligence-Modus kannst du die Shots trotzdem im Prompt strukturieren. Die offiziellen Omni-Beispiele nutzen `Shot 1 (2s): …`. Das ist ein **Hinweis**, kein Vertrag. Wenn du die Dauern brauchst, nimm Customize.

---

## 11. Schritt 5: Subjekt und Handlung

### 11.1 Subjekte sichtbar beschreiben

Der Grundlagen-Guide empfiehlt, Aussehen „in multiple short sentences“ aufzuzählen: Haar, Kleidung, Accessoires, Gesicht, Haltung. Das 3.0-Beispiel macht es vor: „a young white woman in a blue and white striped short-sleeve shirt and khaki shorts, with a brown belt, sits barefoot“.

### 11.2 Handlung als Kette

Der 15-Sekunden-Long-Take aus dem User Guide besteht aus Stationen, getrennt durch Semikolons: aus dem Aufzug, Sonnenbrille ab, Nicken, Tasche aufhängen, Mantel aufhängen, Dokument unterschreiben, an den Tisch setzen, Tee trinken. Jede Station ist eine sichtbare Körperhandlung. **Innere Zustände** werden externalisiert („breathing rapidly yet with a firm gaze“).

### 11.3 Zeitmarken im Long Take

Das offizielle 15-Sekunden-Beispiel steuert den Ablauf mit Zeitangaben im Fließtext: „At the 4th second …“, „At the 8th second …“, „At the 12th second …“, „In the final 3 seconds …“. Ein Omni-Beispiel nutzt `[00:00 - 00:02] Medium shot: …`. Beides ist **keine dokumentierte Syntax**, sondern ein Beispielmuster. **[Empfehlung]** Nutze Zeitmarken als weiches Budget, nicht als framegenauen Schnittpunkt, und nur in Abständen von ≥ 3 s.

### 11.4 Was Kling schlecht kann [User Guide, Grundlagen-Guide]

- **Zahlen:** „Current large video models are not sensitive to numbers“ („10 puppies on the beach“ wird keine 10).
- **Komplexe Physik:** Springende Bälle und Wurfbahnen sind laut Guide schwierig.
- **Bewegung gegen das Bild:** Bei Image-to-Video kann eine Beschreibung, die stark vom Bild abweicht, „a camera cut or transition“ auslösen.

### 11.5 Ursache vor Wirkung

Der 2.6-Audioguide verlangt für Dialoge „first describe the action, then follow with the dialogue“. Das gilt auch ohne Ton [Empfehlung]: erst „the cup slips and shatters“, dann „she flinches and turns“.

---

## 12. Schritt 6: Elements (nur Kling 3.0)

### 12.1 Was ein Element ist [Doku, User Guide]

Ein Element ist ein wiederverwendbares Subjekt aus der Element Library (Figur, Tier, Requisite, Kostüm, Szene, Effekt). Zwei Typen:

| Typ | Aus | Besonderheit |
|---|---|---|
| **Video Character Element** | 3–8 s Video (1080p, 16:9 oder 9:16) einer realistischen, humanoiden Figur | Aussehen und **Stimme** werden extrahiert; Stimme austauschbar |
| **Multi-Image Element** | 1 Frontalbild + 1–3 weitere Ansichten | bei Figuren optional Stimme (5–30 s Sprachaufnahme) |

Name ≤ 20 Zeichen, Beschreibung ≤ 100 Zeichen. Im Proxy werden Elements über `/v1/assets` angelegt und als Referenz `{"type": "element", "asset_id": "asset-kling-element-<id>"}` übergeben.

### 12.2 Regeln bei Kling 3.0

- Höchstens **3 Elements**, nur zusammen mit einem **Startbild** (bzw. Start- und Endbild). Ohne Startbild lehnt der Proxy Elements für `kling-3.0` ab.
- Der User Guide empfiehlt, „elements that appear in the start frame“ zu binden; das FAQ sagt: „The elements must appear in the reference frames to enhance their specific consistency.“ Ein Element für eine Figur, die erst später ins Bild kommt, ist bei 3.0 nicht der vorgesehene Einsatz. Dafür ist Kling 3.0 Omni da.
- Referenz im Prompt über den Proxy: `<<<element_1>>>` usw., nummeriert in der Reihenfolge der Element-Referenzen.

### 12.3 Element-Prompts

```
<<<element_1>>> (the courier in the yellow raincoat) steps out of the elevator, the
camera follows in a steady medium shot. She takes off her sunglasses and nods to a
colleague passing by.
```

- Beschreibe **nicht** erneut das Aussehen, das das Element liefert. Eine minimal abweichende Beschreibung kämpft gegen die Referenz [Empfehlung].
- Wohl aber den **Zustand**: nasse Haare, Schweiß, neue Pose, Handlung.

### 12.4 Element mit Stimme

Hat ein Element eine gebundene Stimme, spricht die Figur mit dieser Stimme. Der User Guide sagt ausdrücklich: „If you choose a subject with a pre-bound voice tone, it's not recommended to set the tone again in the prompt.“ Schreibe also Emotion und Tempo (`quietly`, `hurried`), aber keine Stimmfarbe (`deep male voice`).

### 12.5 Namen von Elements [Doku]

Für die `@Name`-Syntax der neuen API gilt: Element-Namen dürfen keine Teilstrings voneinander sein (`@Zhang` und `@ZhangSan`) und sollen nicht mit sonstigem Prompttext kollidieren (`@gmail` bei einer E-Mail-Adresse im Prompt). Für `<<<element_n>>>` spielt das keine Rolle, ist aber gute Praxis für die Element-Bibliothek.

---

## 13. Schritt 7: Licht, Farbe, Stil

### 13.1 Licht [User Guide]

Der Grundlagen-Guide nennt: ambient lighting, morning light, sunset, interplay of light and shadow, Tyndall effect, artificial lighting. Die 3.0-Beispiele werden konkreter: „gilded afternoon sunlight filters through the shutters onto the perfume bottle, casting dappled light and shadow“, „cold blue night and silvery white starry sky“.

**[Empfehlung]** Lichtformel: `Quelle + Richtung + Qualität + Farbe + was es trifft`.

### 13.2 Stil

Ein Stil pro Prompt. Offizielle Formulierungen: „cinematic texture“, „poetic realism and classical epic temperament“, „American cartoon style animation“, „Cyberpunk style“. „Oriental mood“, „China“, „Asia“ erzeugen laut Grundlagen-Guide leichter chinesische Ästhetik und Figuren. Das zeigt, wie stark Kling auf Stil- und Herkunftswörter reagiert. Setze sie bewusst.

### 13.3 Text im Bild

Kling 3.0 kann Schrift laut User Guide sauber setzen und aus dem Startbild erhalten. Offizielles Beispiel: „The camera remains fixed on the word "KLING" emblazoned on the baseball bat …“. **[Empfehlung]** Exakten Text in doppelte Anführungszeichen und Großbuchstaben setzen, kurz halten (1–3 Wörter), und Preise oder Rechtstexte trotzdem im Schnitt einfügen.

---

## 14. Schritt 8: Ton und Dialog

`generate_audio: true` (Kling 3.0). Laut User Guide erzeugt 3.0 Dialog, Voice-over, Gesang, SFX, Atmo und Musik gemeinsam mit dem Bild.

### 14.1 Dialogformel [User Guide]

> **Dialogue: "Sentence" + Emotion + Speech Speed + Tone + Character Label**

Offizielle 3.0-Schreibweisen (alle funktionieren):

```
Mom (softly, in a surprised tone): Wow, I didn't expect this plot at all.
```
```
A middle-aged man ... speaks in English with an Indian accent and says: "excuse me, ..."
```
```
[Black-suited Agent, raspy, deep voice]: "Don't move."
```

### 14.2 Die vier Dialogregeln [User Guide, 2.6-Audioguide]

| Regel | Richtig | Falsch |
|---|---|---|
| **P1 Feste Namen** | `[Agent]` … `[Agent]` | `[Agent] says … Then, he says …` |
| **P2 Visuelle Verankerung** | `The agent slams his hand on the table. [Agent, angrily shouting]: "Where is the truth?"` | `[Agent]: "Where is the truth?"` ohne Handlung |
| **P3 Stimmprofil pro Figur** | `[Agent, raspy, deep voice]` / `[Assistant, clear, fearful voice]` | `[Man] says … [Woman] says …` |
| **P4 Zeitsteuerung** | `[Agent]: "Why?" Immediately, [Assistant]: "Because it's time."` | zwei Zeilen ohne Verbindungswort (Modell lässt eine Figur beides sagen) |

Optional verstärkt laut Guide der Einschub „this is when the speaker switches“ den Sprecherwechsel. Für stumme Figuren schreibt der Guide „During this, [Name] remains silent.“

### 14.3 Mehrere Figuren

3.0 ordnet laut User Guide auch bei **drei oder mehr** Figuren die Zeilen richtig zu, wenn jede Zeile ihrem Sprecher direkt zugeordnet ist. Offizielles Beispiel:

```
Home setting with a faint hum of the living room air conditioner in the background for
a realistic daily vibe. Mom (softly, in a surprised tone): Wow, I didn't expect this
plot at all. Dad (in a low voice, agreeing, in a calm tone): Yeah, it's totally
unexpected. Never thought that would happen. Boy (in an excited tone): It's the best
twist ever! Girl (nodding along, in an enthusiastic tone): I can't believe they did that!
```

### 14.4 Sprache, Akzent, Dialekt

- Sprache am Sprecher markieren: `Boy (casual tone, Korean): "…"`, `Female tourist (speaking slightly slowly, with an awkward accent, in Spanish): …`.
- Akzent am Sprecher markieren: „speaks in English with an Indian accent“, „British accent“.
- Code-Switching ist erlaubt: eine Figur Japanisch, die andere Englisch.
- Aus dem 2.6-Guide (für 3.0 nicht widerrufen): englische Wörter möglichst **kleinschreiben**, Akronyme und Eigennamen **großschreiben**, damit die Aussprache stimmt.

### 14.5 Voice-over

Offizielles Muster: `Voiceover (lazy French female voice, British accent, slow pace): Bathe in the golden hour.` Wiederholte Zeilen nur mit `Voiceover:` weiterführen.

### 14.6 SFX, Atmo, Musik [User Guide]

- **SFX:** `Sound Source (Action/Object) + State + Sound Effect`, z. B. „[Wooden door] suddenly slams + bang“.
- **Musik:** `Instrument + Genre + Emotion`, z. B. „Piano performance + jazz + melancholy“; offizielles 3.0-Beispiel: „with soft French piano BGM in the background“.
- **Atmo:** als eigener Satz an den Anfang oder ans Ende: „Background: the cheers of the crowd …“, „with a faint hum of the living room air conditioner“.
- Laut Guide helfen **Anführungszeichen**, um Toninhalt abzugrenzen.

**[Empfehlung]** Wer keine Musik will, schreibt das ausdrücklich („no background music, only rain and room tone“). Bei Werbe-, Zeitlupen- und Landschaftsmotiven legt das Modell sonst gern Musik darunter. Das ist eine Beobachtung aus vergleichbaren Modellen, für Kling nicht offiziell belegt.

### 14.7 Ton und Struktur

- Pro Shot nur so viel Dialog, wie die Shotdauer trägt (§10.5).
- Ein Satz, der über eine Shotgrenze läuft, wird oft abgeschnitten [Empfehlung].
- Singen und Dialog: Der 2.6-Guide empfiehlt dafür 10 s statt 5 s. Bei 3.0 heißt das sinngemäß: genug Sekunden einplanen.

---

## 15. Schritt 9: Negativsteuerung

- Die Legacy-API hat ein Feld `negative_prompt` (≤ 2500 Zeichen), der Proxy reicht es für `kling-3.0` durch. Turbo hat kein solches Feld.
- **Offiziell** heißt es auf der Legacy-Seite aber: „It is recommended to supplement negative prompt via negative sentences within positive prompts.“ Und in der neuen API: „The prompt can include positive and negative descriptions.“
- Praktisch heißt das: Verbote als **kurze Sätze in den Hauptprompt** („No subtitles, no on-screen text, no background music.“). `negative_prompt` nur zusätzlich als Substantivliste (`subtitles, watermark, extra fingers, blurry`).
- **[Empfehlung]** Positive Umformulierung schlägt Verbot: `one continuous long take without any cuts` statt `no cuts`; `the courier alone in the frame throughout` statt `no other people`.

---

## 16. Startbild, First/Last Frame

### 16.1 Image-to-Video

- Das Bild ist der erste Frame und legt das Seitenverhältnis fest (kein `aspect_ratio`).
- Laut 2.6-FAQ hängt die Videoqualität stark von der **Bildauflösung** ab, und Bild und Text sollen zusammenpassen („outdoor camping“ nicht mit Innenraumfoto).
- Prompt: **Subjekt + Bewegung**, Hintergrund + Bewegung. Nicht die Szene nacherzählen.
- Offizielles Beispiel: „Mona Lisa puts on sunglasses with her hand, and a ray of light appears in the background“ statt „put on sunglasses“. Ohne Subjekt und Handlung entscheidet das Modell selbst, bei Gemälden oft für einen Kameraschwenk über das Bild.
- Bewegung soll „comply with the laws of physics“ und im Bild plausibel sein.

### 16.2 First + Last Frame (nur 3.0)

- Die beiden Bilder sollen laut Guide „as similar as possible“ sein. „Significant differences may cause a lens switch.“
- Der Prompt beschreibt **den Weg** zwischen den Bildern, nicht die Bilder.
- Elements (≤ 3) sind erlaubt, wenn sie in den Frames vorkommen.

```
The camera slowly arcs from the front of the bakery counter to the side window while
the baker lifts the tray of croissants and turns toward the light. Warm morning light
from the window, flour dust in the air. Sound: soft clatter of the metal tray, quiet
street ambience. No background music.
```

---

## 17. Motion Control (nur Kling 3.0)

### 17.1 Was es tut [Doku, User Guide]

Eine Figur aus einem Bild übernimmt Bewegung und Mimik aus einem Referenzvideo. Der Prompt steuert laut Doku „elements to the screen and motion effects“, im Guide konkret Hintergrund und Zusatzelemente („A corgi runs in, circling around a girl's feet“).

### 17.2 Eingaben im Proxy

```json
{
  "model": "kling-3.0",
  "task": "motion_control",
  "resolution": "1080p",
  "prompt": "A girl wearing a white tank top and a denim skirt on a sunny rooftop. A corgi runs in, circling around her feet.",
  "references": [
    {"type": "image", "role": "subject", "url": "https://…/girl.png"},
    {"type": "video", "role": "motion", "url": "https://…/dance.mp4"},
    {"type": "element", "asset_id": "asset-kling-element-123"}
  ],
  "provider_options": {"kling": {"character_orientation": "video", "keep_original_sound": "yes"}}
}
```

- **`character_orientation`**: `image` (Orientierung aus dem Bild, Kamera per Prompt steuerbar, Video ≤ 10 s) oder `video` (Bewegung, Mimik, **Kamera** und Orientierung aus dem Video, Video ≤ 30 s). Die Kling-App nimmt standardmäßig `video`; **der Proxy setzt ohne Angabe `image`**.
- Mit Element gilt immer die Orientierung aus dem Video. Das Element liefert bei Motion Control **nur Gesichtsinformation**, keine Kleidung, Frisur oder Requisiten.
- Keine Dauer: Die Ausgabe folgt dem Referenzvideo und kann kürzer werden, wenn das Modell weniger als die volle Bewegung extrahieren kann (mindestens 3 s). Abgerechnet wird die Ausgabedauer.
- Kein 4K, kein `generate_audio`; Ton nur als Originalton des Referenzvideos (`keep_original_sound`).

### 17.3 Was das Ergebnis besser macht [User Guide]

1. Ganzkörper zu Ganzkörper, Halbkörper zu Halbkörper zwischen Bild und Video.
2. Bewegungsvideo: **ein** durchgehender Take ohne Schnitte und **ohne Kamerabewegung**, eine Person, moderates Tempo, wenig Ortswechsel.
3. Bei großen Bewegungen im Bild genug Platz um die Figur lassen.
4. Kopf und Körper im Bild unverdeckt.
5. Mehrere Personen im Video: Es wird die größte genommen.
6. Für Element-Gesichter: Frontal- plus Seitenansichten für Kopfdrehungen, neutrale plus lächelnde Frontalansicht für Mimik, für komplexe Mimik lieber ein Video-Element.

### 17.4 Prompt bei Motion Control [Empfehlung]

Beschreibe **nicht** die Bewegung, die kommt aus dem Video. Beschreibe Erscheinung (wenn kein Element), Umgebung, Zusatzobjekte und bei `character_orientation=image` die Kamera („the camera slowly zooms in“, „fixed position“; diese fünf Kameravarianten zeigt der Guide).

---

## 18. Templates

### 18.1 Text-to-Video, Single Shot

```
[Ort, Tageszeit, Licht in einem Satz]. [Figur mit festem Namen und 2–3 Merkmalen]
[Haltung]. [Kamera: Einstellung + Bewegung + Beziehung zur Figur]. [Handlung 1];
[Handlung 2]; [Handlung 3]. [Figur, Tonfall]: "[ein Satz]." Sound: [SFX], [Atmo].
[Musik oder "no background music"]. [Look in einem Satz]. One continuous take.
```

### 18.2 Long Take 10–15 s

```
This is a [N]-second cinematic long take, a single unbroken shot with no edited
transitions. [Ort, Atmosphäre]. The camera [Beziehung zur Figur] throughout.
[Station 1]; [Station 2, Kamera reagiert]; [Station 3]. At the [x]th second, [Wendepunkt].
In the final [y] seconds, [Endzustand, Kamera kommt zur Ruhe].
[Dialog nach §14]. [Ton]. [Look].
```

### 18.3 Multi-Shot (Proxy `shots`)

```
Shot k: [Einstellung + Kamera]. [Figur mit gleichem Namen / <<<element_n>>>] [eine Handlung].
        [optional: Figur, Tonfall: "Zeile"]. [optional: Tonänderung].
```

### 18.4 Image-to-Video

```
[Subjekt aus dem Bild] [Bewegung]; [zweites Subjekt] [Bewegung]; [Hintergrund] [Bewegung].
The camera [eine Bewegung]. [Ton]. No new people enter the frame.
```

### 18.5 Image-to-Video mit Element

```
<<<element_1>>> ([Kurzname]) [Bewegung im Raum des Startbilds]. The camera [Bewegung],
<<<element_1>>> stays in frame. [Dialog ohne Stimmfarbe, falls Stimme gebunden]. [Ton].
```

### 18.6 Werbung mit Produkt und Voice-over

```
[Ort + Licht]. The camera [Bewegung] from [Detail] to [Produkt mit Material und Farbe].
Voiceover ([Stimmprofil], [Tempo]): "[Claim 1]." The camera [Bewegung 2] around the
product, light playing on [Oberfläche]. Voiceover: "[Claim 2]." The camera pulls back
and holds on [Endbild]. [Musik]. Text on the bottle reads "[MARKE]".
```

---

## 19. Ausgearbeitete Beispiele

### 19.1 Dialog, zwei Figuren, Custom Multi-Shot (10 s)

```json
{
  "model": "kling-3.0",
  "task": "multi_shot",
  "seconds": 10,
  "resolution": "1080p",
  "aspect_ratio": "16:9",
  "generate_audio": true,
  "shots": [
    {"seconds": 3, "prompt": "Wide shot, an old green train carriage in afternoon light, fields passing outside. Mike, a young man in a grey knit sweater, and Cindy, a young woman with a red scarf, sit face to face by the window. Soft rattle of the train."},
    {"seconds": 3, "prompt": "Close-up of Cindy's profile, chin resting on her hand, looking out of the window. Cindy (curious, soft voice): \"Where are we going?\" During this, Mike remains silent."},
    {"seconds": 3, "prompt": "Close-up of Mike's face, he looks at Cindy and smiles. Immediately, Mike (warm, calm voice): \"Somewhere it's summer all year.\""},
    {"seconds": 1, "prompt": "Wide shot of the two smiling at each other, the train rattling on. No background music."}
  ]
}
```

Aufbau angelehnt an das offizielle Omni-Beispiel (Mike/Cindy). Jeder Shot nennt Namen, Einstellung und genau eine Handlung; der Sprecherwechsel ist mit „Immediately“ markiert.

### 19.2 Long Take, Text-to-Video (12 s)

```
This is a 12-second cinematic long take with no edited transitions. A narrow
night market alley after rain, neon signs reflecting in puddles. The camera follows
the courier, a young woman in a wet yellow raincoat with a delivery box on her back,
in a steady medium shot from behind, moving in sync with her. She weaves between
food stalls; at the 4th second she stops at a skewer stall, the camera freezes in
sync, and the old vendor hands her a paper bag. At the 8th second she turns toward
the camera, the camera slowly pushes in to a close-up, and she says, slightly out of
breath, "last delivery tonight." In the final seconds she pulls up her hood and
walks out of frame. Sound: sizzling grill, rain dripping from awnings, distant
scooter horns. No background music. Warm neon against cold blue shadows.
```

### 19.3 Image-to-Video mit Element und Startbild (8 s)

```json
{
  "model": "kling-3.0",
  "task": "image_to_video",
  "seconds": 8,
  "generate_audio": true,
  "references": [
    {"type": "image", "role": "first_frame", "url": "https://…/office_start.png"},
    {"type": "element", "asset_id": "asset-kling-element-123"}
  ],
  "prompt": "The camera gradually moves around to the front of <<<element_1>>> (the woman at the desk), who then lifts her head and smiles warmly at the camera, as if seeing an old friend after many years. Quiet office ambience, keyboard clicks in the distance. No background music."
}
```

Der Satz stammt aus dem offiziellen Element-Beispiel, nur die Referenz ist auf die Legacy-Syntax umgestellt.

### 19.4 Dreisprachige Szene (5 s)

```
On the rooftop of a high school at night, city lights glimmer, a soft wind. The girl
leans against the railing. The boy walks over with two cans of cola and hands her one.
Boy (casual tone, Korean): "숙제 다 했어?" Immediately, girl (sighing, English):
"exams are scary." Boy (gentle tone, Korean): "걱정 마." Medium two-shot, slow push-in.
```

Kürzer als das offizielle Beispiel, damit drei Zeilen in 5 s passen. **[Empfehlung]** Für drei Zeilen lieber 8 s.

### 19.5 Turbo-Skizze vor dem 3.0-Master

```json
{"model": "kling-3.0-turbo", "seconds": 6, "resolution": "720p", "aspect_ratio": "9:16",
 "prompt": "Macro close-up, slow push-in on a matte black ceramic mug on a worn oak table. Steam curls up into a beam of low morning sun from camera left; dust drifts in the light. Shallow depth of field, warm grade."}
```

Danach denselben Prompt an `kling-3.0` mit `resolution: 1080p` und `generate_audio: true` plus Tonzeile.

---

## 20. Häufige Fehler und Diagnose

| Symptom | Wahrscheinliche Ursache | Abhilfe |
|---|---|---|
| 400: Shotdauern ≠ `seconds` | Summe der `shots[].seconds` passt nicht | Summe angleichen oder `seconds` weglassen |
| Shot-Prompt abgelehnt | > 512 Zeichen | kürzen, Ort/Look nur in Shot 1 ausführlich |
| Multi-Shot liefert einen einzigen Take | Intelligence-Modus hat entschieden, dass ein Shot passt | `shot_mode=customize` mit expliziten Shots |
| Ungewollte Schnitte im Single Shot | Schnittwörter, Ortswechsel, Prompt weicht vom Startbild ab | „one continuous long take without any cuts“, Kamera an Figur binden |
| Falsche Figur spricht | Pronomen, kein Sprecherwechsel-Marker | P1–P4 (§14.2), „Immediately,“ / „this is when the speaker switches“ |
| Eine Figur sagt beide Zeilen | Zeilen ohne Verbindungswort hintereinander | Verbindungswort, stumme Figur mit „remains silent“ |
| Dialog auf Englisch statt Deutsch | Deutsch ist keine unterstützte Dialogsprache | zh/en/ja/ko/es verwenden oder Ton separat produzieren |
| Elements werden abgelehnt (Proxy) | kein `first_frame` bei `kling-3.0` | Startbild ergänzen oder Kling 3.0 Omni nehmen |
| Element-Figur driftet | Element nicht im Startbild, Aussehen im Text anders beschrieben | Element im Startbild sichtbar, Aussehen nicht nacherzählen |
| Stimme klingt anders als gewünscht | Stimmfarbe im Prompt widerspricht der gebundenen Element-Stimme | Stimmfarbe streichen, nur Emotion/Tempo |
| First/Last Frame „springt“ | Bilder zu unterschiedlich | ähnlichere Bilder, Weg im Prompt beschreiben |
| Zahl der Objekte stimmt nicht | Modell ist laut Guide „not sensitive to numbers“ | Anzahl über Startbild vorgeben |
| Turbo ignoriert Endbild/Element | Turbo hat diese Kanäle nicht | Kling 3.0 verwenden |
| Motion Control kürzer als Video | Bewegung zu schnell/komplex, nur gültige Abschnitte extrahiert | langsamere, durchgehende Bewegung ohne Schnitte |
| Motion Control übernimmt Kamera nicht | `character_orientation=image` (Proxy-Default) | `video` setzen, wenn Kamera aus dem Video kommen soll |
| Content-Filter (Kling 1301) | Inhalt/Bild verletzt Policy | Prompt/Bild ändern, nicht unverändert wiederholen |

---

## 21. Iterationsworkflow [Empfehlung]

1. **Pass 0 – Struktur:** Take oder Shots? Dauer pro Shot festlegen, Summe prüfen.
2. **Pass 1 – Minimalprompt:** Ort, Figuren, Handlung, Kamera. Kein Ton, kein Stil. In Turbo 720p (falls kein Element/Endbild nötig) oder 3.0 720p.
3. **Pass 2 – Bindung:** Startbild, Endbild, Elements. Driftet die Figur, zuerst das Bild bzw. Element verbessern, nicht den Text.
4. **Pass 3 – Ton:** Dialog nach P1–P4, SFX, Atmo, Musikentscheidung. `generate_audio: true`.
5. **Pass 4 – Look:** Licht, Farbe, Stil.
6. **Pass 5 – Master:** 1080p oder 4K, nichts anderes ändern.
7. Pro Durchgang **eine** Variable ändern. Mehrere Aufrufe desselben guten Prompts schlagen ständig neue Formulierungen.

---

## 22. Master-Checkliste

### Modell und Modus
- [ ] Turbo nur für T2V/I2V ohne Endbild, Element, Negativfeld, 4K?
- [ ] Genau ein Modus (T2V, I2V, First/Last, Multi-Shot, Motion Control)?
- [ ] Elements nur mit Startbild und nur Figuren, die im Startbild sind?

### Struktur
- [ ] Single Shot: „one continuous long take“ und Kamera an Figur gebunden?
- [ ] Multi-Shot: 1–6 Shots, jeder ≥ 1 s, Summe = `seconds`, jeder ≤ 512 Zeichen?
- [ ] Jeder Shot nennt Einstellung, Figur mit gleichem Namen, eine Handlung?

### Bild
- [ ] Figuren mit festen Namen und sichtbaren Merkmalen (oder `<<<element_n>>>`)?
- [ ] Handlung chronologisch, Ursache vor Wirkung?
- [ ] Licht mit Quelle und Richtung?
- [ ] Bei I2V: nur Bewegung, keine neue Szene?

### Ton
- [ ] `generate_audio` gesetzt (3.0)?
- [ ] Jede Dialogzeile mit Sprecherlabel, Tonfall, Anführungszeichen?
- [ ] Sprecherwechsel markiert, stumme Figuren als „remains silent“?
- [ ] Dialogsprache zh/en/ja/ko/es?
- [ ] Musik gewollt oder ausdrücklich ausgeschlossen?
- [ ] Bei Element mit Stimme: keine Stimmfarbe im Prompt?

### Parameter
- [ ] `resolution`, `aspect_ratio` (nur ohne Bild), `seconds` als Felder, nicht im Text?
- [ ] Prompt ≤ 2500 Zeichen (3.0 über Proxy) bzw. ≤ 3072 (Turbo)?
- [ ] Verbote als Sätze im Prompt, `negative_prompt` nur ergänzend?

---

## 23. Merksystem

- **15 / 6 / 512 / 3:** maximal 15 s, 6 Shots, 512 Zeichen pro Shot, 3 Elements.
- **Ein Name pro Figur.** Kein Pronomen beim Sprecherwechsel.
- **Aktion vor Dialog.** Erst die Hand auf den Tisch, dann die Zeile.
- **Startbild trägt das Element.** Bei 3.0 bindet ein Element nur, was im Startbild ist.
- **Turbo = Text + Startbild.** Alles andere braucht 3.0.
- **Customize ist Vertrag, Intelligence ist Vorschlag.**

---

## 24. Behauptungen, die nicht pauschal als gesichert gelten

- Kling 3.0 Turbo erzeuge immer Ton bzw. habe einen Audio-Schalter (nicht verifiziert, §2.4).
- Kling 3.0 unterstütze Voice-IDs (`voice_list`) wie 2.6 (Capability Map: nein; Legacy-Seite: unklar; Proxy: nicht angeboten).
- `@Name` funktioniere über diesen Proxy (der Proxy nutzt die Legacy-API mit `<<<element_n>>>`).
- Zeitmarken wie „At the 4th second“ seien framegenau.
- Deutscher Dialog werde nativ gesprochen.
- `negative_prompt` verhindere zuverlässig Untertitel, Text oder Handfehler.
- Mehr Shots bedeuteten mehr Qualität.
- Die Shotdauer werde mit „3s“ geschrieben (offiziell: Zahl ohne Einheit).
- Elements bei 3.0 funktionierten ohne Startbild (bei 3.0 nein; das ist Omni-Terrain).

---

## 25. Quellen

### Primärquellen
1. Kling API: Kling 3.0 Text to Video / Image to Video – https://kling.ai/document-api/api/video/3-0-omni/text-to-video , …/image-to-video (Prompt-Syntax, Multi-Shot, `@`-Elements, Limits)
2. Kling API: Kling 3.0 Turbo – https://kling.ai/document-api/api/video/3-0-turbo/text-to-video , …/image-to-video
3. Kling API Legacy: Image to Video – https://kling.ai/document-api/api/video/3-0-omni/image-to-video/legacy (`multi_prompt`, `negative_prompt`-Empfehlung, `<<<element_1>>>`, `<<<voice_1>>>`)
4. Kling API: Motion Control – https://kling.ai/document-api/api/video/motion-control
5. Kling API: Elements – https://kling.ai/document-api/api/video/3-0-omni/elements
6. Capability Map Video (Stand 2026-05-19) – https://kling.ai/document-api/guides/capability-map/video
7. Changelog – https://kling.ai/document-api/updates/api (Turbo GA, Multi-Shot + First/Last Frame)
8. Kling VIDEO 3.0 Model User Guide – https://kling.ai/quickstart/klingai-video-3-model-user-guide
9. Kling Element Library User Guide – https://kling.ai/quickstart/klingai-element-library-3-user-guide
10. Motion Control User Guide – https://kling.ai/quickstart/motion-control-user-guide
11. KLING VIDEO 2.6 User Guide (Dialogregeln, Audio-Formeln) – https://kling.ai/quickstart/klingai-video-26-audio-user-guide
12. Grundlagen-Guides Text-to-Video, Image-to-Video, Start and End Frames – https://kling.ai/quickstart/text-to-video-prompt-guide , …/image-to-video-guide , …/ai-video-start-end-frames

### Praxisabgleich
13. fal.ai: Kling 3.0 Prompting Guide – https://blog.fal.ai/kling-3-0-prompting-guide/
14. Morphic: Kling 3.0 Turbo Guide – https://morphic.com/resources/how-to/kling-3-0-turbo-guide
15. Interne Recherche `tasks/research/kling.md` und Proxy-Code (`providers/kling`) für Feldzuordnung und Proxy-Defaults.

### Quellenwarnung
Kling ändert Modelle und Schemas häufig (zwei API-Generationen parallel, Defaults unterscheiden sich). Die App-Oberfläche zeigt Funktionen (z. B. `@`-Auswahl, Motion Library), die nicht 1:1 API-Parameter sind. Für eine konkrete Produktion gelten die Capability-Angaben des Proxys (`GET /v1/models`) und die aktuelle Kling-Doku.

---

## Schlussformel

Ein guter Kling-3.0-Prompt beantwortet sieben Fragen ohne Widerspruch:

1. Ein Take oder wie viele Shots, und wie viele Sekunden hat jeder?
2. Wer ist im Bild, unter welchem festen Namen oder welcher Element-Referenz?
3. Was passiert, in welcher Reihenfolge, und wie reagiert die Kamera an jeder Station?
4. Wer sagt welche Zeile, in welcher Sprache und welchem Tonfall, und wann wechselt der Sprecher?
5. Was hört man außer Dialog, und ist Musik gewollt?
6. Welches Bild oder Element liefert welches Aussehen, und was beschreibt deshalb nur noch der Text?
7. Was ist am Ende jedes Shots sichtbar wahr?
