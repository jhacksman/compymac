"""Mock WebSocket server for testing."""

import asyncio
import json
import os
import websockets
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from ..memory.protocol import MemoryMessage

class MockWebSocketServer:
    """Mock WebSocket server for testing memory operations."""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        """Initialize mock server.
        
        Args:
            host: Server host (default: localhost)
            port: Server port (default: 8765)
        """
        self.host = host
        self.port = port
        self.server = None
        self.memories = {}  # In-memory storage for testing
        self.next_id = 1
        
    def start(self):
        """Start the WebSocket server."""
        import threading
        import websockets.sync.server as ws_server
        
        def run_server():
            try:
                # Create WebSocket server
                with ws_server.serve(
                    self.handle_connection,
                    self.host,
                    self.port,
                    ping_interval=None,  # Disable ping/pong
                    ping_timeout=None
                ) as server:
                    self.server = server
                    server.serve_forever()
            except Exception as e:
                print(f"Server error: {str(e)}")
                
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        # Give server time to start
        import time
        time.sleep(3)  # Increased wait time for server startup
    
    def stop(self):
        """Stop the WebSocket server."""
        if hasattr(self, 'server'):
            self.server.shutdown()
        if hasattr(self, 'server_thread'):
            self.server_thread.join(timeout=1.0)
    
    def handle_connection(self, websocket):
        """Handle WebSocket connection.
        
        Args:
            websocket: WebSocket connection
        """
        try:
            while True:
                try:
                    message = websocket.recv()
                    print(f"Received message: {message}")  # Debug logging
                    request = json.loads(message)
                    action = request.get("action")
                    
                    if action == "store_memory":
                        response = self._handle_store_memory(request)
                    elif action == "retrieve_context":
                        response = self._handle_retrieve_context(request)
                    elif action == "update_memory":
                        response = self._handle_update_memory(request)
                    elif action == "delete_memory":
                        response = self._handle_delete_memory(request)
                    elif action == "desktop_create_folder":
                        path = request.get("path")
                        try:
                            os.makedirs(path, exist_ok=True)
                            response = {
                                "action": "desktop_create_folder",
                                "status": "success"
                            }
                        except Exception as e:
                            response = {
                                "action": "desktop_create_folder",
                                "status": "error",
                                "message": str(e)
                            }
                    else:
                        response = {
                            "status": "error",
                            "message": f"Unknown action: {action}"
                        }
                    
                    print(f"Sending response: {json.dumps(response)}")  # Debug logging
                    websocket.send(json.dumps(response))
                    
                except json.JSONDecodeError as e:
                    error_response = {
                        "status": "error",
                        "message": f"Invalid JSON format: {str(e)}"
                    }
                    websocket.send(json.dumps(error_response))
                except Exception as e:
                    error_response = {
                        "status": "error",
                        "message": f"Internal server error: {str(e)}"
                    }
                    websocket.send(json.dumps(error_response))
                    
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")  # Debug logging
    
    def _handle_store_memory(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle store_memory action.
        
        Args:
            request: Request data
            
        Returns:
            Response data
        """
        try:
            if "content" not in request:
                return {
                    "status": "error",
                    "message": "Missing required field: content"
                }
            
            memory_id = str(self.next_id)
            self.next_id += 1
            
            memory = {
                "id": memory_id,
                "content": request["content"],
                "metadata": request.get("metadata", {}),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.memories[memory_id] = memory
            
            return {
                "status": "success",
                **memory
            }
        except KeyError as e:
            return {
                "status": "error",
                "message": f"Missing required field: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to store memory: {str(e)}"
            }
    
    def _handle_retrieve_context(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle retrieve_context action.
        
        Args:
            request: Request data
            
        Returns:
            Response data
        """
        try:
            # Simple mock implementation - return all memories
            memories = list(self.memories.values())
            return {
                "status": "success",
                "memories": memories
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _handle_update_memory(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle update_memory action.
        
        Args:
            request: Request data
            
        Returns:
            Response data
        """
        try:
            memory_id = request["memory_id"]
            if memory_id not in self.memories:
                return {
                    "status": "error",
                    "message": "Memory not found"
                }
            
            memory = self.memories[memory_id]
            updates = request["updates"]
            
            if "content" in updates:
                memory["content"] = updates["content"]
            if "metadata" in updates:
                memory["metadata"].update(updates["metadata"])
            
            return {
                "status": "success",
                **memory
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _handle_delete_memory(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_memory action.
        
        Args:
            request: Request data
            
        Returns:
            Response data
        """
        try:
            memory_id = request["memory_id"]
            if memory_id not in self.memories:
                return {
                    "status": "error",
                    "message": "Memory not found"
                }
            
            del self.memories[memory_id]
            return {
                "status": "success"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
