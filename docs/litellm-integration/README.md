# LiteLLM-Integration

## Modell konfigurieren

Den Inhalt von `litellm-config.example.yaml` in die LiteLLM-Konfiguration
übernehmen:

```yaml
model_list:
  - model_name: seedance
    litellm_params:
      model: openai/seedance
      api_base: http://modelark-video-proxy:8080/v1
      api_key: os.environ/MODELARK_PROXY_API_KEY
```

LiteLLM verwendet damit seinen OpenAI-Videoadapter. Der Modellalias bleibt
stabil; der Proxy löst ihn über `MODEL_MAP` zur im Account freigeschalteten
ModelArk-ID auf.

## Gateway-Aufruf

```bash
curl -X POST http://localhost:4000/v1/videos \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"seedance",
    "prompt":"A fox running through fresh snow",
    "seconds":"5",
    "size":"1280x720"
  }'
```

Provider-Erweiterungen wie `asset_id`, `reference_assets`, `priority` oder
`return_last_frame` stehen im JSON-Body. Bei direkter Nutzung der LiteLLM-
Python-Funktion werden sie über `extra_body` mitgegeben.

```python
from litellm import video_generation

video = video_generation(
    model="openai/seedance",
    prompt="The person in Image 1 turns toward the camera.",
    seconds="4",
    size="864x496",
    api_base="http://modelark-video-proxy:8080/v1",
    api_key="proxy-key",
    extra_body={"asset_id": "asset-…", "generate_audio": False},
)
```

## IDs und Status

LiteLLM kann die Upstream-ID mit Routing-Informationen kodieren. Für Status,
Delete und Download muss exakt die vom LiteLLM-POST zurückgegebene ID verwendet
werden. Direkte Proxy-Aufrufe verwenden dagegen die ModelArk-ID `cgt-…`.
