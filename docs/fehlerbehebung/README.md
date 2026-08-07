# Fehlerbehebung

## `upstream_credentials_invalid`

Der Proxy läuft, hat aber beim letzten Read-only-Check einen ungültigen oder
nicht erreichbaren `ARK_API_KEY` beziehungsweise IAM-Zugang festgestellt.
`GET /health` zeigt unter `credentials` den betroffenen Zugang und den
Prüfzeitpunkt. Nach einer serverseitigen Freischaltung wird der Zugriff beim
nächsten Intervall automatisch aktiviert. Nach einer Änderung der
Container-Umgebungsvariablen ist ein Neustart nötig.

## Seedance-Resource-Package

`QueryBalanceAcct` zeigt nur den allgemeinen BytePlus-Kontosaldo und sagt nichts
Verlässliches über ein gekauftes Seedance-Resource-Package aus. Der Proxy nutzt
diesen Wert deshalb nicht. Die Restmenge steht im Billing Center unter
**Resource package**. Einen von ModelArk bei einer Generierung gelieferten
Package- oder Billing-Fehler reicht der Proxy mit seinem originalen Fehlercode
an LiteLLM und UI weiter.

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

`GET /v1/models`, den IAM-Zugriff und die aktivierte Modell-ID prüfen.
Seedance 2.0 Fast unterstützt
nicht automatisch sämtliche Optionen anderer Seedance-Versionen. Insbesondere
Auflösung, Dauer, Offline-Tier, Seed, Frames und Kamerafixierung sind
modellabhängig.

## LiteLLM findet Task-ID nicht

Für Folgeaufrufe genau die von LiteLLM ausgegebene ID verwenden. LiteLLM kann
Routing-Informationen in der ID kodieren; eine herauskopierte rohe `cgt-…`-ID
kann am Gateway vorbeigeroutet werden.
