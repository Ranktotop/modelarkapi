# Referenzmedien

Der einheitliche Vertrag kennt Referenzen als `references[]`; Seedance akzeptiert
zusätzlich die bisherigen Felder. Die Quellenregeln stehen in
[SPEC.md](../SPEC.md) (Abschnitt 7).

## Referenzobjekt

```json
{
  "type": "image | video | audio | element | voice",
  "role": "first_frame | last_frame | reference | subject | motion | base_video | speech | product | model | avatar | bgm",
  "url": "https://… | data:<mime>;base64,…",
  "upload_id": "ref-…",
  "task_id": "video_… | cgt-… | vid-…",
  "output": 0,
  "asset_id": "asset-…",
  "name": "Anzeigename",
  "real_human": false
}
```

- Genau eine Quelle aus `url`, `upload_id`, `task_id` oder `asset_id`.
- `type` ist Pflicht, außer bei `task_id` (dann `video`) und `asset_id` mit
  bekanntem Präfix (`asset-kling-element-…`, `asset-kling-voice-…`,
  `asset-modelark-…`).
- Ohne `role` vergibt der Proxy sie nach Task: ein Bild wird bei
  `image_to_video` zu `first_frame`, bei `first_last_frame` nacheinander zu
  `first_frame` und `last_frame`, bei `motion_control`, `avatar` und `effect` zu
  `subject`; ein Video bei `edit`, `extend`, `lip_sync`, `video_to_audio` und
  `multi_element_edit` zu `base_video`, bei `motion_control` zu `motion`; Audio bei
  `lip_sync` und `avatar` zu `speech`; alles andere zu `reference`. Bei Commerce
  gelten Bilder als `product`, Videos als `base_video`, Audio als `bgm`; Avatar-
  und Modellbilder müssen die Rolle ausdrücklich tragen.
- Die Seedance-Rollen `reference_image`, `reference_video` und `reference_audio`
  werden im einheitlichen Pfad ignoriert und durch die Task-Rolle ersetzt.
- `output` wählt bei `task_id` die Variante des Quelljobs (Standard 0).
- `name` dient nur der Anzeige und geht nicht an den Anbieter. Kling-Prompts
  verweisen mit `<<<image_n>>>`, `<<<video_n>>>`, `<<<element_n>>>` und
  `<<<voice_n>>>` auf Referenzen (`n` ab 1 je Typ, in Array-Reihenfolge).
- `real_human: true` aktiviert die Seedance-Asset-Verifizierung (siehe unten). Bei
  anderen Anbietern ergibt es `400 unsupported_parameter` (`param: real_human`).

## Quellen und wie der Proxy sie bereitstellt

| Quelle | Seedance / Kling (brauchen URL) | Google (braucht Bytes) |
|---|---|---|
| `https://`-URL | unverändert weitergegeben | Proxy lädt sie herunter (SSRF-geschützt) |
| `data:`-URI | Seedance: Bild und Audio inline weitergegeben, Video über den Media-Store; Kling: Bilder und Lip-Sync-/Avatar-Audio als Base64, Videos über den Media-Store (`PUBLIC_BASE_URL`-Adresse) | dekodiert |
| `upload_id` | Media-Store-URL | lokal gelesen |
| `task_id` | Seedance: Ergebnis-URL eines `cgt-…`-Tasks; sonst lokale Datei über den Media-Store | lokale Datei bzw. Upstream-Referenz (Veo-Extension, Omni-Multi-Turn) |
| `asset_id` | Seedance: `asset://asset-…`; Kling: Element oder Voice (auch eine `char-…`/`character_…`-ID eines OpenAI-Characters) | nicht unterstützt (400) |

Ohne `PUBLIC_BASE_URL` können Seedance und Kling nur `https://`-URLs nutzen;
andere Quellen, die ein Hosting brauchen, ergeben `400 public_base_url_required`.
Kling akzeptiert Bilder (und Audio für Lip Sync und Avatar, bis 5 MB) auch als
Base64; Videos für Lip Sync, Motion Control und Edit nimmt Kling nur per URL.

Wo der Proxy eine URL selbst abruft, gilt: nur `https`, Auflösung des Hosts mit
Ablehnung privater, Loopback-, Link-Local- und Multicast-Adressen (auch nach
Redirects), Größenlimit je Typ und Prüfung der Dateisignatur. `data:`-URIs sind
auf `MAX_INLINE_REFERENCE_BYTES` (Standard 25 MB) begrenzt. Der Typ wird
ausschließlich über die Dateisignatur bestimmt; Dateiname und deklarierter MIME-
Typ werden ignoriert.

## Unterstützte Wege

### Multipart-Upload

`input_reference` akzeptiert ein Bild oder ein MP4/MOV-Video (nur Seedance;
Google und Kling lehnen es ab und erwarten `references`). Ein Video wird
temporär bereitgestellt, weil ModelArk Referenzvideos nur per URL abruft. Darum
muss `PUBLIC_BASE_URL` von ModelArk über HTTPS erreichbar sein.

```bash
curl -X POST http://127.0.0.1:8081/v1/videos \
  -H "Authorization: Bearer $PROXY_KEY" \
  -F 'model=dreamina-seedance-2-0-fast-260128' \
  -F 'prompt=Extend this scene forward' \
  -F 'input_reference=@clip.mp4;type=video/mp4'
```

Mehrere Dateien lädt man vorab über `POST /v1/media/references` (bis zu 50) hoch
und verweist mit `upload_id` oder der zurückgegebenen `url` darauf.

### Öffentliche URLs

Bei Seedance nutzt eine Referenz `input_reference_url`, mehrere nutzen
`reference_urls`; Objekte erlauben `media_type` und `role`. Im einheitlichen Pfad
dient dafür `references[].url`. URLs müssen absolute HTTP(S)-URLs sein und
während der Verarbeitung erreichbar bleiben.

### Real-Human-Referenzen (Seedance)

Eine hochgeladene oder öffentliche Referenz kann mit `real_human: true` markiert
werden. Der Proxy registriert sie dann automatisch in der konfigurierten
Asset-Gruppe. Die temporäre Asset-ID bleibt intern; die Altfelder für Asset-IDs
werden abgewiesen. Siehe [Real-Human-Assets](../real-human-assets/README.md).

Unabhängig davon akzeptiert der Proxy in `references[]` eine öffentliche
ModelArk-Asset-ID (`asset-…`, etwa aus der Digital-Character-Library) und reicht
sie als `asset://asset-…` weiter.

### Rohes ModelArk-Content (Seedance)

Fortgeschrittene Aufrufer können ein `content`-Array mitsenden, etwa mit
Base64-Bildern oder neuen, noch nicht modellierten Content-Typen. Bei anderen
Anbietern ist `content` nicht erlaubt.

```json
{
  "content": [
    {"type":"text", "text":"Animate the subject"},
    {
      "type":"image_url",
      "image_url":{"url":"data:image/png;base64,..."},
      "role":"reference_image"
    }
  ]
}
```

`asset://`-URIs in `content` werden abgewiesen.

## Rollen bei Seedance

Im Altformat gelten:

| Medium | Erlaubte Rollen |
|---|---|
| Bild | `reference_image`, `first_frame`, `last_frame` |
| Video | `reference_video` |
| Audio | `reference_audio` |

## Eingabegrenzen

Die verbindlichen Grenzen je Modell liefert `capabilities.tasks.<task>.references`
(Rolle, Typen, `min`, `max`, `max_bytes`, `formats`, Dauergrenzen) und `limits`
für Gruppenlimits.

| Modell | Grenzen (Auszug) |
|---|---|
| Seedance 2.5 | 30 Bilder, 10 Videos, 10 Audio; Video/Audio je 2–30 s, zusammen ≤ 30 s; Audio auch allein; `edit` mit Video von mindestens 4 s |
| Seedance 2.0 / Fast / Mini | 9 Bilder, 3 Videos, 3 Audio; je 2–15 s, zusammen ≤ 15 s; Audio nicht allein |
| Veo | Bilder JPEG/PNG ≤ 20 MB; Referenzbilder 1–3; Extension-Video MP4, Vertex 1–30 s |
| Omni | Bilder PNG/JPEG/WebP ≤ 20 MB (bis 10), Videos MP4/MOV ≤ 20 MB; `base_video` Vertex 1–30 s, Gemini API bis 10 s; Referenzvideos ≤ 3 s, bis zu 3 |
| Kling | Bilder JPEG/PNG (Legacy ≤ 10 MB, neue API ≤ 50 MB), Motion-Video ≤ 100 MB und 3–30 s, Omni-Video ≤ 200 MB und 3–10 s (3.0 Omni bis 15 s), Audio ≤ 5 MB |

Allgemeine Obergrenzen für Uploads: Bild 30 MB, Video 200 MB, Audio 15 MB
(`MAX_UPLOAD_BYTES` begrenzt zusätzlich die Dateigröße). Video bei Seedance:
MP4/MOV; Bild laut ModelArk unter 30 MB und Request-Body unter 64 MB bei Base64.

ModelArk und Kling führen weitere Prüfungen für Abmessungen, Seitenverhältnis,
Codec, Framerate, Inhalt, Rechte und Gesichter durch.
