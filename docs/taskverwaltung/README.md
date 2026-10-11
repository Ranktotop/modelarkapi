# Taskverwaltung

## Lebenszyklus

Der einheitliche Status lautet `queued`, `in_progress`, `completed` oder `failed`.
`provider_status` bewahrt den genaueren Anbieterzustand.

| Einheitlich | Seedance | Veo | Omni | Kling |
|---|---|---|---|---|
| `queued` | `queued` | Operation angelegt | `queued` | `submitted` |
| `in_progress` | `running` | `done=false` | `in_progress`, `requires_action` | `processing` |
| `completed` | `succeeded` | `done=true` mit Video | `completed` | `succeed` / `succeeded` |
| `failed` | `failed`, `cancelled`, `expired` | Fehler oder kein Video (RAI) | `failed`, `cancelled`, `incomplete` | `failed` |

Mehrstufige Jobs (Kling Lip Sync, Multi-Element-Edit, Seedance Real-Human) bleiben
`in_progress`, bis der letzte Schritt fertig ist; `provider_status` nennt den
Schritt (etwa `face_identification`, `asset_processing`, `rendering`). `progress`
ist eine Schätzung (0, ab 50 bei `in_progress`, 100 bei Abschluss), sofern der
Anbieter keinen Wert liefert.

## Status pollen

Ein Create-Aufruf liefert nur die Video-ID und den Anfangsstatus. Weder ein
direkter Proxy-Aufruf noch das LiteLLM Gateway wartet bis zum fertigen Video. Bei
Nutzung über LiteLLM pollt LiteLLM nicht selbstständig; der API-Client oder ein
eigener Job-Worker ruft den Status-Endpunkt wiederholt auf. Dabei muss exakt die
vom POST ausgegebene, gegebenenfalls kodierte Video-ID (`video_…`) verwendet
werden.

```bash
# Direkter Proxy-Aufruf (Entwicklung: Port 8081)
curl -H "Authorization: Bearer $PROXY_KEY" \
  http://127.0.0.1:8081/v1/videos/VIDEO_ID

# Aufruf über LiteLLM mit exakt der ID aus dessen Create-Antwort
curl -H "Authorization: Bearer $LITELLM_KEY" \
  http://localhost:4000/v1/videos/VIDEO_ID_AUS_LITELLM
```

Ein sinnvolles Polling-Intervall sind etwa 10 Sekunden. Aggressives Polling
erhöht nur Last und kann Quoten verbrauchen. Google- und Kling-Jobs fragt der
Proxy beim Anbieter höchstens alle `PROVIDER_STATUS_MIN_INTERVAL_SECONDS`
(Standard 2 s) je Job ab; dazwischen antwortet er mit dem gespeicherten Zustand.

Mehrstufige Jobs und Real-Human-Jobs laufen unabhängig vom externen Polling in
persistenten Proxy-Workern weiter. Das externe Polling dient nur dazu, den
Fortschritt beziehungsweise Endstatus zu erfahren. Ein Neustart des Proxys
setzt diese Jobs fort.

## Webhooks

Statt zu pollen kann ein Create-Aufruf `webhook_url` (HTTPS) mitgeben. Der Proxy
sendet bei jedem Wechsel auf `in_progress`, `completed` oder `failed` einen
`POST` mit dem Video-Objekt. Das Format folgt *Standard Webhooks*:

```json
{"id":"msg_…","type":"video.completed","created_at":1791720000,"data":{ …Video-Objekt… }}
```

Header: `webhook-id`, `webhook-timestamp`, `webhook-signature` (`v1,<base64>` über
`<id>.<timestamp>.<body>`, HMAC-SHA256). Der Schlüssel ist `WEBHOOK_SECRET`
(`whsec_<base64>` oder beliebiger Text).

- Ohne `WEBHOOK_SECRET` wird `webhook_url` mit `400 invalid_request` abgelehnt;
  es gehen nie unsignierte Webhooks raus.
- Beim Create wird nur geprüft, dass die URL ein absolutes `https` ist. Vor jeder
  Auslieferung löst der Proxy den Host auf und liefert nicht an private,
  Loopback- oder Link-Local-Adressen (SPEC 11.4 nennt die Prüfung schon beim
  Create).
- Ausstehende Auslieferungen liegen in SQLite (Datei `PROVIDER_JOB_DB`) und
  überleben Neustarts. Fehlgeschlagene Auslieferungen werden mit Backoff bis zu
  `WEBHOOK_MAX_ATTEMPTS` (Standard 8) wiederholt, dann verworfen. Erfolg ist jede
  2xx-Antwort; Redirects werden nicht verfolgt.
- Der Proxy nutzt keine Anbieter-Callbacks, sondern pollt selbst im Takt
  `WEBHOOK_INTERVAL_SECONDS` (Standard 5 s).
- `callback_url` ist das native Seedance-Feld: ModelArk ruft den Client direkt im
  ModelArk-Format und **ohne Signatur** auf. Wo Authentizität zählt, `webhook_url`
  verwenden. Replay-Schutz und Idempotenz bleiben Sache des Empfängers.

## Tasks auflisten

```bash
curl -H "Authorization: Bearer $PROXY_KEY" \
  'http://127.0.0.1:8081/v1/videos?page_num=1&page_size=20&filter.status=running'
```

Die Liste umfasst ausschließlich ModelArk-Tasks (Seedance). Filter:
`filter.status`, `filter.task_ids`, `filter.model`, `filter.service_tier`;
`page_num` und `page_size` liegen zwischen 1 und 500. ModelArk stellt nur einen
begrenzten historischen Zeitraum bereit; die Liste ist keine dauerhafte
Jobdatenbank. Google- und Kling-Jobs sind nur über ihre ID abrufbar (SPEC 11.5
sieht eine gemeinsame Liste vor; sie ist nicht umgesetzt).

## Abbrechen oder löschen

```bash
curl -X DELETE -H "Authorization: Bearer $PROXY_KEY" \
  http://127.0.0.1:8081/v1/videos/VIDEO_ID
```

| Anbieter | Wirkung |
|---|---|
| Seedance | wartend (`queued`): ModelArk bricht den Task ab, die Antwort meldet `cancelled`. Beendet: ModelArk löscht den Datensatz, die Antwort enthält `deleted: true`. Laufend (`running`): `409 video_running`, weder Abbruch noch Löschen möglich. Real-Human-Jobs werden abgebrochen und ihre temporären Assets gelöscht |
| Omni | laufender Job wird beim Anbieter abgebrochen (Teilkosten möglich), dann lokal gelöscht |
| Veo | nur lokal gelöscht; der Anbieter-Job läuft weiter und wird berechnet |
| Kling | nur lokal gelöscht (Kling hat keinen Abbruch); der Job läuft weiter und wird berechnet |

Über LiteLLM ist `DELETE` nicht erreichbar (405).

## Ergebnis laden

```bash
curl -H "Authorization: Bearer $PROXY_KEY" \
  'http://127.0.0.1:8081/v1/videos/VIDEO_ID/content' --output result.mp4

# Variante und Ausgabe wählen
curl -H "Authorization: Bearer $PROXY_KEY" \
  'http://127.0.0.1:8081/v1/videos/VIDEO_ID/content?variant=audio&output=0' --output sound.mp3

curl -H "Authorization: Bearer $PROXY_KEY" \
  http://127.0.0.1:8081/v1/videos/VIDEO_ID/last_frame --output last-frame.png
```

`variant`: `video` (Standard), `audio` (`format=wav` für WAV), `watermarked`,
`last_frame`; Kling-Apparel liefert zusätzlich `product_image_n` und
`model_image_n`. `thumbnail` und `spritesheet` ergeben `400`. Welche Varianten ein
Job hat, steht unter `outputs[].variants`. Reine Audio-Tasks (`text_to_audio`)
liefern nur `audio`; `variant=video` ergibt 404. Über LiteLLM kommt immer das
Hauptergebnis.

Das letzte Frame gibt es nur bei Seedance, wenn der Task mit
`return_last_frame: true` erstellt wurde. Ist ein Job noch nicht fertig, antwortet
`/content` mit `409 video_not_ready`; ein abgelaufenes lokal gespeichertes Ergebnis
mit `410 output_expired`.

**Aufbewahrung.** Seedance-Ergebnis-URLs sind zeitlich begrenzt (laut Proxy-Status
`expires_at` etwa 24 Stunden nach Abschluss). Google- und Kling-Ergebnisse kopiert
der Proxy in den Output-Speicher und hält sie `PROVIDER_JOB_TTL_SECONDS` (Standard
48 Stunden); Gemini-Dateien löscht Google nach zwei Tagen, Kling-URLs laufen nach
30 Tagen ab und sind hotlink-geschützt. Wichtige Resultate müssen zeitnah in eine
eigene dauerhafte Ablage kopiert werden.
