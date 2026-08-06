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
`input_reference`-Feld. Für bis zu drei Videos und neun Bilder ist daher
entweder `reference_urls`/`content` als Provider-Erweiterung oder ein späterer
nativer LiteLLM-Provider erforderlich.

## Lokal entwickeln und testen

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
```

Die Tests verwenden simulierte ModelArk-Antworten und verursachen keine Kosten.
