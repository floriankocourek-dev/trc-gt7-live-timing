from __future__ import annotations

import math
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from gt7_protocol import GT7TelemetryError, GT7UdpReceiver, discover_playstation, estimate_lap_progress, speed_is_plausible


@dataclass
class TelemetryPacket:
    timestamp: str
    lap: int
    lap_progress: float
    last_lap_ms: int | None
    best_lap_ms: int | None
    speed_kmh: float
    fuel_liters: float
    gear: int
    rpm: int
    throttle: float
    brake: float
    position_x: float
    position_y: float
    position_z: float
    tire_compound: str | None = None
    tire_temp_fl: float | None = None
    tire_temp_fr: float | None = None
    tire_temp_rl: float | None = None
    tire_temp_rr: float | None = None
    gt7_telemetry: dict | None = None
    telemetry_status: str = "valid"

    def as_payload(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "lap": self.lap,
            "lap_progress": self.lap_progress,
            "last_lap_ms": self.last_lap_ms,
            "best_lap_ms": self.best_lap_ms,
            "speed_kmh": round(self.speed_kmh, 1),
            "fuel_liters": round(self.fuel_liters, 2),
            "gear": self.gear,
            "rpm": self.rpm,
            "throttle": round(self.throttle, 1),
            "brake": round(self.brake, 1),
            "position_x": round(self.position_x, 2),
            "position_y": round(self.position_y, 2),
            "position_z": round(self.position_z, 2),
            "tire_compound": self.tire_compound,
            "tire_temp_fl": round(self.tire_temp_fl, 1) if self.tire_temp_fl is not None else None,
            "tire_temp_fr": round(self.tire_temp_fr, 1) if self.tire_temp_fr is not None else None,
            "tire_temp_rl": round(self.tire_temp_rl, 1) if self.tire_temp_rl is not None else None,
            "tire_temp_rr": round(self.tire_temp_rr, 1) if self.tire_temp_rr is not None else None,
            "gt7_telemetry": self.gt7_telemetry,
            "telemetry_status": self.telemetry_status,
        }


class TelemetrySource(ABC):
    @abstractmethod
    def packets(self) -> Iterator[TelemetryPacket]:
        raise NotImplementedError


class MockTelemetrySource(TelemetrySource):
    def __init__(
        self,
        start_lap: int = 1,
        base_lap_seconds: float = 505.0,
        fuel_liters: float = 100.0,
        fuel_per_lap: float = 6.1,
        update_hz: float = 1.0,
        seed: int | None = None,
    ) -> None:
        self.start_lap = start_lap
        self.base_lap_seconds = base_lap_seconds
        self.fuel_liters = fuel_liters
        self.fuel_per_lap = fuel_per_lap
        self.update_interval = 1.0 / update_hz
        self.random = random.Random(seed)

    def packets(self) -> Iterator[TelemetryPacket]:
        started = time.monotonic()
        lap = self.start_lap
        lap_started = started
        best_lap_ms: int | None = None
        last_lap_ms: int | None = None
        current_lap_seconds = self._next_lap_time()

        while True:
            now = time.monotonic()
            elapsed_lap = now - lap_started
            progress = min(elapsed_lap / current_lap_seconds, 0.999)
            if elapsed_lap >= current_lap_seconds:
                last_lap_ms = int(current_lap_seconds * 1000)
                best_lap_ms = last_lap_ms if best_lap_ms is None else min(best_lap_ms, last_lap_ms)
                lap += 1
                lap_started = now
                current_lap_seconds = self._next_lap_time()
                progress = 0.0

            phase = progress * math.tau
            speed = max(45.0, 210 + 55 * math.sin(phase * 2.6) + self.random.uniform(-8, 8))
            brake = max(0.0, 95 * math.sin(phase * 7.0 - 1.4))
            throttle = max(0.0, min(100.0, 98 - brake + self.random.uniform(-5, 5)))
            gear = max(1, min(6, int(speed // 42) + 1))
            rpm = int(2500 + gear * 750 + throttle * 40 + self.random.uniform(-150, 150))
            total_laps_progress = (lap - self.start_lap) + progress
            fuel = max(0.0, self.fuel_liters - total_laps_progress * self.fuel_per_lap)

            yield TelemetryPacket(
                timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                lap=lap,
                lap_progress=round(progress, 4),
                last_lap_ms=last_lap_ms,
                best_lap_ms=best_lap_ms,
                speed_kmh=speed,
                fuel_liters=fuel,
                gear=gear,
                rpm=rpm,
                throttle=throttle,
                brake=brake,
                position_x=math.cos(phase) * 1800 + self.random.uniform(-6, 6),
                position_y=20 + math.sin(phase * 3) * 3,
                position_z=math.sin(phase) * 1800 + self.random.uniform(-6, 6),
                tire_compound="Medium",
                tire_temp_fl=82 + 8 * math.sin(phase * 2.0),
                tire_temp_fr=83 + 8 * math.sin(phase * 2.0 + 0.2),
                tire_temp_rl=78 + 6 * math.sin(phase * 1.7),
                tire_temp_rr=79 + 6 * math.sin(phase * 1.7 + 0.2),
                gt7_telemetry={
                    "source": "mock",
                    "fuel_capacity": self.fuel_liters,
                    "base_lap_seconds": self.base_lap_seconds,
                    "update_interval": self.update_interval,
                },
            )
            time.sleep(self.update_interval)

    def _next_lap_time(self) -> float:
        return self.base_lap_seconds + self.random.uniform(-6.5, 8.0)


class GT7TelemetrySource(TelemetrySource):
    def __init__(
        self,
        playstation_ip: str | None = None,
        heartbeat_type: str = "A",
        update_hz: float = 1.0,
        bind_port: int = 33740,
        heartbeat_port: int = 33739,
        lap_display_offset: int = 0,
    ) -> None:
        self.playstation_ip = playstation_ip
        self.heartbeat_type = heartbeat_type
        self.update_interval = 1.0 / update_hz
        self.bind_port = bind_port
        self.heartbeat_port = heartbeat_port
        self.lap_display_offset = lap_display_offset
        self.last_packet_sent = 0.0

    def packets(self) -> Iterator[TelemetryPacket]:
        playstation_ip = self.playstation_ip
        if not playstation_ip:
            playstation_ip, host_type = discover_playstation()
            if not playstation_ip:
                raise GT7TelemetryError(
                    "PlayStation was not found. Please enter the PlayStation IP address manually and check that "
                    "the PlayStation and this PC are in the same network."
                )
            if host_type and "STANDBY" in host_type:
                raise GT7TelemetryError("PlayStation was found, but it appears to be in standby. Please turn it on.")

        with GT7UdpReceiver(
            playstation_ip=playstation_ip,
            heartbeat_type=self.heartbeat_type,
            bind_port=self.bind_port,
            heartbeat_port=self.heartbeat_port,
        ) as receiver:
            while True:
                packet = receiver.receive_packet()
                now = time.monotonic()
                if now - self.last_packet_sent < self.update_interval:
                    continue
                self.last_packet_sent = now

                if not speed_is_plausible(packet):
                    continue

                raw_lap = packet.current_lap if packet.current_lap and packet.current_lap > 0 else 0
                lap = raw_lap + self.lap_display_offset if raw_lap else 0
                yield TelemetryPacket(
                    timestamp=packet.received_at,
                    lap=lap,
                    lap_progress=estimate_lap_progress(packet),
                    last_lap_ms=packet.last_lap_time_ms,
                    best_lap_ms=packet.best_lap_time_ms,
                    speed_kmh=packet.speed_kmh,
                    fuel_liters=packet.fuel_level,
                    gear=packet.current_gear or 0,
                    rpm=int(packet.engine_rpm),
                    throttle=packet.throttle_percent,
                    brake=packet.brake_percent,
                    position_x=packet.position_x,
                    position_y=packet.position_y,
                    position_z=packet.position_z,
                    tire_compound=None,
                    tire_temp_fl=packet.tire_temp_fl,
                    tire_temp_fr=packet.tire_temp_fr,
                    tire_temp_rl=packet.tire_temp_rl,
                    tire_temp_rr=packet.tire_temp_rr,
                    gt7_telemetry=packet.as_private_telemetry(),
                    telemetry_status=packet.telemetry_status,
                )
