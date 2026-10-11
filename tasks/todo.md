# Todo: AI Video Studio – zentrale Video-KI-Plattform

Details: [plan.md](plan.md) · Recherche: [research/](research/)

## Phase 0: Verträge und Risiken
- [x] T1: Live-Verifikation mit kostenfreien Aufrufen (Gemini, Vertex, Kling, LiteLLM) und ADR (S)
- [x] T2: Einheitlicher API-Vertrag → [docs/SPEC.md](../docs/SPEC.md) (abgenommen)

## Phase 1: Fundament
- [x] T3: Provider-Kern und Seedance-Adapter (Refactor ohne Verhaltensänderung) (M)
- [x] T4: LiteLLM-robuster Eingang (Multipart-Klammern, JSON-Strings) und IDs im LiteLLM-Format (M)
- [ ] T5: Config, Credentials und Health pro Provider; Backend und Region je Google-Familie (M)
- [ ] T6: Jobregister, Output-Speicher und Worker-Framework (M)
- [ ] T6b: Ausgehende Webhooks (`callback_url`, Standard Webhooks) (S)
- [ ] T7a: Capability-Schema v2 und Validierungs-Engine (M)
- [ ] T7b: UI-Formular-Engine aus Capabilities (M)
- [ ] T8: Prompt-Guide-Registry, Endpunkte, UI-Panel und LiteLLM-Config-Export (M)
- [ ] **Checkpoint 1:** Tests und Build grün, Seedance unverändert, Vertrag abgenommen

## Phase 2: Google
- [ ] T9: Gemini- und Vertex-Backend; Veo Text→Video mit allen Parametern (M)
- [ ] T10: Veo Bild→Video, Start+Ende und Referenzbilder (M)
- [ ] T11: Veo-Extension (beide Backends) (S)
- [ ] T12: Omni Text→Video, Bild→Video und Start+Ende (Interactions, background) (M)
- [ ] T13: Omni-Referenzen, Edit, Extend und Multi-Turn (M)
- [ ] **Checkpoint 2:** Google komplett; Live-Tests nur mit Freigabe

## Phase 3: Kling (parallel zu Phase 2)
- [ ] T14: Kling-Client, Text→Video, Bild→Video, Multi-Shot und Audio (M)
- [ ] T15: Kling Omni (3.0 Omni, O1): Referenzen und Video-Edit (M)
- [ ] T16: Kling Motion Control (S)
- [ ] T17: Kling Elements und Voices, einheitliche Asset-Übersicht (M)
- [ ] T18: Kling Lip Sync (mehrstufig) und Avatar (M)
- [ ] T19: Kling Audio: TTS (`/v1/audio/speech`), Text→Audio, Video→Audio (M)
- [ ] T20: Kling-Effekte (219) und Multi-Element-Bearbeitung (M)
- [ ] T21: Kling Video-Commerce (Talking Agent, Goods Studio, Apparel) (M)
- [ ] **Checkpoint 3:** Kling komplett; Live-Tests nur mit Freigabe

## Phase 4: Seedance vollständig
- [ ] T22: Seedance-Lückenanalyse und Abbildung auf den Vertrag (M)

## Phase 5: Prompt Guides (parallel ab Checkpoint 1)
- [ ] T23: Guide Gemini Omni Flash (M)
- [ ] T24: Guides Kling (3.0/Turbo, 3.0 Omni/O1, 2.6/2.5 Turbo, Spezial-Tasks) (M)
- [ ] T25: Veo-Guide korrigieren, Seedance-Zuordnung prüfen, Lücken schließen (S–M)

## Phase 6: UI und Integration
- [ ] T26: UI-Assetbibliotheken, Effekt-Galerie, Spezialformulare, Multi-Output (L, aufteilen)
- [ ] T27: Branding „AI Video Studio“ und Provider-Texte (S)
- [ ] T28: LiteLLM-Ende-zu-Ende-Suite (zwei LiteLLM-Versionen) (M)
- [ ] T29: Dokumentation und Konfiguration (M)
- [ ] **Checkpoint: Fertig**
