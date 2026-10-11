# AI Video Studio (ModelArk OpenAI Video Proxy)

Dieser Dienst stellt eine einzige OpenAI-kompatible Video-API bereit – mit
zusätzlichen nativen Routen je Anbieter. Er übersetzt Anfragen, die LiteLLM oder
ein direkter Client an `/v1/videos` sendet, in die asynchronen APIs von:

| Anbieter | Modelle | Zugang |
|---|---|---|
| BytePlus ModelArk | Seedance 2.5, 2.0 (Fast, Mini), 1.5 Pro, 1.0 Pro (Fast) | `ARK_API_KEY` plus IAM-AK/SK für die Modellliste |
| Google | Veo 3.1 (Standard, Fast, Lite), Gemini Omni Flash | Gemini API und/oder Vertex AI, Backend und Region je Familie |
| Kling | Kling 3.0 (Turbo), 3.0 Omni, O1, 2.6, 2.5 Turbo sowie Lip Sync, Avatar, Effekte, Multi-Element-Edit, Audio, Video-Commerce | `KLING_API_KEY` |

Kling-Bild-APIs und Virtual Try-On sind bewusst nicht enthalten. Paket- und
Docker-Image-Namen (`modelark-openai-video-proxy`, `ranktotop/modelarkapi`)
bleiben unverändert.

Der Vertrag (Tasks, Referenzen mit Rollen, Parameter, `parameter_policy`,
Capability-Dokument v2, IDs, Webhooks, Assets, LiteLLM-Export, Prompt Guides) ist
in [docs/SPEC.md](docs/SPEC.md) festgeschrieben. Die vollständige, thematisch
gegliederte Dokumentation beginnt unter
[docs/dokumentation.md](docs/dokumentation.md).

Zusätzlich enthält das Projekt das [AI Video Studio](docs/web-studio/README.md)
als separaten Container: eine Single-User-Oberfläche für direkte Generierungen
ohne LiteLLM. Sie speichert fertige Videos nicht dauerhaft auf dem Server.

## Funktionsumfang

- `POST /v1/videos` (JSON oder Multipart) für alle Modelle mit denselben Feldern;
  ein Modellwechsel ändert nur `model`
- Tasks: Text-, Bild-, First/Last-Frame-, Referenz-, Multi-Shot-Video, Edit,
  Extend, Stitch, Motion Control, Lip Sync, Avatar, Effekte, Multi-Element-Edit,
  Video-to-Audio, Text-to-Audio und Kling-Video-Commerce
- `references[]` mit Typ (`image`, `video`, `audio`, `element`, `voice`) und
  Rolle; Quellen: `url`, `data:`-URI, `upload_id`, `task_id`, `asset_id`
- `GET /v1/models` mit Capability-Dokument v2 je Modell, `GET /v1/prompt-guides`
  und `GET /v1/litellm/config` (LiteLLM-`model_list`-Export)
- `GET /v1/videos/{id}`, `/content` (mit `?variant=` und `?output=`),
  `/last_frame`, `POST /v1/videos/{id}/remix`, `/v1/videos/edits`,
  `/v1/videos/extensions`, `DELETE`
- `POST /v1/audio/speech` (Kling TTS, Modell `kling-tts`)
- `/v1/assets` für Kling-Elements und -Voices
- OpenAI-Characters (`/v1/videos/characters`) als Kling-Video-Elements
- `GET /v1/videos` über ModelArk und das lokale Jobregister (alle Anbieter)
- native Routen: `/v1/providers/modelark/tasks`, `/v1/providers/google/veo/…`,
  `/v1/providers/google/interactions` und `/v1/providers/kling/…`
- signierte Webhooks über `webhook_url` für alle Anbieter
- temporäre Uploads über `POST /v1/media/references`
- automatische temporäre Real-Human-Registrierung bei Seedance über
  `real_human: true`
- Seedance-Altfelder (`reference_urls`, `ratio`, `duration`, `content` …) bleiben
  gültig

Die Video-IDs in Antworten haben das LiteLLM-Format `video_<base64>`; eingehend
werden auch die internen IDs (`cgt-…`, `vid-<anbieter>-…`) akzeptiert.

## Teststand

Alle Anbieter sind mit simulierten Upstreams getestet. Live geprüft wurde
bisher nur Veo 3.1 Lite auf Vertex AI (Region `global`, einmalig) sowie die
kostenfreien Credential-Prüfungen. ADR-001 hält zusätzlich einen einmaligen
Direktaufruf der Gemini-API-Omni fest.

**Nicht live getestet:** alle Kling-Generierungen und alle Omni-Generierungen
über den Proxy. Seedance mit einem freigeschalteten Real-Human-Asset ist
ebenfalls noch offen. Details stehen in
[Entwicklung und Tests](docs/entwicklung-und-tests/README.md).

## Die wichtige Einschränkung bei Video-Uploads

Seedance und Kling brauchen Referenzvideos als öffentlich abrufbare URL, nicht
als Base64 oder Multipart-Upload. Die Kette funktioniert daher so:

```text
Client --multipart--> LiteLLM --multipart--> dieser Proxy
       dieser Proxy --öffentliche, zufällige URL--> ModelArk/Seedance/Kling
```

Der Proxy speichert den Upload temporär unter einer kryptografisch zufälligen
URL. `PUBLIC_BASE_URL` muss deshalb aus dem Internet per HTTPS erreichbar sein;
`localhost`, eine reine Docker-Adresse oder ein nur internes LAN reichen nicht.
Die Dateien werden standardmäßig nach 24 Stunden entfernt. Für eine Produktion
sollte TLS vor dem Dienst terminiert werden (z. B. Caddy, Traefik oder Nginx).
Google-Modelle bekommen die Bytes dagegen direkt vom Proxy und brauchen die
öffentliche URL nicht.

Seedance 2.0 nimmt direkte Referenz-Uploads mit echten menschlichen Gesichtern
laut ModelArk-Dokumentation nicht allgemein an. Dafür müssen die von BytePlus
vorgesehenen vertrauenswürdigen Outputs, autorisierten Personen-Assets oder
Digital-Character-Assets verwendet werden.

LiteLLM bezeichnet `input_reference` gemäß OpenAI als Bild. Aktuelle LiteLLM-
Versionen reichen jedoch beliebige Bytes durch und etikettieren unbekannte
Dateien gegebenenfalls als `image/png`. Der Proxy prüft deshalb die tatsächliche
Dateisignatur und erkennt MP4/MOV unabhängig vom von LiteLLM gesetzten MIME-Typ.

## Start

### Entwicklung

Entwicklungsserver starten ausschließlich über die eingecheckte
VS-Code-Konfiguration **Local Full Stack** (`.vscode/launch.json`). Sie lädt die
Secrets aus `.env` und startet:

| Komponente | Adresse |
|---|---|
| Proxy | `http://127.0.0.1:8081` |
| Studio-Backend | `http://127.0.0.1:3000` |
| Vite-Frontend | `http://127.0.0.1:5173` |

Der Proxy nutzt bewusst nicht Port 8080, den ein anderes lokales Projekt belegt.
`docker compose up/run`, `docker run` oder ein direkt aufgerufenes
`uvicorn`/Vite sind für die Entwicklung nicht vorgesehen.

```bash
cp .env.example .env
# .env ausfüllen. Zufallswerte zum Beispiel mit: openssl rand -hex 32
curl http://127.0.0.1:8081/health
curl -H "Authorization: Bearer $PROXY_API_KEY" \
  http://127.0.0.1:8081/v1/real-human/configuration
```

Ein gestarteter Server berechtigt zu keiner kostenpflichtigen oder
biometrischen Generierung. Erst `/health` und den read-only-Aufruf
`/v1/real-human/configuration` nutzen; Live-Tests nur auf ausdrückliche
Anforderung (siehe [Betrieb und Sicherheit](docs/betrieb-und-sicherheit/README.md)).

### Deployment (Docker)

Docker dient der Image-Prüfung und dem Deployment. Nur auf ausdrückliche
Anforderung starten:

```bash
docker compose up -d
curl http://localhost:5192/health   # Proxy (Container-Port 8080)
curl http://localhost:5191/health   # Studio (Container-Port 3000)
```

`./secrets` wird schreibgeschützt nach `/app/secrets` gemountet; für Vertex AI
liegt dort die Service-Account-JSON, deren Dateiname in `GOOGLE_CREDENTIALS_FILE`
steht (Compose setzt daraus `GOOGLE_APPLICATION_CREDENTIALS`). Bei Betrieb hinter
HTTPS muss `UI_COOKIE_SECURE=true` gesetzt sein.

Wesentliche Variablen (vollständige Liste in
[Installation und Konfiguration](docs/installation-und-konfiguration/README.md)):

| Variable | Bedeutung |
|---|---|
| `ARK_API_KEY` | ModelArk API Key (Seedance) |
| `BYTEPLUS_ACCESS_KEY_ID` / `BYTEPLUS_SECRET_ACCESS_KEY` | IAM-Zugang für Modellliste und Real-Human-Assets |
| `GEMINI_API_KEY` | Gemini API (Omni; Veo nur bis zur Abschaltung der Preview-Modelle am 22.10.2026) |
| `VERTEX_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS` | Vertex AI (Veo 3.1, Omni Preview); ohne Datei gelten Application Default Credentials |
| `GOOGLE_VEO_BACKEND` / `GOOGLE_VEO_LOCATION` | `vertex` oder `gemini`, Region (Standard `us-central1`) |
| `GOOGLE_OMNI_BACKEND` / `GOOGLE_OMNI_LOCATION` | `vertex`, `gemini` oder `both` (GA-IDs → Gemini API, `-preview`-IDs → Vertex AI; braucht beide Zugänge), Region (Standard `global`) |
| `DEFAULT_PARAMETER_POLICY` | `strict` (Standard) oder `adapt` für alle Anbieter |
| `KLING_API_KEY`, `KLING_BASE_URL` | Kling (Standard-Endpunkt `https://api-singapore.klingai.com`) |
| `WEBHOOK_SECRET` | Signaturschlüssel für `webhook_url` (`whsec_<base64>`) |
| `PUBLIC_BASE_URL` | Öffentliche HTTPS-Basis-URL dieses Proxys; für Uploads Pflicht |
| `PROXY_API_KEY` | Bearer-Key zwischen Clients, Studio und Proxy (mindestens 32 Zeichen im Docker-Deployment) |
| `BYTEPLUS_ASSET_GROUP_ID` | verifizierte Real-Human-Asset-Gruppe |

Ein Anbieter ist aktiv, sobald seine Zugangsdaten gesetzt sind. Der Proxy prüft
sie beim Start mit kostenfreien Read-only-Aufrufen und wiederholt dies
standardmäßig alle drei Stunden. Ungültige Zugangsdaten sperren nur den
betroffenen Anbieter (`503 upstream_credentials_invalid`); `/health` bleibt
erreichbar und nennt den Zustand je Anbieter unter `providers`.

Ein reiner Netzwerk- oder DNS-Ausfall gilt dabei nicht als ungültiger Zugang: ein
zuvor bestätigter Schlüssel behält den Zustand `valid`, und solange der Zustand
nicht `valid` ist, wird alle 30 Sekunden statt alle drei Stunden erneut geprüft.
Ausgehende Aufrufe wiederholen Verbindungsfehler zudem selbstständig mit
Backoff. Details unter [Fehlerbehebung](docs/fehlerbehebung/README.md).

Der allgemeine BytePlus-Kontosaldo ist kein verlässlicher Indikator für
Seedance-Resource-Packages und wird daher weder angezeigt noch als Sperre
verwendet. Meldet ModelArk bei einem echten Generierungsaufruf ein erschöpftes
Package, reicht der Proxy dessen Fehlercode und Meldung an LiteLLM und UI weiter.

## Beispiel: ein Aufruf für jedes Modell

```bash
curl -X POST http://127.0.0.1:8081/v1/videos \
  -H "Authorization: Bearer $PROXY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "veo-3.1-fast-generate-001",
    "prompt": "A fox running through fresh snow",
    "seconds": 8,
    "resolution": "720p",
    "aspect_ratio": "16:9"
  }'
```

Die Antwort kommt sofort mit `queued` oder `in_progress`. Danach
`GET /v1/videos/{id}` pollen (etwa alle 10 Sekunden) und bei `completed`
`/content` laden. Welche Werte ein Modell akzeptiert, steht im
Capability-Dokument unter `GET /v1/models`; nicht unterstützte Werte führen
standardmäßig zu `400` (`parameter_policy: "strict"`, einstellbar über `DEFAULT_PARAMETER_POLICY`), mit
`"parameter_policy": "adapt"` passt der Proxy sie an und meldet die Änderung
unter `adjustments`.

## LiteLLM anbinden

Die `model_list`-Einträge erzeugt der Proxy selbst:

```bash
curl -H "Authorization: Bearer $PROXY_API_KEY" \
  'http://127.0.0.1:8081/v1/litellm/config?format=yaml&api_base=http://modelarkapi_server:8080/v1' \
  > litellm-models.yaml
```

Beim LiteLLM-Container setzen:

```bash
MODELARK_PROXY_API_KEY=<derselbe mindestens 32 Zeichen lange PROXY_API_KEY>
```

`api_base` muss auf `/v1` dieses Dienstes zeigen. Weil LiteLLM die Anbieter nicht
nativ kennt, wird bewusst sein vorhandener `openai`-Video-Adapter benutzt.
`model_info` enthält je Modell `capabilities` und den Prompt Guide im Volltext;
Apps lesen beides über `GET /v1/model/info`. Was über LiteLLM funktioniert und
was nur direkt am Proxy (Liste, `DELETE`, `variant`), steht in der
[LiteLLM-Integration](docs/litellm-integration/README.md). Die Beispieldatei
`litellm-config.example.yaml` zeigt vier Beispieleinträge im Format des Exports.

Videogenerierung ist auch am LiteLLM Gateway asynchron. LiteLLM pollt einen
gestarteten Job nicht selbstständig: Der aufrufende Client wiederholt
`GET /v1/videos/VIDEO_ID` etwa alle 10 Sekunden, bis `status` den Wert
`completed` oder `failed` erreicht, und lädt erst dann `/content`.

## Eigene Gesichter: Freischaltung und Verifizierung

Seedance 2.0 akzeptiert ein Foto oder Video mit einer realen Person nicht als
gewöhnliche URL oder Datei. Für das eigene Gesicht ist die private
**Real-human Asset Library** vorgesehen. BytePlus führt dabei eine
Echtzeit-Lebendprüfung durch und vergleicht spätere Uploads biometrisch mit der
verifizierten Person. Das gilt nur für Seedance; bei anderen Anbietern führt `real_human` zu `400 unsupported_parameter` (`param: real_human`).

Offizielle Dokumentation:

- [Real-human Assets über die Konsole hinzufügen](https://docs.byteplus.com/en/docs/ModelArk/2315856)
- [Private Real-human Asset Library und Assets API](https://docs.byteplus.com/en/docs/ModelArk/2333589)
- [Advanced Creation Rights](https://docs.byteplus.com/en/docs/ModelArk/2377608)

### Checkliste für die Freischaltung

- [ ] Im BytePlus-Konto die persönliche Real-Human- oder
      Unternehmensverifizierung abschließen.
- [ ] Unter **Model activation → Advanced Creation Rights** prüfen, welche
      kostenlose Stufe für das Konto verfügbar ist.
- [ ] Im **ModelArk Playground → My assets → Real-human → Add real-human
      assets** eine Asset-Gruppe anlegen.
- [ ] Gültigkeitszeitraum und Verwendungszweck festlegen und den
      Autorisierungs-QR-Code erzeugen.
- [ ] QR-Code mit dem persönlichen BytePlus-Konto öffnen, Einwilligungen
      bestätigen und die Echtzeit-Gesichtsprüfung durchführen.
- [ ] Frontalbilder oder Videos derselben Person hochladen. Eine Asset-Gruppe
      darf nur eine Person enthalten; Material mit mehreren Gesichtern wird
      nicht akzeptiert.
- [ ] Das autorisierte Material im ModelArk-Konto annehmen und warten, bis der
      Asset-Status **Active** ist.
- [ ] Die ID der verifizierten Asset-Gruppe als
      `BYTEPLUS_ASSET_GROUP_ID` im Proxy konfigurieren.
- [ ] Erst danach den automatischen Workflow lokal testen.
- [ ] Den kostenpflichtigen Live-Test ganz zuletzt mit 4 Sekunden, 480p und
      ohne Audio starten.

Die Verifizierung ist pro Person und Asset-Gruppe nur einmal nötig. Weitere
Looks derselben Person können später ergänzt werden, durchlaufen aber jeweils
eine Konsistenzprüfung. Die kostenlose Basic-Stufe wird derzeit mit bis zu 50
Assets und 50 Asset-Gruppen geführt; die vollständige Assets-API kann je nach
Account eine Enterprise-/Entry-Freischaltung oder Einladung erfordern.

### Neue Real-Human-Referenz verwenden

LiteLLM beziehungsweise der REST-Client übergibt nur die Referenz und markiert
sie mit `real_human: true`. Der Proxy registriert sie in der konfigurierten
Asset-Gruppe, wartet auf `Active` und verwendet die Asset-ID ausschließlich
intern:

```python
from litellm import video_generation

video = video_generation(
    model="openai/dreamina-seedance-2-0-fast-260128",
    prompt="The person in Video 1 walks into a modern studio.",
    seconds="4",
    size="864x496",
    api_base="http://modelarkapi_server:8080/v1",
    api_key="your-proxy-key",
    extra_body={
        "references": [{
            "type": "video",
            "url": "https://example.com/person.mp4",
            "real_human": True,
        }],
        "generate_audio": False,
    },
)
```

## Provider-spezifische Optionen

Anbieterfelder ohne einheitliche Entsprechung gehören in
`provider_options.<anbieter>` (`modelark`, `google`, `kling`); nur der Block des
Zielmodells wird ausgewertet. Seedance-Felder wie `service_tier`,
`execution_expires_after`, `priority`, `camera_fixed`, `frames`, `draft`,
`callback_url` und `safety_identifier` stehen weiterhin auf oberster Ebene.
Welche Felder ein Modell kennt, listet sein Capability-Dokument unter
`provider_options` beziehungsweise `native_fields`. Die Seedance-Regeln stehen
in [Video-Generierung](docs/video-generierung/README.md).

## Lokal testen

Die Python-Umgebung einmalig einrichten; Server starten über **Local Full
Stack**:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
cd ui/frontend && npm ci && npm test
```

Die Tests verwenden simulierte Upstreams und verursachen keine Kosten. Die
LiteLLM-Ende-zu-Ende-Suite ist opt-in
(`LITELLM_VENVS=/venv-a:/venv-b pytest -m litellm`). Live-Tests gegen Anbieter
gibt es nur auf ausdrückliche Anforderung.
