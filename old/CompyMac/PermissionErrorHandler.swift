import Cocoa

class PermissionErrorHandler {
    static let shared = PermissionErrorHandler()
    private let logger = Logger()
    
    private init() {}
    
    func handlePermissionDenied() {
        logger.log("Permission denied: Accessibility permission not granted")
        showPersistentDenialAlert()
    }
    
    func handlePermissionError(_ error: Error) {
        logger.log("Permission error: \(error.localizedDescription)")
        showErrorBanner(message: error.localizedDescription)
    }
    
    private func showPersistentDenialAlert() {
        let alert = NSAlert()
        alert.messageText = "Permission Required"
        alert.informativeText = """
            CompyMac requires Accessibility permission to function properly.
            
            The app's automation features will be limited until permission is granted.
            
            Would you like to:
            1. Open System Settings to grant permission
            2. View the permission guide
            3. Continue without automation features
            """
        alert.alertStyle = .warning
        
        alert.addButton(withTitle: "Open Settings")
        alert.addButton(withTitle: "View Guide")
        alert.addButton(withTitle: "Continue Limited")
        
        switch alert.runModal() {
        case .alertFirstButtonReturn:
            AccessibilityPermissionManager.shared.requestAccessibilityPermission()
        case .alertSecondButtonReturn:
            NotificationCenter.default.post(name: .showPermissionGuide, object: nil)
        default:
            showLimitedFeaturesNotification()
        }
    }
    
    private func showErrorBanner(message: String) {
        let notification = NSUserNotification()
        notification.title = "CompyMac"
        notification.subtitle = "Permission Error"
        notification.informativeText = message
        notification.soundName = NSUserNotificationDefaultSoundName
        
        NSUserNotificationCenter.default.deliver(notification)
    }
    
    private func showLimitedFeaturesNotification() {
        let notification = NSUserNotification()
        notification.title = "CompyMac"
        notification.subtitle = "Limited Features"
        notification.informativeText = "Running with limited features. Grant Accessibility permission to enable full automation."
        
        NSUserNotificationCenter.default.deliver(notification)
    }
}

// Simple logger for debugging
private class Logger {
    private let logFile: URL
    
    init() {
        let logDirectory = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask).first!
            .appendingPathComponent("Logs")
            .appendingPathComponent("CompyMac")
        
        try? FileManager.default.createDirectory(at: logDirectory, withIntermediateDirectories: true)
        
        logFile = logDirectory.appendingPathComponent("permission.log")
    }
    
    func log(_ message: String) {
        let timestamp = ISO8601DateFormatter().string(from: Date())
        let logMessage = "[\(timestamp)] \(message)\n"
        
        try? logMessage.data(using: .utf8)?.write(to: logFile, options: .atomic)
    }
}
