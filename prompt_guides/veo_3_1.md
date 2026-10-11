# Veo 3.1 Prompting Guide

**Stand: 4. September 2026**  
**Fokus:** Google Veo 3.1 für Text-to-Video, Image-to-Video, First/Last Frame, Referenzbilder („Ingredients to Video“), Video-Extension, Timestamp-Regie und nativen Ton  
**Ziel:** aus einer Idee eine überprüfbare Regieanweisung für **einen einzigen durchgehenden Take** machen, die Veo möglichst wenig interpretieren muss

> Die wichtigste Regel: Veo 3.1 rendert pro Aufruf **einen Take von 4, 6 oder 8 Sekunden – mit Ton**. Ein guter Veo-Prompt ist deshalb kein Drehbuch, sondern ein **Shot-Zettel**: eine Kameraeinstellung, ein Hauptereignis, ein Lichtzustand, eine Tonspur. Alles, was länger ist als ein Beat, gehört in mehrere Aufrufe, in eine Extension oder in eine Timestamp-Struktur – nicht in mehr Adjektive.

---

## 1. Quellenlage und Vertrauensstufen

Dieser Guide trennt bewusst zwischen Modellfakten, Plattformverhalten und verifizierter Praxis.

### Stufe A: Primärquellen

1. Der [offizielle Google-Cloud-Promptguide „The ultimate prompting guide for Veo 3.1“](https://cloud.google.com/blog/products/ai-machine-learning/the-ultimate-prompting-guide-for-veo-3-1) (16. Oktober 2025) – Fünfteilige Masterformel, Kameravokabular, Tonregie, Negativprompts, die drei offiziellen Advanced Workflows.
2. Die [Veo-Dokumentation der Gemini API](https://ai.google.dev/gemini-api/docs/veo) – Modell-IDs, Config-Felder, Featurematrix, Extension-Mechanik, Limits, Einschränkungen.
3. Die [Vertex-AI-Dokumentation zu Veo](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation) und die [Seite zu Referenzbildern](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/use-reference-images-to-guide-video-generation) – Enterprise-Parameter (`generateAudio`, `negativePrompt`, `referenceImages`, `personGeneration`, `storageUri`) und die Asset-/Style-Unterscheidung.

### Stufe B: verifizierte Praxis

Alles, was in diesem Guide als **„praxisverifiziert“** markiert ist, stammt aus laufendem Produktionscode gegen `veo-3.1-fast-generate-preview` über die Gemini Developer API (`:predictLongRunning`) – insbesondere die Fehlermeldungen zu Dauer, `lastFrame` und RAI-Filterung. Diese Punkte stehen teilweise **schärfer** in der Realität als in der Doku (siehe §2.3).

### Stufe C: Produktoberflächen

Google Flow, die Gemini-App und Drittanbieter-Wrapper zeigen Veo 3.1 mit **eigenen** Voreinstellungen, eigenen Längen und teilweise eigener Nachbearbeitung (Upscaling, Schnitt, Musikbett). Was dort möglich ist, ist nicht automatisch ein API-Parameter.

### Was nicht als Primärquelle behandelt wurde

Blogposts von Wrapper-Anbietern, „Veo 3.1 Prompt Guide“-SEO-Seiten und Sammlungen von „Magic Keywords“. Behauptungen wie „Veo versteht 20 Sekunden am Stück“, „`seed` macht Ergebnisse reproduzierbar“ oder „Negativlisten verhindern Text im Bild“ wurden nur übernommen, wenn eine Primärquelle sie stützt. Sie tun es meistens nicht (§28).

---

## 2. Was Veo 3.1 offiziell ist

Veo 3.1 ist Googles Videomodell mit **nativer, synchroner Tonspur** und mehreren Steuerkanälen jenseits des Texts: Startbild, Endbild, Referenzbilder und Fortsetzung eines bereits erzeugten Videos.

### 2.1 Offiziell bestätigte Kernfähigkeiten

| Bereich | Offiziell bestätigter Stand |
|---|---|
| Modell-ID (Gemini API) | `veo-3.1-generate-preview` |
| Schnelle Variante | `veo-3.1-fast-generate-preview` |
| Sparvariante | Veo 3.1 Lite (kein 4K, keine Extension) |
| Dauer | **4, 6 oder 8 Sekunden** – keine Zwischenwerte |
| Auflösung | 720p (Default), 1080p, 4K (nicht bei Lite) |
| Zwang zu 8 s | bei 1080p, 4K und bei Referenzbildern |
| Seitenverhältnis | 16:9 (Default) oder 9:16 – **kein 1:1** |
| Ton | nativ, synchron, bei 3.1 standardmäßig aktiv |
| Videos pro Request | 1 |
| Referenzbilder | bis zu **3** Asset-Bilder |
| Style-Referenz | **nicht** bei Veo 3.1 (nur `veo-2.0-generate-exp`) |
| First/Last Frame | unterstützt; `lastFrame` nur zusammen mit `image` |
| Extension | +7 s pro Schritt, bis zu 20 Schritte, max. ca. 148 s gesamt |
| Extension-Input | max. 141 s, 720p, 16:9 oder 9:16, muss von Veo stammen |
| Add/Remove Object | läuft über **Veo 2**, erzeugt **keinen Ton** |
| Wasserzeichen | SynthID in jeder Ausgabe |
| Serverseitige Aufbewahrung | 2 Tage; eine Extension setzt die Frist neu |
| Promptlänge | Texteingabe bis 1.024 Token |
| Sprache | Englisch vollständig unterstützt; andere Sprachen nicht evaluiert |
| Latenz | ca. 11 Sekunden bis 6 Minuten |

### 2.2 Modellvarianten richtig wählen

- **`veo-3.1-generate-preview`** – die Qualitätsvariante. Nimm sie für den finalen Take, für Dialogszenen und für alles, was Hautdetails, Lippensynchronität oder komplexe Materialien zeigt.
- **`veo-3.1-fast-generate-preview`** – die Iterationsvariante. Nimm sie, um Prompts, Kamerawege und Ton zu testen. Sie versteht **dieselbe** Promptsprache; wechsle erst zum Schluss, und ändere beim Wechsel **nichts** außer dem Modellnamen.
- **Veo 3.1 Lite** – kein 4K, keine Extension. Für Massenvarianten in 720p.

Das ist der wichtigste Kostenhebel: In Fast entstehen die Entscheidungen, in der Vollvariante das Master.

### 2.3 8 Sekunden sind das Nadelöhr

Die Dokumentation formuliert die Dauer stellenweise als „zwischen 4 und 8 Sekunden“. **Praxisverifiziert gilt schärfer:**

- Nur `{4, 6, 8}` werden akzeptiert. `5` oder `7` werden mit `400 INVALID_ARGUMENT` abgelehnt.
- Mit `lastFrame` ist die Dauer **exakt 8**. Andere Werte laufen in „Your use case is currently not supported“.
- 1080p, 4K und Referenzbilder erzwingen ebenfalls 8 Sekunden.

Merke: **Sobald du irgendeine der interessanten Funktionen benutzt, drehst du 8 Sekunden.** Plane den Beat gleich dafür.

### 2.4 Ton ist bei 3.1 der Normalfall, nicht das Extra

Veo 3.1 erzeugt Bild und Ton gemeinsam. Das hat zwei Konsequenzen:

1. Wenn du nichts über Ton schreibst, **erfindet** das Modell trotzdem eine Tonspur – oft mit Musik oder gemurmelter Sprache, die niemand bestellt hat.
2. Ton ist ein Regiekanal wie die Kamera. Wer ihn nicht führt, bekommt Zufall (§12).

Auf Vertex existiert `generateAudio` als Parameter; über die Gemini API ist Ton bei 3.1 der Standardzustand. Verlasse dich nie darauf, Musik über Schweigen im Prompt loszuwerden – formuliere ausdrücklich.

### 2.5 SynthID und Aufbewahrung

Jede Ausgabe trägt ein SynthID-Wasserzeichen. Erzeugte Videos liegen **zwei Tage** auf Googles Servern und werden dann gelöscht; wer sie behalten will, lädt sie herunter oder schreibt direkt in einen eigenen Storage (`storageUri` auf Vertex). Für Extension-Ketten ist das ein echter Zeitplan: Das Quellvideo muss noch existieren.

---

## 3. Plattformmatrix: Warum sich Angaben widersprechen

„Veo 3.1“ bezeichnet das Modell, aber was du einstellen kannst, hängt von der Oberfläche ab.

| Plattform | Zugriff | Besonderheit |
|---|---|---|
| Gemini Developer API | `generativelanguage.googleapis.com`, API-Key | `:predictLongRunning` + Operation-Polling; Video liegt 2 Tage bereit |
| Vertex AI | GCP-Projekt, IAM, Region | zusätzliche Parameter (`generateAudio`, `negativePrompt`, `storageUri`, `personGeneration`), Ausgabe direkt nach GCS |
| Google Flow | Produktoberfläche | Szenenverwaltung, Schnitt, Erweiterungen als UI-Funktion – nicht deckungsgleich mit API-Parametern |
| Gemini-App | Consumer | stark vereinfachte Steuerung, eigene Defaults |
| Wrapper/Drittanbieter | eigenes Schema | eigene Namen für dieselben Felder, teils eigene Limits |

### Die sichere Formulierung

- **Modellkern:** 4/6/8 s, 16:9 oder 9:16, 720p/1080p/4K, Ton nativ.
- **Vertex:** derselbe Kern plus Enterprise-Parameter und GCS-Ausgabe.
- **Flow/Gemini-App:** kann längere Ergebnisse zeigen, weil dort **mehrere Takes montiert** werden. Das ist Produktlogik, kein Modellparameter.

Schreibe deshalb niemals „20 Sekunden“, „1:1“ oder „60 fps“ in den Prompt, um einen Parameter zu erzwingen, den es nicht gibt. Länge, Format und Auflösung gehören in die Felder.

> **1:1 gibt es nicht.** Wer ein quadratisches Ergebnis braucht, rendert 9:16 und beschneidet danach mit ffmpeg. Das ist praxisverifiziert der einzige verlässliche Weg – und der Prompt muss die Komposition mittig halten, sonst schneidet der Crop den Bildinhalt an.

---

## 4. Was sich gegenüber Veo 3 geändert hat

### 4.1 Mehr Steuerkanäle als nur Text

Veo 3 war im Kern Text plus optionales Startbild. Veo 3.1 stellt vier zusätzliche Kanäle daneben:

- **Last Frame** – Ziehe den Take auf ein definiertes Endbild zu.
- **Referenzbilder** – Bis zu drei Assets (Figur, Objekt, Ort), deren Aussehen erhalten bleibt.
- **Extension** – Führe ein bereits erzeugtes Veo-Video um 7 Sekunden weiter.
- **Add/Remove Object** – Objekte in einem erzeugten Video ergänzen oder entfernen (über Veo 2, ohne Ton).

### 4.2 Ton bei den Bildmodi

Neu ist vor allem, dass **Image-to-Video, Ingredients und First/Last Frame Ton erzeugen**. In Veo 3 war Ton faktisch der Text-to-Video-Fall. Wer Bildmodi nutzt, muss den Ton also jetzt aktiv mitregieren.

### 4.3 Bessere Promptbefolgung, gleiche Grundregel

Google beschreibt 3.1 als „stärkere Prompt-Adhärenz“ und „bessere audiovisuelle Qualität“ beim Animieren von Bildern. Das verschiebt die Grenze, aber nicht die Regel: **ein Take pro Aufruf**. Wer drei Szenen in einen Prompt schreibt, bekommt eine matschige.

### 4.4 Timestamps als praktikables Werkzeug

Der offizielle Guide führt „Timestamp Prompting“ ausdrücklich als Workflow: Innerhalb eines 8-Sekunden-Takes lassen sich Abschnitte wie `[00:00-00:02]` mit eigener Kamera, eigener Aktion und eigenem SFX belegen (§14). Das ist kein framegenauer Schnitt, aber ein belastbares Zeitbudget.

---

## 5. Das mentale Modell: ein Take, ein Beat, drei Verträge

Bevor du formulierst, halte drei Dinge fest – für dich, nicht für das Modell.

### 5.1 Shot Contract: Was ist das eine Ereignis?

Ein Take hat **einen** Hauptzustandswechsel. Notiere:

- Was ist in Sekunde 0 sichtbar wahr?
- Welche eine Veränderung geschieht?
- Was ist in der letzten Sekunde sichtbar wahr?

Wenn du diese drei Sätze nicht schreiben kannst, ist die Idee noch keine Einstellung, sondern eine Szene – und braucht mehrere Aufrufe.

### 5.2 Frame Contract: Was liefert welches Bild?

Jedes übergebene Bild hat genau eine Aufgabe. Schreibe sie auf:

| Kanal | Liefert | Liefert **nicht** |
|---|---|---|
| `image` (Startbild) | Komposition, Licht, Aussehen zu Beginn | die Bewegung, den Ton, den Endzustand |
| `lastFrame` | Zielkomposition am Ende | den Weg dorthin |
| `referenceImages` (Asset) | Aussehen einer Figur/eines Objekts | Pose, Ort, Handlung, Bildausschnitt |

Der häufigste Fehler ist, ein Referenzbild wie eine Bildbeschreibung zu behandeln und dessen Hintergrund im Prompt nachzuerzählen. Dann kämpfen Bild und Text gegeneinander.

### 5.3 Sound Contract: Was hört man – und was ausdrücklich nicht?

Notiere drei Zeilen: Dialog (oder keiner), SFX, Ambience. Und eine vierte: was verboten ist (Musik, Sprache, Publikum). Der Ton ist der Kanal, der ohne Vertrag am zuverlässigsten aus dem Ruder läuft.

---

## 6. Die offizielle Masterformel

Google nennt sie fünfteilig – und die Reihenfolge ist Absicht:

> **[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]**

| Baustein | Frage | Beispiel |
|---|---|---|
| Cinematography | Wie beobachtet die Kamera? | *Medium shot, slow dolly-in, shallow depth of field* |
| Subject | Wer oder was ist im Bild? | *a tired corporate worker* |
| Action | Was geschieht körperlich? | *rubbing his temples in exhaustion* |
| Context | Wo, wann, worin? | *in front of a bulky 1980s computer in a cluttered office late at night* |
| Style & Ambiance | Look, Licht, Stimmung | *harsh fluorescent overheads and the green glow of the monitor, retro 1980s film, slightly grainy* |

Das offizielle Beispiel als ein Satz:

```
Medium shot, a tired corporate worker, rubbing his temples in exhaustion, in front of
a bulky 1980s computer in a cluttered office late at night. The scene is lit by the
harsh fluorescent overhead lights and the green glow of the monochrome monitor.
Retro aesthetic, shot as if on 1980s color film, slightly grainy.
```

Warum diese Reihenfolge funktioniert: Die Kamera legt den Bildausschnitt fest, bevor das Modell den Inhalt platziert. Wer die Kamera ans Ende schreibt, bekommt oft eine Einstellung, die zum Motiv nicht passt.

### 6.1 Minimaler Ein-Shot-Prompt

```
[Kamera + Einstellungsgröße], [Subjekt in konkreten visuellen Merkmalen],
[eine körperliche Aktion], [Ort und Tageszeit]. [Lichtquelle und Richtung],
[Farbstimmung/Look]. SFX: [ein bis zwei Geräusche]. Ambient: [Grundton].
```

Vier Zeilen reichen für einen guten Take. Mehr Text ist selten das Problem – falscher Text schon.

### 6.2 Produktionsprompt mit Referenzen

```
Using the provided reference images for [Asset A] and [Asset B]:
[Kamera + Einstellungsgröße] of [Asset A], [Aktion], [Beziehung zu Asset B],
in [Ort]. [Licht], [Farbstimmung], continuous take.
[Asset A] says, "[genau ein Satz]."
SFX: [Geräusch]. Ambient: [Grundton].
No music, no additional speakers, no on-screen text.
```

### 6.3 Struktur für die vollen 8 Sekunden

Ein 8-Sekunden-Take verträgt genau drei Phasen:

1. **0–2 s Etablieren** – Bildausschnitt, Subjekt, Licht stehen.
2. **2–6 s Ereignis** – die eine Veränderung geschieht.
3. **6–8 s Auflösen** – Kamera kommt zur Ruhe, Endzustand ist sichtbar.

Diese Dreiteilung kannst du in Prosa schreiben oder mit Timestamps hart ausbuchstabieren (§14). Was du **nicht** tun solltest: drei Ortswechsel in acht Sekunden verlangen.

---

## 7. Schritt 1: Genau einen Modus wählen

Ein Bild im Input macht den Task nicht automatisch zu Image-to-Video. Entscheidend ist, welche Rolle das Bild spielt.

### 7.1 Entscheidungsbaum

1. Habe ich **gar kein** Bild? → **Text-to-Video**.
2. Soll ein bestimmtes Bild **der erste Frame** sein? → **Image-to-Video**.
3. Kenne ich Anfang **und** Ende? → **First/Last Frame** (Dauer 8 s).
4. Muss eine Figur/ein Objekt über mehrere Shots **gleich aussehen**, ohne dass Bildausschnitt und Ort vorgegeben sind? → **Referenzbilder** (Dauer 8 s).
5. Habe ich schon ein Veo-Video und will **danach weitermachen**? → **Extension**.
6. Will ich in einem fertigen Video **ein Objekt hinzufügen/entfernen**? → **Add/Remove Object** (Veo 2, ohne Ton).

### 7.2 Modusmatrix mit Nebenbedingungen

| Modus | Eingaben | Dauer | Ton | Wichtigste Falle |
|---|---|---|---|---|
| Text-to-Video | Prompt | 4/6/8 s | ja | Nichts ist vorgegeben – Ort und Licht müssen im Prompt stehen |
| Image-to-Video | Prompt + `image` | 4/6/8 s | ja | Der Prompt darf nichts erfinden, was im Bild nicht ist |
| First/Last Frame | Prompt + `image` + `lastFrame` | **8 s** | ja | Beide Bilder müssen plausibel derselbe Raum sein |
| Ingredients | Prompt + bis zu 3 Referenzbildern | **8 s** | ja | Referenz ≠ Bildausschnitt; die Szene beschreibst du |
| Extension | Prompt + Veo-Video | +7 s | ja | Quellvideo 720p, ≤141 s, ≤2 Tage alt |
| Add/Remove Object | Video + Anweisung | – | **nein** | Läuft über Veo 2; Ton muss separat kommen |

### 7.3 Kombinierte Aufgaben aufteilen

„Mach das Produkt größer, tausch den Hintergrund und häng fünf Sekunden dran“ ist kein Prompt, sondern drei Jobs. Reihenfolge: erst den Master erzeugen, dann Objektänderungen, dann Extension. Jeder Schritt bekommt einen eigenen Aufruf und eine eigene Kontrolle.

---

## 8. Schritt 2: Parameter aus dem Prompt heraushalten

Das Modell befolgt Felder zuverlässiger als Sätze. Alles, wofür ein Feld existiert, gehört ins Feld.

### In Feldern einstellen

| Feld | Werte | Anmerkung |
|---|---|---|
| `aspectRatio` | `16:9`, `9:16` | Default 16:9; kein 1:1 |
| `resolution` | `720p`, `1080p`, `4k` | 1080p/4K erzwingen 8 s; 4K nicht bei Lite |
| `durationSeconds` | `4`, `6`, `8` | keine ungeraden Werte |
| `negativePrompt` | Substantivliste | siehe §13 |
| `personGeneration` | `dont_allow`, `allow_adult`, `allow_all` | `allow_all` nur bei Text-to-Video/Extension; Bildmodi maximal `allow_adult`; in EU/UK/CH/MENA gilt `allow_adult` als Obergrenze |
| `generateAudio` | Bool (Vertex) | bei 3.1 ist Ton der Normalfall |
| `sampleCount` / `numberOfVideos` | `1` | mehr geht bei 3.1 nicht |
| `seed` | Ganzzahl | erhöht Ähnlichkeit, garantiert **keine** Reproduzierbarkeit |
| `storageUri` | GCS-Pfad (Vertex) | sonst 2-Tage-Ablage bei Google |

### Im Prompt beschreiben

Kamerabewegung, Einstellungsgröße, Objektiv, Subjekt, Aktion, Ort, Tageszeit, Lichtquelle und -richtung, Farbstimmung, Materialien, Stil, Dialog, SFX, Ambience, Kontinuität („continuous take“).

### Was in **keinen** von beiden gehört

- Dauerangaben in Worten („a 15 second clip“) – das Feld gewinnt, der Satz stiftet nur Verwirrung.
- Auflösungswünsche („in 4K“, „8K“) als Qualitätsbeschwörung.
- Framerate.
- Seitenverhältnis als Text, wenn es dem Feld widerspricht.

---

## 9. Schritt 3: Kamera ist der stärkste Kanal

Der offizielle Guide nennt `[Cinematography]` ausdrücklich „the most powerful tool for conveying tone and emotion“. Das ist keine Floskel: Die Kamerazeile entscheidet, ob ein Take teuer oder nach Stockmaterial aussieht.

### 9.1 Kameraformel

```
[Einstellungsgröße] + [Winkel] + [eine Bewegung] + [optional Objektiv/Fokus]
```

Ein Take, **eine** Hauptbewegung. Zwei Bewegungen gleichzeitig („orbit while craning up and whip panning“) erzeugen Wackelbrei.

### 9.2 Bewegung

Verlässlich verstandene Begriffe:

- `dolly in` / `dolly out` – Kamera fährt auf das Motiv zu oder weg
- `push-in` / `pull-back` – dasselbe, weicher formuliert
- `tracking shot` – Kamera begleitet seitlich
- `crane shot` / `crane up` / `crane down` – vertikale Fahrt, oft mit Enthüllung
- `aerial view` / `drone shot` – Luftperspektive
- `slow pan left` / `slow pan right` – Schwenk
- `tilt up` / `tilt down` – Neigung
- `orbit` / `arc shot` – Umkreisen des Motivs
- `POV shot` – subjektive Kamera
- `whip pan` – schneller Schwenk, nur als Effekt
- `static shot` / `locked-off` – bewusst unbewegt

Offizielles Beispiel für eine Kranfahrt mit Enthüllung:

```
Crane shot starting low on a lone hiker and ascending high above, revealing they are
standing on the edge of a colossal, mist-filled canyon at sunrise, epic fantasy style,
awe-inspiring, soft morning light.
```

Beachte den Aufbau: **Start – Bewegung – was dadurch sichtbar wird.** Eine Kamerabewegung ohne Enthüllungsziel ist nur Zappeln.

### 9.3 Komposition

`extreme close-up`, `close-up`, `medium shot`, `medium close-up`, `two-shot`, `wide shot`, `extreme wide shot`, `establishing shot`, `low angle`, `high angle`, `eye-level`, `top-down shot`, `worm's eye view`, `over-the-shoulder`.

Für Gesichter empfiehlt die offizielle Doku ausdrücklich, das Wort `portrait` zu ergänzen – das verbessert Gesichtsdetails messbar.

### 9.4 Objektiv und Fokus

`shallow depth of field`, `deep focus`, `soft focus`, `rack focus`, `macro lens`, `wide-angle lens`, `telephoto`, `anamorphic lens flare`, `35 mm film`, `handheld`.

Offizielles Beispiel:

```
Close-up with very shallow depth of field, a young woman's face, looking out a bus
window at the passing city lights with her reflection faintly visible on the glass,
inside a bus at night during a rainstorm, melancholic mood with cool blue tones,
moody, cinematic.
```

### 9.5 Fachwort plus sichtbares Ergebnis

Fachbegriffe sind Abkürzungen, keine Garantien. Am stabilsten ist die Doppelung aus Begriff **und** beobachtbarer Wirkung:

- Schwach: `rack focus`.
- Stark: `rack focus – the foreground glass blurs as the face behind it becomes sharp`.
- Schwach: `handheld`.
- Stark: `subtle handheld drift, the frame breathing slightly, no shake`.

### 9.6 Häufige Kamerafehler

| Fehler | Wirkung | Besser |
|---|---|---|
| Zwei bis drei Bewegungen | unruhiges, ziellos schwimmendes Bild | eine Bewegung, ein Ziel |
| „cinematic camera movement“ | das Modell erfindet irgendetwas | Bewegung benennen |
| Bewegung ohne Enthüllung | Fahrt ohne Grund | „…revealing X“ ergänzen |
| Schnitt-Vokabular (`cut to`, `then we see`) | das Modell versucht Schnitte in 8 s | `continuous take` schreiben |
| Kamera zuletzt genannt | Bildausschnitt passt nicht zum Motiv | Kamera zuerst |

---

## 10. Schritt 4: Subjekt und Aktion

### 10.1 Subjekte visuell, nicht kategorial

`a person` ist keine Beschreibung, sondern eine Lücke, die das Modell mit Stockware füllt. Gib mindestens drei konkrete Merkmale: Alter/Bauart, Kleidung/Material, Farbe, Zustand.

- Schwach: `a woman with a product`.
- Stark: `a woman in her fifties with short grey hair and a paint-flecked canvas apron, holding a matte black ceramic mug`.

Bei Objekten gilt dasselbe: `a weathered brass compass with a cracked glass face`, nicht `an object`.

### 10.2 Keine realen Personen

Beschreibe den **Typ**, nicht die Identität. Namen realer Personen führen zu Ablehnungen durch den Sicherheitsfilter oder zu Ergebnissen, die weder wie die Person noch wie eine brauchbare Figur aussehen. Für wiederkehrende Figuren nimm Referenzbilder (§15) und einen wörtlich wiederholten Identitätsblock.

### 10.3 Aktionsformel

```
[Subjekt] + [sichtbare körperliche Bewegung] + [woran sie sichtbar wird] + [Ergebnis am Ende]
```

- Schwach: `she is nervous`.
- Stark: `she taps her index finger three times against the mug, then stills her hand and looks up`.

Innere Zustände müssen externalisiert werden. Das Modell kann keine Absicht rendern, nur Körper: Blickrichtung, Atem, Schulterspannung, Griffwechsel, Tempowechsel.

### 10.4 Ein Hauptereignis pro Take

Vier Sekunden tragen eine Bewegung, acht Sekunden zwei kleine oder eine große mit Auflösung. Eine Kette aus „öffnet die Tür, geht hinein, setzt sich, öffnet den Laptop“ produziert in 8 Sekunden entweder Zeitraffer oder ausgelassene Schritte.

### 10.5 Ursache vor Wirkung

Wenn ein Ereignis eine Reaktion auslöst, schreibe beides und in dieser Reihenfolge: `the cup slips from the shelf and shatters on the tiles; she flinches and turns toward the sound`. Ohne Ursache erfindet das Modell eine – meistens eine andere.

---

## 11. Schritt 5: Kontext, Licht, Farbe, Stil

### 11.1 Ort zuerst physisch definieren

Ein Ort ist Geometrie plus Material plus Tageszeit: `a narrow tiled kitchen, late afternoon, one window on the left`. Erst danach kommen Adjektive der Stimmung. Wer mit „moody atmosphere“ beginnt, bekommt Nebel und Gegenlicht auf alles.

### 11.2 Lichtformel

```
[Lichtquelle] + [Richtung] + [Härte] + [Farbe] + [was es sichtbar macht]
```

- `hard afternoon sun from camera left, cutting a sharp shadow across the desk`
- `soft overcast north light, no visible shadows, flat and even`
- `single dramatic spotlight from the front, deep falloff into black`
- `the green glow of a monochrome monitor plus harsh fluorescent overheads`

Licht ist der wirksamste Hebel für „sieht teuer aus“ – deutlich wirksamer als das Wort `cinematic`.

### 11.3 Farbe und Look

Beschreibe die Farbgebung als Grading-Entscheidung: `cool blue tones`, `warm amber grade`, `desaturated with crushed blacks`, `high-key and clean`. Wenn ein Look zum Medium gehört, benenne das Medium: `shot as if on 1980s color film, slightly grainy`.

### 11.4 Stil

Genre- und Medienbegriffe funktionieren gut, solange sie **einer** Richtung folgen: `film noir`, `documentary handheld`, `sci-fi`, `stop-motion`, `claymation`, `3D animation`, `anime`, `product commercial`. Zwei widersprechende Stile im selben Prompt („photorealistic anime“) erzeugen Mischmasch.

### 11.5 Qualitätswörter sind nachrangig

`8K`, `masterpiece`, `award-winning`, `ultra detailed` ersetzen keine Regie. Sie verbrauchen Tokens und verschieben das Bild Richtung generischem Stockmaterial. Streiche sie zugunsten von Licht, Objektiv und Material.

---

## 12. Schritt 6: Die Tonspur regieren

Veo 3.1 erzeugt „realistic, synchronized sound, from multi-person conversations to precisely timed sound effects, all guided by the prompt“. Das heißt auch: Was du nicht führst, erfindet es.

### 12.1 Die drei Tonkanäle getrennt benennen

| Kanal | Schreibweise | Beispiel |
|---|---|---|
| Dialog | in Anführungszeichen | `A woman says, "We have to leave now."` |
| Sound-Effekte | `SFX:` voranstellen | `SFX: thunder cracks in the distance.` |
| Ambience | `Ambient noise:` voranstellen | `Ambient noise: the quiet hum of a starship bridge.` |

Diese drei Präfixe sind die offiziell dokumentierte Konvention. Halte dich daran – gemischte Prosa (`you can hear some rain and someone talking`) liefert deutlich unschärfere Ergebnisse.

### 12.2 Dialogformel

```
[Sprecher, wie im Bild beschrieben] says[, in a <Tonfall> voice], "[genau ein Satz]."
```

Regeln, die sich in der Praxis auszahlen:

- **Ein Satz pro Sprecher** in 8 Sekunden. Zwei lange Sätze werden gehetzt oder abgeschnitten.
- Sprecher **eindeutig benennen**, wie sie im Bild vorkommen: `the detective`, nicht `he` – bei zwei Personen im Bild ist `he` ein Münzwurf.
- Tonfall gehört zum Sprechakt, nicht in eine eigene Zeile: `says in a weary voice`.
- Erfinde nie mehr Dialog, als der Auftrag hergibt. Wer „irgendwas Nettes“ schreibt, bekommt Werbe-Sprech.

Offizielles Beispiel aus dem Dialog-Workflow:

```
Using the provided images for the detective, the woman, and the office setting, create
a medium shot of the detective behind his desk. He looks up at the woman and says in a
weary voice, "Of all the offices in this town, you had to walk into mine."
```

### 12.3 Untertitel sind das häufigste Tonproblem

Dialog im Prompt führt regelmäßig zu **eingebrannten Untertiteln** im Bild. Gegenmittel, kombiniert einsetzen:

- im `negativePrompt`: `subtitles, captions, text overlay, watermark`
- im Prompt: `no on-screen text, no subtitles`
- Anführungszeichen sparsam: nur den tatsächlich gesprochenen Satz einfassen, keine Regieanweisungen.

### 12.4 Musik ist ein eigener Wille

Ohne Anweisung legt das Modell gern Musik unter – besonders bei Zeitlupe, Landschaften und allem, was nach Werbung aussieht. Wenn du Musik **nicht** willst, sag es ausdrücklich und benenne stattdessen den Ambient-Grundton:

```
Ambient noise: low room tone, distant traffic behind glass.
No music, no score, no soundtrack, no vocals.
```

Umgekehrt: Wenn du Musik willst, beschreibe Besetzung und Funktion (`a sparse solo piano motif, entering after the door closes`) statt „epic music“.

### 12.5 Lippensynchronität

Sie funktioniert am besten, wenn das Gesicht groß genug im Bild ist (`medium close-up` aufwärts), der Satz kurz ist und der Sprecher eindeutig benannt wurde. Bei `wide shot` mit drei Personen ist Lippensync ein Glücksfall, kein Feature.

### 12.6 Ton bei Extensions

Praxisrelevante Einschränkung aus der offiziellen Doku: **Eine Stimme lässt sich nicht wirksam fortsetzen, wenn sie in der letzten Sekunde des Quellvideos nicht vorkommt.** Wer eine Extension mit derselben Stimme plant, muss den Master so anlegen, dass am Ende gesprochen wird – oder die Extension tonlich neu aufsetzen.

---

## 13. Schritt 7: Negativsteuerung

Es gibt zwei getrennte Werkzeuge, und sie werden unterschiedlich geschrieben.

### 13.1 Das Feld `negativePrompt`: Substantive, keine Sätze

Schreibe eine kommagetrennte Liste dessen, was nicht vorkommen soll – **nie** als Verbotssatz. `no cars` im Negativfeld kann Autos genauso gut anziehen; das Feld bewertet Begriffe, nicht Verneinungen.

```
negativePrompt: cartoon, illustration, blurry, low contrast, subtitles, captions,
watermark, distorted hands, extra fingers, text overlay
```

### 13.2 Im Prompt: positiv formulieren

Der offizielle Guide ist hier eindeutig: Beschreibe den gewünschten Zustand, statt den unerwünschten zu verbieten. Statt `no man-made structures` also `a desolate landscape with no buildings or roads` – konkret, als Szenenbeschreibung, nicht als abstrakte Kategorie-Negation.

Weitere Umformulierungen, die sich bewähren:

| Statt | Besser |
|---|---|
| `no cuts` | `continuous take, one uninterrupted shot` |
| `no other people` | `the subject alone in the frame throughout` |
| `don't move the camera` | `static locked-off shot` |
| `no clutter` | `a clean, empty desk with a single mug` |

### 13.3 Was Negativsteuerung nicht leistet

Sie repariert keine fehlende Regie. Hände, Text im Bild und Identitätsdrift lassen sich mit Negativlisten dämpfen, aber nicht zuverlässig abstellen. Der wirksamere Hebel ist fast immer: Bildausschnitt ändern (Hände aus dem Bild), Referenzbild geben (Identität), Typografie im Schnitt ergänzen (Text).

---

## 14. Schritt 8: Timestamp-Prompting

Der dritte offizielle Workflow: Ein 8-Sekunden-Take wird in benannte Zeitabschnitte zerlegt, jeder mit eigener Kamera, Aktion und eigenem Ton.

### 14.1 Schreibweise

```
[00:00-00:02] [Kamera] [Subjekt] [Aktion].
[00:02-00:04] [Kamera] [Aktion]. SFX: [Geräusch].
[00:04-00:06] [Kamera] [Aktion]. Emotion: [Zustand].
[00:06-00:08] [Kamera] [Auflösung]. SFX: [Geräusch].
```

Das offizielle Beispiel:

```
[00:00-00:02] Medium shot from behind a young female explorer with a leather satchel
and messy brown hair in a ponytail, as she pushes aside a large jungle vine to reveal
a hidden path.
[00:02-00:04] Reverse shot of the explorer's freckled face, her expression filled with
awe as she gazes upon ancient, moss-covered ruins in the background. SFX: The rustle of
dense leaves, distant exotic bird calls.
[00:04-00:06] Tracking shot following the explorer as she steps into the clearing and
runs her hand over the intricate carvings on a crumbling stone wall. Emotion: Wonder
and reverence.
[00:06-00:08] Wide, high-angle crane shot, revealing the lone explorer standing small
in the center of the vast, forgotten temple complex, half-swallowed by the jungle.
SFX: A swelling, gentle orchestral score begins to play.
```

### 14.2 Regeln für Zeitbereiche

- **Nur ganze Sekunden**, lückenlos, aufsteigend, ohne Überlappung.
- Die Summe muss der eingestellten `durationSeconds` entsprechen. Timestamps bis `00:12` in einem 8-Sekunden-Job führen dazu, dass das Ende einfach fehlt.
- **Zwei Sekunden sind die sinnvolle Untergrenze** pro Abschnitt. Ein-Sekunden-Blöcke verlaufen ineinander.
- Ein Zeitbereich ist ein **Budget für ein Ereignis**, kein garantierter Schnittpunkt. Erwarte keine framegenauen Übergänge.
- Die Figurbeschreibung gehört in den **ersten** Block; danach wird sie kurz referenziert (`the explorer`), nicht wiederholt und variiert.

### 14.3 Wann Timestamps sich lohnen

- Wenn mehrere Perspektiven auf **dasselbe** Ereignis nötig sind (Blick, Gegenblick, Enthüllung).
- Wenn Ton präzise sitzen soll („SFX ab Sekunde 4“).
- Wenn eine Kamerabewegung ihre Richtung wechselt.

### 14.4 Wann sie schaden

- Bei Image-to-Video mit sanfter Bewegung – die Blockstruktur reißt den Take auseinander.
- Bei nur einem Ereignis. Dann ist ein Prosasatz stabiler.
- Bei 4 Sekunden. Zwei Blöcke lohnen den Aufwand selten.

---

## 15. Referenzbilder: „Ingredients to Video“

Bis zu **drei** Referenzbilder halten das Aussehen von Figuren, Objekten oder Orten über mehrere Shots hinweg konstant. Google nennt das „ingredients to video“; seit 3.1 erzeugt dieser Modus auch Ton.

### 15.1 Harte Regeln

- Maximal **3** Bilder, jeweils mit `referenceType: "asset"`.
- **Style-Referenzen unterstützt Veo 3.1 nicht.** Wer eine Stilreferenz als Bild braucht, muss auf `veo-2.0-generate-exp` ausweichen – oder den Stil in Worten beschreiben, was für die meisten Fälle ausreicht.
- Referenzbilder erzwingen **8 Sekunden**.
- Referenzbilder sind **kein** Startbild. Sie legen weder Bildausschnitt noch Pose noch Ort fest.

### 15.2 Was ein gutes Asset-Bild zeigt

- **Figuren:** frontal oder leicht seitlich, neutrales Licht, Gesicht unverdeckt, unauffälliger Hintergrund. Ein Porträt plus eine Ganzkörperansicht schlagen eine überfüllte Multi-View-Collage.
- **Objekte:** freigestellt oder vor ruhigem Grund, Material und Beschriftung klar erkennbar.
- **Orte:** eine charakteristische Totale, keine Detailaufnahme.

Vermeide Bilder mit eingebranntem Text, Wasserzeichen oder starkem Farbstich – all das wandert mit ins Video.

### 15.3 Wie der Prompt auf Assets verweist

Benenne die Assets im Prompt mit **stabilen, sprechenden Labels** und stelle den Verweis voran:

```
Using the provided images for the detective, the woman, and the office setting, …
```

Danach beschreibst du **Kamera, Handlung und Ton** – nicht das Aussehen. Das Aussehen kommt aus dem Bild. Wer es zusätzlich ausformuliert und dabei minimal abweicht, erzeugt genau die Identitätsdrift, die er verhindern wollte.

### 15.4 Mehrere Shots derselben Szene

Für eine Dialogszene mit zwei Einstellungen: **dieselben** Referenzbilder, **derselbe** einleitende Satz, nur Kamera, Aktion und Dialog ändern sich.

```
# Shot 1
Using the provided images for the detective, the woman, and the office setting, create
a medium shot of the detective behind his desk. He looks up at the woman and says in a
weary voice, "Of all the offices in this town, you had to walk into mine."

# Shot 2
Using the provided images for the detective, the woman, and the office setting, create
a shot focusing on the woman. A slight, mysterious smile plays on her lips as she
replies, "You were highly recommended."
```

Genau so ist der offizielle Dialog-Workflow aufgebaut: identische Zutaten, wechselnde Regie.

### 15.5 Drei Assets sind ein Limit, kein Ziel

Zwei präzise Referenzen schlagen drei mittelmäßige. Wenn ein Ort ohnehin im Prompt gut beschreibbar ist, spare den Slot für die Figur.

---

## 16. First Frame und Last Frame

Der Modus erzeugt einen Übergang zwischen zwei festen Bildern – laut Kunden „transformative“ für narrative Kontrolle.

### 16.1 Harte Regeln

- `lastFrame` funktioniert **nur zusammen mit** `image`.
- Die Dauer ist **8 Sekunden** – praxisverifiziert, andere Werte werden abgelehnt.
- Beide Bilder sollten dieselbe Auflösung und dasselbe Seitenverhältnis haben wie die Ausgabe.

### 16.2 Was in den Prompt gehört

Nicht die Bilder – die kennt das Modell. Sondern **der Weg zwischen ihnen**:

```
The camera performs a smooth 180-degree arc shot, starting with the front-facing view
of the singer and circling around her to seamlessly end on the POV shot from behind
her on stage. The singer sings "when you look me in the eyes, I can see a million stars."
```

Drei Bestandteile: **Bewegung** (arc shot), **Richtung und Ziel** (von vorn nach hinten, endet auf der POV), **Ton** (der gesungene Satz).

### 16.3 Wann der Modus scheitert

- Wenn die Bilder **nicht plausibel derselbe Raum** sind. Zwischen einem Küchentisch und einer Wüste gibt es keinen Kamerafahrt-Übergang, nur Morphing.
- Wenn Licht und Farbe stark abweichen. Das Modell interpoliert dann sichtbar durch einen Zwischenzustand.
- Wenn der Prompt eine Handlung verlangt, die im Endbild nicht bewiesen ist.

### 16.4 Die Bilder selbst erzeugen

Der offizielle Workflow ist bewusst zweistufig: Erst mit **Gemini 2.5 Flash Image (Nano Banana)** beide Frames erzeugen, dann Veo dazwischenrechnen lassen (§20). Das verlagert Komposition, Licht und Figurentreue in ein Bildmodell, das genau dafür präziser steuerbar ist.

---

## 17. Video-Extension

### 17.1 Mechanik

- Eingabe ist ein **von Veo erzeugtes** Video.
- Jede Extension hängt **7 Sekunden** an.
- Bis zu **20** Extensions, damit maximal rund **148 Sekunden** Gesamtlänge.
- Der Input darf höchstens **141 Sekunden** lang sein, muss **720p** sein und 16:9 oder 9:16 haben.
- Verfügbar bei Veo 3.1 und 3.1 Fast, **nicht** bei Lite.
- Das Quellvideo liegt nur **2 Tage** auf dem Server; jede Extension setzt die Frist neu.

### 17.2 Was der Extension-Prompt leisten muss

Er beschreibt **nur die Fortsetzung**, nicht das bereits Gesehene:

```
Continuing the shot: the camera keeps its slow push-in as she sets the mug down and
turns toward the door. The light stays the same warm afternoon side light.
SFX: ceramic on wood, a distant door latch. Ambient noise: low room tone.
No music, no on-screen text.
```

Drei Pflichtangaben an der Naht: **Kamera führt weiter wie bisher**, **Licht bleibt**, **ein neues Ereignis**.

### 17.3 Checkliste vor jeder Extension

1. Endet das Quellvideo in einer **ruhigen** Kameralage? Nahtstellen mitten in einer Whip Pan springen.
2. Ist die Person am Ende **vollständig im Bild**? Halb angeschnittene Subjekte werden neu erfunden.
3. Soll dieselbe Stimme weitersprechen? Dann muss sie in der **letzten Sekunde** hörbar sein.
4. Ist der Look beschrieben, damit das Grading nicht driftet?
5. Ist die Kette dokumentiert? Nach fünf Extensions weiß niemand mehr, welches Video die Quelle war.

### 17.4 Qualitätsverlust über die Kette

Jede Extension arbeitet auf dem Ergebnis der vorherigen. Kontrast, Schärfe und Identität driften kumulativ. Für lange Sequenzen ist es fast immer besser, **mehrere eigenständige Takes** mit denselben Referenzbildern zu erzeugen und im Schnitt zu montieren, als zwanzigmal zu verlängern.

---

## 18. Add/Remove Object

Objekte in einem erzeugten Video ergänzen oder entfernen, wobei die ursprüngliche Komposition erhalten bleibt.

**Zwei Einschränkungen, die man kennen muss:**

1. Die Funktion läuft derzeit über **Veo 2**.
2. Sie erzeugt **keinen Ton**.

Praktisch heißt das: Das ist ein Nachbearbeitungsschritt, kein Regiewerkzeug. Wer Ton braucht, muss ihn separat wieder zuführen – oder den Take mit dem gewünschten Objekt neu erzeugen. Bei Marken, Logos und Produktdetails ist Neurendern mit Referenzbild fast immer sauberer als nachträgliches Einsetzen.

---

## 19. Modus-Templates

### 19.1 Text-to-Video

```
[Einstellungsgröße + Winkel + eine Kamerabewegung], [Subjekt mit drei konkreten
visuellen Merkmalen], [eine körperliche Aktion], [Ort, Tageszeit].
[Lichtquelle + Richtung + Härte], [Farbstimmung/Look], continuous take.
SFX: [ein bis zwei Geräusche]. Ambient noise: [Grundton].
No on-screen text, no subtitles, no music.
```

Beispiel:

```
Slow dolly-in, medium close-up of a steaming ceramic mug on a worn oak café table.
Steam curls upward and catches the light; dust drifts in the beam. Low morning sun
rakes in from camera left through a rain-flecked window. Shallow depth of field, warm
cinematic grade, subtle film grain, continuous take.
SFX: soft ceramic clink against saucer, faint paper rustle off-frame.
Ambient noise: low room tone with distant traffic hum behind glass.
No on-screen text, no subtitles, no music.
```

### 19.2 Image-to-Video

Das Startbild trägt Aussehen und Komposition, der Prompt trägt **Bewegung, Lichtentwicklung und Ton**.

```
[Eine Kamerabewegung] on the scene. [Was sich im Bild bewegt], [wie das Licht sich
entwickelt]. [Farbstimmung], continuous take.
SFX: [Geräusch]. Ambient noise: [Grundton].
No new subjects enter the frame. No on-screen text, no music.
```

Eiserne Regel: **Führe nichts ein, was im Bild nicht zu sehen ist.** Kein „a bird flies into frame“, kein „she pulls out a phone“. Das Standbild ist die Grenze; alles darüber hinaus erzwingt einen sichtbaren Bruch.

### 19.3 First/Last Frame

```
The camera [Bewegung mit Richtung], starting on [Zustand aus dem ersten Bild] and
[wie es sich wandelt], seamlessly ending on [Zustand aus dem letzten Bild].
[Was währenddessen mit Licht/Bewegung passiert].
SFX: [Geräusch]. Ambient noise: [Grundton].
```

Dauer 8 s, `image` + `lastFrame`.

### 19.4 Ingredients / Referenzbilder

```
Using the provided images for [Label A], [Label B] and [Label C]:
[Einstellungsgröße + Kamerabewegung] of [Label A], [Aktion], [Beziehung zu Label B],
in [Label C]. [Licht], [Farbstimmung], continuous take.
[Label A] says, in a [Tonfall] voice, "[ein Satz]."
SFX: [Geräusch]. Ambient noise: [Grundton]. No on-screen text, no subtitles.
```

Dauer 8 s, maximal 3 Assets, keine Stilbilder.

### 19.5 Dialogszene (zwei Personen)

```
Medium two-shot, static locked-off camera. [Person A, drei Merkmale] sits across from
[Person B, drei Merkmale] at [Ort]. [Person A] leans forward slightly and says, in a
[Tonfall] voice, "[ein Satz]." [Person B] [sichtbare Reaktion] and replies, "[ein Satz]."
[Licht], [Farbstimmung], continuous take.
Ambient noise: [Grundton]. No music, no on-screen text, no subtitles.
```

Zwei kurze Sätze sind das Maximum für 8 Sekunden. Bei drei Sprechern lieber zwei Takes.

### 19.6 Produkt-/Werbeshot

```
[Macro oder close-up] + [eine langsame Bewegung: orbit / push-in] on [Produkt mit
Material, Farbe, Oberflächenzustand], on [Untergrund] against [Hintergrund].
[Lichtquelle + Richtung], [Reflexionsverhalten des Materials], [Farbstimmung].
Continuous take, the product alone in frame throughout.
SFX: [ein präzises Geräusch]. Ambient noise: [Grundton]. No on-screen text, no logos,
no music.
```

Typografie und Logo gehören in den Schnitt, nicht in den Prompt – Veo setzt Schrift unzuverlässig.

### 19.7 Extension

```
Continuing the shot: [Kamera führt bisherige Bewegung fort]. [Ein neues Ereignis].
The light stays [Lichtzustand]. [Farbstimmung unverändert].
SFX: [Geräusch]. Ambient noise: [Grundton]. No music, no on-screen text.
```

### 19.8 Timestamp-Sequenz

```
[00:00-00:02] [Kamera] [Subjekt vollständig beschrieben] [Aktion].
[00:02-00:04] [Kamera] [Aktion]. SFX: [Geräusch].
[00:04-00:06] [Kamera] [Aktion]. Emotion: [Zustand].
[00:06-00:08] [Kamera] [Auflösung/Enthüllung]. SFX: [Geräusch].
```

---

## 20. Fortgeschrittene Workflows mit Gemini 2.5 Flash Image

Der offizielle Guide kombiniert Veo ausdrücklich mit **Gemini 2.5 Flash Image (Nano Banana)**. Der Gedanke dahinter: Komposition, Figurentreue und Licht sind in einem Bildmodell billiger und präziser zu iterieren als in einem Videomodell.

### 20.1 Workflow „Dynamischer Übergang“

1. **Startbild erzeugen.**
   ```
   Medium shot of a female pop star singing passionately into a vintage microphone.
   She is on a dark stage, lit by a single, dramatic spotlight from the front. She has
   her eyes closed, capturing an emotional moment. Photorealistic, cinematic.
   ```
2. **Endbild erzeugen** – dieselbe Szene, andere Perspektive.
   ```
   POV shot from behind the singer on stage, looking out at a large, cheering crowd.
   The stage lights are bright, creating lens flare. You can see the back of the
   singer's head and shoulders in the foreground. The audience is a sea of lights and
   silhouettes. Energetic atmosphere.
   ```
3. **Mit Veo verbinden** – beide Bilder als `image` und `lastFrame`, der Prompt beschreibt nur den Weg und den Ton (§16.2).

Der Gewinn: Der Kameraweg wird planbar, weil Anfang und Ende feststehen. Iteriere die Bilder, nicht das Video.

### 20.2 Workflow „Dialogszene aus Zutaten“

1. Mit Nano Banana **Referenzbilder** erzeugen: je ein Bild pro Figur, eines für den Ort.
2. Mit Veo und denselben drei Assets **mehrere Shots** derselben Szene rendern – Shot/Gegenshot, Dialog verteilt (§15.4).
3. Im Schnitt montieren.

Das ist der praktikabelste Weg zu einer Szene, die länger ist als acht Sekunden und trotzdem konsistent aussieht.

### 20.3 Workflow „Timestamp-Sequenz“

Eine komplette Mini-Sequenz in **einem** Aufruf, über Zeitblöcke gesteuert (§14). Vorteil: Alles stammt aus einer Generierung, also ist die visuelle Konsistenz garantiert. Nachteil: Man kann einzelne Abschnitte nicht nachbessern, ohne den ganzen Take neu zu würfeln.

### 20.4 Prompt-Anreicherung mit Gemini

Der offizielle Guide empfiehlt, einen knappen Prompt von Gemini in beschreibende, filmische Sprache erweitern zu lassen. Das funktioniert – mit einer Auflage: **Der Story Contract muss überleben.** Lass dir das Ergebnis ausgeben und prüfe, ob Subjektanzahl, Handlung, Ort und Dialog unverändert sind. Optimierer erfinden gern eine „bessere“ Szene.

---

## 21. Mehrere Shots, ein Film

Acht Sekunden sind kein Film. Für längere Stücke gibt es drei Wege, in dieser Reihenfolge der Zuverlässigkeit:

1. **Mehrere Takes mit identischen Referenzbildern**, im Schnitt montiert. Beste Kontrolle, beste Qualität, benötigt einen Schnittplatz.
2. **Timestamp-Sequenz** innerhalb von 8 Sekunden. Perfekte Konsistenz, aber alles oder nichts.
3. **Extension-Kette.** Längste Laufzeit, aber kumulative Drift und 720p-Zwang.

### 21.1 Konsistenzblock

Wenn du über mehrere Aufrufe hinweg dieselbe Welt brauchst, halte einen Textblock wörtlich identisch und kopiere ihn in jeden Prompt:

```
Look: 35 mm, shallow depth of field, warm amber grade, soft film grain.
Location: a narrow tiled kitchen, late afternoon, one window camera left.
Character: a woman in her fifties, short grey hair, paint-flecked canvas apron.
```

Kopieren, nicht umformulieren. Jede Variation ist eine Einladung zur Drift.

### 21.2 Anschluss planen

Plane Schnitte an **Bewegungsruhe**, nicht mitten in einer Fahrt. Wenn Shot 1 mit einer Push-in endet, beginnt Shot 2 idealerweise statisch – sonst wirkt der Schnitt wie ein Fehler.

---

## 22. API-Bedienung: Gemini Developer API

Der folgende Ablauf ist **praxisverifiziert** gegen `veo-3.1-fast-generate-preview`.

### 22.1 Job starten

`POST https://generativelanguage.googleapis.com/v1beta/models/veo-3.1-fast-generate-preview:predictLongRunning?key=API_KEY`

```json
{
  "instances": [
    {
      "prompt": "Slow dolly-in on the steaming coffee cup, shallow depth of field. …",
      "image": { "bytesBase64Encoded": "<base64>", "mimeType": "image/png" },
      "lastFrame": { "bytesBase64Encoded": "<base64>", "mimeType": "image/png" }
    }
  ],
  "parameters": {
    "aspectRatio": "9:16",
    "durationSeconds": 8,
    "sampleCount": 1
  }
}
```

- `image` weglassen → Text-to-Video.
- `lastFrame` ist nur zusammen mit `image` gültig und verlangt `durationSeconds: 8`.
- Antwort ist eine Operation mit `name`.

### 22.2 Pollen

`GET https://generativelanguage.googleapis.com/v1beta/{operation.name}?key=API_KEY`

- Sinnvolles Intervall: **10 Sekunden**.
- Sinnvolles Budget: **20 Minuten**. Die dokumentierte Latenz reicht von 11 Sekunden bis 6 Minuten; unter Last mehr.
- `metadata.state` und `metadata.progressPercent` taugen als Fortschrittsanzeige, sind aber nicht immer gesetzt.
- Fertig ist der Job bei `done: true`.

### 22.3 Ergebnis lesen

Das Video steckt unter `response.generateVideoResponse.generatedSamples[0]` – entweder als `video.bytesBase64Encoded` oder als `video.uri`. Bei der URI-Variante muss der Download den API-Key als Header `x-goog-api-key` mitschicken.

### 22.4 Der Sonderfall, den jeder übersieht: RAI-Filterung

Ein Job kann mit `done: true` enden, **ohne Video**. Dann steht im selben Objekt:

```json
{
  "raiMediaFilteredCount": 1,
  "raiMediaFilteredReasons": ["…"]
}
```

Das ist **kein** vorübergehender Fehler und darf nicht wiederholt werden – ein Retry kostet nur Geld und liefert dasselbe Ergebnis. Prompt, Startbild oder Seitenverhältnis müssen sich ändern. Laut offizieller Doku wird ein so blockierter Job nicht berechnet.

Wer eine Retry-Logik baut, braucht deshalb zwingend die Unterscheidung: **Netzwerkfehler/Timeout → wiederholbar. Ungültige Dauer, `lastFrame` ohne 8 s, RAI-Filter → nicht wiederholbar.**

### 22.5 Python-SDK

```python
import time
from google import genai
from google.genai import types

client = genai.Client()
operation = client.models.generate_videos(
    model="veo-3.1-generate-preview",
    prompt="Medium shot, slow dolly-in …",
    config=types.GenerateVideosConfig(
        aspect_ratio="16:9",
        resolution="1080p",
        duration_seconds=8,
        negative_prompt="cartoon, blurry, subtitles, watermark",
        person_generation="allow_adult",
    ),
)
while not operation.done:
    time.sleep(10)
    operation = client.operations.get(operation)

video = operation.response.generated_videos[0].video
client.files.download(file=video)
video.save("out.mp4")
```

Die Feldnamen der SDK folgen dem `snake_case`-Pendant der REST-Felder; prüfe sie gegen die installierte Version, da Veo 3.1 als Preview geführt wird.

---

## 23. API-Bedienung: Vertex AI

Auf Vertex ist der Ablauf derselbe (Long-Running Operation + Polling), aber es gibt zusätzliche Felder:

| Feld | Nutzen |
|---|---|
| `negativePrompt` | Substantivliste dessen, was nicht vorkommen soll (§13.1) |
| `generateAudio` | Ton explizit an-/abschalten |
| `personGeneration` | `dont_allow`, `allow_adult`, `allow_all` – regional eingeschränkt |
| `referenceImages[].referenceType` | `asset` (bis 3). `style` **nicht** bei 3.1 – dafür `veo-2.0-generate-exp` |
| `storageUri` | Ausgabe direkt in einen eigenen GCS-Bucket, statt 2-Tage-Ablage |
| `seed` | Ganzzahl; erhöht Ähnlichkeit, garantiert keine Reproduzierbarkeit |

Praktische Folge: Wenn du `negativePrompt` und Style-Referenzen brauchst, ist Vertex die richtige Oberfläche. Wenn du nur schnell Videos willst, ist die Gemini API die kürzere Strecke.

---

## 24. Ein professioneller Iterationsworkflow

Iteriere in **Fast**, finalisiere in der Vollvariante. Ändere pro Durchgang genau **eine** Variable.

### Pass 0: Shot Contract

Schreibe drei Sätze auf: Anfangszustand, das eine Ereignis, Endzustand. Lege Modus, Dauer, Seitenverhältnis und Auflösung fest. Prüfe die Zwangsbedingungen (8 s bei `lastFrame`, Referenzbildern, 1080p, 4K).

### Pass 1: Minimalprompt

Nur Kamera, Subjekt, Aktion, Ort. Kein Licht, kein Stil, kein Ton. Ziel: Stimmt die Einstellung? Passiert das richtige Ereignis?

### Pass 2: Bildbindung

Startbild, Endbild oder Referenzbilder ergänzen. Ziel: Sitzt die Identität? Wenn nein, ist das ein Bildproblem, kein Textproblem – tausche das Referenzbild, bevor du am Prompt schraubst.

### Pass 3: Kamera schärfen

Bewegung präzisieren, Enthüllungsziel ergänzen, Objektiv benennen. Ziel: Sieht die Bewegung motiviert aus?

### Pass 4: Licht, Farbe, Material

Lichtquelle, Richtung, Härte, Grade, Oberflächen. Das ist der Pass, der am meisten Wirkung pro Wort bringt.

### Pass 5: Ton

Dialog (höchstens ein Satz pro Sprecher), SFX, Ambience, plus Verbote für Musik und Untertitel.

### Pass 6: Gezielte Constraints

`negativePrompt` füllen, Positivformulierungen für Schnitte und Statisten ergänzen. Erst jetzt – nicht vorher.

### Pass 7: Best-of-N statt Seed-Jagd

`sampleCount` ist 1, also sind Varianten separate Aufrufe. Drei Aufrufe desselben guten Prompts schlagen zehn Aufrufe mit jeweils neuen Formulierungen. Ein `seed` erhöht die Ähnlichkeit, aber ist keine Garantie – behandle ihn als Werkzeug für Variantennähe, nicht für Reproduzierbarkeit.

---

## 25. Fehlerdiagnose

### 25.1 `400 INVALID_ARGUMENT` bei der Dauer

Ursache: 5 oder 7 Sekunden angefordert. Nur `{4, 6, 8}` sind gültig. Runde immer **auf**.

### 25.2 „Your use case is currently not supported“

Fast immer: `lastFrame` mit einer anderen Dauer als 8 Sekunden. Auch möglich: 1080p/4K oder Referenzbilder mit weniger als 8 Sekunden.

### 25.3 Job fertig, aber kein Video

`raiMediaFilteredCount` prüfen (§22.4). Sicherheitsfilter. Nicht wiederholen – Prompt oder Startbild ändern. Häufige Auslöser: reale Personen, Kinder, Marken/Logos, Gewaltandeutungen, medizinische Motive.

### 25.4 Identitätsdrift über mehrere Shots

- Referenzbilder benutzen (§15), nicht nur Text.
- Identitätsblock **wörtlich identisch** kopieren.
- Aussehen nicht doppelt beschreiben, wenn ein Referenzbild es liefert.

### 25.5 Untertitel im Bild

Dialog im Prompt ist die Ursache. `subtitles, captions, text overlay` ins `negativePrompt`, `no on-screen text, no subtitles` in den Prompt, Anführungszeichen nur um den gesprochenen Satz.

### 25.6 Ungewollte Musik

Ambience ausdrücklich benennen und Musik ausdrücklich ausschließen (§12.4). „Ambient“ allein reicht nicht – das Modell liest es gern als Ambient-Musik.

### 25.7 Sprache, obwohl niemand sprechen soll

`No dialogue, no speech, no voice-over, no vocals` an den Prompt anhängen und keine Person in Sprechhaltung beschreiben (frontal, Mund geöffnet, Mikrofon im Bild).

### 25.8 Kamera wird chaotisch

Zu viele Bewegungen. Auf **eine** reduzieren, Enthüllungsziel ergänzen, `continuous take` schreiben.

### 25.9 Das Modell schneidet mitten im Take

Schnitt-Vokabular im Prompt (`then`, `cut to`, `next we see`) oder eine Handlung, die räumlich nicht in einen Take passt. Umschreiben oder in zwei Aufrufe teilen.

### 25.10 Aktionen werden ausgelassen

Zu viele Ereignisse für die Dauer. Ein Hauptereignis pro Take; den Rest in Shot 2.

### 25.11 Image-to-Video bricht sichtbar

Der Prompt führt etwas ein, was im Startbild nicht existiert. Streiche jede Erwähnung neuer Subjekte, Requisiten oder Räume.

### 25.12 First/Last Frame morpht

Die beiden Bilder sind nicht plausibel derselbe Raum oder haben zu unterschiedliches Licht. Endbild neu erzeugen, näher am Startbild.

### 25.13 Extension springt an der Naht

Quellvideo endet in einer Bewegung, oder Kamera/Licht sind im Extension-Prompt nicht fortgeschrieben. Beides beheben; notfalls den Master so kürzen, dass er ruhig endet.

### 25.14 Extension verliert die Stimme

Die Stimme kommt in der letzten Sekunde des Quellvideos nicht vor. Master anpassen oder Ton neu aufsetzen.

### 25.15 Text im Bild ist falsch geschrieben

Erwartbar. Veo rendert Typografie unzuverlässig. Schrift, Logos und Preise gehören in den Schnitt.

### 25.16 Gesicht bleibt matschig

`portrait` ergänzen, engere Einstellungsgröße wählen, Lichtquelle benennen, in der Vollvariante statt Fast rendern.

### 25.17 Ergebnis wirkt wie Stockmaterial

Zu viele Qualitätswörter, zu wenig Licht und Material. Streiche `cinematic, 8K, masterpiece` und ersetze sie durch Lichtquelle, Richtung, Objektiv und eine Oberflächenbeschreibung.

---

## 26. Master-Checkliste vor dem Absenden

### Modus und Parameter
- [ ] Genau ein Modus gewählt (T2V, I2V, First/Last, Ingredients, Extension)?
- [ ] Dauer ist 4, 6 oder 8 – und **8**, falls `lastFrame`, Referenzbilder, 1080p oder 4K im Spiel sind?
- [ ] Seitenverhältnis 16:9 oder 9:16 gesetzt (kein 1:1 erwartet)?
- [ ] Auflösung bewusst gewählt, nicht im Prompt beschworen?
- [ ] `personGeneration` passend zum Modus und zur Region?

### Bild
- [ ] Genau **eine** Kamerabewegung mit Ziel?
- [ ] Einstellungsgröße genannt?
- [ ] Subjekt mit mindestens drei konkreten Merkmalen beschrieben?
- [ ] Genau ein Hauptereignis?
- [ ] Ort, Tageszeit, Lichtquelle und -richtung benannt?
- [ ] Farbstimmung/Look genannt, ohne Qualitätsfloskeln?
- [ ] `continuous take` gesetzt, falls Schnittgefahr besteht?

### Referenzen
- [ ] Höchstens 3 Asset-Bilder, keine Style-Bilder?
- [ ] Aussehen **nicht** doppelt in Text und Bild beschrieben?
- [ ] Labels stabil und im Prompt vorangestellt?

### Ton
- [ ] Dialog: höchstens ein Satz pro Sprecher, Sprecher eindeutig benannt?
- [ ] `SFX:` und `Ambient noise:` getrennt geschrieben?
- [ ] Musik ausdrücklich gewollt oder ausdrücklich ausgeschlossen?
- [ ] Untertitel ausgeschlossen, falls Dialog vorkommt?

### Negativ
- [ ] `negativePrompt` als Substantivliste, keine „no X“-Sätze?
- [ ] Verbote im Prompt positiv umformuliert?

### Extension
- [ ] Quellvideo von Veo, 720p, ≤141 s, ≤2 Tage alt?
- [ ] Endet es ruhig und mit vollständig sichtbarem Subjekt?
- [ ] Kamera und Licht im Prompt fortgeschrieben?
- [ ] Stimme in der letzten Sekunde vorhanden, falls sie weiterlaufen soll?

---

## 27. Merksystem zum Auswendiglernen

### Die fünf Bausteine: C-S-A-C-S

**C**inematography → **S**ubject → **A**ction → **C**ontext → **S**tyle & Ambiance.

### Die drei Verträge

1. **Shot Contract** – Anfangszustand, ein Ereignis, Endzustand.
2. **Frame Contract** – jedes Bild hat genau eine Aufgabe.
3. **Sound Contract** – Dialog, SFX, Ambience, Verbote.

### Die vier Zahlen

- **4/6/8** – die einzigen Dauern.
- **8** – sobald `lastFrame`, Referenzbilder, 1080p oder 4K im Spiel sind.
- **3** – maximale Referenzbilder.
- **7 × 20 ≈ 148** – Extension-Schritt, Anzahl, Gesamtlänge.

### Die Kameraformel

```
Einstellungsgröße + Winkel + eine Bewegung + Enthüllungsziel + optional Objektiv
```

### Die Lichtformel

```
Quelle + Richtung + Härte + Farbe + was sie sichtbar macht
```

### Die Tonformel

```
"Dialog in Anführungszeichen"  +  SFX: …  +  Ambient noise: …  +  ausdrückliche Verbote
```

### Die drei Fragen für jeden Take

1. Was ist am Anfang sichtbar wahr?
2. Welche eine Veränderung geschieht – und wodurch?
3. Was ist am Ende sichtbar wahr, im Bild **und** im Ton?

---

## 28. Behauptungen, die nicht pauschal als gesichert gelten

- Veo 3.1 erzeuge in einem Aufruf Videos von 15, 20 oder 60 Sekunden.
- 1:1 sei ein unterstütztes Seitenverhältnis.
- Jede Auflösung sei mit jeder Dauer kombinierbar.
- `seed` mache Ergebnisse reproduzierbar.
- Negativlisten verhinderten zuverlässig Text im Bild, Hände-Fehler oder Identitätsdrift.
- Style-Referenzbilder funktionierten mit Veo 3.1.
- Mehr Referenzbilder bedeuteten mehr Konsistenz.
- Timestamps seien framegenaue Schnittpunkte.
- Add/Remove Object erzeuge Ton.
- Eine Extension erhalte Qualität und Identität verlustfrei.
- Deutsche Prompts seien gleichwertig evaluiert – offiziell ist nur Englisch vollständig unterstützt.
- `cinematic`, `8K` oder `masterpiece` ersetzten Licht- und Kameraregie.
- Was Flow oder die Gemini-App zeigen, sei automatisch über die API verfügbar.

---

## 29. Quellen

### Primärquellen

1. [Google Cloud Blog: The ultimate prompting guide for Veo 3.1](https://cloud.google.com/blog/products/ai-machine-learning/the-ultimate-prompting-guide-for-veo-3-1) (16. Oktober 2025) – Fünfteilige Formel, Kameravokabular, Tonregie, Negativprompts, die drei Advanced Workflows, Add/Remove-Object-Hinweis.
2. [Gemini API: Veo](https://ai.google.dev/gemini-api/docs/veo) – Modell-IDs, Config-Felder, Dauer-/Auflösungsmatrix, Referenzbilder, Extension-Mechanik, Retention, SynthID, Einschränkungen.
3. [Vertex AI: Veo Video Generation API](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation) – Enterprise-Parameter.
4. [Vertex AI: Guide video generation using asset and style images](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/use-reference-images-to-guide-video-generation) – Asset- vs. Style-Referenzen, Modellzuordnung.

### Praxisabgleich

5. Laufender Produktionscode gegen `veo-3.1-fast-generate-preview` über `:predictLongRunning` – Dauer `{4,6,8}`, `lastFrame`-Zwang auf 8 Sekunden, RAI-Filterverhalten bei `done: true`, Download über `bytesBase64Encoded` oder `uri`, 1:1 nur per Crop aus 9:16.

### Quellenwarnung

Veo 3.1 wird in Teilen als Preview geführt. Modellnamen, Auflösungsoptionen und Parameterverfügbarkeit können sich ändern, und Gemini API, Vertex AI und Flow zeigen nicht denselben Funktionsumfang. Für eine konkrete Produktion gilt zuletzt das aktuelle Schema der genutzten Oberfläche.

---

## Schlussformel

Ein meisterhafter Veo-3.1-Prompt beantwortet acht Fragen ohne Widerspruch:

1. Welcher Modus wird ausgeführt – und welche Dauer erzwingt er?
2. Wie beobachtet die Kamera, und was macht ihre Bewegung sichtbar?
3. Wer oder was ist im Bild, in drei konkreten Merkmalen?
4. Welche eine körperliche Veränderung geschieht, und wodurch wird sie ausgelöst?
5. Wo, wann, in welchem Licht – aus welcher Richtung, wie hart, in welcher Farbe?
6. Welches Bild liefert welchen Teil der Wahrheit, und was liefert es ausdrücklich nicht?
7. Was hört man – Dialog, SFX, Ambience – und was ist ausdrücklich verboten?
8. Was ist in der letzten Sekunde sichtbar und hörbar wahr?
