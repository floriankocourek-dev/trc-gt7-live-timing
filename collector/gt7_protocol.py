from __future__ import annotations

import math
import socket
import struct
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from Crypto.Cipher import Salsa20


GT7_HEARTBEAT_PORT = 33739
GT7_RECEIVE_PORT = 33740
GT7_HEARTBEAT_INTERVAL_SECONDS = 10
GT7_PACKET_SIZE = 0x128
GT7_KEY = b"Simulator Interface Packet GT7 ver 0.0"[:32]
GT7_IV_MASKS = {
    "A": 0xDEADBEAF,
    "B": 0xDEADBEEF,
    "~": 0x55FABB4F,
}
DISCOVERY_PORT = 9302
DISCOVERY_QUERY = b"SRCH * HTTP/1.1\ndevice-discovery-protocol-version:00030010"


class GT7TelemetryError(RuntimeError):
    pass


class GT7PacketError(GT7TelemetryError):
    pass


@dataclass(frozen=True)
class GT7Packet:
    packet_id: int
    received_at: str
    current_lap: int | None
    total_laps: int | None
    best_lap_time_ms: int | None
    last_lap_time_ms: int | None
    position_x: float
    position_y: float
    position_z: float
    speed_mps: float
    engine_rpm: float
    fuel_level: float
    fuel_capacity: float
    throttle_raw: int
    brake_raw: int
    current_gear: int | None
    suggested_gear: int | None
    flags: int

    @property
    def speed_kmh(self) -> float:
        return self.speed_mps * 3.6

    @property
    def throttle_percent(self) -> float:
        return max(0.0, min(100.0, self.throttle_raw / 255 * 100))

    @property
    def brake_percent(self) -> float:
        return max(0.0, min(100.0, self.brake_raw / 255 * 100))

    @property
    def telemetry_status(self) -> str:
        paused = bool(self.flags & (1 << 1))
        loading = bool(self.flags & (1 << 2))
        on_track = bool(self.flags & 1)
        if loading:
            return "loading"
        if paused:
            return "paused"
        if not on_track:
            return "not_on_track"
        return "valid"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def discover_playstation(timeout_seconds: float = 2.0) -> tuple[str | None, str | None]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout_seconds)
        sock.sendto(DISCOVERY_QUERY, ("<broadcast>", DISCOVERY_PORT))
        packet, address = sock.recvfrom(2048)
    except OSError:
        return None, None
    finally:
        sock.close()

    host_type = None
    try:
        text = packet.decode("utf-8", errors="replace")
        status_code = None
        for line in text.splitlines():
            if line.startswith("HTTP"):
                parts = line.split()
                if len(parts) > 1 and parts[1].isdigit():
                    status_code = int(parts[1])
            elif ":" in line:
                key, value = (part.strip() for part in line.split(":", 1))
                if key.lower() == "host-type":
                    host_type = value
        if status_code == 620 and host_type:
            host_type = f"{host_type} STANDBY"
    except Exception:
        host_type = None
    return address[0], host_type


def decrypt_gt7_packet(data: bytes, heartbeat_type: str = "A") -> bytes:
    if heartbeat_type not in GT7_IV_MASKS:
        raise GT7PacketError(f"Unsupported GT7 heartbeat type: {heartbeat_type}")
    if len(data) < 0x44:
        raise GT7PacketError("Telemetry packet is too short")

    seed = struct.unpack("<I", data[0x40:0x44])[0]
    iv = seed ^ GT7_IV_MASKS[heartbeat_type]
    nonce = struct.pack("<II", iv, seed)
    cipher = Salsa20.new(key=GT7_KEY, nonce=nonce)
    return cipher.decrypt(data)


def parse_gt7_packet(plain: bytes) -> GT7Packet:
    if len(plain) < GT7_PACKET_SIZE:
        raise GT7PacketError(f"Expected at least {GT7_PACKET_SIZE} bytes, got {len(plain)}")
    header = plain[:4].decode("ascii", errors="replace")
    if header not in {"0S7G", "G7S0"}:
        raise GT7PacketError(f"Invalid GT7 packet header: {header}")

    def f32(offset: int) -> float:
        return struct.unpack_from("<f", plain, offset)[0]

    def u8(offset: int) -> int:
        return plain[offset]

    def u16(offset: int) -> int:
        return struct.unpack_from("<H", plain, offset)[0]

    def u32(offset: int) -> int:
        return struct.unpack_from("<I", plain, offset)[0]

    def nullable_u16(value: int) -> int | None:
        return None if value == 0xFFFF else value

    def nullable_lap_time(value: int) -> int | None:
        return None if value == 0xFFFFFFFF else value

    gear_bits = u8(0x90)
    suggested_gear = gear_bits >> 4
    current_gear = gear_bits & 0x0F
    if suggested_gear == 0x0F:
        suggested_gear = None
    if current_gear == 0x0F:
        current_gear = None

    return GT7Packet(
        packet_id=u32(0x70),
        received_at=utc_now(),
        current_lap=nullable_u16(u16(0x74)),
        total_laps=nullable_u16(u16(0x76)),
        best_lap_time_ms=nullable_lap_time(u32(0x78)),
        last_lap_time_ms=nullable_lap_time(u32(0x7C)),
        position_x=f32(0x04),
        position_y=f32(0x08),
        position_z=f32(0x0C),
        speed_mps=f32(0x4C),
        engine_rpm=f32(0x3C),
        fuel_level=f32(0x44),
        fuel_capacity=f32(0x48),
        throttle_raw=u8(0x91),
        brake_raw=u8(0x92),
        current_gear=current_gear,
        suggested_gear=suggested_gear,
        flags=u16(0x8E),
    )


def make_fake_plain_packet(
    lap: int = 3,
    best_lap_ms: int = 502111,
    last_lap_ms: int = 505222,
    speed_mps: float = 67.0,
    fuel_liters: float = 41.5,
) -> bytes:
    packet = bytearray(GT7_PACKET_SIZE)
    packet[:4] = b"0S7G"
    struct.pack_into("<f", packet, 0x04, 123.4)
    struct.pack_into("<f", packet, 0x08, 20.5)
    struct.pack_into("<f", packet, 0x0C, -884.1)
    struct.pack_into("<f", packet, 0x3C, 7420.0)
    struct.pack_into("<I", packet, 0x40, 0x12345678)
    struct.pack_into("<f", packet, 0x44, fuel_liters)
    struct.pack_into("<f", packet, 0x48, 100.0)
    struct.pack_into("<f", packet, 0x4C, speed_mps)
    struct.pack_into("<I", packet, 0x70, 42)
    struct.pack_into("<H", packet, 0x74, lap)
    struct.pack_into("<H", packet, 0x76, 50)
    struct.pack_into("<I", packet, 0x78, best_lap_ms)
    struct.pack_into("<I", packet, 0x7C, last_lap_ms)
    struct.pack_into("<H", packet, 0x8E, 1)
    packet[0x90] = 6
    packet[0x91] = 220
    packet[0x92] = 12
    return bytes(packet)


class GT7UdpReceiver:
    def __init__(
        self,
        playstation_ip: str,
        heartbeat_type: str = "A",
        bind_port: int = GT7_RECEIVE_PORT,
        heartbeat_port: int = GT7_HEARTBEAT_PORT,
        socket_timeout_seconds: float = 2.0,
    ) -> None:
        self.playstation_ip = playstation_ip
        self.heartbeat_type = heartbeat_type
        self.bind_port = bind_port
        self.heartbeat_port = heartbeat_port
        self.socket_timeout_seconds = socket_timeout_seconds
        self._sock: socket.socket | None = None
        self._last_heartbeat = 0.0

    def __enter__(self) -> GT7UdpReceiver:
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def open(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(self.socket_timeout_seconds)
        try:
            sock.bind(("", self.bind_port))
        except OSError as error:
            sock.close()
            raise GT7TelemetryError(
                f"Could not listen on UDP port {self.bind_port}. "
                "Close other GT7 telemetry apps like SimHub/GT7Proxy or change the receive port."
            ) from error
        self._sock = sock
        self.send_heartbeat(force=True)

    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None

    def send_heartbeat(self, force: bool = False) -> None:
        if not self._sock:
            raise GT7TelemetryError("GT7 receiver is not open")
        now = time.monotonic()
        if not force and now - self._last_heartbeat < GT7_HEARTBEAT_INTERVAL_SECONDS:
            return
        self._sock.sendto(self.heartbeat_type.encode("ascii"), (self.playstation_ip, self.heartbeat_port))
        self._last_heartbeat = now

    def receive_packet(self) -> GT7Packet:
        if not self._sock:
            raise GT7TelemetryError("GT7 receiver is not open")
        while True:
            self.send_heartbeat()
            try:
                encrypted, _ = self._sock.recvfrom(4096)
            except socket.timeout as error:
                raise GT7TelemetryError(
                    "GT7 was not found. Please check that GT7 is running, the PlayStation and PC are in the same network, "
                    "and the PlayStation IP address is correct."
                ) from error
            plain = decrypt_gt7_packet(encrypted, self.heartbeat_type)
            try:
                return parse_gt7_packet(plain)
            except GT7PacketError:
                continue


def estimate_lap_progress(packet: GT7Packet) -> float:
    # Until track reference laps exist, expose only a stable neutral progress value.
    # The server can still rank primarily by completed lap.
    if packet.last_lap_time_ms and packet.last_lap_time_ms > 0:
        return 0.0
    return 0.0


def speed_is_plausible(packet: GT7Packet) -> bool:
    return math.isfinite(packet.speed_kmh) and 0 <= packet.speed_kmh <= 650
