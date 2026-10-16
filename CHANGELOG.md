# Änderungen

## v0.0.3

Preisziele mit beliebig vielen Obergrenzen und Farben über Hinzufügen, Bearbeiten und Löschen in den Integrationseinstellungen. Bisherige Einstellungen bleiben erhalten. Balken am äußeren Ende abgerundet; Erklärungstext ins untere Infofeld verschoben und Infofeld-Schrift verkleinert.

## v0.0.2

Korrigiert den ENTSO-E-Abruf für DE-LU: explizite Auswahl von SDAC-Sequenz 1 und Day-Ahead-Vertrag A01, statt unterschiedliche Preisreihen zusammenzuführen. Getrennte Fehlermeldungen für ENTSO-E, fehlende heutige Preise und InfluxDB. Live-Antworten geprüft; neue Regressionstests für mehrere Sequenzen.

## v0.0.1

Erste Version mit ENTSO-E DE-LU, historischem Viertelstundenimport ab 01.10.2025, lokaler Historie, optionalem InfluxDB-2-Export, zwei Preissensoren und Seitenleistenansicht mit Tagesnavigation und einstellbaren Farbschwellen. Noch kein Live-Test mit Home Assistant und privaten Zugängen.
