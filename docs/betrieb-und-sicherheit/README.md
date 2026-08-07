# Betrieb und Sicherheit

## Netz und TLS

`PUBLIC_BASE_URL` muss bei Video-Uploads öffentlich per HTTPS erreichbar sein.
Vor dem FastAPI-Dienst sollte ein Reverse Proxy TLS terminieren. Die Route für
temporäre Referenzen ist absichtlich ohne Bearer-Key erreichbar, weil ModelArk
keinen Proxy-Key mitsendet. Die Dateinamen enthalten 256 Bit Zufall und dienen
als nicht erratbare Capability-URL. Sie haben keine Verzeichnisansicht, werden
nicht gecacht und verschwinden nach der konfigurierten TTL.

Empfohlene öffentliche Reverse-Proxy-Regeln:

- UI-Hostname → Studio-Container; Login mit Username und Passwort,
- API-Hostname beziehungsweise LiteLLM-Netz → Proxy; Bearer-Key erforderlich,
- ausschließlich `/media/reference/<zufälliger Token>` ohne Bearer-Key zum
  Proxy durchreichen, damit BytePlus Referenzen laden kann,
- TLS, Request-Größenlimit und zusätzliche Edge-Rate-Limits aktivieren.

Der Docker-Stack setzt `REQUIRE_PROXY_API_KEY=true` und startet ohne mindestens
32 Zeichen langen `PROXY_API_KEY` nicht. Direkte Client-IP-Header werden nicht
pauschal von beliebigen Absendern vertraut; ein vorgeschalteter Proxy muss als
vertrauenswürdiger Forwarder gezielt konfiguriert werden.

## Schlüssel

Kryptografisch zufällige Werte lassen sich beispielsweise mit
`openssl rand -hex 32` erzeugen. Für `PROXY_API_KEY`, `UI_PASSWORD` und
`UI_SESSION_SECRET` müssen jeweils unabhängige Werte verwendet werden. In einer
Produktionsumgebung sollten sie als Container-Secrets oder über den Secret Store
der Deployment-Plattform injiziert werden; eine lokale `.env` ist nur die
einfachste Betriebsvariante.

- `ARK_API_KEY` nur im Proxy hinterlegen, nie in LiteLLM-Clients.
- Zwischen LiteLLM und Proxy `PROXY_API_KEY` setzen.
- Für die UI `UI_USERNAME`, ein mindestens 16 Zeichen langes `UI_PASSWORD` und
  einen unabhängigen `UI_SESSION_SECRET` mit mindestens 32 Zeichen setzen.
- Zwischen externen Clients und LiteLLM einen separaten Gateway-Key nutzen.
- Schlüssel regelmäßig rotieren und niemals committen.

Das UI verwendet eine signierte, `HttpOnly`-, `SameSite=Strict`-Session. Unter
HTTPS wird ein `Secure`-Cookie mit `__Host-`-Präfix gesetzt. Fehlanmeldungen
werden pro Client sowie global gedrosselt. Antworten tragen CSP-, Frame-,
MIME-, Referrer- und Permissions-Sicherheitsheader. Login und API-Schlüssel
werden nur serverseitig verglichen und nicht an den Browser ausgeliefert.

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
Task-IDs entgegen. Das UI-Backend pollt seine aktiven Jobs separat; andere
API-Clients müssen Statusabfragen selbst einplanen. Ein vorgeschaltetes LiteLLM
Gateway routet diese Abfragen, startet aber kein automatisches Job-Polling.
Real-Human-Asset- und Provider-Jobs werden dagegen unabhängig davon durch die
persistenten Proxy-Worker weiterverarbeitet. Lokale HTTP-Pools und das
gebündelte UI-/Worker-Polling sind konfigurierbar; höhere Werte erhöhen aber
nicht die ModelArk-Rechenquote. RPM-, QPM- und Concurrency-Limits des
aktivierten Modells beziehungsweise Endpoints bleiben maßgeblich. Ein
`queued`-Status bei vielen Aufgaben ist normal und kein lokaler Timeout.
