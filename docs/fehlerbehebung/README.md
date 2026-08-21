# Fehlerbehebung

## `upstream_credentials_invalid`

Der Proxy läuft, hat aber beim letzten Read-only-Check einen von ModelArk
abgelehnten `ARK_API_KEY` beziehungsweise IAM-Zugang festgestellt.
`GET /health` zeigt unter `credentials` den betroffenen Zugang und den
Prüfzeitpunkt. Nach einer serverseitigen Freischaltung wird der Zugriff beim
nächsten Intervall automatisch aktiviert. Nach einer Änderung der
Container-Umgebungsvariablen ist ein Neustart nötig.

## `upstream_credentials_unavailable`

Der Proxy konnte ModelArk bei der Credential-Prüfung nicht erreichen und hat
für diesen Zugang noch nie eine gültige Antwort gesehen — typischerweise beim
Start ohne funktionierendes Netz oder DNS. Der Zustand lautet dann `checking`,
nicht `invalid`: es ist keine Aussage über den Schlüssel, sondern über die
Erreichbarkeit. Geprüft wird im verkürzten Takt aus
`CREDENTIAL_REVALIDATION_INTERVAL_SECONDS` (Standard 30 Sekunden), die Routen
geben sich also ohne Neustart wieder frei. War der Zugang zuvor bereits gültig,
tritt dieser Fall gar nicht ein: der Proxy bleibt dann auf `valid` und nennt den
Netzwerkfehler nur unter `credentials.message`.

## `Name or service not known` / `real_human_asset_error`

DNS im Container ist zeitweise ausgefallen. Der Text stammt aus dem
Betriebssystem und erreicht den Client als `error.message` eines
`video-rh-…`-Jobs. Bevorzugt tritt das bei mehreren gleichzeitigen Aufträgen
auf, weil dabei mehrere Namensauflösungen parallel starten.

Der Proxy fängt das auf zwei Ebenen ab: jeder ModelArk-Aufruf wird bei einem
Verbindungsfehler bis zu `UPSTREAM_RETRY_ATTEMPTS` mal wiederholt, und ein Job,
dessen Aufrufe trotzdem alle scheitern, wird nicht mehr endgültig
abgebrochen. Er wartet stattdessen mit Backoff
(`ASSET_TRANSIENT_RETRY_SECONDS`) und läuft weiter, sobald das Netz wieder da
ist. Erst `ASSET_MAX_PROCESSING_SECONDS` beziehungsweise `ASSET_JOB_TTL_SECONDS`
beenden ihn hart. Im Log erscheinen währenddessen `could not connect` und
`could not reach ModelArk`.

Bleibt der Fehler dauerhaft, liegt er in der Infrastruktur, nicht in der
Anwendung. Docker-eigener DNS unter `127.0.0.11` ist der übliche Kandidat; ein
`dns_opt: ["single-request-reopen"]` am Compose-Service entschärft die bekannte
glibc-Race, bei der A- und AAAA-Abfrage parallel über denselben Port laufen.

Wichtig für die Abgrenzung: erscheint derselbe Text nicht im Job-Objekt, sondern
schon beim Absenden der Anfrage als `APIConnectionError`, dann konnte der Client
beziehungsweise LiteLLM den Proxy selbst nicht auflösen. Dann ist der Alias
`modelarkapi_server` oder das gemeinsame Docker-Netz zu prüfen, nicht dieser
Abschnitt.

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
erzeugte `/media/reference/...`-URL aus dem Internet erreichbar ist. Auch der
automatische Real-Human-Workflow benötigt diese URL für die Asset-Registrierung.

## `Reference URLs must be absolute HTTP(S) URLs`

Relative Pfade, lokale Dateipfade und `file://` sind nicht erlaubt. Eine
öffentliche URL oder für Bilder rohes Base64-`content` verwenden.

## Real-person-/Face-Fehler von ModelArk

Ein gewöhnlicher Upload mit realem Gesicht ist nicht freigegeben. Die Referenz
mit `real_human: true` markieren, damit der Proxy sie in der konfigurierten,
autorisierten Asset-Gruppe registriert. Alternativ einen zugelassenen Digital
Character oder einen weiterhin vertrauenswürdigen Originaloutput verwenden.

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

## `does not support omni_reference_task_type`

Der Task-Typ wurde an ein Modell gesendet, das ihn nicht kennt. `auto`,
`reference`, `edit` und `extend` gibt es ausschließlich bei Seedance 2.5; die
2.0-Familie lehnt das Feld vor dem Upstream-Aufruf mit HTTP 400 ab. Das Feld
weglassen und die Bearbeitungs- oder Verlängerungsabsicht im Prompt
formulieren. Welche Werte ein Modell akzeptiert, steht in `GET /v1/models`
unter `capabilities.task_types`; eine leere Liste bedeutet, dass es keinen
Task-Typ gibt.

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
