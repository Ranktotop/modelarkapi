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
8. Asset-ID kopieren und erst dann einen kostenpflichtigen Test starten.

Zusätzliche Looks derselben Person können ergänzt werden, werden aber erneut
auf Konsistenz geprüft. Verfügbarkeit, Freikontingente, QPM und Zugriff auf die
private Assets API hängen vom Account und der gebuchten Rechte-Stufe ab.

## Verwendung

```json
{
  "model": "seedance",
  "prompt": "The person in Image 1 walks into a modern studio.",
  "asset_id": "asset-…",
  "duration": 4,
  "resolution": "480p",
  "generate_audio": false
}
```

Mehrere Assets:

```json
{
  "reference_assets": [
    {"id":"asset-image-…", "type":"image"},
    {"id":"asset-video-…", "type":"video"},
    {"id":"asset-audio-…", "type":"audio"}
  ]
}
```

Im Prompt heißen sie nach Medienart und Reihenfolge `Image 1`, `Video 1` und
`Audio 1`; die Asset-ID gehört nicht in den Prompt.

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
