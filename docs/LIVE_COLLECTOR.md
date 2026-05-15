# Live GT7 Collector

Diese Seite beschreibt die neue Live-Version des Collectors.

## Was neu ist

Der Collector kann jetzt zwei Datenquellen verwenden:

- `MockTelemetrySource`: simulierte Daten für Tests
- `GT7TelemetrySource`: echte GT7-UDP-Telemetrie von der PlayStation

Die Server-Payload bleibt gleich. Das heißt: Public Timing, Team Engineer View und Race Control müssen nicht wissen, ob die Daten aus dem Mock oder aus GT7 kommen.

## Voraussetzungen

Für echte GT7-Daten:

- PlayStation und PC/Laptop sind im selben Netzwerk
- GT7 läuft auf der PlayStation
- du bist in einer Session, in der GT7 Telemetrie sendet
- Windows Firewall erlaubt Python UDP-Empfang
- keine andere App belegt den GT7-Telemetrieport, z. B. SimHub oder GT7Proxy

Standardports:

```text
Heartbeat zur PlayStation: 33739 UDP
Telemetrie-Empfang am PC: 33740 UDP
```

## Grafische Collector-App starten

Ein fertiger Doppelklick-Start liegt hier:

```text
collector\dist\TRC GT7 Collector.exe
```

Auf diesem Rechner gibt es ausserdem ein Desktop-Symbol:

```text
TRC GT7 Collector
```

Das ist der Weg, den Fahrer spaeter nutzen sollen.

PowerShell:

```powershell
cd "C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing\collector"
.\.venv\Scripts\Activate.ps1
python collector.py --gui
```

Ablauf:

1. Server prüfen, normalerweise `http://localhost:8000`
2. Race Code eingeben, z. B. `TRC8H`
3. `Connect` klicken
4. Team auswählen
5. Fahrer auswählen
6. Team PIN eingeben
7. PlayStation IP eingeben oder leer lassen für Auto-Detect
8. `Start Sending` klicken

Für einen Test ohne PlayStation:

```text
Use mock telemetry for testing
```

aktivieren.

## Live Collector per Kommandozeile starten

Mit Auto-Discovery:

```powershell
python collector.py --server http://localhost:8000 --race TRC8H --entry car_23 --driver florian --team-code H3RKA-2381
```

Mit manueller PlayStation-IP:

```powershell
python collector.py --server http://localhost:8000 --race TRC8H --entry car_23 --driver florian --team-code H3RKA-2381 --ps5-ip 192.168.0.54
```

Mock-Modus:

```powershell
python collector.py --mock --server http://localhost:8000 --race TRC8H --entry car_23 --driver florian --team-code H3RKA-2381
```

## Heartbeat-Typ

Standard:

```text
A
```

Der Collector unterstützt außerdem:

```text
B
~
```

Start mit anderem Heartbeat:

```powershell
python collector.py --server http://localhost:8000 --race TRC8H --entry car_23 --driver florian --team-code H3RKA-2381 --heartbeat-type B
```

Für unser MVP reicht normalerweise `A`.

## Häufige Live-Fehler

### Anzeige wirkt eine Runde bzw. 8-9 Minuten hinten

Der Collector addiert fuer Live-GT7 standardmaessig `+1` auf den GT7-Lap-Wert, weil GT7 haeufig die abgeschlossene Runde liefert. Gerade auf der Nordschleife wirkt das sonst wie eine komplette Runde Verzoegerung.

Falls sich bei einem echten Test herausstellt, dass GT7 in deiner Session bereits die aktuelle Runde liefert, kann der Offset so deaktiviert werden:

```powershell
python collector.py --server http://localhost:8000 --race TRC8H --entry car_23 --driver florian --team-code H3RKA-2381 --lap-display-offset 0
```

### PlayStation wird nicht gefunden

Prüfe:

1. PlayStation ist eingeschaltet
2. GT7 läuft
3. PC und PlayStation sind im selben Netzwerk
4. VPN ist aus
5. PlayStation-IP manuell eintragen

### Keine Daten trotz richtiger IP

Prüfe:

1. GT7 ist nicht nur im Hauptmenü
2. du bist in einer Fahr-Session
3. Windows Firewall blockiert Python nicht
4. kein anderes Telemetrieprogramm hört auf Port `33740`

### Port 33740 ist belegt

Schließe andere GT7-Telemetrieprogramme.

Oder prüfe in PowerShell:

```powershell
Get-NetTCPConnection -LocalPort 33740 -ErrorAction SilentlyContinue
```

UDP-Belegung sieht man unter Windows nicht immer zuverlässig mit diesem Befehl. Wenn SimHub, GT7Proxy oder ein alter Collector läuft, zuerst diese Programme schließen.

### Serververbindung verloren

Der Collector versucht weiterzusenden. Prüfe:

- Backend läuft
- Internet/LAN-Verbindung ist stabil
- Server-URL stimmt

## Sicherheit

Der Collector liest nur GT7-Telemetrie aus dem lokalen Netzwerk und sendet ausgewählte Renntelemetrie an den Timing Server.

Er greift nicht zu auf:

- persönliche Dateien
- Mikrofon
- Kamera
- Tastatureingaben
- Bildschirmaufnahme
- Browserdaten
