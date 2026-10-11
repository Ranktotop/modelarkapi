# AI Video Studio (Web-Oberfläche)

Das Studio ist eine eigenständige Single-User-Oberfläche für direkte Aufrufe von
Seedance, Veo, Gemini Omni und Kling. Es kommuniziert im Docker-Netz mit dem
Proxy und benötigt LiteLLM nicht. Anbieter- und Proxy-Schlüssel gelangen nie in
den Browser.

## Funktionsumfang

- **Modellauswahl** gruppiert nach Anbieter (BytePlus ModelArk, Google, Kling),
  live aus `GET /v1/models`. Welche Modelle erscheinen, hängt von den aktiven
  Anbietern des Proxys ab.
- **Modi aus den Capabilities:** Das Studio zeigt nur Workflows, die das gewählte
  Modell laut `capabilities.tasks` kann (Text, Startbild, Start + Ende,
  Referenzen, Bearbeiten, Verlängern, Verbinden sowie die Kling-Aufgaben). Dauer,
  Auflösung, Seitenverhältnis, Dateiformat, Audio, Wasserzeichen und Varianten
  kommen aus demselben Dokument; durch `constraints` erzwungene Werte sind
  gesperrt und mit einer Begründung versehen.
- **Rolle je Referenz:** Bei Nicht-Seedance-Modellen mit mehreren möglichen Rollen
  wählt eine Auswahl an jeder Referenz die Rolle (z. B. Startbild, Endbild,
  Referenz, Ausgangsvideo, Bewegung, Figur, Sprache). „Rolle automatisch“ überlässt die
  Zuordnung dem Proxy.
- **Task-Felder:** Multi-Shot (bis zu 6 Shots mit Prompt und Dauer, Modus „eigene
  Shots“ oder „automatisch aus dem Prompt“), Effekt-Galerie mit Suche (219
  Kling-Effekte), Sprechtext mit TTS-Stimme und Sprache für Lip Sync und Avatar,
  Objektauswahl, Vertonen, Bewegungsoptionen und Video-Commerce (siehe unten).
- **Kling-Bibliothek** für Elements und Voices: eigene und Kling-Vorlagen
  auswählen, neu anlegen und beobachten, bis sie bereit sind.
- **Prompt-Guide-Modal:** Für Modelle mit Guide öffnet ein Button den Guide in
  einem Dialog (`GET /v1/prompt-guides/{id}` mit `Accept: application/json`).
- **Kostenhinweis je Anbieter:** Vor dem Start erscheint eine Bestätigung, die
  den Abrechnenden nennt (BytePlus, Google (Gemini API), Google Cloud (Vertex AI)
  oder Kling), plus Hinweis, dass das Ergebnis nur etwa 24 Stunden verfügbar ist.
  Die Schaltfläche heißt „Kostenpflichtig starten“.
- **Ergebnis:** automatische Statusaktualisierung, Video-Player, Audio-Player für
  reine Audio-Ergebnisse und ein Download pro Variante (Video, Audio, WAV,
  Produkt-/Modellbilder, weitere Ausgaben bei `n` > 1) sowie Download des letzten
  Frames.
- **Job-Details** zeigen Anbieter, Backend (Vertex AI oder Gemini API), Modell,
  Anbieter-Status, Fortschritt, Fehlercode und -meldung, Referenzen mit Rollen und
  die Rohdaten von Anfrage und Antwort.
- **Seedance-Besonderheiten:** Schalter **Reale Person · automatisch
  verifizieren** pro Referenz, Priorität, letztes Frame und Fortsetzen.
- Abbrechen/Löschen von Jobs und Fortsetzen: über das letzte Frame (Seedance),
  durch Verlängern des Videos (Veo) oder durch Multi-Turn (Omni).

## Start

Entwicklung: **Local Full Stack** aus `.vscode/launch.json` starten (Proxy
`8081`, Studio-Backend `3000`, Vite `5173`; das Studio läuft dort ohne Login mit
`UI_AUTH_DISABLED=true`). Öffnen unter `http://127.0.0.1:5173`.

Deployment: In `.env` müssen zusätzlich gesetzt sein:

```dotenv
UI_USERNAME=studio-admin
UI_PASSWORD=ein-langes-privates-passwort
UI_SESSION_SECRET=ein-zufaelliger-wert-mit-mindestens-32-zeichen
UI_COOKIE_SECURE=true
UI_LOGIN_MAX_ATTEMPTS=5
UI_LOGIN_WINDOW_SECONDS=900
```

Danach (nur auf ausdrückliche Anforderung für Deployment-Tests):

```bash
docker compose up -d
```

Der Container lauscht intern auf Port 3000 (Host `5191`); im öffentlichen Betrieb
wird er ausschließlich über den vorgeschalteten HTTPS-Endpunkt genutzt.
`UI_COOKIE_SECURE=true` bleibt dabei gesetzt. Nur für einen vertrauenswürdigen
lokalen HTTP-Test darf der Wert vorübergehend auf `false` gesetzt werden.

Das Passwort muss mindestens 16 Zeichen enthalten. Nach standardmäßig fünf
Fehlversuchen innerhalb von 15 Minuten wird der anmeldende Client vorübergehend
gesperrt. Benutzername, Passwort und Session-Secret gehören ausschließlich in die
Deployment-Umgebung beziehungsweise einen Secret Store.

Eine Anmeldung kann nur in einem ausdrücklich vertrauenswürdigen lokalen Netz mit
`UI_AUTH_DISABLED=true` abgeschaltet werden. Ohne Passwort und ohne diesen Schalter
verweigert der Container aus Sicherheitsgründen den Start.

## Temporärer Lebenszyklus

Generierte Videos und letzte Frames werden nicht im UI-Container gespeichert. Der
Browser streamt sie über das Studio-Backend aus dem Proxy (`/api/videos/{id}/content`);
bei Google und Kling liegen sie bis zum Jobablauf im Output-Speicher des Proxys
(`PROVIDER_JOB_TTL_SECONDS`), bei Seedance in der ModelArk-URL. Damit können große
Ergebnisdateien den Studio-Server nicht füllen.

Das Studio speichert lediglich kleine Jobmetadaten in SQLite. Sobald ein Job
terminal ist (`completed` oder `failed`), erhält er eine Ablaufzeit von
standardmäßig 24 Stunden. Danach entfernt der Hintergrundprozess den Job beim
Proxy (`DELETE`) und den lokalen Metadatensatz. Referenzuploads werden unabhängig
davon durch den Proxy nach `MEDIA_TTL_SECONDS` gelöscht.

| Variable | Standard | Bedeutung |
|---|---:|---|
| `UI_JOB_TTL_SECONDS` | `86400` | Sichtbarkeit nach Jobabschluss |
| `UI_CLEANUP_INTERVAL_SECONDS` | `900` | Cleanup-Intervall |
| `UI_POLL_INTERVAL_SECONDS` | `10` | Statusabfrage laufender Jobs |
| `UI_POLL_CONCURRENCY` | `20` | maximal parallele Statusabfragen |
| `UI_MAX_PROXY_CONNECTIONS` | `100` | HTTP-Pool zum Proxy |
| `UI_SESSION_TTL_SECONDS` | `43200` | Lebensdauer einer Anmeldung |
| `UI_USERNAME` | leer | verpflichtender Single-User-Loginname |
| `UI_PASSWORD` | leer | verpflichtendes Passwort, mindestens 16 Zeichen |
| `UI_SESSION_SECRET` | leer | unabhängiger Signaturschlüssel, mindestens 32 Zeichen |
| `UI_COOKIE_SECURE` | `true` | Cookie ausschließlich über HTTPS senden |
| `UI_AUTH_DISABLED` | `false` | Login abschalten (nur vertrauenswürdiges Netz) |
| `UI_LOGIN_MAX_ATTEMPTS` | `5` | Fehlversuche pro Zeitfenster und Client |
| `UI_LOGIN_WINDOW_SECONDS` | `900` | Rate-Limit-Zeitfenster |
| `UI_DB_PATH` | `/app/data/ui.db` | temporäres Jobregister im Container |
| `MODELARK_PROXY_URL` | `http://modelark-video-proxy:8080/v1` | Basis-URL des Proxys (Compose setzt `http://modelarkapi_server:8080/v1`) |
| `MODELARK_PROXY_API_KEY` | `PROXY_API_KEY` | Bearer-Key zum Proxy |

Ein manueller Löschvorgang entfernt den Job sofort. Nach dem Ablauf gibt es keine
Wiederherstellung; wichtige Ergebnisse müssen rechtzeitig heruntergeladen werden.

## Gleichzeitige Generierungen

Mehrere Klicks beziehungsweise API-Aufrufe dürfen parallel eingehen. Das
UI-Backend reicht jeden Create-Aufruf asynchron an den Proxy weiter und schreibt
nur den kleinen Metadatensatz kurz in SQLite. Die eigentliche Rechenarbeit findet
beim Anbieter statt. Laufende Generierungen blockieren deshalb weder neue Tasks
noch die Oberfläche.

Das Job-Polling läuft standardmäßig mit bis zu 20 parallelen Statusabfragen. Die
getesteten Pfade umfassen 32 gleichzeitige Proxy-Submissions, 24 gleichzeitige
UI-Submissions und paralleles Polling in begrenzten Gruppen. Die effektive Zahl
gleichzeitig rechnender Videos bleibt durch die Quoten des jeweiligen Anbieters
begrenzt; darüber hinausgehende Tasks werden vom Anbieter in `queued` gehalten.

## Workflows und ihre API-Felder

Die Workflow-Auswahl ist eine reine Bedienhilfe. Sie wird als `ui_mode` an das
UI-Backend gesendet, dort aber zusammen mit allen anderen `ui_*`-Feldern verworfen
und nur für die Jobanzeige gespeichert. Der Proxy sieht Rollen, Task und Felder.

Für **Seedance** sendet das Studio weiterhin das Altformat (`reference_urls`,
`ratio`, `duration`, `omni_reference_task_type`); für alle anderen Anbieter den
einheitlichen Vertrag mit `task`, `references[]` und `seconds`.

| Workflow | Task | Erfordert | Zusätzlich gesendet |
|---|---|---|---|
| Text | `text_to_video` | keine Referenz | nichts |
| Startbild | `image_to_video` | genau ein Bild | Rolle `first_frame` |
| Start + Ende | `first_last_frame` | genau zwei Bilder | `first_frame`, `last_frame` |
| Referenzen | `reference_to_video` | mindestens eine Referenz | Rolle `reference` bzw. Seedance `reference_*` |
| Bearbeiten | `edit` | mindestens ein Video | `base_video`; Seedance 2.5: `omni_reference_task_type: "edit"` |
| Verlängern | `extend` | Video oder Vorgängerjob | `base_video` (oder `task_id`); Seedance 2.5: `"extend"` |
| Verbinden | `stitch` | mindestens zwei Videos | wie Referenzen |
| Multi-Shot | `multi_shot` | – | `shot_mode`, `shots`, `seconds` als Summe |
| Bewegung | `motion_control` | Figur + Bewegungsvideo | `provider_options.kling` (`character_orientation`, `keep_original_sound`) |
| Lip Sync | `lip_sync` | Video, Audio oder Sprechtext | `speech` |
| Avatar | `avatar` | Bild, Audio oder Sprechtext | `speech` |
| Effekt | `effect` | 1–2 Bilder | `effect` |
| Objekte | `multi_element_edit` | Video | `edit_mode`, `selections` |
| Vertonen | `video_to_audio` | Video | `audio.bgm_prompt`, `audio.asmr` |
| Audio | `text_to_audio` | – | Prompt, `seconds` (3–10) |
| Sprecher | `commerce_talking_agent` | Avatar-Bild oder Preset-Avatar, Skript | `commerce` (`script`, `avatar_id`, `title`, `price`, `selling_points`, `speech_rate`, `bgm`), Stimme |
| Produktfilm | `commerce_goods_studio` | Produktbilder, Titel | `commerce` (`title`, `description`) |
| Kleidung | `commerce_apparel` | Video, Produktbilder | `commerce.product_info`, Stimme |

Den Seedance-Task-Typ setzt das Studio nur, wenn das gewählte Modell ihn laut
`capabilities.task_types` unterstützt (derzeit Seedance 2.5). Bei der 2.0-Familie
erzeugen **Bearbeiten**, **Verlängern**, **Verbinden** und **Referenzen**
identische Requests; die Absicht gehört dort in den Prompt, siehe
[Video-Generierung](../video-generierung/README.md#bearbeiten-und-verlängern-ohne-task-typ).

Seitenverhältnis und Dauer sperrt das Studio genau dort, wo
`capabilities.constraints` sie erzwingen (etwa Seedance 2.5 bei `edit`/`extend`,
Kling bei Bild-Tasks).

### Mehrfach-Objektauswahl im Video

Bei **Objekte** (`multi_element_edit`) wird das hochgeladene Video im Formular
abgespielt. Das Video anhalten und auf das Objekt klicken: Jeder Klick speichert
einen Punkt (relative Koordinaten 0–1) am aktuellen Frame
(`frame_index = Zeit × Bildrate`; die Bildrate ist einstellbar, Standard 24).
Höchstens 10 Frames mit je 10 Punkten. Das Ergebnis geht als `selections` an den
Proxy; ohne mindestens einen Klick startet der Job nicht.

### Kling-Bibliothek

Je nach Task zeigt das Studio Elements und/oder Voices (nur wenn das Modell sie
als Referenz zulässt). „Neu anlegen“ nutzt die aktuellen Uploads: Ein Element
nimmt das erste Bild als Frontalansicht und 1–3 weitere Bilder (Name ≤ 20,
Beschreibung ≤ 100 Zeichen); eine Voice nimmt die erste Audio- oder Videodatei.
Gewählte Assets gehen als `references` mit `asset_id` an den Proxy.

## Referenzworkflow

Lokale Dateien werden zuerst über die geschützte UI-API an
`POST /v1/media/references` gesendet. Der Proxy prüft Signatur und Größe und
stellt eine zufällige HTTPS-URL bereit, die der Anbieter abrufen kann. Unterstützt
sind:

- PNG, JPEG, GIF und WEBP
- MP4 und MOV
- MP3 und WAV

Für Video- und Audioabrufe sowie URL-basierte Bilder muss `PUBLIC_BASE_URL`
öffentlich per HTTPS erreichbar sein.

## Fortsetzen

- **Seedance:** Wenn `return_last_frame` aktiviert war, sendet „Fortsetzen“ die
  vorherige Task-ID als `input_reference_task_id`. Der Proxy löst serverseitig die
  noch gültige Last-Frame-URL auf; die signierte URL gelangt nicht in den Browser.
- **Veo und Omni:** „Verlängern“ wechselt in den Modus **Verlängern** mit dem
  Vorgängerjob als `base_video` (`task_id`).

## Bekannte Lücken

- Der Plan (`tasks/todo.md`, T26) führt die UI-Assetbibliotheken, Effekt-Galerie,
  Spezialformulare und Multi-Output noch als offen; die oben beschriebenen Teile
  sind im Code vorhanden, aber nicht live gegen Kling oder Omni getestet.
- Frontend-Tests: `npm test` in `ui/frontend` (prüft die Capability-Auswertung);
  das Backend wird mit `pytest` (`ui/tests`) getestet.
