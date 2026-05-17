import Foundation
import Network

enum GT7UDPCollectorError: LocalizedError {
    case invalidPlayStationIP
    case invalidPort

    var errorDescription: String? {
        switch self {
        case .invalidPlayStationIP:
            return "PlayStation IP address is invalid."
        case .invalidPort:
            return "GT7 UDP port could not be opened."
        }
    }
}

final class GT7UDPCollector {
    private let playStationIP: String
    private let heartbeatType: String
    private let updateInterval: TimeInterval
    private let queue = DispatchQueue(label: "TRCGT7Collector.udp")

    private var listener: NWListener?
    private var heartbeatConnection: NWConnection?
    private var heartbeatTimer: DispatchSourceTimer?
    private var lastPayloadSentAt = Date.distantPast

    var onPayload: ((TelemetryPayload) -> Void)?
    var onStatus: ((String) -> Void)?
    var onError: ((String) -> Void)?

    init(playStationIP: String, heartbeatType: String = "A", updateHz: Double = 1.0) {
        self.playStationIP = playStationIP.trimmingCharacters(in: .whitespacesAndNewlines)
        self.heartbeatType = heartbeatType
        self.updateInterval = 1.0 / max(updateHz, 0.2)
    }

    func start() throws {
        guard !playStationIP.isEmpty else { throw GT7UDPCollectorError.invalidPlayStationIP }
        guard let listenPort = NWEndpoint.Port(rawValue: 33740),
              let sendPort = NWEndpoint.Port(rawValue: 33739) else {
            throw GT7UDPCollectorError.invalidPort
        }

        let params = NWParameters.udp
        params.allowLocalEndpointReuse = true
        let listener = try NWListener(using: params, on: listenPort)
        listener.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                self?.onStatus?("OK")
            case .failed(let error):
                self?.onError?("GT7 connection failed: \(error.localizedDescription)")
            default:
                break
            }
        }
        listener.newConnectionHandler = { [weak self] connection in
            guard let self else { return }
            connection.start(queue: self.queue)
            self.receive(on: connection)
        }
        listener.start(queue: queue)
        self.listener = listener

        let heartbeatConnection = NWConnection(
            host: NWEndpoint.Host(playStationIP),
            port: sendPort,
            using: .udp
        )
        heartbeatConnection.stateUpdateHandler = { [weak self] state in
            if case .failed(let error) = state {
                self?.onError?("Could not send GT7 heartbeat: \(error.localizedDescription)")
            }
        }
        heartbeatConnection.start(queue: queue)
        self.heartbeatConnection = heartbeatConnection

        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now(), repeating: .seconds(10))
        timer.setEventHandler { [weak self] in
            self?.sendHeartbeat()
        }
        timer.resume()
        heartbeatTimer = timer
    }

    func stop() {
        heartbeatTimer?.cancel()
        heartbeatTimer = nil
        heartbeatConnection?.cancel()
        heartbeatConnection = nil
        listener?.cancel()
        listener = nil
        lastPayloadSentAt = .distantPast
    }

    private func receive(on connection: NWConnection) {
        connection.receiveMessage { [weak self] data, _, _, error in
            guard let self else { return }
            if let data, !data.isEmpty {
                self.handle(data)
            }
            if let error {
                self.onError?("GT7 packet receive error: \(error.localizedDescription)")
                return
            }
            self.receive(on: connection)
        }
    }

    private func handle(_ data: Data) {
        do {
            let decrypted = try GT7Packet.decrypt(data, heartbeatType: heartbeatType)
            let packet = try GT7Packet.parse(decrypted)
            let now = Date()
            guard now.timeIntervalSince(lastPayloadSentAt) >= updateInterval else { return }
            lastPayloadSentAt = now
            onStatus?("OK")
            onPayload?(packet.payload())
        } catch {
            onError?("GT7 packet could not be read: \(error.localizedDescription)")
        }
    }

    private func sendHeartbeat() {
        guard let heartbeatConnection else { return }
        let payload = Data(heartbeatType.utf8)
        heartbeatConnection.send(content: payload, completion: .contentProcessed { [weak self] error in
            if let error {
                self?.onError?("Could not reach PlayStation: \(error.localizedDescription)")
            }
        })
    }
}
