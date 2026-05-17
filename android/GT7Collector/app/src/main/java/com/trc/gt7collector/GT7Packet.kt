package com.trc.gt7collector

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import kotlin.math.max
import kotlin.math.min

class GT7PacketException(message: String) : RuntimeException(message)

data class GT7Packet(
    val packetId: Long,
    val receivedAt: String,
    val currentLap: Int,
    val totalLaps: Int?,
    val bestLapTimeMs: Int?,
    val lastLapTimeMs: Int?,
    val positionX: Double,
    val positionY: Double,
    val positionZ: Double,
    val speedMps: Double,
    val velocityX: Double,
    val velocityY: Double,
    val velocityZ: Double,
    val rotationPitch: Double,
    val rotationYaw: Double,
    val rotationRoll: Double,
    val angularVelocityX: Double,
    val angularVelocityY: Double,
    val angularVelocityZ: Double,
    val rideHeight: Double,
    val engineRpm: Double,
    val oilPressure: Double,
    val waterTemp: Double,
    val oilTemp: Double,
    val fuelLevel: Double,
    val fuelCapacity: Double,
    val tireTempFl: Double,
    val tireTempFr: Double,
    val tireTempRl: Double,
    val tireTempRr: Double,
    val throttleRaw: Int,
    val brakeRaw: Int,
    val currentGear: Int?,
    val suggestedGear: Int?,
    val rpmRevWarning: Int,
    val rpmRevLimiter: Int,
    val estimatedTopSpeed: Int,
    val clutch: Double,
    val clutchEngaged: Double,
    val rpmAfterClutch: Double,
    val tireSpeedFl: Double,
    val tireSpeedFr: Double,
    val tireSpeedRl: Double,
    val tireSpeedRr: Double,
    val tireSlipFl: Double,
    val tireSlipFr: Double,
    val tireSlipRl: Double,
    val tireSlipRr: Double,
    val tireDiameterFl: Double,
    val tireDiameterFr: Double,
    val tireDiameterRl: Double,
    val tireDiameterRr: Double,
    val suspensionFl: Double,
    val suspensionFr: Double,
    val suspensionRl: Double,
    val suspensionRr: Double,
    val gearRatios: List<Double>,
    val carId: Int,
    val flags: Int
) {
    val speedKmh: Double get() = speedMps * 3.6
    val throttlePercent: Double get() = max(0.0, min(100.0, throttleRaw / 255.0 * 100.0))
    val brakePercent: Double get() = max(0.0, min(100.0, brakeRaw / 255.0 * 100.0))

    val telemetryStatus: String
        get() = when {
            flags and (1 shl 2) != 0 -> "loading"
            flags and (1 shl 1) != 0 -> "paused"
            flags and 1 == 0 -> "not_on_track"
            else -> "valid"
        }

    fun payload(): TelemetryPayload = TelemetryPayload(
        timestamp = receivedAt,
        lap = currentLap,
        lapProgress = 0.0,
        lastLapMs = lastLapTimeMs,
        bestLapMs = bestLapTimeMs,
        speedKmh = speedKmh,
        fuelLiters = fuelLevel,
        gear = currentGear ?: 0,
        rpm = engineRpm.toInt(),
        throttle = throttlePercent,
        brake = brakePercent,
        positionX = positionX,
        positionY = positionY,
        positionZ = positionZ,
        tireTempFl = tireTempFl,
        tireTempFr = tireTempFr,
        tireTempRl = tireTempRl,
        tireTempRr = tireTempRr,
        gt7Telemetry = privateTelemetry(),
        telemetryStatus = telemetryStatus
    )

    private fun privateTelemetry(): JSONObject = JSONObject().apply {
        put("packet_id", packetId)
        putNullable("total_laps", totalLaps)
        put("speed_mps", speedMps)
        put("speed_kmh", speedKmh)
        put("velocity_x", velocityX)
        put("velocity_y", velocityY)
        put("velocity_z", velocityZ)
        put("rotation_pitch", rotationPitch)
        put("rotation_yaw", rotationYaw)
        put("rotation_roll", rotationRoll)
        put("angular_velocity_x", angularVelocityX)
        put("angular_velocity_y", angularVelocityY)
        put("angular_velocity_z", angularVelocityZ)
        put("ride_height", rideHeight)
        put("engine_rpm", engineRpm)
        put("rpm_rev_warning", rpmRevWarning)
        put("rpm_rev_limiter", rpmRevLimiter)
        put("estimated_top_speed", estimatedTopSpeed)
        put("oil_pressure", oilPressure)
        put("water_temp", waterTemp)
        put("oil_temp", oilTemp)
        put("fuel_capacity", fuelCapacity)
        putNullable("current_gear", currentGear)
        putNullable("suggested_gear", suggestedGear)
        put("clutch", clutch)
        put("clutch_engaged", clutchEngaged)
        put("rpm_after_clutch", rpmAfterClutch)
        put("tire_speed_fl", tireSpeedFl)
        put("tire_speed_fr", tireSpeedFr)
        put("tire_speed_rl", tireSpeedRl)
        put("tire_speed_rr", tireSpeedRr)
        put("tire_slip_fl", tireSlipFl)
        put("tire_slip_fr", tireSlipFr)
        put("tire_slip_rl", tireSlipRl)
        put("tire_slip_rr", tireSlipRr)
        put("tire_diameter_fl", tireDiameterFl)
        put("tire_diameter_fr", tireDiameterFr)
        put("tire_diameter_rl", tireDiameterRl)
        put("tire_diameter_rr", tireDiameterRr)
        put("suspension_fl", suspensionFl)
        put("suspension_fr", suspensionFr)
        put("suspension_rl", suspensionRl)
        put("suspension_rr", suspensionRr)
        put("gear_ratios", JSONArray(gearRatios))
        put("car_id", carId)
        put("flags", flags)
        put("telemetry_status", telemetryStatus)
    }

    companion object {
        private const val PACKET_SIZE = 0x128
        private val key = "Simulator Interface Packet GT7 ver 0.0"
            .toByteArray(Charsets.US_ASCII)
            .copyOfRange(0, 32)
        private val masks = mapOf(
            "A" to 0xDEADBEAFu,
            "B" to 0xDEADBEEFu,
            "~" to 0x55FABB4Fu
        )

        fun decrypt(data: ByteArray, heartbeatType: String = "A"): ByteArray {
            val mask = masks[heartbeatType] ?: throw GT7PacketException("Unsupported GT7 heartbeat type.")
            if (data.size < 0x44) throw GT7PacketException("Telemetry packet is too short.")
            val seed = data.u32(0x40)
            val iv = seed xor mask
            val nonce = ByteArray(8)
            nonce.writeU32(0, iv)
            nonce.writeU32(4, seed)
            return Salsa20.decrypt(data, key, nonce)
        }

        fun parse(data: ByteArray): GT7Packet {
            if (data.size < PACKET_SIZE) throw GT7PacketException("Telemetry packet is too short.")
            val header = data.copyOfRange(0, 4).toString(Charsets.US_ASCII)
            if (header != "0S7G" && header != "G7S0") {
                throw GT7PacketException("GT7 packet header is invalid.")
            }
            val gearBits = data.u8(0x90)
            val suggested = gearBits ushr 4
            val current = gearBits and 0x0f

            return GT7Packet(
                packetId = data.u32(0x70).toLong() and 0xffff_ffffL,
                receivedAt = Instant.now().toString(),
                currentLap = data.nullableU16(0x74) ?: 0,
                totalLaps = data.nullableU16(0x76),
                bestLapTimeMs = data.nullableLapTime(0x78),
                lastLapTimeMs = data.nullableLapTime(0x7c),
                positionX = data.f32(0x04),
                positionY = data.f32(0x08),
                positionZ = data.f32(0x0c),
                speedMps = data.f32(0x4c),
                velocityX = data.f32(0x10),
                velocityY = data.f32(0x14),
                velocityZ = data.f32(0x18),
                rotationPitch = data.f32(0x1c),
                rotationYaw = data.f32(0x20),
                rotationRoll = data.f32(0x24),
                angularVelocityX = data.f32(0x2c),
                angularVelocityY = data.f32(0x30),
                angularVelocityZ = data.f32(0x34),
                rideHeight = data.f32(0x38),
                engineRpm = data.f32(0x3c),
                oilPressure = data.f32(0x54),
                waterTemp = data.f32(0x58),
                oilTemp = data.f32(0x5c),
                fuelLevel = data.f32(0x44),
                fuelCapacity = data.f32(0x48),
                tireTempFl = data.f32(0x60),
                tireTempFr = data.f32(0x64),
                tireTempRl = data.f32(0x68),
                tireTempRr = data.f32(0x6c),
                throttleRaw = data.u8(0x91),
                brakeRaw = data.u8(0x92),
                currentGear = if (current == 0x0f) null else current,
                suggestedGear = if (suggested == 0x0f) null else suggested,
                rpmRevWarning = data.u16(0x88),
                rpmRevLimiter = data.u16(0x8a),
                estimatedTopSpeed = data.u16(0x8c),
                clutch = data.f32(0xf4),
                clutchEngaged = data.f32(0xf8),
                rpmAfterClutch = data.f32(0xfc),
                tireSpeedFl = data.f32(0xa4),
                tireSpeedFr = data.f32(0xa8),
                tireSpeedRl = data.f32(0xac),
                tireSpeedRr = data.f32(0xb0),
                tireSlipFl = data.f32(0xb4),
                tireSlipFr = data.f32(0xb8),
                tireSlipRl = data.f32(0xbc),
                tireSlipRr = data.f32(0xc0),
                tireDiameterFl = data.f32(0xc4),
                tireDiameterFr = data.f32(0xc8),
                tireDiameterRl = data.f32(0xcc),
                tireDiameterRr = data.f32(0xd0),
                suspensionFl = data.f32(0xd4),
                suspensionFr = data.f32(0xd8),
                suspensionRl = data.f32(0xdc),
                suspensionRr = data.f32(0xe0),
                gearRatios = (0x104 until 0x124 step 4).map { data.f32(it) },
                carId = data.i32(0x124),
                flags = data.u16(0x8e)
            )
        }
    }
}

private fun ByteArray.u8(offset: Int): Int = this[offset].toInt() and 0xff

private fun ByteArray.u16(offset: Int): Int =
    u8(offset) or (u8(offset + 1) shl 8)

private fun ByteArray.u32(offset: Int): UInt =
    (u8(offset).toUInt()) or
        (u8(offset + 1).toUInt() shl 8) or
        (u8(offset + 2).toUInt() shl 16) or
        (u8(offset + 3).toUInt() shl 24)

private fun ByteArray.i32(offset: Int): Int =
    u32(offset).toInt()

private fun ByteArray.f32(offset: Int): Double =
    Float.fromBits(i32(offset)).toDouble()

private fun ByteArray.nullableU16(offset: Int): Int? {
    val value = u16(offset)
    return if (value == 0xffff) null else value
}

private fun ByteArray.nullableLapTime(offset: Int): Int? {
    val value = u32(offset)
    return if (value == 0xffff_ffffu) null else value.toInt()
}

private fun ByteArray.writeU32(offset: Int, value: UInt) {
    this[offset] = (value and 0xffu).toByte()
    this[offset + 1] = ((value shr 8) and 0xffu).toByte()
    this[offset + 2] = ((value shr 16) and 0xffu).toByte()
    this[offset + 3] = ((value shr 24) and 0xffu).toByte()
}
