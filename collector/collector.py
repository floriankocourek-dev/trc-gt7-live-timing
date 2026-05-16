from __future__ import annotations

import argparse
import sys
import time
from typing import Callable

import httpx

from gt7_protocol import GT7TelemetryError
from telemetry_sources import GT7TelemetrySource, MockTelemetrySource, TelemetrySource


LIVE_SERVER_URL = "https://trc-gt7-live-timing.onrender.com"

FRIENDLY_ERRORS = {
    401: "Team code is incorrect. Please check the code provided by Race Control.",
    404: "Race or team was not found. Please check the race code and selected team.",
    409: "This team already has a conflicting session. Please contact Race Control.",
}


class CollectorClient:
    def __init__(
        self,
        server_url: str,
        race_code: str,
        entry_id: str,
        driver_id: str,
        team_code: str,
        source: TelemetrySource,
        version: str = "0.1.0",
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.race_code = race_code
        self.entry_id = entry_id
        self.driver_id = driver_id
        self.team_code = team_code
        self.source = source
        self.version = version
        self.token: str | None = None
        self.status_callback = status_callback or print
        self.running = True

    def stop(self) -> None:
        self.running = False

    def status(self, message: str) -> None:
        self.status_callback(message)

    def register(self) -> None:
        payload = {
            "race_code": self.race_code,
            "entry_id": self.entry_id,
            "team_code": self.team_code,
            "driver_id": self.driver_id,
            "collector_version": self.version,
        }
        try:
            response = httpx.post(f"{self.server_url}/api/collector/register", json=payload, timeout=10)
        except httpx.RequestError:
            raise RuntimeError("Connection to timing server failed. Please check your internet connection and server URL.")

        if response.status_code >= 400:
            raise RuntimeError(FRIENDLY_ERRORS.get(response.status_code, f"Server rejected registration ({response.status_code})."))

        data = response.json()
        self.token = data["collector_token"]
        self.status(f"Connected to timing server for {self.entry_id}. Sending allowed: {data['send_allowed']}")

    def run(self) -> None:
        if not self.token:
            self.register()
        assert self.token is not None

        failures = 0
        for packet in self.source.packets():
            if not self.running:
                break
            try:
                response = httpx.post(
                    f"{self.server_url}/api/collector/telemetry",
                    json=packet.as_payload(),
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=10,
                )
                if response.status_code == 401:
                    self.status("Collector token expired or was rejected. Reconnecting...")
                    self.register()
                    continue
                response.raise_for_status()
                failures = 0
                self.status(
                    f"sent lap={packet.lap} progress={packet.lap_progress:.3f} "
                    f"speed={packet.speed_kmh:.0f}km/h fuel={packet.fuel_liters:.1f}L"
                )
            except (httpx.RequestError, httpx.HTTPStatusError):
                failures += 1
                wait_seconds = min(30, 2 * failures)
                self.status("Connection to timing server lost. The app will keep trying to reconnect.")
                time.sleep(wait_seconds)


def build_source(args: argparse.Namespace) -> TelemetrySource:
    if args.mock:
        return MockTelemetrySource(
            start_lap=args.start_lap,
            base_lap_seconds=args.base_lap_seconds,
            fuel_liters=args.fuel_liters,
            fuel_per_lap=args.fuel_per_lap,
            update_hz=args.update_hz,
            seed=args.seed,
        )
    return GT7TelemetrySource(
        playstation_ip=args.ps5_ip,
        heartbeat_type=args.heartbeat_type,
        update_hz=args.update_hz,
        bind_port=args.bind_port,
        heartbeat_port=args.heartbeat_port,
        lap_display_offset=args.lap_display_offset,
    )


def fetch_collector_entries(server_url: str, race_code: str) -> dict:
    try:
        response = httpx.get(f"{server_url.rstrip('/')}/api/collector/races/{race_code}/entries", timeout=10)
    except httpx.RequestError:
        raise RuntimeError("Connection to timing server failed. Please check your internet connection and server URL.")
    if response.status_code == 404:
        raise RuntimeError("Race code was not found. Please check the race code provided by Race Control.")
    response.raise_for_status()
    return response.json()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TRC GT7 Collector")
    parser.add_argument("--gui", action="store_true", help="Open the simple collector window")
    parser.add_argument("--mock", action="store_true", help="Use simulated telemetry data")
    parser.add_argument("--server", default=LIVE_SERVER_URL, help="Timing server URL")
    parser.add_argument("--race", help="Race code, for example TRC8H")
    parser.add_argument("--entry", help="Entry ID, for example car_23")
    parser.add_argument("--driver", help="Driver ID, for example florian")
    parser.add_argument("--team-code", help="Team code provided by Race Control")
    parser.add_argument("--ps5-ip", default=None, help="PlayStation IP address. Leave empty to auto-detect.")
    parser.add_argument("--heartbeat-type", default="A", choices=["A", "B", "~"], help="GT7 heartbeat type")
    parser.add_argument("--bind-port", type=int, default=33740, help="Local UDP receive port for GT7 telemetry")
    parser.add_argument("--heartbeat-port", type=int, default=33739, help="PlayStation UDP heartbeat port")
    parser.add_argument("--lap-display-offset", type=int, default=1, help="Added to GT7 lap count for live current-lap display")
    parser.add_argument("--start-lap", type=int, default=1)
    parser.add_argument("--base-lap-seconds", type=float, default=505.0)
    parser.add_argument("--fuel-liters", type=float, default=100.0)
    parser.add_argument("--fuel-per-lap", type=float, default=6.1)
    parser.add_argument("--update-hz", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.gui:
        from collector_gui import run_gui

        run_gui(default_server=args.server)
        return 0

    missing = [name for name in ("race", "entry", "driver", "team_code") if getattr(args, name) is None]
    if missing:
        print(f"Missing required arguments: {', '.join('--' + item.replace('_', '-') for item in missing)}")
        print("Use --gui for the simple collector window.")
        return 2

    source = build_source(args)
    client = CollectorClient(
        server_url=args.server,
        race_code=args.race,
        entry_id=args.entry,
        driver_id=args.driver,
        team_code=args.team_code,
        source=source,
    )
    try:
        client.run()
    except RuntimeError as error:
        print(str(error))
        return 1
    except GT7TelemetryError as error:
        print(str(error))
        return 1
    except KeyboardInterrupt:
        print("Collector stopped.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
