"""Mock PyObjC interfaces for development environment."""

import os
import shutil

class NSWorkspace:
    @classmethod
    def sharedWorkspace(cls):
        return NSWorkspace()
    
    def runningApplications(self):
        return []
    
    def launchApplication_(self, app_name):
        print(f"Mock: Would launch {app_name}")
        return True
        
    def frontmostApplication(self):
        return MockApplication()
        
    def openURL_(self, url):
        print(f"Mock: Opening URL {url}")
        return True

class MockApplication:
    def bundleIdentifier(self):
        return "com.apple.finder"
        
    def selection(self):
        return [MockFileItem()]

class MockFileItem:
    def path(self):
        return "/mock/path/to/file"

class NSFileManager:
    @classmethod
    def defaultManager(cls):
        return NSFileManager()
        
    def createDirectoryAtPath_withIntermediateDirectories_attributes_error_(
        self, path, create_intermediates, attributes, error):
        print(f"Mock: Creating directory at {path}")
        os.makedirs(path, exist_ok=True)
        return True
        
    def moveItemAtURL_toURL_error_(self, source_url, dest_url, error):
        print(f"Mock: Moving item from {source_url} to {dest_url}")
        src = source_url.replace('file://', '')
        dst = dest_url.replace('file://', '')
        import shutil
        shutil.move(src, dst)
        return True
        
    def isWritableFileAtPath_(self, path):
        return True
        
    def isReadableFileAtPath_(self, path):
        return True

class NSURL:
    @classmethod
    def fileURLWithPath_(cls, path):
        return f"file://{path}"

class AXUIElement:
    @staticmethod
    def createSystemWide():
        return AXUIElement()

# Export mock objects
Cocoa = type('Cocoa', (), {'NSWorkspace': NSWorkspace})
Foundation = type('Foundation', (), {
    'NSFileManager': NSFileManager,
    'NSURL': NSURL
})
Quartz = type('Quartz', (), {})
ApplicationServices = type('ApplicationServices', (), {
    'AXUIElementCreateSystemWide': AXUIElement.createSystemWide
})
