# Entwicklung und Tests

## Entwicklungsserver über VS Code starten

Entwicklungsserver werden ausschließlich lokal über `.vscode/launch.json`
gestartet. In VS Code unter **Run and Debug** steht dafür die Compound-
Konfiguration **Local Full Stack** bereit. Sie startet:

- Proxy auf `http://127.0.0.1:8081`,
- Studio-Backend auf `http://127.0.0.1:3000`,
- Vite-Frontend auf `http://127.0.0.1:5173`.

Die Einzelkonfigurationen (Proxy, Studio-Backend, Studio-Frontend) können
verwendet werden, wenn nur eine Komponente benötigt wird. Werte aus `.env` werden
von den Python-Konfigurationen geladen; Secrets stehen nicht in der Launch-Datei.
Der Proxy nutzt bewusst nicht Port 8080, den ein anderes lokales Projekt belegt.

Nicht verwendet werden für die Entwicklung: `docker compose up`, `docker compose
run`, `docker run` sowie ein direkt gestartetes `uvicorn` oder Vite. Docker ist
ausschließlich für Build-/Deployment-Prüfungen vorgesehen und wird nur auf
ausdrückliche Anforderung gestartet.

## Testumgebung

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest                       # tests/ und ui/tests
ruff check .
cd ui/frontend && npm ci && npm test && npm run build
```

- `pytest` führt `tests/` und `ui/tests` aus (`ui/backend` liegt im Pfad).
- Frontend: `npm test` in `ui/frontend` kompiliert die Tests und führt sie mit
  `node --test` aus (derzeit die Capability-Auswertung); `npm run build` prüft
  zusätzlich die Typen.

Die automatisierten Tests verwenden ausschließlich simulierte Upstreams
(Mock-Transports). Sie prüfen unter anderem:

| Bereich | Dateien |
|---|---|
| Eingang, Wire-Format, IDs, Webhooks | `test_proxy.py`, `test_wire_format.py`, `test_webhooks.py` |
| Validierung und Capabilities | `test_validation.py`, `test_models.py`, `test_references.py`, `test_prompt_guides.py` |
| Seedance | `test_seedance_fields.py`, `test_seedance_unified.py` |
| Google | `test_providers.py`, `test_veo.py`, `test_omni.py`, `test_provider_jobs.py` |
| Kling | `test_kling*.py` (Basis, Omni, Assets, Audio, Commerce, Effekte, Lip Sync) |
| Credentials | `test_credentials.py` |
| Studio-Backend | `ui/tests/test_server.py` |

Die Concurrency-Tests verwenden verzögerte Mock-Upstreams und prüfen überlappende
Create-Aufrufe sowie begrenztes paralleles Status-Polling.

## LiteLLM-Ende-zu-Ende-Suite

`tests/integration/test_litellm.py` startet echte LiteLLM-Proxies als Subprozess
vor dem Proxy; dessen Anbieter sind skriptgesteuerte Fakes. Die Suite ist opt-in:

```bash
LITELLM_VENVS=/venv-a:/venv-b pytest -m litellm
```

Jede virtuelle Umgebung braucht `litellm[proxy]`. Getestet wurden LiteLLM 1.95.0,
1.104.2 und 1.105.0 (27 Tests, einschließlich OpenAI-Characters). Die Ergebnisse (was LiteLLM durchreicht und was nicht) stehen
in der [LiteLLM-Integration](../litellm-integration/README.md#getestete-litellm-versionen).

## OpenAPI manuell prüfen

Nach lokalem Start sind `/openapi.json` und `/docs` verfügbar. Diese Ansicht
dokumentiert die Endpunkte; die flexiblen JSON-/Multipart-Felder sind in der
Markdown-API-Referenz und in der SPEC vollständiger beschrieben.

## Prompt Guides

Guides liegen als Markdown unter `prompt_guides/`; `manifest.yaml` ordnet sie
Modell-ID-Präfixen zu (der längste passende Präfix gewinnt):

| Guide | Modelle (Präfix) |
|---|---|
| `seedance_2_5` | `dreamina-seedance-2-5` |
| `seedance_2_0_fast` | `dreamina-seedance-2-0` (gesamte 2.0-Serie) |
| `veo_3_1` | `veo-3.1-` |
| `gemini_omni_flash` | `gemini-omni-` |
| `kling_3_0` | `kling-3.0` (3.0 und Turbo) |
| `kling_omni` | `kling-3.0-omni`, `kling-o1` |
| `kling_2_x` | `kling-2.` |
| `kling_tools` | die virtuellen Kling-Modelle |

Seedance 1.x hat keinen Guide. Ein neuer Guide braucht eine Datei und einen
Manifest-Eintrag (`id`, `file`, `title`, `language`, `updated`, `models`); fehlt
die Datei, scheitert der Start. Die Guides sind über
`GET /v1/prompt-guides` (ohne Proxy-Key), `GET /v1/models/{id}` und den Link
im LiteLLM-Export (`model_info.prompt_guide_url`) abrufbar.

## Live-Tests

Ein Serverstart autorisiert keine kostenpflichtige oder biometrische Generierung.
Live-Tests laufen nur, wenn sie ausdrücklich angefordert werden. Reihenfolge:
`/health` und `/v1/real-human/configuration` zuerst, dann erst Assets oder
Generierungen.

Stand:

| Bereich | Live geprüft |
|---|---|
| Credential-Prüfungen (Gemini, Vertex, Kling, LiteLLM `model/info`) | ja, kostenfrei (ADR-001) |
| Veo 3.1 Lite auf Vertex (Region `global`, 4 s, 720p, mit Ton) | ja, einmalig; ohne Provisioned Throughput; Ergebnis inline als Base64 |
| Omni auf der Gemini API | einmaliger Direktaufruf in ADR-001; Generierung über den Proxy **nicht** getestet |
| Omni auf Vertex, Veo auf der Gemini API | nicht |
| Kling (alle Tasks, Lip Sync, Commerce, Audio, Assets) | **nicht** |
| Seedance mit freigeschaltetem Real-Human-Asset | **nicht**; erst wenn Gruppe und Asset `Active` sind |
| Seedance (normale Generierung) | über simulierte Antworten; Live-Test mit 4 s, 480p, ohne Audio vorgesehen |

Voraussetzungen für den Real-Human-Live-Test:

- richtige Fast-Modell-ID oder Endpoint-ID im Account aktiviert
- Real-Human-Gruppe und verwendetes Asset im Status `Active`
- korrekte Einwilligung und Nutzungsrechte
- bei Video-Upload öffentliche HTTPS-Erreichbarkeit des Proxys
- minimales kostenkontrolliertes Profil: 4 Sekunden, 480p, Audio aus

Erst danach werden nacheinander Create, Polling, Download und optionaler Last-Frame-
Download geprüft. Schlüssel und signierte Ergebnis-URLs dürfen nicht in
Testausgaben committed werden.

Offene Punkte aus der Recherche (`tasks/research/`), die nur Live-Tests klären:
ob Kling 3.0 Turbo immer mit Ton rendert, ob Seedance 2.x einen gesetzten `seed`
annimmt, die Kosten der Kling-Selection-Schritte sowie Details zu Rate-Limits der
Gemini API.

## Qualitätscheck vor einem Commit

```bash
ruff check .
pytest
cd ui/frontend && npm test && npm run build
git diff --check
git status --short
```
