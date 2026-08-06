# Video-Generierung

Seedance arbeitet asynchron. Jeder POST erzeugt zunächst eine Task-ID; danach
wird gepollt und das Ergebnis heruntergeladen.

## Text-to-Video

```json
{
  "model": "seedance",
  "prompt": "Cinematic macro shot of rain on a red leaf",
  "duration": 5,
  "resolution": "720p",
  "ratio": "16:9",
  "generate_audio": true
}
```

## First-Frame und First-/Last-Frame

Eine Bildreferenz mit `role: "first_frame"` startet das Video exakt aus diesem
Bild. Für ein festes Endbild wird zusätzlich ein zweites Bild mit
`role: "last_frame"` übergeben:

```json
{
  "prompt": "A smooth camera transition between both scenes",
  "reference_assets": [
    {"id":"asset-first", "type":"image", "role":"first_frame"},
    {"id":"asset-last", "type":"image", "role":"last_frame"}
  ],
  "duration": 6
}
```

First-/Last-Frame und multimodale `reference_*`-Rollen sind laut ModelArk
getrennte Szenarien und dürfen nicht kombiniert werden. Der Proxy weist solche
Mischungen vor dem Upstream-Aufruf zurück.

## Multimodale Generierung und Bearbeitung

`reference_image`, `reference_video` und `reference_audio` können gemeinsam
verwendet werden. Der Prompt beschreibt, wie `Image 1`, `Video 1` und `Audio 1`
verwendet werden sollen. Damit sind unter anderem Stil-/Bewegungsübertragung,
gezielte Videobearbeitung, Vorwärts-/Rückwärtsverlängerung und das Verbinden
von bis zu drei Clips erreichbar.

```json
{
  "prompt": "Extend Video 1 forward. Keep its camera motion and use Audio 1 as background music.",
  "reference_urls": [
    {"url":"https://media.example/clip.mp4", "media_type":"video"},
    {"url":"https://media.example/music.mp3", "media_type":"audio"}
  ],
  "duration": 8,
  "ratio": "adaptive"
}
```

Audio darf nicht allein stehen; mindestens ein Bild oder Video ist nötig.

## Ausgabeoptionen für Seedance 2.0 Fast

Der derzeitige Fast-Zugang unterstützt 480p und 720p. Die Dauer beträgt 4 bis
15 ganze Sekunden oder `-1` für automatische Wahl. Übliche Seitenverhältnisse
sind `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9` und `adaptive`.
`generate_audio` schaltet synchrones Mono-Audio ein oder aus. Modellabhängige
Felder wie `frames`, `seed`, `camera_fixed`, `service_tier=flex` oder 4K dürfen
bei Seedance 2.0 Fast nicht als verfügbar vorausgesetzt werden; ModelArk ist
hier die maßgebliche Validierungsinstanz.

Mit `return_last_frame: true` kann ein PNG-Endframe angefordert werden. Es ist
anschließend über `/v1/videos/{id}/last_frame` abrufbar und eignet sich als
First-Frame eines Folgetasks.
