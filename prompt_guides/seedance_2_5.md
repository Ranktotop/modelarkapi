# Seedance 2.5 Prompting Guide

**Stand: 21. August 2026**  
**Fokus:** ByteDance/Dreamina Seedance 2.5 für Text-to-Video, First/Last Frame, multimodale Referenzen, Keyframes, Storyboards, Blockouts, Video- und Audio-Editing, Extension und lange Erzählungen  
**Ziel:** aus einer Idee eine überprüfbare Produktionsanweisung machen, die Seedance 2.5 möglichst wenig interpretieren muss

> Die wichtigste Regel: Ein starker Seedance-2.5-Prompt ist kein Haufen Filmadjektive. Er ist ein kompakter Produktionsplan. Er legt fest, **welcher Task ausgeführt wird**, **welche Assets welche Aufgabe haben**, **welche Zustände nacheinander entstehen**, **was unverändert bleibt** und **wie Bild, Kamera und Ton zusammenarbeiten**.

---

## 1. Quellenlage und Vertrauensstufen

Dieser Guide unterscheidet bewusst zwischen Modellfakten, Plattformfunktionen und Praxiserfahrung.

### Stufe A: Primärquellen

Die wichtigsten Aussagen stammen aus:

1. dem [offiziellen ByteDance-Seed-Launch](https://seed.bytedance.com/en/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5),
2. der [offiziellen Seedance-2.5-Modellseite](https://seed.bytedance.com/en/seedance2_5),
3. dem [offiziellen BytePlus-Promptguide](https://docs.byteplus.com/en/docs/ModelArk/2607689),
4. dem [offiziellen BytePlus-Tutorial](https://docs.byteplus.com/en/docs/ModelArk/2607688),
5. der [aktuellen Video-API-Referenz](https://docs.byteplus.com/api/docs/ModelArk/1520757) und
6. ByteDance/BytePlus’ offiziellem Prompt-Optimierungs-Skill `sd25-pe`, auf das Promptguide und Tutorial ausdrücklich verweisen.

### Stufe B: ByteDance-nahe Produktoberflächen

Dreamina und CapCut gehören zum ByteDance-Ökosystem. Ihre Angaben beschreiben jedoch teilweise **Produkt-Workflows inklusive Nachbearbeitung**, nicht nur den nackten Modellendpunkt. Das ist besonders bei 4K, 60 fps und 180-Sekunden-Modi wichtig.

- [Dreamina Seedance 2.5](https://dreamina.capcut.com/seedance/seedance-2-5)
- [CapCut Seedance 2.5](https://www.capcut.com/zh-tw/features/seedance-2-5-for-video-editor)

### Stufe C: offizielle Partner und Provider

- [Replicate: offizielles ByteDance-Modell](https://replicate.com/bytedance/seedance-2.5)
- [fal: Seedance-2.5-Dokumentationsguide](https://fal.ai/learn/devs/how-to-use-seedance-2-5)
- [fal: Seedance-2.5-API](https://fal.ai/models/bytedance/seedance-2.5/text-to-video/api)

Diese Quellen sind nützlich, um Provider-Unterschiede zu erkennen. Ihre Parameter dürfen nicht ungeprüft auf BytePlus ModelArk, Jimeng, Dreamina oder CapCut übertragen werden.

### Was nicht als Primärquelle behandelt wurde

Ein Artikel auf einer Volcengine-Community-Domain ist nicht automatisch ein offizielles Produktdokument. Ebenso sind Webseiten mit „Seedance“ im Domainnamen häufig unabhängige Wrapper oder SEO-Seiten. Behauptungen wie „native 4K in jeder API“, „bis zu 50 Referenzbilder“ oder „framegenaue Kontrolle“ wurden nur übernommen, wenn eine aktuelle Primärquelle sie stützt.

---

## 2. Was Seedance 2.5 offiziell ist

Seedance 2.5 ist ByteDances neues Audio-Video-Gemeinschaftsmodell für längere Erzählungen, umfangreiche multimodale Referenzen und gezielte Video-/Audio-Bearbeitung.

### 2.1 Offiziell bestätigte Kernfähigkeiten

| Bereich | Offiziell bestätigter Stand |
|---|---|
| Modell-ID bei BytePlus ModelArk | `dreamina-seedance-2-5-260628` |
| Standarddauer | 4 bis 30 Sekunden oder automatische Dauer `-1` |
| Bildreferenzen | bis zu 30 |
| Videoreferenzen | bis zu 10; zusammen höchstens 30 Sekunden |
| Audioreferenzen | bis zu 10; zusammen höchstens 30 Sekunden |
| Gesamtzahl Referenzassets | bis zu 50 |
| Audio-only-Referenz | bei BytePlus ModelArk für 2.5 unterstützt |
| Standardausgabe ModelArk | 480p, 720p oder 1080p |
| Framerate ModelArk | 24 fps |
| Formate ModelArk | MP4 und MOV |
| Native Audioerzeugung | standardmäßig aktiviert |
| Zeitsteuerung | ganzzahlige Sekundenintervalle, Zeitpunkte und relative Zeit |
| Editing | Bild und Ton, optional auf Zeitbereiche begrenzt |
| Extension | vorwärts und rückwärts |
| First/Last Frame | unterstützt |
| Keyframes und Storyboards | unterstützt |
| Blockout/Clay Render | grobe und feine 3D-Vorvisualisierung |
| Promptsprachen | Englisch plus zehn weitere offiziell gelistete Sprachen; Deutsch ist nicht ausdrücklich gelistet |

### 2.2 30 Sekunden sind eine Erzählfläche, kein Zwang

Die maximale Länge von 30 Sekunden bedeutet nicht, dass jede Idee auf 30 Sekunden gedehnt werden sollte. Ein klarer 8-Sekunden-Shot kann besser sein als eine unterfüllte 30-Sekunden-Sequenz. Nutze 30 Sekunden, wenn die Handlung mehrere kausal verbundene Zustände benötigt.

### 2.3 Keine eigene „Fast“-Variante

Seedance 2.5 wird in den aktuellen offiziellen Unterlagen als eigenständiges Produktionsmodell geführt. Eine offizielle Variante „Seedance 2.5 Fast“ ist im recherchierten Stand nicht dokumentiert.

### 2.4 Kein öffentliches technisches 2.5-Paper

ByteDance führt Seedance 2.5 zum Recherchezeitpunkt als Modell und Launch-Blog, aber nicht als eigenständige wissenschaftliche Publikation. Architekturdetails, Parameterzahl oder unabhängige Benchmarktabellen sind daher nicht so umfassend dokumentiert wie bei Seedance 2.0. Aussagen aus dem 2.0-Paper dürfen nicht automatisch als neue 2.5-Spezifikation verkauft werden.

---

## 3. Plattformmatrix: Warum sich technische Angaben widersprechen

„Seedance 2.5“ bezeichnet das Modell, aber die sichtbaren Einstellungen hängen von der Produktoberfläche ab.

| Plattform | Dokumentierter Output | Dauer | Besonderheit |
|---|---:|---:|---|
| BytePlus ModelArk | 480p, 720p, 1080p | 4–30 s | 1080p: 10-Bit, HEVC; MP4 oder MOV |
| BytePlus LAS Enhanced | 480p, 720p | 4–30 s | zusätzlicher Vor-/Nachbearbeitungsdienst |
| fal | 480p, 720p | 4–30 s/Auto | provider-spezifische Endpunkte |
| Dreamina/CapCut | bewirbt 4K und teils bis 60 fps | Standard bis 30 s; Beta-Workflow bis 180 s | kann Upscaling, Interpolation oder Produktoberflächen-Nachbearbeitung einschließen |
| Replicate | Schema des jeweiligen Deployments | bis 30 s | Wrapper-Parameter wie `seed` können von ModelArk abweichen |

### Die sichere Formulierung

- **Modellkern/ModelArk:** bis 1080p, 24 fps.
- **LAS-Operator und manche Drittanbieter:** derzeit bis 720p.
- **Dreamina/CapCut-Produktworkflow:** bewirbt 4K/60-fps-Ausgabe; das ist nicht dasselbe wie ein überall verfügbarer nativer ModelArk-Parameter.

Schreibe deshalb niemals „4K“ oder „60 fps“ in den Prompt, um einen nicht vorhandenen Parameter zu erzwingen. Wähle Auflösung, Dauer, Format und Framerate in der jeweiligen Oberfläche.

---

## 4. Was sich gegenüber Seedance 2.0 wirklich geändert hat

### 4.1 Timestamps sind jetzt ein offizieller Kontrollkanal

Bei Seedance 2.0 waren Shotnummern zuverlässiger als sekundengenaue Vorgaben. Seedance 2.5 unterstützt ausdrücklich:

- Zeitintervalle wie `0–4 s`,
- einzelne Zeitpunkte wie „bei Sekunde 5“ und
- relative Zeit wie „drei Sekunden nach dem Knopfdruck“.

Das macht Timestamps nützlich, aber nicht framegenau. Ein Zeitbereich ist ein **Budget für ein Ereignis**, kein garantierter Schnittpunkt.

### 4.2 Multi-View-Referenzen werden unterstützt

2.0 riet bei Menschen häufig von Multi-View-Collagen ab. 2.5 kann mehrere Ansichten besser verarbeiten. Trotzdem gilt:

- bis fünf Subjekte: Einzel- und Mehrfachansichten sind möglich;
- bei mehr als fünf Subjekten sind getrennte Einzelansichten meist stabiler;
- getrennte Dateien sind leichter eindeutig zuzuordnen als ein überfülltes Kontaktblatt.

### 4.3 Assets werden semantisch oder timeline-lockend benutzt

Seedance 2.5 unterscheidet deutlicher:

- **Unlocked/semantische Referenz:** Das Asset liefert Identität, Stil, Bewegung, Stimme oder Struktur. Verhältnis und Dauer können frei sein.
- **Locked:** Das Asset ist eine Randbedingung oder Timeline-Grundlage. First Frame, Editing und Extension sperren bestimmte Parameter.

### 4.4 Editing und Extension sind eigene Tasktypen

Ein Video im Input macht den Task nicht automatisch zu Video-Editing. Entscheidend ist die Absicht:

- „Nutze die Kamerabewegung aus Video 1“ → Referenzgenerierung.
- „Ersetze in Video 1 den roten Becher“ → Editing.
- „Setze Video 1 nach hinten fort“ → Extension.

### 4.5 Produktionsassets werden stärker verstanden

Neu oder deutlich ausgebaut sind:

- grobe und feine Blockout-/Clay-Render-Referenzen,
- Multi-Keyframes,
- Storyboard-Grids,
- Green-Screen-Workflows,
- Perspektivänderungen,
- Audio-Editing,
- nahtlose Übergänge und
- Ein-Klick-Montagen aus mehreren Assets.

---

## 5. Das mentale Modell: Story Contract, Asset Contract, State Machine

Die zuverlässigste Denkweise hat drei Ebenen.

### 5.1 Story Contract: Was darf sich inhaltlich nicht ändern?

Notiere intern:

- Subjekte und ihre Anzahl,
- Identitäten und Beziehungen,
- zentrale Requisiten,
- Besitzwechsel,
- Ursache-Wirkungs-Reihenfolge,
- Start- und Endzustand,
- Dialogsprecher,
- Orte und räumliche Beziehungen,
- gewünschte und verbotene Änderungen.

Der Story Contract verhindert, dass ein Optimierer aus einer klaren Geschichte eine „kreativere“, aber falsche macht.

### 5.2 Asset Contract: Was liefert jedes Asset – und was nicht?

Für jedes verwendete Asset brauchst du:

```text
Asset → Aufgabe → erlaubte Merkmale → ausdrücklich nicht übernehmen
```

Beispiel:

```text
@Image1 definiert Gesicht, Frisur und braune Schürze der Barista.
Den Hintergrund und die Personen im Hintergrund nicht übernehmen.

@Video1 liefert ausschließlich Handbewegung und Gießrhythmus.
Identität, Kleidung und Café aus dem Video nicht übernehmen.
```

### 5.3 State Machine: Was ist am Ende jedes Beats sichtbar wahr?

Seedance arbeitet stabiler, wenn Ereignisse als Zustandsänderungen geschrieben werden:

```text
Startzustand → eine Hauptänderung → überprüfbarer Endzustand
```

Statt:

```text
Die Verkäuferin packt das Produkt professionell ein.
```

besser:

```text
Zu Beginn liegt das offene Versandkarton flach vor der Verkäuferin.
Sie stellt genau eine Flasche hinein und faltet beide Seitenlaschen zu.
Am Ende steht der geschlossene Karton allein in der Tischmitte; ihre Hände berühren ihn nicht mehr.
```

---

## 6. Die offizielle Masterformel

BytePlus empfiehlt diese Reihenfolge:

```text
Subjekt
+ Handlung oder Ereignis
+ Szene und Umgebung
+ visueller Stil
+ Kamera oder Schnitt
+ Ton
```

Unnötige Teile dürfen entfallen. Die Reihenfolge ist kein starrer Parser, sondern eine Priorisierung.

### 6.1 Minimaler Ein-Shot-Prompt

```text
[Subjekt] führt [sichtbare Hauptaktion] in [Ort und Umgebung] aus.
Das Bild verwendet [Licht, Material, Farbe oder Stil].
Die Kamera [Shotgröße + Ziel + Bewegungsweg + Geschwindigkeit].
Zu hören sind [Dialog, Ambiente, Effekte oder Musik].
```

### 6.2 Produktionsprompt mit Referenzen

```text
【Generierungsziel】
[Videoart und Kernereignis].

【Referenzrollen】
@Image1 definiert [Subjekt] hinsichtlich [Aussehen/Kleidung/Struktur]. Nicht übernehmen: [irrelevante Elemente].
@Video1 definiert [Aktion/Kamera/Rhythmus]. Nicht übernehmen: [Identität/Szene/Kleidung].
@Audio1 definiert [Stimme/Dialog/Ambiente/Musik].

【Subjekte und Beziehungen】
[Eindeutige Identitäten, Anzahl, Besitz und räumliche Position].

【Ereignisablauf】
Start: [sichtbarer Zustand].
Hauptaktion: [kausale, filmische Aktion].
Ende: [prüfbarer Zustand].

【Konsistenz】
[Identität, Anzahl, Kleidung, Requisiten, Raumachse, Tonbeziehungen].
```

### 6.3 30-Sekunden-Struktur

```text
【Globaler Produktionsvertrag】
[Figuren, Ort, Stil, Kamera- und Tonlogik, die überall gelten].

【Stufe 1 – Ausgangslage】
Startzustand: ...
Hauptereignis: ...
Endzustand: ...

【Stufe 2 – Entwicklung】
Fortsetzung aus dem vorherigen Endzustand: ...
Hauptereignis: ...
Endzustand: ...

【Stufe 3 – Wendepunkt】
Auslöser: ...
Reaktion: ...
Endzustand: ...

【Stufe 4 – Abschluss】
Schlusshandlung: ...
Letztes Bild und Tonende: ...
```

---

## 7. Schritt 1: Genau einen Primärtask wählen

Ein Prompt sollte standardmäßig genau einen Primärtask haben:

1. **Generierung** – neues Video aus Text und optionalen Referenzen.
2. **Editing** – bestehendes Video gezielt verändern.
3. **Extension** – neue Zeit vor oder nach einem Video erzeugen.

First/Last Frame, Keyframes, Storyboard, Blockout, Audio und lange Dauer sind Module innerhalb dieser Tasks.

### 7.1 Entscheidungsbaum

```text
Soll ein vorhandenes Video innerhalb seiner Timeline verändert werden?
├─ Ja → Editing
└─ Nein
   Soll vor oder nach dem Video neue Zeit entstehen?
   ├─ Ja → Extension
   └─ Nein → Generierung mit optionaler Videoreferenz
```

### 7.2 Wann eine vermeintliche Bearbeitung keine Bearbeitung ist

Editing übernimmt das Seitenverhältnis und annähernd die Dauer des Mastervideos. Verlangt der Nutzer beispielsweise aus einem 16:9-Clip ein neues 9:16-Video oder aus acht Sekunden zwanzig Sekunden ohne klare Extension-Richtung, ist das technisch eher **Referenzgenerierung**.

Dann darf das Video Inhalt, Aktion, Kamera und Ton referenzieren, ist aber nicht mehr der timeline-lockende Editing-Master.

### 7.3 Kombinierte Operationen aufteilen

„Ersetze die Jacke und verlängere danach die Szene“ sind zwei Operationen:

1. Video editieren.
2. Das Ergebnis als neuen Master verlängern.

Zwei getrennte Prompts sind stabiler als ein Hybridprompt, dessen Tasktyp unklar ist.

---

## 8. Schritt 2: Parameter aus dem Prompt heraushalten

Die offizielle Optimierungslogik trennt Inhalt und technische Einstellungen.

### In UI/API einstellen

- Seitenverhältnis,
- Gesamtdauer,
- Auflösung,
- Ausgabeformat,
- Audio an/aus,
- Wasserzeichen,
- Rückgabe des letzten Frames.

### Im Prompt beschreiben

- Ereignisreihenfolge,
- Zeitbudgets einzelner Beats,
- Shotstruktur,
- sichtbare Zustände,
- Kameraweg,
- Toninhalt,
- Referenzrollen,
- Konsistenz.

Falsch:

```text
Erzeuge ein 30-Sekunden-Video in 16:9, 1080p, 24 fps.
```

Besser:

```text
Die Geschichte besteht aus vier kausal verbundenen Stufen mit einem klar gehaltenen Schlussbild.
```

Die technischen Werte gehören daneben in die Oberfläche.

---

## 9. Schritt 3: Referenzassets wie ein Produktionsarchiv organisieren

### 9.1 Harte Limits

| Asset | ModelArk-Limit |
|---|---:|
| Bilder | 1–30 |
| Videos | bis 10; zusammen maximal 30 s |
| Audio | bis 10; zusammen maximal 30 s |
| Summe | maximal 50 Assets |

### 9.2 Stabilitätsbereiche

| Fall | Empfohlener Bereich | Erweitert testbar |
|---|---:|---:|
| Subjekte in Bildreferenzen | 1–8 | 9–12, mehr Wiederholungen nötig |
| Subjekte in Audio-/Videoreferenzen | 1–5 | 6–10, Stabilität sinkt |
| Länge einer Subjektvideo-Referenz | 5–10 s | länger möglich, aber weniger stabil |
| Editing-Master | unter 20 s | bis 30 s zulässig |
| Zusatzbilder beim Editing | 1–5 | 6–8, Stabilität sinkt |
| Storyboard-Grid | höchstens 15 Panels | mehr Panels können Reihenfolgefehler erzeugen |

### 9.3 Anzahl ist kein Qualitätswert

Fünfzig Assets sind ein Kapazitätslimit, kein Ziel. Jede zusätzliche Referenz kann Konflikte einführen. Verwende nur Assets, die eine eindeutige Produktionsaufgabe erfüllen.

### 9.4 Mappingreihenfolge

Die robuste Reihenfolge lautet:

```text
Assetrolle → Subjektzuordnung → Gruppierung → Subjektprofil → Aktivierung pro Szene
```

### 9.5 Niemals nur Range-Mapping

Schwach:

```text
Images 1–4 zeigen die vier Figuren.
```

Stark:

```text
Mira entspricht @Image1; übernimm Gesicht, kurzes schwarzes Haar und roten Mantel.
Jonas entspricht @Image2; übernimm Gesicht, Brille und graue Jacke.
Die Mechanikerin entspricht @Image3; übernimm Gesicht, Overall und Handschuhe.
Der Wachmann entspricht @Image4; übernimm Gesicht, Uniform und Mütze.
Die Identitäten, Kleidungen, Positionen und Dialoge dürfen nicht vertauscht werden.
```

### 9.6 Mehrere Ansichten desselben Subjekts

```text
@Image1 definiert die Vorderansicht desselben Motorrads.
@Image2 definiert die linke Seite desselben Motorrads.
@Image3 definiert Heck und Auspuff desselben Motorrads.
Alle drei Bilder definieren genau ein Motorrad; es darf nicht vervielfacht werden.
```

### 9.7 Nicht verwendete Assets bewusst deaktivieren

Wenn die vollständige Assetliste bekannt ist, kann ein Block helfen:

```text
【Nicht verwendete Assets】
@Image7 und @Image8 werden nicht für Figuren, Szene, Requisiten oder Stil verwendet.
@Audio3 wird nicht für Dialog, Stimme, Ambiente, Effekte oder Musik verwendet.
```

Das ist besonders nützlich, wenn eine Oberfläche alle Uploads im Projektkontext behält.

---

## 10. Schritt 4: Subjekte, Anzahl und Beziehungen fixieren

### 10.1 Stabile Namen

Verwende dieselbe Bezeichnung durchgehend. Wechsel nicht zwischen „Frau“, „Kundin“, „sie“ und „Protagonistin“, wenn mehrere Menschen im Bild sind.

### 10.2 Cardinality Lock

Schreibe Mengen dort, wo Duplikation teuer wäre:

```text
Es gibt während des gesamten Videos genau eine grüne Flasche und genau zwei Figuren.
```

### 10.3 Besitzwechsel explizit beenden

```text
Nach der Übergabe hält nur der Kunde die Tasse. Beide Hände der Barista haben die Tasse vollständig losgelassen.
```

### 10.4 Räumliche Beziehungen an feste Objekte binden

„Links“ und „rechts“ können sich mit der Kamera ändern. Stabiler:

```text
Die Verkäuferin steht auf der Innenseite der Glasvitrine und blickt zum Eingang.
Der Kunde steht auf der Außenseite der Vitrine ihr gegenüber.
```

### 10.5 Storyfakten nicht aus Bildern halluzinieren

Ein Bild zeigt sichtbare Merkmale, aber nicht automatisch Beruf, Alter, Verwandtschaft oder Motivation. Namen und Beziehungen kommen aus dem Briefing; Assets ergänzen nur sicht- oder hörbare Eigenschaften.

---

## 11. Schritt 5: Handlung als Kausal- und Zustandskette schreiben

### 11.1 Aktionsformel

```text
Auslöser + Handelnder + sichtbare Aktion + betroffenes Objekt + physische Folge + Endzustand
```

### 11.2 Ursache vor Reaktion zeigen

Wenn eine Figur erschrickt, muss der Zuschauer zuerst den Auslöser verstehen.

```text
Die Tür hinter ihr schlägt zu. Erst danach stoppt ihre Hand, ihr Blick springt zur Tür und ihre Schultern spannen sich an.
```

### 11.3 Innere Zustände externalisieren

Schwach:

```text
Er ist enttäuscht.
```

Stark:

```text
Nachdem er den Rücksendestempel erkennt, stoppt sein Daumen auf dem Umschlag. Sein Blick sinkt, der Mundwinkel verliert die angedeutete Spannung, und er legt den Brief langsam mit der Schrift nach unten.
```

### 11.4 Ein Hauptzustandswechsel pro Stufe

Eine Stufe darf Nebenbewegungen enthalten, sollte aber nur eine zentrale Veränderung haben. Das macht Fehler lokalisierbar.

### 11.5 Produkte und Prozesse

Übersetze abstrakte Vorteile in sichtbare Abläufe:

```text
Ausgangszustand → eine konkrete Bedienhandlung → sichtbares Ergebnis
```

„intelligenter Luftreiniger“ wird beispielsweise zu:

```text
Die Anzeige steht zunächst auf rot. Die Nutzerin drückt einmal die Automatik-Taste. Der Lüfter beschleunigt, die Anzeige wechselt sichtbar von rot über gelb zu grün, und die Nutzerin nimmt die Hand wieder vom Gerät.
```

---

## 12. Schritt 6: Zeitplanung für Seedance 2.5

### 12.1 Standard: Stufen statt Sekunden

Für normale Erzählungen empfiehlt sich:

```text
Stufe 1: Startzustand → Hauptereignis → Endzustand
Stufe 2: Übernahme des Endzustands → Hauptereignis → Endzustand
Stufe 3: Abschluss → finales Bild
```

### 12.2 Wann Timestamps sinnvoll sind

Nutze Sekundenangaben für:

- klaren Eintritt oder Austritt,
- Besitzübergabe,
- Schnitt oder Transition,
- Musikakzent,
- einzelne Dialogzeile,
- lokale Editing-Zone.

### 12.3 Drei offizielle Formen

```text
Zeitbereich: 0–4 s: ...; 4–9 s: ...
Zeitpunkt: Bei Sekunde 5 füllt der rote Schirm das Bild und löst den Übergang aus.
Relativ: Drei Sekunden nach dem Knopfdruck erlischt das Raumlicht.
```

### 12.4 Regeln für Zeitbereiche

- ganzzahlige Sekunden verwenden;
- lückenlos und nicht überlappend schreiben;
- Ereignisdichte realistisch halten;
- keine Hochfrequenzbefehle wie „dreimal pro Sekunde“;
- Grenzen als ungefähres Budget verstehen;
- am Ende jedes Bereichs einen sichtbaren Zustand angeben.

### 12.5 Parameterdauer nicht rückwärts in Timestamps umrechnen

Wenn die Oberfläche 30 Sekunden vorgibt, erfinde nicht automatisch `0–8`, `8–18`, `18–30`. Teile nur dann numerisch, wenn die Geschichte echte Timinganforderungen besitzt. Sonst reichen Stufen.

---

## 13. Schritt 7: Kamera wie einen Weg beschreiben

### 13.1 Kameraformel

```text
Shotgröße + Zielsubjekt + Startposition + Bewegungsrichtung + Geschwindigkeit + Zielposition
```

Beispiel:

```text
Mittlere Einstellung auf die Restauratorin. Die Kamera startet frontal auf Tischhöhe, fährt langsam seitlich nach rechts und endet in einer nahen Dreiviertelansicht ihrer Hände am Objekt.
```

### 13.2 Direkt verständliche Begriffe

**Shotgrößen:** Extreme Wide, Wide, Medium, Medium Close-up, Close-up, Extreme Close-up.

**Bewegungen:** Push-in, Pull-out, Pan, Seitfahrt, Follow, Orbit, Dive, Tilt-up, Handheld.

**Perspektiven:** Low Angle, Overhead, First Person, Luftperspektive.

**Beliebte Techniken:** One Take, Dolly Zoom, FPV, Bullet Time, Speed Ramp.

### 13.3 Fachwort plus sichtbares Ergebnis

Bei spezialisierten Begriffen schreibe beides:

```text
Rack Focus: Zunächst ist die Teetasse im Vordergrund scharf und die Figur unscharf. Der Fokus wandert gleichmäßig zur Figur; am Ende ist ihr Gesicht scharf und die Tasse weich verschwommen.
```

### 13.4 One Take richtig prompten

„One Take“ allein reicht nicht. Definiere, was die Kamera nacheinander passiert:

```text
Ein kontinuierlicher Gimbal-Shot. Die Kamera beginnt hinter der halb geöffneten Tür, folgt der Sängerin durch den Korridor, weicht einem Bühnenarbeiter aus, umrundet sie beim Betreten der Bühne und endet hinter ihr mit Blick auf das Publikum. Keine Schnitte.
```

### 13.5 Handheld dosieren

```text
Leichte natürliche Handheld-Bewegung, die der Schulterbewegung der gehenden Figur folgt; kein starkes Zittern.
```

### 13.6 Übergänge brauchen Auslöser und Zielzustand

```text
Bei Sekunde 6 schwenkt die Kamera schnell nach links. Eine dunkle Säule füllt das Bild vollständig. Während der Verdeckung wechselt die Szene; die Bewegung endet in derselben Richtung auf einer nächtlichen Straße.
```

---

## 14. Schritt 8: Licht, Farbe, Material und Stil

### 14.1 Szene zuerst physisch definieren

Nenne nur Details, die Handlung oder Komposition beeinflussen:

- Bodenbeschaffenheit,
- Engstellen und Wege,
- Fenster und Lichtquellen,
- bewegliche Objekte,
- Wetter und Partikel,
- feste Orientierungspunkte.

### 14.2 Lichtformel

```text
Quelle + Richtung + Härte + Farbtemperatur + betroffene Flächen + zeitliche Änderung
```

Beispiel:

```text
Weiches warmes Seitenlicht fällt durch das linke Fenster. Es zeichnet eine schmale Kontur auf Gesicht und Messinggehäuse; der hintere Raum bleibt neutral und leicht unterbelichtet.
```

### 14.3 Stil nicht gegen Referenzen kämpfen lassen

Wenn eine Referenz realistisch ist und der Prompt „flache 2D-Animegrafik“ verlangt, benenne die Transformation ausdrücklich:

```text
Übernimm aus @Image1 nur Gesichtszüge und Kleidung; rendere beides vollständig als handgezeichnete 2D-Cel-Animation. Fotorealistische Haut- und Stofftextur nicht übernehmen.
```

### 14.4 Qualitätswörter sind nachrangig

„cinematic“, „high quality“ und „8K“ ersetzen keine konkrete Regie. Priorität:

1. Task,
2. Subjekt,
3. Zustand und Aktion,
4. Referenzrollen,
5. Kamera,
6. Licht/Stil,
7. allgemeine Qualitätsbegriffe.

---

## 15. Schritt 9: Audio, Dialog und sichtbarer Text

### 15.1 Natürliche Sprache ist ausreichend

Die offizielle Dokumentation erlaubt normalen Fließtext. Symbole sind optional und helfen bei komplexem Audio:

| Inhalt | Syntax |
|---|---|
| Musik | `( ... )` |
| Soundeffekt | `< ... >` |
| Dialog | `{ ... }` |
| Untertitel/Text | `【 ... 】` beziehungsweise providerabhängig `〖 ... 〗` |

Wichtig ist die eindeutige Funktion, nicht die konkrete Klammerform.

### 15.2 Dialogformel

```text
Sprache + optionaler Akzent + Sprechweise + Sprecher + exakter Dialog
```

```text
Die Mechanikerin sagt ruhig auf natürlichem britischem Englisch: {The pressure is stable now.}
```

### 15.3 Mehrere Sprecher binden

```text
Mira spricht; Jonas hört zu und hält den Mund natürlich geschlossen.
Danach spricht Jonas; Mira reagiert nur mit Blick und Atmung.
```

### 15.4 Nicht mehr Dialog erfinden als vorgegeben

Wenn nur ein kurzer Satz geliefert wurde, erweitere ihn nicht zu einer Rede. Emotion kann über Tonfall und sichtbare Reaktion ergänzt werden.

### 15.5 Tonspuren separat benennen

```text
Dialog: ...
Ambiente: leise Lüftung und entfernte Schritte.
Effekte: Metallklick beim Schließen des Gehäuses.
Musik: keine.
```

### 15.6 Negative Audiokontrolle

Offiziell unterstützt sind unter anderem:

```text
Keine Hintergrundmusik; nur Raumton und Aktionsgeräusche.
Kein Dialog und keine Erzählstimme.
Kein Audio.
Keine Untertitel.
```

### 15.7 Mono-/Stereo-Widerspruch

Die aktuelle ModelArk-API dokumentiert generiertes Audio als Mono. CapCut bewirbt in seiner Produktoberfläche Stereo-Audio. Behandle das als Plattformunterschied und prüfe die tatsächliche Datei, statt Stereo allein durch Prompttext zu erwarten.

### 15.8 Exakter Text bleibt riskant

Kurze, häufige Wörter können funktionieren. Für Logos, juristische Angaben, Formeln, Produktwerte oder typografisch exakte Claims ist ein vorbereiteter Grafik-/Keyframe-Asset oder Postproduktion sicherer.

---

## 16. Text-to-Video-Template

```text
【Ziel】
Erzeuge [Videoart] über [Kernereignis].

【Subjekte und Ausgangslage】
[Identität, Anzahl, Kleidung, wichtige Requisiten, Startposition].

【Ereignisablauf】
Stufe 1: [Startzustand → eine Änderung → Endzustand].
Stufe 2: [Übernahme → eine Änderung → Endzustand].
Stufe 3: [Abschluss und finales Bild].

【Bild und Kamera】
[Szene, Licht, Material, Stil].
[Kameraweg pro Stufe].

【Ton】
[Dialog, Ambiente, Effekte, Musik].

【Konsistenz】
[Identität, Anzahl, Raumachse, Requisiten, Stil].
```

### Beispiel

```text
【Ziel】
Erzeuge eine ruhige dokumentarische Miniatur über eine Uhrmacherin, die eine Taschenuhr wieder in Gang setzt.

【Subjekte und Ausgangslage】
Eine Uhrmacherin sitzt allein an einem Holztisch. Vor ihr liegen genau eine geöffnete Taschenuhr, eine Pinzette und ein kleines Zahnrad.

【Ereignisablauf】
Stufe 1: Sie untersucht das stillstehende Werk und nimmt das einzelne Zahnrad mit der Pinzette auf. Am Ende befindet es sich über der freien Achse.
Stufe 2: Sie setzt das Zahnrad ein, drückt es vorsichtig fest und zieht die Pinzette zurück. Das Werk beginnt gleichmäßig zu laufen.
Stufe 3: Sie schließt den Deckel, legt die Uhr in die Tischmitte und hört einen Moment auf das Ticken. Am Ende berührt keine Hand die Uhr.

【Bild und Kamera】
Warme Werkstatt am frühen Morgen, weiches Seitenlicht von links, sichtbare Messingtextur und geringe Tiefenschärfe. Beginne in einer mittleren Einstellung, fahre langsam zu den Händen und ende in einer Makroaufnahme des laufenden Werks.

【Ton】
Nur Raumton, Pinzettenklick und das allmählich einsetzende Ticken; keine Musik und keine Sprache.
```

---

## 17. Multimodale Referenzgenerierung

```text
【Generierungsziel】
Erzeuge [neues Video].

【Figuren】
[Name] entspricht @Image1. Übernimm nur [Aussehen/Kleidung].
[Name] entspricht @Image2. Übernimm nur [Aussehen/Kleidung].
Identitäten und Dialoge nicht vertauschen.

【Requisiten】
[Objekt] entspricht @Image3 und gehört ausschließlich [Figur].

【Szene】
@Image4 liefert Raumaufteilung, Materialien und Licht. Personen darin nicht übernehmen.

【Aktion und Kamera】
@Video1 liefert [Aktion] und [Kamerarhythmus]. Personen, Kleidung und Ort nicht übernehmen.

【Ton】
@Audio1 liefert die Stimme von [Figur].

【Ablauf】
[Start, Handlung, Endzustände].
```

### Referenzvideo nicht unnötig nacherzählen

Wenn Video 1 die Bewegung bereits exakt zeigt:

```text
Übernimm streng die Handlungsreihenfolge und Kamerabewegung aus @Video1.
```

Dann nur noch beschreiben, **wer**, **wo** und **in welchem Stil** diese Struktur ausführt. Eine zweite, abweichende Bewegungsbeschreibung erzeugt Konflikte.

---

## 18. First Frame, Last Frame und Keyframes

### 18.1 Dedizierter First-Frame-Modus

Der First Frame sperrt das Seitenverhältnis. Schreibe die Rolle separat und eindeutig:

```text
Use @Image1 as the first frame.
Dieser Frame definiert Startkomposition, Positionen, Posen, Requisitenzustand, Szene und Kamerarichtung.

Danach [kontinuierliche Aktion].
```

### 18.2 First und Last Frame

```text
Use @Image1 as the first frame.
@Image1 definiert Startkomposition, Positionen, Posen, Requisiten und Kamerarichtung.

Use @Image2 as the last frame.
@Image2 definiert Endkomposition, Positionen, Posen, Requisiten und Kamerarichtung.

@Image3 definiert das Aussehen der Hauptfigur, ohne die Kompositionen von @Image1 oder @Image2 zu überschreiben.

Die Handlung beginnt natürlich im Zustand von @Image1, durchläuft [kontinuierliche Aktion] und erreicht ohne Sprung den Zustand von @Image2.
Identität, Requisitenstruktur, Besitz, Szene und Kameraachse bleiben durchgehend konsistent.
```

First und Last Frame sollten dasselbe Seitenverhältnis haben. Andernfalls kann der letzte Frame gestreckt werden.

### 18.3 Semantische First/Last-Referenz

Mit `reference_image` kann ein Prompt ein Bild als Anfang oder Ende bezeichnen, ohne den dedizierten Rollenparameter zu verwenden. Das ist flexibler, aber weniger strikt. Verwende die dedizierten Rollen, wenn die Randbilder wirklich fix sein müssen.

### 18.4 Multi-Keyframe-Sequenz

```text
Use @Image1 through @Image5 as keyframes in that order.

@Image1 definiert den Startzustand: ...
@Image2 definiert den Zustand nach Stufe 1: ...
@Image3 definiert den Wendepunkt: ...
@Image4 definiert den Zustand nach Stufe 3: ...
@Image5 definiert das Schlussbild: ...

Die Handlung erreicht diese Zustände in der genannten Reihenfolge durch kontinuierliche Übergänge. Die Keyframes sind semantische Anker und keine Aufforderung zum statischen Halten oder zur pixelgenauen Zwischenbildkopie.
```

---

## 19. Storyboard-Grids

Ein Storyboard-Grid steuert Shotfolge und ungefähre Komposition, nicht jedes Pixel.

### 19.1 Vorbereitung

- höchstens 15 Panels bevorzugen;
- klare Leserichtung;
- einfache Line-Art oder Strichzeichnungen;
- wenig Text;
- keine überschärften, verrauschten KI-Bilder;
- keine widersprüchlichen Achsen und Aktionen.

### 19.2 Template

```text
@Image1 liefert Shotreihenfolge und ungefähre Kompositionen eines 8-Panel-Storyboards.
Lies von links nach rechts und oben nach unten.
Skizzenstil, Pfeile, Beschriftungen und Platzhalterfiguren nicht übernehmen.

@Image2 definiert Aussehen und Kleidung der Hauptfigur.
@Image3 definiert Struktur und Material des Produkts.

Shot 1: [Shotgröße, Startzustand, Aktion].
Shot 2: [Aktion, Kamera oder Übergang].
...
Shot 8: [Schlusshandlung und finales Bild].

Die finale Bildsprache ist [Stil]. Zu hören sind [Ton].
```

### 19.3 Wann einzelne Keyframes besser sind

Wenn bestimmte Zustände streng getroffen werden müssen, lade die Panels einzeln als Keyframes hoch. Ein Grid bleibt bewusst interpretierbarer.

---

## 20. Blockout-/Clay-Render-Referenzen

### 20.1 Grobes Blockout

Ein grobes Blockout liefert Bewegungs- und Raumstruktur, nicht das finale Design.

```text
@Video1 ist ein grobes Blockout.
Übernimm ausschließlich Bewegungswege, Blocking, Eintritt/Austritt, Kameraposition, Kamerabewegung, Schnitte und Lichtwechsel.
Graue Geometrie, Materialien, leeren Hintergrund, Achsen, Pfadlinien und Produktionsmarker nicht übernehmen.

Der hohe Zylinder in @Video1 entspricht [Figur A].
Der niedrige Quader entspricht [Requisite].
@Image1 definiert Aussehen und Kleidung von [Figur A].
@Image2 definiert Struktur und Material der Requisite.
@Image3 definiert Szene, Material und Licht.

[Finale Handlung].
```

### 20.2 Feines Blockout

Ein feines Blockout hat bereits brauchbare Geometrie und dient eher dem Re-Rendering.

```text
@Video1 ist ein feines Blockout.
Bewahre Struktur, räumliche Anordnung, Aktionen, Kameraposition, Kamerabewegung und Schnitte.
Originale graue Materialien, leeren Hintergrund und Produktionsmarker nicht übernehmen.

@Image1 definiert das gebürstete Messing der Außenstruktur.
@Image2 definiert die transluzenten blauen Glasflächen.
@Image3 definiert Galerie, Licht und Farbstimmung.

Rendere die vorhandene Struktur als [finales Objekt] in [finaler Szene].
```

### 20.3 Blockout ist Referenzgenerierung, nicht automatisch Editing

Das Blockout liefert Struktur und Zeitinformation. Es ist normalerweise kein „Mastervideo“, dessen Pixel erhalten werden sollen.

---

## 21. Video-Editing

Editing verlangt einen einzigen Master und einen geschlossenen Änderungsumfang.

### 21.1 Parameterregeln

- `ratio: adaptive`
- `duration: -1`
- Editing-Video 4–30 Sekunden
- Output übernimmt das Seitenverhältnis
- Output bleibt annähernd gleich lang; durch Frameverarbeitung kann er leicht kürzer sein
- MOV als Input und Output ist für Farbkonsistenz empfehlenswert

### 21.2 Master-Template

```text
【Editing-Ziel】
Editiere @Video1. Verändere ausschließlich [Objekt/Region/Ton] zu [Ziel].

【Mastervideo】
@Video1 ist der einzige Editing-Master und bestimmt Originalszene, Figuren, Aktionen, Komposition, Kamera, Verdeckungen, Ton und Ereignisreihenfolge.

【Zielmaterial】
@Image1 definiert [Aussehen/Struktur/Material] des Zielobjekts. Hintergrund und andere Elemente des Bildes nicht übernehmen.

【Umfang】
Ändere nur [genauer Bereich/Objekt/Zeitbereich]. Die Anzahl des Zielobjekts beträgt durchgehend [N].

【Timeline-Vererbung】
Das Zielobjekt übernimmt Auftreten, Bewegung, Geschwindigkeit, Pfad, Verdeckung und Austritt des Originalobjekts.

【Bewahren】
Außer den ausdrücklich geänderten Elementen bleiben alle anderen sichtbaren Figuren, Requisiten, Hintergründe, Aktionen, Kamerabewegungen, Schnitte und Töne aus @Video1 unverändert.
```

### 21.3 Dynamisches Objekt ersetzen

```text
Entferne nur den roten Lieferwagen und ersetze ihn durch den weißen Elektrotransporter aus @Image1. Der Elektrotransporter übernimmt exakt den Bewegungsslot des roten Lieferwagens: Auftretenszeit, Weg, Geschwindigkeit, Verdeckungen und Ausfahrt. Der rote Lieferwagen darf im Ergebnis nicht mehr erscheinen. Alle übrigen Elemente bleiben unverändert.
```

### 21.4 Hintergrund ersetzen

```text
Editiere @Video1. Ersetze ausschließlich den Green-Screen-Bereich außerhalb der Kontur der Hauptfigur durch die regennasse Nachtstraße aus @Image1. Figur, Kleidung, Gesicht, Körperbewegung, Haarbewegung und Kamerabewegung bleiben erhalten. Passe nur Lichtreflexe und Windwirkung physikalisch an die neue Umgebung an.
```

### 21.5 Perspektive oder Kamera ändern

```text
Editiere @Video1. Figuren, Aktionen, Szene, Licht, Ton und Ereignisreihenfolge bleiben unverändert. Ändere ausschließlich die Kamerabewegung: [zeitlich gegliederter neuer Kameraweg].
```

### 21.6 Lokale Änderung per Timestamp

```text
Editiere @Video1. Ändere nur zwischen 4 und 7 Sekunden das kalte blaue Wandlicht rechts in warmes orangefarbenes Licht. Die Haut darf physikalisch auf das neue Umgebungslicht reagieren. Alles außerhalb dieses Zeitbereichs sowie Identität, Kleidung, Position, Aktion, Kamera, Dialog und Raumton bleiben unverändert.
```

### 21.7 Scope Closure ist Pflicht

Jeder Editing-Prompt sollte enden mit einer Variante von:

```text
Außer den oben ausdrücklich veränderten Objekten bleiben alle anderen sichtbaren Figuren, Requisiten und Hintergründe unverändert und werden weder ersetzt noch entfernt.
```

Wenn nur bestimmte Objekte erhalten bleiben sollen:

```text
Außer den ausdrücklich beibehaltenen Objekten entferne alle anderen sichtbaren Subjekte; füge nichts Neues hinzu.
```

---

## 22. Audio-Editing

```text
【Editing-Ziel】
Editiere @Video1. Ändere ausschließlich [Dialog/Stimme/BGM/Ambiente/Effekt] in [Zeitbereich].

【Mastervideo】
@Video1 ist der einzige Master und bestimmt alle Bilder, Aktionen, Lippenbewegungszeiten, Shots, Schnittrhythmus und alle nicht geänderten Töne.

【Zielaudio】
@Audio1 liefert [Stimmfarbe/Dialog/Musik/Effekt] für [Sprecher/Tonkategorie].

【Umfang】
Ändere ausschließlich [genaue Tonspur].

【Bewahren】
Alle anderen Dialoge, Lippenbewegungen, Atmosphären, Aktionsgeräusche, Bilder, Shots und Schnittzeiten bleiben unverändert.
```

### BGM entfernen

```text
Editiere @Video1. Entferne ausschließlich die Hintergrundmusik. Bewahre Dialog, Lippenbewegungszeiten, Raumton, Schritte, Aktionsgeräusche und sämtliche Bildinformationen unverändert.
```

### Dialog übersetzen

```text
Editiere @Video1. Übersetze ausschließlich den gesprochenen Dialog in natürliches Deutsch und passe die Lippenbewegungen an den übersetzten Text an. Keine Untertitel. Alle Bilder, Aktionen, Kamerabewegungen, Schnitte, Ambiente und Effekte bleiben unverändert.
```

---

## 23. Video-Extension

Extension erzeugt nur den neuen Abschnitt. Das Quellvideo wird nicht gleichzeitig editiert.

### 23.1 Vorwärts verlängern

```text
@Video1 ist das Quellvideo für die Vorwärts-Extension.

Extend @Video1 forward.
Der erste Frame des neuen Abschnitts setzt direkt am letzten Frame von @Video1 an. Bewahre Haltung und Orientierung der Figur, Requisitenpositionen, Hintergrund, räumliche Beziehungen, Kamera, Komposition, Licht, Audiozustand und Bewegungsrichtung.

Danach [neue Handlung].

Die Figur bleibt dieselbe kontinuierliche Instanz; keine Duplikation oder Aufspaltung. Körperstruktur, Anzahl der Teile, Kleidung, Requisiten und Raumachse bleiben stabil.
```

### 23.2 Rückwärts verlängern

```text
@Video1 ist das Quellvideo für die Rückwärts-Extension.

Extend @Video1 backward.
Vor dem Beginn des Quellvideos geschieht [vorherige Handlung].

Der letzte Frame des neuen Abschnitts erreicht exakt den sichtbaren Startzustand von @Video1: [Pose, Orientierung, Requisiten, Positionen, Kamera, Licht, Ton und Bewegungsrichtung].

Figuren, Requisiten oder Effekte, die erst später im Quellvideo erscheinen, dürfen im neuen Vorlauf nicht vorzeitig auftauchen.
```

### 23.3 Boundary Checklist

Prüfe am Anschluss:

- Pose und Blickrichtung,
- Position und Besitz von Requisiten,
- Hintergrundgeometrie,
- Kameraachse und Bewegungsvektor,
- Belichtung und Farbtemperatur,
- Wind/Partikel,
- Musikphase, Ambiente und Lautstärke,
- Bewegungsimpuls.

### 23.4 MOV für Continuity

BytePlus empfiehlt für Editing und Extension möglichst MOV als Input und Output. Das reduziert Farb-, Helligkeits- und Audioabweichungen, garantiert aber keine unsichtbare Naht.

---

## 24. Nahtloser Übergang zwischen zwei Videos

```text
@Video1 ist der Clip vor dem Übergang und liefert dessen Endsubjekt, Bewegung, Komposition, Kamerarichtung und Ton.
@Video2 ist der Clip nach dem Übergang und liefert dessen Startsubjekt, Komposition, Kamerarichtung und Ton.

Am Ende von @Video1 löst [Subjekt/Objekt] den Übergang durch [Aktion] aus.
Die Kamera [Richtung und Geschwindigkeit]. Währenddessen verwandelt sich [Form/Material/Licht/Raum] kontinuierlich in [korrespondierendes Element aus @Video2].
Der Übergang endet natürlich in der Startkomposition von @Video2; Subjektposition, Kamerarichtung und Bewegungsimpuls bleiben anschlussfähig.
Der Ton wechselt gleichmäßig von [Ton 1] zu [Ton 2].
```

Gute Trigger:

- Vollbildverdeckung,
- Objektmorph,
- Drehung einer Figur,
- Dive oder Reverse Move,
- Push/Pull mit Fokuswechsel,
- identische geometrische Form.

Eine generierte Brücke ist keine pixelidentische Schnittoperation. Beide Quellbereiche müssen anschließend kontrolliert werden.

---

## 25. One-Click-Video aus mehreren Bildern

```text
【Assetrollen】
@Image1: Eröffnungsort.
@Image2: Hauptfigur beim ersten Ereignis.
@Image3: Produktdetail.
@Image4: Gruppenszene.
@Image5: Schlussbild.
@Video1: nur Schnittrhythmus und Übergangsstil; Personen und Orte nicht übernehmen.

【Reihenfolge】
Zeige @Image1 bis @Image5 in dieser Reihenfolge und bilde [Geschichtsbogen].

【Bildbewegung】
Umgebungsbilder: langsamer Push-in und subtile Parallaxe.
Figurenbilder: nur Blinzeln, leichte Kopfdrehung und minimale Kleidungsbewegung.
Produktstruktur und vorhandener Text bleiben stabil.

【Montage】
[Schnittrhythmus, Übergänge, Farbe, Grafikbehandlung].

【Ton】
[Ambiente, Effekte, Musik].
```

Schreibe nicht nur „mach daraus ein Video“. Materialrollen, Reihenfolge, Bewegungsmenge, Montagerhythmus und Ton müssen beschrieben sein.

---

## 26. Dialog- und Schauspielführung

### 26.1 Emotionsformel

```text
emotionale Richtung + Auslöser + unmittelbare Reaktion + sichtbare Entwicklung + Endverhalten
```

### 26.2 Beispiel

```text
Die Emotion wechselt von zurückgehaltener Hoffnung zu kontrollierter Enttäuschung. Nachdem die Kellnerin den ungeöffnet zurückgesandten Brief auf den Tisch legt, stoppt die Hand der Frau. Ihr Blick fällt auf den Stempel, die Lippen entspannen sich, und sie atmet langsam ein. Schließlich dreht sie den Brief um, richtet die Schultern auf und sagt leise: {Ich verstehe.}
```

### 26.3 Zwei bis vier Signale reichen oft

Nutze Augen, Brauen, Mund, Atmung, Blickrichtung, Hände und Körperhaltung. Zu viele Mikroexpressionen in derselben Sekunde können konkurrieren.

### 26.4 Sprecherbuch führen

Für jeden Beat intern prüfen:

- Wer spricht?
- Exakter Text?
- Welche Sprache?
- Welche Stimme/Audio-Referenz?
- On- oder off-screen?
- Was machen die anderen Münder?

---

## 27. Negativanweisungen: gezielt statt generisch

Der offizielle 2.5-Workflow rät dazu, keine pauschalen „Quality Packs“ anzuhängen, die der Nutzer gar nicht braucht.

### Sinnvoll

```text
Keine Untertitel.
Keine Hintergrundmusik; nur Raumton.
Keine zweite Flasche.
Das Originalobjekt darf nach der Ersetzung nicht mehr erscheinen.
Pfeile und Beschriftungen aus dem Storyboard nicht übernehmen.
```

### Weniger sinnvoll

```text
masterpiece, best quality, no errors, no artifacts, no bad hands, no duplicates, no watermark, 8K
```

Negative Anweisungen funktionieren am besten, wenn sie einen konkreten, plausiblen Fehler des aktuellen Tasks verhindern.

---

## 28. API-Bedienung mit BytePlus ModelArk

### 28.1 Minimales Text-to-Video-Beispiel

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A documentary-style scene of a watchmaker repairing one pocket watch..."
    }
  ],
  "generate_audio": true,
  "resolution": "720p",
  "ratio": "16:9",
  "duration": 12,
  "output_format": "mp4",
  "watermark": false
}
```

### 28.2 Referenzgenerierung

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "omni_reference_task_type": "reference",
  "content": [
    {
      "type": "text",
      "text": "@Image1 defines the character. @Video1 defines only the camera movement..."
    },
    {
      "type": "image_url",
      "image_url": { "url": "https://example.com/character.png" },
      "role": "reference_image"
    },
    {
      "type": "video_url",
      "video_url": { "url": "https://example.com/camera.mov" },
      "role": "reference_video"
    }
  ],
  "generate_audio": true,
  "resolution": "720p",
  "ratio": "16:9",
  "duration": 15,
  "output_format": "mp4"
}
```

### 28.3 Editing

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "omni_reference_task_type": "edit",
  "content": [
    {
      "type": "text",
      "text": "Edit @Video1. Replace only the red cup with the blue cup from @Image1..."
    },
    {
      "type": "video_url",
      "video_url": { "url": "https://example.com/master.mov" },
      "role": "reference_video"
    },
    {
      "type": "image_url",
      "image_url": { "url": "https://example.com/blue-cup.png" },
      "role": "reference_image"
    }
  ],
  "generate_audio": true,
  "resolution": "720p",
  "ratio": "adaptive",
  "duration": -1,
  "output_format": "mov"
}
```

### 28.4 Extension

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "omni_reference_task_type": "extend",
  "content": [
    {
      "type": "text",
      "text": "Extend @Video1 forward. Continue directly from its last frame..."
    },
    {
      "type": "video_url",
      "video_url": { "url": "https://example.com/source.mov" },
      "role": "reference_video"
    }
  ],
  "generate_audio": true,
  "resolution": "720p",
  "ratio": "adaptive",
  "duration": 10,
  "output_format": "mov"
}
```

### 28.5 `omni_reference_task_type`

| Wert | Bedeutung |
|---|---|
| `auto` | Modell bestimmt Reference, Edit oder Extend aus Prompt und Assets |
| `reference` | neues Video aus semantischen Referenzen |
| `edit` | bestehende Timeline gezielt bearbeiten |
| `extend` | neue Zeit vor oder nach dem Video |

Der Parameter ersetzt keinen klaren Prompt. Wenn Parameter und Promptabsicht widersprechen, kann `InvalidParameter.TaskTypeMismatch` entstehen.

### 28.6 ModelArk-Parameterregeln

| Task | Ratio | Duration |
|---|---|---|
| Text-/Referenzgenerierung | festes Verhältnis oder `adaptive` | 4–30 oder `-1` |
| Editing | nur `adaptive` | nur `-1` |
| Extension | nur `adaptive` | 4–30 oder `-1` |
| First/Last Frame | nur `adaptive` | 4–30 oder `-1` |

### 28.7 `seed`

Die aktuelle ModelArk-API führt den Seed-Parameter nicht als unterstützt für Seedance 2.5. Drittanbieter wie Replicate können einen Wrapper-Seed anbieten. Selbst dort ist identische Ausgabe nicht garantiert.

### 28.8 Promptlänge

Die API empfiehlt höchstens:

- 500 chinesische Zeichen oder
- 1.000 englische Wörter.

Das ist eine Obergrenze, kein Qualitätsziel. Je länger der Prompt, desto eher verteilt sich Aufmerksamkeit und Details werden ausgelassen.

### 28.9 Offiziell gelistete Sprachen

Seedance 2.5 unterstützt bei BytePlus ausdrücklich:

- Chinesisch,
- Englisch,
- Spanisch,
- Indonesisch,
- Portugiesisch,
- Japanisch,
- Malaiisch,
- Thai,
- Arabisch,
- Vietnamesisch,
- Koreanisch.

Deutsch ist nicht ausdrücklich gelistet. Für maximale Prompttreue ist Englisch die sicherere Wahl; deutschsprachiger Dialog kann trotzdem explizit verlangt werden.

---

## 29. Eingabedateien bei ModelArk

### Bilder

- JPEG, PNG, WebP, BMP, TIFF, GIF, HEIC, HEIF
- Seitenverhältnis 0,4 bis 2,5
- Breite und Höhe 300–6.000 px
- unter 30 MB pro Bild
- Request Body höchstens 64 MB

### Videos

- MP4 oder MOV
- 480p bis 4K als Input
- 24–60 fps als Input
- 2–30 Sekunden für Referenzgenerierung
- 4–30 Sekunden für Editing
- höchstens 200 MB pro Video
- insgesamt höchstens 30 Sekunden Videoreferenz

### Audio

- WAV oder MP3
- 2–30 Sekunden pro Clip
- höchstens 15 MB pro Clip
- insgesamt höchstens 30 Sekunden

### Output

- 480p und 720p: 8-Bit
- 1080p: 10-Bit HEVC/H.265
- 24 fps
- MP4 oder MOV
- MOV verwendet einen professionelleren Farbabtastungs-/Audio-Workflow, ist aber nicht in jedem Browser direkt abspielbar

---

## 30. Ein professioneller Iterationsworkflow

### Pass 0: Produktionsvertrag

Schreibe noch keinen schönen Prompt. Kläre:

- Primärtask,
- Subjekte und Anzahl,
- Start- und Endzustand,
- unveränderliche Beziehungen,
- Assetrollen,
- technische Parameter außerhalb des Prompts.

### Pass 1: Minimaler Ereignisablauf

Nur Subjekt, Aktion, Szene und Endzustand. Teste, ob die Geschichte grundsätzlich funktioniert.

### Pass 2: Referenzbindung

Ordne jedem Asset genau eine Funktion zu und füge Ausschlüsse hinzu.

### Pass 3: Zeit und Kamera

Stufen oder notwendige Timestamps ergänzen. Pro Stufe einen klaren Kameraweg.

### Pass 4: Ton und Text

Sprecher, Sprache, Audioquellen, BGM, Effekte und Untertitel festlegen.

### Pass 5: Gezielte Constraints

Nur Fehler verhindern, die in diesem Task plausibel sind.

### Pass 6: Kontrollierte Variation

Mehrere Takes erzeugen. Pro Iteration möglichst nur eine Variable ändern:

- Handlung,
- Kamera,
- Referenzrolle,
- Licht/Stil,
- Timing oder
- Ton.

Wenn alles gleichzeitig geändert wird, ist nicht erkennbar, was geholfen hat.

### Pass 7: Edit statt Voll-Neugenerierung

Wenn 24 von 30 Sekunden funktionieren, editiere die fehlerhafte Zone oder ändere den Zustand, an dem der Fehler beginnt. Wiederhole nicht grundlos die gesamte Generation.

---

## 31. Fehlerdiagnose

### 31.1 Figurendrift

**Ursache:** unklare Zuordnung, konkurrierende Assets, zu viele Merkmale oder keine globale Identitätsdefinition.

**Reparatur:**

- eine eindeutige Zeile pro Figur;
- mehrere Ansichten ausdrücklich als dieselbe Figur binden;
- pro Szene nur benötigte Assets aktivieren;
- Identität, Kleidung und Stimme nicht über mehrere Figuren teilen.

### 31.2 Doppelte Figuren oder Objekte

**Ursache:** mehrere Ansichten werden als mehrere Instanzen interpretiert oder Besitzwechsel bleibt offen.

**Reparatur:**

```text
Alle drei Referenzbilder definieren dieselbe einzelne Figur.
Es gibt während des gesamten Videos genau eine Tasche.
Nach der Übergabe besitzt nur Figur B die Tasche.
```

### 31.3 Reihenfolge stimmt nicht

**Ursache:** Prosa ohne Zustände, Storyboard mit zu vielen Panels oder überfüllte Zeitfenster.

**Reparatur:**

- Stufen mit Endzuständen;
- Ursache vor Reaktion;
- Keyframes einzeln;
- weniger Ereignisse;
- Timestamps lückenlos.

### 31.4 Aktionen werden ausgelassen

**Ursache:** zu viele Hauptaktionen im selben Beat.

**Reparatur:** eine Hauptänderung pro Stufe, Nebenaktionen reduzieren, Zustandswechsel konkretisieren.

### 31.5 Kamera wird chaotisch

**Ursache:** mehrere Bewegungen ohne Ziel oder widersprüchliche Shotbegriffe.

**Reparatur:** Zielsubjekt, Start, Weg, Geschwindigkeit und Endposition definieren. Pro Beat eine dominante Kamerabewegung.

### 31.6 Referenzvideo kontaminiert Identität oder Szene

**Reparatur:** positive Rolle plus Ausschluss:

```text
@Video1 liefert nur Aktion und Kamera; Personen, Kleidung, Ort, Licht und Ton nicht übernehmen.
```

### 31.7 Editing verändert zu viel

**Ursache:** Master, Scope oder Preservation-Block fehlt.

**Reparatur:** genau ein Mastervideo; A→B-Änderung; Menge; Zeitbereich; Timeline-Vererbung; Scope Closure.

### 31.8 Editing wird als Referenzgenerierung klassifiziert

**Ursache:** Prompt sagt nur „referenziere Video 1“ oder Parameter widersprechen Editing.

**Reparatur:** klares Edit-Verb, `omni_reference_task_type: edit`, `ratio: adaptive`, `duration: -1`.

### 31.9 Referenzgenerierung wird fälschlich als Editing erkannt

**Ursache:** Wörter wie „ändere Video 1“, obwohl neues Verhältnis oder neue Dauer gewünscht ist.

**Reparatur:** als neues Video formulieren und Video 1 nur als Referenz für konkrete Dimensionen verwenden.

### 31.10 Extension springt an der Naht

**Ursache:** Boundary-Zustand unvollständig.

**Reparatur:** Pose, Requisiten, Kamera, Licht, Audio und Bewegungsimpuls am Rand explizit beschreiben; MOV verwenden.

### 31.11 Rückwärts-Extension verrät spätere Elemente

**Reparatur:** ausdrücklich festlegen, welche Figuren, Requisiten oder Effekte erst im Quellvideo beginnen und im Vorlauf nicht erscheinen dürfen.

### 31.12 Audio passt nicht

**Ursache:** Sprecher nicht gebunden, BGM und Ambiente vermischt oder Provider beschränkt Audio-only.

**Reparatur:** Sprecher pro Beat; getrennte Tonkategorien; Provider-Schema prüfen. ModelArk unterstützt Audio-only, manche Drittanbieter verlangen trotzdem Bild oder Video.

### 31.13 Text ist falsch

**Reparatur:** kürzere Texte, Text als Keyframe/Overlay vorbereiten oder nachträglich setzen. Prompt allein garantiert keine typografische Genauigkeit.

### 31.14 1080p funktioniert nicht

**Ursache:** Plattform unterstützt nur 720p oder Provider-Endpoint ist noch älter.

**Reparatur:** ModelArk-Endpoint prüfen; bei fal/LAS 720p verwenden; 4K/60 fps gegebenenfalls als Plattform-Nachbearbeitung behandeln.

### 31.15 Reale Gesichter werden abgelehnt

BytePlus ModelArk dokumentiert, dass direkte Uploads von Bildern oder Videos mit realen menschlichen Gesichtern nicht allgemein unterstützt werden. Verwende die dafür vorgesehenen Portrait-/Digital-Character-Workflows und notwendige Einwilligungen beziehungsweise Asset-Bibliotheken der Plattform.

---

## 32. Die Master-Checkliste vor dem Absenden

### Task

- [ ] Genau ein Primärtask: Generate, Edit oder Extend?
- [ ] Promptabsicht und API-Tasktyp stimmen überein?
- [ ] Keine verborgene zweite Operation?

### Story

- [ ] Alle Figuren und Objekte vorhanden?
- [ ] Mengen eindeutig?
- [ ] Ursache vor Wirkung?
- [ ] Besitzwechsel abgeschlossen?
- [ ] Start- und Endzustand sichtbar?

### Assets

- [ ] Jedes verwendete Asset hat eine Aufgabe?
- [ ] Jede Figur einzeln gemappt?
- [ ] Mehrfachansichten als dieselbe Instanz deklariert?
- [ ] Irrelevante Hintergründe/Personen ausgeschlossen?
- [ ] Nicht verwendete Assets deaktiviert?

### Zeit

- [ ] Stufen statt unnötiger Sekundenteilung?
- [ ] Timestamps ganzzahlig, lückenlos und nicht überlappend?
- [ ] Ereignisdichte realistisch?
- [ ] Ein Hauptzustandswechsel pro Stufe?

### Kamera

- [ ] Zielsubjekt genannt?
- [ ] Start, Richtung, Geschwindigkeit und Ende klar?
- [ ] Übergangsauslöser sichtbar?
- [ ] Fachwörter durch sichtbares Ergebnis präzisiert?

### Ton

- [ ] Sprecher, Sprache und exakter Text gebunden?
- [ ] Zuhörer halten den Mund geschlossen?
- [ ] Dialog, Ambiente, Effekte und Musik getrennt?
- [ ] Untertitelwunsch eindeutig?

### Editing/Extension

- [ ] Ein einziger Master?
- [ ] Änderungsumfang geschlossen?
- [ ] Zu bewahrende Elemente genannt?
- [ ] Ratio-/Duration-Locks eingehalten?
- [ ] Boundary-Zustand vollständig?

### Parameter

- [ ] Dauer, Verhältnis, Auflösung, Framerate und Audio-Toggle außerhalb des Prompttexts?
- [ ] Provider unterstützt die gewählten Werte?
- [ ] MOV bei professionellem Editing/Extension erwogen?

---

## 33. Merksystem zum Auswendiglernen

### Die sechs Promptbausteine: S-A-O-B-K-T

```text
S – Subjekt
A – Aktion/Ereignis
O – Ort/Umgebung
B – Bildstil/Licht/Material
K – Kamera/Schnitt
T – Ton
```

### Die fünf Produktionsverträge

```text
1. Taskvertrag: Generate, Edit oder Extend?
2. Storyvertrag: Wer tut was, warum und mit welchem Endzustand?
3. Assetvertrag: Welches Asset liefert genau was?
4. Zeitvertrag: Welche Stufe übernimmt welchen Zustand?
5. Konsistenzvertrag: Was darf sich niemals ändern?
```

### Die drei Fragen für jeden Beat

```text
Was ist am Anfang sichtbar wahr?
Welche eine Hauptänderung geschieht?
Was ist am Ende sichtbar wahr?
```

### Die Kameraformel

```text
Größe → Ziel → Start → Weg → Tempo → Ende
```

### Die Assetformel

```text
Quelle → Funktion → erlaubte Merkmale → Ausschlüsse
```

---

## 34. Behauptungen, die nicht pauschal als gesichert gelten

- Seedance 2.5 erzeuge über jede API nativ 4K.
- Jede Seedance-2.5-Ausgabe habe 60 fps.
- Alle Provider unterstützen 1080p.
- Audio-only funktioniere bei jedem Drittanbieter genau wie bei ModelArk.
- Ein `seed` mache Ausgaben reproduzierbar.
- Timestamps seien framegenaue Schnittpunkte.
- 50 Assets verbesserten automatisch die Qualität.
- Ein Storyboard werde Panel für Panel pixelgenau kopiert.
- Deutsch sei offiziell als gleichwertige Prompt-Sprache gelistet.
- Negative-Prompt-Keywordlisten verhinderten zuverlässig Hände-, Text- oder Identitätsfehler.
- „Cinematic“, „8K“ oder „masterpiece“ ersetzten eine Produktionsstruktur.
- Editing könne Seitenverhältnis und Dauer unabhängig vom Master ändern.
- Eine Extension erhalte die Naht pixelidentisch.

---

## 35. Offizielles Prompt-Optimierungs-Skill

BytePlus stellt `sd25-pe` als offiziellen Prompt-Optimierer bereit. Die Dokumentation empfiehlt die Installation über die angegebene Skill-Quelle und die Nutzung mit `/sd25-pe`.

Der wichtigste Wert des Skills ist nicht ein geheimes Keyword, sondern sein Arbeitsprozess:

1. Story Contract bilden.
2. Assets vollständig inventarisieren.
3. Fakten und Assetbeobachtungen trennen.
4. genau einen Primärtask wählen.
5. Parameterkompatibilität prüfen.
6. task-spezifisches Template anwenden.
7. alle verwendeten und ungenutzten Assets bilanzieren.
8. Endzustände und Konsistenz prüfen.
9. genau einen besten, direkt einreichbaren Prompt ausgeben.

Der Guide in dieser Datei integriert diese Regeln, sodass sie auch manuell angewendet werden können.

---

## 36. Quellen

### Primärquellen

1. [ByteDance Seed: Introducing Seedance 2.5](https://seed.bytedance.com/en/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5) – Launch, 30 Sekunden, 50 Assets, Editing, Blockout und offizielle Beispiele.
2. [ByteDance Seed: Seedance 2.5](https://seed.bytedance.com/en/seedance2_5) – offizielle Modellpositionierung und Produktmerkmale.
3. [ByteDance Seed: Models](https://seed.bytedance.com/en/models) – Einordnung in die Seed-Modellfamilie.
4. [BytePlus: Dreamina Seedance 2.5 Prompt Guide](https://docs.byteplus.com/en/docs/ModelArk/2607689) – offizielle Promptstruktur, Referenzregeln, Timestamps, Kamera, Storyboards, Keyframes, Blockouts und Fehlerhinweise.
5. [BytePlus: Dreamina Seedance 2.5 Tutorial](https://docs.byteplus.com/en/docs/ModelArk/2607688) – Modell-ID, Tasktypen, Limits, Auflösung, Formate, Sprachen und API-Beispiele.
6. [BytePlus: Create Video Generation Task](https://docs.byteplus.com/api/docs/ModelArk/1520757) – aktuelle Parameter, Rollen, Task-Hints, Dateilimits und Fehlertypen.
7. [Dreamina: Seedance 2.5](https://dreamina.capcut.com/seedance/seedance-2-5) – Produktoberflächenfunktionen, 4K-/Long-Video-Workflow und Creator-Zugang.
8. [CapCut: Seedance 2.5 for Video Editor](https://www.capcut.com/zh-tw/features/seedance-2-5-for-video-editor) – CapCut-spezifische Auflösung, Langvideo und Nachbearbeitung.

### Offizielle Partner und Praxisabgleich

9. [Replicate: bytedance/seedance-2.5](https://replicate.com/bytedance/seedance-2.5) – offizielles ByteDance-Deployment und Provider-Schema.
10. [fal: How to Use Seedance 2.5](https://fal.ai/learn/devs/how-to-use-seedance-2-5) – von BytePlus redigierter ausführlicher Praxisguide.
11. [fal: Seedance 2.5 Prompting Guide](https://fal.ai/learn/devs/seedance-2-5-prompting-guide) – kontrollierte Iteration und Providerparameter.
12. [fal: Text-to-Video API](https://fal.ai/models/bytedance/seedance-2.5/text-to-video/api) – aktuelle fal-spezifische Limits.

### Quellenwarnung

Bei Auflösung, Framerate, Audio-only und langer Dauer können gleichzeitig mehrere scheinbar widersprüchliche Aussagen korrekt sein, weil sie verschiedene Produkte beschreiben. Dieser Guide nennt deshalb immer die Plattform. Für eine konkrete Produktion gilt zuletzt die live sichtbare Oberfläche beziehungsweise das aktuelle API-Schema des verwendeten Providers.

---

## Schlussformel

Ein meisterhafter Seedance-2.5-Prompt beantwortet neun Fragen ohne Widerspruch:

1. Welcher Primärtask wird ausgeführt?
2. Wer oder was ist im Bild – und wie oft?
3. Was ist zu Beginn sichtbar wahr?
4. Welche kausale Zustandsänderung geschieht?
5. Was ist am Ende sichtbar wahr?
6. Welches Asset kontrolliert welchen Teil – und welchen ausdrücklich nicht?
7. Wie beobachtet die Kamera das Ereignis?
8. Was hört man, wer spricht und in welcher Sprache?
9. Was muss trotz Shots, Schnitten, Edits oder Extensions unverändert bleiben?

Wer diese neun Fragen präzise beantwortet, promptet Seedance 2.5 nicht wie eine Bildmaschine, sondern wie ein kontrollierbares Produktionssystem.
