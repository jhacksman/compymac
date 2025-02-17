// MARK: - IPC Service Layer
class PythonBrowserService {
    static let shared = PythonBrowserService()
    private var socketTask: URLSessionWebSocketTask?
    private var isConnected = false
    private var retryCount = 0
    private let maxRetries = 5
    private let baseDelay: TimeInterval = 1.0
    
    func connect() {
        guard !isConnected else { return }
        
        let serverURL = URL(string: "ws://127.0.0.1:8765")!
        socketTask = URLSession.shared.webSocketTask(with: serverURL)
        
        socketTask?.resume()
        isConnected = true
        retryCount = 0  // Reset retry count on successful connection
        
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
            handleError(errorMsg, action: action)
            return
        }
        
        // Handle successful responses based on action type
        switch action {
        case "openPage":
            if let title = response["title"] as? String {
                notifySuccess("Page opened successfully", subtitle: title)
            }
        case "desktop_launch_app":
            notifySuccess("Application launched successfully")
        case "desktop_click_menu":
            notifySuccess("Menu item clicked successfully")
        case "desktop_type_text":
            notifySuccess("Text input completed")
        case "desktop_handle_dialog":
            if let result = response["result"] as? [String: Any] {
                notifySuccess("Dialog handled successfully", subtitle: "\(result)")
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
                reconnect()
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
    
    private func reconnect() {
        guard retryCount < maxRetries else {
            notifyReconnectionFailed()
            return
        }
        
        let delay = baseDelay * pow(2.0, Double(retryCount))
        retryCount += 1
        isConnected = false
        
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
            self?.connect()
        }
    }
    
    private func notifyReconnectionFailed() {
        let notification = NSUserNotification()
        notification.title = "Connection Error"
        notification.informativeText = "Failed to reconnect to automation service after multiple attempts"
        NSUserNotificationCenter.default.deliver(notification)
    }
    

    private func handleError(_ message: String, action: String) {
        let notification = NSUserNotification()
        notification.title = "Automation Error"
        notification.subtitle = action.replacingOccurrences(of: "_", with: " ").capitalized
        notification.informativeText = message
        NSUserNotificationCenter.default.deliver(notification)
    }
    
    private func notifySuccess(_ message: String, subtitle: String? = nil) {
        let notification = NSUserNotification()
        notification.title = "Automation Success"
        if let subtitle = subtitle {
            notification.subtitle = subtitle
        }
        notification.informativeText = message
        NSUserNotificationCenter.default.deliver(notification)
    }


// MARK: - Desktop Automation
extension PythonBrowserService {
    func launchApplication(_ appName: String) async throws -> Result<[String: Any], Error> {
        return try await sendCommand("desktop_launch_app", payload: ["app_name": appName])
    }
    
    func clickMenuItem(appName: String, menuPath: [String]) async throws -> Result<[String: Any], Error> {
        return try await sendCommand("desktop_click_menu", payload: [
            "app_name": appName,
            "menu_path": menuPath
        ])
    }
    
    func typeText(_ text: String) async throws -> Result<[String: Any], Error> {
        return try await sendCommand("desktop_type_text", payload: ["text": text])
    }
    
    func handleDialog(action: String, params: [String: Any]) async throws -> Result<[String: Any], Error> {
        return try await sendCommand("desktop_handle_dialog", payload: [
            "dialog_action": action,
            "dialog_params": params
        ])
    }
}


    func disconnect() {
        socketTask?.cancel(with: .goingAway, reason: nil)
        isConnected = false
    }
}
