# Referenzmedien

## Unterstützte Wege

### Multipart-Upload

`input_reference` akzeptiert ein Bild oder ein MP4/MOV-Video. Der Proxy prüft
die Dateisignatur statt sich allein auf den MIME-Typ zu verlassen. Ein Video
wird temporär bereitgestellt, weil ModelArk Referenzvideos nur per URL abruft.
Darum muss `PUBLIC_BASE_URL` von ModelArk über HTTPS erreichbar sein.

```bash
curl -X POST http://localhost:8080/v1/videos \
  -H "Authorization: Bearer $PROXY_KEY" \
  -F 'model=seedance' \
  -F 'prompt=Extend this scene forward' \
  -F 'input_reference=@clip.mp4;type=video/mp4'
```

### Öffentliche URLs

Eine Referenz nutzt `input_reference_url`; mehrere nutzen `reference_urls`.
Objekte erlauben `media_type` und `role`. URLs müssen absolute HTTP(S)-URLs
sein und während der Verarbeitung erreichbar bleiben.

### Autorisierte Assets

Assets werden als `asset-…` oder `asset://asset-…` angenommen und zu der von
ModelArk erwarteten URI normalisiert. Für sie ist keine `PUBLIC_BASE_URL`
nötig. Siehe [Real-Human-Assets](../real-human-assets/README.md).

### Rohes ModelArk-Content

Fortgeschrittene Aufrufer können ein `content`-Array mitsenden, etwa mit
Base64-Bildern oder neuen, noch nicht eigens modellierten Content-Typen:

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

## Rollen

| Medium | Erlaubte Rollen |
|---|---|
| Bild | `reference_image`, `first_frame`, `last_frame` |
| Video | `reference_video` |
| Audio | `reference_audio` |

## Seedance-2.0-Grenzen

- maximal 9 Referenzbilder
- maximal 3 Referenzvideos; je 2–15 Sekunden, zusammen höchstens 15 Sekunden
- maximal 3 Audiodateien; Audio nicht ohne Bild oder Video
- Video: MP4/MOV, höchstens 200 MB je Datei
- Bild: laut ModelArk unter 30 MB und Request-Body unter 64 MB bei Base64

ModelArk führt weitere Prüfungen für Abmessungen, Seitenverhältnis, Codec,
Framerate, Inhalt, Rechte und Gesichter durch. Die lokale Maximalgröße wird mit
`MAX_UPLOAD_BYTES` begrenzt.
