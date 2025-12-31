"""
FastAPI server for CompyMac Interactive UI.

This server provides:
- WebSocket endpoint for real-time communication with the agent
- REST endpoints for session management
- Integration with the CompyMac agent loop and local harness
- Real tool execution (CLI, Browser, Todos)
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from compymac.browser import BrowserConfig, BrowserMode, BrowserService
from compymac.config import LLMConfig
from compymac.harness import HarnessConfig
from compymac.llm import ChatResponse, LLMClient
from compymac.local_harness import LocalHarness
from compymac.types import ToolCall

logger = logging.getLogger(__name__)

app = FastAPI(title="CompyMac API", version="0.2.0")

# Enable CORS for the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Screenshot directory for browser screenshots
SCREENSHOT_DIR = Path("/tmp/compymac_screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files for serving screenshots
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOT_DIR)), name="screenshots")


@dataclass
class SessionRuntime:
    """Runtime state for a session including harness and tools."""
    session_id: str
    harness: LocalHarness
    llm_client: LLMClient
    browser_service: BrowserService | None = None
    browser_control: str = "user"  # "user" or "agent"
    messages: list[dict[str, Any]] = field(default_factory=list)
    todos: list[dict[str, Any]] = field(default_factory=list)
    terminal_output: list[dict[str, Any]] = field(default_factory=list)
    browser_state: dict[str, Any] | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


# Session storage
sessions: dict[str, SessionRuntime] = {}
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


def create_session_runtime(session_id: str) -> SessionRuntime:
    """Create a new session runtime with harness and tools."""
    harness_config = HarnessConfig()
    harness = LocalHarness(config=harness_config)
    llm_client = get_llm_client()

    return SessionRuntime(
        session_id=session_id,
        harness=harness,
        llm_client=llm_client,
    )


async def send_event(websocket: WebSocket, event_type: str, data: dict[str, Any]) -> None:
    """Send an event to the WebSocket client."""
    await websocket.send_json({
        "type": "event",
        "event": {"type": event_type, **data},
    })


async def initialize_browser(runtime: SessionRuntime) -> BrowserService:
    """Initialize browser service for a session."""
    if runtime.browser_service is None:
        config = BrowserConfig(
            mode=BrowserMode.HEADLESS,
            capture_screenshots=True,
            screenshot_dir=str(SCREENSHOT_DIR),
        )
        runtime.browser_service = BrowserService(config)
        await runtime.browser_service.initialize()
    return runtime.browser_service


async def get_browser_state(runtime: SessionRuntime) -> dict[str, Any]:
    """Get current browser state with screenshot."""
    if runtime.browser_service is None:
        return {
            "url": "",
            "title": "No browser session",
            "screenshot_url": None,
            "elements": [],
        }

    try:
        action = await runtime.browser_service.get_page_content()
        if action.page_state:
            screenshot_url = None
            if action.page_state.screenshot_path:
                filename = Path(action.page_state.screenshot_path).name
                screenshot_url = f"/screenshots/{filename}"

            return {
                "url": action.page_state.url,
                "title": action.page_state.title,
                "screenshot_url": screenshot_url,
                "elements": [e.to_dict() for e in action.page_state.elements[:20]],
            }
    except Exception as e:
        logger.error(f"Error getting browser state: {e}")

    return {
        "url": "",
        "title": "Error getting browser state",
        "screenshot_url": None,
        "elements": [],
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/sessions")
async def create_session() -> dict[str, Any]:
    """Create a new agent session."""
    session_id = str(uuid.uuid4())
    runtime = create_session_runtime(session_id)
    sessions[session_id] = runtime
    return {
        "id": session_id,
        "status": "running",
        "created_at": runtime.created_at,
    }


@app.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """Get session details."""
    if session_id not in sessions:
        return {"error": "Session not found"}
    runtime = sessions[session_id]
    return {
        "id": session_id,
        "status": "running",
        "created_at": runtime.created_at,
        "message_count": len(runtime.messages),
        "todo_count": len(runtime.todos),
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint for real-time agent communication."""
    await websocket.accept()
    active_connections[session_id] = websocket

    # Create or get session runtime
    if session_id not in sessions:
        sessions[session_id] = create_session_runtime(session_id)

    runtime = sessions[session_id]

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type", "")

            if msg_type == "send_message":
                await handle_send_message(websocket, runtime, message)

            elif msg_type == "subscribe":
                await handle_subscribe(websocket, runtime)

            elif msg_type == "run_command":
                await handle_run_command(websocket, runtime, message)

            elif msg_type == "browser_navigate":
                await handle_browser_navigate(websocket, runtime, message)

            elif msg_type == "browser_click":
                await handle_browser_click(websocket, runtime, message)

            elif msg_type == "browser_type":
                await handle_browser_type(websocket, runtime, message)

            elif msg_type == "browser_screenshot":
                await handle_browser_screenshot(websocket, runtime)

            elif msg_type == "browser_control":
                await handle_browser_control(websocket, runtime, message)

            elif msg_type == "todo_create":
                await handle_todo_create(websocket, runtime, message)

            elif msg_type == "todo_update":
                await handle_todo_update(websocket, runtime, message)

            elif msg_type == "get_state":
                await handle_get_state(websocket, runtime)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
        if session_id in active_connections:
            del active_connections[session_id]
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if session_id in active_connections:
            del active_connections[session_id]


async def handle_send_message(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle sending a message to the agent."""
    content = message.get("content", "")
    if not content:
        return

    # Add user message
    user_msg = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    }
    runtime.messages.append(user_msg)
    await send_event(websocket, "message_complete", {"message": user_msg})

    # Get LLM response
    try:
        chat_messages = [
            {"role": "system", "content": "You are CompyMac, an AI coding assistant. Be helpful and concise."},
        ]
        for msg in runtime.messages:
            chat_messages.append({"role": msg["role"], "content": msg["content"]})

        def call_llm(client: LLMClient, msgs: list[dict[str, str]]) -> ChatResponse:
            return client.chat(msgs)

        loop = asyncio.get_event_loop()
        response: ChatResponse = await loop.run_in_executor(
            None, call_llm, runtime.llm_client, chat_messages
        )

        # Add assistant message
        assistant_msg = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": response.content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        runtime.messages.append(assistant_msg)
        await send_event(websocket, "message_complete", {"message": assistant_msg})

    except Exception as e:
        logger.error(f"LLM error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "llm_error",
            "message": str(e),
        })


async def handle_subscribe(websocket: WebSocket, runtime: SessionRuntime) -> None:
    """Handle subscription request - send current state."""
    # Send message backfill
    await websocket.send_json({
        "type": "backfill",
        "events": [
            {"type": "message_complete", "message": msg}
            for msg in runtime.messages
        ],
    })

    # Send current todos
    await send_event(websocket, "todos_updated", {"todos": runtime.todos})

    # Send current terminal output
    await send_event(websocket, "terminal_output", {"lines": runtime.terminal_output})

    # Send browser state if available
    if runtime.browser_service:
        browser_state = await get_browser_state(runtime)
        await send_event(websocket, "browser_state", browser_state)

    # Send browser control state
    await send_event(websocket, "browser_control", {"control": runtime.browser_control})


async def handle_run_command(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle running a shell command."""
    command = message.get("command", "")
    exec_dir = message.get("exec_dir", "/home/ubuntu")

    if not command:
        return

    try:
        loop = asyncio.get_event_loop()

        def execute_bash() -> str:
            tool_call = ToolCall(
                id=str(uuid.uuid4()),
                name="bash",
                arguments={
                    "command": command,
                    "exec_dir": exec_dir,
                    "bash_id": "ui_terminal",
                },
            )
            result = runtime.harness.execute(tool_call)
            return result.content

        output = await loop.run_in_executor(None, execute_bash)

        # Add to terminal output
        terminal_entry = {
            "id": str(uuid.uuid4()),
            "command": command,
            "output": output,
            "timestamp": datetime.utcnow().isoformat(),
            "exit_code": 0,
        }
        runtime.terminal_output.append(terminal_entry)

        # Send terminal output event
        await send_event(websocket, "terminal_output", {
            "lines": runtime.terminal_output,
            "new_entry": terminal_entry,
        })

    except Exception as e:
        logger.error(f"Command execution error: {e}")
        error_entry = {
            "id": str(uuid.uuid4()),
            "command": command,
            "output": f"Error: {e}",
            "timestamp": datetime.utcnow().isoformat(),
            "exit_code": 1,
        }
        runtime.terminal_output.append(error_entry)
        await send_event(websocket, "terminal_output", {
            "lines": runtime.terminal_output,
            "new_entry": error_entry,
        })


async def handle_browser_navigate(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle browser navigation."""
    url = message.get("url", "")
    if not url:
        return

    try:
        browser = await initialize_browser(runtime)
        action = await browser.navigate(url)

        if action.success and action.page_state:
            screenshot_action = await browser.screenshot()
            screenshot_url = None
            if screenshot_action.success and screenshot_action.details.get("path"):
                filename = Path(screenshot_action.details["path"]).name
                screenshot_url = f"/screenshots/{filename}"

            browser_state = {
                "url": action.page_state.url,
                "title": action.page_state.title,
                "screenshot_url": screenshot_url,
                "elements": [e.to_dict() for e in action.page_state.elements[:20]],
            }
            runtime.browser_state = browser_state
            await send_event(websocket, "browser_state", browser_state)
        else:
            await websocket.send_json({
                "type": "error",
                "code": "browser_error",
                "message": action.error or "Navigation failed",
            })

    except Exception as e:
        logger.error(f"Browser navigation error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "browser_error",
            "message": str(e),
        })


async def handle_browser_click(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle browser click."""
    element_id = message.get("element_id")
    coordinates = message.get("coordinates")

    if not element_id and not coordinates:
        return

    try:
        browser = await initialize_browser(runtime)

        if element_id:
            action = await browser.click(element_id=element_id)
        else:
            action = await browser.click(coordinates=tuple(coordinates))

        if action.success:
            screenshot_action = await browser.screenshot()
            screenshot_url = None
            if screenshot_action.success and screenshot_action.details.get("path"):
                filename = Path(screenshot_action.details["path"]).name
                screenshot_url = f"/screenshots/{filename}"

            if action.page_state:
                browser_state = {
                    "url": action.page_state.url,
                    "title": action.page_state.title,
                    "screenshot_url": screenshot_url,
                    "elements": [e.to_dict() for e in action.page_state.elements[:20]],
                }
                runtime.browser_state = browser_state
                await send_event(websocket, "browser_state", browser_state)

    except Exception as e:
        logger.error(f"Browser click error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "browser_error",
            "message": str(e),
        })


async def handle_browser_type(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle browser typing."""
    element_id = message.get("element_id")
    text = message.get("text", "")
    press_enter = message.get("press_enter", False)

    if not element_id or not text:
        return

    try:
        browser = await initialize_browser(runtime)
        action = await browser.type_text(
            text=text,
            element_id=element_id,
            press_enter=press_enter,
        )

        if action.success and action.page_state:
            screenshot_action = await browser.screenshot()
            screenshot_url = None
            if screenshot_action.success and screenshot_action.details.get("path"):
                filename = Path(screenshot_action.details["path"]).name
                screenshot_url = f"/screenshots/{filename}"

            browser_state = {
                "url": action.page_state.url,
                "title": action.page_state.title,
                "screenshot_url": screenshot_url,
                "elements": [e.to_dict() for e in action.page_state.elements[:20]],
            }
            runtime.browser_state = browser_state
            await send_event(websocket, "browser_state", browser_state)

    except Exception as e:
        logger.error(f"Browser type error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "browser_error",
            "message": str(e),
        })


async def handle_browser_screenshot(websocket: WebSocket, runtime: SessionRuntime) -> None:
    """Handle browser screenshot request."""
    try:
        browser = await initialize_browser(runtime)
        action = await browser.screenshot()

        if action.success and action.details.get("path"):
            filename = Path(action.details["path"]).name
            screenshot_url = f"/screenshots/{filename}"

            page_action = await browser.get_page_content()
            if page_action.page_state:
                browser_state = {
                    "url": page_action.page_state.url,
                    "title": page_action.page_state.title,
                    "screenshot_url": screenshot_url,
                    "elements": [e.to_dict() for e in page_action.page_state.elements[:20]],
                }
                runtime.browser_state = browser_state
                await send_event(websocket, "browser_state", browser_state)

    except Exception as e:
        logger.error(f"Browser screenshot error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "browser_error",
            "message": str(e),
        })


async def handle_browser_control(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle browser control handoff (user/agent)."""
    control = message.get("control", "user")
    if control not in ("user", "agent"):
        return

    runtime.browser_control = control
    await send_event(websocket, "browser_control", {"control": control})


async def handle_todo_create(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle creating a new todo."""
    content = message.get("content", "")
    if not content:
        return

    todo = {
        "id": str(uuid.uuid4()),
        "content": content,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }
    runtime.todos.append(todo)
    await send_event(websocket, "todos_updated", {"todos": runtime.todos})


async def handle_todo_update(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle updating a todo."""
    todo_id = message.get("id")
    status = message.get("status")

    if not todo_id:
        return

    for todo in runtime.todos:
        if todo["id"] == todo_id:
            if status:
                todo["status"] = status
            todo["updated_at"] = datetime.utcnow().isoformat()
            break

    await send_event(websocket, "todos_updated", {"todos": runtime.todos})


async def handle_get_state(websocket: WebSocket, runtime: SessionRuntime) -> None:
    """Handle request for full state."""
    browser_state = None
    if runtime.browser_service:
        browser_state = await get_browser_state(runtime)

    await websocket.send_json({
        "type": "state",
        "data": {
            "messages": runtime.messages,
            "todos": runtime.todos,
            "terminal_output": runtime.terminal_output,
            "browser_state": browser_state,
            "browser_control": runtime.browser_control,
        },
    })


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
