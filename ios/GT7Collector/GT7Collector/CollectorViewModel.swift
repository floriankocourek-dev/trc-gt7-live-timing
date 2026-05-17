import Foundation
import Combine

@MainActor
final class CollectorViewModel: ObservableObject {
    @Published var serverURL = defaultServerURL
    @Published var raceCode = ""
    @Published var teamCode = ""
    @Published var playStationIP = ""
    @Published var entries: [EntryInfo] = []
    @Published var selectedEntryID = ""
    @Published var selectedDriverID = ""
    @Published var gt7Status = "not connected"
    @Published var serverStatus = "not connected"
    @Published var sendingStatus = "NO"
    @Published var lastPacket = "-"
    @Published var message = ""
    @Published var isRunning = false

    private let api = TimingAPI()
    private var collectorToken: String?
    private var udpCollector: GT7UDPCollector?

    var selectedEntry: EntryInfo? {
        entries.first { $0.entryId == selectedEntryID }
    }

    var availableDrivers: [DriverInfo] {
        selectedEntry?.drivers ?? []
    }

    var canStart: Bool {
        !serverURL.isEmpty
            && !raceCode.isEmpty
            && !selectedEntryID.isEmpty
            && !selectedDriverID.isEmpty
            && !teamCode.isEmpty
            && !playStationIP.isEmpty
            && !isRunning
    }

    func loadEntries() {
        let code = raceCode.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard !code.isEmpty else {
            message = "Please enter the race code provided by Race Control."
            return
        }

        Task {
            do {
                let response = try await api.fetchEntries(serverURL: serverURL, raceCode: code)
                raceCode = response.race.raceId
                entries = response.entries
                selectedEntryID = entries.first?.entryId ?? ""
                selectedDriverID = entries.first?.drivers.first?.driverId ?? ""
                serverStatus = "OK"
                message = "Race loaded. Select your car and driver."
            } catch {
                entries = []
                selectedEntryID = ""
                selectedDriverID = ""
                serverStatus = "not connected"
                message = friendly(error)
            }
        }
    }

    func startSending() {
        guard canStart else {
            message = "Please fill in Race Code, Team, Driver, Team PIN and PlayStation IP first."
            return
        }

        Task {
            do {
                let registration = try await api.register(
                    serverURL: serverURL,
                    raceCode: raceCode,
                    entryId: selectedEntryID,
                    teamCode: teamCode,
                    driverId: selectedDriverID
                )
                guard registration.sendAllowed else {
                    message = "Race Control does not allow this collector to send data."
                    return
                }

                collectorToken = registration.collectorToken
                let collector = GT7UDPCollector(playStationIP: playStationIP)
                collector.onStatus = { [weak self] status in
                    Task { @MainActor in self?.gt7Status = status }
                }
                collector.onError = { [weak self] error in
                    Task { @MainActor in
                        self?.gt7Status = "not connected"
                        self?.message = self?.friendlyMessage(error) ?? error
                    }
                }
                collector.onPayload = { [weak self] payload in
                    Task { @MainActor in self?.send(payload) }
                }
                try collector.start()
                udpCollector = collector
                isRunning = true
                serverStatus = "OK"
                sendingStatus = "YES"
                lastPacket = "waiting for GT7 packet..."
                message = "Collector is sending selected telemetry to the timing server."
            } catch {
                serverStatus = "not connected"
                sendingStatus = "NO"
                message = friendly(error)
                stopSending()
            }
        }
    }

    func stopSending() {
        udpCollector?.stop()
        udpCollector = nil
        isRunning = false
        sendingStatus = "NO"
        gt7Status = "not connected"
        collectorToken = nil
    }

    func selectEntry(_ entryID: String) {
        selectedEntryID = entryID
        selectedDriverID = entries.first { $0.entryId == entryID }?.drivers.first?.driverId ?? ""
    }

    private func send(_ payload: TelemetryPayload) {
        guard let collectorToken else { return }
        Task {
            do {
                try await api.sendTelemetry(serverURL: serverURL, token: collectorToken, payload: payload)
                serverStatus = "OK"
                sendingStatus = "YES"
                lastPacket = "lap=\(payload.lap) speed=\(Int(payload.speedKmh))km/h fuel=\(String(format: "%.1f", payload.fuelLiters))L"
            } catch {
                serverStatus = "not connected"
                message = "Connection to timing server lost. The app will keep trying while it is open."
            }
        }
    }

    private func friendly(_ error: Error) -> String {
        if let apiError = error as? TimingAPIError {
            switch apiError {
            case .serverRejected(let detail):
                return friendlyMessage(detail)
            default:
                return apiError.localizedDescription
            }
        }
        return friendlyMessage(error.localizedDescription)
    }

    private func friendlyMessage(_ detail: String) -> String {
        let lower = detail.lowercased()
        if lower.contains("race") && lower.contains("not found") {
            return "Race code was not found. Please check the race code provided by Race Control."
        }
        if lower.contains("team") && (lower.contains("code") || lower.contains("pin")) {
            return "Team code is incorrect. Please check the code provided by Race Control."
        }
        if lower.contains("entry") && lower.contains("not found") {
            return "Team/car was not found. Please press Connect again and select the correct car."
        }
        if lower.contains("gt7") || lower.contains("playstation") || lower.contains("udp") {
            return "GT7 was not found. Please check that GT7 is running and your iPhone and PlayStation are in the same network."
        }
        return detail
    }
}
