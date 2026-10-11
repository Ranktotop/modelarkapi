# LiteLLM-Integration

LiteLLM verwendet für alle Modelle seinen OpenAI-Videoadapter
(`model: openai/<modell>`). Der Proxy übersetzt dahinter in Seedance, Veo, Omni
und Kling. Der Vertrag für Apps steht in [SPEC.md](../SPEC.md), Abschnitt 18.

## Modelle konfigurieren: Export

Die `model_list`-Einträge erzeugt der Proxy aus den aktiven Modellen:

```bash
curl -H "Authorization: Bearer $PROXY_API_KEY" \
  'http://127.0.0.1:8081/v1/litellm/config?format=yaml&api_base=http://modelarkapi_server:8080/v1' \
  > litellm-models.yaml
```

| Parameter | Bedeutung |
|---|---|
| `format` | `yaml` (Standard) oder `json` |
| `api_base` | Basis-URL, die LiteLLM aufruft; Standard `PUBLIC_BASE_URL/v1`, sonst `http://modelarkapi_server:8080/v1` |
| `name_template` | Muster für `model_name`; Standard `{family_slug}_api`; erlaubt sind `{family_slug}` und `{model}` |

Der Export schreibt nichts in LiteLLM. Das Ergebnis, hier gekürzt:

```yaml
model_list:
  - model_name: veo_31_fast_api
    litellm_params:
      model: openai/veo-3.1-fast-generate-001
      api_base: http://modelarkapi_server:8080/v1
      api_key: os.environ/MODELARK_PROXY_API_KEY
    model_info:
      mode: video_generation          # audio_speech für kling-tts
      provider: google
      capabilities: {…}               # Capability-Dokument v2
      prompt_guide: "…Markdown-Volltext…"
      prompt_guide_url: https://…/v1/prompt-guides/veo_3_1
```

- `model_name` leitet sich aus der Modellfamilie ab (`family_slug`). Die
  bisherigen Namen bleiben erhalten: `seedance_25_api`, `seedance_20_fast_api`.
- Virtuelle Kling-Modelle erscheinen wie echte; `kling-tts` bekommt
  `mode: audio_speech`.
- `prompt_guide_url` ist nur gesetzt, wenn `PUBLIC_BASE_URL` konfiguriert ist.
- Die Datei `litellm-config.example.yaml` im Repository zeigt vier Einträge im
  Format des Exports (Seedance, Veo, Kling, `kling_tts_api`); die vollständige
  Liste liefert `GET /v1/litellm/config`.

Beim LiteLLM-Container muss gesetzt sein:

```bash
MODELARK_PROXY_API_KEY=<derselbe mindestens 32 Zeichen lange PROXY_API_KEY>
```

## Capabilities und Prompt Guides über LiteLLM

Apps lesen beides aus `GET /v1/model/info` von LiteLLM (`model_info.capabilities`,
`model_info.prompt_guide` als Markdown-Text) und filtern clientseitig nach
`model_name`. Ein Pass-Through der Proxy-Routen ist nicht nötig.

## Gateway-Aufruf

Alle Felder des einheitlichen Vertrags stehen auf oberster Ebene des JSON-Bodys.
Strukturierte Felder (`references`, `shots`, `speech`, `provider_options` …) am
besten als JSON-String senden; das ist laut Test in allen LiteLLM-Versionen
gleich robust.

```bash
curl -X POST http://localhost:4000/v1/videos \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"seedance_25_api",
    "prompt":"A fox running through fresh snow",
    "seconds":"5",
    "size":"1280x720"
  }'
```

Dateien als `data:`-URI oder öffentliche `https`-URL in `references[].url`; für
genau eine Bilddatei geht auch `input_reference` als Multipart-Datei (nur
Seedance). Bei direkter Nutzung der LiteLLM-Python-Funktion kommen
Anbieterfelder über `extra_body`:

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
        "references": [{
            "type": "video",
            "url": "https://example.com/person.mp4",
            "real_human": True,
        }],
        "generate_audio": False,
    },
)
```

## Getestete LiteLLM-Versionen

`tests/integration/test_litellm.py` startet echte LiteLLM-Proxies (1.95.0,
1.104.2 und 1.105.0) vor dem Proxy; dessen Anbieter sind simulierte Upstreams,
es entstehen keine Kosten. Die Suite (30 Tests) ist opt-in; jede virtuelle Umgebung braucht
`litellm[proxy]`:

```bash
LITELLM_VENVS=/venv-a:/venv-b pytest -m litellm
```

**Funktioniert über LiteLLM:**

| Funktion | Anmerkung |
|---|---|
| `GET /v1/model/info` | `model_info.prompt_guide` (Text) und `capabilities` |
| `POST /v1/videos` | JSON und Multipart |
| `GET /v1/videos/{id}` und `/content` | mit der ID aus der Create-Antwort |
| Remix | auch mit `extra_body` |
| `POST /v1/videos/edits` | zusätzliche Felder nur in `extra_body` |
| `POST /v1/videos/extensions` | LiteLLM verlangt `seconds` |
| `POST /v1/audio/speech` | `kling-tts` (Modus `audio_speech`) |
| `POST /v1/videos/characters` (+ `GET …/{id}`) | legt ein Kling-Video-Element an; LiteLLM sendet nur `name` und `video`. IDs `character_<base64>`, auch als `asset_id` nutzbar |

**Nicht über LiteLLM erreichbar** (direkt am Proxy mit dem Proxy-Key nutzen):

| Funktion | Verhalten von LiteLLM |
|---|---|
| `GET /v1/videos` (Liste) | 400 |
| `DELETE /v1/videos/{id}` | 405 |
| `GET …/content?variant=` | der Parameter wird nicht weitergegeben; es kommt immer das Hauptvideo (auch bei Audio-Ergebnissen; LiteLLM meldet `video/mp4`, die Bytes stimmen) |
| `output` > 0, `last_frame`, `/v1/assets`, Guides als Ressource | nicht geroutet |

LiteLLM < 1.100 sendet Formularfelder als JSON-Strings (`"true"`, `"5"`); der
Proxy typisiert Booleans und Integer. Ab 1.100 erzeugt LiteLLM Multipart-
Klammernotation (`references[][url]=…`), die der Proxy ebenfalls liest. Ob eine
LiteLLM-Version nach 1.105.0 `DELETE` oder `variant` durchreicht, ist offen.

Über LiteLLM sind mehrere Varianten (`n` > 1) nicht abrufbar; Apps senden dann
`n` Einzelanfragen.

## IDs und Status

Antworten enthalten IDs im Format `video_<base64>`, das LiteLLM versteht: Das
Modell der Create-Anfrage steckt darin, damit LiteLLM Status-, Remix-, Edit- und
Extension-Aufrufe wieder an diesen Proxy routet. Für Status und Download muss die
von LiteLLM zurückgegebene ID verwendet werden; der Proxy akzeptiert zusätzlich
die internen Formen (`cgt-…`, `vid-<anbieter>-…`).

## Asynchroner Ablauf und Polling

`POST /v1/videos` wartet weder bei LiteLLM noch bei diesem Proxy auf das
gerenderte Video. Der Aufruf liefert eine Video-ID und einen Anfangsstatus wie
`queued`. LiteLLM startet jedoch keinen Polling-Worker für den Job. Der API-Client
oder dessen Job-Worker muss den Status wiederholt abfragen:

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

Ein Intervall von etwa 10 Sekunden ist sinnvoll. Das Muster entspricht der
offiziellen
[LiteLLM-Dokumentation für Vertex AI Veo](https://docs.litellm.ai/docs/providers/vertex_ai/videos).
Wer statt Polling Benachrichtigungen will, setzt `webhook_url` (siehe
[Taskverwaltung](../taskverwaltung/README.md#webhooks)); die Weitergabe des Felds
durch LiteLLM ist nicht in der Suite abgedeckt.

### Real-Human-Jobs

Bei einer als `real_human` markierten Referenz gibt der Proxy bereits vor
Abschluss der Asset-Verifizierung eine lokale `video-rh-…`-ID zurück. Seine
persistenten Hintergrundworker pollen selbstständig die Asset-Verifizierung,
starten nach `Active` den Seedance-Task und überwachen ihn bis zum Endstatus.
Extern bleibt der Vertrag unverändert: Der Client pollt die von LiteLLM erhaltene
ID, um den Zustand zu erfahren. Mehrstufige Kling-Jobs (Lip Sync, Multi-Element-
Edit) verhalten sich genauso.
