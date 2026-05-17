import Foundation

let defaultServerURL = "https://trc-gt7-live-timing.onrender.com"

struct RaceInfo: Codable, Hashable {
    let raceId: String
    let name: String
    let trackId: String?
    let eventType: String
    let driversPerTeam: Int
    let status: String

    enum CodingKeys: String, CodingKey {
        case raceId = "race_id"
        case name
        case trackId = "track_id"
        case eventType = "event_type"
        case driversPerTeam = "drivers_per_team"
        case status
    }
}

struct DriverInfo: Codable, Hashable, Identifiable {
    let driverId: String
    let displayName: String

    var id: String { driverId }

    enum CodingKeys: String, CodingKey {
        case driverId = "driver_id"
        case displayName = "display_name"
    }
}

struct EntryInfo: Codable, Hashable, Identifiable {
    let entryId: String
    let carNumber: Int
    let teamName: String
    let carModel: String
    let carClass: String
    let drivers: [DriverInfo]

    var id: String { entryId }
    var label: String { "#\(carNumber) - \(teamName) - \(carModel)" }

    enum CodingKeys: String, CodingKey {
        case entryId = "entry_id"
        case carNumber = "car_number"
        case teamName = "team_name"
        case carModel = "car_model"
        case carClass = "class"
        case drivers
    }
}

struct CollectorRaceResponse: Codable {
    let race: RaceInfo
    let entries: [EntryInfo]
}

struct CollectorRegisterRequest: Encodable {
    let raceCode: String
    let entryId: String
    let teamCode: String
    let driverId: String
    let collectorVersion: String

    enum CodingKeys: String, CodingKey {
        case raceCode = "race_code"
        case entryId = "entry_id"
        case teamCode = "team_code"
        case driverId = "driver_id"
        case collectorVersion = "collector_version"
    }
}

struct CollectorRegisterResponse: Decodable {
    let collectorToken: String
    let entryId: String
    let collectorId: String
    let sendAllowed: Bool

    enum CodingKeys: String, CodingKey {
        case collectorToken = "collector_token"
        case entryId = "entry_id"
        case collectorId = "collector_id"
        case sendAllowed = "send_allowed"
    }
}

struct TelemetryPayload: Encodable {
    let timestamp: String
    let lap: Int
    let lapProgress: Double
    let lastLapMs: Int?
    let bestLapMs: Int?
    let speedKmh: Double
    let fuelLiters: Double
    let gear: Int
    let rpm: Int
    let throttle: Double
    let brake: Double
    let positionX: Double
    let positionY: Double
    let positionZ: Double
    let tireCompound: String?
    let tireTempFl: Double?
    let tireTempFr: Double?
    let tireTempRl: Double?
    let tireTempRr: Double?
    let gt7Telemetry: [String: JSONValue]?
    let telemetryStatus: String

    enum CodingKeys: String, CodingKey {
        case timestamp
        case lap
        case lapProgress = "lap_progress"
        case lastLapMs = "last_lap_ms"
        case bestLapMs = "best_lap_ms"
        case speedKmh = "speed_kmh"
        case fuelLiters = "fuel_liters"
        case gear
        case rpm
        case throttle
        case brake
        case positionX = "position_x"
        case positionY = "position_y"
        case positionZ = "position_z"
        case tireCompound = "tire_compound"
        case tireTempFl = "tire_temp_fl"
        case tireTempFr = "tire_temp_fr"
        case tireTempRl = "tire_temp_rl"
        case tireTempRr = "tire_temp_rr"
        case gt7Telemetry = "gt7_telemetry"
        case telemetryStatus = "telemetry_status"
    }
}

enum JSONValue: Encodable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case null
    case array([JSONValue])

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .int(let value):
            try container.encode(value)
        case .double(let value):
            try container.encode(value)
        case .bool(let value):
            try container.encode(value)
        case .null:
            try container.encodeNil()
        case .array(let values):
            try container.encode(values)
        }
    }
}
