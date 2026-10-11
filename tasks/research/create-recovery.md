# Create-Recovery: verlorene Create-Antworten bei bezahlten Video-Jobs

Stand der Recherche: **2026-10-11**. Es wurden keine Code-Änderungen und keine bezahlten API-Calls gemacht.

Kennzeichnung jeder Aussage:
- **[Doku]**: offizielle Dokumentation oder API-Referenz.
- **[Code/SDK]**: Discovery-Dokument, OpenAPI-Spec oder SDK-Quellcode.
- **[Issue/Forum]**: GitHub-Issue oder Entwicklerforum.
- **[unklar]**: Schlussfolgerung, nicht belegt.

Feld- und API-Namen sind auf Englisch belassen.

Anlass: Am 2026-10-11 lieferte `POST https://aiplatform.googleapis.com/v1beta1/projects/{P}/locations/global/interactions` (`gemini-omni-1.1-flash-preview`, `background: true`, `store: true`) innerhalb von 60 s keine Response-Header (httpx `ReadTimeout`). Ein identischer zweiter Call kam sofort mit `in_progress` zurück. `GET …/interactions?page_size=5` lieferte danach `{}`.

---

## A. Google Interactions API (Gemini API und Vertex)

### A1. Kehrt der Create mit `background: true` garantiert sofort zurück?

- **Laut Doku ja, eine Zusage mit Zeitgrenze (SLA) gibt es aber nicht.** Die Doku schreibt: „set `"background": true` … The API immediately returns an interaction ID“. Begründet wird das mit HTTP-Requests, die „typically close after 60 seconds“. **[Doku]** https://ai.google.dev/gemini-api/docs/background-execution
- Für Vertex steht in der Doku dasselbe: „The API immediately returns an Interaction object with an id that you can poll“. **[Doku]** https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/interactions/developer-guide
- **Vertex unterstützt Background für Omni.** Googles offizielles Vertex-Notebook zu Omni nutzt `client.interactions.create(model=omni_model, input=prompt, background=True)` mit `genai.Client(enterprise=True, location="global")` und pollt danach per `interactions.get`. **[Doku/Code]** https://github.com/GoogleCloudPlatform/generative-ai/blob/main/vision/getting-started/gemini_omni_1_1_flash_video_gen.ipynb
- Die Omni-Doku der Gemini API empfiehlt `background=false, store=false, stream=false` „for faster, synchronous unary generation“. Background ist also ein unterstützter, aber nicht der schnellste Pfad. **[Doku]** https://ai.google.dev/gemini-api/docs/omni
- Das Enum `status` enthält **`QUEUED`** („waiting for processing (e.g. waiting for off-peak capacity)“). Queueing ist also vorgesehen, mindestens für Flex/Deferred-Tiers. **[Code/SDK]** Vertex-Discovery, Schema `GenaiVertexV1beta1Interaction.status`: https://aiplatform.googleapis.com/$discovery/rest?version=v1beta1
- **Berichte über Störungen rund um Background-Creates:**
  - Gemini API, 2026-09-21: Background-Creates bekamen 20:55–21:10 UTC zeitweise HTTP 400 „does not support background interactions“. Einige Creates im selben Fenster lieferten eine ID, die später auf `failed` ging. Google: „We are looking into this.“ **[Issue/Forum]** https://discuss.ai.google.dev/t/gemini-3-8-flash-and-gemini-3-1-flash-lite-intermittently-return-400-does-not-support-background-interactions/184236
  - Gemini API, 2026-09-17/18: Der Create lieferte 200/`in_progress`, danach ergab jeder GET 404. Ein Maintainer sprach von einem „temporary backend hiccup“. **[Issue/Forum]** https://github.com/googleapis/python-genai/issues/2985
  - Gemini API, seit 3./4. Oktober: Background-Create ok, GET mit 400 (Auth-Fehler). **[Issue/Forum]** https://discuss.ai.google.dev/t/get-v1beta-interactions-id-returns-400-multiple-authentication-credentials-received-for-background-interactions-aq-key-since-oct-3-4/186789
  - Vertex, Omni: Interactions blieben > 60 min `in_progress`, obwohl das Video schon geliefert war. Danach kam ein 500 beim Verketten. **[Issue/Forum]** https://discuss.google.dev/t/issue-report-gemini-omni-1-1-flash-video-prolonged-in-progress-status-on-scene-extension-causing-http-500-error/400710
  - Laut Suchtreffer hat ein LiteLLM-Fork-PR („render Omni video synchronously, Google stopped resolving backgrounded interactions“) auf synchrones Rendern umgestellt und dabei 23–38 s gemessen. Das Repo ist inzwischen nicht mehr erreichbar (404). **[Issue/Forum, nicht verifizierbar]** https://github.com/nolgiainc/litellm/pull/95
- **Einen dokumentierten Fall „Create blockiert > 60 s trotz background“ habe ich nicht gefunden.** Unser Vorfall ist damit nicht offiziell erklärt. Denkbar sind ein Cold Start, ein Vorab-Upload oder eine Validierung der Inputs vor dem Erzeugen der ID, oder eine Störung im Backend. **[unklar]**

### A2. Eigene Interaction-ID, Request-ID oder Idempotency-Key?

- **Nein. Es gibt weder ein Idempotency-Feld noch einen solchen Header.** In der Vertex-Discovery hat `GenaiVertexV1beta1CreateInteractionRequest` nur `interaction`, `background`, `store` und `stream`. `Interaction.id` ist „Output only“. In keinem `GenaiVertex*`-Schema gibt es ein Feld `requestId`, `idempotency…` oder `dedup…`. **[Code/SDK]** https://aiplatform.googleapis.com/$discovery/rest?version=v1beta1 (Revision 20261007)
- In der OpenAPI-Spec der Gemini API hat `POST /{api_version}/interactions` keine Parameter, und es gibt kein Idempotency-Feld. **[Code/SDK]** https://ai.google.dev/static/api/interactions.openapi.json, Referenz https://ai.google.dev/api/interactions-api
- **Das offizielle SDK `google-genai` hat keinen Idempotency-Key, wiederholt Creates aber automatisch.** Der generierte Client `_gaos/interactions.py` nutzt `retry_config = (retries, ["408","409","429","5XX"])` mit `retry_connection_errors=True`. `retries.py` behandelt dabei auch `httpx.TimeoutException` als wiederholbar. Der Default sind 2 Retries (`_DEFAULT_MAX_RETRIES = 2`, `_MAX_ELAPSED_TIME_MS = 30000`). Das Default-Timeout für Interactions ist `httpx.Timeout(None)`, also unbegrenzt (Tests `test_client_vertex_default_timeout`). Wer im SDK ein Timeout setzt, riskiert damit doppelte Creates. **[Code/SDK]** https://github.com/googleapis/python-genai/blob/main/google/genai/_gaos/interactions.py , https://github.com/googleapis/python-genai/blob/main/google/genai/_gaos/google_genai.py , https://github.com/googleapis/python-genai/blob/main/google/genai/tests/interactions/test_integration.py (Commit 969d0e7, 2026-10-09)
- **Was es gibt:** `labels` (map, Keys/Values ≤ 63 Zeichen, nur Kleinbuchstaben, Ziffern, `_` und `-`) sowohl auf Vertex als auch in der Gemini API. Darin lässt sich eine eigene Job-ID mitschicken. Ein Lookup nach Label ist aber **nicht dokumentiert**. **[Code/SDK]** Discovery `GenaiVertexV1beta1Interaction.labels`; **[Doku]** https://ai.google.dev/api/interactions-api (`labels`)
- **Nur Gemini API: `webhook_config`** mit `uris` und `user_metadata` („returned on each event emission“). Laut Doku erfordert es `background=True`. **[Doku]** https://ai.google.dev/api/interactions-api , https://ai.google.dev/gemini-api/docs/webhooks
  - Events `interaction.completed`, `interaction.failed` und `interaction.cancelled` enthalten `data.id`. Die Zustellung ist „at-least-once“ mit Header `webhook-id`, Retries laufen 24 h.
  - Auch statische Projekt-Webhooks feuern „for any matching event“.
  - Wir bekommen die Interaction-ID darüber also **auch dann, wenn die Create-Antwort verloren geht**.
  - **Vertex hat kein `webhookConfig`.** Das Discovery-Dokument enthält das Wort „webhook“ null Mal. **[Code/SDK]**
- `X-Server-Timeout` ist ein allgemeiner Google-Systemparameter („Timeout … for the server to finish processing the request“). Er bricht nur serverseitig ab und dedupliziert nichts. Bezahlte Teilarbeit kann trotzdem entstehen. **[Doku]** https://docs.cloud.google.com/apis/docs/system-parameters
- Googles eigenes API-Designmuster AIP-155 sieht ein Feld `request_id` für Idempotenz vor. Die Interactions API setzt das **nicht** um. **[Doku]** https://google.aip.dev/155

### A3. List-Endpoint

- **Gemini API: Es gibt keinen List-Endpoint.** Die OpenAPI-Spec kennt für Interactions nur `POST /interactions` sowie `GET`, `DELETE` und `POST …/cancel` auf `/interactions/{id}`. **[Code/SDK]** https://ai.google.dev/static/api/interactions.openapi.json
- **Vertex: Ein List-Endpoint ist dokumentiert, aber stark eingeschränkt.**
  - `GET https://aiplatform.googleapis.com/v1beta1/projects/{project}/locations/global/interactions`
  - Parameter sind nur `page_size` (Default 10, max. 500) und `page_token`. Antwort: `{"interaction_metadatas":[{"id":…}],"next_page_token":…}`.
  - Die Doku sagt dazu: „**Only the id field is currently supported; other fields are not yet supported.**“ Es gibt **keine Filter** (Zeit, Modell, Label) und **keine** Felder `created` oder `model` in der Liste.
  - **[Doku]** https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/interactions-api („Listing created interactions“, „InteractionMetadata“)
- Im Discovery-Dokument (Revision 20261007) **fehlt eine List-Methode ganz**. Dort stehen nur `create`, `createStream`, `delete`, `get`/`getPoll`/`getStream`, `cancel` und `interactionsHttp.*`. Das spricht dafür, dass List noch nicht vollständig ausgerollt ist. **[Code/SDK]** + **[unklar]**
- **Warum `{}`?** proto3-JSON lässt leere Repeated-Felder und leere Strings standardmäßig weg (**[Doku]** https://protobuf.dev/programming-guides/json/). `{}` heißt also wahrscheinlich „0 Einträge“. Dass auch die erfolgreiche zweite Interaction fehlt, spricht dafür, dass List für unseren Fall noch nichts liefert. Mögliche Gründe: Ausrollstand, Omni bzw. Background wird nicht indexiert, oder die Liste ist an Principal oder Region gebunden. **[unklar]**
- Abgleich über Zeitstempel: Ein einzelnes `Interaction` hat `created` und `updated` (ISO 8601), dazu `labels` und `model`. Man müsste also jede gelistete ID per GET nachladen und mit `created` oder `labels` abgleichen. Das geht nur, wenn List überhaupt IDs liefert. **[Code/SDK]** Discovery `GenaiVertexV1beta1Interaction`
- Retention: Gespeicherte Interactions bleiben 7 Tage erhalten. **[Doku]** Vertex Developer Guide (URL oben)

### A4. Liefert `stream: true` die ID sofort?

- **Ja, als erstes Event.** Laut Doku ist der Ablauf „1. `interaction.created`: The interaction is created, includes metadata (ID, model, status)“, zum Beispiel `data: {"interaction":{"id":"v1_...","status":"in_progress",…},"event_type":"interaction.created"}`. Danach folgen `interaction.status_update`, `step.*` und `interaction.completed`. **[Doku]** https://ai.google.dev/gemini-api/docs/streaming
- Die Vertex-Referenz zeigt dasselbe: `event: interaction.created` und `event_id` für den Resume per `last_event_id`. **[Doku]** https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/interactions-api
- In der Discovery gibt es dafür die eigene Methode `projects.locations.interactions.createStream` (`…/interactions:createStream`) mit `GenaiVertexV1beta1InteractionCreatedSseEvent` („Server response confirming that a new interaction was created“). **[Code/SDK]**
- **`stream` und `background` lassen sich kombinieren.** Die Doku zeigt `stream=True, background=True` für Agents („you can also stream agent interactions“). Ein abgebrochener Stream lässt sich per `GET /interactions/{id}?stream=true&last_event_id=…` fortsetzen. **[Doku]** https://ai.google.dev/gemini-api/docs/streaming (Abschnitt „Streaming with agents“), https://ai.google.dev/gemini-api/docs/background-execution
- **Einschränkung:** Ob `interaction.created` bei Omni oder Video vor einer langen Vorverarbeitung kommt, ist nicht belegt. Hängt der Server schon vor dem Anlegen, hilft Streaming nicht. **[unklar]** Im Stream kann auch `event: error` mit `"code":"gateway_timeout"` kommen. **[Doku]** Streaming-Seite.

### A5. Bricht ein Client-Disconnect oder Timeout die Generierung ab? Wird trotzdem abgerechnet?

- **Background:** Der Task läuft serverseitig weiter, bis er abgeschlossen ist. Gestoppt wird er nur per `POST …/cancel`. **[Doku]** background-execution
- Zu Cancel sagt die Vertex-Doku: „Users will still be charged for partially generated tokens for cancelled interactions.“ **[Doku]** Vertex-Referenz (Abschnitt „Canceling an interaction“)
- **Ein offizieller Satz zu Client-Disconnect im Foreground oder Stream fehlt.** Ein Google-Forumsbeitrag (Vertex) sagt: „You will be charged for all tokens that the model had already generated.“ **[Issue/Forum]** https://discuss.ai.google.dev/t/do-i-get-charged-for-generated-tokens-if-client-disconnects-during-a-vertex-ai-streaming-response/89490
- Folgerung für unseren Fall: Wenn der erste Create serverseitig angelegt wurde, wurde er sehr wahrscheinlich generiert und abgerechnet. **[unklar]**

### A6. Timeout- und Retry-Empfehlungen von Google

- Die Doku empfiehlt Background für alles, was über die üblichen 60 s Connection-Limits hinausgeht, und Polling etwa alle 5–10 s (Codebeispiele). Ein konkretes Client-Timeout für den Create nennt sie nicht. **[Doku]** background-execution, omni
- Das SDK setzt für Interactions **kein** Timeout (`httpx.Timeout(None)`) und wiederholt bei 408/409/429/5XX und bei Transportfehlern. **[Code/SDK]** siehe A2
- Veo nennt als Request-Latenz „Min: 11 seconds; Max: 6 minutes (during peak hours)“. Das ist die Gesamtdauer der Generierung, nicht die des Create-Calls. **[Doku]** https://ai.google.dev/gemini-api/docs/veo

---

## B. Google Veo über `predictLongRunning`

- **Kein Request-ID- oder Idempotency-Feld.**
  - Vertex: `GoogleCloudAiplatformV1beta1PredictLongRunningRequest` hat nur `instances`, `parameters` und `labels`. Zu `labels` steht dort „used for billing and reporting only“.
  - Gemini API: `PredictLongRunningRequest` hat dieselben drei Felder.
  - **[Code/SDK]** https://aiplatform.googleapis.com/$discovery/rest?version=v1beta1 , https://generativelanguage.googleapis.com/$discovery/rest?version=v1beta
- **Operations auflisten:**
  - Gemini API: Es gibt `GET v1beta/models/{model}/operations` (`filter`, `pageSize`, `pageToken`, Standard-Methode „ListOperations“: „If the server doesn't support this method, it returns `UNIMPLEMENTED`“). **[Code/SDK]** Gemini-Discovery. Ob dort Veo-Operations auftauchen und welche Filter gehen, ist nicht dokumentiert. **[unklar]**
  - Vertex: Publisher-Modelle haben **nur** `predictLongRunning` und `fetchPredictOperation` (POST mit `operationName`). Es gibt **kein** `publishers/*/models/*/operations`-List. `projects.locations.models.operations.list` und `projects.locations.operations.list` gelten für eigene Ressourcen (Model Registry usw.), nicht für Veo. **[Code/SDK]** Vertex-Discovery. Eine verlorene Veo-Operation lässt sich auf Vertex also nicht wiederfinden. **[unklar, aber naheliegend]**
  - Gemini API: Der statische Webhook `video.generated` liefert `id`, `output_file_uri` und `file_name` für „Video generation LRO completed“. Darüber lassen sich verlorene Operations nachträglich zuordnen, mindestens für Gemini-API-Keys. **[Doku]** https://ai.google.dev/gemini-api/docs/webhooks (Event catalog)
- **Latenz des Create-Calls:** Für den reinen `predictLongRunning`-Call (Rückgabe des Operation-Namens) ist keine Latenz dokumentiert. Doku-Beispiele pollen alle 5–10 s. **[unklar]** Die Videos werden 2 Tage aufbewahrt. **[Doku]** https://ai.google.dev/gemini-api/docs/veo

---

## C. BytePlus ModelArk und Volcengine Ark Seedance

- **Kein Idempotency-Key** in der Create-Doku. Die Request-Felder enden mit `callback_url`, `execution_expires_after`, `priority` und `safety_identifier`. Die Antwort enthält nur `id`. **[Doku]** https://docs.byteplus.com/en/docs/ModelArk/1520757 , Volcengine: https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh
- **Das SDK `volcenginesdkarkruntime`:**
  - Es setzt pro Request einen Header **`X-Client-Request-Id`** (Zeitstempel + 20 Zufallszeichen) und liest ihn aus der Antwort zurück. Das dient der Nachverfolgung. Dass der Server danach dedupliziert, ist nicht belegt.
  - `RequestOptions.idempotency_key` existiert (aus dem Stainless-Template), wird aber nirgends benutzt.
  - Wichtig: `DEFAULT_MAX_RETRIES = 2`, und bei `httpx.TimeoutException` wird **der POST wiederholt**. Das SDK kann also selbst doppelte Tasks erzeugen.
  - **[Code/SDK]** https://github.com/volcengine/volcengine-python-sdk/blob/master/volcenginesdkarkruntime/_constants.py , …/_base_client.py , …/_utils/_utils.py , …/_request_options.py (Commit f51af28, 2026-10-09)
  - Ob der Server `X-Client-Request-Id` zur Deduplizierung nutzt: **[unklar]**, kein Beleg.
- **List** `GET /api/v3/contents/generations/tasks`:
  - Filter gibt es nur für `page_num`, `page_size`, `filter.status`, `filter.task_ids`, `filter.model` (Endpoint- oder Modell-ID) und `filter.service_tier`. **Einen Zeitfilter gibt es nicht.** Abfragbar sind nur die letzten 7 Tage („[T-7 days, T)“).
  - Die Items enthalten `id`, `model`, `status`, `content.video_url`, `usage`, `created_at`, `updated_at`, `seed`, `resolution`, `ratio`, `duration`, `framespersecond`, `service_tier`, `execution_expires_after`, `generate_audio`, `draft` und `priority`.
  - **Prompt und Input-Content fehlen.**
  - **[Doku]** https://docs.byteplus.com/en/docs/ModelArk/list-video-generation-tasks-api
  - Laut unserer früheren Recherche wird `safety_identifier` in Get/List zurückgegeben. Quelle: `tasks/research/seedance.md` §5.1, nach https://docs.byteplus.com/en/docs/ModelArk/get-video-generation-task-api **[Doku]**
  - Für den Abgleich bleiben damit nur `model` + `created_at`-Fenster + `resolution`/`ratio`/`duration` + optional `seed` und `safety_identifier`. Bei parallelen gleichartigen Jobs ist das mehrdeutig. **[unklar]**
- **`callback_url`:** Bei jeder Statusänderung kommt ein POST mit dem Get-Body, also mit `id`. Bei `succeeded`/`failed` gibt es 3 Retries. **[Doku]** Create-Seite und Video-Tutorial, siehe `tasks/research/seedance.md` §7. Eine **pro Job eindeutige Callback-URL** (z. B. `/cb/seedance/{job_id}`) liefert die Task-ID also auch nach einem Timeout. Ob Query-Parameter in `callback_url` erhalten bleiben, ist nicht dokumentiert. **[unklar]**, deshalb besser ein Pfadsegment nutzen.

---

## D. Kling

- **Neue API (`options.external_task_id`):**
  - Doku: „Custom task ID, which can be used for querying and will not overwrite the system-generated task ID, **must be unique within the scope of the account**.“
  - Abfrage per `GET /tasks?external_task_ids=a,b` (Batch mit Komma; schließt `task_ids` aus). Die Antwort enthält `external_id`, `create_time` und `outputs`.
  - **[Doku]** https://kling.ai/document-api/api/video/3-0-omni/text-to-video.md (Abschnitte „options“ und „Query Task“)
  - Laut unserer früheren Recherche gibt es zusätzlich `POST /tasks` als Cursor-Liste mit `start_time`/`end_time` und `filters`. **[Doku]** siehe `tasks/research/kling.md` §4.5
- **Legacy (`external_task_id` top-level):**
  - Doku: „Customized Task ID … will not overwrite the system-generated task ID but can be used for task queries. Must be unique within a single user account.“
  - Einzelabfrage `GET /v1/videos/text2video/{id}`: „Choose either task_id or external_task_id for querying“ (beides als Path-Parameter). Für `omni-video` gilt dasselbe wörtlich: „The external_task_id provided when creating the task.“
  - Die Create-Antwort spiegelt die ID zurück: `task_info.external_task_id`.
  - **[Doku]** https://kling.ai/document-api/api/video/3-0-omni/text-to-video/legacy , https://kling.ai/document-api/api/video/3-0-omni/video-omni/legacy (SPA, im Browser gerendert)
  - Für die übrigen Legacy-Familien (`image2video`, `motion-control` usw.) gilt laut früherer Recherche dasselbe Muster. **[Doku]** `tasks/research/kling.md` §5
- **Was passiert, wenn dieselbe externe ID zweimal kommt?** Das ist **nicht dokumentiert**. Die Fehlercode-Tabelle hat keinen eigenen Code für ein Duplikat. Eine Ablehnung käme vermutlich als 400/1201 („Invalid parameters“) zurück. **[Doku]** https://kling.ai/document-api/api/get-started/error-codes ; Verhalten **[unklar]**. Die Pflicht zur Eindeutigkeit spricht für eine Ablehnung, belegt ist das nicht. Weder Suche noch Issues haben einen Bericht ergeben.
  - Folge: Die externe ID taugt verlässlich als **Lookup-Schlüssel**. Ob sie als **Idempotency-Key** taugt, muss ein einmaliger, bewusst freigegebener Test klären.

---

## E. Allgemeine Best Practice (kurz)

- **Eine eigene ID vor dem Call vergeben und speichern.** Erst den Job als `submitting` mit eigener `job_id` und dem Request-Hash dauerhaft speichern, dann den Provider aufrufen. Nach einem Timeout geht der Job auf `unknown`, nicht auf `failed`. Danach wird abgeglichen (Lookup, Callback, Webhook) und erst bei nachgewiesenem Nichtvorhandensein erneut gesendet. Das entspricht dem Transactional-Outbox-Muster: https://microservices.io/patterns/data/transactional-outbox.html **[Doku]**
- **Idempotency-Key nur dort verwenden, wo der Server ihn wirklich auswertet.** Beispiele sind die IETF-Draft `Idempotency-Key` (https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/) und Stripe (https://docs.stripe.com/api/idempotent_requests) **[Doku]**. Fehlt das, gilt der POST als nicht wiederholbar. Das ist der Kern von AWS Builders' Library „Making retries safe with idempotent APIs“: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/ **[Doku]**
- **Automatische Retries für Creates im Proxy und in den genutzten SDKs abschalten.** Beide SDKs wiederholen Creates bei einem Timeout (siehe A2 und C).
- **Getrennte Timeouts setzen:** ein kurzes Connect-Timeout und ein langes Read-Timeout für Creates (mehrere Minuten). Ein Read-Timeout bei einem Create ist ein **unbekannter** Ausgang, kein Fehler.
- **Callbacks und Webhooks zusätzlich zum Polling nutzen,** mit eigener Job-ID in der URL oder in den Metadaten. Duplikate werden über die Provider-ID beziehungsweise `webhook-id` aussortiert.

---

## Empfehlung pro Anbieter

Was der Proxy bei einem Create-Timeout tun soll, sortiert von sicher nach unsicher:

1. **Kling (am sichersten)**
   - Immer `external_task_id` (Legacy) bzw. `options.external_task_id` (neu) = unsere `job_id` senden, zusätzlich `callback_url` mit `job_id`.
   - Bei einem Timeout `GET /tasks?external_task_ids={job_id}` (neu) bzw. `GET /v1/videos/<feature>/{job_id}` (Legacy) aufrufen, mehrfach über einige Minuten:
     - Treffer: den Job übernehmen.
     - Kein Treffer nach der Karenzzeit: erneut mit **derselben** externen ID senden. Wird sie als Duplikat abgelehnt, erneut nachschlagen. Ein Doppel-Billing ist dann ausgeschlossen, sofern Kling die Eindeutigkeit durchsetzt. Das ist [unklar] und muss einmal getestet werden.
2. **Gemini API Interactions (`generativelanguage`)**
   - `background: true` plus `webhook_config.user_metadata = {job_id}` (oder `uris` mit `job_id` im Pfad) senden, dazu `labels.job_id`. Optional einen statischen Webhook für `interaction.*`.
   - Bei einem Timeout **nicht** erneut senden. Auf den Webhook warten: Er liefert `id` und unsere Metadaten. Erst wenn innerhalb eines großzügigen Fensters (z. B. 15–30 min) kein Event kommt, den Job als „verloren, vermutlich nicht angelegt“ markieren und nur nach Freigabe neu senden.
   - Alternativ oder zusätzlich `stream: true` + `background: true`, um die ID aus `interaction.created` sofort zu bekommen.
3. **BytePlus Seedance**
   - Pro Job eine eindeutige `callback_url` (`/cb/seedance/{job_id}`) setzen, im SDK `max_retries=0`.
   - Bei einem Timeout auf den Callback warten. Parallel `GET …/tasks?filter.model=…&page_size=…` (1 QPS) abfragen und nach `created_at` im Fenster [Sendezeit − 5 s, + Timeout] sowie `resolution`/`ratio`/`duration` (und `seed`, falls gesetzt) abgleichen.
   - Ist der Treffer eindeutig, übernehmen. Ist er mehrdeutig oder fehlt, **nicht** automatisch neu senden, sondern den Job zur manuellen Klärung markieren.
   - `safety_identifier` als Abgleichschlüssel pro Request zu missbrauchen widerspricht seinem Zweck (stabile End-User-ID). Davon rate ich ab.
4. **Vertex Interactions (Omni), unser Vorfall**
   - Es gibt keinen Idempotency-Key, keinen Webhook und kein verwertbares List-Ergebnis.
   - Am robustesten ist es, die ID vor der langen Arbeit zu bekommen: per `createStream` (`stream: true` + `background: true`) mit Read-Timeout pro Event. Sobald `interaction.created` die `id` liefert, die `id` speichern und den Stream schließen oder per GET pollen. Dazu `labels.job_id` setzen.
   - Das Read-Timeout für den Create deutlich über 60 s anheben (z. B. 180–300 s). Das SDK nutzt standardmäßig kein Timeout.
   - Bei einem Timeout **niemals automatisch neu senden**. `GET …/interactions` versuchen; wenn IDs kommen, jede per GET auf `labels.job_id` prüfen. Sonst den Job als `unknown` markieren und erst nach Freigabe neu senden. Das Risiko einer Doppelbelastung wird dabei bewusst akzeptiert.
5. **Vertex Veo (`predictLongRunning`, am unsichersten)**
   - Es gibt kein List für Publisher-Operations und keinen Webhook. Auf der Gemini API eventuell `models/{model}/operations` oder den statischen Webhook `video.generated` nutzen.
   - Ein langes Read-Timeout setzen und nach einem Timeout nur nach Freigabe neu senden.

---

## Unklar / nicht verifizierbar

- Warum der erste Vertex-Create > 60 s ohne Header hing. Dazu gibt es weder Doku noch Issue. Möglich sind Vorverarbeitung vor dem Erzeugen der ID, ein Cold Start oder eine Störung.
- Ob der erste Create serverseitig überhaupt angelegt und abgerechnet wurde. Ohne ID lässt sich das nicht prüfen. Abhilfe: im Billing-Export oder in Cloud Logging (Data Access Audit Logs für `aiplatform.googleapis.com`, sofern aktiviert) nach einer zweiten Interaction um 2026-10-11 suchen. Dass solche Logs für Interactions existieren, ist **[unklar]**.
- Warum Vertex-List `{}` liefert, obwohl die Doku den Endpoint beschreibt und das Discovery-Dokument ihn nicht enthält.
- Ob `interaction.created` bei Omni sofort kommt oder erst nach der Input-Verarbeitung.
- Ob Gemini-API `models/{veo}/operations` Veo-Operations auflistet und welche Filter es unterstützt.
- Kling: wie der Server auf eine doppelte `external_task_id` reagiert.
- Seedance: ob `X-Client-Request-Id` serverseitig dedupliziert, und ob Query-Parameter in `callback_url` erhalten bleiben.
- Der LiteLLM-Fork-PR (Omni-Background „stopped resolving“) war nur als Suchtreffer sichtbar. Das Repo ist nicht erreichbar.
