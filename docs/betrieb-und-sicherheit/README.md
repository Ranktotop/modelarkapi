# Betrieb und Sicherheit

## Netz und TLS

`PUBLIC_BASE_URL` muss bei Video-Uploads öffentlich per HTTPS erreichbar sein.
Vor dem FastAPI-Dienst sollte ein Reverse Proxy TLS terminieren. Die Route für
temporäre Referenzen ist absichtlich ohne Bearer-Key erreichbar, weil ModelArk
keinen Proxy-Key mitsendet; zufällige Dateinamen dienen als Capability-URL.

## Schlüssel

- `ARK_API_KEY` nur im Proxy hinterlegen, nie in LiteLLM-Clients.
- Zwischen LiteLLM und Proxy `PROXY_API_KEY` setzen.
- Zwischen externen Clients und LiteLLM einen separaten Gateway-Key nutzen.
- Schlüssel regelmäßig rotieren und niemals committen.

## Temporäre und dauerhafte Daten

Uploads werden in `MEDIA_DIR` abgelegt und nach `MEDIA_TTL_SECONDS` bereinigt.
Die Bereinigung läuft beim Proxy-Start, bei Generierungen und zusätzlich
periodisch. Der Standard sind 24 Stunden. ModelArk-Taskdaten sind ebenfalls begrenzt
verfügbar, und signierte Resultat-URLs laufen typischerweise nach 24 Stunden
ab. Produktionssysteme sollten erfolgreiche Videos sofort in kontrollierten
Object Storage kopieren.

Das Web Studio archiviert fertige Videos absichtlich nicht. Seine SQLite-Datei
enthält nur Prompt, Parameter, Task-ID und Status und löscht abgeschlossene
Einträge nach `UI_JOB_TTL_SECONDS`. Damit entsteht keine dauerhafte Galerie.

## Download-Schutz

Der Proxy streamt nur HTTPS-Ergebnisse von explizit erlaubten Host-Suffixen.
`ALLOWED_DOWNLOAD_HOST_SUFFIXES` darf nur um vertrauenswürdige ModelArk-/TOS-
Domains erweitert werden. Damit wird verhindert, dass eine manipulierte
Upstream-Antwort den Proxy beliebige interne URLs abrufen lässt.

## Datenschutz und Personen

Für reale Personen müssen Einwilligung, Zweck und Gültigkeitszeitraum zur
Asset-Autorisierung passen. Die OpenAI-`user`-Kennung wird als
`safety_identifier` an ModelArk gesendet; empfohlen ist eine stabile,
datensparsame, gehashte Kennung mit höchstens 64 Zeichen. Roh-E-Mailadressen
oder Namen sollten nicht verwendet werden.

Callbacks werden direkt an ModelArk weitergereicht. Der Betreiber muss am
Callback-Endpunkt Authentizität, Idempotenz, kurze Antwortzeiten und Schutz
gegen Replay beziehungsweise unerwartete Payloads selbst sicherstellen.

## Parallelität und Quoten

Der lokale Stack blockiert nicht bis zum fertigen Video. Er nimmt asynchron
Task-IDs entgegen und pollt Resultate separat. Lokale HTTP-Pools und das
gebündelte Status-Polling sind konfigurierbar; höhere Werte erhöhen aber nicht
die ModelArk-Rechenquote. RPM-, QPM- und Concurrency-Limits des aktivierten
Modells beziehungsweise Endpoints bleiben maßgeblich. Ein `queued`-Status bei
vielen Aufgaben ist normal und kein lokaler Timeout.
