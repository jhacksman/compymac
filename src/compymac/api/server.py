"""
FastAPI server for CompyMac Interactive UI.

This server provides:
- WebSocket endpoint for real-time communication with the agent
- REST endpoints for session management
- Integration with the CompyMac LLM client
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from compymac.config import LLMConfig
from compymac.llm import ChatResponse, LLMClient

logger = logging.getLogger(__name__)

app = FastAPI(title="CompyMac API", version="0.1.0")

# Enable CORS for the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage (for MVP - would use PostgreSQL in production)
sessions: dict[str, dict[str, Any]] = {}
active_connections: dict[str, WebSocket] = {}


def get_llm_client() -> LLMClient:
    """Create an LLM client with configuration from environment."""
    config = LLMConfig(
        model=os.environ.get("LLM_MODEL", "qwen3-235b-a22b-instruct-2507"),
        base_url=os.environ.get("LLM_BASE_URL", "https://api.venice.ai/api/v1"),
        api_key=os.environ.get("LLM_API_KEY", ""),
        temperature=0.0,
        max_tokens=4096,
    )
    return LLMClient(config=config, validate_config=True)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/sessions")
async def create_session() -> dict[str, Any]:
    """Create a new agent session."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "id": session_id,
        "status": "running",
        "messages": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    return sessions[session_id]


@app.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """Get session details."""
    if session_id not in sessions:
        return {"error": "Session not found"}
    return sessions[session_id]


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint for real-time agent communication."""
    await websocket.accept()
    active_connections[session_id] = websocket

    # Create or get session
    if session_id not in sessions:
        sessions[session_id] = {
            "id": session_id,
            "status": "running",
            "messages": [],
            "created_at": datetime.utcnow().isoformat(),
        }

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "send_message":
                content = message.get("content", "")
                if content:
                    # Add user message to session
                    user_msg = {
                        "id": str(uuid.uuid4()),
                        "role": "user",
                        "content": content,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    sessions[session_id]["messages"].append(user_msg)

                    # Send acknowledgment
                    await websocket.send_json({
                        "type": "event",
                        "event": {"type": "message_complete", "message": user_msg},
                    })

                    # Get LLM response
                    try:
                        llm = get_llm_client()
                        chat_messages = [
                            {"role": "system", "content": "You are CompyMac, an AI coding assistant. Be helpful and concise."},
                        ]
                        for msg in sessions[session_id]["messages"]:
                            chat_messages.append({"role": msg["role"], "content": msg["content"]})

                        # Run LLM call in thread pool to not block
                        # Use a helper function to avoid B023 lint error
                        def call_llm(client: LLMClient, msgs: list[dict[str, str]]) -> ChatResponse:
                            return client.chat(msgs)

                        loop = asyncio.get_event_loop()
                        response: ChatResponse = await loop.run_in_executor(
                            None, call_llm, llm, chat_messages
                        )

                        # Add assistant message to session
                        assistant_msg = {
                            "id": str(uuid.uuid4()),
                            "role": "assistant",
                            "content": response.content,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        sessions[session_id]["messages"].append(assistant_msg)

                        # Send response to client
                        await websocket.send_json({
                            "type": "event",
                            "event": {"type": "message_complete", "message": assistant_msg},
                        })

                        llm.close()

                    except Exception as e:
                        logger.error(f"LLM error: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "code": "llm_error",
                            "message": str(e),
                        })

            elif message.get("type") == "subscribe":
                # Send backfill of existing messages
                await websocket.send_json({
                    "type": "backfill",
                    "events": [
                        {"type": "message_complete", "message": msg}
                        for msg in sessions[session_id]["messages"]
                    ],
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
        if session_id in active_connections:
            del active_connections[session_id]
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if session_id in active_connections:
            del active_connections[session_id]


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
