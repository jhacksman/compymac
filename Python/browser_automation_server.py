import asyncio
import json
from websockets import serve
from playwright.sync_api import sync_playwright

class BrowserAutomationServer:
    def __init__(self):
        self.playwright = None
        self.browser = None
    
    async def start_server(self):
        async with serve(self.handle_client_message, "localhost", 8765):
            print("Browser automation server listening on ws://localhost:8765")
            await asyncio.Future()  # run forever
    
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
        if action == "openPage":
            url = params.get("url")
            if not url:
                return {
                    "action": "openPage",
                    "status": "error",
                    "message": "URL not specified"
                }
            
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(url)
                    title = page.title()
                    browser.close()
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

if __name__ == "__main__":
    server = BrowserAutomationServer()
    asyncio.run(server.start_server())
