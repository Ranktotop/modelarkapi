# Seedance 2.0 Fast Prompting Guide

**Stand: 21. August 2026**  
**Fokus:** Doubao/ByteDance Seedance 2.0 Fast, Text-to-Video, Image-to-Video, First/Last Frame, multimodale Referenzen, Video-Editing und Video-Extension  
**Ziel:** reproduzierbar bessere Videos durch klare Regieanweisungen statt bloßer Stil-Adjektive

> Kurzfassung: Seedance 2.0 Fast wird am zuverlässigsten wie ein Regisseur bedient. Definiere zuerst eindeutig, **wer oder was** wichtig ist und **was sichtbar geschieht**. Lege danach Szene, Licht, Kamera, Stil, Ton und Grenzen fest. Bei komplexeren Clips schreibst du keine Prosageschichte, sondern eine geordnete Shot-Liste. Referenzmaterial bekommt eine eindeutige Aufgabe. Pro Shot gibt es möglichst nur eine Hauptaktion und eine Kamerabewegung.

---

## 1. Was offiziell gesichert ist

### 1.1 Fast verwendet dieselbe Promptlogik wie die Seedance-2.0-Serie

ByteDance/Volcengine veröffentlicht keinen separaten Promptaufbau nur für Fast. Der offizielle **„Doubao Seedance 2.0 Series Prompt Guide“** gilt für die gesamte 2.0-Serie. Seedance 2.0 Fast ist die beschleunigte Variante für niedrigere Latenz. Es gibt keine belastbare offizielle Aussage, dass Fast eine andere Wortreihenfolge, besondere Keywords, Prompt-Gewichte oder eine eigene Negative-Prompt-Syntax benötigt.

Quellen: [Offizieller Seedance-2.0-Serien-Promptguide](https://www.volcengine.com/docs/82379/2222480), [ByteDance Seed Technical Report](https://arxiv.org/abs/2604.14148), [ByteDance Seed Launch](https://seed.bytedance.com/en/blog/seedance-2-0-official-launch).

### 1.2 Aktuelle technische Grenzen von Seedance 2.0 Fast bei Volcengine

| Eigenschaft | Offizieller Stand |
|---|---:|
| Model-ID | `doubao-seedance-2-0-fast-260128` |
| Ausgabeauflösung | 480p oder 720p, 8 Bit |
| Framerate | 24 fps |
| Dauer | 4–15 Sekunden oder `duration: -1` für intelligente Wahl |
| Seitenverhältnisse | `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`, `adaptive` |
| Audio | native synchrone Audioerzeugung; standardmäßig aktiviert |
| Bilder als multimodale Referenz | bis zu 9 |
| Videos als Referenz | bis zu 3, insgesamt höchstens 15 Sekunden |
| Audios als Referenz | bis zu 3, insgesamt höchstens 15 Sekunden |
| Reine Audioeingabe | bei 2.0/Fast nicht erlaubt; zusätzlich mindestens ein Bild oder Video nötig |
| Promptsprachen | offiziell: Chinesisch, Englisch, Spanisch, Indonesisch, Portugiesisch, Japanisch |
| Deutscher Prompt | nicht offiziell als unterstützt aufgeführt; Englisch ist für deutsche Nutzer der sichere Default |
| Empfohlene Maximallänge | Chinesisch höchstens 500 Zeichen; Englisch höchstens 1.000 Wörter |

Quellen: [Aktuelle Volcengine-Modellliste](https://www.volcengine.com/docs/82379/1330310), [Create Video Generation Task API](https://www.volcengine.com/docs/82379/1520757).

Wichtig: Andere Anbieter kapseln dasselbe Modell mit abweichenden Limits. Leonardo erlaubt zum Beispiel einen Prompt bis 5.000 Zeichen und stellt eigene Referenzfelder bereit; Fal und Leonardo führen Fast ebenfalls nur mit 480p/720p. Solche Wrapper-Parameter sind **Anbieterfunktionen**, keine universelle Seedance-Promptgrammatik. Quellen: [Leonardo Seedance 2.0 Fast](https://docs.leonardo.ai/docs/seedance-20-fast), [Fal Seedance 2.0 Fast](https://fal.ai/models/bytedance/seedance-2.0/fast/text-to-video/api).

### 1.3 Fast oder Standard?

Offiziell wird Fast als beschleunigte Variante für latenzkritische Szenarien beschrieben. Die aktuelle Volcengine-Ausgabe ist auf 720p begrenzt; Standard unterstützt inzwischen höhere Auflösungen. Ein belastbarer Prompting-Workflow ist deshalb:

1. Komposition, Handlung und Kamera mit Fast bei 480p oder 720p entwickeln.
2. Mehrere Takes erzeugen und den Prompt jeweils nur an einer Stelle ändern.
3. Gewinner mit Fast finalisieren, wenn 720p genügt, oder denselben Regieplan mit Standard in höherer Auflösung ausgeben.

Ein Filmemacher beschreibt genau diese Praxis: Fast in niedriger Qualität zur kostengünstigen Iteration, danach hochwertige Generierungen für den finalen Take. Das ist Praxiserfahrung, keine ByteDance-Garantie. Quelle: [Creative Bloq, Interview mit Kévin Mendiboure](https://www.creativebloq.com/ai/how-a-filmmaker-turned-a-10-year-old-unmakeable-movie-idea-into-reality-with-ai).

---

## 2. Das mentale Modell: Raum plus Zeit

Der wichtigste Gedanke des offiziellen Guides ist die Trennung in zwei Ebenen:

- **Raumebene:** Was befindet sich im Bild? Subjekte, Umgebung, Gegenstände, Positionen, Kleidung, Material, Licht, Farben und Stil.
- **Zeitebene:** Was verändert sich? Aktionen, Reaktionen, Bewegungsübergänge, Kamerafahrt, Schnitte, Rhythmus, Dialog und Ton.

Ein guter Prompt ist daher kein literarischer Absatz, sondern eine **ausführbare Produktionsanweisung**. Alles, was nur Stimmung behauptet, aber keine sicht- oder hörbare Konsequenz hat, ist schwächer als eine konkrete Beobachtung.

Schwach:

> A sad woman in a cinematic scene.

Stärker:

> A woman lowers her gaze; her shoulders tremble slightly, her fingers tighten around the edge of her coat, and tears gather in her eyes without falling. Medium close-up, slow stable push-in, cold window light.

Die zweite Fassung übersetzt „traurig“ in Körperhaltung, Mikroaktion, Bildgröße, Kamerafahrt und Licht.

---

## 3. Die Masterformel und die richtige Reihenfolge

Der offizielle Serienguide empfiehlt diese Reihenfolge:

```text
präzises Subjekt
+ Aktionsdetails
+ Szene/Umgebung
+ Licht/Farbton
+ Kamera/Bewegung
+ visueller Stil
+ Bildqualität
+ Constraints
```

Für die praktische Arbeit mit Ton und Referenzen wird daraus:

```text
1. Aufgabenmodus
2. Subjekt- und Referenzdefinition
3. sichtbare Hauptaktion
4. Szene und räumliche Beziehungen
5. Shot-Größe, Kamerawinkel und genau eine Kamerabewegung
6. Licht und Farbpalette
7. visueller Stil und Materialästhetik
8. Audio, Dialog und Rhythmus
9. Qualitätsziele
10. harte Constraints
```

### 3.1 Universaltemplate für einen einzelnen Shot

```text
[MODE / REFERENCE ASSIGNMENTS]

[SPECIFIC SUBJECT] performs [ONE VISIBLE ACTION with speed, force, amplitude,
and a natural transition] in [SPECIFIC ENVIRONMENT and spatial relation].

[SHOT SIZE and ANGLE]. [ONE CAMERA MOVE, speed, and endpoint].
[LIGHT SOURCE, COLOR PALETTE, ATMOSPHERE]. [VISUAL STYLE].

Audio: [dialogue / ambience / foley / music / silence].
Quality: [useful concrete quality goals].
Constraints: [only the few failures that matter].
```

### 3.2 Universaltemplate für mehrere Shots

```text
[SUBJECT DEFINITIONS AND REFERENCE MANIFEST]
[GLOBAL SCENE, STYLE, AUDIO, AND CONTINUITY RULES]

Shot 1: [framing + camera]. [subject + location + visible action/expression].
[audio cue].

Shot 2: [transition or cut + framing + camera]. [subject + action/reaction].
[audio cue].

Shot 3: [transition or cut + framing + camera]. [final action + endpoint].
[audio cue].

Global constraints: [identity, text, logo, duplicate, anatomy, flicker rules].
```

### 3.3 Warum diese Reihenfolge funktioniert

- Das Subjekt steht früh, weil es die semantische Priorität setzt.
- Die Aktion steht vor dem Stil, weil Video zuerst eine zeitliche Veränderung braucht.
- Szene und Licht bauen den räumlichen Rahmen.
- Kamera beschreibt, wie der Betrachter die Handlung erlebt.
- Stil und Qualität verfeinern eine bereits definierte Szene.
- Constraints stehen am Ende und verengen die Lösung, ohne das Hauptmotiv zu verdrängen.

Die Reihenfolge ist keine magische Parser-Syntax. Sie ist eine robuste Informationshierarchie. Wenn eine Referenz extrem wichtig ist, wird sie zusätzlich im ersten Block und bei jeder relevanten Aktion eindeutig genannt.

---

## 4. Schritt 1: Den Aufgabenmodus eindeutig festlegen

Seedance 2.0 unterscheidet semantisch zwischen Referenzgenerierung, Editing und Extension. Die Wortwahl entscheidet mit, wie das Modell die Aufgabe klassifiziert.

### 4.1 Neues Video mit Referenzen

Nutze „reference“ und sage **welche Eigenschaft** übernommen werden soll:

```text
Reference Image 1 for the woman's face and hairstyle only.
Reference Image 2 for her full-body wardrobe and silhouette.
Reference Video 1 for camera path and pacing only.
Reference Audio 1 for vocal timbre and emotional energy only.
Generate a new video...
```

Offizielle Grundmuster:

- Bild: Referenziere Subjekt, Szene, Gegenstand oder Stil aus Bild N.
- Video: Referenziere Bewegung, Kamera, Stil, Rhythmus, Effekt oder Ton aus Video N.
- Audio: Referenziere Stimmfarbe, Musik, Rhythmus oder Atmosphäre aus Audio N.

### 4.2 Video editieren

Beim Editing direkt das zu bearbeitende Video benennen. **Nicht** „reference Video 1“ schreiben, weil Seedance das sonst als Inspirationsquelle statt als Edit-Ziel interpretieren kann.

```text
Strictly edit Video 1. Replace the perfume bottle with the cream jar from
Image 1. Preserve the original hand motion, camera path, timing, background,
lighting, and all unmentioned regions.
```

Grundmuster:

```text
Strictly edit Video N: change [old property] to [new property].
Keep [everything that must remain unchanged].
```

Für das Hinzufügen eines Elements:

```text
Add [precise element] at [location] when [visible cue occurs].
Preserve all other content.
```

Für das Entfernen:

```text
Remove [precise element]. Keep [named protected regions] unchanged.
```

### 4.3 Video verlängern

Auch hier das Video direkt als Ziel benennen:

```text
Extend Video 1 forward. Continue the same character, environment, camera
language, visual style, motion direction, and audio atmosphere. Then...
```

Oder rückwärts:

```text
Extend Video 1 backward and create the preceding action...
```

### 4.4 Kombinationsaufgabe

```text
Reference Video 1 for the particle effect only. Strictly edit Video 2:
apply the same particle trajectory around the woman while preserving Video 2's
character identity, costume, location, camera path, and dialogue.
```

Merksatz:

> **Reference** beschreibt eine Quelle. **Strictly edit** beschreibt ein Ziel. **Extend** beschreibt eine zeitliche Fortsetzung.

---

## 5. Schritt 2: Subjekte definieren und dauerhaft binden

### 5.1 Einfache Szene ohne Vorabdefinition

Wenn ein Bild mehrere Objekte enthält, binde Subjekt und Asset bei jeder Erwähnung:

```text
the woman in a red dress from Image 1
the silver camera from Image 2
the restaurant interior from Image 3
```

In Dreamina/Jimeng kann die Oberfläche `@Image 1` oder Assetnamen einsetzen. In der Volcengine-API entspricht die Reihenfolge der `reference_image`-Elemente Image 1, Image 2 usw. Provider können stattdessen `[Image1]`, `@Image1` oder eigene Guidance-Felder verwenden.

### 5.2 Komplexe Szene: stabile Labels definieren

```text
Define the tall man in Video 1 as POLICE OFFICER.
Define the shorter man in Video 1 as THIEF.
Define the woman in Image 2 as SHOP OWNER.
```

Danach ausschließlich diese Labels verwenden. Nicht zwischen „man“, „he“, „officer“ und „tall person“ wechseln.

### 5.3 Gute Identitätsmerkmale

Nutze zwei bis drei stabile, statische Merkmale:

- Kleidung: red silk dress, dark-green apron
- Frisur: short silver bob, braided black hair
- Silhouette: tall and lean, compact round product body
- Kategorie/Material: matte ceramic bottle, brushed aluminum camera

Vermeide widersprüchliche Attribute wie „kurze glatte Locken“ oder wechselnde Farben.

### 5.4 Menschen: Headshot plus Ganzkörper statt Multi-View-Collage

Der offizielle Troubleshooting-Teil empfiehlt bei ID-Drift:

- ein separates, frontales, gut ausgeleuchtetes Gesichtsbild ohne starken Ausdruck;
- zusätzlich ein Ganzkörperbild für Kleidung und Silhouette;
- Gesicht und Styling im Prompt getrennt zuweisen;
- die wichtigste Referenz früh nennen.

```text
The protagonist's facial identity comes from Image 1, a clean headshot.
Her wardrobe and full-body silhouette come from Image 2.
```

Für menschliche Identität sollte keine Collage mit mehreren Ansichten verwendet werden. Das Modell kann verschiedene Ansichten fälschlich als mehrere Personen interpretieren. Bei Produkten können saubere Einzelbilder aus mehreren Winkeln dagegen hilfreich sein.

### 5.5 Referenzprioritäten explizit machen

Wenn Quellen konkurrieren, schreibe ein Manifest:

```text
Image 1: face identity only.
Image 2: wardrobe and body silhouette only.
Image 3: environment, palette, and key-light direction only.
Video 1: camera path and cut rhythm only; do not copy its actor or location.
Audio 1: tempo and vocal timbre only; do not reproduce its spoken words.

Priority: face identity > action continuity > camera path > set decoration.
```

Die Prioritätszeile ist eine praxisbewährte Ergänzung, keine dokumentierte Gewichtungssyntax. Sie hilft, Konflikte sprachlich zu lösen.

### 5.6 Nicht das Materiallimit ausreizen

Volcengine empfiehlt insgesamt ungefähr vier bis fünf funktionale Assets:

1. ein bis zwei Charakterbilder, typischerweise Headshot plus Ganzkörper;
2. ein Szenenbild;
3. ein kurzes Kamerabewegungs- oder Bewegungsreferenzvideo;
4. ein Audio für Rhythmus, Stimmung oder Stimme.

Mehr Material erzeugt nicht automatisch mehr Kontrolle. Es erhöht die Wahrscheinlichkeit widersprüchlicher Stile, unklarer Priorität und Identitätsverwechslungen.

---

## 6. Schritt 3: Aktionen sichtbar, körperlich und kausal schreiben

### 6.1 Die Aktionsformel

```text
Körperteil/Gegenstand + konkrete Bewegung + Geschwindigkeit + Amplitude
+ Kraft + Übergang + sichtbare Folge
```

Beispiele:

- `She slowly raises her right hand by ten centimeters.`
- `He turns his head quickly toward the doorway, then freezes.`
- `She pushes firmly off her left foot and lands with bent knees.`
- `Using the momentum of the turn, she naturally lifts the cup toward her lips.`

### 6.2 Kleine, kontinuierliche Bewegungen sind stabiler

Für maximale Trefferquote bevorzugt der offizielle Guide langsame, sanfte, zusammenhängende Mikroaktionen:

- slow walk
- slight head tilt
- gentle hand raise
- naturally sits down
- subtle breathing
- restrained eye movement

Große Sprünge, hektische Sprints, Überschläge und mehrere explosive Aktionen sind möglich, aber fehleranfälliger. Wenn sie wichtig sind:

1. nutze ein kurzes Bewegungsreferenzvideo;
2. teile die Sequenz in Shots oder eigenständige Clips;
3. beschreibe Abstoß, Flugphase, Kontakt und Landung kausal;
4. reduziere gleichzeitig Kamerakomplexität und Nebenaktionen.

### 6.3 Emotion in beobachtbare Signale übersetzen

| Abstrakt | Sichtbare Anweisung |
|---|---|
| Trauer | Blick sinkt, Schultern zittern leicht, Finger greifen den Mantelsaum, Tränen sammeln sich |
| Freude | Mundwinkel heben sich, Augenbrauen entspannen, Schritte werden leicht, kurzer spontaner Dreh |
| Nervosität | wiederholter Blick zur Uhr, Fingerspitzen klopfen, flacher Atem, ausweichender Blick |
| Wut | Fäuste schließen sich, Kiefer spannt an, Brust hebt und senkt sich stark, starrer Blick |
| Erleichterung | langer Ausatem, Schultern sinken, kleines Lächeln, Blick hebt sich in die Ferne |

### 6.4 Ursache vor Wirkung

Schwach:

```text
The glass breaks and everyone is shocked.
```

Stärker:

```text
The metal ball strikes the center of the glass. A spiderweb crack spreads
outward from the impact point; the pane collapses into small fragments.
Only after the crash do the three people recoil and cover their faces.
```

Die Reihenfolge verhindert, dass Reaktion, Ursache und Effekt gleichzeitig oder vertauscht erscheinen.

---

## 7. Schritt 4: Zeit mit Shots statt mit einer Prosawand kontrollieren

### 7.1 Die offizielle Empfehlung

Komplexe Videos werden als `Shot 1`, `Shot 2`, `Shot 3` in Ereignisreihenfolge geschrieben. Pro Shot:

1. Shot-Größe, Wechsel oder Kamerabewegung;
2. Hauptsubjekt und sichtbare Aktion;
3. Ort oder räumliche Veränderung;
4. passender Ton.

### 7.2 Exakte Sekundenangaben: ein wichtiger Widerspruch

Ältere offizielle Launch-Beispiele verwenden Bereiche wie `0–3 s`. Der neuere offizielle Promptguide vom Juni 2026 warnt jedoch, dass die Einhaltung exakter Zeitfenster instabil ist und harte Sekundenlimits zu ungewöhnlichen Ergebnissen führen können.

Darum gilt:

- **Standard:** `Shot 1 / Shot 2 / finally` und natürliche Rhythmuswahl.
- **Soft Timing:** „briefly“, „after a short pause“, „on the next beat“, „near the end“.
- **Zeitcodes nur als weiche Zielmarken**, wenn Beat-Sync, Werbung oder Dialog sie wirklich benötigt.
- Wenn exakte Synchronität entscheidend ist, Referenzaudio/-video und Postproduktion einsetzen.

### 7.3 Komplexität an die Länge anpassen

Praxisheuristik:

| Dauer | Sinnvolle Komplexität |
|---|---|
| 4–5 s | ein Subjekt, eine Hauptaktion, eine Kamerabewegung, eine Stimmung |
| 6–9 s | ein bis zwei zusammenhängende Beats oder zwei einfache Shots |
| 10–15 s | zwei bis vier klare Shots mit gemeinsamer Handlung |

Das ist keine harte Modellgrenze. Es ist ein Stabilitätsbudget. Jede zusätzliche Figur, Aktion, Kamerafahrt, Textzeile und Transformation verbraucht einen Teil davon.

### 7.4 Ein Shot oder mehrere Clips?

- **Video-Extension:** gut für Dialog, langsame emotionale Entwicklung und kontinuierliche Bewegung in derselben Szene.
- **Separat generieren und schneiden:** besser für Ortswechsel, schnelle Verfolgungen, Kampf, Montage und harte Plotwendungen.
- **Hybrid:** kontinuierlichen Dialog verlängern, Inserts/Establishing Shots separat generieren und im Schnitt verbinden.

---

## 8. Schritt 5: Kamera präzise beschreiben

### 8.1 Die Kamerazeile

```text
Shot-Größe + Winkel + Startposition + eine Bewegung + Geschwindigkeit
+ Endposition/Fokus
```

Beispiel:

```text
Medium close-up at eye level. The camera slowly pushes forward on a stable
axis and stops in a tight close-up with both eyes sharp.
```

### 8.2 Shot-Größen

| Begriff | Einsatz |
|---|---|
| extreme wide / establishing shot | Geografie, Maßstab, Einstieg |
| wide / full shot | ganze Figur und Umgebung |
| medium shot | Dialog, Gestik, Interaktion |
| medium close-up | Gesicht plus Schulter/Arme |
| close-up | Emotion, Produktdetail |
| extreme close-up / macro | Auge, Material, Tropfen, Mechanik |

### 8.3 Winkel und Perspektiven

- eye-level / neutral angle
- low-angle looking up
- high-angle looking down
- overhead / top-down
- aerial / drone
- over-the-shoulder
- first-person POV
- profile / side view
- underwater camera
- ground-level camera
- foreground-framed shot

### 8.4 Kamerabewegungen, die Seedance versteht

- slow push-in / dolly-in
- pull-back / dolly-out reveal
- pan left/right
- tilt up/down
- lateral tracking / truck left/right
- follow shot
- crane up/down
- orbit around subject
- stable locked-off shot
- handheld with subtle natural shake
- rack focus from foreground to background
- whip pan
- dolly zoom / Hitchcock zoom

Der aktuelle 2.0-Guide empfiehlt **eine Bewegungsart pro Shot**. Die ältere offizielle 1.0-Kamerareferenz zeigt zwar komplexe Kombinationen für One-Takes, aber bei Fast ist eine einzige klare Kameraintention die stabilere Grundregel. Komplexe Moves am besten als Start → Pfad → Ende oder über ein Referenzvideo definieren.

### 8.5 Häufige Kamerafehler

Schlecht:

```text
Fast zoom in while slowly dollying out, panning left and orbiting 360 degrees.
```

Gut:

```text
Start in a frontal medium shot at table height. Move clockwise in a smooth
30-degree arc at constant speed. End in a stable close-up of the label.
No zoom and no vertical camera movement.
```

### 8.6 Kamera nicht unnötig mikromanagen

Seedance 2.0 besitzt nach ByteDance-Angaben eigene Kamera- und Shot-Planungsfähigkeit. Für explorative Ideation darf der Prompt deshalb absichtlich nur Handlung und Stimmung definieren. Für reproduzierbare Produktionsshots ist explizite Kamera jedoch besser. Ein guter Workflow ist:

1. offene Version für unerwartete Regieideen;
2. beste gefundene Inszenierung in eine präzise Shot-Liste übersetzen;
3. kontrollierte Varianten erzeugen.

---

## 9. Schritt 6: Szene, Licht, Farbe und Stil

### 9.1 Szene

Beschreibe nur Dinge, die Bildaufbau oder Handlung ändern:

```text
inside a narrow 1970s train compartment
on a wet Tokyo side street at blue hour
in a clean white studio with a black marble tabletop
```

Räumliche Beziehungen möglichst durch Referenzbilder lösen. Lange verbale Geometriebeschreibungen erhöhen Konflikte.

### 9.2 Licht

Konkrete Lichtquellen sind besser als „beautiful lighting“:

- soft window light from camera left
- warm tungsten practicals in the background
- hard top light on the product
- cold moonlight with a narrow rim light
- diffused overcast daylight
- neon reflections on wet pavement
- backlit dust in volumetric haze

### 9.3 Farbe

- cold blue-gray low-saturation palette
- warm amber and muted green
- black, white, and orange only
- natural skin tones, restrained contrast
- deep shadows with controlled red highlights

### 9.4 Stil

Kombiniere nicht wahllos zehn Stilrichtungen. Nutze einen Hauptstil plus ein bis zwei materielle Merkmale:

```text
observational 2000s documentary, restrained contrast, subtle sensor noise
premium skincare commercial, clean specular highlights, crisp macro texture
2D Japanese animation, flat cel shading, clean linework
Chinese ink-wash animation, visible dry-brush texture, generous negative space
```

Wenn ein Referenzbild realistisch ist, der Output aber 2D/3D werden soll, Stil ausdrücklich wiederholen oder das Referenzbild vorher in den Zielstil umwandeln. Das reduziert Style Drift.

### 9.5 Qualität

Nützliche positive Qualitätsziele:

```text
clear facial structure, stable body proportions, natural skin texture,
coherent object geometry, smooth motion, consistent lighting,
rich material detail, natural color, restrained film grain
```

„4K“, „8K“ oder „60 fps“ im Prompt überschreibt nicht die Modellparameter. Fast gibt bei Volcengine maximal 720p und 24 fps aus. Auflösung, Dauer, Verhältnis und Audio gehören in die UI/API-Einstellungen, nicht als Wunschdenken in den Text.

---

## 10. Schritt 7: Audio, Dialog und Text

### 10.1 Audio als eigener Regiekanal

Seedance 2.0 kann Sprache, Foley, Umgebung und Musik gleichzeitig generieren. Beschreibe die Ebenen getrennt:

```text
Dialogue: the woman says in a quiet, controlled tone, "I knew you would come."
Foley: soft leather footsteps and one metallic click from the door lock.
Ambience: distant rain against the windows.
Music: no background music.
```

### 10.2 Dialog

Die aktuelle API-Dokumentation empfiehlt Dialog in doppelten Anführungszeichen. Verwende außerdem:

- Sprecher eindeutig benennen;
- Tonfall und Lautstärke angeben;
- kurze, sprechbare Sätze;
- bei mehreren Personen den Sprecherwechsel in getrennte Shots oder Beats legen;
- eine Sprache pro Dialogszene; Sprachmischung vermeiden.

Deutsch ist nicht offiziell als Prompt-/Sprachsupport genannt. Für deutsche Dialoge: Regieanweisungen auf Englisch, deutsche Rede klar markieren und mehrere Takes einplanen.

```text
The woman speaks in German, calmly and without subtitles:
"Ich wusste, dass du kommen würdest."
```

### 10.3 Referenzaudio

```text
Reference Audio 1 for vocal timbre, speaking pace, and emotional restraint.
Do not reproduce its original words. The new dialogue is: "..."
```

Stimmfarbe besser zusätzlich beschreiben: Alterseindruck, Tonhöhe, Rauheit, Tempo, Energie, Atemigkeit, Resonanz. Die Dialogart sollte zur Referenz passen.

### 10.4 Offizielle Symbolkonventionen

Der Volcengine-Guide zeigt folgende Informationsmarker:

| Typ | Marker | Beispiel |
|---|---|---|
| Musik | `( )` | `(slow restrained piano begins)` |
| Soundeffekt | `< >` | `<a dog barks in the distance>` |
| Dialog | `{ }` | `{Hello}` |
| On-Screen-Text | `【 】` | `【Chapter One】` |

Für anbieterübergreifende Prompts sind beschriftete Blöcke plus Anführungszeichen meist klarer. Die Marker sind hilfreich, aber keine universelle Programmiersyntax.

### 10.5 Text im Video

Textanweisung vollständig spezifizieren:

```text
Near the end, centered text appears: "MOVE WITH PURPOSE".
Bold white sans-serif, clean kerning, subtle fade-in, no other text.
```

Für Untertitel:

```text
Bottom-centered subtitles reproduce the spoken line exactly and remain
synchronized with the speech. No other text appears.
```

Verwende gebräuchliche Zeichen und kurze Texte. Texttreue ist weiterhin nicht perfekt. Für absolut korrekte Typografie Text besser in der Postproduktion setzen.

### 10.6 Stereo-Widerspruch

ByteDance bewirbt Seedance 2.0 mit zweikanaligem/immersivem Audio. Die aktuelle Volcengine-API-Dokumentation sagt jedoch, dass dort erzeugte Audio-Videos mono ausgegeben werden. Behandle Audio-Kanalzahl daher als plattformabhängig und prüfe die tatsächlich verwendete Oberfläche/API.

---

## 11. Schritt 8: Constraints statt Keyword-Müll

Constraints sollten kurz, relevant und prüfbar sein.

### 11.1 Solider globaler Constraint-Block

```text
Preserve the defined character identity, wardrobe, and object geometry.
Natural anatomy and physically plausible contact.
No duplicate people, no identity swap, no extra limbs, no flicker.
No subtitles, no text, no logo, and no watermark.
```

### 11.2 Was Constraints nicht leisten

- Sie garantieren keine fehlerfreien Hände.
- Sie verhindern Text, Logos oder Wasserzeichen nicht zu 100 %.
- Sie ersetzen keine klare positive Szenenbeschreibung.
- Eine riesige Liste negativer Begriffe kann Aufmerksamkeit vom Ziel abziehen.

Regel: Nenne nur die drei bis sechs Fehler, die diesen Shot wirklich ruinieren würden.

---

## 12. Modusspezifische Templates

### 12.1 Text-to-Video

```text
A matte-black espresso machine with brushed steel controls releases one slow
stream of coffee into a clear glass cup. Steam curls upward while the crema
forms a clean amber layer. Minimal modern cafe interior at dawn.

Macro close-up at counter height. Slow stable push-in, ending with the crema
and steel texture in sharp focus. Soft window light from the left, warm neutral
palette. Premium observational product film, crisp material detail.

Audio: quiet machine hum, liquid pour, soft cup resonance; no music.
Constraints: stable product geometry, no extra controls, no text, no logo,
no watermark, no camera shake.
```

### 12.2 Image-to-Video: Referenzbild trägt das Aussehen, Prompt trägt die Bewegung

```text
Use Image 1 as the exact character and composition reference.
The woman blinks once, slowly turns her gaze toward the window, takes a quiet
breath, and lightly tightens her fingers around the cup. A soft breeze moves
only a few loose strands of hair and the curtain.

Locked medium close-up with no cut. Very subtle dolly-in.
Preserve her face, hairstyle, clothing, cup, room layout, and color palette.
Natural micro-motion, stable anatomy, no new objects, no text or watermark.
```

### 12.3 First/Last Frame

First- und Last-Frame-Modus ist in der API vom multimodalen Referenzmodus getrennt. Wenn exakte Anfangs-/Endkomposition wichtiger ist als zusätzliche Referenzen, nutze diesen Modus.

```text
Begin exactly from the first-frame image. The paper sculpture unfolds in one
continuous physically coherent motion; each fold opens from the center outward
while the camera remains locked. The motion settles naturally into the exact
composition of the last-frame image. Preserve material texture and lighting.
No cut, no extra folds, no text.
```

### 12.4 Bewegungsreferenz

```text
Reference Video 1 for choreography, acceleration, pauses, and body rhythm only.
Apply that motion to the woman from Image 1. Do not copy the original dancer's
face, body, clothing, background, camera, or text.

The new scene is a quiet concrete studio. Medium-wide lateral tracking shot.
Preserve the woman from Image 1 throughout. Soft overhead light, muted gray
palette. No duplicates, no identity drift, no subtitles.
```

### 12.5 Kamerareferenz

```text
Reference Video 1 for camera height, path, speed, framing changes, and cut
rhythm only. Use the product from Image 1 as the new subject and the set from
Image 2 as the environment. Do not copy Video 1's people, wardrobe, text,
logos, or location.
```

### 12.6 Style-/VFX-Referenz

```text
Reference Video 1 for the golden particle shape, density, trajectory, and
dissipation only. Apply the effect around the flute player from Image 1.
The particles emerge on the first note, orbit once at shoulder height, then
dissolve upward. Preserve the character and background. No other effects.
```

### 12.7 Video-Editing

```text
Strictly edit Video 1. Replace the perfume bottle with the cream jar from
Image 1. Preserve the exact hand contact, finger placement, action timing,
camera path, background, lighting, shadows, audio, and all unmentioned regions.
Keep the new jar's label and geometry stable. Add nothing else.
```

### 12.8 Video-Extension

```text
Extend Video 1 forward. Continue the same character identity, clothing,
location, lighting, camera direction, walking speed, and ambient sound.
The woman takes two more slow steps, notices the open door on her right,
briefly stops, and turns only her head toward it. The camera follows at the
same distance and settles behind her shoulder. No cut and no new character.
```

### 12.9 Dialogszene

```text
Define the woman in Image 1 as MAYA and the man in Image 2 as LEON.
Reference Image 3 for the small train compartment.

Shot 1: Medium two-shot at eye level, locked camera. MAYA keeps her gaze on the
rainy window; her thumb slowly rubs the rim of the cup. LEON sits opposite her,
waiting. Quiet train rumble.

Shot 2: Cut to MAYA in medium close-up. She exhales, turns toward LEON, and says
in German, softly: "Ich habe dir nicht die ganze Wahrheit gesagt."

Shot 3: Cut to LEON's close-up. He does not speak; his jaw tightens and his eyes
drop briefly to the table. The train enters a tunnel and the window light fades.

Natural conversational pacing, restrained acting, cool rainy daylight, realistic
European drama. Preserve both identities and wardrobe. No subtitles, no music,
no duplicate characters, no camera movement within a shot.
```

---

## 13. Fast-spezifischer Iterationsworkflow

### 13.1 Pass 0: Brief in eine Shot-Spezifikation übersetzen

Vor dem Generieren diese Fragen beantworten:

1. Was ist der einzige primäre Blickfang?
2. Was verändert sich sichtbar?
3. Wie beginnt und endet die Aktion?
4. Wie beginnt und endet die Kamera?
5. Welches Asset steuert welche Eigenschaft?
6. Was sind die drei fatalsten Fehler?

### 13.2 Pass 1: Minimalprompt

Nur Subjekt, Aktion, Szene und Kamera. Prüfe Komposition und Bewegungslogik.

### 13.3 Pass 2: Identität und Referenzzuweisung

Headshot, Ganzkörper, Produkt oder Szenenasset eindeutig zuweisen. Noch keine unnötigen Stilwörter hinzufügen.

### 13.4 Pass 3: Licht, Farbe und Stil

Nur eine visuelle Variable ändern. Beispiel: zuerst Licht, dann Farbpalette, dann Materialästhetik.

### 13.5 Pass 4: Audio und Text

Dialog, Foley, Atmosphäre und Musik getrennt ergänzen. Text im Bild nur hinzufügen, wenn er wirklich generativ entstehen muss.

### 13.6 Pass 5: Constraints

Nur beobachtete Fehler bekämpfen. Keine prophylaktische Liste mit 40 Negativbegriffen.

### 13.7 Best-of-N statt „perfekter Seed“

Die aktuelle Volcengine-Dokumentation führt den `seed`-Parameter nicht als unterstützt für Seedance 2.0/Fast auf. Manche Drittanbieter bieten trotzdem einen Wrapper-Seed an. Selbst dort ist gleiche Ausgabe nicht garantiert. Plane deshalb mehrere Takes und eine Auswahlphase ein.

### 13.8 Pro Iteration nur eine Variable

Führe ein Log:

| Version | Änderung | Identität | Aktion | Kamera | Audio | Auswahlgrund |
|---|---|---:|---:|---:|---:|---|
| v01 | Basis | 3 | 2 | 3 | – | Aktion zu hektisch |
| v02 | „slowly“ + Übergang | 3 | 4 | 3 | – | behalten |
| v03 | Licht geändert | 3 | 4 | 3 | – | Hauttöne schlechter |

Bewertungsskala 1–5:

- Prompttreue
- Identitäts-/Produktkonsistenz
- Physik und Kontakt
- Bewegungskontinuität
- Kameratreue
- Komposition und Licht
- Audioqualität/Synchronität
- Text-/Logo-Treue
- Nutzbare Sekunden

---

## 14. Fehlerdiagnose und Reparatur

### 14.1 ID Drift oder „Gesichtswechsel“

**Ursachen:** Gesicht zu klein, Collage, konkurrierende Menschen, wechselnde Bezeichnungen, Prompt zu lang.

**Fix:**

1. separates neutrales Headshot-Asset;
2. Ganzkörper separat;
3. Gesicht früh und eindeutig zuweisen;
4. konstantes Label in jedem Shot;
5. Nebenrollen reduzieren;
6. Referenz- und Stilkonflikte entfernen.

### 14.2 Doppelte Person / Zwilling

Am Promptende:

```text
Never show duplicate people or matching clones. Each defined character appears
only once in the same frame. No identical wardrobe, accessories, or face is
repeated on another person.
```

Zusätzlich Einzelbilder statt Multi-View-Collagen und maximal wenige Referenzpersonen verwenden.

### 14.3 Mehr als vier Referenzpersonen

Der offizielle Guide meldet sinkende Stabilität oberhalb von vier Personen. Workaround:

1. Personen in Gruppen bis vier aufteilen;
2. pro Gruppe ein sauberes Gruppenbild erzeugen;
3. diese Gruppenbilder als Referenzen für den finalen Clip nutzen.

### 14.4 Unerwünschte Untertitel

```text
No subtitles. No captions. No letters, words, or interface elements anywhere.
```

Zusätzlich Text aus Referenzbildern/-videos vorher entfernen. Laut Volcengine tritt unerwünschter Text im Querformat seltener als im Hochformat auf; wenn der Workflow es erlaubt, horizontal generieren und später schneiden.

### 14.5 Unerwünschtes Logo oder Wasserzeichen

```text
No logo and no watermark.
```

API-Wasserzeichen zusätzlich mit `watermark: false` abschalten. Prompt und Parameter lösen unterschiedliche Ursachen.

### 14.6 Style Drift

- Zielstil ausdrücklich nennen;
- realistische Referenz vorab in Zielstil umwandeln;
- einen Hauptstil verwenden;
- Stil pro Shot wiederholen, wenn die Szene wechselt;
- konkurrierende Stilreferenzen entfernen.

### 14.7 Effekt stimmt nicht

Text allein ist schwach für präzise Partikelformen, Countdowns, Transformationen oder komplexe Übergänge. Ein kurzes Effektvideo als Referenz verwenden und nur Form, Flugbahn, Geschwindigkeit und Auflösung übernehmen lassen.

### 14.8 Extension springt am Schnitt

Offizieller Postproduktions-Workaround:

- am Ende des vorherigen Clips sechs Frames entfernen;
- am Anfang des neuen Clips einen Frame entfernen;
- alle Übergänge prüfen;
- Extensions möglichst mit einem natürlichen Cut/Transition beenden und den nächsten Clip im neuen Bildzustand starten.

### 14.9 Extension verliert Bildqualität

Mehrfache Fortsetzungen akkumulieren Fehler, besonders im Gesicht. Maßnahmen:

- möglichst vom hochwertigsten Ursprungsmaterial verlängern;
- Anzahl der Extensions begrenzen;
- hochauflösende Bildreferenz erneut mitführen;
- lange Sequenz in unabhängige Shots zerlegen;
- ungewöhnlicher offizieller Workaround: Ursprungsbewegung als weißes, texturloses 3D-„White Model“-Video abstrahieren und dieses als Bewegungsbasis verwenden.

### 14.10 Audio klickt am Ende

Neu generieren oder in CapCut/Jianying bzw. einem NLE die letzten Frames mit einer Lautstärkehüllkurve auf null ausblenden.

### 14.11 Aussprachefehler

- kurze Sätze und gebräuchliche Wörter;
- keine Sprachmischung;
- problematische Eigennamen phonetisch vereinfachen;
- mehrere Takes;
- kritischen Dialog extern aufnehmen und als Referenz/Finalton verwenden.

### 14.12 Zu viel passiert, Teile fehlen

Symptom: Modell zeigt Fragmente aller Wünsche, aber keine vollständige Kausalität.

Fix:

1. Nebenhandlungen löschen;
2. pro Shot eine Hauptaktion;
3. einen Kameramove;
4. harte Sekundenmarken entfernen;
5. komplexen Shot in zwei Clips teilen;
6. wichtige Anweisung nach vorne;
7. Referenzmanifest verkürzen.

---

## 15. API- und UI-Bedienung: Prompt versus Parameter

### 15.1 Was in Parameterfelder gehört

- Model-ID
- Auflösung
- Seitenverhältnis
- Dauer
- Audio an/aus
- Wasserzeichen
- Referenzrollen

Diese Angaben nicht nur in Prosa schreiben. Die aktuelle Volcengine-API empfiehlt starke, separat validierte Body-Parameter.

### 15.2 Minimales Volcengine-Beispiel für Fast

```json
{
  "model": "doubao-seedance-2-0-fast-260128",
  "content": [
    {
      "type": "text",
      "text": "A matte-black espresso machine releases one slow stream of coffee into a clear glass cup. Macro close-up, stable slow push-in, soft window light, realistic product film. Audio: quiet machine hum and liquid pour. No text or watermark."
    }
  ],
  "resolution": "720p",
  "ratio": "16:9",
  "duration": 6,
  "generate_audio": true,
  "watermark": false
}
```

Endpoint:

```text
POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks
```

### 15.3 Multimodale Referenzen

```json
{
  "model": "doubao-seedance-2-0-fast-260128",
  "content": [
    {
      "type": "text",
      "text": "Reference Image 1 for product identity only. Reference Video 1 for camera path only. Reference Audio 1 for tempo only. Generate a new premium product film. Do not copy the actor, room, text, or spoken words from the references."
    },
    {
      "type": "image_url",
      "image_url": { "url": "https://example.com/product.png" },
      "role": "reference_image"
    },
    {
      "type": "video_url",
      "video_url": { "url": "https://example.com/camera.mp4" },
      "role": "reference_video"
    },
    {
      "type": "audio_url",
      "audio_url": { "url": "https://example.com/tempo.mp3" },
      "role": "reference_audio"
    }
  ],
  "resolution": "720p",
  "ratio": "16:9",
  "duration": 8,
  "generate_audio": true,
  "watermark": false
}
```

### 15.4 Referenzmodi sind teilweise gegenseitig exklusiv

In der offiziellen API sind diese Modi getrennt:

- First Frame
- First + Last Frame
- multimodale All-Reference-Generierung

Sie dürfen nicht beliebig als Rollen gemischt werden. Multimodale Referenzgenerierung kann ein Bild im Prompt als gewünschten Start-/Endzustand nennen, garantiert aber nicht dieselbe Präzision wie der dedizierte First/Last-Frame-Modus.

### 15.5 Web Search Tool

Volcengine erlaubt bei Seedance 2.0/Fast optional `tools: [{"type":"web_search"}]`. Das Modell entscheidet dann, ob es aktuelle Informationen wie Produkte oder Wetter sucht. Das erhöht Latenz und ersetzt keine klare visuelle Spezifikation.

---

## 16. Die „perfekter Prompt“-Checkliste

Vor dem Absenden:

- [ ] Ist der Aufgabenmodus eindeutig: neu, referenzieren, editieren oder verlängern?
- [ ] Steht das wichtigste Subjekt früh?
- [ ] Ist jede Referenz auf genau eine Funktion begrenzt?
- [ ] Haben wiederkehrende Figuren konstante Labels?
- [ ] Hat jeder Shot eine sichtbare Hauptaktion?
- [ ] Sind Geschwindigkeit, Amplitude, Kraft und Übergang nur dort genannt, wo nötig?
- [ ] Ist Ursache vor Wirkung beschrieben?
- [ ] Hat jeder Shot höchstens eine primäre Kamerabewegung?
- [ ] Sind Shot-Größe, Winkel und Kameraendpunkt klar?
- [ ] Sind Lichtquelle und Farbpalette konkret?
- [ ] Gibt es einen dominanten Stil statt einer Adjektivsammlung?
- [ ] Sind Dialog, Foley, Atmosphäre und Musik getrennt?
- [ ] Sind harte Sekundenmarken wirklich erforderlich?
- [ ] Sind technische Einstellungen in UI/API statt nur im Prompt gesetzt?
- [ ] Enthält der Constraint-Block nur relevante Fehler?
- [ ] Passt die Komplexität in 4–15 Sekunden?
- [ ] Sind menschliche Referenzen Headshot plus Ganzkörper statt Multi-View-Collage?
- [ ] Werden nicht unnötig alle Referenzslots gefüllt?
- [ ] Wird pro Iteration nur eine Variable geändert?
- [ ] Sind mehrere Takes eingeplant?

---

## 17. Merksystem zum Auswendiglernen

### Die acht Kernbausteine

```text
WER – TUT WAS – WO – IN WELCHEM LICHT – WIE GEFILMT
– IN WELCHEM STIL – WIE SOLL ES KLINGEN – WAS DARF NICHT PASSIEREN
```

### Die fünf Regeln

1. **Eindeutigkeit vor Länge.**
2. **Sichtbare Aktion vor abstrakter Stimmung.**
3. **Ein Shot, eine Hauptaktion, eine Kameraintention.**
4. **Jede Referenz bekommt genau eine Aufgabe.**
5. **Fast iteriert; Auswahl und Schnitt vollenden.**

### Die Drei-Pass-Methode

```text
PASS A — Inhalt: Subjekt, Aktion, Szene
PASS B — Regie: Shots, Kamera, Licht, Audio
PASS C — Stabilität: Referenzbindung, Qualität, Constraints
```

---

## 18. Was man nicht als gesichert behandeln sollte

Folgende Behauptungen tauchen oft in SEO-Artikeln oder Community-Posts auf, sind aber nicht als universelle Seedance-2.0-Fast-Regeln belegt:

- Fast brauche grundsätzlich weniger als 80 Wörter.
- Seedance lese strikt links nach rechts mit messbar abnehmender Gewichtung.
- Wörter wie „masterpiece“, „8K“ oder Kamera-Marken erzeugten verlässlich bessere Qualität.
- Klammern oder Doppelklammern änderten Keyword-Gewichte wie bei Stable Diffusion.
- Ein identischer Seed liefere ein identisches Video.
- Exakte Sekundenbereiche würden zuverlässig eingehalten.
- Maximale Referenzanzahl erzeuge maximale Konsistenz.
- Seedance 2.0 Fast gebe bei Volcengine 1080p oder 4K nativ aus.
- Deutsche Prompts seien offiziell gleichwertig unterstützt.

Solche Techniken dürfen getestet werden, gehören aber in ein Experimentprotokoll, nicht in den unveränderlichen Kern des Prompting-Systems.

---

## 19. Quellenbewertung und weiterführende Quellen

### Primärquellen

1. [Volcengine: Doubao Seedance 2.0 Series Prompt Guide](https://www.volcengine.com/docs/82379/2222480) – wichtigste Quelle für Promptstruktur, Task-Klassifikation, Referenzbindung, Shot-Reihenfolge, Aktionsbeschreibung, Constraints und Troubleshooting.
2. [Volcengine: Create Video Generation Task API](https://www.volcengine.com/docs/82379/1520757) – aktueller Stand für Parameter, Promptlänge, Sprachen, Referenzrollen, Dateilimits, Dauer, Audio und Modusgrenzen.
3. [Volcengine: Model List](https://www.volcengine.com/docs/82379/1330310) – Model-ID, 480p/720p, 24 fps, 4–15 Sekunden und Fast-Funktionsumfang.
4. [ByteDance Seed: Seedance 2.0 Official Launch](https://seed.bytedance.com/en/blog/seedance-2-0-official-launch) – offizielle Beispielprompts, multimodale Fähigkeiten, Kamera-/Audioaussagen und bekannte Grenzen.
5. [ByteDance Seed: Seedance 2.0 Model Page](https://seed.bytedance.com/en/seedance2_0) – Produktpositionierung und Regiekontrolle.
6. [Seedance 2.0 Technical Report](https://arxiv.org/abs/2604.14148) – Architektur, Fast-Positionierung, Evaluation und Limitierungen.
7. [Volcengine: Seedance 1.0 Series Prompt Guide](https://www.volcengine.com/docs/82379/1631633#afc80793) – vom 2.0-Guide verlinktes offizielles Kameravokabular; ältere komplexe Kamerabeispiele nur mit Vorsicht auf Fast übertragen.
8. [Volcengine Developer Community: Seedance 2.0 Launch in Ark](https://developer.volcengine.com/articles/7606009619928449070) – offizielle Demo-Prompts und frühe Produktbeispiele.

### Sekundärquellen und Praxisabgleich

9. [Luma: How to Prompt Seedance 2.0](https://lumalabs.ai/learning-center/articles/how-to-prompt-seedance-2.0) – gute praktische Zusammenfassung von Subjekt, Bewegung, Kamera, Referenzen, Audio und Text. Wo sie der neueren ByteDance-Anleitung widerspricht, hat die Primärquelle Vorrang.
10. [Fal: Seedance 2.0 Fast API](https://fal.ai/models/bytedance/seedance-2.0/fast/text-to-video/api) – Wrapper-Limits und Fast-Parameter.
11. [Leonardo: Seedance 2.0 Fast](https://docs.leonardo.ai/docs/seedance-20-fast) – alternative Providerfelder, Referenzstärken und Promptlimit.
12. [Replicate: ByteDance Seedance 2.0](https://replicate.com/bytedance/seedance-2.0/readme) – offizielle Partnerbereitstellung und Referenzsyntax.
13. [Creative Bloq: Filmmaker workflow](https://www.creativebloq.com/ai/how-a-filmmaker-turned-a-10-year-old-unmakeable-movie-idea-into-reality-with-ai) – reale Fast-zu-Final-Iteration und die Bedeutung von Auswahl/Postproduktion.

### Qualitätswarnung zur Recherche

Die Volcengine-Domain enthält neben offizieller Produktdokumentation auch Community-/SEO-Artikel. Domainname allein bedeutet deshalb nicht, dass ein Text von ByteDance-Forschern oder dem Produktteam stammt. Für diesen Guide wurden Angaben nur dann als „offiziell“ behandelt, wenn sie aus dem Dokumentationszentrum, ByteDance Seed, der API-Referenz, der Modellliste oder dem technischen Bericht stammen.

---

## Schlussformel

Der perfekte Seedance-2.0-Fast-Prompt ist nicht der längste und nicht der mit den meisten Filmbegriffen. Er ist die kürzeste vollständige Regieanweisung, die:

1. das Subjekt stabil verankert,
2. eine sichtbare und kausale Handlung vorgibt,
3. den zeitlichen Ablauf in klare Shots zerlegt,
4. der Kamera pro Shot einen eindeutigen Weg gibt,
5. Referenzen funktional statt dekorativ zuweist,
6. Ton und Text als eigene Spuren behandelt,
7. nur relevante Fehler verbietet und
8. durch kontrollierte Fast-Iterationen, Auswahl und Schnitt verfeinert wird.

