# Live Deployment

Das System braucht fuer die komplette Live-Version einen dauerhaft laufenden Backend-Prozess mit WebSockets und persistenter Datenbank.

## Warum nicht einfach Vercel fuer alles?

Vercel ist fuer das React-Frontend sehr gut geeignet. Dieses Projekt braucht aber zusaetzlich:

- FastAPI als dauerhaft laufenden ASGI-Server
- WebSocket-Verbindungen fuer Live Timing
- Collector-Ingest von vielen Fahrern
- eine persistente SQLite-Datei oder spaeter PostgreSQL

Vercel Functions sind fuer requestbasierte Serverless-Funktionen gedacht. Fuer dieses MVP ist ein klassischer Webservice auf Render, Railway, Fly.io, Hetzner, DigitalOcean oder einem eigenen VPS passender.

## Vorbereitet

Es gibt jetzt:

```text
Dockerfile
render.yaml
```

Der Docker-Container baut das React-Frontend und serviert es direkt ueber FastAPI. Dadurch reicht ein einziger Webservice.

## Render Blueprint

1. Projekt in ein GitHub-Repo pushen
2. Render oeffnen
3. `New` -> `Blueprint`
4. GitHub-Repo auswaehlen
5. `render.yaml` bestaetigen
6. Env Var setzen:

```text
TRC_RACE_CONTROL_PASSWORD=<sicheres-passwort>
```

7. Deploy starten

Nach dem Deploy laeuft alles unter einer Render-URL, z. B.:

```text
https://trc-gt7-live-timing.onrender.com
```

Collector Server URL waere dann:

```text
https://trc-gt7-live-timing.onrender.com
```

## GitHub vorbereiten

Lokal im Projektordner:

```powershell
cd "C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing"
git add .
git commit -m "Initial GT7 live timing MVP"
git branch -M main
```

Dann auf GitHub ein neues leeres Repository erstellen, z. B.:

```text
trc-gt7-live-timing
```

Danach die GitHub-URL verbinden:

```powershell
git remote add origin https://github.com/<dein-user>/trc-gt7-live-timing.git
git push -u origin main
```

Wenn GitHub nach Login fragt, im Browser anmelden oder einen GitHub Personal Access Token verwenden.

## Spaeter fuer echte Rennen

Fuer ernsthafte Events sollte SQLite durch PostgreSQL ersetzt werden, damit Deploys, Backups und gleichzeitige Schreibzugriffe stabiler werden.
