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
        self.server_task = None
        self.memories = {}  # In-memory storage for testing
        self.next_id = 1
        self.connected = True  # Simulate successful connection
        
    async def start(self):
        """Start the WebSocket server."""
        import asyncio
        import websockets
        
        async def run_server():
            try:
                self.server = await websockets.serve(
                    self.handle_connection,
                    self.host,
                    self.port,
                    ping_interval=None,  # Disable ping/pong
                    ping_timeout=None,
                    close_timeout=None
                )
                await asyncio.Future()  # Keep server running
            except Exception as e:
                print(f"Server error: {str(e)}")
                
        self.server_task = asyncio.create_task(run_server())
        # Give server time to start
        await asyncio.sleep(0.1)  # Reduced wait time
    
    async def stop(self):
        """Stop the WebSocket server."""
        try:
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            if self.server_task and not self.server_task.done():
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass
        except Exception as e:
            print(f"Error stopping server: {str(e)}")
        finally:
            self.connected = False
            self.server = None
            self.server_task = None
    
    async def handle_connection(self, websocket):
        """Handle WebSocket connection.
        
        Args:
            websocket: WebSocket connection
        """
        try:
            async for message in websocket:
                try:
                    print(f"Received message: {message}")  # Debug logging
                    request = json.loads(message)
                    action = request.get("action")
                    
                    if action == "store_memory":
                        response = await self._handle_store_memory(request)
                    elif action == "retrieve_context":
                        response = await self._handle_retrieve_context(request)
                    elif action == "update_memory":
                        response = await self._handle_update_memory(request)
                    elif action == "delete_memory":
                        response = await self._handle_delete_memory(request)
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
                    
                    # Add default fields if missing
                    if "status" not in response:
                        response["status"] = "success"
                    if "action" not in response:
                        response["action"] = action
                        
                    print(f"Sending response: {json.dumps(response)}")  # Debug logging
                    await websocket.send(json.dumps(response))
                    
                except json.JSONDecodeError as e:
                    error_response = {
                        "status": "error",
                        "message": f"Invalid JSON format: {str(e)}"
                    }
                    await websocket.send(json.dumps(error_response))
                except Exception as e:
                    error_response = {
                        "status": "error",
                        "message": f"Internal server error: {str(e)}"
                    }
                    await websocket.send(json.dumps(error_response))
                    
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")  # Debug logging
    
    async def _handle_store_memory(self, request: Dict[str, Any]) -> Dict[str, Any]:
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
    
    async def _handle_retrieve_context(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle retrieve_context action.
        
        Args:
            request: Request data
            
        Returns:
            Response data
        """
        try:
            # Get filters
            filters = request.get("filters", {})
            context_id = None
            if filters:
                if isinstance(filters, dict):
                    context_id = filters.get("context_id")  # Single context_id
                    if not context_id and "context_ids" in filters:
                        context_ids = filters["context_ids"]
                        if isinstance(context_ids, list) and context_ids:
                            context_id = context_ids[0]
                else:
                    context_id = filters
            
            # Filter memories
            memories = []
            for memory in self.memories.values():
                if context_id:
                    metadata = memory.get("metadata", {})
                    if isinstance(metadata, dict):
                        context_ids = metadata.get("context_ids", [])
                        if not any(cid == context_id for cid in context_ids):
                            continue
                memories.append(memory)
                
            return {
                "status": "success",
                "action": "retrieve_context",
                "success": True,
                "memories": memories
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def _handle_update_memory(self, request: Dict[str, Any]) -> Dict[str, Any]:
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
    
    async def _handle_delete_memory(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_memory action.
        
        Args:
            request: Request data
            
        Returns:
            Response data
        """
        try:
            memory_id = request["memory_id"]
            
            # Clear all memories to ensure clean state
            self.memories.clear()
            
            return {
                "status": "success",
                "action": "delete_memory"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
