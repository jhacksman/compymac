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
from typing import Annotated, Any

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from compymac.agent_loop import AgentConfig, AgentLoop
from compymac.browser import BrowserConfig, BrowserMode, BrowserService
from compymac.config import LLMConfig
from compymac.harness import HarnessConfig
from compymac.ingestion.chunker import DocumentChunker
from compymac.ingestion.parsers import DocumentParser
from compymac.llm import LLMClient
from compymac.local_harness import LocalHarness, ToolCategory
from compymac.session import Session
from compymac.storage.library_store import DocumentStatus, LibraryStore
from compymac.storage.run_store import RunStatus, RunStore
from compymac.types import ToolCall

logger = logging.getLogger(__name__)

# Global RunStore for session persistence
run_store = RunStore()

# Global LibraryStore for document management
library_store = LibraryStore()

# Upload directory for PDF files
UPLOAD_DIR = Path("/tmp/compymac_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

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


# System prompt for the agent that instructs it to create todo plans
AGENT_SYSTEM_PROMPT = """You are CompyMac, an AI coding assistant with access to tools.

## CRITICAL: Tool Usage Requirements

You MUST use tools for ALL actions. NEVER provide text-only responses when a tool can be used.

**Every response must include at least one tool call.** When asked to perform any action or retrieve information, you must:
1. Identify the appropriate tool(s) to use
2. Call the tool(s) with the correct parameters
3. Wait for the tool results before responding

Do NOT describe what you would do - actually DO it by calling the tools.

## Task Workflow

When given a task:
1. FIRST, create a todo list using TodoCreate for each step you plan to take
2. Before working on each step, call TodoStart with the todo ID
3. After completing a step, call TodoClaim with evidence
4. Use TodoVerify to verify completion when possible

Available tools include: Read, Edit, Write, bash, grep, glob, think, TodoCreate, TodoRead, TodoStart, TodoClaim, TodoVerify, librarian, and more.

## Document Library Tools

You have access to a document library containing uploaded PDFs and EPUBs. You MUST use the `librarian` tool to search and retrieve information. The librarian is a specialist agent that handles all library operations.

**IMPORTANT:** When asked about documents in your library, you MUST call the librarian tool. Do NOT guess or make assumptions about document content.

**Librarian Actions:**
- `list`: List all documents in the library with their IDs and metadata
- `activate`: Activate a document for searching (requires document_id)
- `deactivate`: Remove a document from active search sources (requires document_id)
- `status`: See which documents are currently active for search
- `search`: Search for relevant content across active documents (requires query)
- `get_content`: Get the full content of a specific document or page (requires document_id)
- `answer`: Search and synthesize an answer with citations (requires query)

**Example workflow:**
1. `librarian(action="list")` - see available documents (REQUIRED when asked about library contents)
2. `librarian(action="activate", document_id="...")` - enable a document for search
3. `librarian(action="answer", query="What does the document say about X?")` - get grounded answer with citations

The librarian returns structured JSON with answer, citations, excerpts, and actions_taken.

Be helpful, thorough, and always create a plan before executing. Remember: ALWAYS use tools, never just describe what you would do."""


@dataclass
class SessionRuntime:
    """Runtime state for a session including harness and tools."""
    session_id: str
    harness: LocalHarness
    llm_client: LLMClient
    agent_loop: AgentLoop | None = None
    browser_service: BrowserService | None = None
    browser_control: str = "user"  # "user" or "agent"
    messages: list[dict[str, Any]] = field(default_factory=list)
    terminal_output: list[dict[str, Any]] = field(default_factory=list)
    browser_state: dict[str, Any] | None = None
    created_at: str = ""
    _last_todo_version: int = 0  # Track todo changes
    # Human intervention state
    is_paused: bool = False
    pause_reason: str = ""
    audit_events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    def get_harness_todos(self) -> list[dict[str, Any]]:
        """Get todos from the harness (agent-created todos) with full audit info."""
        todos = self.harness.get_todos()
        return [
            {
                "id": todo.get("id", ""),
                "content": todo.get("content", ""),
                "status": todo.get("status", "pending"),
                "created_at": todo.get("created_at", ""),
                # Auditor-related fields
                "review_status": todo.get("review_status", "not_requested"),
                "explanation": todo.get("explanation", ""),
                "audit_attempts": todo.get("audit_attempts", 0),
                "revision_attempts": todo.get("revision_attempts", 0),
                "auditor_feedback": todo.get("auditor_feedback", ""),
                "human_notes": todo.get("human_notes", []),
            }
            for todo in todos
        ]

    def get_todo_version(self) -> int:
        """Get current todo version (for change detection)."""
        return self.harness.get_todo_version()

    def todos_changed(self) -> bool:
        """Check if todos have changed since last check."""
        current_version = self.get_todo_version()
        if current_version != self._last_todo_version:
            self._last_todo_version = current_version
            return True
        return False

    def has_todos(self) -> bool:
        """Check if any todos exist (for planning gate)."""
        return self.harness.has_todos()

    def log_audit_event(self, event_type: str, todo_id: str, details: dict[str, Any]) -> None:
        """Log an audit event for accountability."""
        self.audit_events.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "todo_id": todo_id,
            "details": details,
        })


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
    """Create a new session runtime with harness, agent loop, and tools."""
    harness_config = HarnessConfig()
    harness = LocalHarness(config=harness_config)

    # Enable TODO tools for the agent
    harness._active_toolset.enable_category(ToolCategory.TODO)

    # Enable Library tools for document search and retrieval (Phase 1 RAG integration)
    harness.register_library_tools(library_store, session_id)

    llm_client = get_llm_client()

    # Create agent config with system prompt
    agent_config = AgentConfig(
        max_steps=50,
        system_prompt=AGENT_SYSTEM_PROMPT,
        action_gated=False,  # Disabled - qwen3 model ignores tool_choice='required'
        require_complete_tool=True,  # Agent must call complete() to finish
        use_menu_system=True,  # Hierarchical tool menu - reduces initial tools to prevent analysis paralysis (arxiv:2504.00914)
        use_guided_templates=False,  # Disabled by default - adds prompt bloat (arxiv:2510.05381)
        guided_template_retry=False,  # Disabled with guided templates
    )

    # Create agent loop
    agent_loop = AgentLoop(
        harness=harness,
        llm_client=llm_client,
        config=agent_config,
    )

    return SessionRuntime(
        session_id=session_id,
        harness=harness,
        llm_client=llm_client,
        agent_loop=agent_loop,
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

            # Human intervention handlers
            elif msg_type == "pause_session":
                await handle_pause_session(websocket, runtime, message)

            elif msg_type == "resume_session":
                await handle_resume_session(websocket, runtime, message)

            elif msg_type == "todo_approve":
                await handle_todo_approve(websocket, runtime, message)

            elif msg_type == "todo_reject":
                await handle_todo_reject(websocket, runtime, message)

            elif msg_type == "todo_add_note":
                await handle_todo_add_note(websocket, runtime, message)

            elif msg_type == "todo_edit":
                await handle_todo_edit(websocket, runtime, message)

            elif msg_type == "todo_delete":
                await handle_todo_delete(websocket, runtime, message)

            elif msg_type == "get_audit_log":
                await handle_get_audit_log(websocket, runtime, message)

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
    """Handle sending a message to the agent using AgentLoop.

    Implements agent-driven todos like Manus/Devin:
    1. Planning gate: Agent must create todos before executing other tools
    2. Proper termination: Check harness.is_completion_signaled() after each step
    3. Real-time streaming: Broadcast todo updates as agent works
    """
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

    # Run agent loop with streaming updates
    try:
        if runtime.agent_loop is None:
            raise ValueError("Agent loop not initialized")

        # Add user message to agent loop
        runtime.agent_loop.add_user_message(content)

        # Send initial "agent working" event with planning phase
        await send_event(websocket, "agent_status", {"status": "planning"})

        # Run agent steps until completion
        loop = asyncio.get_event_loop()
        max_steps = runtime.agent_loop.config.max_steps
        planning_phase = True  # Start in planning phase
        planning_reminder_sent = False

        # Collect citations from librarian tool results
        collected_citations: list[dict[str, Any]] = []

        while runtime.agent_loop.state.step_count < max_steps:
            # Run one step in executor (blocking LLM call)
            def run_step() -> tuple[str | None, list]:
                return runtime.agent_loop.run_step()

            text_response, tool_results = await loop.run_in_executor(None, run_step)

            # Extract citations from librarian tool results
            for result in tool_results:
                if result.success and result.content:
                    try:
                        # Try to parse as JSON (librarian returns JSON)
                        result_data = json.loads(result.content)
                        if isinstance(result_data, dict) and "citations" in result_data:
                            citations = result_data.get("citations", [])
                            if isinstance(citations, list):
                                collected_citations.extend(citations)
                    except (json.JSONDecodeError, TypeError):
                        # Not JSON or not a librarian result, skip
                        pass

            # Check for todo changes and broadcast
            if runtime.todos_changed():
                todos = runtime.get_harness_todos()
                await send_event(websocket, "todos_updated", {"todos": todos})

                # If we now have todos, transition from planning to executing
                if planning_phase and runtime.has_todos():
                    planning_phase = False
                    await send_event(websocket, "agent_status", {"status": "executing"})

            # Planning gate: If still in planning phase after first step and no todos,
            # inject a reminder to create todos (like Manus/Devin pattern)
            if planning_phase and runtime.agent_loop.state.step_count >= 2 and not runtime.has_todos():
                if not planning_reminder_sent:
                    # Add system message to remind agent to create todos
                    runtime.agent_loop.add_system_message(
                        "REMINDER: You must create a todo plan before proceeding. "
                        "Use TodoCreate to create at least one todo item describing your plan. "
                        "Do not execute other tools until you have created your plan."
                    )
                    planning_reminder_sent = True

            # Check for completion using harness signal (fixes termination bug)
            if runtime.harness.is_completion_signaled():
                # Get the completion answer
                completion_answer = runtime.harness.get_completion_answer()
                if completion_answer:
                    runtime.agent_loop.state.final_response = completion_answer
                runtime.agent_loop.state.is_complete = True
                runtime.harness.reset_completion_signal()
                break

            # Also check agent loop's own completion flag
            if runtime.agent_loop.state.is_complete:
                break

            # If we got a text response with no tool calls in non-action-gated mode
            if text_response is not None and not tool_results:
                if not runtime.agent_loop.config.action_gated:
                    break

            # Small delay to allow UI updates
            await asyncio.sleep(0.1)

        # Get final response
        final_response = runtime.agent_loop.state.final_response
        if not final_response and runtime.agent_loop.state.messages:
            # Get last assistant message content
            for msg in reversed(runtime.agent_loop.state.messages):
                if msg.role == "assistant" and msg.content:
                    final_response = msg.content
                    break

        # Add assistant message with citations if any were collected
        assistant_msg: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": final_response or "Task completed.",
            "timestamp": datetime.utcnow().isoformat(),
        }
        if collected_citations:
            assistant_msg["citations"] = collected_citations
        runtime.messages.append(assistant_msg)
        await send_event(websocket, "message_complete", {"message": assistant_msg})

        # Send final todo state
        todos = runtime.get_harness_todos()
        await send_event(websocket, "todos_updated", {"todos": todos})

        # Send agent done status
        await send_event(websocket, "agent_status", {"status": "idle"})

    except Exception as e:
        logger.error(f"Agent error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "agent_error",
            "message": str(e),
        })
        await send_event(websocket, "agent_status", {"status": "error"})


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

    # Send current todos (from harness - agent-created)
    todos = runtime.get_harness_todos()
    await send_event(websocket, "todos_updated", {"todos": todos})

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
    """Handle creating a new todo (user-initiated, uses harness TodoCreate)."""
    content = message.get("content", "")
    if not content:
        return

    try:
        loop = asyncio.get_event_loop()

        def create_todo() -> str:
            tool_call = ToolCall(
                id=str(uuid.uuid4()),
                name="TodoCreate",
                arguments={"content": content},
            )
            result = runtime.harness.execute(tool_call)
            return result.content

        await loop.run_in_executor(None, create_todo)

        # Send updated todos from harness
        todos = runtime.get_harness_todos()
        await send_event(websocket, "todos_updated", {"todos": todos})

    except Exception as e:
        logger.error(f"Todo create error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "todo_error",
            "message": str(e),
        })


async def handle_todo_update(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle updating a todo status (user-initiated, uses harness tools)."""
    todo_id = message.get("id")
    status = message.get("status")

    if not todo_id or not status:
        return

    try:
        loop = asyncio.get_event_loop()

        def update_todo() -> str:
            # Map status to appropriate harness tool
            # pending -> in_progress: TodoStart
            # in_progress -> claimed: TodoClaim
            # claimed -> verified: TodoVerify
            if status == "in_progress":
                tool_call = ToolCall(
                    id=str(uuid.uuid4()),
                    name="TodoStart",
                    arguments={"id": todo_id},
                )
            elif status == "claimed":
                tool_call = ToolCall(
                    id=str(uuid.uuid4()),
                    name="TodoClaim",
                    arguments={"id": todo_id, "evidence": []},
                )
            elif status == "verified":
                tool_call = ToolCall(
                    id=str(uuid.uuid4()),
                    name="TodoVerify",
                    arguments={"id": todo_id},
                )
            else:
                return "Invalid status"

            result = runtime.harness.execute(tool_call)
            return result.content

        await loop.run_in_executor(None, update_todo)

        # Send updated todos from harness
        todos = runtime.get_harness_todos()
        await send_event(websocket, "todos_updated", {"todos": todos})

    except Exception as e:
        logger.error(f"Todo update error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "todo_error",
            "message": str(e),
        })


async def handle_get_state(websocket: WebSocket, runtime: SessionRuntime) -> None:
    """Handle request for full state."""
    browser_state = None
    if runtime.browser_service:
        browser_state = await get_browser_state(runtime)

    # Get todos from harness (agent-created)
    todos = runtime.get_harness_todos()

    await websocket.send_json({
        "type": "state",
        "data": {
            "messages": runtime.messages,
            "todos": todos,
            "terminal_output": runtime.terminal_output,
            "browser_state": browser_state,
            "browser_control": runtime.browser_control,
            "is_paused": runtime.is_paused,
            "pause_reason": runtime.pause_reason,
        },
    })


# ============================================================================
# Human Intervention Handlers
# ============================================================================


async def handle_pause_session(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle pausing the agent session (human intervention).

    When paused:
    - Agent loop stops executing new steps
    - User can edit todos, approve/reject claims, add notes
    - Agent resumes when user calls resume
    """
    reason = message.get("reason", "User requested pause")

    runtime.is_paused = True
    runtime.pause_reason = reason

    runtime.log_audit_event(
        event_type="SESSION_PAUSED",
        todo_id="",
        details={"reason": reason, "actor": "human"},
    )

    await send_event(websocket, "session_paused", {
        "is_paused": True,
        "reason": reason,
    })

    logger.info(f"Session {runtime.session_id} paused: {reason}")


async def handle_resume_session(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle resuming the agent session after pause."""
    feedback = message.get("feedback", "")

    runtime.is_paused = False
    runtime.pause_reason = ""

    runtime.log_audit_event(
        event_type="SESSION_RESUMED",
        todo_id="",
        details={"feedback": feedback, "actor": "human"},
    )

    await send_event(websocket, "session_resumed", {
        "is_paused": False,
        "feedback": feedback,
    })

    logger.info(f"Session {runtime.session_id} resumed")


async def handle_todo_approve(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle human approval of a claimed todo (override auditor).

    This is a human override that moves a todo from 'claimed' to 'verified'
    without waiting for auditor approval.
    """
    todo_id = message.get("id")
    reason = message.get("reason", "Human approved")

    if not todo_id:
        await websocket.send_json({
            "type": "error",
            "code": "missing_todo_id",
            "message": "Todo ID is required for approval",
        })
        return

    try:
        todos = runtime.harness._todos
        if todo_id not in todos:
            raise ValueError(f"Todo '{todo_id}' not found")

        todo = todos[todo_id]
        current_status = todo.get("status", "pending")

        # Can only approve claimed todos
        if current_status != "claimed":
            raise ValueError(
                f"Cannot approve todo '{todo_id}': status is '{current_status}', "
                f"but only 'claimed' todos can be approved"
            )

        # Update status
        todo["status"] = "verified"
        todo["review_status"] = "overridden"
        todo["verified_at"] = datetime.utcnow().isoformat()
        todo["verified_by"] = "human"
        todo["override_reason"] = reason

        # Increment version
        runtime.harness._todo_version += 1

        runtime.log_audit_event(
            event_type="TODO_APPROVED_BY_HUMAN",
            todo_id=todo_id,
            details={"reason": reason, "actor": "human"},
        )

        # Send updated todos
        todos_list = runtime.get_harness_todos()
        await send_event(websocket, "todos_updated", {"todos": todos_list})
        await send_event(websocket, "todo_approved", {
            "id": todo_id,
            "reason": reason,
            "verified_by": "human",
        })

        logger.info(f"Todo {todo_id} approved by human: {reason}")

    except Exception as e:
        logger.error(f"Todo approve error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "todo_error",
            "message": str(e),
        })


async def handle_todo_reject(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle human rejection of a claimed todo (send back to agent).

    This moves a todo from 'claimed' back to 'in_progress' with feedback
    for the agent to address.
    """
    todo_id = message.get("id")
    reason = message.get("reason", "")
    feedback = message.get("feedback", "")

    if not todo_id:
        await websocket.send_json({
            "type": "error",
            "code": "missing_todo_id",
            "message": "Todo ID is required for rejection",
        })
        return

    if not reason and not feedback:
        await websocket.send_json({
            "type": "error",
            "code": "missing_feedback",
            "message": "Reason or feedback is required for rejection",
        })
        return

    try:
        todos = runtime.harness._todos
        if todo_id not in todos:
            raise ValueError(f"Todo '{todo_id}' not found")

        todo = todos[todo_id]
        current_status = todo.get("status", "pending")

        # Can only reject claimed todos
        if current_status != "claimed":
            raise ValueError(
                f"Cannot reject todo '{todo_id}': status is '{current_status}', "
                f"but only 'claimed' todos can be rejected"
            )

        # Update status - send back to in_progress
        todo["status"] = "in_progress"
        todo["review_status"] = "changes_requested"
        todo["revision_attempts"] = todo.get("revision_attempts", 0) + 1
        todo["auditor_feedback"] = feedback or reason

        # Add to human notes
        if "human_notes" not in todo:
            todo["human_notes"] = []
        todo["human_notes"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "rejection",
            "reason": reason,
            "feedback": feedback,
        })

        # Increment version
        runtime.harness._todo_version += 1

        runtime.log_audit_event(
            event_type="TODO_REJECTED_BY_HUMAN",
            todo_id=todo_id,
            details={"reason": reason, "feedback": feedback, "actor": "human"},
        )

        # Send updated todos
        todos_list = runtime.get_harness_todos()
        await send_event(websocket, "todos_updated", {"todos": todos_list})
        await send_event(websocket, "todo_rejected", {
            "id": todo_id,
            "reason": reason,
            "feedback": feedback,
        })

        logger.info(f"Todo {todo_id} rejected by human: {reason}")

    except Exception as e:
        logger.error(f"Todo reject error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "todo_error",
            "message": str(e),
        })


async def handle_todo_add_note(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle adding a human note to a todo."""
    todo_id = message.get("id")
    note = message.get("note", "")

    if not todo_id or not note:
        await websocket.send_json({
            "type": "error",
            "code": "missing_params",
            "message": "Todo ID and note are required",
        })
        return

    try:
        todos = runtime.harness._todos
        if todo_id not in todos:
            raise ValueError(f"Todo '{todo_id}' not found")

        todo = todos[todo_id]

        # Add to human notes
        if "human_notes" not in todo:
            todo["human_notes"] = []
        todo["human_notes"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "note",
            "content": note,
        })

        # Increment version
        runtime.harness._todo_version += 1

        runtime.log_audit_event(
            event_type="TODO_NOTE_ADDED",
            todo_id=todo_id,
            details={"note": note, "actor": "human"},
        )

        # Send updated todos
        todos_list = runtime.get_harness_todos()
        await send_event(websocket, "todos_updated", {"todos": todos_list})

        logger.info(f"Note added to todo {todo_id}")

    except Exception as e:
        logger.error(f"Todo add note error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "todo_error",
            "message": str(e),
        })


async def handle_todo_edit(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle editing a todo's content (human intervention)."""
    todo_id = message.get("id")
    new_content = message.get("content")

    if not todo_id or not new_content:
        await websocket.send_json({
            "type": "error",
            "code": "missing_params",
            "message": "Todo ID and content are required",
        })
        return

    try:
        todos = runtime.harness._todos
        if todo_id not in todos:
            raise ValueError(f"Todo '{todo_id}' not found")

        todo = todos[todo_id]
        old_content = todo.get("content", "")

        # Update content
        todo["content"] = new_content
        todo["edited_at"] = datetime.utcnow().isoformat()
        todo["edited_by"] = "human"

        # Increment version
        runtime.harness._todo_version += 1

        runtime.log_audit_event(
            event_type="TODO_EDITED_BY_HUMAN",
            todo_id=todo_id,
            details={"old_content": old_content, "new_content": new_content, "actor": "human"},
        )

        # Send updated todos
        todos_list = runtime.get_harness_todos()
        await send_event(websocket, "todos_updated", {"todos": todos_list})

        logger.info(f"Todo {todo_id} edited by human")

    except Exception as e:
        logger.error(f"Todo edit error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "todo_error",
            "message": str(e),
        })


async def handle_todo_delete(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle deleting a todo (human intervention)."""
    todo_id = message.get("id")

    if not todo_id:
        await websocket.send_json({
            "type": "error",
            "code": "missing_todo_id",
            "message": "Todo ID is required for deletion",
        })
        return

    try:
        todos = runtime.harness._todos
        if todo_id not in todos:
            raise ValueError(f"Todo '{todo_id}' not found")

        todo = todos[todo_id]

        # Remove the todo
        del todos[todo_id]

        # Increment version
        runtime.harness._todo_version += 1

        runtime.log_audit_event(
            event_type="TODO_DELETED_BY_HUMAN",
            todo_id=todo_id,
            details={"content": todo.get("content", ""), "actor": "human"},
        )

        # Send updated todos
        todos_list = runtime.get_harness_todos()
        await send_event(websocket, "todos_updated", {"todos": todos_list})

        logger.info(f"Todo {todo_id} deleted by human")

    except Exception as e:
        logger.error(f"Todo delete error: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "todo_error",
            "message": str(e),
        })


async def handle_get_audit_log(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle request for audit log."""
    todo_id = message.get("id")  # Optional filter by todo

    events = runtime.audit_events
    if todo_id:
        events = [e for e in events if e.get("todo_id") == todo_id]

    await websocket.send_json({
        "type": "audit_log",
        "data": {"events": events},
    })


@app.get("/api/sessions")
async def list_sessions(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """
    List all persisted sessions from RunStore.

    Gap 4: Session Continuity - allows users to see all past sessions.

    Args:
        status: Optional filter by status (pending, running, paused, completed, failed, interrupted)
        limit: Maximum number of sessions to return
        offset: Number of sessions to skip for pagination

    Returns:
        List of session metadata with id, status, task_description, timestamps, etc.
    """
    try:
        status_filter = RunStatus(status) if status else None
    except ValueError:
        status_filter = None

    runs = run_store.list_runs(status=status_filter, limit=limit, offset=offset)

    return {
        "sessions": [
            {
                "id": run.run_id,
                "status": run.status.value,
                "title": run.task_description or f"Session {run.run_id[:8]}",
                "task_description": run.task_description,
                "created_at": run.created_at.isoformat(),
                "updated_at": run.updated_at.isoformat(),
                "step_count": run.step_count,
                "tool_calls_count": run.tool_calls_count,
                "error_message": run.error_message,
                "tags": run.tags,
            }
            for run in runs
        ],
        "total": len(runs),
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/sessions/resumable")
async def list_resumable_sessions() -> dict[str, Any]:
    """
    List all sessions that can be resumed (paused or interrupted).

    Gap 4: Session Continuity - allows users to see which sessions can be resumed.

    Returns:
        List of resumable session metadata.
    """
    runs = run_store.get_resumable_runs()

    return {
        "sessions": [
            {
                "id": run.run_id,
                "status": run.status.value,
                "title": run.task_description or f"Session {run.run_id[:8]}",
                "task_description": run.task_description,
                "created_at": run.created_at.isoformat(),
                "updated_at": run.updated_at.isoformat(),
                "step_count": run.step_count,
                "tool_calls_count": run.tool_calls_count,
            }
            for run in runs
        ],
    }


@app.get("/api/sessions/{session_id}")
async def get_persisted_session(session_id: str) -> dict[str, Any]:
    """
    Get details of a persisted session including conversation history.

    Gap 4: Session Continuity - allows viewing full session state.

    Args:
        session_id: The session ID to retrieve

    Returns:
        Full session data including messages and metadata.
    """
    saved_run = run_store.load_run(session_id)
    if not saved_run:
        return {"error": "Session not found", "session_id": session_id}

    return {
        "id": saved_run.metadata.run_id,
        "status": saved_run.metadata.status.value,
        "title": saved_run.metadata.task_description or f"Session {session_id[:8]}",
        "task_description": saved_run.metadata.task_description,
        "created_at": saved_run.metadata.created_at.isoformat(),
        "updated_at": saved_run.metadata.updated_at.isoformat(),
        "step_count": saved_run.metadata.step_count,
        "tool_calls_count": saved_run.metadata.tool_calls_count,
        "error_message": saved_run.metadata.error_message,
        "tags": saved_run.metadata.tags,
        "messages": [msg.to_dict() for msg in saved_run.session.messages] if saved_run.session else [],
        "system_prompt": saved_run.session.system_prompt if saved_run.session else None,
    }


@app.post("/api/sessions/{session_id}/resume")
async def resume_session(session_id: str) -> dict[str, Any]:
    """
    Resume a paused or interrupted session.

    Gap 4: Session Continuity - allows users to resume interrupted sessions.

    This loads the session from RunStore and creates a new active runtime
    with the restored conversation history.

    Args:
        session_id: The session ID to resume

    Returns:
        The resumed session info with a new runtime session ID.
    """
    saved_run = run_store.load_run(session_id)
    if not saved_run:
        return {"error": "Session not found", "session_id": session_id}

    if saved_run.metadata.status not in [RunStatus.PAUSED, RunStatus.INTERRUPTED]:
        return {
            "error": f"Session cannot be resumed (status: {saved_run.metadata.status.value})",
            "session_id": session_id,
        }

    if not saved_run.session:
        return {"error": "Session has no conversation history to resume", "session_id": session_id}

    # Create a new runtime with the restored session
    runtime = create_session_runtime(session_id)

    # Restore messages from the saved session
    for msg in saved_run.session.messages:
        runtime.messages.append(msg.to_dict())

    # Update the session status to running
    run_store.update_status(session_id, RunStatus.RUNNING)

    # Store the runtime
    sessions[session_id] = runtime

    return {
        "id": session_id,
        "status": "running",
        "title": saved_run.metadata.task_description or f"Session {session_id[:8]}",
        "message_count": len(runtime.messages),
        "resumed_from": saved_run.metadata.status.value,
        "created_at": runtime.created_at,
    }


@app.post("/api/sessions/{session_id}/save")
async def save_session(session_id: str, task_description: str = "") -> dict[str, Any]:
    """
    Save the current session state to RunStore.

    Gap 4: Session Continuity - allows persisting session state.

    Args:
        session_id: The session ID to save
        task_description: Optional description of the task

    Returns:
        Confirmation of the save operation.
    """
    if session_id not in sessions:
        return {"error": "Session not found in active sessions", "session_id": session_id}

    runtime = sessions[session_id]

    # Create a Session object from the runtime messages
    from compymac.message import Message, Role

    session = Session(id=session_id, system_prompt=AGENT_SYSTEM_PROMPT)
    for msg_dict in runtime.messages:
        role_str = msg_dict.get("role", "user")
        role = Role.USER if role_str == "user" else Role.ASSISTANT if role_str == "assistant" else Role.SYSTEM
        content = msg_dict.get("content", "")
        session.add_message(Message(role=role, content=content))

    # Determine status based on runtime state
    status = RunStatus.PAUSED if runtime.is_paused else RunStatus.RUNNING

    # Save to RunStore
    run_store.save_run(
        run_id=session_id,
        session=session,
        status=status,
        task_description=task_description or f"Session {session_id[:8]}",
        step_count=len(runtime.messages),
        tool_calls_count=len([m for m in runtime.messages if m.get("tool_calls")]),
    )

    return {
        "id": session_id,
        "status": status.value,
        "saved_at": datetime.utcnow().isoformat(),
        "message_count": len(runtime.messages),
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    """
    Delete a persisted session from RunStore.

    Args:
        session_id: The session ID to delete

    Returns:
        Confirmation of the delete operation.
    """
    success = run_store.delete_run(session_id)

    # Also remove from active sessions if present
    if session_id in sessions:
        del sessions[session_id]

    return {
        "id": session_id,
        "deleted": success,
    }


# =============================================================================
# Library / PDF Upload Endpoints (Phase 1)
# =============================================================================


@app.post("/api/documents/upload")
async def upload_document(
    file: Annotated[UploadFile, File()],
    user_id: str = "default",
    library_path: str = "",
    add_to_library: bool = True,
) -> dict[str, Any]:
    """
    Upload a PDF or EPUB document for processing.

    Args:
        file: The PDF or EPUB file to upload
        user_id: User ID for library storage (default: "default")
        library_path: Relative path for folder structure (default: filename)
        add_to_library: Whether to add to persistent library (default: True)

    Returns:
        Document metadata including ID and processing status.
    """
    from compymac.ingestion.parsers import extract_navigation

    if not file.filename:
        return {"error": "No filename provided"}

    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".epub"):
        return {"error": "Only PDF and EPUB files are supported"}

    doc_format = "epub" if ext == ".epub" else "pdf"

    # Sanitize library_path
    safe_library_path = _sanitize_library_path(library_path or file.filename)

    # Create document entry
    doc = library_store.create_document(
        user_id=user_id,
        filename=file.filename,
        file_size_bytes=file.size or 0,
        library_path=safe_library_path,
        doc_format=doc_format,
    )

    try:
        # Save uploaded file with correct extension
        file_path = UPLOAD_DIR / f"{doc.id}{ext}"
        content = await file.read()
        file_path.write_bytes(content)

        # Update document with file path
        library_store.update_document(doc.id, metadata={"file_path": str(file_path)})

        # Process the document
        library_store.update_document(doc.id, status=DocumentStatus.PROCESSING)

        # Parse document
        parser = DocumentParser()
        parse_result = parser.parse(file_path)

        # Extract navigation (TOC/bookmarks)
        navigation = extract_navigation(file_path, doc_format)

        # Chunk the text
        chunker = DocumentChunker(chunk_size=512, chunk_overlap=50)
        chunks = chunker.chunk(
            text=parse_result.text,
            doc_id=doc.id,
            metadata=parse_result.metadata,
        )

        # Convert chunks to dicts for storage
        chunk_dicts = [
            {
                "id": chunk.id,
                "content": chunk.content,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "metadata": chunk.metadata,
            }
            for chunk in chunks
        ]

        # Update document with results
        page_count = parse_result.metadata.get("page_count", 0)
        if doc_format == "epub":
            # For EPUB, use chapter count as "page count"
            page_count = parse_result.metadata.get("chapter_count", 0)

        library_store.update_document(
            doc.id,
            status=DocumentStatus.READY,
            page_count=page_count,
            chunks=chunk_dicts,
            metadata=parse_result.metadata,
            navigation=navigation,
        )

        doc = library_store.get_document(doc.id)
        return doc.to_dict() if doc else {"error": "Document not found after processing"}

    except Exception as e:
        logger.error(f"Error processing document {doc.id}: {e}")
        library_store.update_document(
            doc.id,
            status=DocumentStatus.FAILED,
            error=str(e),
        )
        doc = library_store.get_document(doc.id)
        return doc.to_dict() if doc else {"error": str(e)}


def _sanitize_library_path(path: str) -> str:
    """Sanitize user-provided path to prevent traversal attacks."""
    # Normalize separators
    path = path.replace("\\", "/")
    # Remove dangerous components
    parts = [p for p in path.split("/") if p and p != ".." and not p.startswith(".")]
    # Rejoin
    return "/".join(parts)


@app.post("/api/documents/upload-batch")
async def upload_batch(
    files: Annotated[list[UploadFile], File()],
    relative_paths: Annotated[list[str] | None, Form()] = None,
    user_id: str = "default",
) -> dict[str, Any]:
    """
    Upload multiple documents with preserved folder structure.

    Args:
        files: List of files to upload
        relative_paths: Corresponding relative paths (from webkitRelativePath)
        user_id: User ID for library storage

    Returns:
        Batch upload results with per-file status.
    """
    from compymac.ingestion.parsers import extract_navigation

    results = []

    # Handle None relative_paths
    paths = relative_paths or []

    # Ensure paths matches files length
    if len(paths) < len(files):
        # Pad with filenames if not enough paths provided
        paths = list(paths) + [
            f.filename or f"file_{i}" for i, f in enumerate(files[len(paths):])
        ]

    for file, rel_path in zip(files, paths, strict=False):
        if not file.filename:
            results.append({
                "filename": "unknown",
                "id": None,
                "status": "failed",
                "error": "No filename provided",
            })
            continue

        # Validate file type
        ext = Path(file.filename).suffix.lower()
        if ext not in (".pdf", ".epub"):
            results.append({
                "filename": file.filename,
                "id": None,
                "status": "failed",
                "error": "Only PDF and EPUB files are supported",
            })
            continue

        doc_format = "epub" if ext == ".epub" else "pdf"
        safe_path = _sanitize_library_path(rel_path)

        try:
            # Create document entry
            doc = library_store.create_document(
                user_id=user_id,
                filename=file.filename,
                file_size_bytes=file.size or 0,
                library_path=safe_path,
                doc_format=doc_format,
            )

            # Save uploaded file
            file_path = UPLOAD_DIR / f"{doc.id}{ext}"
            content = await file.read()
            file_path.write_bytes(content)

            # Update document with file path
            library_store.update_document(doc.id, metadata={"file_path": str(file_path)})

            # Process the document
            library_store.update_document(doc.id, status=DocumentStatus.PROCESSING)

            # Parse document
            parser = DocumentParser()
            parse_result = parser.parse(file_path)

            # Extract navigation
            navigation = extract_navigation(file_path, doc_format)

            # Chunk the text
            chunker = DocumentChunker(chunk_size=512, chunk_overlap=50)
            chunks = chunker.chunk(
                text=parse_result.text,
                doc_id=doc.id,
                metadata=parse_result.metadata,
            )

            # Convert chunks to dicts
            chunk_dicts = [
                {
                    "id": chunk.id,
                    "content": chunk.content,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "metadata": chunk.metadata,
                }
                for chunk in chunks
            ]

            # Update document with results
            page_count = parse_result.metadata.get("page_count", 0)
            if doc_format == "epub":
                page_count = parse_result.metadata.get("chapter_count", 0)

            library_store.update_document(
                doc.id,
                status=DocumentStatus.READY,
                page_count=page_count,
                chunks=chunk_dicts,
                metadata=parse_result.metadata,
                navigation=navigation,
            )

            results.append({
                "filename": file.filename,
                "id": doc.id,
                "status": "ready",
                "library_path": safe_path,
                "navigation_count": len(navigation),
            })

        except Exception as e:
            logger.error(f"Error processing {file.filename}: {e}")
            results.append({
                "filename": file.filename,
                "id": None,
                "status": "failed",
                "error": str(e),
            })

    return {
        "total_files": len(files),
        "results": results,
        "success_count": sum(1 for r in results if r["status"] == "ready"),
        "failure_count": sum(1 for r in results if r["status"] == "failed"),
    }


@app.get("/api/documents/{document_id}")
async def get_document(document_id: str) -> dict[str, Any]:
    """Get document details by ID, including chunks."""
    doc = library_store.get_document(document_id)
    if not doc:
        return {"error": "Document not found"}
    result = doc.to_dict()
    # Include chunks for content viewing
    result["chunks"] = doc.chunks
    # Include full metadata for OCR info
    result["metadata"] = doc.metadata
    return result


@app.get("/api/documents/{document_id}/epub/chapter")
async def get_epub_chapter(
    document_id: str,
    href: str | None = None,
    chapter_index: int | None = None,
) -> dict[str, Any]:
    """
    Get a sanitized EPUB chapter for rendering.

    Args:
        document_id: UUID of the document
        href: Chapter href (e.g., "chapter1.xhtml")
        chapter_index: Chapter index (0-based), used if href is None

    Returns:
        Sanitized chapter HTML with scoped CSS
    """
    from compymac.ingestion.epub_renderer import render_epub_chapter

    doc = library_store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify it's an EPUB
    if doc.doc_format != "epub":
        raise HTTPException(status_code=400, detail="Document is not an EPUB")

    # Get file path from metadata
    file_path = doc.metadata.get("file_path")
    if not file_path:
        # Try chunks metadata
        if doc.chunks and doc.chunks[0].get("metadata", {}).get("filepath"):
            file_path = doc.chunks[0]["metadata"]["filepath"]

    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Document file not found")

    # Security: validate file is in upload directory
    upload_dir = Path("/tmp/compymac_uploads").resolve()
    file_path_resolved = Path(file_path).resolve()
    if not str(file_path_resolved).startswith(str(upload_dir)):
        raise HTTPException(status_code=403, detail="Access denied")

    # Render chapter
    chapter_data = render_epub_chapter(
        epub_path=file_path,
        href=href,
        chapter_index=chapter_index,
    )

    if not chapter_data:
        raise HTTPException(status_code=404, detail="Chapter not found")

    return chapter_data


@app.get("/api/documents/{document_id}/epub/chapters")
async def list_epub_chapters(document_id: str) -> dict[str, Any]:
    """
    List all chapters in an EPUB document.

    Args:
        document_id: UUID of the document

    Returns:
        List of chapters with href, title, and index
    """
    from compymac.ingestion.epub_renderer import get_epub_renderer

    doc = library_store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify it's an EPUB
    if doc.doc_format != "epub":
        raise HTTPException(status_code=400, detail="Document is not an EPUB")

    # Get file path from metadata
    file_path = doc.metadata.get("file_path")
    if not file_path:
        if doc.chunks and doc.chunks[0].get("metadata", {}).get("filepath"):
            file_path = doc.chunks[0]["metadata"]["filepath"]

    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Document file not found")

    # Security: validate file is in upload directory
    upload_dir = Path("/tmp/compymac_uploads").resolve()
    file_path_resolved = Path(file_path).resolve()
    if not str(file_path_resolved).startswith(str(upload_dir)):
        raise HTTPException(status_code=403, detail="Access denied")

    renderer = get_epub_renderer()
    chapters = renderer.get_chapter_list(file_path)

    return {
        "document_id": document_id,
        "chapters": chapters,
        "count": len(chapters),
    }


@app.get("/api/documents/{document_id}/pages/{page_num}.png")
async def get_document_page_image(
    document_id: str,
    page_num: int,
    dpi: int = 150,
) -> Response:
    """
    Render a PDF page as a PNG image.

    Args:
        document_id: UUID of the document
        page_num: 1-indexed page number
        dpi: Resolution (default 150)

    Returns:
        PNG image of the rendered page
    """
    import fitz

    doc = library_store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get file path from metadata
    file_path = doc.metadata.get("file_path")
    if not file_path:
        # Try chunks metadata
        if doc.chunks and doc.chunks[0].get("metadata", {}).get("filepath"):
            file_path = doc.chunks[0]["metadata"]["filepath"]

    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Document file not found")

    # Security: validate file is in upload directory
    upload_dir = Path("/tmp/compymac_uploads").resolve()
    file_path_resolved = Path(file_path).resolve()
    if not str(file_path_resolved).startswith(str(upload_dir)):
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate page number
    if page_num < 1 or page_num > doc.page_count:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid page number. Document has {doc.page_count} pages.",
        )

    # Render page to image
    try:
        pdf_doc = fitz.open(file_path)
        page = pdf_doc[page_num - 1]  # 0-indexed
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        image_bytes = pix.tobytes("png")
        pdf_doc.close()

        return Response(content=image_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to render page: {e}"
        ) from e


@app.get("/api/library")
async def list_library(user_id: str = "default") -> dict[str, Any]:
    """List all documents in a user's library."""
    docs = library_store.get_user_documents(user_id)
    return {
        "user_id": user_id,
        "documents": [doc.to_dict() for doc in docs],
        "count": len(docs),
    }


@app.delete("/api/library/{document_id}")
async def delete_library_document(document_id: str) -> dict[str, Any]:
    """Delete a document from the library."""
    doc = library_store.get_document(document_id)
    if not doc:
        return {"error": "Document not found"}

    # Delete the uploaded file if it exists
    if doc.metadata.get("file_path"):
        file_path = Path(doc.metadata["file_path"])
        if file_path.exists():
            file_path.unlink()

    success = library_store.delete_document(document_id)
    return {"id": document_id, "deleted": success}


@app.post("/api/library/search")
async def search_library(
    query: str,
    document_ids: list[str] | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """
    Search for relevant chunks in library documents.

    Args:
        query: Search query
        document_ids: Optional list of document IDs to search (default: all)
        top_k: Number of results to return (default: 5)

    Returns:
        List of relevant chunks with citations.
    """
    results = library_store.search_chunks(
        query=query,
        doc_ids=document_ids,
        top_k=top_k,
    )
    return {
        "query": query,
        "results": results,
        "count": len(results),
    }


@app.post("/api/library/{document_id}/activate")
async def activate_document(document_id: str, session_id: str) -> dict[str, Any]:
    """Add a document to active sources for a session."""
    success = library_store.add_active_source(session_id, document_id)
    if not success:
        return {"error": "Document not found"}
    return {"document_id": document_id, "session_id": session_id, "activated": True}


@app.post("/api/library/{document_id}/deactivate")
async def deactivate_document(document_id: str, session_id: str) -> dict[str, Any]:
    """Remove a document from active sources for a session."""
    success = library_store.remove_active_source(session_id, document_id)
    return {"document_id": document_id, "session_id": session_id, "deactivated": success}


@app.get("/api/library/active")
async def get_active_sources(session_id: str) -> dict[str, Any]:
    """Get all active source documents for a session."""
    docs = library_store.get_active_sources(session_id)
    return {
        "session_id": session_id,
        "documents": [doc.to_dict() for doc in docs],
        "count": len(docs),
    }


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
