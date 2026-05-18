package com.trc.gt7collector

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager

class CollectorService : Service() {
    private val api = TimingApi()
    private var udpCollector: GT7UdpCollector? = null
    private var worker: Thread? = null
    private var collectorToken: String? = null
    private var activeServerUrl = DEFAULT_SERVER_URL
    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopCollector()
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_START -> startCollector(intent)
        }
        return START_STICKY
    }

    override fun onDestroy() {
        stopCollector()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startCollector(intent: Intent) {
        stopCollector()
        val serverUrl = intent.getStringExtra(EXTRA_SERVER_URL).orEmpty()
        val raceCode = intent.getStringExtra(EXTRA_RACE_CODE).orEmpty()
        val entryId = intent.getStringExtra(EXTRA_ENTRY_ID).orEmpty()
        val teamCode = intent.getStringExtra(EXTRA_TEAM_CODE).orEmpty()
        val driverId = intent.getStringExtra(EXTRA_DRIVER_ID).orEmpty()
        val ps5Ip = intent.getStringExtra(EXTRA_PS5_IP).orEmpty()
        activeServerUrl = serverUrl

        startForeground(NOTIFICATION_ID, notification("Starting collector", "Registering with timing server..."))
        acquireLocks()
        broadcast("GT7 connection", "not connected")
        broadcast("Server connection", "loading")
        broadcast("Sending data", "NO")

        worker = Thread {
            try {
                collectorToken = api.register(serverUrl, raceCode, entryId, teamCode, driverId)
                broadcast("Server connection", "OK")
                broadcast("Sending data", "YES")
                broadcast("Last packet", "waiting for GT7 packet...")
                updateNotification("TRC GT7 Collector running", "Sending telemetry for $entryId")

                udpCollector = GT7UdpCollector(
                    playStationIp = ps5Ip,
                    updateHz = 2.0,
                    onPayload = { payload -> sendTelemetry(payload) },
                    onStatus = { value -> broadcast("GT7 connection", value) },
                    onError = { message -> broadcastMessage(message, true) }
                ).also { it.start() }
            } catch (error: Exception) {
                broadcast("Server connection", "not connected")
                broadcast("Sending data", "NO")
                broadcastMessage(friendly(error), true)
                stopSelf()
            }
        }.apply {
            name = "CollectorServiceRegister"
            start()
        }
    }

    private fun sendTelemetry(payload: TelemetryPayload) {
        val token = collectorToken ?: return
        try {
            api.sendTelemetry(activeServerUrl, token, payload)
            broadcast("Server connection", "OK")
            broadcast("Sending data", "YES")
            broadcast("Last packet", "lap=${payload.lap} speed=${payload.speedKmh.toInt()}km/h fuel=${"%.1f".format(payload.fuelLiters)}L")
        } catch (_: Exception) {
            broadcast("Server connection", "not connected")
            broadcastMessage("Connection to timing server lost. The app will keep trying while it is open.", true)
        }
    }

    private fun stopCollector() {
        udpCollector?.stop()
        udpCollector = null
        worker?.interrupt()
        worker = null
        collectorToken = null
        releaseLocks()
        broadcast("GT7 connection", "not connected")
        broadcast("Sending data", "NO")
    }

    private fun acquireLocks() {
        val powerManager = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "TRC:CollectorWakeLock").apply {
            setReferenceCounted(false)
            acquire()
        }
        val wifiManager = applicationContext.getSystemService(WIFI_SERVICE) as WifiManager
        wifiLock = wifiManager.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "TRC:CollectorWifiLock").apply {
            setReferenceCounted(false)
            acquire()
        }
    }

    private fun releaseLocks() {
        if (wakeLock?.isHeld == true) wakeLock?.release()
        wakeLock = null
        if (wifiLock?.isHeld == true) wifiLock?.release()
        wifiLock = null
    }

    private fun updateNotification(title: String, text: String) {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, notification(title, text))
    }

    private fun notification(title: String, text: String): Notification {
        val openIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stopIntent = Intent(this, CollectorService::class.java).setAction(ACTION_STOP)
        val stopPendingIntent = PendingIntent.getService(
            this,
            1,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_trc)
            .setContentTitle(title)
            .setContentText(text)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .addAction(R.drawable.ic_stat_trc, "Stop", stopPendingIntent)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
            val channel = NotificationChannel(
                CHANNEL_ID,
                "TRC GT7 Collector",
                NotificationManager.IMPORTANCE_LOW
            )
            manager.createNotificationChannel(channel)
        }
    }

    private fun broadcast(label: String, value: String) {
        sendBroadcast(Intent(ACTION_STATUS).apply {
            setPackage(packageName)
            putExtra(EXTRA_STATUS_LABEL, label)
            putExtra(EXTRA_STATUS_VALUE, value)
        })
    }

    private fun broadcastMessage(message: String, isError: Boolean) {
        sendBroadcast(Intent(ACTION_MESSAGE).apply {
            setPackage(packageName)
            putExtra(EXTRA_MESSAGE, message)
            putExtra(EXTRA_IS_ERROR, isError)
        })
    }

    private fun friendly(error: Exception): String {
        val text = error.message.orEmpty()
        val lower = text.lowercase()
        return when {
            lower.contains("race") && lower.contains("not found") ->
                "Race code was not found. Please check the race code provided by Race Control."
            lower.contains("team") && (lower.contains("code") || lower.contains("pin")) ->
                "Team code is incorrect. Please check the code provided by Race Control."
            lower.contains("entry") && lower.contains("not found") ->
                "Team/car was not found. Please press Connect again and select the correct car."
            else -> text.ifBlank { "Connection failed. Please check your server, race code and network." }
        }
    }

    companion object {
        const val ACTION_START = "com.trc.gt7collector.START"
        const val ACTION_STOP = "com.trc.gt7collector.STOP"
        const val ACTION_STATUS = "com.trc.gt7collector.STATUS"
        const val ACTION_MESSAGE = "com.trc.gt7collector.MESSAGE"
        const val EXTRA_SERVER_URL = "server_url"
        const val EXTRA_RACE_CODE = "race_code"
        const val EXTRA_ENTRY_ID = "entry_id"
        const val EXTRA_TEAM_CODE = "team_code"
        const val EXTRA_DRIVER_ID = "driver_id"
        const val EXTRA_PS5_IP = "ps5_ip"
        const val EXTRA_STATUS_LABEL = "status_label"
        const val EXTRA_STATUS_VALUE = "status_value"
        const val EXTRA_MESSAGE = "message"
        const val EXTRA_IS_ERROR = "is_error"
        private const val CHANNEL_ID = "trc_gt7_collector"
        private const val NOTIFICATION_ID = 2381
    }
}
