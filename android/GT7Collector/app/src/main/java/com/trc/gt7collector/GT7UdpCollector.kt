package com.trc.gt7collector

import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import java.util.concurrent.atomic.AtomicBoolean

class GT7UdpCollector(
    private val playStationIp: String,
    private val heartbeatType: String = "A",
    private val updateHz: Double = 1.0,
    private val onPayload: (TelemetryPayload) -> Unit,
    private val onStatus: (String) -> Unit,
    private val onError: (String) -> Unit
) {
    private val running = AtomicBoolean(false)
    private var worker: Thread? = null

    fun start() {
        if (!running.compareAndSet(false, true)) return
        worker = Thread {
            var socket: DatagramSocket? = null
            try {
                val target = InetAddress.getByName(playStationIp.trim())
                socket = DatagramSocket(null).apply {
                    reuseAddress = true
                    bind(InetSocketAddress(33740))
                    soTimeout = 1000
                }
                onStatus("OK")
                val heartbeat = heartbeatType.toByteArray(Charsets.US_ASCII)
                var lastHeartbeat = 0L
                var lastPayload = 0L
                val minPayloadIntervalMs = (1000.0 / updateHz.coerceAtLeast(0.2)).toLong()
                val buffer = ByteArray(2048)

                while (running.get()) {
                    val now = System.currentTimeMillis()
                    if (now - lastHeartbeat >= 10_000L) {
                        val packet = DatagramPacket(heartbeat, heartbeat.size, target, 33739)
                        socket.send(packet)
                        lastHeartbeat = now
                    }

                    try {
                        val packet = DatagramPacket(buffer, buffer.size)
                        socket.receive(packet)
                        if (System.currentTimeMillis() - lastPayload >= minPayloadIntervalMs) {
                            val raw = packet.data.copyOf(packet.length)
                            val decrypted = GT7Packet.decrypt(raw, heartbeatType)
                            val telemetry = GT7Packet.parse(decrypted).payload()
                            lastPayload = System.currentTimeMillis()
                            onStatus("OK")
                            onPayload(telemetry)
                        }
                    } catch (_: SocketTimeoutException) {
                        // Keep the heartbeat alive while waiting for GT7 to send telemetry.
                    }
                }
            } catch (error: Exception) {
                if (running.get()) {
                    onStatus("not connected")
                    onError(friendly(error))
                }
            } finally {
                socket?.close()
            }
        }.apply {
            name = "GT7UdpCollector"
            start()
        }
    }

    fun stop() {
        running.set(false)
        worker?.interrupt()
        worker = null
    }

    private fun friendly(error: Exception): String =
        if (error.message?.contains("Address already in use", ignoreCase = true) == true) {
            "GT7 telemetry port is already in use. Please close other GT7 telemetry apps on this phone."
        } else {
            "GT7 was not found. Please check that GT7 is running and your phone and PlayStation are in the same network."
        }
}
