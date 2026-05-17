import SwiftUI

struct ContentView: View {
    @StateObject private var model = CollectorViewModel()

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("TRC GT7 Collector")
                            .font(.title2)
                            .fontWeight(.bold)
                        Text("Reads GT7 telemetry from your local network and sends selected race telemetry to the timing server.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                }

                Section("Server") {
                    TextField("Server", text: $model.serverURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()

                    HStack {
                        TextField("Race Code", text: $model.raceCode)
                            .textInputAutocapitalization(.characters)
                            .autocorrectionDisabled()
                        Button("Connect") {
                            model.loadEntries()
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }

                Section("Team") {
                    Picker("Team / Car", selection: Binding(
                        get: { model.selectedEntryID },
                        set: { model.selectEntry($0) }
                    )) {
                        Text("Select team").tag("")
                        ForEach(model.entries) { entry in
                            Text(entry.label).tag(entry.entryId)
                        }
                    }

                    Picker("Current Driver", selection: $model.selectedDriverID) {
                        Text("Select driver").tag("")
                        ForEach(model.availableDrivers) { driver in
                            Text(driver.displayName).tag(driver.driverId)
                        }
                    }

                    SecureField("Team PIN", text: $model.teamCode)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Section("PlayStation") {
                    TextField("PlayStation IP", text: $model.playStationIP)
                        .keyboardType(.numbersAndPunctuation)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Section("Status") {
                    statusRow("GT7 connection", model.gt7Status)
                    statusRow("Server connection", model.serverStatus)
                    statusRow("Sending data", model.sendingStatus)
                    statusRow("Last packet", model.lastPacket)

                    HStack {
                        Button("Start Sending") {
                            model.startSending()
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(!model.canStart)

                        Button("Stop") {
                            model.stopSending()
                        }
                        .buttonStyle(.bordered)
                        .disabled(!model.isRunning)
                    }

                    if !model.message.isEmpty {
                        Text(model.message)
                            .font(.footnote)
                            .foregroundStyle(messageColor(model.message))
                    }
                }

                Section("Privacy") {
                    Text("This app only reads GT7 telemetry from your local network and sends selected race telemetry to the timing server. It does not access personal files, microphone, camera, keyboard input, screen capture or browser data.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Collector")
        }
    }

    private func statusRow(_ title: String, _ value: String) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text(value)
                .fontWeight(.semibold)
                .foregroundStyle(statusColor(value))
                .multilineTextAlignment(.trailing)
        }
    }

    private func statusColor(_ value: String) -> Color {
        let lower = value.lowercased()
        if lower == "ok" || lower == "yes" { return .green }
        if lower == "no" || lower.contains("not") { return .red }
        return .secondary
    }

    private func messageColor(_ value: String) -> Color {
        let lower = value.lowercased()
        if lower.contains("not") || lower.contains("lost") || lower.contains("incorrect") {
            return .red
        }
        return .secondary
    }
}

#Preview {
    ContentView()
}
