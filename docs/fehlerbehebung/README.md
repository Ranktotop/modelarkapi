# Fehlerbehebung

## `PUBLIC_BASE_URL is required`

Ein lokales Referenzvideo wurde hochgeladen, aber der Proxy besitzt keine
öffentliche HTTPS-URL. `PUBLIC_BASE_URL` setzen und sicherstellen, dass die
erzeugte `/media/reference/...`-URL aus dem Internet erreichbar ist. Bei einem
autorisierten `asset_id` ist diese URL nicht nötig.

## `Reference URLs must be absolute HTTP(S) URLs`

Relative Pfade, lokale Dateipfade und `file://` sind nicht erlaubt. Eine
öffentliche URL, ein Asset oder für Bilder rohes Base64-`content` verwenden.

## Real-person-/Face-Fehler von ModelArk

Ein gewöhnlicher Upload mit realem Gesicht ist nicht freigegeben. Eine aktive
Real-Human-Asset-ID, einen zugelassenen Digital Character oder einen weiterhin
vertrauenswürdigen Originaloutput verwenden. Die Asset-Autorisierung muss zur
Person, zum Account und zum Nutzungszeitraum passen.

## `video_not_ready`

Der Download wurde vor `succeeded` angefordert. Status pollen und erst bei
`completed` laden.

## Letztes Frame fehlt

Der Task wurde nicht mit `return_last_frame: true` erstellt oder das gewählte
Modell unterstützt die Funktion nicht. Der Proxy antwortet dann mit 404.

## First-/Last-Frame kann nicht mit Referenzen gemischt werden

ModelArk behandelt exakte Frame-Steuerung und multimodale Referenzen als
gegenseitig ausschließende Szenarien. Entweder nur `first_frame`/`last_frame`
oder nur `reference_image`/`reference_video`/`reference_audio` einsetzen. In
einem multimodalen Prompt kann ein Bild stattdessen semantisch als Anfang oder
Ende beschrieben werden, ohne eine Frame-Rolle zu verwenden.

## Modell oder Parameter nicht unterstützt

`MODEL_MAP` und die aktivierte Modell-ID prüfen. Seedance 2.0 Fast unterstützt
nicht automatisch sämtliche Optionen anderer Seedance-Versionen. Insbesondere
Auflösung, Dauer, Offline-Tier, Seed, Frames und Kamerafixierung sind
modellabhängig.

## LiteLLM findet Task-ID nicht

Für Folgeaufrufe genau die von LiteLLM ausgegebene ID verwenden. LiteLLM kann
Routing-Informationen in der ID kodieren; eine herauskopierte rohe `cgt-…`-ID
kann am Gateway vorbeigeroutet werden.
