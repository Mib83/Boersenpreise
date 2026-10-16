# Börsenpreise · v0.0.1

Home-Assistant-Integration für deutsche Day-Ahead-Börsenstrompreise von ENTSO-E (Gebotszone DE-LU).

## Funktionen

- Eigener Menüpunkt **Börsenpreise** in der linken Seitenleiste.
- Tagesauswahl, Zurück/Weiter, Heute/Morgen; horizontal scrollbar auf kleinen Bildschirmen.
- Echte 15-Minuten-Balken mit negativen Preisen und Einzelwerten als Tabelle.
- Einstellbare Preisobergrenzen und drei frei wählbare Farben: standardmäßig bis einschließlich 5 ct/kWh grün, über 5 bis einschließlich 10 ct/kWh gelb, darüber rot. Negative Preise gehören zur ersten Stufe.
- Historischer Import ab **1. Oktober 2025** im Hintergrund, nach Neustart fortsetzbar. Fehlende/unvollständige Tage werden erneut versucht.
- Lokale dauerhafte Historie in Home Assistants `.storage`, unabhängig vom Recorder.
- Optional direkter Export einschließlich Historie nach **InfluxDB 2**.
- Sensoren für den aktuellen und nächsten Viertelstundenpreis in ct/kWh.
- Einrichtung und spätere Änderungen unter **Einstellungen → Geräte & Dienste → Börsenpreise → Konfigurieren**; kein YAML nötig.

## Voraussetzungen und Installation

Home Assistant **2026.10 oder neuer**. Dies ist eine erste Version; Tests in einer laufenden Home-Assistant-Installation und mit echten Zugangsdaten stehen noch aus.

### HACS

1. HACS öffnen → benutzerdefinierte Repositories.
2. `https://github.com/Mib83/B-rsenpreise` als **Integration** hinzufügen.
3. Börsenpreise herunterladen und Home Assistant neu starten.
4. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Börsenpreise**.

### Manuell

Den Ordner `custom_components/boersenpreise` nach `/config/custom_components/boersenpreise` kopieren und Home Assistant neu starten. Danach die Integration hinzufügen. Das Release-Archiv `boersenpreise.zip` enthält direkt die Dateien dieses Integrationsordners.

## ENTSO-E: Konto und API-Token

1. [Transparency Platform](https://transparency.entsoe.eu/) öffnen, **Sign in** wählen und ein kostenloses Konto registrieren. Eventuelle E-Mail-Bestätigung abschließen.
2. Von deiner registrierten Adresse eine E-Mail an **transparency@entsoe.eu** senden.
3. Betreff: **Restful API access**. Im Text die registrierte E-Mail-Adresse nennen und um REST-API-Zugang bitten. Zum Beispiel:

   > Please enable RESTful API access for my Transparency Platform account. Registered email address: YOUR_EMAIL. I would like to retrieve DE-LU day-ahead electricity prices for a private Home Assistant integration, including historical data from 1 October 2025 onwards.

4. Nach Freischaltung anmelden und in den Kontoeinstellungen **Web Api Security Token** suchen. Die genaue Menübezeichnung kann sich ändern.
5. Token erzeugen und sofort sicher speichern. Laut ENTSO-E ist er nach Schließen des Dialogs nicht erneut sichtbar; erneutes Erzeugen ersetzt den alten Token.
6. Token ausschließlich in der Integration eintragen. Nicht in Issues, Screenshots oder das Repository kopieren.

[Offizielle ENTSO-E-Anleitung zur Tokenverwaltung](https://transparency.entsoe.eu/content/static_content/download?path=%2FStatic+content%2FAPI-Token-Management.pdf).

## InfluxDB 2

Optional aktivieren, sobald die Datenbank bereitsteht. Benötigt werden Serveradresse (z. B. `http://192.168.1.20:8086`), Organisation, ein bereits angelegter Bucket und ein Token mit **Schreibrecht für diesen Bucket**. v0.0.1 liest die Tagesansicht aus dem lokalen Archiv; ein Leserecht für InfluxDB wird dafür nicht benötigt.

Für eine vollständige Historie den Bucket ohne automatische Löschung anlegen. Bei HTTPS wird das Zertifikat geprüft. Die Datenbank muss von Home Assistant aus erreichbar sein; `localhost` bezeichnet bei Containern die jeweilige Containerumgebung.

Beim Einrichtungstest wird ein echter heutiger Preispunkt geschrieben. Nach Aktivierung werden auch die bereits lokal gespeicherten Tage übertragen. Fehlgeschlagene Übertragungen werden wiederholt; lokale Preise bleiben erhalten. Ein Wechsel von Server, Organisation oder Bucket startet den Export in das neue Ziel erneut.

Schema: Measurement `boersenpreise`, Tag `zone=DE-LU`, Felder `eur_mwh` und `ct_kwh`, UTC-Zeitstempel des Intervallbeginns mit Sekundenpräzision. Wiederholte Schreibvorgänge auf dasselbe Intervall aktualisieren denselben Punkt.

## Daten und Betriebsverhalten

ENTSO-E-Abfrage: Dokumenttyp `A44`, In-/Out-Domain `10Y1001A1001A82H`, nur EUR/MWh und `PT15M`. Umrechnung: **EUR/MWh ÷ 10 = ct/kWh**. Es werden keine Stundenwerte künstlich in Viertelstunden aufgeteilt. A03-Kurven werden gemäß ihrer konstanten Abschnitte aufgelöst; echte A01-Lücken bleiben fehlend.

Heute und morgen werden alle 15 Minuten erneut angefragt. Fehlende Zukunftsdaten sind normal: Day-Ahead ist keine langfristige Prognose. Die historischen Tage werden mit gedrosselten Einzelabfragen importiert. Das kann bei der ersten Einrichtung mehrere Minuten dauern, bei Störungen länger. Der Fortschritt steht im Panel. Preise werden lokal dauerhaft gespeichert; regelmäßige Home-Assistant-Backups einschließen.

Anzeige in **Europe/Berlin**, Speicherung in UTC. Normale Tage enthalten 96, Zeitumstellungstage 92 oder 100 Viertelstunden. Die Tabelle zeigt zur Unterscheidung wiederholter Uhrzeiten die Zeitzone an. Alle Preise sind reine Großhandelspreise ohne Endkundentarifbestandteile. Datenquelle: ENTSO-E Transparency Platform; deren Nutzungsbedingungen gelten.

Konfiguration und Tokens liegen in Home Assistants lokalen Konfigurationseinträgen und können damit auch in Backups enthalten sein. Das Frontend erhält keine Tokens. Es wird nur eine Instanz für DE-LU unterstützt. Nach Änderung des Importstarts bleiben zuvor gespeicherte Daten erhalten.

## Prüfung und Grenzen von v0.0.1

Lokale automatisierte Tests decken XML-Auflösung, negative Preise, Lücken, A03-Kurven, Umrechnung und Zeitumstellung ab. Ein Live-Test mit neuem ENTSO-E-Token, deiner InfluxDB und Home Assistant ist vor produktiver Nutzung erforderlich. Fehlerstatus und Importfortschritt sind im Panel sichtbar. Die Farben werden mit Hex-Codes `#RRGGBB` eingestellt. Individuelle zusätzliche Farbstufen sind in dieser Version nicht enthalten.

Tests: `python3 -m unittest discover -s tests -v`
