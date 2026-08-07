# Real-Human-Assets und Gesichtsverifizierung

## Warum die Verifizierung nötig ist

Seedance 2.0 akzeptiert Referenzbilder oder -videos realer Personen nicht
generell als gewöhnlichen Upload. Für das eigene Gesicht ist die private
Real-Human Asset Library vorgesehen. Die Person stimmt der Nutzung zu, führt
eine Echtzeit-Lebendprüfung durch und autorisiert einen Verwendungszweck und
Zeitraum. Der Proxy kann diese Prüfung weder durchführen noch umgehen.

## Freischaltung in der BytePlus-Konsole

1. Konto- beziehungsweise
   [Unternehmensverifizierung](https://console.byteplus.com/user/authentication/enterprise/)
   abschließen.
2. Unter **Model activation → Advanced Creation Rights** die verfügbaren
   Rechte und die Real-Human-Funktion prüfen.
3. **ModelArk Playground → My assets → Real-human → Add real-human assets**
   öffnen und eine Asset-Gruppe anlegen.
4. Gültigkeitszeitraum und Zweck festlegen und den QR-Code erzeugen.
5. Die betroffene Person öffnet den QR-Code mit ihrem persönlichen Konto,
   bestätigt die Einwilligungen und absolviert die Live-Gesichtsprüfung.
6. Frontalmaterial derselben Person hochladen. Eine Gruppe darf nur eine
   Person enthalten.
7. Das Material im ModelArk-Konto annehmen und auf Status `Active` warten.
8. Die Gruppen-ID im Proxy konfigurieren und erst dann einen kostenpflichtigen
   Test starten.

Zusätzliche Looks derselben Person können ergänzt werden, werden aber erneut
auf Konsistenz geprüft. Verfügbarkeit, Freikontingente, QPM und Zugriff auf die
private Assets API hängen vom Account und der gebuchten Rechte-Stufe ab.

## Dedizierten IAM-User und AK/SK anlegen

Für den automatischen temporären Asset-Workflow sollte kein Schlüssel des
Hauptkontos verwendet werden:

1. Als Hauptkonto in der BytePlus-Konsole anmelden und
   [IAM → User Management](https://console.byteplus.com/iam/identitymanage/user)
   öffnen.
2. **New User** wählen und einen eigenen Benutzer, beispielsweise
   `seedance-asset-proxy`, mit programmatischem Zugriff anlegen.
3. Im Benutzer unter **Policy** die Berechtigung `ArkFullAccess` für das
   Projekt vergeben, in dem sowohl Asset-Gruppe als auch Seedance-Endpunkt
   liegen. Sie deckt außerdem die read-only Modell-Discovery des Studios ab.
   Neue IAM-User besitzen zunächst keine Rechte.
4. Im Reiter **Access key** auf **Create access key** klicken. Alternativ steht
   [IAM → Key Management](https://console.byteplus.com/iam/keymanage/) zur
   Verfügung. BytePlus erlaubt höchstens zwei Access Keys pro Benutzer.
5. Access Key ID und Secret Access Key unmittelbar sicher speichern. Der
   Secret Key darf nicht in Git, Browsercode, Logs oder Screenshots gelangen.
6. Die vorhandene Real-Human-Gruppe in **ModelArk → My assets → Real human**
   öffnen und ihre `group-…`-ID notieren. Bei mehreren Gruppen niemals
   automatisch die erste auswählen.
7. Folgende Werte ausschließlich im Proxy-Container konfigurieren:

   ```dotenv
   BYTEPLUS_ACCESS_KEY_ID=AKLT...
   BYTEPLUS_SECRET_ACCESS_KEY=...
   BYTEPLUS_ASSET_GROUP_ID=group-...
   BYTEPLUS_PROJECT_NAME=default
   BYTEPLUS_ASSET_REGION=ap-southeast-1
   ```

8. Vor einem kostenpflichtigen Test die Konfiguration über den read-only-Aufruf
   prüfen:

   ```bash
   curl -H "Authorization: Bearer $PROXY_API_KEY" \
     http://localhost:8080/v1/real-human/configuration
   ```

   `configured: true` und `verified: true` bestätigen, dass der intern
   verwendete `ListAssetGroups`-Aufruf die konfigurierte Gruppe findet.
   `AccessDenied` weist meist auf fehlendes `ArkFullAccess`, ein falsches
   Projekt oder einen Schlüssel des falschen Kontos hin.

Asset-Gruppe und Seedance-Inferenzendpunkt müssen exakt im selben `ProjectName`
liegen. Für einen Schlüsselwechsel zuerst den zweiten Key anlegen, den
Container umstellen und erst danach den alten Key deaktivieren oder löschen.

Offizielle Anleitungen: [Access Key erstellen](https://docs.byteplus.com/en/docs/IAM/creating-an-access-key),
[Access Keys und IAM-Sicherheit](https://docs.byteplus.com/en/docs/IAM/about-access-keys).

## Automatischer temporärer Workflow

Bei einer Referenz mit `real_human: true` führt der Proxy selbstständig aus:

1. `CreateAsset` in der konfigurierten verifizierten Asset-Gruppe,
2. asynchrones `GetAsset`-Polling bis `Active` oder `Failed`,
3. interner Seedance-Aufruf mit der erzeugten `asset://<Asset-ID>`,
4. `DeleteAsset`, sobald der Videoauftrag abgeschlossen, fehlgeschlagen oder
   abgebrochen ist.

Der ursprüngliche HTTP-Aufruf wartet nicht auf die Asset-Prüfung. Er gibt eine
lokale `video-rh-…`-Job-ID zurück, die über die normalen Video-Endpunkte
abgefragt wird. Job- und Asset-Zuordnungen liegen persistent in SQLite. Ein
zusätzlicher Reconciler löscht nach der TTL ausschließlich verwaiste Assets mit
dem reservierten Namen `modelark-proxy-temp-…`. Manuell angelegte Assets werden
nie automatisch gelöscht.

BytePlus vergleicht das neue Material bei `CreateAsset` mit der während der
Lebendprüfung erfassten Person. Die Schnittstelle ist asynchron und garantiert
keine maximale Bearbeitungszeit. Mehrere Gesichter oder eine abweichende Person
können zu `Failed` führen.

`CreateAsset` übernimmt keine Multipart-Datei, sondern eine für BytePlus
erreichbare URL. Bei Studio-Uploads muss deshalb `PUBLIC_BASE_URL` auf die
öffentliche HTTPS-Adresse des Proxy-Containers zeigen. Die lokale Datei bleibt
bis zum Status `Active` verfügbar und wird danach sofort entfernt.

## Verwendung

Automatische Registrierung einer neuen URL:

```json
{
  "prompt": "Edit Video 1.",
  "reference_urls": [
    {
      "url": "https://proxy.example.com/media/reference/example.mp4",
      "media_type": "video",
      "role": "reference_video",
      "real_human": true
    }
  ]
}
```

Ist `real_human` nicht gesetzt oder `false`, wird die Referenz ohne
Asset-Registrierung normal an Seedance übergeben. Extern gelieferte Asset-IDs
werden abgewiesen; die temporäre ID bleibt ausschließlich im Proxy.

## Alternativen für Gesichter

ModelArk nennt außerdem freigegebene Digital Characters und unveränderte,
vertrauenswürdige Originalausgaben unterstützter Modelle im selben Account.
Trusted Outputs müssen unverändert sein und sind nur innerhalb des von
BytePlus angegebenen Zeitfensters nutzbar; Download, Komprimierung oder andere
Verarbeitung kann die Vertrauenskette ungültig machen.

## Offizielle Quellen

- [Real-human Assets in der Konsole](https://docs.byteplus.com/en/docs/ModelArk/2315856)
- [Private Real-human Asset Library / Assets API](https://docs.byteplus.com/en/docs/ModelArk/2333589)
- [Advanced Creation Rights](https://docs.byteplus.com/en/docs/ModelArk/2377608)
- [Seedance-2.0-Tutorial](https://docs.byteplus.com/en/docs/ModelArk/2291680)
- [Spezifische Bedingungen für Video Generation](https://docs.byteplus.com/en/docs/modelark/Specific_Terms_for_the_BytePlus_Video_Generation_Model_Services)

Der noch offene Live-Test wird erst nach bestätigtem `Active`-Status mit 4
Sekunden, 480p und zunächst ohne Audio durchgeführt.
