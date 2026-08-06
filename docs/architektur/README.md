# Architektur

## Datenfluss

```text
Client → LiteLLM Gateway → ModelArk OpenAI Video Proxy → BytePlus ModelArk
Browser → Seedance Web Studio ────────────────┘
                                      ↓                         ↓
                         temporäre Referenz-URL        asynchroner Seedance-Task
```

LiteLLM verwendet seinen OpenAI-Videoadapter. Dieser Proxy nimmt die
OpenAI-ähnliche Anfrage entgegen, baut daraus einen ModelArk-Task und gibt die
Task-ID in einem OpenAI-Videoobjekt zurück. Status und Ergebnis werden danach
über eigene GET-Endpunkte abgefragt.

## Komponenten

- `app.py`: HTTP-Routen, Authentifizierung, Validierung und Streaming.
- `translation.py`: Feld-, Format- und Statusübersetzung.
- `client.py`: authentifizierter asynchroner ModelArk-Client.
- `media.py`: Signaturprüfung und zeitlich begrenzte Ablage von Uploads.
- `config.py`: Konfiguration aus `.env` beziehungsweise Prozessumgebung.
- `schemas.py`: OpenAI-nahe Video- und Listenobjekte.
- `ui/backend/server.py`: Single-User-Session, temporäres Jobregister und
  serverseitige Kommunikation mit dem Proxy.
- `ui/frontend`: React-/TypeScript-Studio, das als statische Anwendung vom
  UI-Backend ausgeliefert wird.

## Übersetzungsgrenze

Der Proxy ist absichtlich zustandsarm. ModelArk ist die maßgebliche Quelle für
Taskstatus und Resultate. Lokaler Zustand wird nur für hochgeladene
Referenzdateien gehalten. Daher bleibt ein Task auch nach einem Neustart des
Proxys abrufbar, solange ModelArk seinen Datensatz noch aufbewahrt.

Standardfelder werden übersetzt; ModelArk-Funktionen ohne OpenAI-Entsprechung
werden als klar benannte Erweiterungen angenommen. Für Sonderfälle steht das
rohe `content`-Array zur Verfügung. Es wird weitgehend unverändert an ModelArk
weitergereicht, unterliegt aber den Referenz-Limits des Proxys.

## Parallelität

Proxy und UI-Backend verwenden durchgehend asynchrone HTTP-Clients. Ein
Create-Aufruf wartet nur auf die ModelArk-Task-ID und niemals auf die eigentliche
Videogenerierung. Während Seedance einen Task rendert, hält der Container keine
offene Generierungsanfrage und kann weitere Tasks, Statusabfragen, Uploads und
Downloads annehmen.

Beide internen HTTP-Pools erlauben standardmäßig 100 gleichzeitige
Upstream-Verbindungen. Das Status-Polling der UI verarbeitet laufende Jobs in
begrenzten parallelen Gruppen, damit ein langsamer Statusaufruf nicht alle
anderen Jobs verzögert und ModelArk trotzdem nicht mit unbegrenzten Abfragen
überlastet wird.

Der UI-Container läuft absichtlich mit einem Uvicorn-Prozess: Die Arbeit ist
I/O-lastig, und mehrere Prozesse würden das SQLite-Jobregister sowie Cleanup-
Schleifen unnötig duplizieren. Horizontale UI-Replikation ist für diesen
Single-User-Betrieb nicht vorgesehen.

## Kein Bestandteil des Proxys

- Er erstellt oder genehmigt keine BytePlus-Assets.
- Er umgeht keine Gesichts-, Rechte- oder Inhaltsprüfung.
- Er speichert Ergebnisse nicht dauerhaft.
- Er wartet bei `POST /v1/videos` nicht auf die fertige Generierung.
- Er ersetzt keine öffentlich erreichbare Medienablage für Video-Uploads.
