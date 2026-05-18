package com.trc.gt7collector

import android.Manifest
import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.View
import android.view.WindowManager
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import android.widget.AdapterView

class MainActivity : Activity() {
    private val api = TimingApi()
    private var entries: List<EntryInfo> = emptyList()
    private var isSending = false
    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                CollectorService.ACTION_STATUS -> {
                    val label = intent.getStringExtra(CollectorService.EXTRA_STATUS_LABEL).orEmpty()
                    val value = intent.getStringExtra(CollectorService.EXTRA_STATUS_VALUE).orEmpty()
                    updateStatusFromService(label, value)
                }
                CollectorService.ACTION_MESSAGE -> {
                    val message = intent.getStringExtra(CollectorService.EXTRA_MESSAGE).orEmpty()
                    val isError = intent.getBooleanExtra(CollectorService.EXTRA_IS_ERROR, false)
                    showMessage(message, isError)
                }
            }
        }
    }

    private lateinit var serverInput: EditText
    private lateinit var raceInput: EditText
    private lateinit var teamSpinner: Spinner
    private lateinit var driverSpinner: Spinner
    private lateinit var pinInput: EditText
    private lateinit var ps5Input: EditText
    private lateinit var gt7Status: TextView
    private lateinit var serverStatus: TextView
    private lateinit var sendingStatus: TextView
    private lateinit var lastPacket: TextView
    private lateinit var messageView: TextView
    private lateinit var startButton: Button
    private lateinit var stopButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        requestNotificationPermission()
        buildUi()
    }

    override fun onStart() {
        super.onStart()
        val filter = IntentFilter().apply {
            addAction(CollectorService.ACTION_STATUS)
            addAction(CollectorService.ACTION_MESSAGE)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(statusReceiver, filter, RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("DEPRECATION")
            registerReceiver(statusReceiver, filter)
        }
    }

    override fun onStop() {
        unregisterReceiver(statusReceiver)
        super.onStop()
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(18), dp(18), dp(24))
        }

        val title = TextView(this).apply {
            text = "TRC GT7 Collector"
            textSize = 26f
            setTextColor(Color.rgb(20, 20, 20))
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        root.addView(title)
        root.addView(TextView(this).apply {
            text = "Reads GT7 telemetry from your local network and sends selected race telemetry to the timing server."
            textSize = 13f
            setTextColor(Color.rgb(80, 86, 101))
            setPadding(0, dp(4), 0, dp(18))
        })

        serverInput = input("Server", DEFAULT_SERVER_URL)
        raceInput = input("Race Code", "")
        teamSpinner = spinner()
        driverSpinner = spinner()
        pinInput = input("Team PIN", "").apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        ps5Input = input("PlayStation IP", "")

        root.addView(label("Server"))
        root.addView(serverInput)
        root.addView(label("Race Code"))
        root.addView(row(raceInput, Button(this).apply {
            text = "Connect"
            setOnClickListener { loadEntries() }
        }))
        root.addView(label("Team / Car"))
        root.addView(teamSpinner)
        root.addView(label("Current Driver"))
        root.addView(driverSpinner)
        root.addView(label("Team PIN"))
        root.addView(pinInput)
        root.addView(label("PlayStation IP"))
        root.addView(ps5Input)

        root.addView(sectionTitle("Status"))
        gt7Status = statusValue("not connected")
        serverStatus = statusValue("not connected")
        sendingStatus = statusValue("NO")
        lastPacket = statusValue("-")
        root.addView(statusRow("GT7 connection", gt7Status))
        root.addView(statusRow("Server connection", serverStatus))
        root.addView(statusRow("Sending data", sendingStatus))
        root.addView(statusRow("Last packet", lastPacket))

        startButton = Button(this).apply {
            text = "Start Sending"
            setOnClickListener { startSending() }
        }
        stopButton = Button(this).apply {
            text = "Stop"
            isEnabled = false
            setOnClickListener { stopSending() }
        }
        root.addView(row(startButton, stopButton))

        messageView = TextView(this).apply {
            textSize = 13f
            setTextColor(Color.rgb(80, 86, 101))
            setPadding(0, dp(12), 0, dp(8))
        }
        root.addView(messageView)
        root.addView(TextView(this).apply {
            text = "This app only reads GT7 telemetry from your local network and sends selected race telemetry to the timing server. It does not access personal files, microphone, camera, keyboard input, screen capture or browser data."
            textSize = 12f
            setTextColor(Color.rgb(100, 110, 125))
            setPadding(0, dp(12), 0, 0)
        })

        teamSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                updateDriverSpinner()
            }

            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }

        setContentView(ScrollView(this).apply { addView(root) })
        setTeamOptions(emptyList())
        setDriverOptions(emptyList())
    }

    private fun loadEntries() {
        val raceCode = raceInput.text.toString().trim()
        val serverUrl = serverInput.text.toString().trim()
        if (raceCode.isEmpty()) {
            showMessage("Please enter the race code provided by Race Control.", true)
            return
        }
        setStatus(serverStatus, "loading")
        Thread {
            try {
                val response = api.fetchEntries(serverUrl, raceCode)
                entries = response.entries
                runOnUiThread {
                    raceInput.setText(response.raceId)
                    setTeamOptions(entries.map { it.label })
                    updateDriverSpinner()
                    setStatus(serverStatus, "OK")
                    showMessage("Race loaded. Select your car and driver.", false)
                }
            } catch (error: Exception) {
                entries = emptyList()
                runOnUiThread {
                    setTeamOptions(emptyList())
                    setDriverOptions(emptyList())
                    setStatus(serverStatus, "not connected")
                    showMessage(friendly(error), true)
                }
            }
        }.start()
    }

    private fun startSending() {
        val entry = selectedEntry()
        val driver = selectedDriver()
        val pin = pinInput.text.toString()
        val ps5Ip = ps5Input.text.toString().trim()
        val serverUrl = serverInput.text.toString().trim()
        val raceCode = raceInput.text.toString().trim()
        if (entry == null || driver == null || pin.isBlank() || ps5Ip.isBlank()) {
            showMessage("Please fill in Team, Driver, Team PIN and PlayStation IP first.", true)
            return
        }

        startButton.isEnabled = false
        stopButton.isEnabled = true
        isSending = true
        setStatus(serverStatus, "loading")
        setStatus(sendingStatus, "YES")
        setStatus(lastPacket, "waiting for GT7 packet...")
        showMessage("Collector runs in the background until you press Stop.", false)

        val intent = Intent(this, CollectorService::class.java).apply {
            action = CollectorService.ACTION_START
            putExtra(CollectorService.EXTRA_SERVER_URL, serverUrl)
            putExtra(CollectorService.EXTRA_RACE_CODE, raceCode)
            putExtra(CollectorService.EXTRA_ENTRY_ID, entry.entryId)
            putExtra(CollectorService.EXTRA_TEAM_CODE, pin)
            putExtra(CollectorService.EXTRA_DRIVER_ID, driver.driverId)
            putExtra(CollectorService.EXTRA_PS5_IP, ps5Ip)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    private fun stopSending() {
        isSending = false
        stopService(Intent(this, CollectorService::class.java).setAction(CollectorService.ACTION_STOP))
        setStatus(gt7Status, "not connected")
        setStatus(sendingStatus, "NO")
        if (::startButton.isInitialized) startButton.isEnabled = true
        if (::stopButton.isInitialized) stopButton.isEnabled = false
    }

    private fun updateStatusFromService(label: String, value: String) {
        when (label) {
            "GT7 connection" -> setStatus(gt7Status, value)
            "Server connection" -> setStatus(serverStatus, value)
            "Sending data" -> {
                setStatus(sendingStatus, value)
                isSending = value.equals("YES", ignoreCase = true)
                startButton.isEnabled = !isSending
                stopButton.isEnabled = isSending
            }
            "Last packet" -> setStatus(lastPacket, value)
        }
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 2381)
        }
    }

    private fun selectedEntry(): EntryInfo? =
        entries.getOrNull(teamSpinner.selectedItemPosition)

    private fun selectedDriver(): DriverInfo? =
        selectedEntry()?.drivers?.getOrNull(driverSpinner.selectedItemPosition)

    private fun updateDriverSpinner() {
        setDriverOptions(selectedEntry()?.drivers?.map { "${it.driverId} - ${it.displayName}" }.orEmpty())
    }

    private fun setTeamOptions(labels: List<String>) {
        teamSpinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, labels).apply {
            setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        }
    }

    private fun setDriverOptions(labels: List<String>) {
        driverSpinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, labels).apply {
            setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        }
    }

    private fun input(hint: String, value: String): EditText = EditText(this).apply {
        setHint(hint)
        setText(value)
        setSingleLine(true)
        setPadding(dp(10), 0, dp(10), 0)
    }

    private fun spinner(): Spinner = Spinner(this).apply {
        setPadding(0, dp(4), 0, dp(4))
    }

    private fun label(text: String): TextView = TextView(this).apply {
        this.text = text.uppercase()
        textSize = 12f
        setTypeface(typeface, android.graphics.Typeface.BOLD)
        setTextColor(Color.rgb(80, 86, 101))
        setPadding(0, dp(10), 0, dp(4))
    }

    private fun sectionTitle(text: String): TextView = TextView(this).apply {
        this.text = text
        textSize = 20f
        setTypeface(typeface, android.graphics.Typeface.BOLD)
        setTextColor(Color.rgb(20, 20, 20))
        setPadding(0, dp(22), 0, dp(8))
    }

    private fun statusValue(value: String): TextView = TextView(this).apply {
        textSize = 14f
        setTypeface(typeface, android.graphics.Typeface.BOLD)
        setStatus(this, value)
    }

    private fun statusRow(title: String, value: TextView): LinearLayout =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(4), 0, dp(4))
            addView(TextView(this@MainActivity).apply {
                text = "$title:"
                textSize = 14f
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            })
            addView(value.apply {
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            })
        }

    private fun row(left: View, right: View): LinearLayout =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(left, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            addView(right, LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                leftMargin = dp(8)
            })
        }

    private fun setStatus(view: TextView, value: String) {
        view.text = value
        val lower = value.lowercase()
        view.setTextColor(
            when {
                lower == "ok" || lower == "yes" -> Color.rgb(23, 107, 53)
                lower == "no" || lower.contains("not") -> Color.rgb(176, 0, 32)
                else -> Color.rgb(80, 86, 101)
            }
        )
    }

    private fun showMessage(message: String, isError: Boolean) {
        messageView.text = message
        messageView.setTextColor(if (isError) Color.rgb(176, 0, 32) else Color.rgb(80, 86, 101))
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

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
