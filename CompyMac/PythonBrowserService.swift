import Foundation
import AppKit
import WebKit
import UserNotifications

// MARK: - IPC Service Layer
public class PythonBrowserService {
    public static let shared = PythonBrowserService()
    private var socketTask: URLSessionWebSocketTask?
    private var isConnected = false
    private var retryCount = 0
    private let maxRetries = 5
    private let baseDelay: TimeInterval = 1.0
    
    // MARK: - Command Types
    
    public struct CommandResult {
        public let success: Bool
        public let output: String?
        public let error: String?
        public let returnCode: Int?
    }
    
    public func connect() {
        guard !isConnected else { return }
        
        let serverURL = URL(string: "ws://127.0.0.1:8765")!
        socketTask = URLSession.shared.webSocketTask(with: serverURL)
        
        socketTask?.resume()
        isConnected = true
        retryCount = 0  // Reset retry count on successful connection
        
        listenForMessages()
    }
    
    public func sendCommand(_ action: String, payload: [String: Any]) async throws -> Result<[String: Any], Error> {
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
    
    // MARK: - CLI Operations
    
    public func executeCommand(_ command: String) async throws -> Result<CommandResult, Error> {
        let result = try await sendCommand("runCommand", payload: ["command": command])
        return .success(CommandResult(success: true, output: "", error: nil)) // Response handled via message listener
    }
    
    // MARK: - Browser Types
    
    public enum BrowserMode: String {
        case webkit = "webkit"
    }
    
    public struct BrowserResult {
        public let success: Bool
        public let title: String?
        public let url: String?
        public let error: String?
    }
    
    // MARK: - Browser Operations
    
    public func openBrowser(url: String) async throws -> Result<BrowserResult, Error> {
        _ = try await sendCommand("openBrowser", payload: ["url": url])
        return .success(BrowserResult(success: true, title: "", url: url, error: nil))
    }
    
    public func clickElement(selector: String) async throws -> Result<BrowserResult, Error> {
        _ = try await sendCommand("clickElement", payload: ["selector": selector])
        return .success(BrowserResult(success: true, title: nil, url: nil, error: nil))
    }
    
    public func fillForm(fields: [String: String]) async throws -> Result<BrowserResult, Error> {
        _ = try await sendCommand("fillForm", payload: ["fields": fields])
        return .success(BrowserResult(success: true, title: nil, url: nil, error: nil))
    }
    
    public func navigateBack() async throws -> Result<BrowserResult, Error> {
        _ = try await sendCommand("navigateBack", payload: [:])
        return .success(BrowserResult(success: true, title: nil, url: nil, error: nil))
    }
    
    public func navigateForward() async throws -> Result<BrowserResult, Error> {
        _ = try await sendCommand("navigateForward", payload: [:])
        return .success(BrowserResult(success: true, title: nil, url: nil, error: nil))
    }
    
    public func refresh() async throws -> Result<BrowserResult, Error> {
        _ = try await sendCommand("refresh", payload: [:])
        return .success(BrowserResult(success: true, title: nil, url: nil, error: nil))
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
        case "openBrowser":
            if let title = response["title"] as? String,
               let url = response["url"] as? String {
                print("Browser opened: \(title) at \(url)")
            }
        case "runCommand":
            if let output = response["output"] as? String {
                print("Command output: \(output)")
                if let error = response["error"] as? String, !error.isEmpty {
                    print("Command error: \(error)")
                }
            }
        case "openPage":
            if let title = response["title"] as? String {
                print("Page opened: \(title)")
            }
        default:
            break
        }
    }
    
    private func listenForMessages() {
        socketTask?.receive { [weak self] (result: Result<URLSessionWebSocketTask.Message, Error>) in
            switch result {
            case .failure(let error):
                print("WebSocket receive error: \(error)")
                self?.reconnect()
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
        
        let delay = baseDelay * Foundation.pow(2.0, Double(retryCount))
        retryCount += 1
        isConnected = false
        
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
            self?.connect()
        }
    }
    
    private func notifyReconnectionFailed() {
        let content = UNMutableNotificationContent()
        content.title = "Connection Error"
        content.body = "Failed to reconnect to automation service after multiple attempts"
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
        Task {
            try? await UNUserNotificationCenter.current().add(request)
        }
    }
    
    private func handleError(_ message: String, action: String) {
        let content = UNMutableNotificationContent()
        content.title = "Automation Error"
        content.subtitle = action.replacingOccurrences(of: "_", with: " ").capitalized
        content.body = message
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
        Task {
            try? await UNUserNotificationCenter.current().add(request)
        }
    }
    
    private func notifySuccess(_ message: String, subtitle: String? = nil) {
        let content = UNMutableNotificationContent()
        content.title = "Automation Success"
        if let subtitle = subtitle {
            content.subtitle = subtitle
        }
        content.body = message
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
        Task {
            try? await UNUserNotificationCenter.current().add(request)
        }
    }

// MARK: - Desktop Automation
extension PythonBrowserService {
    // MARK: - Finder Operations
    
    public struct FinderResult {
        public let success: Bool
        public let items: [String]?
        public let error: String?
    }
    
    public func openFolder(_ path: String) async throws -> Result<FinderResult, Error> {
        let result = try await sendCommand("desktop_open_folder", payload: ["path": path])
        return .success(FinderResult(success: true, items: nil, error: nil))
    }
    
    public func createFolder(_ path: String) async throws -> Result<FinderResult, Error> {
        let result = try await sendCommand("desktop_create_folder", payload: ["path": path])
        return .success(FinderResult(success: true, items: nil, error: nil))
    }
    
    public func moveItems(sourcePaths: [String], destinationPath: String) async throws -> Result<FinderResult, Error> {
        let result = try await sendCommand("desktop_move_items", payload: [
            "source_paths": sourcePaths,
            "destination_path": destinationPath
        ])
        return .success(FinderResult(success: true, items: nil, error: nil))
    }
    
    public func getSelectedItems() async throws -> Result<FinderResult, Error> {
        let result = try await sendCommand("desktop_get_selected", payload: [:])
        return .success(FinderResult(success: true, items: [], error: nil))
    }
    
    // MARK: - App Control
    
    public func launchApplication(_ appName: String) async throws -> Result<[String: Any], Error> {
        return try await sendCommand("desktop_launch_app", payload: ["app_name": appName])
    }
    
    public func clickMenuItem(appName: String, menuPath: [String]) async throws -> Result<[String: Any], Error> {
        return try await sendCommand("desktop_click_menu", payload: [
            "app_name": appName,
            "menu_path": menuPath
        ])
    }
    
    public func typeText(_ text: String) async throws -> Result<[String: Any], Error> {
        return try await sendCommand("desktop_type_text", payload: ["text": text])
    }
    
    public func handleDialog(action: String, params: [String: Any]) async throws -> Result<[String: Any], Error> {
        return try await sendCommand("desktop_handle_dialog", payload: [
            "dialog_action": action,
            "dialog_params": params
        ])
    }
    
    public func disconnect() {
        socketTask?.cancel(with: .goingAway, reason: "Disconnecting".data(using: .utf8))
        isConnected = false
    }
}
