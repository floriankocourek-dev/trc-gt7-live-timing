# Bedienungsanleitung

Diese Anleitung beschreibt, wie du das aktuelle MVP des TRC GT7 Live Timing Systems lokal startest und testest.

## 1. Was aktuell funktioniert

Das MVP besteht aus drei Teilen:

- Backend Server: empfängt Telemetrie, verwaltet Rennen, Teams, Logins und Standings
- Web Frontend: Public Timing, Team Engineer View und Race Control
- Mock Collector: simuliert GT7-Telemetrie, bis der echte GT7-UDP-Collector eingebaut wird

Aktuell wird noch keine echte PlayStation-/GT7-Telemetrie gelesen. Für Tests senden Mock-Collectors realistische Fake-Daten an den Server.

## 2. Ordner

Das Projekt liegt hier:

```powershell
C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing
```

Wichtige Unterordner:

```text
server     Backend / FastAPI / SQLite
web        React Frontend
collector  Mock Collector
docs       Dokumentation
```

## 3. Backend starten

Öffne PowerShell und führe aus:

```powershell
cd "C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing\server"
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Danach läuft der Backend Server hier:

```text
http://localhost:8000
```

Test im Browser:

```text
http://localhost:8000/api/health
```

Wenn alles passt, erscheint ungefähr:

```json
{
  "status": "ok",
  "time": "..."
}
```

Kurzform, wenn du nur lokal starten willst:

```text
Backend:  http://localhost:8000
Frontend: http://localhost:5173
Collector: Desktop-Symbol "TRC GT7 Collector"
```

## 4. Frontend starten

Öffne eine zweite PowerShell und führe aus:

```powershell
cd "C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing\web"
npm run dev
```

Danach läuft die Weboberfläche hier:

```text
http://localhost:5173
```

Im Browser öffnen:

```text
http://localhost:5173
```

## 5. Demo-Rennen anlegen

Wenn Backend und Frontend laufen, öffne:

```text
http://localhost:5173
```

Dann:

1. Oben auf `Race Control` klicken
2. Auf `Create Demo Race` klicken

Alternativ per PowerShell:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/dev/seed-demo -Method Post -ContentType 'application/json' -Body '{}'
```

Dadurch wird ein Demo-Rennen angelegt:

```text
Race Code: TRC8H
Race Name: TRC 8H Nurburgring
```

Demo-Teams:

```text
car_23   #23 HERKA Racing            Team Code: H3RKA-2381
car_80   #80 AMG Nordschleife Team   Team Code: AMG-9082
car_911  #911 Porsche Squad          Team Code: POR-9117
```

## 6. Race Control verwenden

Im Frontend:

```text
http://localhost:5173
```

Dann oben auf:

```text
Race Control
```

Lokales Demo-Passwort:

```text
admin
```

In Race Control kannst du aktuell:

- Rennen anlegen
- Solo- oder Team-Event auswählen
- Fahrer pro Team setzen
- Entries / Teams anlegen
- Team-Codes automatisch generieren lassen
- Collectors überwachen
- Public Standings sehen
- private Telemetrie aller Teams sehen
- Strafen setzen
- Rennstatus starten/stoppen
- Race Log ansehen

Wichtig: Team-Codes werden beim Erstellen eines Entries nur einmal angezeigt. Für echte Events solltest du sie danach direkt notieren.

## 7. Public Live Timing verwenden

Im Frontend oben auf:

```text
Public
```

Race Code:

```text
TRC8H
```

Die Public-Seite zeigt nur öffentliche Motorsportdaten:

- Position
- Startnummer
- Klasse
- Team
- Fahrer
- Auto
- Runden
- Gap
- letzte Runde
- beste Runde
- Pit Stops
- Penalty
- Status
- Verbindung

Nicht sichtbar sind:

- Fuel
- RPM
- Gear
- Throttle
- Brake
- Position X/Y/Z
- private Rohtelemetrie

## 8. Team Engineer View verwenden

Im Frontend oben auf:

```text
Engineer
```

Beispiel-Login:

```text
Race Code: TRC8H
Entry ID:   car_23
Team Code:  H3RKA-2381
```

Die Teamseite zeigt nur Daten des eingeloggten Teams.

Beispiel: Wer mit `car_23` eingeloggt ist, bekommt nur private Daten von `car_23`.

Sichtbar sind dort:

- eigene Position
- eigener Fahrer
- aktuelle Runde
- letzte Runde
- beste Runde
- Fuel
- Fuel per Lap, sobald genug Daten vorhanden sind
- geschätzte Rest-Runden
- Speed
- Gear
- RPM
- Throttle
- Brake
- eigener Connection Status

## 9. Mock Collector starten

Ein Mock Collector simuliert ein Auto und sendet jede Sekunde Telemetrie.

Öffne eine neue PowerShell:

```powershell
cd "C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing\collector"
.\.venv\Scripts\Activate.ps1
```

Collector für #23 starten:

```powershell
python collector.py --mock --server http://localhost:8000 --race TRC8H --entry car_23 --driver florian --team-code H3RKA-2381
```

Collector für #80 starten:

```powershell
python collector.py --mock --server http://localhost:8000 --race TRC8H --entry car_80 --driver max --team-code AMG-9082
```

Collector für #911 starten:

```powershell
python collector.py --mock --server http://localhost:8000 --race TRC8H --entry car_911 --driver tom --team-code POR-9117
```

Für mehrere Collectors brauchst du mehrere PowerShell-Fenster.

Stoppen:

```text
Strg + C
```

## 9.1 Live GT7 Collector starten

Für echte GT7-Telemetrie gibt es jetzt eine einfache lokale Collector-App.

Auf diesem Rechner wurde bereits ein Desktop-Symbol erstellt:

```text
TRC GT7 Collector
```

Darauf doppelklicken, dann oeffnet sich die Collector-Oberflaeche.

PowerShell:

```powershell
cd "C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing\collector"
.\.venv\Scripts\Activate.ps1
python collector.py --gui
```

Ablauf:

1. Race Code eingeben
2. `Connect` klicken
3. Team auswählen
4. Fahrer auswählen
5. Team PIN eingeben
6. PlayStation-IP eintragen oder leer lassen für Auto-Detect
7. `Start Sending` klicken

Mehr Details stehen hier:

```text
docs\LIVE_COLLECTOR.md
```

Eine gebaute Windows-EXE liegt hier:

```text
collector\dist\TRC GT7 Collector.exe
```

Diese Datei kann spaeter an Fahrer verteilt werden. Fuer echte Downloads sollten wir danach noch Versionierung, ZIP-Paket, Signierung und Auto-Update klaeren.

## 10. Typischer Testablauf

1. Backend starten
2. Frontend starten
3. Demo-Rennen anlegen
4. Public Timing öffnen
5. Race Control öffnen
6. Einen oder mehrere Mock-Collectors starten
7. Prüfen, ob die Standings live aktualisieren
8. Team Engineer Login testen
9. Falschen Team-Code testen
10. Collector stoppen und prüfen, ob Race Control den Verbindungsstatus erkennt

## 10.1 Automatischer Funktionstest

Wenn Backend und Frontend laufen, kannst du fast alle wichtigen MVP-Funktionen automatisch testen.

PowerShell:

```powershell
cd "C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing"
.\server\.venv\Scripts\python.exe scripts\smoke_test.py
```

Der Test prüft:

- Backend Healthcheck
- Frontend-Erreichbarkeit
- Demo-Rennen
- Race-Control-Login
- falsches Race-Control-Passwort
- Race-Control-Rennliste
- Collector-Team-/Fahrerliste
- Entries
- Team-Login mit korrektem Code
- Team-Login mit falschem Code
- Collector-Registrierung
- falscher Fahrer beim Collector
- Telemetrie-Ingest
- Public Standings
- Public/Private-Datentrennung
- Team Private API
- Race-Control Private View
- Collector-Monitoring
- Pitstop-Erkennung ueber Fuel-Anstieg
- Penalty-Update
- Entry-Erstellung und Entry-Loeschen
- Race-Status-Update
- Race Log
- Public WebSocket
- Team WebSocket
- Race-Control WebSocket
- Reset des Demo-Zustands nach dem Test

Erfolgreiches Ergebnis:

```text
Result: 31/31 checks passed
```

## 11. Häufige Fehler

### Backend startet nicht

Prüfe, ob du im richtigen Ordner bist:

```powershell
cd "C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing\server"
```

Dann:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

### Frontend zeigt keine Daten

Prüfe:

- Backend läuft auf `http://localhost:8000`
- Frontend läuft auf `http://localhost:5173`
- Demo-Rennen `TRC8H` wurde angelegt
- mindestens ein Mock Collector läuft

### Team Login geht nicht

Prüfe:

- Race Code stimmt
- Entry ID stimmt
- Team Code stimmt

Beispiel:

```text
Race Code: TRC8H
Entry ID: car_23
Team Code: H3RKA-2381
```

### Collector meldet Team-Code-Fehler

Dann passt der Code nicht zum Entry.

Beispiel:

`H3RKA-2381` gehört zu `car_23`, nicht zu `car_80`.

### Port ist bereits belegt

Backend Standardport:

```text
8000
```

Frontend Standardport:

```text
5173
```

Wenn dort schon etwas läuft, das andere Programm beenden oder den Port ändern.

Wenn beim Backend-Start dieser Fehler erscheint:

```text
WinError 10013
Der Zugriff auf einen Socket war aufgrund der Zugriffsrechte des Sockets unzulässig
```

prüfe zuerst, ob der Server bereits läuft:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/health
```

Wenn dort `"status": "ok"` zurückkommt, ist alles gut. Dann musst du den Backend-Server nicht nochmal starten.

Falls du den alten Server stoppen willst:

```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object LocalAddress,LocalPort,State,OwningProcess
Stop-Process -Id <OwningProcess>
```

Danach kannst du das Backend wieder starten:

```powershell
uvicorn app.main:app --reload
```

Alternativ kannst du testweise einen anderen Port verwenden:

```powershell
uvicorn app.main:app --reload --port 8001
```

Dann muss das Frontend aber auch auf diesen Backend-Port zeigen.

## 12. Wichtige Entwicklungsgrenzen des aktuellen MVP

Noch nicht enthalten:

- echter GT7 UDP Collector
- Windows-Installer
- grafische Collector-App
- perfekte Gap-Berechnung
- Trackmap
- Pitlane-Erkennung
- OBS Overlay
- Admin-Userverwaltung

Schon vorbereitet:

- austauschbare Collector-Telemetriequelle
- klare Trennung Public vs Private
- Team-Token
- Collector-Token
- Race-Control-Rolle
- WebSocket-Liveupdates
- SQLite-Datenbank

## 13. Server stoppen

Im jeweiligen PowerShell-Fenster:

```text
Strg + C
```

Stoppe:

- Backend-Fenster
- Frontend-Fenster
- alle Collector-Fenster

## 14. Wichtig für echte Tests

Für einen ersten Member-Test reicht:

- Backend und Frontend auf einem Rechner starten
- Demo-Rennen oder echtes Rennen in Race Control anlegen
- pro Team einen Mock Collector starten
- Public Timing und Team Engineer View prüfen

Für echte GT7-Daten kommt später:

```text
MockTelemetrySource
→ GT7TelemetrySource
```

Die Server-API bleibt dabei gleich.
