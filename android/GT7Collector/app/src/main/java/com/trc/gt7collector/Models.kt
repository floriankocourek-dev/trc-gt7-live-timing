package com.trc.gt7collector

import org.json.JSONArray
import org.json.JSONObject

const val DEFAULT_SERVER_URL = "https://trc-gt7-live-timing.onrender.com"

data class DriverInfo(
    val driverId: String,
    val displayName: String
)

data class EntryInfo(
    val entryId: String,
    val carNumber: Int,
    val teamName: String,
    val carModel: String,
    val carClass: String,
    val drivers: List<DriverInfo>
) {
    val label: String get() = "#$carNumber - $teamName - $carModel"
}

data class CollectorRaceResponse(
    val raceId: String,
    val raceName: String,
    val entries: List<EntryInfo>
)

data class TelemetryPayload(
    val timestamp: String,
    val lap: Int,
    val lapProgress: Double,
    val lastLapMs: Int?,
    val bestLapMs: Int?,
    val speedKmh: Double,
    val fuelLiters: Double,
    val gear: Int,
    val rpm: Int,
    val throttle: Double,
    val brake: Double,
    val positionX: Double,
    val positionY: Double,
    val positionZ: Double,
    val tireTempFl: Double?,
    val tireTempFr: Double?,
    val tireTempRl: Double?,
    val tireTempRr: Double?,
    val gt7Telemetry: JSONObject?,
    val telemetryStatus: String
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("timestamp", timestamp)
        put("lap", lap)
        put("lap_progress", lapProgress)
        putNullable("last_lap_ms", lastLapMs)
        putNullable("best_lap_ms", bestLapMs)
        put("speed_kmh", speedKmh)
        put("fuel_liters", fuelLiters)
        put("gear", gear)
        put("rpm", rpm)
        put("throttle", throttle)
        put("brake", brake)
        put("position_x", positionX)
        put("position_y", positionY)
        put("position_z", positionZ)
        putNullable("tire_compound", null)
        putNullable("tire_temp_fl", tireTempFl)
        putNullable("tire_temp_fr", tireTempFr)
        putNullable("tire_temp_rl", tireTempRl)
        putNullable("tire_temp_rr", tireTempRr)
        putNullable("gt7_telemetry", gt7Telemetry)
        put("telemetry_status", telemetryStatus)
    }
}

fun JSONObject.putNullable(name: String, value: Any?) {
    put(name, value ?: JSONObject.NULL)
}

fun JSONArray.toStringList(): List<String> =
    (0 until length()).map { getString(it) }
