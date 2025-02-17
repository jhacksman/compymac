import Cocoa

class AccessibilityPermissionManager {
    static let shared = AccessibilityPermissionManager()
    
    private init() {}
    
    func checkAccessibilityPermission() -> Bool {
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true]
        let hasPermission = AXIsProcessTrustedWithOptions(options as CFDictionary)
        
        if !hasPermission {
            PermissionErrorHandler.shared.handlePermissionDenied()
        }
        
        return hasPermission
    }
    
    func requestAccessibilityPermission() {
        if !checkAccessibilityPermission() {
            showPermissionAlert()
        }
    }
    
    private func showPermissionAlert() {
        let alert = NSAlert()
        alert.messageText = "Accessibility Permission Required"
        alert.informativeText = """
            CompyMac needs Accessibility permission to automate actions in other applications.
            
            1. Click 'Open System Settings'
            2. Click the lock icon to make changes
            3. Enable CompyMac in the list
            
            This permission is required for automation features to work properly.
            """
        alert.alertStyle = .informational
        alert.addButton(withTitle: "Open System Settings")
        alert.addButton(withTitle: "Later")
        
        if alert.runModal() == .alertFirstButtonReturn {
            openAccessibilityPreferences()
        }
    }
    
    private func openAccessibilityPreferences() {
        let prefpaneUrl = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!
        NSWorkspace.shared.open(prefpaneUrl)
    }
    
    func monitorPermissionStatus(callback: @escaping (Bool) -> Void) {
        // Check permission status periodically
        Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { timer in
            let hasPermission = self.checkAccessibilityPermission()
            callback(hasPermission)
            
            if hasPermission {
                timer.invalidate()
            }
        }
    }
}
