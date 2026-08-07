# Entwicklung und Tests

## Entwicklungsserver über VS Code starten

Entwicklungsserver werden ausschließlich lokal über
`.vscode/launch.json` gestartet. In VS Code unter **Run and Debug** steht dafür
die Compound-Konfiguration **Local Full Stack** bereit. Sie startet:

- ModelArk-Proxy auf `http://127.0.0.1:8081`,
- Studio-Backend auf `http://127.0.0.1:3000`,
- Vite-Frontend auf `http://127.0.0.1:5173`.

Die Einzelkonfigurationen können verwendet werden, wenn nur eine Komponente
benötigt wird. Werte aus `.env` werden von den Python-Konfigurationen geladen;
Secrets stehen nicht in der Launch-Datei. Docker ist ausschließlich für
Build-/Deployment-Prüfungen vorgesehen und wird nicht zum Starten einer
Entwicklungsinstanz verwendet.

## Testumgebung

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
ruff check .
PYTHONPATH=ui/backend pytest -q tests ui/tests
cd ui/frontend && npm ci && npm run build
```

Die automatisierten Tests simulieren ModelArk und Ergebnisdownloads. Sie
prüfen Übersetzung, Upload-Sniffing, Assets, Rollen, Tasklisten, Status,
Authentifizierung und Streaming, ohne externe Anfrage und ohne Kosten. Die
Concurrency-Tests verwenden verzögerte Mock-Upstreams und prüfen überlappende
Create-Aufrufe sowie begrenztes paralleles Status-Polling.

## OpenAPI manuell prüfen

Nach lokalem Start sind `/openapi.json` und `/docs` verfügbar. Diese Ansicht
dokumentiert die Endpunkte; die flexiblen JSON-/Multipart-Felder sind in der
vorliegenden Markdown-API-Referenz vollständiger beschrieben.

## Verschobener Live-Test

Der Live-Test bleibt bewusst am Ende. Voraussetzungen:

- richtige Fast-Modell-ID oder Endpoint-ID im Account aktiviert
- Real-Human-Gruppe und verwendetes Asset im Status `Active`
- korrekte Einwilligung und Nutzungsrechte
- bei Video-Upload öffentliche HTTPS-Erreichbarkeit des Proxys
- minimales kostenkontrolliertes Profil: 4 Sekunden, 480p, Audio aus

Erst danach werden nacheinander Create, Polling, MP4-Download und optionaler
Last-Frame-Download gegen ModelArk geprüft. Der Schlüssel und signierte
Ergebnis-URLs dürfen nicht in Testausgaben committed werden.

## Qualitätscheck vor einem Commit

```bash
ruff check .
pytest -q
git diff --check
git status --short
```
