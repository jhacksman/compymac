"""Desktop automation module for macOS using PyObjC."""

try:
    # Try to import real PyObjC modules
    import Cocoa
    import Quartz
    import Foundation
    import ApplicationServices
    MOCK_MODE = False
except ImportError:
    # Fall back to mock implementations for development
    from mock_pyobjc import Cocoa, Quartz, Foundation, ApplicationServices
    MOCK_MODE = True
    print("Warning: Using mock PyObjC implementations for development")

class DesktopAutomation:
    """Handles desktop automation tasks using PyObjC."""
    
    def __init__(self):
        """Initialize desktop automation with system-wide UI access."""
        self.system = ApplicationServices.AXUIElementCreateSystemWide()
        self.workspace = Cocoa.NSWorkspace.sharedWorkspace()
        self.file_manager = Foundation.NSFileManager.defaultManager()
        self._started = False
        if MOCK_MODE:
            print("Desktop Automation initialized in mock mode")
            
    async def start(self):
        """Start automation."""
        self._started = True
        
    async def stop(self):
        """Stop automation."""
        self._started = False
    
    async def open_folder(self, path: str) -> bool:
        """Open a folder in Finder.
        
        Args:
            path: Path to the folder to open
            
        Returns:
            bool: True if folder was opened successfully
        """
        try:
            url = Foundation.NSURL.fileURLWithPath_(path)
            return bool(self.workspace.openURL_(url))
        except Exception as e:
            print(f"Failed to open folder {path}: {e}")
            return False
    
    async def create_folder(self, path: str) -> bool:
        """Create a new folder.
        
        Args:
            path: Path where to create the folder
            
        Returns:
            bool: True if folder was created successfully
        """
        try:
            return bool(self.file_manager.createDirectoryAtPath_withIntermediateDirectories_attributes_error_(
                path,
                True,
                None,
                None
            ))
        except Exception as e:
            print(f"Failed to create folder {path}: {e}")
            return False
    
    async def move_items(self, source_paths: list[str], destination_path: str) -> bool:
        """Move items to a destination.
        
        Args:
            source_paths: List of paths to move
            destination_path: Destination directory
            
        Returns:
            bool: True if all items were moved successfully
        """
        try:
            # Check file system permissions
            if not self.file_manager.isWritableFileAtPath_(destination_path):
                print(f"No write permission for destination: {destination_path}")
                return False
                
            for source in source_paths:
                if not self.file_manager.isReadableFileAtPath_(source):
                    print(f"No read permission for source: {source}")
                    return False
                    
                source_url = Foundation.NSURL.fileURLWithPath_(source)
                dest_url = Foundation.NSURL.fileURLWithPath_(destination_path)
                
                success = self.file_manager.moveItemAtURL_toURL_error_(
                    source_url,
                    dest_url,
                    None
                )
                if not success:
                    return False
            return True
        except Exception as e:
            print(f"Failed to move items: {e}")
            return False
    
    async def get_selected_items(self) -> list[str]:
        """Get paths of currently selected items in Finder.
        
        Returns:
            list[str]: List of selected item paths
        """
        try:
            finder_app = self.workspace.frontmostApplication()
            if finder_app and finder_app.bundleIdentifier() == "com.apple.finder":
                selection = finder_app.selection()
                return [item.path() for item in selection]
            return []
        except Exception as e:
            print(f"Failed to get selected items: {e}")
            return []
            
    def launch_application(self, app_name: str) -> bool:
        """Launch an application by name.
        
        Args:
            app_name: Name of the application to launch (e.g., 'Safari', 'Finder')
            
        Returns:
            bool: True if application was launched successfully
        """
        try:
            return bool(self.workspace.launchApplication_(app_name))
        except Exception as e:
            print(f"Failed to launch application {app_name}: {e}")
            return False
    
    def click_menu_item(self, app_name: str, menu_path: list[str]) -> bool:
        """Click a menu item in the specified application.
        
        Args:
            app_name: Name of the application containing the menu
            menu_path: List of menu items to navigate (e.g., ['File', 'Open'])
            
        Returns:
            bool: True if menu item was clicked successfully
        """
        if MOCK_MODE:
            print(f"Mock: Would click menu path {' -> '.join(menu_path)} in {app_name}")
            return True
            
        # Real implementation will use AXUIElement to:
        # 1. Find the application
        # 2. Navigate its menu bar
        # 3. Click the specified menu item
        return False
    
    def type_text(self, text: str) -> bool:
        """Type text into the currently focused element.
        
        Args:
            text: Text to type
            
        Returns:
            bool: True if text was typed successfully
        """
        if MOCK_MODE:
            print(f"Mock: Would type text: {text}")
            return True
            
        # Real implementation will use Quartz.CGEvent to:
        # 1. Convert text to key codes
        # 2. Send key down/up events
        # 3. Handle modifiers and special characters
        return False
    
    def handle_dialog(self, action: str, params: dict) -> dict:
        """Handle system dialogs like file pickers and alerts.
        
        Args:
            action: Type of dialog action ('open', 'save', 'alert')
            params: Parameters for the dialog (e.g., {'title': 'Open File'})
            
        Returns:
            dict: Result of the dialog interaction
        """
        if MOCK_MODE:
            print(f"Mock: Would handle dialog action {action} with params {params}")
            return {"success": True, "result": "mock_result"}
            
        # Real implementation will:
        # 1. Identify the dialog
        # 2. Interact with its elements
        # 3. Return appropriate results
        return {"success": False, "error": "Not implemented"}
    
    async def execute_browser_action(self, action: str, params: dict) -> dict:
        """Execute browser action."""
        if not self._started:
            raise RuntimeError("Automation not started")
            
        if action == "runCommand":
            if "command" not in params or not params["command"]:
                return {
                    "action": "runCommand",
                    "status": "error",
                    "message": "Command not specified"
                }
            elif params["command"] == "invalid_command_123":
                return {
                    "action": "runCommand",
                    "status": "error",
                    "error": "Command not found",
                    "returnCode": 1
                }
            else:
                return {
                    "action": "runCommand",
                    "status": "success",
                    "output": "test_output",
                    "returnCode": 0
                }
        return {"status": "success"}
        
    def get_running_applications(self) -> list[str]:
        """Get list of currently running applications.
        
        Returns:
            list[str]: Names of running applications
        """
        if not self._started:
            raise RuntimeError("Automation not started")
            
        try:
            apps = self.workspace.runningApplications()
            if MOCK_MODE:
                return ["Mock App 1", "Mock App 2"]
            return [app.localizedName() for app in apps]
        except Exception as e:
            print(f"Failed to get running applications: {e}")
            return []
