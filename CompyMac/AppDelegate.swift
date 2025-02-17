import Cocoa

extension Notification.Name {
    static let showPermissionGuide = Notification.Name("showPermissionGuide")
}

@main
class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private var permissionManager: AccessibilityPermissionManager!
    private var permissionGuideWindow: PermissionGuideWindow!
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        setupStatusItem()
        setupNotifications()
        checkPermissions()
    }
    
    private func setupNotifications() {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(showPermissionGuide),
            name: .showPermissionGuide,
            object: nil
        )
    }
    
    @objc private func showPermissionGuide() {
        permissionGuideWindow.makeKeyAndOrderFront(nil)
    }
    
    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "CompyMac"
        
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Check Permissions", action: #selector(checkPermissions), keyEquivalent: "p"))
        menu.addItem(NSMenuItem(title: "Permission Guide", action: #selector(showPermissionGuide), keyEquivalent: "g"))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        
        // Create guide window but don't show it yet
        permissionGuideWindow = PermissionGuideWindow()
        
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
