import Foundation

enum GT7PacketError: LocalizedError {
    case packetTooShort
    case invalidHeader
    case unsupportedHeartbeat

    var errorDescription: String? {
        switch self {
        case .packetTooShort:
            return "GT7 packet is too short."
        case .invalidHeader:
            return "GT7 packet header is invalid."
        case .unsupportedHeartbeat:
            return "GT7 heartbeat type is not supported."
        }
    }
}

struct GT7Packet {
    static let packetSize = 0x128
    static let key = Array("Simulator Interface Packet GT7 ver 0.0".utf8.prefix(32))
    static let ivMasks: [String: UInt32] = [
        "A": 0xDEADBEAF,
        "B": 0xDEADBEEF,
        "~": 0x55FABB4F
    ]

    let packetId: UInt32
    let receivedAt: String
    let currentLap: Int
    let totalLaps: Int?
    let bestLapTimeMs: Int?
    let lastLapTimeMs: Int?
    let positionX: Double
    let positionY: Double
    let positionZ: Double
    let speedMps: Double
    let velocityX: Double
    let velocityY: Double
    let velocityZ: Double
    let rotationPitch: Double
    let rotationYaw: Double
    let rotationRoll: Double
    let angularVelocityX: Double
    let angularVelocityY: Double
    let angularVelocityZ: Double
    let rideHeight: Double
    let engineRpm: Double
    let oilPressure: Double
    let waterTemp: Double
    let oilTemp: Double
    let fuelLevel: Double
    let fuelCapacity: Double
    let tireTempFl: Double
    let tireTempFr: Double
    let tireTempRl: Double
    let tireTempRr: Double
    let throttleRaw: UInt8
    let brakeRaw: UInt8
    let currentGear: Int?
    let suggestedGear: Int?
    let rpmRevWarning: Int
    let rpmRevLimiter: Int
    let estimatedTopSpeed: Int
    let clutch: Double
    let clutchEngaged: Double
    let rpmAfterClutch: Double
    let tireSpeedFl: Double
    let tireSpeedFr: Double
    let tireSpeedRl: Double
    let tireSpeedRr: Double
    let tireSlipFl: Double
    let tireSlipFr: Double
    let tireSlipRl: Double
    let tireSlipRr: Double
    let tireDiameterFl: Double
    let tireDiameterFr: Double
    let tireDiameterRl: Double
    let tireDiameterRr: Double
    let suspensionFl: Double
    let suspensionFr: Double
    let suspensionRl: Double
    let suspensionRr: Double
    let gearRatios: [Double]
    let carId: Int
    let flags: UInt16

    var speedKmh: Double { speedMps * 3.6 }
    var throttlePercent: Double { max(0, min(100, Double(throttleRaw) / 255 * 100)) }
    var brakePercent: Double { max(0, min(100, Double(brakeRaw) / 255 * 100)) }

    var telemetryStatus: String {
        if flags & (1 << 2) != 0 { return "loading" }
        if flags & (1 << 1) != 0 { return "paused" }
        if flags & 1 == 0 { return "not_on_track" }
        return "valid"
    }

    static func decrypt(_ data: Data, heartbeatType: String) throws -> Data {
        guard let mask = ivMasks[heartbeatType] else { throw GT7PacketError.unsupportedHeartbeat }
        guard data.count >= 0x44 else { throw GT7PacketError.packetTooShort }
        let seed = data.u32(0x40)
        let iv = seed ^ mask
        let nonce = Data.u32Bytes(iv) + Data.u32Bytes(seed)
        return Salsa20.decrypt(data, key: key, nonce: nonce)
    }

    static func parse(_ data: Data) throws -> GT7Packet {
        guard data.count >= packetSize else { throw GT7PacketError.packetTooShort }
        guard let header = String(data: data.subdata(in: 0..<4), encoding: .ascii),
              header == "0S7G" || header == "G7S0" else {
            throw GT7PacketError.invalidHeader
        }

        let gearBits = data.u8(0x90)
        let suggested = gearBits >> 4
        let current = gearBits & 0x0F

        return GT7Packet(
            packetId: data.u32(0x70),
            receivedAt: ISO8601DateFormatter().string(from: Date()),
            currentLap: data.nullableU16(0x74) ?? 0,
            totalLaps: data.nullableU16(0x76),
            bestLapTimeMs: data.nullableLapTime(0x78),
            lastLapTimeMs: data.nullableLapTime(0x7C),
            positionX: data.f32(0x04),
            positionY: data.f32(0x08),
            positionZ: data.f32(0x0C),
            speedMps: data.f32(0x4C),
            velocityX: data.f32(0x10),
            velocityY: data.f32(0x14),
            velocityZ: data.f32(0x18),
            rotationPitch: data.f32(0x1C),
            rotationYaw: data.f32(0x20),
            rotationRoll: data.f32(0x24),
            angularVelocityX: data.f32(0x2C),
            angularVelocityY: data.f32(0x30),
            angularVelocityZ: data.f32(0x34),
            rideHeight: data.f32(0x38),
            engineRpm: data.f32(0x3C),
            oilPressure: data.f32(0x54),
            waterTemp: data.f32(0x58),
            oilTemp: data.f32(0x5C),
            fuelLevel: data.f32(0x44),
            fuelCapacity: data.f32(0x48),
            tireTempFl: data.f32(0x60),
            tireTempFr: data.f32(0x64),
            tireTempRl: data.f32(0x68),
            tireTempRr: data.f32(0x6C),
            throttleRaw: data.u8(0x91),
            brakeRaw: data.u8(0x92),
            currentGear: current == 0x0F ? nil : Int(current),
            suggestedGear: suggested == 0x0F ? nil : Int(suggested),
            rpmRevWarning: Int(data.u16(0x88)),
            rpmRevLimiter: Int(data.u16(0x8A)),
            estimatedTopSpeed: Int(data.u16(0x8C)),
            clutch: data.f32(0xF4),
            clutchEngaged: data.f32(0xF8),
            rpmAfterClutch: data.f32(0xFC),
            tireSpeedFl: data.f32(0xA4),
            tireSpeedFr: data.f32(0xA8),
            tireSpeedRl: data.f32(0xAC),
            tireSpeedRr: data.f32(0xB0),
            tireSlipFl: data.f32(0xB4),
            tireSlipFr: data.f32(0xB8),
            tireSlipRl: data.f32(0xBC),
            tireSlipRr: data.f32(0xC0),
            tireDiameterFl: data.f32(0xC4),
            tireDiameterFr: data.f32(0xC8),
            tireDiameterRl: data.f32(0xCC),
            tireDiameterRr: data.f32(0xD0),
            suspensionFl: data.f32(0xD4),
            suspensionFr: data.f32(0xD8),
            suspensionRl: data.f32(0xDC),
            suspensionRr: data.f32(0xE0),
            gearRatios: stride(from: 0x104, to: 0x124, by: 4).map { data.f32($0) },
            carId: Int(data.i32(0x124)),
            flags: data.u16(0x8E)
        )
    }

    func payload() -> TelemetryPayload {
        TelemetryPayload(
            timestamp: receivedAt,
            lap: currentLap,
            lapProgress: 0,
            lastLapMs: lastLapTimeMs,
            bestLapMs: bestLapTimeMs,
            speedKmh: speedKmh,
            fuelLiters: fuelLevel,
            gear: currentGear ?? 0,
            rpm: Int(engineRpm),
            throttle: throttlePercent,
            brake: brakePercent,
            positionX: positionX,
            positionY: positionY,
            positionZ: positionZ,
            tireCompound: nil,
            tireTempFl: tireTempFl,
            tireTempFr: tireTempFr,
            tireTempRl: tireTempRl,
            tireTempRr: tireTempRr,
            gt7Telemetry: privateTelemetry(),
            telemetryStatus: telemetryStatus
        )
    }

    private func privateTelemetry() -> [String: JSONValue] {
        [
            "packet_id": .int(Int(packetId)),
            "total_laps": totalLaps.map(JSONValue.int) ?? .null,
            "speed_mps": .double(speedMps),
            "speed_kmh": .double(speedKmh),
            "velocity_x": .double(velocityX),
            "velocity_y": .double(velocityY),
            "velocity_z": .double(velocityZ),
            "rotation_pitch": .double(rotationPitch),
            "rotation_yaw": .double(rotationYaw),
            "rotation_roll": .double(rotationRoll),
            "angular_velocity_x": .double(angularVelocityX),
            "angular_velocity_y": .double(angularVelocityY),
            "angular_velocity_z": .double(angularVelocityZ),
            "ride_height": .double(rideHeight),
            "engine_rpm": .double(engineRpm),
            "rpm_rev_warning": .int(rpmRevWarning),
            "rpm_rev_limiter": .int(rpmRevLimiter),
            "estimated_top_speed": .int(estimatedTopSpeed),
            "oil_pressure": .double(oilPressure),
            "water_temp": .double(waterTemp),
            "oil_temp": .double(oilTemp),
            "fuel_capacity": .double(fuelCapacity),
            "current_gear": currentGear.map(JSONValue.int) ?? .null,
            "suggested_gear": suggestedGear.map(JSONValue.int) ?? .null,
            "clutch": .double(clutch),
            "clutch_engaged": .double(clutchEngaged),
            "rpm_after_clutch": .double(rpmAfterClutch),
            "tire_speed_fl": .double(tireSpeedFl),
            "tire_speed_fr": .double(tireSpeedFr),
            "tire_speed_rl": .double(tireSpeedRl),
            "tire_speed_rr": .double(tireSpeedRr),
            "tire_slip_fl": .double(tireSlipFl),
            "tire_slip_fr": .double(tireSlipFr),
            "tire_slip_rl": .double(tireSlipRl),
            "tire_slip_rr": .double(tireSlipRr),
            "tire_diameter_fl": .double(tireDiameterFl),
            "tire_diameter_fr": .double(tireDiameterFr),
            "tire_diameter_rl": .double(tireDiameterRl),
            "tire_diameter_rr": .double(tireDiameterRr),
            "suspension_fl": .double(suspensionFl),
            "suspension_fr": .double(suspensionFr),
            "suspension_rl": .double(suspensionRl),
            "suspension_rr": .double(suspensionRr),
            "gear_ratios": .array(gearRatios.map(JSONValue.double)),
            "car_id": .int(carId),
            "flags": .int(Int(flags)),
            "telemetry_status": .string(telemetryStatus)
        ]
    }
}

private extension Data {
    func u8(_ offset: Int) -> UInt8 {
        self[offset]
    }

    func u16(_ offset: Int) -> UInt16 {
        UInt16(self[offset]) | UInt16(self[offset + 1]) << 8
    }

    func u32(_ offset: Int) -> UInt32 {
        UInt32(self[offset])
            | UInt32(self[offset + 1]) << 8
            | UInt32(self[offset + 2]) << 16
            | UInt32(self[offset + 3]) << 24
    }

    func i32(_ offset: Int) -> Int32 {
        Int32(bitPattern: u32(offset))
    }

    func f32(_ offset: Int) -> Double {
        let raw = u32(offset)
        return Double(Float(bitPattern: raw))
    }

    func nullableU16(_ offset: Int) -> Int? {
        let value = u16(offset)
        return value == 0xffff ? nil : Int(value)
    }

    func nullableLapTime(_ offset: Int) -> Int? {
        let value = u32(offset)
        return value == 0xffff_ffff ? nil : Int(value)
    }

    static func u32Bytes(_ value: UInt32) -> [UInt8] {
        [
            UInt8(value & 0xff),
            UInt8((value >> 8) & 0xff),
            UInt8((value >> 16) & 0xff),
            UInt8((value >> 24) & 0xff)
        ]
    }
}
