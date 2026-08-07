# Seedance Web Studio

Das Web Studio ist eine eigenständige Single-User-Oberfläche für direkte
Seedance-Aufrufe. Es kommuniziert im Docker-Netz mit dem ModelArk-Proxy und
benötigt LiteLLM nicht. ModelArk- und Proxy-Schlüssel gelangen nie in den
Browser.

## Funktionsumfang

- Text-to-Video
- Live-Modellauswahl aus den im BytePlus-Konto verfügbaren Seedance-Modellen
- First-Frame und First-/Last-Frame
- multimodale Bild-, Video- und Audioreferenzen
- Video bearbeiten, verlängern und mehrere Clips verbinden
- manuelle Real-Human- und Digital-Character-Asset-IDs
- automatische temporäre Real-Human-Registrierung pro Referenz über den
  Schalter **Reale Person · automatisch verifizieren**
- modellabhängige Dauer, Auflösung und Seitenverhältnisse sowie Audio,
  Wasserzeichen, letztes Frame und Priorität
- kostenpflichtige Bestätigung vor dem Start
- automatische Statusaktualisierung, Video-Player und Downloads
- Abbrechen/Löschen und Fortsetzung über das letzte Frame

## Start

In `.env` müssen zusätzlich gesetzt sein:

```dotenv
UI_USERNAME=seedance-admin
UI_PASSWORD=ein-langes-privates-passwort
UI_SESSION_SECRET=ein-zufaelliger-wert-mit-mindestens-32-zeichen
UI_COOKIE_SECURE=true
UI_LOGIN_MAX_ATTEMPTS=5
UI_LOGIN_WINDOW_SECONDS=900
```

Danach:

```bash
docker compose up --build -d
```

Der Container lauscht intern auf `http://localhost:3000`; im öffentlichen
Betrieb wird er ausschließlich über den vorgeschalteten HTTPS-Endpunkt genutzt.
`UI_COOKIE_SECURE=true` bleibt dabei gesetzt. Nur für einen vertrauenswürdigen
lokalen HTTP-Test darf der Wert vorübergehend auf `false` gesetzt werden.

Das Passwort muss mindestens 16 Zeichen enthalten. Nach standardmäßig fünf
Fehlversuchen innerhalb von 15 Minuten wird der anmeldende Client vorübergehend
gesperrt. Benutzername, Passwort und Session-Secret gehören ausschließlich in
die Deployment-Umgebung beziehungsweise einen Secret Store.

Eine Anmeldung kann nur in einem ausdrücklich vertrauenswürdigen lokalen Netz
mit `UI_AUTH_DISABLED=true` abgeschaltet werden. Ohne Passwort und ohne diesen
Schalter verweigert der Container aus Sicherheitsgründen den Start.

## Temporärer Lebenszyklus

Generierte Videos und letzte Frames werden nicht im UI-Container gespeichert.
Der Browser streamt sie über den Proxy direkt aus dem ModelArk-Ergebnis. Damit
können große Ergebnisdateien den Server nicht füllen.

Das Studio speichert lediglich kleine Jobmetadaten in SQLite. Sobald ein Job
terminal ist (`completed` oder `failed`), erhält er eine Ablaufzeit von
standardmäßig 24 Stunden. Danach entfernt der Hintergrundprozess den
ModelArk-Task und den lokalen Metadatensatz. Referenzuploads werden unabhängig
davon durch den Proxy nach `MEDIA_TTL_SECONDS` gelöscht.

| Variable | Standard | Bedeutung |
|---|---:|---|
| `UI_JOB_TTL_SECONDS` | `86400` | Sichtbarkeit nach Jobabschluss |
| `UI_CLEANUP_INTERVAL_SECONDS` | `900` | Cleanup-Intervall |
| `UI_POLL_INTERVAL_SECONDS` | `10` | Statusabfrage laufender Jobs |
| `UI_POLL_CONCURRENCY` | `20` | maximal parallele Statusabfragen |
| `UI_MAX_PROXY_CONNECTIONS` | `100` | HTTP-Pool zum ModelArk-Proxy |
| `UI_SESSION_TTL_SECONDS` | `43200` | Lebensdauer einer Anmeldung |
| `UI_USERNAME` | leer | verpflichtender Single-User-Loginname |
| `UI_PASSWORD` | leer | verpflichtendes Passwort, mindestens 16 Zeichen |
| `UI_SESSION_SECRET` | leer | unabhängiger Signaturschlüssel, mindestens 32 Zeichen |
| `UI_COOKIE_SECURE` | `true` | Cookie ausschließlich über HTTPS senden |
| `UI_LOGIN_MAX_ATTEMPTS` | `5` | Fehlversuche pro Zeitfenster und Client |
| `UI_LOGIN_WINDOW_SECONDS` | `900` | Rate-Limit-Zeitfenster |
| `UI_DB_PATH` | `/app/data/ui.db` | temporäres Jobregister im Container |

Ein manueller Löschvorgang entfernt den Job sofort. Nach dem Ablauf gibt es
keine Wiederherstellung; wichtige Ergebnisse müssen rechtzeitig heruntergeladen
werden.

## Gleichzeitige Generierungen

Mehrere Klicks beziehungsweise API-Aufrufe dürfen parallel eingehen. Das
UI-Backend reicht jeden Create-Aufruf asynchron an den Proxy weiter und schreibt
nur den kleinen Metadatensatz kurz in SQLite. Die eigentliche GPU-Arbeit findet
bei BytePlus statt. Laufende Generierungen blockieren deshalb weder neue Tasks
noch die Oberfläche.

Das Job-Polling läuft standardmäßig mit bis zu 20 parallelen Statusabfragen.
Die getesteten Pfade umfassen 32 gleichzeitige Proxy-Submissions, 24
gleichzeitige UI-Submissions und paralleles Polling in begrenzten Gruppen. Die
effektive Zahl gleichzeitig rechnender Videos bleibt trotzdem durch die
ModelArk-/Endpoint-Quota begrenzt; darüber hinausgehende Tasks werden von
ModelArk in `queued` gehalten.

## Referenzworkflow

Lokale Dateien werden zuerst über die geschützte UI-API an
`POST /v1/media/references` gesendet. Der Proxy prüft Signatur und Größe und
stellt eine zufällige HTTPS-URL bereit, die ModelArk abrufen kann. Unterstützt
sind:

- PNG, JPEG, GIF und WEBP
- MP4 und MOV
- MP3 und WAV

Für Video- und Audioabrufe sowie URL-basierte Bilder muss `PUBLIC_BASE_URL`
öffentlich per HTTPS erreichbar sein. Autorisierte `asset-…`-IDs benötigen
keinen Dateiupload.

## Fortsetzen mit letztem Frame

Wenn `return_last_frame` aktiviert war, kann „Fortsetzen“ gewählt werden. Die
UI sendet die vorherige Task-ID als `input_reference_task_id`. Der Proxy löst
serverseitig die noch gültige ModelArk-Last-Frame-URL auf und verwendet sie als
`first_frame`; die signierte URL wird nicht an den Browser ausgegeben.
