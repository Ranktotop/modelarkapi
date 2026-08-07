# Taskverwaltung

## Lebenszyklus

```text
queued → running → succeeded
                 ↘ failed / cancelled / expired
```

Der OpenAI-nahe Status lautet entsprechend `queued`, `in_progress`,
`completed` oder `failed`. `provider_status` bewahrt den genaueren
ModelArk-Zustand.

## Status pollen

Ein Create-Aufruf liefert nur die Task-ID und den Anfangsstatus. Weder ein
direkter Proxy-Aufruf noch das LiteLLM Gateway wartet bis zum fertigen Video.
Bei Nutzung über LiteLLM pollt LiteLLM nicht selbstständig; der API-Client oder
ein eigener Job-Worker ruft den Status-Endpunkt wiederholt auf. Dabei muss
exakt die vom LiteLLM-POST ausgegebene, gegebenenfalls kodierte Video-ID
verwendet werden.

```bash
# Direkter Proxy-Aufruf mit der ModelArk- oder lokalen Real-Human-ID
curl -H "Authorization: Bearer $PROXY_KEY" \
  http://localhost:8080/v1/videos/cgt-…

# Aufruf über LiteLLM mit exakt der ID aus dessen Create-Antwort
curl -H "Authorization: Bearer $LITELLM_KEY" \
  http://localhost:4000/v1/videos/VIDEO_ID_AUS_LITELLM
```

Ein sinnvolles Polling-Intervall sind etwa 10 Sekunden. Aggressives Polling
erhöht nur Last und kann Quoten verbrauchen.

Real-Human-Jobs sind davon unabhängig: Persistente Proxy-Worker führen
Asset-Verifizierung und Seedance-Generierung intern weiter, auch wenn gerade
kein externer Statusaufruf stattfindet. Das externe Polling dient in diesem
Fall nur dazu, den Fortschritt beziehungsweise Endstatus zu erfahren.

## Tasks auflisten

```bash
curl -H "Authorization: Bearer $PROXY_KEY" \
  'http://localhost:8080/v1/videos?page_num=1&page_size=20&filter.status=running'
```

ModelArk stellt nur einen begrenzten historischen Zeitraum bereit. Die Liste
ist deshalb keine dauerhafte Jobdatenbank.

## Abbrechen oder löschen

```bash
curl -X DELETE -H "Authorization: Bearer $PROXY_KEY" \
  http://localhost:8080/v1/videos/cgt-…
```

Bei wartenden/laufenden Tasks wirkt DELETE als Abbruch; bei abgeschlossenen
Tasks löscht ModelArk den Taskdatensatz gemäß seiner API-Semantik.

## Ergebnis laden

```bash
curl -H "Authorization: Bearer $PROXY_KEY" \
  http://localhost:8080/v1/videos/cgt-…/content --output result.mp4

curl -H "Authorization: Bearer $PROXY_KEY" \
  http://localhost:8080/v1/videos/cgt-…/last_frame --output last-frame.png
```

Das letzte Frame existiert nur, wenn der Task mit `return_last_frame: true`
erstellt wurde. ModelArk-Ergebnis-URLs sind zeitlich begrenzt; wichtige
Resultate müssen zeitnah in eine eigene dauerhafte Ablage kopiert werden.
