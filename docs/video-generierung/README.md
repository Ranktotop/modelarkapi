# Video-Generierung

Seedance arbeitet asynchron. Jeder POST erzeugt zunächst eine Task-ID; danach
wird gepollt und das Ergebnis heruntergeladen.

## Text-to-Video

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

## First-Frame und First-/Last-Frame

Eine Bildreferenz mit `role: "first_frame"` startet das Video exakt aus diesem
Bild. Für ein festes Endbild wird zusätzlich ein zweites Bild mit
`role: "last_frame"` übergeben:

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

Bei Seedance 2.0 darf Audio nicht allein stehen; mindestens ein Bild oder
Video ist nötig. Seedance 2.5 akzeptiert auch reine Audioreferenzen.

## Modellabhängige Ausgabeoptionen

Die maßgeblichen Werte liefert `GET /v1/models` je Modell unter
`capabilities`; der Proxy validiert dagegen, bevor er einen Task anlegt.

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

1080p bei Seedance 2.5 und 4k bei Seedance 2.0 liefern 10-Bit-Farbtiefe mit
H.265/HEVC. Nicht jeder Player spielt das ab; VLC, mpv oder QuickTime sind der
verlässliche Weg.

## Bearbeiten und Verlängern ohne Task-Typ

Nur Seedance 2.5 kennt `omni_reference_task_type`. Bei Seedance 2.0, 2.0 Fast
und 2.0 Mini gibt es kein Feld, das eine Bearbeitung von einer gewöhnlichen
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

Weil der Proxy hier keinen Task-Typ kennt, erzwingt er auch weder
`ratio: "adaptive"` noch `duration: -1`. Beide Werte bleiben frei wählbar und
gelten für das Ergebnis, statt vom Ausgangsvideo übernommen zu werden.

Wird `omni_reference_task_type` trotzdem an ein 2.0-Modell gesendet, antwortet
der Proxy mit HTTP 400 statt einer Task-ID. Ob ein Modell den Typ akzeptiert,
steht in `GET /v1/models` unter `capabilities.task_types`; eine leere Liste
bedeutet, dass der Prompt der einzige Steuerweg ist.

## Task-Typen bei Seedance 2.5

Seedance 2.5 leitet aus Referenzen und Prompt ab, ob es sich um eine
Referenz-, Bearbeitungs- oder Verlängerungsaufgabe handelt. `edit` und
`extend` unterliegen dabei eigenen Regeln. `omni_reference_task_type` legt den
Typ vorab fest und verschiebt die Prüfung nach vorn:

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
  Länge des Originals behält. Der Prompt muss die Bearbeitungsabsicht nennen
  („edit the video“, „add“, „remove“, „replace“).
- `extend` verlangt ebenfalls eine Videoreferenz und `ratio: "adaptive"`; die
  Länge ist mit `[4, 30]` oder `-1` frei wählbar. Der Prompt muss die
  Fortsetzung benennen („extend forward/backward“, „continue“).
- First-/Last-Frame-Tasks übernehmen das Seitenverhältnis des Startbilds und
  laufen deshalb ebenfalls mit `ratio: "adaptive"`.

Der Proxy setzt diese erzwungenen Werte selbst und lehnt widersprüchliche
Angaben sofort mit HTTP 400 ab. Weicht der vom Modell erkannte Task-Typ
trotzdem vom angegebenen ab, meldet ModelArk asynchron
`InvalidParameter.TaskTypeMismatch`.

Mit `return_last_frame: true` kann ein PNG-Endframe angefordert werden. Es ist
anschließend über `/v1/videos/{id}/last_frame` abrufbar und eignet sich als
First-Frame eines Folgetasks.
