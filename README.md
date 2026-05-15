# TRC GT7 Live Timing

MVP for a Gran Turismo 7 endurance live timing and race-control system.

The first version uses mock telemetry so the backend, public timing, private team view, permissions and race-control flows can be tested before the real GT7 UDP collector is added.

## Structure

```text
collector/  Python collector with interchangeable telemetry sources
server/     FastAPI backend with SQLite, auth, ingest and WebSockets
web/        React frontend for public timing, team engineer and race control
docs/       Project notes
```

## Quick Start

Eine ausführliche deutschsprachige Bedienungsanleitung liegt hier:

[docs/BEDIENUNGSANLEITUNG.md](docs/BEDIENUNGSANLEITUNG.md)

Details zur echten GT7-Collector-Version:

[docs/LIVE_COLLECTOR.md](docs/LIVE_COLLECTOR.md)

Deployment-Notizen:

[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

### Backend

```powershell
cd "C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing\server"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000`.

Race Control default password for local development: `admin`

To create the built-in demo race, either click `Create Demo Race` in Race Control or run:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/dev/seed-demo -Method Post -ContentType 'application/json' -Body '{}'
```

Demo team codes:

```text
car_23   H3RKA-2381
car_80   AMG-9082
car_911  POR-9117
```

### Web

```powershell
cd "C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing\web"
npm install
npm run dev
```

The frontend runs at `http://localhost:5173`.

### Mock Collector

Create a race and entry in Race Control first, then run:

```powershell
cd "C:\Users\Florian\Desktop\TRC Live Tracking\trc-gt7-live-timing\collector"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python collector.py --mock --server http://localhost:8000 --race TRC8H --entry car_23 --driver florian --team-code H3RKA-2381
```

## Security Shape

Public endpoints never expose fuel, inputs, RPM, gear or raw position data. Team endpoints use the authenticated session to identify the entry and only return that team's private data. Collectors register with a team code once and then send telemetry with a temporary token.
