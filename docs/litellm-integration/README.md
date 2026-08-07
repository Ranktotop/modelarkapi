# LiteLLM-Integration

## Modell konfigurieren

Den Inhalt von `litellm-config.example.yaml` in die LiteLLM-Konfiguration
übernehmen:

```yaml
model_list:
  - model_name: dreamina-seedance-2-0-fast-260128
    litellm_params:
      model: openai/dreamina-seedance-2-0-fast-260128
      api_base: http://modelarkapi_server:8080/v1
      api_key: os.environ/MODELARK_PROXY_API_KEY
```

LiteLLM verwendet damit seinen OpenAI-Videoadapter und sendet die konkrete
ModelArk-ID. Die aktuell im Account verfügbaren Seedance-IDs können vorher über
`GET /v1/models` am Proxy abgerufen werden.

## Gateway-Aufruf

```bash
curl -X POST http://localhost:4000/v1/videos \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"dreamina-seedance-2-0-fast-260128",
    "prompt":"A fox running through fresh snow",
    "seconds":"5",
    "size":"1280x720"
  }'
```

Provider-Erweiterungen wie `reference_urls`, `priority` oder
`return_last_frame` stehen im JSON-Body. Bei direkter Nutzung der LiteLLM-
Python-Funktion werden sie über `extra_body` mitgegeben. Asset-IDs werden nicht
von LiteLLM oder anderen Clients entgegengenommen.

```python
from litellm import video_generation

video = video_generation(
    model="openai/dreamina-seedance-2-0-fast-260128",
    prompt="The person in Video 1 turns toward the camera.",
    seconds="4",
    size="864x496",
    api_base="http://modelarkapi_server:8080/v1",
    api_key="proxy-key",
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

## IDs und Status

LiteLLM kann die Upstream-ID mit Routing-Informationen kodieren. Für Status,
Delete und Download muss exakt die vom LiteLLM-POST zurückgegebene ID verwendet
werden. Direkte Proxy-Aufrufe verwenden dagegen die ModelArk-ID `cgt-…`.

## Asynchroner Ablauf und Polling

`POST /v1/videos` wartet weder bei LiteLLM noch bei diesem Proxy auf das
gerenderte Video. Der Aufruf liefert eine Video-ID und einen Anfangsstatus wie
`queued`. LiteLLM bewahrt in seiner ausgegebenen ID die Provider- und
Deployment-Zuordnung auf und kann dadurch spätere Status- und Downloadaufrufe
wieder an denselben Proxy routen. Es startet jedoch keinen dauerhaften
Polling-Worker für den Job.

Der API-Client oder dessen Job-Worker muss den Status deshalb wiederholt
abfragen:

```bash
video_id="DIE_ID_AUS_DER_LITELLM_POST_ANTWORT"

while true; do
  response=$(curl -fsS \
    -H "Authorization: Bearer $LITELLM_KEY" \
    "http://localhost:4000/v1/videos/$video_id")
  status=$(printf '%s' "$response" | jq -r '.status')

  case "$status" in
    completed) break ;;
    failed) printf '%s\n' "$response" >&2; exit 1 ;;
  esac

  sleep 10
done

curl -fsS \
  -H "Authorization: Bearer $LITELLM_KEY" \
  "http://localhost:4000/v1/videos/$video_id/content" \
  --output result.mp4
```

Ein Intervall von etwa 10 Sekunden ist für normale Clients sinnvoll. Dieses
Create-, Poll- und Downloadmuster entspricht der offiziellen
[LiteLLM-Dokumentation für Vertex AI Veo](https://docs.litellm.ai/docs/providers/vertex_ai/videos).
Die dortigen synchronen und asynchronen Python-Beispiele rufen ebenfalls
`video_status` beziehungsweise `avideo_status` in einer Schleife auf;
`avideo_generation` bedeutet nicht, dass LiteLLM automatisch bis zum Ende
pollt.

### Real-Human-Jobs

Bei einer als `real_human` markierten Referenz gibt der Proxy bereits vor
Abschluss der Asset-Verifizierung eine lokale `video-rh-…`-ID zurück. Seine
persistenten Hintergrundworker pollen danach selbstständig die
Asset-Verifizierung, starten nach `Active` den Seedance-Task und überwachen
diesen bis zum Endstatus. Dieser interne Ablauf läuft auch weiter, wenn gerade
kein LiteLLM-Client den Status abfragt. Extern bleibt der Vertrag unverändert:
Der Client pollt die von LiteLLM erhaltene ID, um den aktuellen Zustand zu
erfahren.
