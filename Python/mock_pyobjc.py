"""Mock PyObjC interfaces for development environment."""

class NSObject:
    """Mock NSObject."""
    pass

class DesktopAutomation:
    """Mock DesktopAutomation."""
    async def start(self):
        pass
    
    async def stop(self):
        pass
    
    async def execute_browser_action(self, action, params):
        return {"status": "success"}
    
    async def create_folder(self, path):
        return True
    
    async def get_selected_items(self):
        return []

class NSWorkspace(NSObject):
    """Mock NSWorkspace."""
    @classmethod
    def sharedWorkspace(cls):
        return NSWorkspace()
    
    def runningApplications(self):
        return []
    
    def launchApplication_(self, app_name):
        print(f"Mock: Would launch {app_name}")
        return True
    
    def frontmostApplication(self):
        return None

class NSRunningApplication(NSObject):
    """Mock NSRunningApplication."""
    def activateWithOptions_(self, options):
        pass

class AXUIElement:
    """Mock AXUIElement."""
    @staticmethod
    def createSystemWide():
        return AXUIElement()

# Export mock objects
Cocoa = type('Cocoa', (), {
    'NSWorkspace': NSWorkspace,
    'NSRunningApplication': NSRunningApplication,
    'NSApplicationActivateIgnoringOtherApps': 1 << 0
})

Quartz = type('Quartz', (), {
    'CGWindowListCopyWindowInfo': lambda option, relativeToWindow: [],
    'kCGWindowListOptionOnScreenOnly': 1,
    'kCGNullWindowID': 0,
    'kCGWindowName': "kCGWindowName",
    'kCGWindowOwnerName': "kCGWindowOwnerName"
})

class NSFileManager:
    """Mock NSFileManager."""
    @classmethod
    def defaultManager(cls):
        return NSFileManager()
        
    def createDirectoryAtPath_withIntermediateDirectories_attributes_error_(
        self, path, create_intermediates, attributes, error
    ):
        return True
        
    def moveItemAtURL_toURL_error_(self, source_url, dest_url, error):
        return True
        
    def isWritableFileAtPath_(self, path):
        return True
        
    def isReadableFileAtPath_(self, path):
        return True

class NSURL:
    """Mock NSURL."""
    @classmethod
    def fileURLWithPath_(cls, path):
        return NSURL()
        
    def path(self):
        return "/mock/path"

class Foundation:
    """Mock Foundation module."""
    NSFileManager = NSFileManager
    NSURL = NSURL
    
    @staticmethod
    def NSMakeRect(x, y, w, h):
        return (x, y, w, h)

# Export mock objects
Cocoa = type('Cocoa', (), {
    'NSWorkspace': NSWorkspace,
    'NSRunningApplication': NSRunningApplication,
    'NSApplicationActivateIgnoringOtherApps': 1 << 0
})

Quartz = type('Quartz', (), {
    'CGWindowListCopyWindowInfo': lambda option, relativeToWindow: [],
    'kCGWindowListOptionOnScreenOnly': 1,
    'kCGNullWindowID': 0,
    'kCGWindowName': "kCGWindowName",
    'kCGWindowOwnerName': "kCGWindowOwnerName"
})

ApplicationServices = type('ApplicationServices', (), {
    'AXUIElementCreateSystemWide': AXUIElement.createSystemWide,
    'kAXErrorSuccess': 0,
    'kAXErrorCannotComplete': -25204
})
