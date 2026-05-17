import Foundation

enum TimingAPIError: LocalizedError {
    case invalidServerURL
    case requestFailed(String)
    case serverRejected(String)

    var errorDescription: String? {
        switch self {
        case .invalidServerURL:
            return "Server URL is invalid."
        case .requestFailed(let message):
            return message
        case .serverRejected(let message):
            return message
        }
    }
}

final class TimingAPI {
    private let session: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(session: URLSession = .shared) {
        self.session = session
        self.encoder = JSONEncoder()
        self.decoder = JSONDecoder()
    }

    func fetchEntries(serverURL: String, raceCode: String) async throws -> CollectorRaceResponse {
        let url = try endpoint(serverURL, "/api/collector/races/\(raceCode.uppercased())/entries")
        let (data, response) = try await session.data(from: url)
        try validate(response, data: data)
        return try decoder.decode(CollectorRaceResponse.self, from: data)
    }

    func register(
        serverURL: String,
        raceCode: String,
        entryId: String,
        teamCode: String,
        driverId: String
    ) async throws -> CollectorRegisterResponse {
        let request = CollectorRegisterRequest(
            raceCode: raceCode.uppercased(),
            entryId: entryId,
            teamCode: teamCode,
            driverId: driverId,
            collectorVersion: "ios-0.1.0"
        )
        let url = try endpoint(serverURL, "/api/collector/register")
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try encoder.encode(request)
        let (data, response) = try await session.data(for: urlRequest)
        try validate(response, data: data)
        return try decoder.decode(CollectorRegisterResponse.self, from: data)
    }

    func sendTelemetry(serverURL: String, token: String, payload: TelemetryPayload) async throws {
        let url = try endpoint(serverURL, "/api/collector/telemetry")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try encoder.encode(payload)
        let (data, response) = try await session.data(for: request)
        try validate(response, data: data)
    }

    private func endpoint(_ serverURL: String, _ path: String) throws -> URL {
        guard let base = URL(string: serverURL.trimmingCharacters(in: .whitespacesAndNewlines)) else {
            throw TimingAPIError.invalidServerURL
        }
        return base.appending(path: path)
    }

    private func validate(_ response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
            throw TimingAPIError.requestFailed("No HTTP response from timing server.")
        }
        guard 200..<300 ~= http.statusCode else {
            if let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = body["detail"] as? String {
                throw TimingAPIError.serverRejected(detail)
            }
            throw TimingAPIError.serverRejected("Timing server rejected the request (\(http.statusCode)).")
        }
    }
}
