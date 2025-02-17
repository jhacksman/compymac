// MARK: - IPC Service Layer
class PythonBrowserService {
    static let shared = PythonBrowserService()
    private var socketTask: URLSessionWebSocketTask?
    private var isConnected = false
    
    func connect() {
        guard !isConnected else { return }
        let serverURL = URL(string: "ws://127.0.0.1:8765")!
        socketTask = URLSession.shared.webSocketTask(with: serverURL)
        socketTask?.resume()
        isConnected = true
        listenForMessages()
    }
    
    func sendCommand(_ action: String, payload: [String: Any]) async throws -> Result<[String: Any], Error> {
        if !isConnected {
            connect()
        }
        
        var request = payload
        request["action"] = action
        
        let jsonData = try JSONSerialization.data(withJSONObject: request)
        let jsonString = String(data: jsonData, encoding: .utf8) ?? "{}"
        
        try await socketTask?.send(.string(jsonString))
        return .success([:]) // Actual response handled via message listener
    }
    
    private func handleResponse(_ response: [String: Any]) {
        guard let action = response["action"] as? String else { return }
        
        if let status = response["status"] as? String, status == "error" {
            let errorMsg = response["message"] as? String ?? "Unknown error"
            print("Python service reported error for \(action): \(errorMsg)")
            return
        }
        
        // Handle successful responses based on action type
        switch action {
        case "openPage":
            if let title = response["title"] as? String {
                print("Page opened: \(title)")
            }
        default:
            break
        }
    }
    
    private func listenForMessages() {
        socketTask?.receive { [weak self] result in
            switch result {
            case .failure(let error):
                print("WebSocket receive error: \(error)")
            case .success(let message):
                switch message {
                case .string(let text):
                    if let data = text.data(using: .utf8),
                       let response = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        self?.handleResponse(response)
                    }
                default:
                    break
                }
            }
            self?.listenForMessages()
        }
    }
    
    func disconnect() {
        socketTask?.cancel(with: .goingAway, reason: nil)
        isConnected = false
    }
}
