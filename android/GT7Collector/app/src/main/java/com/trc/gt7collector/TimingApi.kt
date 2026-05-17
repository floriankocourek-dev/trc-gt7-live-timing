package com.trc.gt7collector

import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class TimingApi {
    fun fetchEntries(serverUrl: String, raceCode: String): CollectorRaceResponse {
        val code = encode(raceCode.trim().uppercase())
        val json = request("GET", "$serverUrl/api/collector/races/$code/entries")
        val race = json.getJSONObject("race")
        val entriesJson = json.getJSONArray("entries")
        val entries = (0 until entriesJson.length()).map { index ->
            val entry = entriesJson.getJSONObject(index)
            val driversJson = entry.getJSONArray("drivers")
            EntryInfo(
                entryId = entry.getString("entry_id"),
                carNumber = entry.getInt("car_number"),
                teamName = entry.getString("team_name"),
                carModel = entry.getString("car_model"),
                carClass = entry.getString("class"),
                drivers = (0 until driversJson.length()).map { driverIndex ->
                    val driver = driversJson.getJSONObject(driverIndex)
                    DriverInfo(
                        driverId = driver.getString("driver_id"),
                        displayName = driver.getString("display_name")
                    )
                }
            )
        }
        return CollectorRaceResponse(
            raceId = race.getString("race_id"),
            raceName = race.getString("name"),
            entries = entries
        )
    }

    fun register(
        serverUrl: String,
        raceCode: String,
        entryId: String,
        teamCode: String,
        driverId: String
    ): String {
        val body = JSONObject().apply {
            put("race_code", raceCode.trim().uppercase())
            put("entry_id", entryId)
            put("team_code", teamCode)
            put("driver_id", driverId)
            put("collector_version", "android-0.1.0")
        }
        val response = request("POST", "$serverUrl/api/collector/register", body)
        if (!response.optBoolean("send_allowed", false)) {
            throw TimingApiException("Race Control does not allow this collector to send data.")
        }
        return response.getString("collector_token")
    }

    fun sendTelemetry(serverUrl: String, token: String, payload: TelemetryPayload) {
        request(
            method = "POST",
            urlText = "$serverUrl/api/collector/telemetry",
            body = payload.toJson(),
            token = token
        )
    }

    private fun request(
        method: String,
        urlText: String,
        body: JSONObject? = null,
        token: String? = null
    ): JSONObject {
        val url = URL(urlText)
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 8000
            readTimeout = 12000
            setRequestProperty("Accept", "application/json")
            if (token != null) {
                setRequestProperty("Authorization", "Bearer $token")
            }
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
            }
        }

        if (body != null) {
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use {
                it.write(body.toString())
            }
        }

        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) {
            val detail = runCatching { JSONObject(text).optString("detail") }.getOrNull()
            throw TimingApiException(detail?.takeIf { it.isNotBlank() } ?: "Timing server rejected the request ($status).")
        }
        return if (text.isBlank()) JSONObject() else JSONObject(text)
    }

    private fun encode(value: String): String =
        URLEncoder.encode(value, Charsets.UTF_8.name())
}

class TimingApiException(message: String) : RuntimeException(message)
