import asyncio
import json
from websockets import serve
from playwright.async_api import async_playwright
from desktop_automation import DesktopAutomation

class BrowserAutomationServer:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.desktop = DesktopAutomation()
        self.server = None
        
    def __del__(self):
        """Cleanup browser resources."""
        self._cleanup_browser()
        
    def _cleanup_browser(self):
        """Clean up browser resources."""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    async def _setup_browser(self):
        """Initialize browser instance with Playwright."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.webkit.launch(headless=True)
            self.page = await self.browser.new_page()
        except Exception as e:
            print(f"Failed to initialize browser: {e}")
    
    async def start_server(self):
        if self.server:
            return
        await self._setup_browser()
        self.server = await serve(
            self.handle_client_message,
            "localhost",
            8765,
            reuse_port=True
        )
        print("Browser automation server listening on ws://localhost:8765")
    
    async def handle_client_message(self, websocket):
        print("Swift client connected")
        async for message in websocket:
            try:
                request = json.loads(message)
            except json.JSONDecodeError:
                error_response = {
                    "action": "unknown",
                    "status": "error",
                    "message": "Invalid JSON format"
                }
                await websocket.send(json.dumps(error_response))
                continue
            
            action = request.get("action")
            response = await self.execute_browser_action(action, request)
            await websocket.send(json.dumps(response))
    
    async def execute_browser_action(self, action: str, params: dict):
        if action.startswith("desktop_"):
            return await self.execute_desktop_action(action, params)
        elif action == "navigateBack":
            try:
                if not self.page:
                    return {
                        "action": "navigateBack",
                        "status": "error",
                        "message": "No active browser page"
                    }
                
                self.page.go_back()
                return {
                    "action": "navigateBack",
                    "status": "success",
                    "url": self.page.url
                }
            except Exception as e:
                return {
                    "action": "navigateBack",
                    "status": "error",
                    "message": str(e)
                }
                
        elif action == "navigateForward":
            try:
                if not self.page:
                    return {
                        "action": "navigateForward",
                        "status": "error",
                        "message": "No active browser page"
                    }
                
                self.page.go_forward()
                return {
                    "action": "navigateForward",
                    "status": "success",
                    "url": self.page.url
                }
            except Exception as e:
                return {
                    "action": "navigateForward",
                    "status": "error",
                    "message": str(e)
                }
                
        elif action == "refresh":
            try:
                if not self.page:
                    return {
                        "action": "refresh",
                        "status": "error",
                        "message": "No active browser page"
                    }
                
                self.page.reload()
                return {
                    "action": "refresh",
                    "status": "success",
                    "url": self.page.url
                }
            except Exception as e:
                return {
                    "action": "refresh",
                    "status": "error",
                    "message": str(e)
                }
                
        elif action == "openBrowser":
            url = params.get("url")
            if not url:
                return {
                    "action": "openBrowser",
                    "status": "error",
                    "message": "URL not specified"
                }
            
            try:
                if not self.page:
                    self._setup_browser()
                
                self.page.goto(url)
                title = self.page.title()
                
                return {
                    "action": "openBrowser",
                    "status": "success",
                    "title": title,
                    "url": url
                }
            except Exception as e:
                return {
                    "action": "openBrowser",
                    "status": "error",
                    "message": str(e)
                }
                
        elif action == "clickElement":
            selector = params.get("selector")
            if not selector:
                return {
                    "action": "clickElement",
                    "status": "error",
                    "message": "Selector not specified"
                }
            
            try:
                if not self.page:
                    return {
                        "action": "clickElement",
                        "status": "error",
                        "message": "No active browser page"
                    }
                
                self.page.click(selector)
                return {
                    "action": "clickElement",
                    "status": "success"
                }
            except Exception as e:
                return {
                    "action": "clickElement",
                    "status": "error",
                    "message": str(e)
                }
                
        elif action == "fillForm":
            fields = params.get("fields", {})
            if not fields:
                return {
                    "action": "fillForm",
                    "status": "error",
                    "message": "Form fields not specified"
                }
            
            try:
                if not self.page:
                    return {
                        "action": "fillForm",
                        "status": "error",
                        "message": "No active browser page"
                    }
                
                for selector, value in fields.items():
                    self.page.fill(selector, value)
                
                return {
                    "action": "fillForm",
                    "status": "success"
                }
            except Exception as e:
                return {
                    "action": "fillForm",
                    "status": "error",
                    "message": str(e)
                }
                
        elif action == "runCommand":
            command = params.get("command")
            if not command:
                return {
                    "action": "runCommand",
                    "status": "error",
                    "message": "Command not specified"
                }
            
            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                return {
                    "action": "runCommand",
                    "status": "success" if process.returncode == 0 else "error",
                    "output": stdout.decode() if stdout else "",
                    "error": stderr.decode() if stderr else "",
                    "returnCode": process.returncode
                }
            except Exception as e:
                return {
                    "action": "runCommand",
                    "status": "error",
                    "message": str(e)
                }
                
        elif action == "openPage":
            url = params.get("url")
            if not url:
                return {
                    "action": "openPage",
                    "status": "error",
                    "message": "URL not specified"
                }
            
            try:
                p = await async_playwright().start()
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url)
                title = await page.title()
                await browser.close()
                await p.stop()
                return {
                    "action": "openPage",
                    "status": "success",
                    "title": title
                }
            except Exception as e:
                return {
                    "action": "openPage",
                    "status": "error",
                    "message": str(e)
                }
        else:
            return {
                "action": action or "unknown",
                "status": "error",
                "message": "Unsupported action"
            }

    async def execute_desktop_action(self, action: str, params: dict):
        """Execute desktop automation actions.
        
        Args:
            action: The desktop action to perform (prefixed with 'desktop_')
            params: Parameters for the action
            
        Returns:
            dict: Response containing action status and results
        """
        try:
            if action == "desktop_open_folder":
                path = params.get("path")
                if not path:
                    return {
                        "action": action,
                        "status": "error",
                        "message": "Folder path not specified"
                    }
                success = await self.desktop.open_folder(path)
                return {
                    "action": action,
                    "status": "success" if success else "error",
                    "message": f"Folder {'opened' if success else 'failed to open'}"
                }
                
            elif action == "desktop_create_folder":
                path = params.get("path")
                if not path:
                    return {
                        "action": action,
                        "status": "error",
                        "message": "Folder path not specified"
                    }
                success = await self.desktop.create_folder(path)
                return {
                    "action": action,
                    "status": "success" if success else "error",
                    "message": f"Folder {'created' if success else 'failed to create'}"
                }
                
            elif action == "desktop_move_items":
                source_paths = params.get("source_paths", [])
                destination_path = params.get("destination_path")
                if not source_paths or not destination_path:
                    return {
                        "action": action,
                        "status": "error",
                        "message": "Source and destination paths required"
                    }
                success = await self.desktop.move_items(source_paths, destination_path)
                return {
                    "action": action,
                    "status": "success" if success else "error",
                    "message": f"Items {'moved' if success else 'failed to move'}"
                }
                
            elif action == "desktop_get_selected":
                try:
                    items = await self.desktop.get_selected_items()
                    return {
                        "action": action,
                        "status": "success",
                        "items": items
                    }
                except Exception as e:
                    return {
                        "action": action,
                        "status": "error",
                        "message": str(e)
                    }
                    
            elif action == "desktop_launch_app":
                app_name = params.get("app_name")
                if not app_name:
                    return {
                        "action": action,
                        "status": "error",
                        "message": "Application name not specified"
                    }
                success = self.desktop.launch_application(app_name)
                return {
                    "action": action,
                    "status": "success" if success else "error",
                    "message": f"Application {'launched' if success else 'failed to launch'}"
                }
            
            elif action == "desktop_click_menu":
                app_name = params.get("app_name")
                menu_path = params.get("menu_path", [])
                if not app_name or not menu_path:
                    return {
                        "action": action,
                        "status": "error",
                        "message": "Application name or menu path not specified"
                    }
                success = self.desktop.click_menu_item(app_name, menu_path)
                return {
                    "action": action,
                    "status": "success" if success else "error",
                    "message": f"Menu item {'clicked' if success else 'failed to click'}"
                }
            
            elif action == "desktop_type_text":
                text = params.get("text")
                if not text:
                    return {
                        "action": action,
                        "status": "error",
                        "message": "Text not specified"
                    }
                success = self.desktop.type_text(text)
                return {
                    "action": action,
                    "status": "success" if success else "error",
                    "message": f"Text {'typed' if success else 'failed to type'}"
                }
            
            elif action == "desktop_handle_dialog":
                dialog_action = params.get("dialog_action")
                dialog_params = params.get("dialog_params", {})
                if not dialog_action:
                    return {
                        "action": action,
                        "status": "error",
                        "message": "Dialog action not specified"
                    }
                result = self.desktop.handle_dialog(dialog_action, dialog_params)
                return {
                    "action": action,
                    "status": "success" if result.get("success") else "error",
                    "message": result.get("error", "Dialog handled successfully"),
                    "result": result.get("result")
                }
            
            else:
                return {
                    "action": action,
                    "status": "error",
                    "message": f"Unsupported desktop action: {action}"
                }
                
        except Exception as e:
            return {
                "action": action,
                "status": "error",
                "message": str(e)
            }
if __name__ == "__main__":
    server = BrowserAutomationServer()
    asyncio.run(server.start_server())
