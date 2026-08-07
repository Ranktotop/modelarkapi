# ModelArk OpenAI Video Proxy

Dieser Dienst übersetzt die von LiteLLM verwendete OpenAI Videos API in die
asynchrone Video-API von BytePlus ModelArk. Damit lässt sich Seedance hinter
einem bestehenden LiteLLM Gateway wie ein OpenAI-kompatibles Videomodell
verwenden.

Die vollständige, thematisch gegliederte Dokumentation beginnt unter
[docs/dokumentation.md](docs/dokumentation.md).

Zusätzlich enthält das Projekt ein temporäres
[Seedance Web Studio](docs/web-studio/README.md) als separaten Docker-Container.
Es ermöglicht direkte Single-User-Generierungen ohne LiteLLM und speichert
fertige Videos nicht dauerhaft auf dem Server.

Unterstützt sind:

- `POST /v1/videos` (JSON oder Multipart, inklusive `input_reference`)
- `GET /v1/models` (live verfügbare Seedance-Modelle des BytePlus-Kontos)
- `POST /v1/media/references` (mehrere temporäre Bild-/Video-/Audio-Uploads)
- `GET /v1/videos` (Taskliste und Filter)
- `GET /v1/videos/{id}` (Status)
- `GET /v1/videos/{id}/content` (MP4-Download als Stream)
- `GET /v1/videos/{id}/last_frame` (optionales PNG-Endframe)
- `DELETE /v1/videos/{id}` (Abbruch/Löschen bei ModelArk)
- Text-to-video, Bildreferenz und eine hochgeladene MP4/MOV-Videoreferenz
- zusätzliche Referenzen als öffentliche URLs (`reference_urls`)
- automatische temporäre Registrierung neuer Real-Human-Referenzen über
  `real_human: true`, einschließlich Status-Polling und `DeleteAsset`-Cleanup
- Übersetzung von `seconds` → `duration` und `size` → `resolution` + `ratio`

## Die wichtige Einschränkung bei Video-Uploads

ModelArk akzeptiert Referenzvideos **nur als öffentlich abrufbare URL**, nicht
als Base64 oder Multipart-Upload. Die Kette funktioniert daher so:

```text
Client --multipart--> LiteLLM --multipart--> dieser Proxy
       dieser Proxy --öffentliche, zufällige URL--> ModelArk/Seedance
```

Der Proxy speichert den Upload temporär unter einer kryptografisch zufälligen
URL. `PUBLIC_BASE_URL` muss deshalb aus dem Internet per HTTPS erreichbar sein;
`localhost`, eine reine Docker-Adresse oder ein nur internes LAN reichen nicht.
Die Dateien werden standardmäßig nach 24 Stunden entfernt. Für eine Produktion
sollte TLS vor dem Dienst terminiert werden (z. B. Caddy, Traefik oder Nginx).

Seedance 2.0 nimmt direkte Referenz-Uploads mit echten menschlichen Gesichtern
laut ModelArk-Dokumentation nicht allgemein an. Dafür müssen die von BytePlus
vorgesehenen vertrauenswürdigen Outputs, autorisierten Personen-Assets oder
Digital-Character-Assets verwendet werden.

LiteLLM bezeichnet `input_reference` gemäß OpenAI als Bild. Aktuelle LiteLLM-
Versionen reichen jedoch beliebige Bytes durch und etikettieren unbekannte
Dateien gegebenenfalls als `image/png`. Der Proxy prüft deshalb die tatsächliche
Dateisignatur und erkennt MP4/MOV unabhängig vom von LiteLLM gesetzten MIME-Typ.

## Start

```bash
cp .env.example .env
# .env ausfüllen, einschließlich UI_USERNAME, UI_PASSWORD und UI_SESSION_SECRET
# Zufallswerte zum Beispiel mit: openssl rand -hex 32
docker compose up --build -d
curl http://localhost:8080/health
curl http://localhost:3000/health
```

Die Single-User-Oberfläche ist anschließend unter `http://localhost:3000`
erreichbar. Bei Betrieb hinter HTTPS muss `UI_COOKIE_SECURE=true` gesetzt sein.

Wesentliche Variablen:

| Variable | Bedeutung |
|---|---|
| `ARK_API_KEY` | ModelArk API Key |
| `CREDENTIAL_VALIDATION_INTERVAL_SECONDS` | Abstand der erneuten API-Key-/IAM-Prüfung (Standard: drei Stunden) |
| `PUBLIC_BASE_URL` | Öffentliche HTTPS-Basis-URL dieses Proxys; für Uploads Pflicht |
| `PROXY_API_KEY` | verpflichtender Schlüssel im Docker-Deployment zwischen LiteLLM und Proxy |
| `BYTEPLUS_ACCESS_KEY_ID` / `BYTEPLUS_SECRET_ACCESS_KEY` | verpflichtender IAM-Zugang für die Live-Modellliste |
| `MODEL_CACHE_TTL_SECONDS` | Cache-Dauer der live abgerufenen Modellauswahl |

Der Proxy prüft beim Start mit kostenfreien Read-only-Aufrufen sowohl den
`ARK_API_KEY` als auch den IAM-Zugang und wiederholt dies standardmäßig alle drei
Stunden. Bei ungültigen Zugangsdaten bleibt der Prozess samt `/health` erreichbar,
antwortet auf Fachrouten aber mit `503 upstream_credentials_invalid`. Sobald eine
spätere Prüfung erfolgreich ist, werden die Routen automatisch wieder freigegeben.

Der allgemeine BytePlus-Kontosaldo ist kein verlässlicher Indikator für
Seedance-Resource-Packages und wird daher weder angezeigt noch als Sperre
verwendet. BytePlus dokumentiert die Package-Restmenge derzeit nur im Billing
Center. Meldet ModelArk bei einem echten Generierungsaufruf ein erschöpftes
Package, reicht der Proxy dessen Fehlercode und Meldung an LiteLLM und UI weiter.

## LiteLLM anbinden

Den Eintrag aus `litellm-config.example.yaml` in die LiteLLM-Konfiguration
übernehmen und beim LiteLLM-Container setzen:

```bash
MODELARK_PROXY_API_KEY=<derselbe mindestens 32 Zeichen lange PROXY_API_KEY>
```

`api_base` muss auf `/v1` dieses Dienstes zeigen. Weil LiteLLM Seedance noch
nicht nativ kennt, wird bewusst sein vorhandener `openai`-Video-Adapter benutzt.
LiteLLM sendet die konkrete, versionierte ModelArk-ID. Die aktuell verfügbaren
Seedance-IDs liefert dieser Proxy über `GET /v1/models`; das Beispiel verwendet
`dreamina-seedance-2-0-fast-260128`.

Text-to-video über das LiteLLM Gateway:

```bash
curl -X POST http://localhost:4000/v1/videos \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "dreamina-seedance-2-0-fast-260128",
    "prompt": "A fox running through fresh snow",
    "seconds": "5",
    "size": "1280x720"
  }'
```

Videoreferenz hochladen:

```bash
curl -X POST http://localhost:4000/v1/videos \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -F 'model=dreamina-seedance-2-0-fast-260128' \
  -F 'prompt=Continue this scene with a slow camera pullback' \
  -F 'seconds=6' \
  -F 'size=1280x720' \
  -F 'input_reference=@reference.mp4;type=video/mp4'
```

Status und Ergebnis:

```bash
curl -H "Authorization: Bearer $LITELLM_KEY" \
  http://localhost:4000/v1/videos/VIDEO_ID

curl -H "Authorization: Bearer $LITELLM_KEY" \
  http://localhost:4000/v1/videos/VIDEO_ID/content \
  --output result.mp4
```

LiteLLM kodiert die zurückgegebene Video-ID intern mit Routing-Informationen.
Beim Status- und Download-Aufruf muss deshalb genau die von LiteLLM erhaltene
ID verwendet werden.

## Eigene Gesichter: Freischaltung und Verifizierung

Seedance 2.0 akzeptiert ein Foto oder Video mit einer realen Person nicht als
gewöhnliche URL oder Datei. Für das eigene Gesicht ist die private
**Real-human Asset Library** vorgesehen. BytePlus führt dabei eine
Echtzeit-Lebendprüfung durch und vergleicht spätere Uploads biometrisch mit der
verifizierten Person.

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
    api_base="http://modelark-video-proxy:8080/v1",
    api_key="your-proxy-key",
    extra_body={
        "reference_urls": [{
            "url": "https://example.com/person.mp4",
            "media_type": "video",
            "real_human": True,
        }],
        "generate_audio": False,
    },
)
```

## Provider-spezifische Optionen

Bei einem direkten Request an diesen Proxy können ModelArk-Felder wie
`generate_audio`, `watermark`, `resolution`, `ratio`, `duration`, `priority`,
`service_tier` und `return_last_frame` mitgegeben werden. Mehrere öffentliche
Referenzen sind über `reference_urls` möglich:

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "prompt": "Use @Video1 as the motion reference",
  "reference_urls": [
    {"url": "https://example.com/reference.mp4", "media_type": "video/mp4"}
  ],
  "generate_audio": true,
  "ratio": "16:9",
  "resolution": "720p",
  "duration": 6
}
```

Die standardisierte OpenAI/LiteLLM-Oberfläche besitzt nur ein
`input_reference`-Feld. Der Adapter nutzt deshalb `reference_urls` oder
`content` als Provider-Erweiterungen für mehrere Referenzen. Extern gelieferte
Asset-IDs werden abgewiesen.

## Lokal entwickeln und testen

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
```

Die Tests verwenden simulierte ModelArk-Antworten und verursachen keine Kosten.
Der Live-Test für ein verifiziertes Real-Human-Asset bleibt bewusst ausstehend,
bis Freischaltung, Einwilligung und Asset-Status `Active` bestätigt sind.
