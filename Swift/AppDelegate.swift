import Cocoa

@main
class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private var permissionManager: AccessibilityPermissionManager!
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        setupStatusItem()
        checkPermissions()
    }
    
    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "CompyMac"
        
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Check Permissions", action: #selector(checkPermissions), keyEquivalent: "p"))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        
        statusItem.menu = menu
    }
    
    @objc private func checkPermissions() {
        permissionManager = AccessibilityPermissionManager.shared
        
        // Request permission and monitor status
        permissionManager.requestAccessibilityPermission()
        permissionManager.monitorPermissionStatus { [weak self] hasPermission in
            self?.updateStatusItemUI(hasPermission: hasPermission)
        }
    }
    
    private func updateStatusItemUI(hasPermission: Bool) {
        DispatchQueue.main.async { [weak self] in
            if hasPermission {
                self?.statusItem.button?.title = "CompyMac ✓"
            } else {
                self?.statusItem.button?.title = "CompyMac ⚠️"
            }
        }
    }
}
