import Cocoa

class PermissionGuideWindow: NSWindow {
    convenience init() {
        let contentRect = NSRect(x: 0, y: 0, width: 500, height: 400)
        self.init(
            contentRect: contentRect,
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false)
        
        title = "Accessibility Permission Guide"
        let newContentView = NSView(frame: contentRect)
        newContentView.wantsLayer = true
        newContentView.layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
        self.contentView = newContentView
        
        setupUI()
        center()
        isReleasedWhenClosed = false
    }
    
    private func setupUI() {
        let stackView = NSStackView(frame: NSRect(x: 20, y: 20, width: 460, height: 360))
        stackView.orientation = .vertical
        stackView.alignment = .leading
        stackView.spacing = 16
        
        // Title
        let titleLabel = NSTextField(labelWithString: "How to Enable Accessibility Permission")
        titleLabel.font = .boldSystemFont(ofSize: 16)
        
        // Instructions
        let instructionsLabel = NSTextField(wrappingLabelWithString: """
            CompyMac requires Accessibility permission to automate actions in other applications. Follow these steps to grant permission:
            
            1. Click 'Open System Settings' below or in the menu bar
            2. Navigate to Privacy & Security > Accessibility
            3. Click the lock icon in the bottom left to make changes
            4. Find 'CompyMac' in the list and enable it
            5. Return to CompyMac - the status icon will update automatically
            
            Note: This permission is required for all automation features to work properly. CompyMac will only use these permissions for the automation tasks you request.
            """)
        
        // Open Settings Button
        let openButton = NSButton(title: "Open System Settings", target: self, action: #selector(openSettings))
        openButton.bezelStyle = .rounded
        
        stackView.addArrangedSubview(titleLabel)
        stackView.addArrangedSubview(instructionsLabel)
        stackView.addArrangedSubview(openButton)
        
        contentView.addSubview(stackView)
        self.contentView = contentView
    }
    
    @objc private func openSettings() {
        AccessibilityPermissionManager.shared.requestAccessibilityPermission()
    }
}
