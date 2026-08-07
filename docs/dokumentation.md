# ModelArk OpenAI Video Proxy – Dokumentation

Diese Dokumentation beschreibt Installation, API und Betrieb des Proxys, der
OpenAI-/LiteLLM-Videoanfragen in die asynchrone BytePlus-ModelArk-API für
Seedance übersetzt. Der Proxy führt keine Videogenerierung selbst aus.

## Dokumentationsbereiche

- [Architektur](architektur/README.md) – Komponenten, Datenfluss und Grenzen
  des Adapters.
- [Installation und Konfiguration](installation-und-konfiguration/README.md) –
  lokaler Start, Docker und alle Umgebungsvariablen.
- [API-Referenz](api-referenz/README.md) – sämtliche HTTP-Endpunkte,
  Authentifizierung und Request-/Response-Felder.
- [Video-Generierung](video-generierung/README.md) – Text-to-Video,
  First-/Last-Frame, multimodale Bearbeitung, Verlängerung und Audio.
- [Referenzmedien](referenzmedien/README.md) – Uploads, öffentliche URLs,
  automatische Real-Human-Verarbeitung, Rollen und Eingabegrenzen.
- [Real-Human-Assets](real-human-assets/README.md) – Gesichtsverifizierung,
  Freischaltung und Nutzung der eigenen Person.
- [LiteLLM-Integration](litellm-integration/README.md) – Gateway-Konfiguration
  und Aufrufe über LiteLLM.
- [Seedance Web Studio](web-studio/README.md) – temporäre Single-User-UI für
  direkte Generierungen ohne LiteLLM.
- [Taskverwaltung](taskverwaltung/README.md) – Status, Listen, Abbruch,
  Video- und Last-Frame-Download.
- [Betrieb und Sicherheit](betrieb-und-sicherheit/README.md) – TLS,
  Schlüssel, temporäre Medien, SSRF-Schutz und Aufbewahrungsfristen.
- [Entwicklung und Tests](entwicklung-und-tests/README.md) – lokale Tests,
  Qualitätschecks und der bewusst verschobene Live-Test.
- [Fehlerbehebung](fehlerbehebung/README.md) – typische Fehlerbilder und ihre
  Ursachen.

## Stand der Implementierung

Alle wesentlichen Seedance-2.0-Workflows sind über die API erreichbar:

- Text-, Bild-, Video- und Audioreferenzen
- ein First-Frame sowie ein First-/Last-Frame-Paar
- multimodale Generierung, Bearbeitung, Verlängerung und Clip-Stitching
- öffentliche URLs, Multipart-Upload und rohes
  ModelArk-`content`
- Audioausgabe und unterstützte Ausgabeparameter
- Task-Erstellung, Liste, Status, Abbruch/Löschen, MP4 und letztes Frame
- OpenAI-Feldübersetzung für `seconds`, `size` und `user`
- optionaler Docker-UI-Container mit Datei-Uploads, Live-Status und Downloads

Noch nicht live verifiziert ist ausschließlich der kostenpflichtige Aufruf mit
einem freigeschalteten Real-Human-Asset. Dieser Test wird erst durchgeführt,
wenn die betreffende Asset-Gruppe in ModelArk den Status `Active` hat. Die
Unit- und Integrationstests verwenden simulierte ModelArk-Antworten und lösen
keine Kosten aus.

Die tatsächliche Verfügbarkeit einzelner Funktionen wird zusätzlich durch das
aktivierte Modell, Account-Rechte, Regionen, Quoten und BytePlus-Richtlinien
bestimmt. Für den aktuell freigeschalteten Seedance-2.0-Fast-Zugang sind
insbesondere dessen Ausgabegrenzen maßgeblich.
