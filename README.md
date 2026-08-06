# ModelArk OpenAI Video Proxy

Dieser Dienst übersetzt die von LiteLLM verwendete OpenAI Videos API in die
asynchrone Video-API von BytePlus ModelArk. Damit lässt sich Seedance hinter
einem bestehenden LiteLLM Gateway wie ein OpenAI-kompatibles Videomodell
verwenden.

Unterstützt sind:

- `POST /v1/videos` (JSON oder Multipart, inklusive `input_reference`)
- `GET /v1/videos/{id}` (Status)
- `GET /v1/videos/{id}/content` (MP4-Download als Stream)
- `DELETE /v1/videos/{id}` (Abbruch/Löschen bei ModelArk)
- Text-to-video, Bildreferenz und eine hochgeladene MP4/MOV-Videoreferenz
- zusätzliche Referenzen als öffentliche URLs (`reference_urls`)
- verifizierte Real-Human-Assets über `asset://...` (`asset_id`,
  `reference_asset_ids` oder `reference_assets`)
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
# .env ausfüllen
docker compose up --build -d
curl http://localhost:8080/health
```

Wesentliche Variablen:

| Variable | Bedeutung |
|---|---|
| `ARK_API_KEY` | ModelArk API Key |
| `PUBLIC_BASE_URL` | Öffentliche HTTPS-Basis-URL dieses Proxys; für Uploads Pflicht |
| `PROXY_API_KEY` | Optionaler Schlüssel zwischen LiteLLM und diesem Proxy |
| `DEFAULT_MODEL` | ModelArk-Modell-ID |
| `MODEL_MAP` | Optionales JSON mit Modell-Aliasen |

## LiteLLM anbinden

Den Eintrag aus `litellm-config.example.yaml` in die LiteLLM-Konfiguration
übernehmen und beim LiteLLM-Container setzen:

```bash
MODELARK_PROXY_API_KEY=choose-a-private-key-for-litellm
```

`api_base` muss auf `/v1` dieses Dienstes zeigen. Weil LiteLLM Seedance noch
nicht nativ kennt, wird bewusst sein vorhandener `openai`-Video-Adapter benutzt.
LiteLLM sendet dabei den stabilen Alias `seedance`; über `MODEL_MAP` in `.env`
kann dieser ohne Änderung an LiteLLM auf die für den Account freigeschaltete
ModelArk-ID zeigen. Das Beispiel verwendet aktuell
`dreamina-seedance-2-0-fast-260128`.

Text-to-video über das LiteLLM Gateway:

```bash
curl -X POST http://localhost:4000/v1/videos \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "seedance",
    "prompt": "A fox running through fresh snow",
    "seconds": "5",
    "size": "1280x720"
  }'
```

Videoreferenz hochladen:

```bash
curl -X POST http://localhost:4000/v1/videos \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -F 'model=seedance' \
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
- [ ] Die Asset-ID kopieren. Für die API wird daraus
      `asset://<asset_id>`; eine öffentliche `PUBLIC_BASE_URL` ist dafür nicht
      erforderlich.
- [ ] Erst danach den unten beschriebenen lokalen Übersetzungstest ausführen.
- [ ] Den kostenpflichtigen Live-Test ganz zuletzt mit 4 Sekunden, 480p und
      ohne Audio starten.

Die Verifizierung ist pro Person und Asset-Gruppe nur einmal nötig. Weitere
Looks derselben Person können später ergänzt werden, durchlaufen aber jeweils
eine Konsistenzprüfung. Die kostenlose Basic-Stufe wird derzeit mit bis zu 50
Assets und 50 Asset-Gruppen geführt; die vollständige Assets-API kann je nach
Account eine Enterprise-/Entry-Freischaltung oder Einladung erfordern.

### Verifiziertes Bild über LiteLLM verwenden

Der Proxy akzeptiert eine einzelne Bild-Asset-ID über `asset_id`. LiteLLM
reicht das Feld über `extra_body` an den Adapter weiter:

```python
from litellm import video_generation

video = video_generation(
    model="openai/seedance",
    prompt="The person in Image 1 walks into a modern studio and looks at the camera.",
    seconds="4",
    size="864x496",
    api_base="http://modelark-video-proxy:8080/v1",
    api_key="your-proxy-key",
    extra_body={
        "asset_id": "asset-2026...",
        "generate_audio": False,
    },
)
```

Über das LiteLLM Gateway kann dasselbe Feld im JSON-Body stehen:

```bash
curl -X POST http://localhost:4000/v1/videos \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "seedance",
    "prompt": "The person in Image 1 walks into a modern studio.",
    "seconds": "4",
    "size": "864x496",
    "asset_id": "asset-2026...",
    "generate_audio": false
  }'
```

Mehrere oder typisierte Assets werden mit `reference_assets` übergeben:

```json
{
  "reference_assets": [
    {"id": "asset-image-...", "type": "image"},
    {"id": "asset-video-...", "type": "video"},
    {"id": "asset-audio-...", "type": "audio"}
  ]
}
```

Erlaubte Typen sind `image`, `video` und `audio`. Im Prompt werden sie anhand
ihrer Reihenfolge als `Image 1`, `Video 1` oder `Audio 1` bezeichnet – nicht
mit der Asset-ID. Der Adapter normalisiert und validiert die IDs und erzeugt
die von ModelArk erwarteten `asset://...`-URIs.

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
`input_reference`-Feld. Der Adapter nutzt deshalb `reference_urls`,
`reference_assets` oder `content` als Provider-Erweiterungen für mehrere
Referenzen.

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
