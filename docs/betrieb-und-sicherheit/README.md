# Betrieb und Sicherheit

## Live-API-Sicherheit

- Ein lokaler Serverstart berechtigt nicht zu einer kostenpflichtigen
  Generierung bei Seedance, Veo, Omni oder Kling.
- Zuerst `GET /health` und den read-only-Aufruf `GET /v1/real-human/configuration`
  nutzen; beide verursachen keine Kosten.
- Ein kostenpflichtiger oder biometrischer Live-Test (Generierung, Real-Human-
  Asset, Kling-Selection-Schritte, Lip-Sync-Gesichtserkennung) läuft nur, wenn er
  ausdrücklich angefordert wurde.
- Tests nutzen ausschließlich simulierte Upstreams.

## Netz und TLS

`PUBLIC_BASE_URL` muss bei Uploads, die an Seedance oder Kling gehen, öffentlich per
HTTPS erreichbar sein. Vor dem FastAPI-Dienst sollte ein Reverse Proxy TLS
terminieren. Die Route für temporäre Referenzen ist absichtlich ohne Bearer-Key
erreichbar, weil die Anbieter keinen Proxy-Key mitsenden. Die Dateinamen enthalten
256 Bit Zufall und dienen als nicht erratbare Capability-URL. Sie haben keine
Verzeichnisansicht, werden nicht gecacht und verschwinden nach der konfigurierten
TTL.

Empfohlene öffentliche Reverse-Proxy-Regeln:

- UI-Hostname → Studio-Container; Login mit Username und Passwort,
- API-Hostname beziehungsweise LiteLLM-Netz → Proxy; Bearer-Key erforderlich,
- ausschließlich `/media/reference/<zufälliger Token>` ohne Bearer-Key zum Proxy
  durchreichen, damit ModelArk und Kling Referenzen laden können,
- TLS, Request-Größenlimit und zusätzliche Edge-Rate-Limits aktivieren.

Der Docker-Stack setzt `REQUIRE_PROXY_API_KEY=true` und startet ohne mindestens
32 Zeichen langen `PROXY_API_KEY` nicht. Direkte Client-IP-Header werden nicht
pauschal von beliebigen Absendern vertraut; ein vorgeschalteter Proxy muss als
vertrauenswürdiger Forwarder gezielt konfiguriert werden.

## Schlüssel und Secrets

Kryptografisch zufällige Werte lassen sich beispielsweise mit
`openssl rand -hex 32` erzeugen. Für `PROXY_API_KEY`, `UI_PASSWORD`,
`UI_SESSION_SECRET` und `WEBHOOK_SECRET` müssen jeweils unabhängige Werte
verwendet werden. In einer Produktionsumgebung sollten sie als Container-Secrets
oder über den Secret Store der Deployment-Plattform injiziert werden; eine lokale
`.env` ist nur die einfachste Betriebsvariante.

- `ARK_API_KEY`, `BYTEPLUS_*`, `GEMINI_API_KEY`, `KLING_API_KEY` nur im Proxy
  hinterlegen, nie in LiteLLM-Clients oder im Browser.
- Die Vertex-Service-Account-JSON liegt in `./secrets` (nicht in Git) und wird
  schreibgeschützt nach `/app/secrets` gemountet; `.env` enthält nur den
  Dateinamen (`GOOGLE_CREDENTIALS_FILE`).
- Entwicklungs-Launch-Konfigurationen laden Secrets aus `.env`. Secret-Werte gehören
  weder in `.vscode/launch.json` noch in Commits, Logs, Fehlermeldungen oder
  Screenshots.
- Zwischen LiteLLM und Proxy `PROXY_API_KEY` setzen.
- Für die UI `UI_USERNAME`, ein mindestens 16 Zeichen langes `UI_PASSWORD` und einen
  unabhängigen `UI_SESSION_SECRET` mit mindestens 32 Zeichen setzen.
- Zwischen externen Clients und LiteLLM einen separaten Gateway-Key nutzen.
- Schlüssel regelmäßig rotieren und niemals committen.

Das UI verwendet eine signierte, `HttpOnly`-, `SameSite=Strict`-Session. Unter
HTTPS wird ein `Secure`-Cookie mit `__Host-`-Präfix gesetzt. Fehlanmeldungen werden
pro Client sowie global gedrosselt. Antworten tragen CSP-, Frame-, MIME-, Referrer-
und Permissions-Sicherheitsheader. Login und API-Schlüssel werden nur serverseitig
verglichen und nicht an den Browser ausgeliefert.

## Provider-Credentials im Betrieb

Jeder Anbieter wird einzeln mit einem kostenfreien Read-only-Aufruf geprüft;
`/health` zeigt den Zustand unter `providers`. Ein ungültiger Anbieter sperrt nur
seine eigenen Routen (`503 upstream_credentials_invalid`). Details und das
Verhalten bei Netzwerkausfällen stehen unter
[Installation und Konfiguration](../installation-und-konfiguration/README.md#modelllisten).

## Temporäre und dauerhafte Daten

Uploads werden in `MEDIA_DIR` abgelegt und nach `MEDIA_TTL_SECONDS` bereinigt. Die
Bereinigung läuft beim Proxy-Start, bei Generierungen und zusätzlich periodisch.
Der Standard sind 24 Stunden.

Der Proxy hält außerdem Zustand, der ein Volume braucht (im Docker-Stack
`server_state`):

- das Jobregister für Google und Kling samt Webhook-Zustand (`PROVIDER_JOB_DB`),
- gespeicherte Ergebnisse (`OUTPUT_DIR`, Inline-Bytes von Vertex und Omni,
  heruntergeladene Kling-Dateien),
- die Real-Human-Asset-Jobs (`ASSET_JOB_DB`).

Jobs und Outputs laufen nach `PROVIDER_JOB_TTL_SECONDS` (Standard 48 Stunden) ab
und werden beim Start und periodisch entfernt. ModelArk-Taskdaten sind ebenfalls
begrenzt verfügbar, und signierte Resultat-URLs laufen typischerweise nach 24
Stunden ab. Produktionssysteme sollten erfolgreiche Videos sofort in kontrollierten
Object Storage kopieren.

Das Studio archiviert fertige Videos absichtlich nicht. Seine SQLite-Datei enthält
nur Prompt, Parameter, Job-ID und Status und löscht abgeschlossene Einträge nach
`UI_JOB_TTL_SECONDS`. Damit entsteht keine dauerhafte Galerie.

## Download- und SSRF-Schutz

- Ergebnisdownloads streamt der Proxy nur über HTTPS von explizit erlaubten
  Host-Suffixen: `ALLOWED_DOWNLOAD_HOST_SUFFIXES` (ModelArk),
  `GOOGLE_DOWNLOAD_HOST_SUFFIXES`, `KLING_DOWNLOAD_HOST_SUFFIXES`. Sie dürfen nur
  um vertrauenswürdige Domains erweitert werden, damit eine manipulierte
  Upstream-Antwort den Proxy keine beliebigen internen URLs abrufen lässt.
- Ruft der Proxy eine vom Client genannte Referenz-URL selbst ab (Google, Kling-
  Bilder), gilt: nur `https`, Hostauflösung mit Ablehnung privater,
  Loopback-, Link-Local- und Multicast-Adressen (auch nach Redirects, höchstens 3),
  Größenlimit je Typ, Timeout und Dateisignaturprüfung.
- Webhook-Ziele müssen `https` sein und beim Create wie vor jeder Auslieferung auf
  eine öffentliche Adresse auflösen; der Proxy folgt keinen Redirects.
- `GET /v1/providers/kling/account/costs` ist auf einen Aufruf pro
  `KLING_COSTS_MIN_INTERVAL_SECONDS` (Standard 1 s) gedrosselt.
- `data:`-Referenzen sind auf `MAX_INLINE_REFERENCE_BYTES` begrenzt.
- Native Kling-Pfade sind eine Allowlist dokumentierter Präfixe; Bild-APIs und
  Virtual Try-On sind ausgeschlossen.

## Webhooks

`webhook_url` verlangt `WEBHOOK_SECRET`; Ereignisse sind nach *Standard Webhooks*
signiert. Der Empfänger prüft Signatur, Zeitstempel (Replay) und die `webhook-id`
(Idempotenz) selbst. Das native Seedance-`callback_url` ist dagegen **unsigniert**:
Wer es verwendet, muss Authentizität, Idempotenz, kurze Antwortzeiten und Schutz
gegen Replay beziehungsweise unerwartete Payloads am Callback-Endpunkt selbst
sicherstellen. Empfohlen ist `webhook_url`.

## Datenschutz und Personen

Für reale Personen müssen Einwilligung, Zweck und Gültigkeitszeitraum zur
Asset-Autorisierung passen (nur Seedance). Die OpenAI-`user`-Kennung wird als
`safety_identifier` an ModelArk gesendet; empfohlen ist eine stabile, datensparsame,
gehashte Kennung. Kennungen über 64 Zeichen hasht der Proxy selbst mit SHA-256.
Roh-E-Mail-Adressen oder Namen sollten nicht verwendet werden.

Bilder, Videos und Audio werden an den gewählten Anbieter übertragen (bei Google als
Bytes, bei Seedance und Kling über temporäre URLs). Das Studio zeigt vor dem Start
an, wer abrechnet.

## Parallelität und Quoten

Der Stack blockiert nicht bis zum fertigen Video. Er nimmt asynchron Job-IDs
entgegen. Das UI-Backend pollt seine aktiven Jobs separat; andere API-Clients müssen
Statusabfragen selbst einplanen oder `webhook_url` nutzen. Ein vorgeschaltetes
LiteLLM Gateway routet diese Abfragen, startet aber kein automatisches Job-Polling.
Real-Human- und mehrstufige Kling-Jobs werden unabhängig davon durch die
persistenten Proxy-Worker weiterverarbeitet. Lokale HTTP-Pools und das gebündelte
UI-/Worker-Polling sind konfigurierbar; höhere Werte erhöhen aber nicht die Quote
beim Anbieter. RPM-, QPM- und Concurrency-Limits des jeweiligen Anbieters
(ModelArk-Endpoint, Gemini/Vertex-Quota, Kling-Parallelität) bleiben maßgeblich.
Ein `queued`-Status bei vielen Aufgaben ist normal und kein lokaler Timeout.
Anbieter-Antworten mit Rate-Limit (`429`) kommen als `rate_limited` mit
`retryable: true` zurück; Kling meldet Abrechnungsfehler (`billing`, 402)
getrennt davon.
