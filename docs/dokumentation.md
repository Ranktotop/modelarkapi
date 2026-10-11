# AI Video Studio – Dokumentation

Diese Dokumentation beschreibt Installation, API und Betrieb des Proxys, der
OpenAI-/LiteLLM-Videoanfragen in die asynchronen APIs von Seedance (BytePlus
ModelArk), Google Veo 3.1 und Gemini Omni Flash (Gemini API und/oder Vertex AI)
sowie Kling übersetzt. Der Proxy führt keine Videogenerierung selbst aus. Paket-
und Image-Namen (`modelark-openai-video-proxy`, `ranktotop/modelarkapi`) sind
unverändert.

Der verbindliche API-Vertrag steht in [SPEC.md](SPEC.md) (abgenommen am
11.10.2026). Die Bereichsdokumente beschreiben, was der Code auf dem Branch
`feature/multi-provider` tatsächlich tut.

## Dokumentationsbereiche

- [SPEC](SPEC.md) – API-Vertrag: Tasks, Referenzen, Parameter,
  Capability-Dokument v2, IDs, Webhooks, Assets, LiteLLM-Export, Prompt Guides.
- [Architektur](architektur/README.md) – Komponenten, Datenfluss, Grenzen und
  ADR-001 mit den Live-Befunden.
- [Installation und Konfiguration](installation-und-konfiguration/README.md) –
  Entwicklungsstart über VS Code, Docker-Deployment und alle
  Umgebungsvariablen.
- [API-Referenz](api-referenz/README.md) – sämtliche HTTP-Endpunkte,
  Authentifizierung, Modelle und Capabilities.
- [Video-Generierung](video-generierung/README.md) – Tasks je Anbieter, Parameter
  und Seedance-Regeln (Draft, Task-Typen, Audio, Service-Tier).
- [Referenzmedien](referenzmedien/README.md) – Referenzen mit Rollen, Quellen,
  Uploads, Real-Human und Eingabegrenzen.
- [Real-Human-Assets](real-human-assets/README.md) – Gesichtsverifizierung,
  Freischaltung und Nutzung der eigenen Person (nur Seedance).
- [LiteLLM-Integration](litellm-integration/README.md) – Konfigurations-Export,
  getestete Versionen und die Grenzen von LiteLLM.
- [AI Video Studio (Web-Oberfläche)](web-studio/README.md) – temporäre
  Single-User-UI für direkte Generierungen ohne LiteLLM.
- [Taskverwaltung](taskverwaltung/README.md) – Status, Listen, Abbruch,
  Webhooks, Download und Varianten.
- [Betrieb und Sicherheit](betrieb-und-sicherheit/README.md) – TLS, Schlüssel,
  Secrets, temporäre Medien, SSRF-Schutz und Aufbewahrungsfristen.
- [Entwicklung und Tests](entwicklung-und-tests/README.md) – Entwicklungsserver,
  Tests, Live-Test-Regeln und Prompt Guides.
- [Fehlerbehebung](fehlerbehebung/README.md) – typische Fehlerbilder und ihre
  Ursachen.

Hintergrund und Quellen: `tasks/plan.md`, `tasks/todo.md` und
`tasks/research/` (Google, Kling, Seedance, LiteLLM/OpenAI).

## Stand der Implementierung

| Bereich | Stand |
|---|---|
| Einheitlicher Vertrag (`/v1/videos`, Tasks, `references[]`, `parameter_policy`, Capability v2) | umgesetzt |
| Seedance (2.5, 2.0, 1.x) inklusive Draft, Real-Human und Altfeldern | umgesetzt, simulierte Tests |
| Veo 3.1 (Vertex und Gemini API): Text, Bild, First/Last, Referenzbilder, Extension, `n` bis 4 auf Vertex | umgesetzt; auf Vertex einmal live geprüft (Lite, Region `global`) |
| Gemini Omni Flash (Interactions API, `background`): Text, Bild, First/Last, Referenzen, Edit, Extend, Multi-Turn | umgesetzt; Generierung über den Proxy nicht live getestet |
| Kling (3.0, Turbo, Omni, O1, 2.6, 2.5 Turbo): Text, Bild, First/Last, Multi-Shot, Motion Control, Referenzen, Edit | umgesetzt; nicht live getestet |
| Kling-Werkzeuge: Lip Sync, Avatar, Effekte (219), Multi-Element-Edit, Video-to-Audio, Video-Commerce, Elements und Voices | umgesetzt; nicht live getestet |
| Webhooks (`webhook_url`, Standard Webhooks) für alle Anbieter | umgesetzt |
| Prompt Guides (`/v1/prompt-guides`) und LiteLLM-Export | umgesetzt |
| LiteLLM-Ende-zu-Ende-Suite (1.95.0, 1.104.2, 1.105.0) | umgesetzt, opt-in |
| AI Video Studio: Modellgruppen, Rollen, Task-Felder, Element-/Voice-Bibliothek, Guide-Modal | umgesetzt (T26 in `tasks/todo.md` noch offen) |

Nicht angeboten (Nutzerentscheidung): Kling-Bild-Endpunkte und Virtual Try-On.

Noch offen:

- Live-Tests für Kling, Omni und Seedance mit freigeschaltetem Real-Human-Asset.
  Sie laufen nur auf ausdrückliche Anforderung; ein Serverstart berechtigt nie
  zu einer kostenpflichtigen oder biometrischen Generierung.
- Seedance 1.x hat keinen Prompt Guide (Manifest deckt nur 2.5 und 2.0 ab).

Die tatsächliche Verfügbarkeit einzelner Funktionen wird zusätzlich durch das
aktivierte Modell, Account-Rechte, Regionen, Quoten und Anbieter-Richtlinien
bestimmt. Seedance 1.5 Pro ist von BytePlus als abgekündigt markiert (Abschaltung
2026-11-11, Nachfolger `dreamina-seedance-2-0-mini`); Veo über die Gemini API
endet laut Google am 22.10.2026.
