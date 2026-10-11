# Fehlerbehebung

Fehlerantworten haben die Form `{"error": {"code", "message", "param", …}}`;
Fehler eines Jobs stehen unter `error` im Video-Objekt. Die Codes sind in der
[API-Referenz](../api-referenz/README.md) und in SPEC 11.3 aufgeführt.

## `upstream_credentials_invalid`

Der Proxy läuft, hat aber beim letzten Read-only-Check die Zugangsdaten eines
Anbieters als abgelehnt festgestellt (ModelArk: `ARK_API_KEY` oder IAM; Google:
`GEMINI_API_KEY` oder vertex; Kling: `KLING_API_KEY`). Nur Routen dieses Anbieters
sind gesperrt, die anderen Modelle laufen weiter. `GET /health` zeigt unter
`providers` den betroffenen Anbieter (mit `message`) und den Prüfzeitpunkt. Nach
einer serverseitigen Freischaltung wird der Zugriff beim nächsten Intervall
automatisch aktiviert. Nach einer Änderung der Umgebungsvariablen ist ein Neustart
nötig.

## `upstream_credentials_unavailable`

Der Proxy konnte den Anbieter bei der Credential-Prüfung nicht erreichen und hat für
diesen Zugang noch nie eine gültige Antwort gesehen — typischerweise beim Start ohne
funktionierendes Netz oder DNS. Der Zustand lautet dann `checking`, nicht `invalid`:
es ist keine Aussage über den Schlüssel, sondern über die Erreichbarkeit. Geprüft
wird im verkürzten Takt aus `CREDENTIAL_REVALIDATION_INTERVAL_SECONDS` (Standard 30
Sekunden), die Routen geben sich also ohne Neustart wieder frei. War der Zugang
zuvor bereits gültig, tritt dieser Fall gar nicht ein: der Proxy bleibt dann auf
`valid` und nennt den Netzwerkfehler nur unter `message`.

## `model_unavailable` / Modell fehlt in `/v1/models`

Das Modell gehört zu einem Anbieter, der nicht konfiguriert oder derzeit nicht
erreichbar ist, oder die Modell-ID wird vom Anbieter nicht gemeldet.
`GET /v1/models` und `/health` prüfen. Hinweise:

- Veo über die Gemini API (`veo-3.1-*-generate-preview`) endet laut Google am
  22.10.2026; die Liste zeigt nur, was `models.list` meldet. Auf Vertex Veo-
  Backend und `GOOGLE_VEO_LOCATION` prüfen (`us-central1` und `global` sind
  erreichbar, `europe-west4` laut ADR-001 nicht).
- Omni auf Vertex kennt nur die Preview-IDs `gemini-omni-1.1-flash-preview` und
  `gemini-omni-flash-preview`; `gemini-omni-1.1-flash` gibt es nur auf der Gemini
  API. `GOOGLE_OMNI_BACKEND` muss `vertex` oder `gemini` sein; `both` wird nicht
  unterstützt.
- Kling meldet bei abgekündigten Modellen Code 1203; der Proxy macht daraus
  `model_unavailable`.

## `unsupported_parameter`, `unsupported_task`, `reference_limit`

Das Modell kann das Feld, den Wert, den Task oder die Referenzkombination nicht.
Die Fehlermeldung nennt die erlaubten Werte; dieselben stehen im Capability-Dokument
(`GET /v1/models/{id}`). Optionen: Wert anpassen, ein anderes Modell wählen oder
`"parameter_policy": "adapt"` setzen — dann passt der Proxy Werte an und listet jede
Änderung unter `adjustments`. Typische Auslöser:

- Veo: 1080p/4k nur mit 8 s; `first_last_frame` und `reference_to_video` nur mit 8 s.
- Kling: `generate_audio` zusammen mit Referenzvideo (Omni); Elements und Voices
  gleichzeitig; Elements ohne Startbild; Dauer bei Tasks, die der Anbieter bestimmt.
- Seedance: siehe die folgenden Abschnitte.

## Seedance lehnt ein Feld ab

Der Proxy prüft Seedance-Felder vor dem Upstream-Aufruf:

- `does not generate audio`: `generate_audio` an Seedance 1.0 Pro / Pro Fast.
- `does not support camera_fixed` oder `camera_fixed cannot be combined with
  reference images`: `camera_fixed` gibt es nur bei 1.x und nicht mit Referenzbildern.
- `does not support priority` / `priority cannot be combined with
  service_tier=flex`: `priority` (0–9) gibt es nur bei 2.x; `flex` nur bei 1.x.
- `execution_expires_after must be between 3600 and 259200 seconds`.
- `frames must be 25 + 4n between 29 and 289`.
- `A final video inherits these fields from its draft`: Beim Endvideo mit
  `draft_task_id` nur `resolution`, `watermark`, `return_last_frame`,
  `output_format`, `service_tier`, `execution_expires_after`, `priority`,
  `callback_url` und `safety_identifier` senden. `Draft videos are rendered in 480p
  only`: für `draft: true` keine andere Auflösung wählen.
- `Asset IDs are managed internally`: die Altfelder für Asset-IDs und `asset://`
  in `content` sind gesperrt. Öffentliche `asset-…`-IDs gehören in
  `references[].asset_id`.
- `Inline data: references are accepted for images and audio only`: Videos
  brauchen eine URL oder einen Upload.

## `409 video_running`

Ein laufender Seedance-Task lässt sich weder abbrechen noch löschen. Erst nach
`succeeded`/`failed` löschen; ein `queued`-Task wird dagegen abgebrochen. In der
Studio-Oberfläche verschwindet der Job lokal, der Eintrag bleibt aber beim Proxy,
bis er endet.

## Kling-Fehler

| Code | Bedeutung |
|---|---|
| `billing` (402) | Guthaben oder Ressourcenpaket erschöpft (Kling 1100–1102) |
| `rate_limited` (429, `retryable`) | Rate- oder Parallelitätslimit (1302/1303, oder HTTP 429); später wiederholen |
| `content_policy` (400) | Inhaltsfilter (1300/1301) |
| `upstream_forbidden` (403) | Zugriff verweigert (1103) |
| `upstream_credentials_invalid` (503) | Schlüsselfehler (1000–1004) |
| `model_unavailable` (404) | Modell nicht verfügbar (1203) |

Weitere Hinweise:

- Referenzvideos und Audio für Kling brauchen `PUBLIC_BASE_URL` (oder eine eigene
  `https`-URL), siehe unten.
- Prompt-Referenzen heißen `<<<image_1>>>`, `<<<video_1>>>`, `<<<element_1>>>`,
  `<<<voice_1>>>`; die `@Name`-Schreibweise der Kling-App gilt für die API nicht.
- `DELETE` bricht einen Kling-Job nicht ab (Kling hat keinen Abbruch); er läuft
  weiter und wird berechnet.
- Lip Sync ohne `audio.end_ms`: Die Synchronisation endet an der gemessenen Länge
  der Audiodatei. Findet Kling kein Gesicht, scheitert der Job mit
  `invalid_request`.
- Motion Control: Ohne Angabe gilt `character_orientation=image`.
- Alle Kling-Generierungen sind noch nicht live getestet; unerwartete
  Antwortformate sind daher möglich.

## Google: `region_restricted`, Inhaltsfilter, leere Ergebnisse

- Veo meldet blockierte Videos über die RAI-Felder; der Proxy macht daraus einen
  Job mit `error.code: content_policy`. Ein Veo-Ergebnis ohne Video ohne Grund
  erscheint als `upstream_error: Veo returned no video`.
- Omni-Edit und -Extend über die Gemini API sind laut Recherche im EWR
  eingeschränkt; Vertex ist der Standard. Bei einem Omni-Ergebnis ohne Video lautet
  der Fehler `content_policy: Omni returned no video`.
- Ein frisch fertiger Gemini-Output kann kurz noch nicht herunterladbar sein; der
  Job bleibt dann `in_progress` mit `provider_status: finalizing`.
- Veo-Extension über die Gemini API funktioniert nur mit Videos, die dieser Proxy
  erzeugt hat (`task_id`); für fremde Videos das Vertex-Backend verwenden.
- `Google models do not accept input_reference uploads`: Referenzen über
  `references[]` senden.

## Webhooks

- `webhook_url requires WEBHOOK_SECRET to be configured on the proxy`:
  `WEBHOOK_SECRET` setzen und den Proxy neu starten.
- `webhook_url must be an absolute https URL`: nur HTTPS-Ziele.
- Es kommt nichts an: Der Proxy liefert nicht an Hosts, die auf private,
  Loopback- oder Link-Local-Adressen auflösen, und folgt keinen Redirects. Nach
  `WEBHOOK_MAX_ATTEMPTS` Fehlversuchen (Standard 8) wird die Auslieferung
  verworfen; die Warnung steht im Log.

## `Name or service not known` / `real_human_asset_error`

DNS im Container ist zeitweise ausgefallen. Der Text stammt aus dem
Betriebssystem und erreicht den Client als `error.message` eines
`video-rh-…`-Jobs. Bevorzugt tritt das bei mehreren gleichzeitigen Aufträgen auf,
weil dabei mehrere Namensauflösungen parallel starten.

Der Proxy fängt das auf zwei Ebenen ab: jeder Anbieter-Aufruf wird bei einem
Verbindungsfehler bis zu `UPSTREAM_RETRY_ATTEMPTS` mal wiederholt, und ein Job,
dessen Aufrufe trotzdem alle scheitern, wird nicht mehr endgültig abgebrochen. Er
wartet stattdessen mit Backoff (`ASSET_TRANSIENT_RETRY_SECONDS`) und läuft weiter,
sobald das Netz wieder da ist. Erst `ASSET_MAX_PROCESSING_SECONDS` beziehungsweise
`ASSET_JOB_TTL_SECONDS` beenden ihn hart. Im Log erscheinen währenddessen `could
not connect` und `could not reach ModelArk`.

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
diesen Wert deshalb nicht. Die Restmenge steht im Billing Center unter **Resource
package**. Einen von ModelArk bei einer Generierung gelieferten Package- oder
Billing-Fehler reicht der Proxy mit seinem originalen Fehlercode an LiteLLM und UI
weiter.

## `PUBLIC_BASE_URL is required` / `public_base_url_required`

Ein lokales Referenzvideo (oder eine `data:`-/Upload-Quelle, die ein Anbieter per
URL abrufen muss) wurde übergeben, aber der Proxy besitzt keine öffentliche
HTTPS-URL. `PUBLIC_BASE_URL` setzen und sicherstellen, dass die erzeugte
`/media/reference/...`-URL aus dem Internet erreichbar ist. Auch der automatische
Real-Human-Workflow benötigt diese URL für die Asset-Registrierung. Google-Modelle
brauchen sie nicht.

## `Reference URLs must be absolute HTTP(S) URLs`

Relative Pfade, lokale Dateipfade und `file://` sind nicht erlaubt. Eine
öffentliche URL, einen Upload oder für Bilder eine `data:`-URI verwenden.

## Real-person-/Face-Fehler von ModelArk

Ein gewöhnlicher Upload mit realem Gesicht ist nicht freigegeben. Die Referenz mit
`real_human: true` markieren, damit der Proxy sie in der konfigurierten,
autorisierten Asset-Gruppe registriert. Alternativ einen zugelassenen Digital
Character oder einen weiterhin vertrauenswürdigen Originaloutput verwenden.

## `video_not_ready`

Der Download wurde vor Abschluss angefordert. Status pollen und erst bei
`completed` laden.

## `output_expired`

Der lokal gespeicherte Output eines Google- oder Kling-Jobs ist nach
`PROVIDER_JOB_TTL_SECONDS` (Standard 48 Stunden) entfernt worden. Ergebnisse
rechtzeitig herunterladen.

## Letztes Frame fehlt

Das letzte Frame gibt es nur bei Seedance. Der Task wurde nicht mit
`return_last_frame: true` erstellt oder das gewählte Modell unterstützt die
Funktion nicht; der Proxy antwortet dann mit 404.

## First-/Last-Frame kann nicht mit Referenzen gemischt werden

ModelArk behandelt exakte Frame-Steuerung und multimodale Referenzen als
gegenseitig ausschließende Szenarien. Entweder nur `first_frame`/`last_frame` oder
nur Referenzen einsetzen. In einem multimodalen Prompt kann ein Bild stattdessen
semantisch als Anfang oder Ende beschrieben werden, ohne eine Frame-Rolle zu
verwenden.

## `does not support omni_reference_task_type`

Der Task-Typ wurde an ein Modell gesendet, das ihn nicht kennt. `auto`,
`reference`, `edit` und `extend` gibt es ausschließlich bei Seedance 2.5; die
2.0-Familie lehnt das Feld vor dem Upstream-Aufruf mit HTTP 400 ab. Das Feld
weglassen und die Bearbeitungs- oder Verlängerungsabsicht im Prompt formulieren.
Welche Werte ein Modell akzeptiert, steht in `GET /v1/models` unter
`capabilities.task_types`; eine leere Liste bedeutet, dass es keinen Task-Typ gibt.

## Modell oder Parameter nicht unterstützt

`GET /v1/models`, den IAM-Zugriff und die aktivierte Modell-ID prüfen. Seedance
2.0 Fast unterstützt nicht automatisch sämtliche Optionen anderer
Seedance-Versionen. Insbesondere Auflösung, Dauer, Service-Tier, Seed, Frames und
Kamerafixierung sind modellabhängig. Seedance 1.5 Pro ist abgekündigt (Abschaltung
2026-11-11, Nachfolger `dreamina-seedance-2-0-mini`).

## LiteLLM findet die Video-ID nicht / Funktion fehlt über LiteLLM

Für Folgeaufrufe genau die von LiteLLM ausgegebene ID verwenden. LiteLLM kodiert
Routing-Informationen in der ID; eine herauskopierte rohe `cgt-…`- oder
`vid-…`-ID kann am Gateway vorbeigeroutet werden. Der Proxy akzeptiert beide
Formen, wenn er direkt angesprochen wird.

Bestimmte Funktionen reicht LiteLLM nicht durch: Liste (`GET /v1/videos`, 400),
`DELETE` (405) und `?variant=` (es kommt immer das Hauptvideo). Diese Aufrufe direkt
am Proxy mit dem Proxy-Key ausführen. Erwartet `extra_body` im Remix-, Edit- oder
Extension-Aufruf Anbieterfelder, müssen sie dort stehen; `/v1/videos/extensions`
verlangt bei LiteLLM `seconds`. LiteLLM < 1.100 sendet Formularfelder als
JSON-Strings, was der Proxy für Booleans und Integer umwandelt.
