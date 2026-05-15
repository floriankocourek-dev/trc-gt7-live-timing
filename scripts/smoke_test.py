from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import websockets


API_BASE = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000"
WEB_BASE = "http://127.0.0.1:5173"
RACE_ID = "TRC8H"


PRIVATE_PUBLIC_FIELDS = {
    "fuel_liters",
    "fuel_per_lap",
    "estimated_laps_remaining",
    "throttle",
    "brake",
    "gear",
    "rpm",
    "position_x",
    "position_y",
    "position_z",
}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


checks: list[Check] = []


class ApiError(RuntimeError):
    def __init__(self, status: int, body: Any) -> None:
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


def record(name: str, ok: bool, detail: str = "") -> None:
    checks.append(Check(name, ok, detail))
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {name}{f' - {detail}' if detail else ''}")


def request_json(path: str, method: str = "GET", body: Any | None = None, token: str | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            body_data = json.loads(raw)
        except json.JSONDecodeError:
            body_data = raw
        raise ApiError(error.code, body_data) from error
    except URLError as error:
        raise RuntimeError(f"Could not reach API: {error}") from error


def request_text(url: str) -> tuple[int, str]:
    request = Request(url, method="GET")
    with urlopen(request, timeout=10) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def assert_http_error(name: str, status: int, func) -> None:
    try:
        func()
    except ApiError as error:
        record(name, error.status == status, f"expected {status}, got {error.status}")
        return
    record(name, False, f"expected HTTP {status}, got success")


async def websocket_snapshot(path: str) -> Any:
    async with websockets.connect(f"{WS_BASE}{path}", open_timeout=10) as socket:
        raw = await asyncio.wait_for(socket.recv(), timeout=10)
        return json.loads(raw)


async def run_websocket_checks(team_token: str, admin_token: str) -> None:
    public = await websocket_snapshot(f"/ws/races/{RACE_ID}/public")
    record("public websocket snapshot", public.get("type") == "standings" and len(public.get("standings", [])) >= 3)

    team = await websocket_snapshot(f"/ws/races/{RACE_ID}/team?token={team_token}")
    record("team websocket snapshot", team.get("type") == "team_state" and team["state"]["entry"]["entry_id"] == "car_23")

    control = await websocket_snapshot(f"/ws/races/{RACE_ID}/race-control?token={admin_token}")
    record(
        "race-control websocket snapshot",
        control.get("type") == "race_control"
        and len(control.get("standings", [])) >= 3
        and "private_states" in control,
    )


def ingest_packet(token: str, lap: int, progress: float, fuel: float, speed: float) -> None:
    request_json(
        "/api/collector/telemetry",
        method="POST",
        token=token,
        body={
            "lap": lap,
            "lap_progress": progress,
            "last_lap_ms": 505123,
            "best_lap_ms": 502111,
            "speed_kmh": speed,
            "fuel_liters": fuel,
            "gear": 6,
            "rpm": 7420,
            "throttle": 88,
            "brake": 0,
            "position_x": 1000 + progress,
            "position_y": 20,
            "position_z": -500 - progress,
            "telemetry_status": "valid",
        },
    )


def main() -> int:
    try:
        health = request_json("/api/health")
        record("backend health", health.get("status") == "ok")

        status, html = request_text(WEB_BASE)
        record("frontend reachable", status == 200 and "root" in html)

        seed = request_json("/api/dev/seed-demo", method="POST", body={})
        record("demo race seed", seed.get("ok") is True and seed.get("race_id") == RACE_ID)

        admin = request_json("/api/race-control/login", method="POST", body={"password": "admin"})
        admin_token = admin["race_control_token"]
        record("race-control login", bool(admin_token))

        assert_http_error(
            "race-control rejects wrong password",
            401,
            lambda: request_json("/api/race-control/login", method="POST", body={"password": "wrong"}),
        )

        races = request_json("/api/race-control/races", token=admin_token)
        record("race-control race list", any(race["race_id"] == RACE_ID for race in races))

        detail = request_json(f"/api/race-control/races/{RACE_ID}", token=admin_token)
        record("race detail with entries", len(detail.get("entries", [])) >= 3)

        collector_meta = request_json(f"/api/collector/races/{RACE_ID}/entries")
        record(
            "collector can load team and driver list",
            len(collector_meta.get("entries", [])) >= 3
            and collector_meta["entries"][0]["drivers"][0]["driver_id"],
        )

        assert_http_error(
            "team login rejects wrong team code",
            401,
            lambda: request_json(
                "/api/team/login",
                method="POST",
                body={"race_code": RACE_ID, "entry_id": "car_23", "team_code": "WRONG"},
            ),
        )

        team_login = request_json(
            "/api/team/login",
            method="POST",
            body={"race_code": RACE_ID, "entry_id": "car_23", "team_code": "H3RKA-2381"},
        )
        team_token = team_login["session_token"]
        record("team login accepts correct code", team_login["entry_id"] == "car_23" and bool(team_token))

        assert_http_error(
            "collector rejects wrong driver",
            400,
            lambda: request_json(
                "/api/collector/register",
                method="POST",
                body={
                    "race_code": RACE_ID,
                    "entry_id": "car_23",
                    "team_code": "H3RKA-2381",
                    "driver_id": "max",
                    "collector_version": "smoke-test",
                },
            ),
        )

        collectors = {
            "car_23": request_json(
                "/api/collector/register",
                method="POST",
                body={
                    "race_code": RACE_ID,
                    "entry_id": "car_23",
                    "team_code": "H3RKA-2381",
                    "driver_id": "florian",
                    "collector_version": "smoke-test",
                },
            )["collector_token"],
            "car_80": request_json(
                "/api/collector/register",
                method="POST",
                body={
                    "race_code": RACE_ID,
                    "entry_id": "car_80",
                    "team_code": "AMG-9082",
                    "driver_id": "max",
                    "collector_version": "smoke-test",
                },
            )["collector_token"],
            "car_911": request_json(
                "/api/collector/register",
                method="POST",
                body={
                    "race_code": RACE_ID,
                    "entry_id": "car_911",
                    "team_code": "POR-9117",
                    "driver_id": "tom",
                    "collector_version": "smoke-test",
                },
            )["collector_token"],
        }
        record("collector registration", all(collectors.values()))

        ingest_packet(collectors["car_23"], lap=12, progress=0.72, fuel=42.4, speed=241.2)
        ingest_packet(collectors["car_80"], lap=12, progress=0.80, fuel=38.1, speed=236.8)
        ingest_packet(collectors["car_911"], lap=11, progress=0.95, fuel=51.7, speed=229.4)
        record("telemetry ingest", True)

        public = request_json(f"/api/public/races/{RACE_ID}/standings")
        public_json = json.dumps(public)
        leaked = sorted(field for field in PRIVATE_PUBLIC_FIELDS if field in public_json)
        record("public standings has entries", len(public) >= 3)
        record("public standings ranking", public[0]["entry_id"] == "car_80", f"leader={public[0]['entry_id']}")
        record("public API hides private fields", not leaked, f"leaked={leaked}" if leaked else "")

        private = request_json("/api/team/me", token=team_token)
        record("team private endpoint returns own entry", private["entry"]["entry_id"] == "car_23")
        record("team private endpoint includes fuel", private["fuel_liters"] == 42.4)
        record("team private endpoint includes driver inputs", private["throttle"] == 88 and private["rpm"] == 7420)

        all_private = request_json(f"/api/race-control/races/{RACE_ID}/private", token=admin_token)
        record("race control can view all private states", len(all_private) >= 3)

        collector_rows = request_json(f"/api/race-control/races/{RACE_ID}/collectors", token=admin_token)
        record("race control collector monitor", len(collector_rows) >= 3)

        try:
            request_json("/api/race-control/entries/car_997", method="DELETE", token=admin_token)
        except ApiError:
            pass

        temp_entry = request_json(
            f"/api/race-control/races/{RACE_ID}/entries",
            method="POST",
            token=admin_token,
            body={
                "car_number": 997,
                "team_name": "Smoke Test Entry",
                "car_model": "Test Car",
                "class": "GT3 Test",
                "drivers": [{"driver_id": "smoke", "display_name": "Smoke"}],
                "team_code": "SMOKE-997",
            },
        )
        record("race control creates visible entry", temp_entry["entry_id"] == "car_997")

        temp_token = request_json(
            "/api/collector/register",
            method="POST",
            body={
                "race_code": RACE_ID,
                "entry_id": "car_997",
                "team_code": "SMOKE-997",
                "driver_id": "smoke",
                "collector_version": "smoke-test",
            },
        )["collector_token"]
        ingest_packet(temp_token, lap=5, progress=0.2, fuel=30.0, speed=70.0)
        ingest_packet(temp_token, lap=5, progress=0.21, fuel=36.0, speed=12.0)
        pit_rows = request_json(f"/api/public/races/{RACE_ID}/standings")
        pit_entry = next(row for row in pit_rows if row["entry_id"] == "car_997")
        record("pit stop detected from fuel increase", pit_entry["pit_stops"] == 1 and pit_entry["pit_status"] == "in_pit")

        deleted = request_json("/api/race-control/entries/car_997", method="DELETE", token=admin_token)
        after_delete = request_json(f"/api/race-control/races/{RACE_ID}", token=admin_token)
        record(
            "race control deletes entry",
            deleted["ok"] is True and all(entry["entry_id"] != "car_997" for entry in after_delete["entries"]),
        )

        penalty = request_json(
            "/api/race-control/entries/car_23/penalty",
            method="POST",
            token=admin_token,
            body={"seconds": 7, "reason": "smoke-test"},
        )
        with_penalty = request_json(f"/api/public/races/{RACE_ID}/standings")
        car_23 = next(row for row in with_penalty if row["entry_id"] == "car_23")
        record("race control penalty update", penalty["penalty_seconds"] == 7 and car_23["penalty_seconds"] == 7)

        status = request_json(
            f"/api/race-control/races/{RACE_ID}/status",
            method="PATCH",
            token=admin_token,
            body={"status": "running"},
        )
        record("race status update", status["status"] == "running")

        log = request_json(f"/api/race-control/races/{RACE_ID}/log", token=admin_token)
        record("race log records actions", any("smoke-test" in item["message"] for item in log))

        asyncio.run(run_websocket_checks(team_token, admin_token))

        request_json(
            "/api/race-control/entries/car_23/penalty",
            method="POST",
            token=admin_token,
            body={"seconds": 0, "reason": "reset after smoke-test"},
        )
        request_json(
            f"/api/race-control/races/{RACE_ID}/status",
            method="PATCH",
            token=admin_token,
            body={"status": "scheduled"},
        )
        record("cleanup reset demo state", True)

    except Exception as error:
        record("smoke test crashed", False, str(error))

    failed = [check for check in checks if not check.ok]
    print()
    print(f"Result: {len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        print("Failed checks:")
        for check in failed:
            print(f"- {check.name}: {check.detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
