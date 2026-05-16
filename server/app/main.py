from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
import string
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field


BASE_DIR = Path(__file__).resolve().parents[1]
WEB_DIST_DIR = BASE_DIR.parent / "web" / "dist"
DB_PATH = Path(os.getenv("TRC_DB_PATH", BASE_DIR / "trc_timing.sqlite3"))
SECRET = os.getenv("TRC_SECRET", "dev-secret-change-me")
RACE_CONTROL_PASSWORD = os.getenv("TRC_RACE_CONTROL_PASSWORD", "admin")
ONLINE_WINDOW_SECONDS = 10
REFERENCE_LAP_SECONDS = 500
PIT_FUEL_INCREASE_LITERS = 1.0
PIT_EXIT_SPEED_KMH = 90.0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def hash_value(value: str) -> str:
    return hashlib.sha256(f"{SECRET}:{value}".encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def slug(value: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    return "_".join(part for part in clean.split("_") if part) or "driver"


def make_entry_id(car_number: int) -> str:
    return f"car_{car_number}"


def make_team_code(team_name: str, car_number: int) -> str:
    prefix = "".join(ch for ch in team_name.upper() if ch in string.ascii_uppercase + string.digits)[:5]
    if len(prefix) < 3:
        prefix = f"CAR{car_number}"
    return f"{prefix}-{secrets.randbelow(9000) + 1000}"


@contextmanager
def db() -> Any:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute(query, params).fetchone()


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(query, params).fetchall()


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    with db() as conn:
        conn.execute(query, params)


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS races (
                race_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                track_id TEXT,
                duration_minutes INTEGER NOT NULL,
                start_time TEXT,
                event_type TEXT NOT NULL,
                drivers_per_team INTEGER NOT NULL,
                classes_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entries (
                entry_id TEXT PRIMARY KEY,
                race_id TEXT NOT NULL,
                car_number INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                car_model TEXT NOT NULL,
                car_class TEXT NOT NULL,
                drivers_json TEXT NOT NULL,
                team_code_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                pit_stops INTEGER NOT NULL DEFAULT 0,
                pit_status TEXT NOT NULL DEFAULT 'on_track',
                penalty_seconds INTEGER NOT NULL DEFAULT 0,
                manual_status TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (race_id) REFERENCES races(race_id)
            );

            CREATE TABLE IF NOT EXISTS collector_sessions (
                collector_id TEXT PRIMARY KEY,
                race_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                driver_id TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                connected_at TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                status TEXT NOT NULL,
                version TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS team_sessions (
                session_id TEXT PRIMARY KEY,
                race_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_sessions (
                session_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS telemetry_packets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                driver_id TEXT NOT NULL,
                collector_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                lap INTEGER NOT NULL,
                lap_progress REAL,
                last_lap_ms INTEGER,
                best_lap_ms INTEGER,
                speed_kmh REAL,
                fuel_liters REAL,
                gear INTEGER,
                rpm INTEGER,
                throttle REAL,
                brake REAL,
                position_x REAL,
                position_y REAL,
                position_z REAL,
                tire_compound TEXT,
                tire_temp_fl REAL,
                tire_temp_fr REAL,
                tire_temp_rl REAL,
                tire_temp_rr REAL,
                telemetry_status TEXT NOT NULL,
                received_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS latest_telemetry (
                entry_id TEXT PRIMARY KEY,
                race_id TEXT NOT NULL,
                driver_id TEXT NOT NULL,
                collector_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                lap INTEGER NOT NULL,
                lap_progress REAL,
                last_lap_ms INTEGER,
                best_lap_ms INTEGER,
                speed_kmh REAL,
                fuel_liters REAL,
                gear INTEGER,
                rpm INTEGER,
                throttle REAL,
                brake REAL,
                position_x REAL,
                position_y REAL,
                position_z REAL,
                tire_compound TEXT,
                tire_temp_fl REAL,
                tire_temp_fr REAL,
                tire_temp_rl REAL,
                tire_temp_rr REAL,
                telemetry_status TEXT NOT NULL,
                received_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS race_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id TEXT NOT NULL,
                entry_id TEXT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        ensure_column(conn, "entries", "pit_status", "TEXT NOT NULL DEFAULT 'on_track'")
        for table in ("telemetry_packets", "latest_telemetry"):
            ensure_column(conn, table, "tire_compound", "TEXT")
            ensure_column(conn, table, "tire_temp_fl", "REAL")
            ensure_column(conn, table, "tire_temp_fr", "REAL")
            ensure_column(conn, table, "tire_temp_rl", "REAL")
            ensure_column(conn, table, "tire_temp_rr", "REAL")


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


class RaceCreate(BaseModel):
    race_id: str
    name: str
    track_id: str | None = None
    duration_minutes: int = 480
    start_time: str | None = None
    event_type: Literal["solo", "team"] = "team"
    drivers_per_team: int = 2
    classes: list[str] = Field(default_factory=lambda: ["GT3"])
    status: str = "scheduled"


class DriverInput(BaseModel):
    driver_id: str | None = None
    display_name: str


class EntryCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entry_id: str | None = None
    car_number: int
    team_name: str
    car_model: str
    car_class: str = Field(alias="class")
    drivers: list[DriverInput]
    team_code: str | None = None
    status: str = "active"


class TeamLogin(BaseModel):
    race_code: str
    entry_id: str
    team_code: str


class CollectorRegister(BaseModel):
    race_code: str
    entry_id: str
    team_code: str
    driver_id: str
    collector_version: str = "0.1.0"


class TelemetryIn(BaseModel):
    timestamp: str | None = None
    lap: int
    lap_progress: float | None = None
    last_lap_ms: int | None = None
    best_lap_ms: int | None = None
    speed_kmh: float | None = None
    fuel_liters: float | None = None
    gear: int | None = None
    rpm: int | None = None
    throttle: float | None = None
    brake: float | None = None
    position_x: float | None = None
    position_y: float | None = None
    position_z: float | None = None
    tire_compound: str | None = None
    tire_temp_fl: float | None = None
    tire_temp_fr: float | None = None
    tire_temp_rl: float | None = None
    tire_temp_rr: float | None = None
    telemetry_status: str = "valid"


class AdminLogin(BaseModel):
    password: str


class PenaltyUpdate(BaseModel):
    seconds: int
    reason: str | None = None


class StatusUpdate(BaseModel):
    status: str
    note: str | None = None


class RaceStatusUpdate(BaseModel):
    status: str


def row_to_race(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "race_id": row["race_id"],
        "name": row["name"],
        "track_id": row["track_id"],
        "duration_minutes": row["duration_minutes"],
        "start_time": row["start_time"],
        "event_type": row["event_type"],
        "drivers_per_team": row["drivers_per_team"],
        "classes": json.loads(row["classes_json"]),
        "status": row["status"],
        "created_at": row["created_at"],
    }


def row_to_entry(row: sqlite3.Row, include_private: bool = False) -> dict[str, Any]:
    item = {
        "entry_id": row["entry_id"],
        "race_id": row["race_id"],
        "car_number": row["car_number"],
        "team_name": row["team_name"],
        "car_model": row["car_model"],
        "class": row["car_class"],
        "drivers": json.loads(row["drivers_json"]),
        "status": row["status"],
        "pit_stops": row["pit_stops"],
        "pit_status": row["pit_status"],
        "penalty_seconds": row["penalty_seconds"],
        "manual_status": row["manual_status"],
    }
    if include_private:
        item["team_code_hash"] = row["team_code_hash"]
    return item


def get_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.removeprefix("Bearer ").strip()


def require_admin(authorization: str | None = Header(default=None)) -> str:
    token = get_bearer_token(authorization)
    token_hash = hash_value(token)
    row = fetch_one("SELECT * FROM admin_sessions WHERE token_hash = ?", (token_hash,))
    if not row:
        raise HTTPException(status_code=401, detail="Invalid race control token")
    execute("UPDATE admin_sessions SET last_seen = ? WHERE session_id = ?", (now_iso(), row["session_id"]))
    return row["session_id"]


def require_team(authorization: str | None = Header(default=None)) -> sqlite3.Row:
    token = get_bearer_token(authorization)
    token_hash = hash_value(token)
    row = fetch_one("SELECT * FROM team_sessions WHERE token_hash = ?", (token_hash,))
    if not row:
        raise HTTPException(status_code=401, detail="Invalid team token")
    execute("UPDATE team_sessions SET last_seen = ? WHERE session_id = ?", (now_iso(), row["session_id"]))
    return row


def require_collector(authorization: str | None = Header(default=None)) -> sqlite3.Row:
    token = get_bearer_token(authorization)
    token_hash = hash_value(token)
    row = fetch_one("SELECT * FROM collector_sessions WHERE token_hash = ?", (token_hash,))
    if not row:
        raise HTTPException(status_code=401, detail="Invalid collector token")
    return row


def driver_display(entry: sqlite3.Row, driver_id: str | None) -> str | None:
    if not driver_id:
        return None
    for driver in json.loads(entry["drivers_json"]):
        if driver["driver_id"] == driver_id:
            return driver["display_name"]
    return driver_id


def verify_team_code(entry: sqlite3.Row, team_code: str) -> None:
    if not secrets.compare_digest(entry["team_code_hash"], hash_value(team_code)):
        raise HTTPException(status_code=401, detail="Team code is incorrect")


def verify_driver(entry: sqlite3.Row, driver_id: str) -> None:
    drivers = json.loads(entry["drivers_json"])
    if driver_id not in {driver["driver_id"] for driver in drivers}:
        raise HTTPException(status_code=400, detail="Driver does not belong to this entry")


def log_event(race_id: str, message: str, entry_id: str | None = None, level: str = "info") -> None:
    execute(
        "INSERT INTO race_log (race_id, entry_id, level, message, created_at) VALUES (?, ?, ?, ?, ?)",
        (race_id, entry_id, level, message, now_iso()),
    )


def connection_status(latest: sqlite3.Row | None) -> str:
    if not latest:
        return "offline"
    try:
        received = datetime.fromisoformat(latest["received_at"].replace("Z", "+00:00"))
    except ValueError:
        return "offline"
    age = datetime.now(timezone.utc).timestamp() - received.timestamp()
    return "online" if age <= ONLINE_WINDOW_SECONDS else "offline"


def compute_standings(race_id: str) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT e.*, lt.driver_id AS lt_driver_id, lt.lap, lt.lap_progress, lt.last_lap_ms,
               lt.best_lap_ms, lt.telemetry_status, lt.received_at
        FROM entries e
        LEFT JOIN latest_telemetry lt ON lt.entry_id = e.entry_id
        WHERE e.race_id = ?
        """,
        (race_id,),
    )

    sortable: list[tuple[float, sqlite3.Row]] = []
    for row in rows:
        laps = row["lap"] or 0
        progress = row["lap_progress"] if row["lap_progress"] is not None else 0
        sortable.append((float(laps) + float(progress), row))
    sortable.sort(key=lambda item: item[0], reverse=True)

    leader_progress = sortable[0][0] if sortable else None
    previous_progress: float | None = None
    standings: list[dict[str, Any]] = []

    for index, (progress, row) in enumerate(sortable, start=1):
        latest_present = row["received_at"] is not None
        status = row["manual_status"] or (row["pit_status"] if latest_present else "offline")
        gap_to_leader = None
        gap_to_ahead = None
        if leader_progress is not None and progress < leader_progress:
            lap_delta = int(leader_progress) - int(progress)
            if lap_delta > 0:
                gap_to_leader = f"+{lap_delta} Lap" if lap_delta == 1 else f"+{lap_delta} Laps"
            else:
                gap_to_leader = f"+{(leader_progress - progress) * REFERENCE_LAP_SECONDS:.1f}s est"
        if previous_progress is not None and progress < previous_progress:
            lap_delta = int(previous_progress) - int(progress)
            if lap_delta > 0:
                gap_to_ahead = f"+{lap_delta} Lap" if lap_delta == 1 else f"+{lap_delta} Laps"
            else:
                gap_to_ahead = f"+{(previous_progress - progress) * REFERENCE_LAP_SECONDS:.1f}s est"

        standings.append(
            {
                "position": index,
                "entry_id": row["entry_id"],
                "car_number": row["car_number"],
                "class": row["car_class"],
                "team_name": row["team_name"],
                "current_driver": driver_display(row, row["lt_driver_id"]),
                "car_model": row["car_model"],
                "laps": row["lap"] or 0,
                "lap_progress": row["lap_progress"],
                "gap_to_leader": gap_to_leader,
                "gap_to_ahead": gap_to_ahead,
                "last_lap_ms": row["last_lap_ms"],
                "best_lap_ms": row["best_lap_ms"],
                "pit_status": row["pit_status"] if latest_present else "offline",
                "pit_stops": row["pit_stops"],
                "penalty_seconds": row["penalty_seconds"],
                "status": status,
                "connection_status": connection_status(row if latest_present else None),
            }
        )
        previous_progress = progress
    return standings


def public_race_list() -> list[dict[str, Any]]:
    rows = fetch_all("SELECT * FROM races ORDER BY created_at DESC, race_id ASC")
    return [row_to_race(row) for row in rows]


def private_state_for_entry(entry_id: str) -> dict[str, Any]:
    entry = fetch_one("SELECT * FROM entries WHERE entry_id = ?", (entry_id,))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    latest = fetch_one("SELECT * FROM latest_telemetry WHERE entry_id = ?", (entry_id,))
    standings = compute_standings(entry["race_id"])
    own_standing = next((item for item in standings if item["entry_id"] == entry_id), None)

    fuel_per_lap = None
    estimated_laps_remaining = None
    current_stint_laps = 0
    history = fetch_all(
        """
        SELECT lap, fuel_liters FROM telemetry_packets
        WHERE entry_id = ? AND fuel_liters IS NOT NULL
        ORDER BY id DESC LIMIT 200
        """,
        (entry_id,),
    )
    if len(history) >= 2:
        newest = history[0]
        oldest = history[-1]
        lap_delta = newest["lap"] - oldest["lap"]
        fuel_delta = oldest["fuel_liters"] - newest["fuel_liters"]
        if lap_delta > 0 and fuel_delta > 0:
            fuel_per_lap = round(fuel_delta / lap_delta, 2)
            if latest and latest["fuel_liters"] is not None:
                estimated_laps_remaining = round(latest["fuel_liters"] / fuel_per_lap, 1)
            current_stint_laps = lap_delta

    latest_dict = dict(latest) if latest else {}
    return {
        "entry": row_to_entry(entry),
        "standing": own_standing,
        "fuel_liters": latest_dict.get("fuel_liters"),
        "fuel_per_lap": fuel_per_lap,
        "estimated_laps_remaining": estimated_laps_remaining,
        "speed_kmh": latest_dict.get("speed_kmh"),
        "gear": latest_dict.get("gear"),
        "rpm": latest_dict.get("rpm"),
        "throttle": latest_dict.get("throttle"),
        "brake": latest_dict.get("brake"),
        "position_x": latest_dict.get("position_x"),
        "position_y": latest_dict.get("position_y"),
        "position_z": latest_dict.get("position_z"),
        "tire_compound": latest_dict.get("tire_compound"),
        "tire_temp_fl": latest_dict.get("tire_temp_fl"),
        "tire_temp_fr": latest_dict.get("tire_temp_fr"),
        "tire_temp_rl": latest_dict.get("tire_temp_rl"),
        "tire_temp_rr": latest_dict.get("tire_temp_rr"),
        "current_stint_laps": current_stint_laps,
        "last_seen": latest_dict.get("received_at"),
        "connection_status": connection_status(latest),
    }


def update_pit_detection(conn: sqlite3.Connection, session: sqlite3.Row, payload: TelemetryIn) -> None:
    previous = conn.execute("SELECT * FROM latest_telemetry WHERE entry_id = ?", (session["entry_id"],)).fetchone()
    entry = conn.execute("SELECT pit_status, pit_stops FROM entries WHERE entry_id = ?", (session["entry_id"],)).fetchone()
    if not entry:
        return

    current_status = entry["pit_status"] or "on_track"
    next_status = current_status
    should_count_stop = False

    if previous and previous["fuel_liters"] is not None and payload.fuel_liters is not None:
        fuel_increase = payload.fuel_liters - previous["fuel_liters"]
        if fuel_increase >= PIT_FUEL_INCREASE_LITERS:
            next_status = "in_pit"
            should_count_stop = current_status != "in_pit"

    if current_status == "in_pit" and payload.speed_kmh is not None and payload.speed_kmh >= PIT_EXIT_SPEED_KMH:
        next_status = "on_track"

    if next_status != current_status or should_count_stop:
        pit_stops = entry["pit_stops"] + (1 if should_count_stop else 0)
        conn.execute(
            "UPDATE entries SET pit_status = ?, pit_stops = ? WHERE entry_id = ?",
            (next_status, pit_stops, session["entry_id"]),
        )
        if should_count_stop:
            conn.execute(
                "INSERT INTO race_log (race_id, entry_id, level, message, created_at) VALUES (?, ?, ?, ?, ?)",
                (session["race_id"], session["entry_id"], "info", f"Pit stop detected for {session['entry_id']}", now_iso()),
            )


class WebSocketHub:
    def __init__(self) -> None:
        self._sockets: dict[str, list[tuple[WebSocket, str, str | None]]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, race_id: str, websocket: WebSocket, kind: str, token: str | None = None) -> None:
        await websocket.accept()
        async with self._lock:
            self._sockets.setdefault(race_id, []).append((websocket, kind, token))

    async def disconnect(self, race_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._sockets.get(race_id, [])
            self._sockets[race_id] = [item for item in sockets if item[0] is not websocket]

    async def send_snapshot(self, race_id: str, websocket: WebSocket, kind: str, token: str | None = None) -> None:
        payload = build_socket_payload(race_id, kind, token)
        await websocket.send_json(payload)

    async def broadcast(self, race_id: str) -> None:
        async with self._lock:
            sockets = list(self._sockets.get(race_id, []))
        for websocket, kind, token in sockets:
            try:
                await self.send_snapshot(race_id, websocket, kind, token)
            except Exception:
                await self.disconnect(race_id, websocket)


hub = WebSocketHub()
app = FastAPI(title="TRC GT7 Live Timing", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("TRC_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


def build_socket_payload(race_id: str, kind: str, token: str | None = None) -> dict[str, Any]:
    if kind == "public":
        return {"type": "standings", "race_id": race_id, "standings": compute_standings(race_id)}
    if kind == "team":
        if not token:
            raise HTTPException(status_code=401, detail="Missing team token")
        row = fetch_one("SELECT * FROM team_sessions WHERE token_hash = ? AND race_id = ?", (hash_value(token), race_id))
        if not row:
            raise HTTPException(status_code=401, detail="Invalid team token")
        return {"type": "team_state", "race_id": race_id, "state": private_state_for_entry(row["entry_id"])}
    if kind == "race-control":
        if not token:
            raise HTTPException(status_code=401, detail="Missing race control token")
        row = fetch_one("SELECT * FROM admin_sessions WHERE token_hash = ?", (hash_value(token),))
        if not row:
            raise HTTPException(status_code=401, detail="Invalid race control token")
        return {
            "type": "race_control",
            "race_id": race_id,
            "standings": compute_standings(race_id),
            "collectors": list_collectors(race_id),
            "private_states": [private_state_for_entry(entry["entry_id"]) for entry in fetch_all("SELECT entry_id FROM entries WHERE race_id = ?", (race_id,))],
        }
    raise HTTPException(status_code=400, detail="Unknown socket kind")


def list_collectors(race_id: str) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT cs.*, e.car_number, e.team_name
        FROM collector_sessions cs
        JOIN entries e ON e.entry_id = cs.entry_id
        WHERE cs.race_id = ?
        ORDER BY e.car_number
        """,
        (race_id,),
    )
    result = []
    for row in rows:
        result.append(
            {
                "collector_id": row["collector_id"],
                "entry_id": row["entry_id"],
                "car_number": row["car_number"],
                "team_name": row["team_name"],
                "driver_id": row["driver_id"],
                "connected_at": row["connected_at"],
                "last_seen": row["last_seen"],
                "status": row["status"],
                "version": row["version"],
            }
        )
    return result


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": now_iso()}


@app.post("/api/race-control/login")
def admin_login(payload: AdminLogin) -> dict[str, str]:
    if not secrets.compare_digest(payload.password, RACE_CONTROL_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid race control password")
    token = new_token()
    session_id = f"admin_{secrets.token_hex(8)}"
    execute(
        "INSERT INTO admin_sessions (session_id, token_hash, created_at, last_seen) VALUES (?, ?, ?, ?)",
        (session_id, hash_value(token), now_iso(), now_iso()),
    )
    return {"race_control_token": token}


@app.get("/api/race-control/races")
def get_races(_: str = Depends(require_admin)) -> list[dict[str, Any]]:
    return [row_to_race(row) for row in fetch_all("SELECT * FROM races ORDER BY created_at DESC")]


@app.post("/api/race-control/races")
async def create_race(payload: RaceCreate, _: str = Depends(require_admin)) -> dict[str, Any]:
    if fetch_one("SELECT race_id FROM races WHERE race_id = ?", (payload.race_id,)):
        raise HTTPException(status_code=409, detail="Race already exists")
    execute(
        """
        INSERT INTO races (race_id, name, track_id, duration_minutes, start_time, event_type,
                           drivers_per_team, classes_json, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.race_id,
            payload.name,
            payload.track_id,
            payload.duration_minutes,
            payload.start_time,
            payload.event_type,
            payload.drivers_per_team,
            json.dumps(payload.classes),
            payload.status,
            now_iso(),
        ),
    )
    log_event(payload.race_id, f"Race created: {payload.name}")
    await hub.broadcast(payload.race_id)
    return row_to_race(fetch_one("SELECT * FROM races WHERE race_id = ?", (payload.race_id,)))


@app.get("/api/race-control/races/{race_id}")
def get_race(race_id: str, _: str = Depends(require_admin)) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM races WHERE race_id = ?", (race_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Race not found")
    entries = fetch_all("SELECT * FROM entries WHERE race_id = ? ORDER BY car_number", (race_id,))
    return {"race": row_to_race(row), "entries": [row_to_entry(entry) for entry in entries]}


@app.patch("/api/race-control/races/{race_id}/status")
async def update_race_status(race_id: str, payload: RaceStatusUpdate, _: str = Depends(require_admin)) -> dict[str, Any]:
    if not fetch_one("SELECT race_id FROM races WHERE race_id = ?", (race_id,)):
        raise HTTPException(status_code=404, detail="Race not found")
    execute("UPDATE races SET status = ? WHERE race_id = ?", (payload.status, race_id))
    log_event(race_id, f"Race status changed to {payload.status}")
    await hub.broadcast(race_id)
    return {"ok": True, "status": payload.status}


@app.post("/api/race-control/races/{race_id}/entries")
async def create_entry(race_id: str, payload: EntryCreate, _: str = Depends(require_admin)) -> dict[str, Any]:
    if not fetch_one("SELECT race_id FROM races WHERE race_id = ?", (race_id,)):
        raise HTTPException(status_code=404, detail="Race not found")
    entry_id = payload.entry_id or make_entry_id(payload.car_number)
    if fetch_one("SELECT entry_id FROM entries WHERE entry_id = ?", (entry_id,)):
        raise HTTPException(status_code=409, detail="Entry already exists")
    team_code = payload.team_code or make_team_code(payload.team_name, payload.car_number)
    drivers = [
        {"driver_id": driver.driver_id or slug(driver.display_name), "display_name": driver.display_name}
        for driver in payload.drivers
    ]
    execute(
        """
        INSERT INTO entries (entry_id, race_id, car_number, team_name, car_model, car_class,
                             drivers_json, team_code_hash, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry_id,
            race_id,
            payload.car_number,
            payload.team_name,
            payload.car_model,
            payload.car_class,
            json.dumps(drivers),
            hash_value(team_code),
            payload.status,
            now_iso(),
        ),
    )
    log_event(race_id, f"Entry created: #{payload.car_number} {payload.team_name}", entry_id)
    await hub.broadcast(race_id)
    created = row_to_entry(fetch_one("SELECT * FROM entries WHERE entry_id = ?", (entry_id,)))
    created["team_code"] = team_code
    return created


@app.delete("/api/race-control/entries/{entry_id}")
async def delete_entry(entry_id: str, _: str = Depends(require_admin)) -> dict[str, Any]:
    entry = fetch_one("SELECT * FROM entries WHERE entry_id = ?", (entry_id,))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    with db() as conn:
        conn.execute("DELETE FROM telemetry_packets WHERE entry_id = ?", (entry_id,))
        conn.execute("DELETE FROM latest_telemetry WHERE entry_id = ?", (entry_id,))
        conn.execute("DELETE FROM collector_sessions WHERE entry_id = ?", (entry_id,))
        conn.execute("DELETE FROM team_sessions WHERE entry_id = ?", (entry_id,))
        conn.execute("DELETE FROM entries WHERE entry_id = ?", (entry_id,))
        conn.execute(
            "INSERT INTO race_log (race_id, entry_id, level, message, created_at) VALUES (?, ?, ?, ?, ?)",
            (entry["race_id"], entry_id, "warning", f"Entry deleted: #{entry['car_number']} {entry['team_name']}", now_iso()),
        )
    await hub.broadcast(entry["race_id"])
    return {"ok": True, "entry_id": entry_id}


@app.get("/api/race-control/races/{race_id}/collectors")
def get_collectors(race_id: str, _: str = Depends(require_admin)) -> list[dict[str, Any]]:
    return list_collectors(race_id)


@app.get("/api/race-control/races/{race_id}/private")
def get_all_private_states(race_id: str, _: str = Depends(require_admin)) -> list[dict[str, Any]]:
    entries = fetch_all("SELECT entry_id FROM entries WHERE race_id = ? ORDER BY car_number", (race_id,))
    return [private_state_for_entry(entry["entry_id"]) for entry in entries]


@app.get("/api/race-control/races/{race_id}/log")
def get_race_log(race_id: str, _: str = Depends(require_admin)) -> list[dict[str, Any]]:
    rows = fetch_all("SELECT * FROM race_log WHERE race_id = ? ORDER BY id DESC LIMIT 100", (race_id,))
    return [dict(row) for row in rows]


@app.post("/api/race-control/entries/{entry_id}/penalty")
async def set_penalty(entry_id: str, payload: PenaltyUpdate, _: str = Depends(require_admin)) -> dict[str, Any]:
    entry = fetch_one("SELECT * FROM entries WHERE entry_id = ?", (entry_id,))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    execute("UPDATE entries SET penalty_seconds = ? WHERE entry_id = ?", (payload.seconds, entry_id))
    note = f": {payload.reason}" if payload.reason else ""
    log_event(entry["race_id"], f"Penalty set to {payload.seconds}s{note}", entry_id, "warning")
    await hub.broadcast(entry["race_id"])
    return {"ok": True, "entry_id": entry_id, "penalty_seconds": payload.seconds}


@app.post("/api/race-control/entries/{entry_id}/status")
async def set_entry_status(entry_id: str, payload: StatusUpdate, _: str = Depends(require_admin)) -> dict[str, Any]:
    entry = fetch_one("SELECT * FROM entries WHERE entry_id = ?", (entry_id,))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    execute("UPDATE entries SET manual_status = ? WHERE entry_id = ?", (payload.status, entry_id))
    note = f": {payload.note}" if payload.note else ""
    log_event(entry["race_id"], f"Manual status set to {payload.status}{note}", entry_id)
    await hub.broadcast(entry["race_id"])
    return {"ok": True, "entry_id": entry_id, "status": payload.status}


@app.get("/api/public/races/{race_id}/standings")
def public_standings(race_id: str) -> list[dict[str, Any]]:
    if not fetch_one("SELECT race_id FROM races WHERE race_id = ?", (race_id,)):
        raise HTTPException(status_code=404, detail="Race not found")
    return compute_standings(race_id)


@app.get("/api/public/races")
def public_races() -> list[dict[str, Any]]:
    return public_race_list()


@app.post("/api/team/login")
def team_login(payload: TeamLogin) -> dict[str, str]:
    entry = fetch_one("SELECT * FROM entries WHERE race_id = ? AND entry_id = ?", (payload.race_code, payload.entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    verify_team_code(entry, payload.team_code)
    token = new_token()
    session_id = f"team_{secrets.token_hex(8)}"
    execute(
        "INSERT INTO team_sessions (session_id, race_id, entry_id, token_hash, created_at, last_seen) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, payload.race_code, payload.entry_id, hash_value(token), now_iso(), now_iso()),
    )
    return {"session_token": token, "entry_id": payload.entry_id}


@app.get("/api/team/me")
def team_me(session: sqlite3.Row = Depends(require_team)) -> dict[str, Any]:
    return private_state_for_entry(session["entry_id"])


@app.post("/api/collector/register")
async def collector_register(payload: CollectorRegister) -> dict[str, Any]:
    entry = fetch_one("SELECT * FROM entries WHERE race_id = ? AND entry_id = ?", (payload.race_code, payload.entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    verify_team_code(entry, payload.team_code)
    verify_driver(entry, payload.driver_id)
    token = new_token()
    collector_id = f"collector_{secrets.token_hex(8)}"
    execute(
        """
        INSERT INTO collector_sessions (collector_id, race_id, entry_id, driver_id, token_hash,
                                        connected_at, last_seen, status, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            collector_id,
            payload.race_code,
            payload.entry_id,
            payload.driver_id,
            hash_value(token),
            now_iso(),
            now_iso(),
            "online",
            payload.collector_version,
        ),
    )
    log_event(payload.race_code, f"Collector connected for driver {payload.driver_id}", payload.entry_id)
    await hub.broadcast(payload.race_code)
    return {"collector_token": token, "entry_id": payload.entry_id, "collector_id": collector_id, "send_allowed": True}


@app.get("/api/collector/races/{race_id}/entries")
def collector_entries(race_id: str) -> dict[str, Any]:
    race = fetch_one("SELECT * FROM races WHERE race_id = ?", (race_id,))
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    entries = fetch_all(
        """
        SELECT entry_id, car_number, team_name, car_model, car_class, drivers_json, status
        FROM entries
        WHERE race_id = ? AND status = 'active'
        ORDER BY car_number
        """,
        (race_id,),
    )
    return {
        "race": {
            "race_id": race["race_id"],
            "name": race["name"],
            "track_id": race["track_id"],
            "event_type": race["event_type"],
            "drivers_per_team": race["drivers_per_team"],
            "status": race["status"],
        },
        "entries": [
            {
                "entry_id": row["entry_id"],
                "car_number": row["car_number"],
                "team_name": row["team_name"],
                "car_model": row["car_model"],
                "class": row["car_class"],
                "drivers": json.loads(row["drivers_json"]),
            }
            for row in entries
        ],
    }


@app.post("/api/collector/telemetry")
async def telemetry_ingest(payload: TelemetryIn, session: sqlite3.Row = Depends(require_collector)) -> dict[str, Any]:
    received_at = now_iso()
    timestamp = payload.timestamp or received_at
    params = (
        session["race_id"],
        session["entry_id"],
        session["driver_id"],
        session["collector_id"],
        timestamp,
        payload.lap,
        payload.lap_progress,
        payload.last_lap_ms,
        payload.best_lap_ms,
        payload.speed_kmh,
        payload.fuel_liters,
        payload.gear,
        payload.rpm,
        payload.throttle,
        payload.brake,
        payload.position_x,
        payload.position_y,
        payload.position_z,
        payload.tire_compound,
        payload.tire_temp_fl,
        payload.tire_temp_fr,
        payload.tire_temp_rl,
        payload.tire_temp_rr,
        payload.telemetry_status,
        received_at,
    )
    with db() as conn:
        update_pit_detection(conn, session, payload)
        conn.execute(
            """
            INSERT INTO telemetry_packets (race_id, entry_id, driver_id, collector_id, timestamp, lap, lap_progress,
                                           last_lap_ms, best_lap_ms, speed_kmh, fuel_liters, gear, rpm, throttle,
                                           brake, position_x, position_y, position_z, tire_compound, tire_temp_fl,
                                           tire_temp_fr, tire_temp_rl, tire_temp_rr, telemetry_status, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            params,
        )
        conn.execute(
            """
            INSERT INTO latest_telemetry (race_id, entry_id, driver_id, collector_id, timestamp, lap, lap_progress,
                                          last_lap_ms, best_lap_ms, speed_kmh, fuel_liters, gear, rpm, throttle,
                                          brake, position_x, position_y, position_z, tire_compound, tire_temp_fl,
                                          tire_temp_fr, tire_temp_rl, tire_temp_rr, telemetry_status, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entry_id) DO UPDATE SET
                race_id = excluded.race_id,
                driver_id = excluded.driver_id,
                collector_id = excluded.collector_id,
                timestamp = excluded.timestamp,
                lap = excluded.lap,
                lap_progress = excluded.lap_progress,
                last_lap_ms = excluded.last_lap_ms,
                best_lap_ms = excluded.best_lap_ms,
                speed_kmh = excluded.speed_kmh,
                fuel_liters = excluded.fuel_liters,
                gear = excluded.gear,
                rpm = excluded.rpm,
                throttle = excluded.throttle,
                brake = excluded.brake,
                position_x = excluded.position_x,
                position_y = excluded.position_y,
                position_z = excluded.position_z,
                tire_compound = excluded.tire_compound,
                tire_temp_fl = excluded.tire_temp_fl,
                tire_temp_fr = excluded.tire_temp_fr,
                tire_temp_rl = excluded.tire_temp_rl,
                tire_temp_rr = excluded.tire_temp_rr,
                telemetry_status = excluded.telemetry_status,
                received_at = excluded.received_at
            """,
            params,
        )
        conn.execute(
            "UPDATE collector_sessions SET last_seen = ?, status = 'online' WHERE collector_id = ?",
            (received_at, session["collector_id"]),
        )
    await hub.broadcast(session["race_id"])
    return {"ok": True, "received_at": received_at}


@app.websocket("/ws/races/{race_id}/public")
async def ws_public(websocket: WebSocket, race_id: str) -> None:
    await hub.connect(race_id, websocket, "public")
    try:
        await hub.send_snapshot(race_id, websocket, "public")
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(race_id, websocket)


@app.websocket("/ws/races/{race_id}/team")
async def ws_team(websocket: WebSocket, race_id: str, token: str) -> None:
    if not fetch_one("SELECT session_id FROM team_sessions WHERE token_hash = ? AND race_id = ?", (hash_value(token), race_id)):
        await websocket.close(code=1008)
        return
    await hub.connect(race_id, websocket, "team", token)
    try:
        await hub.send_snapshot(race_id, websocket, "team", token)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(race_id, websocket)


@app.websocket("/ws/races/{race_id}/race-control")
async def ws_race_control(websocket: WebSocket, race_id: str, token: str) -> None:
    if not fetch_one("SELECT session_id FROM admin_sessions WHERE token_hash = ?", (hash_value(token),)):
        await websocket.close(code=1008)
        return
    await hub.connect(race_id, websocket, "race-control", token)
    try:
        await hub.send_snapshot(race_id, websocket, "race-control", token)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(race_id, websocket)


@app.post("/api/dev/seed-demo")
async def seed_demo() -> dict[str, Any]:
    admin_token = new_token()
    execute(
        "INSERT INTO admin_sessions (session_id, token_hash, created_at, last_seen) VALUES (?, ?, ?, ?)",
        (f"admin_{secrets.token_hex(8)}", hash_value(admin_token), now_iso(), now_iso()),
    )
    if not fetch_one("SELECT race_id FROM races WHERE race_id = 'TRC8H'"):
        await create_race(
            RaceCreate(
                race_id="TRC8H",
                name="TRC 8H Nurburgring",
                track_id="nurburgring_24h",
                duration_minutes=480,
                event_type="team",
                drivers_per_team=2,
                classes=["GT3 Pro", "GT3 Am"],
            ),
            admin_token,
        )
    created_codes: dict[str, str] = {}
    demo_entries = [
        EntryCreate(
            car_number=23,
            team_name="HERKA Racing",
            car_model="BMW M4 GT3",
            **{"class": "GT3 Pro"},
            drivers=[DriverInput(driver_id="florian", display_name="Florian"), DriverInput(driver_id="veronika", display_name="Veronika")],
            team_code="H3RKA-2381",
        ),
        EntryCreate(
            car_number=80,
            team_name="AMG Nordschleife Team",
            car_model="Mercedes-AMG GT3",
            **{"class": "GT3 Pro"},
            drivers=[DriverInput(driver_id="max", display_name="Max"), DriverInput(driver_id="lena", display_name="Lena")],
            team_code="AMG-9082",
        ),
        EntryCreate(
            car_number=911,
            team_name="Porsche Squad",
            car_model="Porsche 911 RSR",
            **{"class": "GT3 Am"},
            drivers=[DriverInput(driver_id="tom", display_name="Tom"), DriverInput(driver_id="mia", display_name="Mia")],
            team_code="POR-9117",
        ),
    ]
    for entry in demo_entries:
        entry_id = make_entry_id(entry.car_number)
        if not fetch_one("SELECT entry_id FROM entries WHERE entry_id = ?", (entry_id,)):
            created = await create_entry("TRC8H", entry, admin_token)
            created_codes[created["entry_id"]] = created["team_code"]
    return {"ok": True, "race_id": "TRC8H", "team_codes": created_codes, "race_control_token": admin_token}


if (WEB_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST_DIR / "assets"), name="assets")

if WEB_DIST_DIR.exists():
    @app.get("/")
    def web_index() -> FileResponse:
        return FileResponse(WEB_DIST_DIR / "index.html")

    @app.get("/{full_path:path}")
    def web_fallback(full_path: str) -> FileResponse:
        if full_path.startswith(("api/", "ws/", "assets/")):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (WEB_DIST_DIR / full_path).resolve()
        if candidate.is_file() and WEB_DIST_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(WEB_DIST_DIR / "index.html")
