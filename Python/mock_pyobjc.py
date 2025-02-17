"""Mock PyObjC interfaces for development environment."""

class NSWorkspace:
    @classmethod
    def sharedWorkspace(cls):
        return NSWorkspace()
    
    def runningApplications(self):
        return []
    
    def launchApplication_(self, app_name):
        print(f"Mock: Would launch {app_name}")
        return True

class AXUIElement:
    @staticmethod
    def createSystemWide():
        return AXUIElement()

# Export mock objects
Cocoa = type('Cocoa', (), {'NSWorkspace': NSWorkspace})
Quartz = type('Quartz', (), {})
ApplicationServices = type('ApplicationServices', (), {
    'AXUIElementCreateSystemWide': AXUIElement.createSystemWide
})
