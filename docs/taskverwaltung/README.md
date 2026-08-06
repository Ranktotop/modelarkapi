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

```bash
curl -H "Authorization: Bearer $PROXY_KEY" \
  http://localhost:8080/v1/videos/cgt-…
```

Ein sinnvolles Polling-Intervall sind etwa 5–10 Sekunden. Aggressives Polling
erhöht nur Last und kann Quoten verbrauchen.

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
